#!/usr/bin/env python3
# HYBRID-only lighter trade loop (TP/SL watcher → MARKET-only closes)
# - Tek pozisyon
# - HYBRID sinyal + yön (long/short)
# - TP/SL: watcher, MARKET reduce-only (limit denemeleri yok)
# - Startup watermark: açılıştaki aktif sinyali yoksayar
# - Günlük PnL JSON ve Günlük istatistik JSON (09:00 reset)
# - Günlük durdurma kuralları (istatistik tabanlı):
#     * loss_count - win_count ≥ 3  → gün kilit
#     * win_count  - loss_count ≥ 2 → gün kilit (profit target)
# - Terminal log: entry/exit, qty, notional, TP/SL hedefleri ve beklenen $PnL

import os, sys, math, time, json, asyncio, logging, inspect, pathlib, datetime
from typing import Optional, Dict, Any

# ---------------- ENV LOADING ----------------
from dotenv import load_dotenv
_here = pathlib.Path(__file__).parent
_env_from_var = os.getenv("ENV_FILE")
if _env_from_var:
    load_dotenv(dotenv_path=_env_from_var)
elif (_here / ".env.lighter").exists():
    load_dotenv(dotenv_path=_here / ".env.lighter")
else:
    load_dotenv()

# ---------------- CONFIG ----------------
MAINNET_URL        = os.getenv("LIGHTER_MAINNET_URL", "").strip()
MARKET_ID          = int(os.getenv("LIGHTER_MAINNET_MARKET_ID", "1"))
TARGET_NOTIONAL    = float(os.getenv("TARGET_NOTIONAL_USDC", "10.0"))     # USD
ACCOUNT_LEVERAGE   = float(os.getenv("ACCOUNT_LEVERAGE", "10.0"))         # yalnız log/marjin hesap
PRICE_HINT_USD     = float(os.getenv("PRICE_HINT_USD", "110000"))
SAFETY_RATIO       = float(os.getenv("SAFETY_RATIO", "0.98"))

# TP/SL oran (fraction). Örn: 0.00135 = %0.135
TP_PCT             = float(os.getenv("TP_PCT", "0.013"))                  # default %1.3
SL_PCT             = float(os.getenv("SL_PCT", "0.010"))                  # default %1.0

WATCH_INTERVAL_SEC = float(os.getenv("WATCH_INTERVAL_SEC", "1.0"))
WATCH_TIMEOUT_SEC  = float(os.getenv("WATCH_TIMEOUT_SEC", "3600"))
SIGNAL_POLL_SEC    = float(os.getenv("SIGNAL_POLL_SEC", "2.0"))

