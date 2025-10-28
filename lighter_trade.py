#!/usr/bin/env python3
# HYBRID-only trading loop (direction-aware, single position)
# MARKET orders (no-guard), client-side TP/SL watcher
# Daily risk control: Max Drawdown & Target Profit limits

import os, sys, math, time, json, asyncio, logging, inspect, pathlib, datetime
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv

# ========= ENV =========
load_dotenv()

MAINNET_URL        = os.getenv("LIGHTER_MAINNET_URL", "").strip()
MARKET_ID          = int(os.getenv("LIGHTER_MAINNET_MARKET_ID", "1"))
TARGET_NOTIONAL    = float(os.getenv("TARGET_NOTIONAL_USDC", "1.0"))
ACCOUNT_LEVERAGE   = float(os.getenv("ACCOUNT_LEVERAGE", "10.0"))
PRICE_HINT_USD     = float(os.getenv("PRICE_HINT_USD", "110000"))
SAFETY_RATIO       = float(os.getenv("SAFETY_RATIO", "0.98"))
TP_PCT             = float(os.getenv("TP_PCT", "0.02"))
SL_PCT             = float(os.getenv("SL_PCT", "0.01"))
WATCH_INTERVAL_SEC = float(os.getenv("WATCH_INTERVAL_SEC", "1.0"))
WATCH_TIMEOUT_SEC  = float(os.getenv("WATCH_TIMEOUT_SEC", "3600"))
SIGNAL_POLL_SEC    = float(os.getenv("SIGNAL_POLL_SEC", "2.0"))

