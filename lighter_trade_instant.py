#!/usr/bin/env python3
# INSTANT-only trading loop (direction-aware, single position)
# MARKET orders (no-guard), client-side TP/SL watcher
# Daily risk control + Startup watermark (ignore existing signal)

import os, sys, math, time, json, asyncio, logging, inspect, pathlib, datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# ========= ENV =========
load_dotenv()

MAINNET_URL        = os.getenv("LIGHTER_MAINNET_URL", "").strip()
MARKET_ID          = int(os.getenv("LIGHTER_MAINNET_MARKET_ID", "1"))
TARGET_NOTIONAL    = float(os.getenv("TARGET_NOTIONAL_USDC", "1.0"))
ACCOUNT_LEVERAGE   = float(os.getenv("ACCOUNT_LEVERAGE", "10.0"))
PRICE_HINT_USD     = float(os.getenv("PRICE_HINT_USD", "110000"))
SAFETY_RATIO       = float(os.getenv("SAFETY_RATIO", "0.98"))
TP_PCT             = float(os.getenv("TP_PCT_INS", "0.02"))
SL_PCT             = float(os.getenv("SL_PCT_INS", "0.01"))
WATCH_INTERVAL_SEC = float(os.getenv("WATCH_INTERVAL_SEC", "1.0"))
WATCH_TIMEOUT_SEC  = float(os.getenv("WATCH_TIMEOUT_SEC", "3600"))
SIGNAL_POLL_SEC    = float(os.getenv("SIGNAL_POLL_SEC", "2.0"))