PRIVATE_KEY        = os.getenv("LIGHTER_MAINNET_PRIVATE_KEY", "").strip() # 0x... (API key private)
ACCOUNT_INDEX      = int(os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX", "0"))
API_KEY_INDEX      = int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX", "0"))

# ---- Günlük PnL dosyası (takip amaçlı) ----
RISK_FILE          = os.getenv("RISK_FILE", ".risk/day_pnl.json")
DAILY_TZ           = os.getenv("DAILY_TZ", "Europe/Istanbul")

# ---- Günlük istatistik dosyası + reset zamanı ----
STATS_FILE         = os.getenv("STATS_FILE", ".risk/day_stats.json")
RESET_HOUR         = int(os.getenv("RESET_HOUR", "9"))
RESET_MINUTE       = int(os.getenv("RESET_MINUTE", "0"))

# ---- İstatistik tabanlı günlük durdurma eşikleri ----
LOSS_MINUS_WIN_STOP = int(os.getenv("LOSS_MINUS_WIN_STOP", "3"))  # loss - win ≥ 3 → stop
WIN_MINUS_LOSS_STOP = int(os.getenv("WIN_MINUS_LOSS_STOP", "2"))  # win - loss ≥ 2 → stop

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("lighter-hybrid-trade")

# ---------------- TZ HELPERS ----------------
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(DAILY_TZ)
except Exception:
    _TZ = None

def now_in_tz() -> datetime.datetime:
    return datetime.datetime.now(tz=_TZ) if _TZ else datetime.datetime.now()

def day_key() -> str:
    return now_in_tz().strftime("%Y-%m-%d")

# ---------------- DAILY RISK STATE (PnL tracking only) ----------------
def _ensure_dir_for(path: str):
    pathlib.Path(os.path.dirname(path) or ".").mkdir(parents=True, exist_ok=True)

def load_risk() -> Dict[str, Any]:
    _ensure_dir_for(RISK_FILE)
    if not os.path.exists(RISK_FILE): return {}
    try:
        with open(RISK_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except Exception:
        return {}

def save_risk(state: Dict[str, Any]) -> None:
    _ensure_dir_for(RISK_FILE)
    tmp = RISK_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RISK_FILE)

def get_today_pnl(state: Dict[str, Any]) -> float:
    return float(state.get(day_key(), {}).get("pnl_usd", 0.0))

def add_today_pnl(state: Dict[str, Any], delta: float) -> None:
    k = day_key()
    d = state.get(k) or {}
    d["pnl_usd"] = float(d.get("pnl_usd", 0.0)) + float(delta)
    state[k] = d

def reset_if_new_day(state: Dict[str, Any]) -> None:
    # Takvim günü değişirse yeni key doğal olarak açılacak.
    pass

# ---------------- DAILY STATS (09:00 reset) ----------------
class DailyStats:
    def __init__(self, filepath: str, tz_name: str = "Europe/Istanbul",
                 reset_hour: int = 9, reset_minute: int = 0):
        self.filepath = filepath
        self.reset_hour = reset_hour
        self.reset_minute = reset_minute
        try:
            self.tz = ZoneInfo(tz_name) if ZoneInfo else None
        except Exception:
            self.tz = None
        self.state = {
            "day_key": None,
            "trade_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "pnl_total": 0.0,
        }
        self._ensure_dir()
        self._load()
        self._rollover_if_needed()

    def _ensure_dir(self):
        p = pathlib.Path(self.filepath)
        p.parent.mkdir(parents=True, exist_ok=True)

    def _now_local(self) -> datetime.datetime:
        if self.tz:
            return datetime.datetime.now(tz=self.tz)
        return datetime.datetime.now()

    def _trading_day_key(self, dt: Optional[datetime.datetime] = None) -> str:
        if dt is None:
            dt = self._now_local()
        reset_today = dt.replace(hour=self.reset_hour, minute=self.reset_minute, second=0, microsecond=0)
        if dt < reset_today:
            trading_day = (reset_today - datetime.timedelta(days=1)).date()
        else:
            trading_day = reset_today.date()
        return trading_day.isoformat() + f"@{self.reset_hour:02d}:{self.reset_minute:02d}"

    def _load(self):
        p = pathlib.Path(self.filepath)
        if not p.exists():
            self._init_today(); self._save(); return
        try:
            self.state = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            self._init_today(); self._save()

    def _save(self):
        tmp = self.filepath + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.filepath)

    def _init_today(self):
        self.state = {
            "day_key": self._trading_day_key(),
            "trade_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "pnl_total": 0.0,
        }

    def _rollover_if_needed(self):
        current_key = self._trading_day_key()
        if self.state.get("day_key") != current_key:
            self.state["day_key"] = current_key
            self.state["trade_count"] = 0
            self.state["win_count"]   = 0
            self.state["loss_count"]  = 0
            self.state["pnl_total"]   = 0.0
            self._save()

    def tick(self):
        self._rollover_if_needed()

    def record_trade(self, pnl_usd: float):
        self.state["trade_count"] += 1
        if pnl_usd > 0: self.state["win_count"] += 1
        elif pnl_usd < 0: self.state["loss_count"] += 1
        self.state["pnl_total"] = float(self.state.get("pnl_total", 0.0)) + float(pnl_usd)
        self._save()

    def snapshot(self) -> Dict[str, Any]:
        return dict(self.state)