PRIVATE_KEY        = os.getenv("LIGHTER_MAINNET_PRIVATE_KEY", "").strip()
ACCOUNT_INDEX      = int(os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX", "0"))
API_KEY_INDEX      = int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX", "0"))

# === Daily risk ===
MAX_DD_USD         = float(os.getenv("MAX_DD_USD", "2.0"))   # günlük max loss
TARGET_PNL_USD     = float(os.getenv("TARGET_PNL_USD", "3.0")) # günlük hedef kâr
DAILY_TZ           = os.getenv("DAILY_TZ", "Europe/Istanbul")
RISK_FILE          = os.getenv("RISK_FILE", ".risk/day_pnl.json")

# ========= LOG =========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hybrid-direction-dd")

# ========= SDK =========
import lighter  # pip install lighter-python
VERY_HIGH_CAP_CENTS = 2_147_483_647

# ========= TZ / Risk helpers =========
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(DAILY_TZ)
except Exception:
    _TZ = None

def now_in_tz() -> datetime.datetime:
    if _TZ:
        return datetime.datetime.now(tz=_TZ)
    return datetime.datetime.now()

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
        from database import db, db_signals  # noqa
    except Exception as e:
        log.warning(f"database importu yapılamadı: {e}")
        return None

    if hasattr(db_signals, "get_active_signal"):
        try:
            sig = await _maybe_await(db_signals.get_active_signal(signal_type="HYBRID"))
            return _to_dict_like(sig)
        except Exception as e:
            log.warning(f"db_signals.get_active_signal(HYBRID) hata: {e}")
    return None

# ========= Market/Order helpers =========
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
        log.warning(f"order_book_orders failed: {e} — using PRICE_HINT_USD")
        best_bid = best_ask = mark = price_hint

    base_lot = 0.000001; price_tick = 0.01
    try:
        det = await ord_api.order_book_details(market_id=market_id)
        base_lot   = float(getattr(det, "base_lot_size", None) or getattr(det, "base_step", None) or 0.000001)
        price_tick = float(getattr(det, "price_tick_size", None) or getattr(det, "price_step", None) or 0.01)
    except Exception as e: log.debug(f"order_book_details warn: {e}")

    return mark, best_bid, best_ask, base_lot, price_tick

async def place_market_open_no_guard(signer, market_id: int, lots: int, direction: str):
    direction = (direction or "").lower()
    coid = int(time.time() % 1_000_000)

    if direction == "long":
        log.info("📝 OPEN: MARKET BUY (no-guard)…")
        tx, tx_hash, err = await signer.create_market_order(
            market_index=market_id,
            client_order_index=coid,
            base_amount=lots,
            is_ask=0,
            avg_execution_price=VERY_HIGH_CAP_CENTS,
            reduce_only=0,
        )
    elif direction == "short":
        log.info("📝 OPEN: MARKET SELL (no-guard)…")
        tx, tx_hash, err = await signer.create_market_order(
            market_index=market_id,
            client_order_index=coid,
            base_amount=lots,
            is_ask=1,
            avg_execution_price=1,
            reduce_only=0,
        )
    else: raise ValueError(f"Unsupported direction: {direction}")

    if err: raise RuntimeError(f"OPEN rejected: {err}")
    log.info(f"✅ OPEN accepted. tx_hash={tx_hash}")
    return tx_hash

async def market_close_reduce_only_no_guard(signer, market_id: int, lots_to_close: int, direction: str) -> bool:
    direction = (direction or "").lower()
    tries = 5
    for i in range(1, tries+1):
        coid = int(time.time() % 1_000_000) + 999 + i
        try:
            if direction == "long":
                tx, txh, err = await signer.create_market_order(
                    market_index=market_id,
                    client_order_index=coid,
                    base_amount=lots_to_close,
                    is_ask=1,
                    avg_execution_price=1,
                    reduce_only=1,
                )
            elif direction == "short":
                tx, txh, err = await signer.create_market_order(
                    market_index=market_id,
                    client_order_index=coid,
                    base_amount=lots_to_close,
                    is_ask=0,
                    avg_execution_price=VERY_HIGH_CAP_CENTS,
                    reduce_only=1,
                )
            else: raise ValueError(f"Unsupported direction: {direction}")
        except Exception as e:
            log.warning(f"MARKET close raised (try#{i}): {e}")
            await asyncio.sleep(0.25*i)
            continue

        if err:
            log.warning(f"MARKET close rejected (try#{i}): {err}")
            await asyncio.sleep(0.25*i)
        else:
            log.info(f"✅ MARKET close accepted (try#{i}) tx_hash={txh}")
            return True

    log.error("❌ MARKET close tüm denemelerde reddedildi.")
    return False

# ========= TP/SL watcher =========
async def tp_sl_watcher_market_close(signer, ord_api, market_id, lots_to_close, tp_usd, sl_usd, direction: str):
    direction = (direction or "").lower()
    log.info(f"👀 TP/SL watcher (dir={direction}) active: TP={tp_usd:.2f}, SL={sl_usd:.2f}")

    start = time.time(); last_mark = None
    while time.time() - start < WATCH_TIMEOUT_SEC:
        try:
            ob = await ord_api.order_book_orders(market_id=market_id, limit=1)
            if getattr(ob, "bids", None) and getattr(ob, "asks", None):
                bid, ask = float(ob.bids[0].price), float(ob.asks[0].price)
                mark = (bid + ask)/2.0
            else: bid = ask = mark = PRICE_HINT_USD
            last_mark = mark
            log.info(f"⏱️ mark={mark:,.2f}")

            if direction == "long":
                if mark >= tp_usd:
                    log.info("🎯 TP hit (long) → SELL reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots_to_close, "long")
                    return ("tp_ok" if ok else "tp_fail", mark)
                if mark <= sl_usd:
                    log.info("🛑 SL hit (long) → SELL reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots_to_close, "long")
                    return ("sl_ok" if ok else "sl_fail", mark)
            elif direction == "short":
                if mark <= tp_usd:
                    log.info("🎯 TP hit (short) → BUY reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots_to_close, "short")
                    return ("tp_ok" if ok else "tp_fail", mark)
                if mark >= sl_usd:
                    log.info("🛑 SL hit (short) → BUY reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots_to_close, "short")
                    return ("sl_ok" if ok else "sl_fail", mark)

        except Exception as e:
            log.warning(f"watcher error: {e}")
        await asyncio.sleep(WATCH_INTERVAL_SEC)

    return ("timeout", last_mark or PRICE_HINT_USD)

# ========= PnL calc =========
def approx_realized_pnl_usd(entry_mark, exit_mark, lots, base_lot_btc, direction):
    qty_btc = lots * base_lot_btc
    if direction.lower() == "long": return (exit_mark - entry_mark) * qty_btc
    return (entry_mark - exit_mark) * qty_btc

# ========= MAIN LOOP =========
async def hybrid_loop():
    if not MAINNET_URL or not PRIVATE_KEY.startswith("0x"):
        log.error("⚠️ Lighter parametreleri eksik."); sys.exit(1)

    log.info("="*74)
    log.info("🚀 HYBRID loop + Daily MaxDD / TargetPnL")
    log.info("="*74)
    log.info(f"Market={MARKET_ID} | Target=${TARGET_NOTIONAL} | Lev={ACCOUNT_LEVERAGE}x")
    log.info(f"TP/SL={TP_PCT:.2%}/{SL_PCT:.2%} | Watch={WATCH_INTERVAL_SEC}s")
    log.info(f"Daily Risk: DD={MAX_DD_USD:.2f} USD | TP={TARGET_PNL_USD:.2f} USD | TZ={DAILY_TZ}")
    log.info("="*74)

    signer  = lighter.SignerClient(url=MAINNET_URL, private_key=PRIVATE_KEY, account_index=ACCOUNT_INDEX, api_key_index=API_KEY_INDEX)
    ord_api = lighter.OrderApi(signer.api_client)
    risk_state = load_risk()
    reset_if_new_day(risk_state)

    in_position=False; last_opened_signal_id=None; last_direction=None
    entry_mark=None; entry_lots=None; entry_base_lot=None

    try:
        while True:
            reset_if_new_day(risk_state)
            today_pnl = get_today_pnl(risk_state)

            # === Günlük Risk Kontrolleri ===
            if today_pnl <= -MAX_DD_USD:
                log.warning(f"🛑 Günlük DD aşıldı (PnL={today_pnl:.2f} ≤ -{MAX_DD_USD:.2f}). Bugün poz yok.")
                await asyncio.sleep(SIGNAL_POLL_SEC); continue
            if today_pnl >= TARGET_PNL_USD:
                log.warning(f"✅ Günlük hedef kâr ulaşıldı (PnL={today_pnl:.2f} ≥ {TARGET_PNL_USD:.2f}). Bugün poz yok.")
                await asyncio.sleep(SIGNAL_POLL_SEC); continue

            if not in_position:
                sig = await fetch_active_signal()
                if sig:
                    direction = (sig.get("direction") or sig.get("side") or "").lower()
                    sig_id = sig.get("id")
                    if direction in ("long","short"):
                        if last_opened_signal_id and sig_id == last_opened_signal_id:
                            log.info(f"HYBRID sinyal {sig_id} zaten işlendi.")
                        else:
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
                            last_opened_signal_id=sig_id
                            last_direction=direction
                            entry_mark=mark; entry_lots=lots; entry_base_lot=base_lot

                            outcome,exit_mk = await tp_sl_watcher_market_close(signer,ord_api,MARKET_ID,lots,tp_price,sl_price,direction)
                            log.info(f"Watcher outcome={outcome}")

                            pnl=approx_realized_pnl_usd(entry_mark, exit_mk, lots, base_lot, direction)
                            add_today_pnl(risk_state,pnl)
                            save_risk(risk_state)
                            total=get_today_pnl(risk_state)
                            log.info(f"💰 Realized PnL≈{pnl:+.2f} | Günlük≈{total:+.2f}")

                            if total<=-MAX_DD_USD:
                                log.warning(f"🛑 Günlük DD limitine ulaşıldı (PnL={total:.2f}). Yeni pozlar durduruldu.")
                            if total>=TARGET_PNL_USD:
                                log.warning(f"✅ Günlük hedef kâr ulaşıldı (PnL={total:.2f}). Yeni pozlar durduruldu.")

                            in_position=False; last_direction=None
                            entry_mark=entry_lots=entry_base_lot=None

                await asyncio.sleep(SIGNAL_POLL_SEC)
            else:
                await asyncio.sleep(0.5)

    finally:
        try: await signer.close()
        except: pass

if __name__ == "__main__":
    try:
        asyncio.run(hybrid_loop())
    except KeyboardInterrupt:
        print("\nInterrupted.")
