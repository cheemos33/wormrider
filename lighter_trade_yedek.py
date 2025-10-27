#!/usr/bin/env python3
# HYBRID-only trading loop (single position) for Lighter mainnet
# - Poll active signal from database.db_signals
# - Only if signal.type == "HYBRID": open position in "direction" (long/short)
# - TP/SL via client-side watcher using MARKET reduce-only close (no-guard)
# - One position at a time; after close, wait for next HYBRID signal.

import os, sys, math, time, asyncio, logging, inspect
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# ========= ENV =========
MAINNET_URL        = os.getenv("LIGHTER_MAINNET_URL", "").strip()
MARKET_ID          = int(os.getenv("LIGHTER_MAINNET_MARKET_ID", "1"))        # BTC genelde 1
TARGET_NOTIONAL    = float(os.getenv("TARGET_NOTIONAL_USDC", "10.0"))
ACCOUNT_LEVERAGE   = float(os.getenv("ACCOUNT_LEVERAGE", "10.0"))            # sadece log amaçlı
PRICE_HINT_USD     = float(os.getenv("PRICE_HINT_USD", "110000"))            # order book boşsa fallback
SAFETY_RATIO       = float(os.getenv("SAFETY_RATIO", "0.98"))

# TP/SL yüzdeleri (örn: 0.02 = %2)
TP_PCT             = float(os.getenv("TP_PCT", "0.02"))
SL_PCT             = float(os.getenv("SL_PCT", "0.01"))
WATCH_INTERVAL_SEC = float(os.getenv("WATCH_INTERVAL_SEC", "1.0"))
WATCH_TIMEOUT_SEC  = float(os.getenv("WATCH_TIMEOUT_SEC", "3600"))
SIGNAL_POLL_SEC    = float(os.getenv("SIGNAL_POLL_SEC", "2.0"))