# ---------------- LIGHTER SDK ----------------
import lighter  # pip install lighter-python
VERY_HIGH_CAP_CENTS = 2_147_483_647  # buy cap tavan (int32 sınır)

# ---------------- DB SIGNALS HELPERS ----------------
async def _maybe_await(x): return await x if inspect.isawaitable(x) else x

def _to_dict_like(sig: Any) -> Optional[Dict[str, Any]]:
    if sig is None: return None
    if isinstance(sig, dict): return sig
    d: Dict[str, Any] = {}
    for key in ("id","type","signal_type","kind","direction","side","symbol","tp_pct","sl_pct","notional_usd","status","ts","created_at","timestamp"):
        if hasattr(sig, key): d[key] = getattr(sig, key)
    if hasattr(sig, "__dict__"):
        d.update({k:v for k,v in sig.__dict__.items() if k not in d})
    return d or {"value": sig}

async def fetch_active_signal() -> Optional[Dict[str, Any]]:
    """
    database paketinden HYBRID aktif sinyali getirir.
    """
    try:
        from database import db, db_signals  # noqa: F401
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

# ---------------- MARKET HELPERS ----------------
def snap_down(x: float, step: float) -> float:
    if step <= 0: return x
    return math.floor(x / step) * step

async def fetch_mark_and_params(ord_api, market_id: int, price_hint: float):
    try:
        ob = await ord_api.order_book_orders(market_id=market_id, limit=1)
        if getattr(ob, "bids", None) and getattr(ob, "asks", None):
            bid = float(ob.bids[0].price)
            ask = float(ob.asks[0].price)
            mark = (bid + ask) / 2.0
        else:
            raise ValueError("empty orderbook")
    except Exception as e:
        log.warning(f"order_book_orders failed: {e} — fallback={price_hint}")
        bid = ask = mark = price_hint

    base_lot = 0.000001; price_tick = 0.01
    try:
        det = await ord_api.order_book_details(market_id=market_id)
        base_lot   = float(getattr(det, "base_lot_size", None) or getattr(det, "base_step", None) or 0.000001)
        price_tick = float(getattr(det, "price_tick_size", None) or getattr(det, "price_step", None) or 0.01)
    except Exception:
        pass
    return mark, bid, ask, base_lot, price_tick

async def place_market_open_no_guard(signer, market_id: int, lots: int, direction: str):
    coid = int(time.time() % 1_000_000)
    d = (direction or "").lower()
    if d == "long":
        tx, tx_hash, err = await signer.create_market_order(
            market_index=market_id, client_order_index=coid,
            base_amount=lots, is_ask=0,
            avg_execution_price=VERY_HIGH_CAP_CENTS,  # alım için tavan
            reduce_only=0,
        )
    elif d == "short":
        tx, tx_hash, err = await signer.create_market_order(
            market_index=market_id, client_order_index=coid,
            base_amount=lots, is_ask=1,
            avg_execution_price=1,  # satış için taban
            reduce_only=0,
        )
    else:
        raise ValueError(f"Unsupported direction: {direction}")
    if err: raise RuntimeError(f"OPEN rejected: {err}")
    log.info(f"✅ OPEN accepted. tx_hash={tx_hash}")
    return tx_hash