PRIVATE_KEY        = os.getenv("LIGHTER_MAINNET_PRIVATE_KEY", "").strip()
ACCOUNT_INDEX      = int(os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX", "0"))
API_KEY_INDEX      = int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX", "0"))

# === Daily risk ===
MAX_DD_USD         = float(os.getenv("MAX_DD_USD", "2.0"))
TARGET_PNL_USD     = float(os.getenv("TARGET_PNL_USD", "3.0"))
DAILY_TZ           = os.getenv("DAILY_TZ", "Europe/Istanbul")
RISK_FILE          = os.getenv("RISK_FILE", ".risk/day_pnl.json")

# ========= LOG =========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("instant-direction-dd")

# ========= SDK =========
import lighter
VERY_HIGH_CAP_CENTS = 2_147_483_647

# ========= TZ / Risk helpers =========
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(DAILY_TZ)
except Exception:
    _TZ = None

def now_in_tz() -> datetime.datetime:
    return datetime.datetime.now(tz=_TZ) if _TZ else datetime.datetime.now()

def day_key() -> str:
    return now_in_tz().strftime("%Y-%m-%d")

def _ensure_risk_dir():
    pathlib.Path(os.path.dirname(RISK_FILE) or ".").mkdir(parents=True, exist_ok=True)

def load_risk() -> Dict[str, Any]:
    _ensure_risk_dir()
    if not os.path.exists(RISK_FILE): return {}
    try:
        with open(RISK_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

def save_risk(state: Dict[str, Any]) -> None:
    _ensure_risk_dir()
    tmp = RISK_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RISK_FILE)

def get_today_pnl(state: Dict[str, Any]) -> float:
    return float(state.get(day_key(), {}).get("pnl_usd", 0.0))

def add_today_pnl(state: Dict[str, Any], delta: float) -> None:
    key = day_key()
    day = state.get(key) or {}
    day["pnl_usd"] = float(day.get("pnl_usd", 0.0)) + float(delta)
    state[key] = day

def reset_if_new_day(state: Dict[str, Any]) -> None:
    pass

# ========= DB (database.db_signals) =========
async def _maybe_await(x): return await x if inspect.isawaitable(x) else x

def _to_dict_like(sig: Any) -> Optional[Dict[str, Any]]:
    if sig is None: return None
    if isinstance(sig, dict): return sig
    d: Dict[str, Any] = {}
    for key in ("id","type","signal_type","kind","direction","side","symbol","tp_pct","sl_pct","notional_usd","status","ts"):
        if hasattr(sig, key): d[key] = getattr(sig, key)
    if hasattr(sig, "__dict__"): d.update({k:v for k,v in sig.__dict__.items() if k not in d})
    return d or {"value": sig}

async def fetch_active_signal() -> Optional[Dict[str, Any]]:
    try:
        from database import db, db_signals
    except Exception as e:
        log.warning(f"database importu yapılamadı: {e}")
        return None

    if hasattr(db_signals, "get_active_signal"):
        try:
            sig = await _maybe_await(db_signals.get_active_signal(signal_type="INSTANT"))
            return _to_dict_like(sig)
        except Exception as e:
            log.warning(f"db_signals.get_active_signal(INSTANT) hata: {e}")
    return None

# ========= Market helpers =========
def snap_down(x: float, step: float) -> float:
    if step <= 0: return x
    return math.floor(x / step) * step

async def fetch_mark_and_params(ord_api, market_id: int, price_hint: float):
    try:
        ob = await ord_api.order_book_orders(market_id=market_id, limit=1)
        if getattr(ob, "bids", None) and getattr(ob, "asks", None):
            best_bid = float(ob.bids[0].price)
            best_ask = float(ob.asks[0].price)
            mark = (best_bid + best_ask) / 2.0
        else: raise ValueError("empty orderbook")
    except Exception as e:
        log.warning(f"order_book_orders failed: {e} — fallback={price_hint}")
        best_bid = best_ask = mark = price_hint

    base_lot = 0.000001; price_tick = 0.01
    try:
        det = await ord_api.order_book_details(market_id=market_id)
        base_lot   = float(getattr(det, "base_lot_size", None) or getattr(det, "base_step", None) or 0.000001)
        price_tick = float(getattr(det, "price_tick_size", None) or getattr(det, "price_step", None) or 0.01)
    except Exception: pass
    return mark, best_bid, best_ask, base_lot, price_tick

async def place_market_open_no_guard(signer, market_id: int, lots: int, direction: str):
    coid = int(time.time() % 1_000_000)
    direction = direction.lower()
    if direction == "long":
        tx, tx_hash, err = await signer.create_market_order(market_index=market_id, client_order_index=coid, base_amount=lots, is_ask=0, avg_execution_price=VERY_HIGH_CAP_CENTS, reduce_only=0)
    elif direction == "short":
        tx, tx_hash, err = await signer.create_market_order(market_index=market_id, client_order_index=coid, base_amount=lots, is_ask=1, avg_execution_price=1, reduce_only=0)
    else: raise ValueError(f"Unsupported direction: {direction}")
    if err: raise RuntimeError(f"OPEN rejected: {err}")
    log.info(f"✅ OPEN accepted. tx_hash={tx_hash}")
    return tx_hash

async def market_close_reduce_only_no_guard(signer, market_id: int, lots: int, direction: str) -> bool:
    direction = direction.lower()
    for i in range(1, 6):
        coid = int(time.time() % 1_000_000) + 999 + i
        try:
            if direction == "long":
                tx, txh, err = await signer.create_market_order(market_index=market_id, client_order_index=coid, base_amount=lots, is_ask=1, avg_execution_price=1, reduce_only=1)
            elif direction == "short":
                tx, txh, err = await signer.create_market_order(market_index=market_id, client_order_index=coid, base_amount=lots, is_ask=0, avg_execution_price=VERY_HIGH_CAP_CENTS, reduce_only=1)
            else: raise ValueError(f"Unsupported direction: {direction}")
        except Exception as e:
            log.warning(f"MARKET close try#{i}: {e}")
            await asyncio.sleep(0.25*i)
            continue
        if err:
            log.warning(f"MARKET close rejected try#{i}: {err}")
            await asyncio.sleep(0.25*i)
        else:
            log.info(f"✅ MARKET close accepted tx_hash={txh}")
            return True
    log.error("❌ MARKET close reddedildi.")
    return False

async def tp_sl_watcher_market_close(signer, ord_api, market_id, lots, tp_usd, sl_usd, direction):
    direction = direction.lower()
    log.info(f"👀 TP/SL watcher aktif: dir={direction} TP={tp_usd:.2f} SL={sl_usd:.2f}")
    start = time.time()
    while time.time() - start < WATCH_TIMEOUT_SEC:
        try:
            ob = await ord_api.order_book_orders(market_id=market_id, limit=1)
            if getattr(ob, "bids", None) and getattr(ob, "asks", None):
                bid, ask = float(ob.bids[0].price), float(ob.asks[0].price)
                mark = (bid + ask)/2.0
            else: mark = PRICE_HINT_USD
            log.info(f"⏱️ mark={mark:,.2f}")
            if direction == "long":
                if mark >= tp_usd:
                    log.info("🎯 TP hit (long)")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots, "long")
                    return ("tp_ok" if ok else "tp_fail", mark)
                if mark <= sl_usd:
                    log.info("🛑 SL hit (long)")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots, "long")
                    return ("sl_ok" if ok else "sl_fail", mark)
            elif direction == "short":
                if mark <= tp_usd:
                    log.info("🎯 TP hit (short)")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots, "short")
                    return ("tp_ok" if ok else "tp_fail", mark)
                if mark >= sl_usd:
                    log.info("🛑 SL hit (short)")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots, "short")
                    return ("sl_ok" if ok else "sl_fail", mark)
        except Exception as e:
            log.warning(f"watcher error: {e}")
        await asyncio.sleep(WATCH_INTERVAL_SEC)
    return ("timeout", mark)