PRIVATE_KEY        = os.getenv("LIGHTER_MAINNET_PRIVATE_KEY", "").strip()    # 0x...
ACCOUNT_INDEX      = int(os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX", "0"))
API_KEY_INDEX      = int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX", "0"))

# ========= LOG =========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("lighter-hybrid-direction-loop")

# ========= SDK =========
import lighter  # pip install lighter-python

VERY_HIGH_CAP_CENTS = 2_147_483_647  # ~$21,474,836.47 — BUY no-guard cap

# ========= DB (database.db_signals) =========
# Kullanım: from database import db, db_signals
async def _maybe_await(x):
    return await x if inspect.isawaitable(x) else x

def _to_dict_like(sig: Any) -> Optional[Dict[str, Any]]:
    if sig is None:
        return None
    if isinstance(sig, dict):
        return sig
    d: Dict[str, Any] = {}

    # Sık kullanılan alanlar:
    for key in ("id", "type", "signal_type", "kind",
                "direction", "side", "symbol",
                "tp_pct", "sl_pct", "notional_usd",
                "status", "ts"):
        if hasattr(sig, key):
            d[key] = getattr(sig, key)

    # Ek alanlar (__dict__)
    if hasattr(sig, "__dict__"):
        d.update({k: v for k, v in sig.__dict__.items() if k not in d})

    return d or {"value": sig}

async def fetch_active_signal() -> Optional[Dict[str, Any]]:
    """
    database paketi altından aktif sinyali alır.
    Denenecek sıralama:
      - database.db_signals.get_active_signal()
      - database.db_signals.SignalsRepo().get_active()
      - database.db_signals.SignalsDB().get_active()
    """
    try:
        from database import db, db_signals  # noqa: F401
    except Exception as e:
        log.warning(f"database importu yapılamadı: {e}")
        return None

    # 1) Fonksiyon
    if hasattr(db_signals, "get_active_signal"):
        try:
            sig = await _maybe_await(db_signals.get_active_signal('HYBRID'))
            return _to_dict_like(sig)
        except Exception as e:
            log.warning(f"db_signals.get_active_signal() hata: {e}")

   
    return None

# ========= Yardımcılar =========
def snap_down(x: float, step: float) -> float:
    if step <= 0: return x
    return math.floor(x / step) * step

async def fetch_mark_and_params(ord_api, market_id: int, price_hint: float):
    # Top-of-book
    try:
        ob = await ord_api.order_book_orders(market_id=market_id, limit=1)
        if getattr(ob, "bids", None) and getattr(ob, "asks", None):
            best_bid = float(ob.bids[0].price)
            best_ask = float(ob.asks[0].price)
            mark = (best_bid + best_ask) / 2.0
        else:
            raise ValueError("empty orderbook")
    except Exception as e:
        log.warning(f"order_book_orders failed: {e} — using PRICE_HINT_USD")
        best_bid = best_ask = mark = price_hint

    # Market params
    base_lot = 0.000001
    price_tick = 0.01
    try:
        det = await ord_api.order_book_details(market_id=market_id)
        base_lot   = float(
            getattr(det, "base_lot_size", None)
            or getattr(det, "base_step", None)
            or getattr(det, "baseLotSize", None)
            or base_lot
        )
        price_tick = float(
            getattr(det, "price_tick_size", None)
            or getattr(det, "price_step", None)
            or getattr(det, "priceTickSize", None)
            or price_tick
        )
    except Exception as e:
        log.debug(f"order_book_details warn: {e}")

    return mark, best_bid, best_ask, base_lot, price_tick

# ========= Market OPEN (no-guard) =========
async def place_market_open_no_guard(signer, market_id: int, lots: int, direction: str):
    """
    direction: 'long' → BUY no-guard (cap=VERY_HIGH_CAP_CENTS)
               'short' → SELL no-guard (floor=1)
    """
    direction = (direction or "").lower()
    coid = int(time.time() % 1_000_000)

    if direction == "long":
        log.info("📝 MARKET BUY (IOC, no-guard; VERY_HIGH_CAP_CENTS)…")
        tx, tx_hash, err = await signer.create_market_order(
            market_index=market_id,
            client_order_index=coid,
            base_amount=lots,
            is_ask=0,  # BUY
            avg_execution_price=VERY_HIGH_CAP_CENTS,  # BUY no-guard
            reduce_only=0,
        )
    elif direction == "short":
        log.info("📝 MARKET SELL (IOC, no-guard; floor=1)…")
        tx, tx_hash, err = await signer.create_market_order(
            market_index=market_id,
            client_order_index=coid,
            base_amount=lots,
            is_ask=1,  # SELL
            avg_execution_price=1,  # SELL no-guard
            reduce_only=0,
        )
    else:
        raise ValueError(f"Unsupported direction: {direction}")

    if err:
        raise RuntimeError(f"OPEN rejected: {err}")
    log.info(f"✅ OPEN accepted. tx_hash={tx_hash}")
    return tx_hash

# ========= Market CLOSE (reduce-only, no-guard) =========
async def market_close_reduce_only_no_guard(signer, market_id: int, lots_to_close: int, direction: str):
    """
    Long kapatmak için SELL reduce-only (avg=1).
    Short kapatmak için BUY reduce-only (avg=VERY_HIGH_CAP_CENTS).
    """
    direction = (direction or "").lower()
    tries = 5
    for i in range(1, tries+1):
        coid = int(time.time() % 1_000_000) + 990 + i
        try:
            if direction == "long":
                # Close long → SELL reduce-only
                tx, txh, err = await signer.create_market_order(
                    market_index=market_id,
                    client_order_index=coid,
                    base_amount=lots_to_close,
                    is_ask=1,              # SELL
                    avg_execution_price=1, # SELL no-guard
                    reduce_only=1,
                )
            elif direction == "short":
                # Close short → BUY reduce-only
                tx, txh, err = await signer.create_market_order(
                    market_index=market_id,
                    client_order_index=coid,
                    base_amount=lots_to_close,
                    is_ask=0,                           # BUY
                    avg_execution_price=VERY_HIGH_CAP_CENTS,  # BUY no-guard
                    reduce_only=1,
                )
            else:
                raise ValueError(f"Unsupported direction for close: {direction}")
        except Exception as e:
            log.warning(f"MARKET close raised (try#{i}): {e}")
            await asyncio.sleep(0.25 * i)
            continue

        if err:
            log.warning(f"MARKET close rejected (try#{i}): {err}")
            await asyncio.sleep(0.25 * i)
        else:
            log.info(f"✅ MARKET close accepted (try#{i}) tx_hash={txh}")
            return True

    log.error("❌ MARKET close tüm denemelerde reddedildi.")
    return False

# ========= TP/SL watcher =========
async def tp_sl_watcher_market_close(signer, ord_api, market_id, lots_to_close, tp_usd, sl_usd, direction: str):
    """
    Long:  TP = mark >= tp,  SL = mark <= sl  → SELL reduce-only
    Short: TP = mark <= tp,  SL = mark >= sl  → BUY reduce-only
    """
    direction = (direction or "").lower()
    log.info(f"👀 TP/SL watcher (dir={direction}) active: TP={tp_usd:.2f}, SL={sl_usd:.2f}")

    start = time.time()
    while time.time() - start < WATCH_TIMEOUT_SEC:
        try:
            ob = await ord_api.order_book_orders(market_id=market_id, limit=1)
            if getattr(ob, "bids", None) and getattr(ob, "asks", None):
                bid, ask = float(ob.bids[0].price), float(ob.asks[0].price)
                mark = (bid + ask)/2.0
            else:
                bid = ask = mark = PRICE_HINT_USD

            log.info(f"⏱️ mark={mark:,.2f} (bid={bid:,.2f} / ask={ask:,.2f})")

            if direction == "long":
                if mark >= tp_usd:
                    log.info("🎯 TP hit (long) → close by SELL reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots_to_close, direction="long")
                    return "tp_ok" if ok else "tp_fail"
                if mark <= sl_usd:
                    log.info("🛑 SL hit (long) → close by SELL reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots_to_close, direction="long")
                    return "sl_ok" if ok else "sl_fail"

            elif direction == "short":
                if mark <= tp_usd:
                    log.info("🎯 TP hit (short) → close by BUY reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots_to_close, direction="short")
                    return "tp_ok" if ok else "tp_fail"
                if mark >= sl_usd:
                    log.info("🛑 SL hit (short) → close by BUY reduce-only")
                    ok = await market_close_reduce_only_no_guard(signer, market_id, lots_to_close, direction="short")
                    return "sl_ok" if ok else "sl_fail"

        except Exception as e:
            log.warning(f"watcher error: {e}")

        await asyncio.sleep(WATCH_INTERVAL_SEC)

    log.warning("⌛ TP/SL watcher timeout.")
    return "timeout"

# ========= Main loop (HYBRID only, single position) =========
async def hybrid_loop():
    if not MAINNET_URL:
        log.error("LIGHTER_MAINNET_URL boş olamaz."); sys.exit(1)
    if not PRIVATE_KEY.startswith("0x"):
        log.error("LIGHTER_MAINNET_PRIVATE_KEY 0x ile başlamalı."); sys.exit(1)

    log.info("=" * 70)
    log.info("🚀 HYBRID-only trading loop (direction-aware, single-position)")
    log.info("=" * 70)
    log.info(f"Endpoint        : {MAINNET_URL}")
    log.info(f"Account Index   : {ACCOUNT_INDEX} | API Key Index: {API_KEY_INDEX}")
    log.info(f"Market ID       : {MARKET_ID}")
    log.info(f"Notional target : ${TARGET_NOTIONAL}  | Leverage(info)={ACCOUNT_LEVERAGE}x")
    log.info(f"TP/SL           : TP={TP_PCT:.2%} | SL={SL_PCT:.2%} | Watch={WATCH_INTERVAL_SEC}s | Timeout={WATCH_TIMEOUT_SEC}s")
    log.info(f"Signal poll     : {SIGNAL_POLL_SEC}s")
    log.info("=" * 70)

    signer  = lighter.SignerClient(
        url=MAINNET_URL,
        private_key=PRIVATE_KEY,
        account_index=ACCOUNT_INDEX,
        api_key_index=API_KEY_INDEX,
    )
    ord_api = lighter.OrderApi(signer.api_client)

    in_position = False
    last_opened_signal_id = None
    last_direction = None   # "long" / "short" (mevcut pozisyon yönü)

    try:
        while True:
            if not in_position:
                sig = await fetch_active_signal()
                if sig:
                    sig_type = (sig.get("type") or sig.get("signal_type") or sig.get("kind") or "").upper()
                    direction = (sig.get("direction") or sig.get("side") or "").lower()
                    sig_id = sig.get("id")

                    if sig_type == "HYBRID" and direction in ("long", "short"):
                        print("yeni sinyal var")
                        if last_opened_signal_id is not None and sig_id == last_opened_signal_id:
                            log.info(f"HYBRID sinyal (id={sig_id}) zaten işlendi, bekliyorum…")
                        else:
                            # Market & sizing
                            mark, _, _, base_lot, _ = await fetch_mark_and_params(ord_api, MARKET_ID, PRICE_HINT_USD)
                            base_qty_btc = (TARGET_NOTIONAL / mark) * SAFETY_RATIO
                            lots = max(1, int(base_qty_btc / base_lot))
                            est_notional = lots * base_lot * mark
                            est_margin   = est_notional / max(ACCOUNT_LEVERAGE, 1.0)

                            log.info("🧮 Sizing (HYBRID open)")
                            log.info(f"   dir={direction} | mark={mark:,.2f} | lot={base_lot:.8f} BTC | lots={lots} | notional≈${est_notional:,.2f} | margin≈${est_margin:,.2f}")

                            # OPEN
                            try:
                                _ = await place_market_open_no_guard(signer, MARKET_ID, lots, direction=direction)
                            except Exception as e:
                                log.error(f"OPEN failed: {e}")
                                await asyncio.sleep(SIGNAL_POLL_SEC)
                                continue

                            # TP/SL eşikleri
                            if direction == "long":
                                tp_price = mark * (1.0 + TP_PCT)
                                sl_price = mark * (1.0 - SL_PCT)
                            else:  # short
                                tp_price = mark * (1.0 - TP_PCT)  # short için TP aşağıda
                                sl_price = mark * (1.0 + SL_PCT)  # short için SL yukarıda

                            log.info(f"🎯 TP={tp_price:,.2f} | 🛑 SL={sl_price:,.2f} — watcher start (dir={direction})")

                            in_position = True
                            last_opened_signal_id = sig_id
                            last_direction = direction

                            outcome = await tp_sl_watcher_market_close(
                                signer, ord_api, MARKET_ID, lots_to_close=lots,
                                tp_usd=tp_price, sl_usd=sl_price, direction=direction
                            )
                            log.info(f"Watcher outcome={outcome}")

                            in_position = False
                            last_direction = None
                await asyncio.sleep(SIGNAL_POLL_SEC)
            else:
                # pratikte watcher blocking olduğundan burada çok kalınmaz; geleceğe hazırlık
                await asyncio.sleep(0.5)
    finally:
        try:    await signer.close()
        except: pass

if __name__ == "__main__":
    try:
        asyncio.run(hybrid_loop())
    except KeyboardInterrupt:
        print("\nInterrupted.")