async def market_close_reduce_only_no_guard(signer, market_id: int, lots: int, direction: str) -> bool:
    """
    TP ve SL kapatmaları için saf MARKET reduce-only.
    """
    d = (direction or "").lower()
    for i in range(1, 6):
        coid = int(time.time() % 1_000_000) + 1000 + i
        try:
            if d == "long":
                tx, txh, err = await signer.create_market_order(
                    market_index=market_id, client_order_index=coid,
                    base_amount=lots, is_ask=1,
                    avg_execution_price=1,  # satış için taban
                    reduce_only=1,
                )
            elif d == "short":
                tx, txh, err = await signer.create_market_order(
                    market_index=market_id, client_order_index=coid,
                    base_amount=lots, is_ask=0,
                    avg_execution_price=VERY_HIGH_CAP_CENTS,  # alım için tavan
                    reduce_only=1,
                )
            else:
                raise ValueError(f"Unsupported direction: {direction}")
        except Exception as e:
            log.warning(f"MARKET close try#{i} raised: {e}")
            await asyncio.sleep(0.25 * i); continue

        if err:
            log.warning(f"MARKET close rejected try#{i}: {err}")
            await asyncio.sleep(0.25 * i)
        else:
            log.info(f"✅ MARKET close accepted tx_hash={txh}")
            return True

    log.error("❌ MARKET close reddedildi.")
    return False