def approx_realized_pnl_usd(entry, exit, lots, base_lot_btc, direction):
    qty_btc = lots * base_lot_btc
    return (exit - entry) * qty_btc if direction=="long" else (entry - exit) * qty_btc

# ========= MAIN LOOP =========
async def instant_loop():
    if not MAINNET_URL or not PRIVATE_KEY.startswith("0x"):
        log.error("⚠️ Lighter parametreleri eksik."); sys.exit(1)

    log.info("="*74)
    log.info("🚀 INSTANT loop + Daily Risk + Startup watermark")
    log.info("="*74)
    log.info(f"Market={MARKET_ID} | Target=${TARGET_NOTIONAL} | Lev={ACCOUNT_LEVERAGE}x")
    log.info(f"TP/SL={TP_PCT:.2%}/{SL_PCT:.2%} | DD={MAX_DD_USD:.2f} | TPday={TARGET_PNL_USD:.2f}")
    log.info("="*74)

    signer  = lighter.SignerClient(url=MAINNET_URL, private_key=PRIVATE_KEY, account_index=ACCOUNT_INDEX, api_key_index=API_KEY_INDEX)
    ord_api = lighter.OrderApi(signer.api_client)
    risk_state = load_risk()
    reset_if_new_day(risk_state)

    # --- startup watermark ---
    startup_ts = time.time()
    try:
        initial_sig = await fetch_active_signal()
    except Exception:
        initial_sig = None
    ignore_signal_id = (initial_sig or {}).get("id")
    ignore_until_ts = startup_ts
    log.info(f"🧊 Startup watermark set: ignore_signal_id={ignore_signal_id}, ts={int(ignore_until_ts)}")

    in_position=False; last_opened_signal_id=None; last_direction=None

    try:
        while True:
            reset_if_new_day(risk_state)
            today_pnl = get_today_pnl(risk_state)

            if today_pnl <= -MAX_DD_USD:
                log.warning(f"🛑 Günlük DD limitine ulaşıldı ({today_pnl:.2f}). Bugün poz yok.")
                await asyncio.sleep(SIGNAL_POLL_SEC); continue
            if today_pnl >= TARGET_PNL_USD:
                log.warning(f"✅ Günlük hedef kâr ({today_pnl:.2f}). Bugün poz yok.")
                await asyncio.sleep(SIGNAL_POLL_SEC); continue

            if not in_position:
                sig = await fetch_active_signal()
                if sig:
                    direction = (sig.get("direction") or sig.get("side") or "").lower()
                    sig_id = sig.get("id")
                    sig_ts = None
                    for key in ("created_at","createdAt","ts","timestamp","created"):
                        if key in sig and sig[key]:
                            try: sig_ts=float(sig[key])
                            except: pass
                            break

                    # --- startup ignore rules ---
                    if ignore_signal_id and sig_id == ignore_signal_id:
                        log.info(f"🧊 Startup sinyali hâlâ aktif (id={sig_id}) → yoksay.")
                        await asyncio.sleep(SIGNAL_POLL_SEC); continue
                    if sig_ts and sig_ts <= ignore_until_ts:
                        log.info(f"🧊 Açılıştan önce oluşmuş sinyal (ts={sig_ts:.0f}) → yoksay.")
                        await asyncio.sleep(SIGNAL_POLL_SEC); continue

                    if direction in ("long","short"):
                        log.info("✨ Yeni INSTANT sinyal tespit edildi.")
                        mark,_,_,base_lot,_ = await fetch_mark_and_params(ord_api, MARKET_ID, PRICE_HINT_USD)
                        base_qty_btc = (TARGET_NOTIONAL / mark) * SAFETY_RATIO
                        lots = max(1,int(base_qty_btc/base_lot))
                        log.info(f"🧮 dir={direction}, mark={mark:,.2f}, lots={lots}")

                        try:
                            _ = await place_market_open_no_guard(signer, MARKET_ID, lots, direction)
                        except Exception as e:
                            log.error(f"OPEN failed: {e}")
                            await asyncio.sleep(SIGNAL_POLL_SEC)
                            continue

                        tp_price = mark*(1+TP_PCT) if direction=="long" else mark*(1-TP_PCT)
                        sl_price = mark*(1-SL_PCT) if direction=="long" else mark*(1+SL_PCT)
                        log.info(f"🎯 TP={tp_price:,.2f} | 🛑 SL={sl_price:,.2f}")

                        in_position=True
                        last_opened_signal_id=sig_id; last_direction=direction
                        entry_mark=mark; entry_lots=lots; entry_base_lot=base_lot

                        outcome,exit_mk = await tp_sl_watcher_market_close(signer,ord_api,MARKET_ID,lots,tp_price,sl_price,direction)
                        log.info(f"Watcher outcome={outcome}")

                        pnl=approx_realized_pnl_usd(entry_mark,exit_mk,lots,base_lot,direction)
                        add_today_pnl(risk_state,pnl); save_risk(risk_state)
                        total=get_today_pnl(risk_state)
                        log.info(f"💰 Realized PnL≈{pnl:+.2f} | Günlük≈{total:+.2f}")

                        if total<=-MAX_DD_USD:
                            log.warning(f"🛑 Günlük DD limitine ulaşıldı (PnL={total:.2f}). Yeni pozlar durduruldu.")
                        if total>=TARGET_PNL_USD:
                            log.warning(f"✅ Günlük hedef kâr ulaşıldı (PnL={total:.2f}). Yeni pozlar durduruldu.")

                        # reset position and watermark update
                        in_position=False; last_direction=None
                        ignore_signal_id = sig_id
                        ignore_until_ts = time.time()

            await asyncio.sleep(SIGNAL_POLL_SEC)

    finally:
        try: await signer.close()
        except: pass


if __name__ == "__main__":
    try:
        asyncio.run(instant_loop())
    except KeyboardInterrupt:
        print("\nInterrupted.")