async def tp_sl_watcher(signer, ord_api, market_id, lots, tp_usd, sl_usd, direction):
    """
    TP/SL watcher: sadece piyasa emriyle kapatır (reduce-only).
    """
    d = (direction or "").lower()
    log.info(f"👀 TP/SL watcher aktif: dir={d} TP={tp_usd:.2f} SL={sl_usd:.2f}")
    start = time.time(); last_mark = None
    while time.time() - start < WATCH_TIMEOUT_SEC:
        try:
            ob = await ord_api.order_book_orders(market_id=market_id, limit=1)
            if getattr(ob, "bids", None) and getattr(ob, "asks", None):
                bid, ask = float(ob.bids[0].price), float(ob.asks[0].price)
                mark = (bid + ask) / 2.0
            else:
                mark = PRICE_HINT_USD
            last_mark = mark
            log.info(f"⏱️ mark={mark:,.2f}")

            if d == "long":
                if mark >= tp_usd:
                    log.info("🎯 TP hit (long) → MARKET reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots, "long")
                    return ("tp_ok" if ok else "tp_fail", mark)
                if mark <= sl_usd:
                    log.info("🛑 SL hit (long) → MARKET reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots, "long")
                    return ("sl_ok" if ok else "sl_fail", mark)

            elif d == "short":
                if mark <= tp_usd:
                    log.info("🎯 TP hit (short) → MARKET reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots, "short")
                    return ("tp_ok" if ok else "tp_fail", mark)
                if mark >= sl_usd:
                    log.info("🛑 SL hit (short) → MARKET reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots, "short")
                    return ("sl_ok" if ok else "sl_fail", mark)

        except Exception as e:
            log.warning(f"watcher error: {e}")

        await asyncio.sleep(WATCH_INTERVAL_SEC)

    return ("timeout", last_mark if last_mark is not None else PRICE_HINT_USD)

def compute_pnl(entry_price: float, exit_price: float, lots: int, base_lot_btc: float, direction: str):
    """
    USD PnL + yüzdesel PnL ve marjin bazlı PnL'yi döndürür.
    """
    qty_btc = lots * base_lot_btc
    if (direction or "").lower() == "long":
        pnl_usd = (exit_price - entry_price) * qty_btc
        pnl_pct = (exit_price / entry_price) - 1.0
    else:
        pnl_usd = (entry_price - exit_price) * qty_btc
        pnl_pct = (entry_price / exit_price) - 1.0

    notional_open = entry_price * qty_btc
    margin_used = notional_open / max(ACCOUNT_LEVERAGE, 1.0)
    pnl_on_margin = pnl_usd / margin_used if margin_used > 0 else 0.0
    return pnl_usd, pnl_pct, notional_open, margin_used, pnl_on_margin

# ---------------- MAIN LOOP ----------------
async def hybrid_loop():
    if not MAINNET_URL or not PRIVATE_KEY.startswith("0x"):
        log.error("⚠️ Lighter bağlantı parametreleri eksik (URL/PRIVATE_KEY).")
        sys.exit(1)

    log.info("=" * 74)
    log.info("🚀 HYBRID loop + Stats-based daily cutoffs + Startup watermark (MARKET-only TP/SL)")
    log.info("=" * 74)
    log.info(f"Market={MARKET_ID} | Target=${TARGET_NOTIONAL} | Lev={ACCOUNT_LEVERAGE}x")
    log.info(f"TP/SL={TP_PCT:.3%}/{SL_PCT:.3%} | Cuts: (loss-win)>={LOSS_MINUS_WIN_STOP}, (win-loss)>={WIN_MINUS_LOSS_STOP}")
    log.info("=" * 74)

    signer  = lighter.SignerClient(url=MAINNET_URL, private_key=PRIVATE_KEY, account_index=ACCOUNT_INDEX, api_key_index=API_KEY_INDEX)
    ord_api = lighter.OrderApi(signer.api_client)

    # Daily PnL track (bilgi amaçlı)
    risk_state = load_risk(); reset_if_new_day(risk_state)

    # Daily stats controller (09:00 reset)
    stats = DailyStats(STATS_FILE, tz_name=DAILY_TZ, reset_hour=RESET_HOUR, reset_minute=RESET_MINUTE)
    log.info(f"📊 Daily stats init: {stats.snapshot()}")

    # Startup watermark
    startup_ts = time.time()
    try:
        initial_sig = await fetch_active_signal()
    except Exception:
        initial_sig = None
    ignore_signal_id = (initial_sig or {}).get("id")
    ignore_until_ts = startup_ts
    log.info(f"🧊 Startup watermark: ignore_signal_id={ignore_signal_id}, ts={int(ignore_until_ts)}")

    in_position = False

    try:
        while True:
            reset_if_new_day(risk_state)
            stats.tick()
            snap = stats.snapshot()
            wins  = int(snap.get("win_count", 0))
            losses= int(snap.get("loss_count", 0))
            net_l = losses - wins
            net_w = wins - losses

            if net_l >= LOSS_MINUS_WIN_STOP:
                log.warning(f"🛑 Daily risk limit reached: loss-win={net_l} ≥ {LOSS_MINUS_WIN_STOP} → Yeni poz yok (gün sonuna kadar).")
                await asyncio.sleep(SIGNAL_POLL_SEC); continue

            if net_w >= WIN_MINUS_LOSS_STOP:
                log.warning(f"✅ Daily profit target reached: win-loss={net_w} ≥ {WIN_MINUS_LOSS_STOP} → Yeni poz yok (gün sonuna kadar).")
                await asyncio.sleep(SIGNAL_POLL_SEC); continue

            if not in_position:
                sig = await fetch_active_signal()
                if sig:
                    direction = (sig.get("direction") or sig.get("side") or "").lower()
                    sig_id = sig.get("id")
                    sig_ts = None
                    for k in ("created_at","createdAt","ts","timestamp","created"):
                        if sig.get(k):
                            try: sig_ts = float(sig[k]); break
                            except: pass

                    # startup ignore
                    if ignore_signal_id and sig_id == ignore_signal_id:
                        log.info(f"🧊 Startup sinyali hâlâ aktif (id={sig_id}) → yoksay.")
                        await asyncio.sleep(SIGNAL_POLL_SEC); continue
                    if sig_ts and sig_ts <= ignore_until_ts:
                        log.info(f"🧊 Açılıştan önce oluşmuş sinyal(ts={sig_ts:.0f}) → yoksay.")
                        await asyncio.sleep(SIGNAL_POLL_SEC); continue

                    if direction in ("long","short"):
                        log.info("✨ Yeni HYBRID sinyal tespit edildi.")
                        mark, _, _, base_lot, _ = await fetch_mark_and_params(ord_api, MARKET_ID, PRICE_HINT_USD)

                        # lot bazlı sizing
                        base_qty_btc = (TARGET_NOTIONAL / mark) * SAFETY_RATIO
                        lots = max(1, int(base_qty_btc / base_lot))
                        log.info(f"🧮 dir={direction}, mark={mark:,.2f}, lots={lots} (lot={base_lot:.8f} BTC)")

                        # Açılış
                        try:
                            _ = await place_market_open_no_guard(signer, MARKET_ID, lots, direction)
                        except Exception as e:
                            log.error(f"OPEN failed: {e}")
                            await asyncio.sleep(SIGNAL_POLL_SEC); continue

                        # Entry kalibrasyonu: 0.5s bekle + yeni mark
                        await asyncio.sleep(0.5)
                        entry_price_est, _, _, entry_base_lot, _ = await fetch_mark_and_params(ord_api, MARKET_ID, PRICE_HINT_USD)
                        entry_lots = lots

                        # TP/SL seviyeleri (fraction)
                        if direction == "long":
                            tp_price = entry_price_est * (1 + TP_PCT)
                            sl_price = entry_price_est * (1 - SL_PCT)
                        else:
                            tp_price = entry_price_est * (1 - TP_PCT)
                            sl_price = entry_price_est * (1 + SL_PCT)

                        # Hedeflerin beklenen $PnL etkisi (entry notional’a göre)
                        notional_open = entry_price_est * (entry_lots * entry_base_lot)
                        exp_tp_usd = notional_open * TP_PCT
                        exp_sl_usd = notional_open * SL_PCT
                        log.info(
                            "🎯 Targets | TP=%.2f (≈+$%.3f) | SL=%.2f (≈-$%.3f) | Notional≈$%.2f | Qty≈%.8f BTC",
                            tp_price, exp_tp_usd, sl_price, exp_sl_usd, notional_open, (entry_lots * entry_base_lot)
                        )

                        # Watcher (market-only closes)
                        in_position = True
                        outcome, exit_mk = await tp_sl_watcher(
                            signer, ord_api, MARKET_ID, entry_lots, tp_price, sl_price, direction
                        )
                        log.info(f"Watcher outcome={outcome}")

                        # PnL hesapla ve yaz
                        pnl_usd, pnl_pct, notional_open, margin_used, pnl_on_margin = compute_pnl(
                            entry_price=entry_price_est,
                            exit_price=exit_mk,
                            lots=entry_lots,
                            base_lot_btc=entry_base_lot,
                            direction=direction
                        )
                        add_today_pnl(risk_state, pnl_usd); save_risk(risk_state)
                        stats.record_trade(pnl_usd)
                        snap = stats.snapshot()

                        log.info(
                            ("📊 Realized PnL | dir=%s | entry=%.2f exit=%.2f | qty=%.8f BTC | "
                             "notional≈%.2f | pnl=%.3f usd (%.3f%%) | margin≈%.2f | pnl_on_margin=%.3fx"),
                            direction, entry_price_est, exit_mk, (entry_lots * entry_base_lot),
                            notional_open, pnl_usd, pnl_pct*100, margin_used, pnl_on_margin
                        )
                        log.info(
                            "📈 Daily Stats | day=%s trades=%d win=%d loss=%d pnl_total=%.2f | PnL_today≈%.2f",
                            snap["day_key"], snap["trade_count"], snap["win_count"], snap["loss_count"],
                            snap["pnl_total"], get_today_pnl(risk_state)
                        )

                        # Pozisyon reset + watermark
                        in_position = False
                        ignore_signal_id = sig_id
                        ignore_until_ts = time.time()

            await asyncio.sleep(SIGNAL_POLL_SEC)

    finally:
        try: await signer.close()
        except: pass

# ---------------- RUN ----------------
if __name__ == "__main__":
    try:
        asyncio.run(hybrid_loop())
    except KeyboardInterrupt:
        print("\nInterrupted.")
