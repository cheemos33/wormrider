#!/usr/bin/env python3
# Lighter MAINNET — BTC MARKET BUY (dynamic) + TP/SL watcher
# BUY:    avg_execution_price = VERY_HIGH_CAP (no-guard)
# SELL:   avg_execution_price = 1           (no-guard)
# Close:  MARKET SELL reduce-only, retry + backoff

import os, sys, math, time, asyncio, logging
from dotenv import load_dotenv
load_dotenv()

# ========= .env =========
MAINNET_URL        = os.getenv("LIGHTER_MAINNET_URL", "").strip()
MARKET_ID          = int(os.getenv("LIGHTER_MAINNET_MARKET_ID", "1"))        # BTC genelde 1
TARGET_NOTIONAL    = float(os.getenv("TARGET_NOTIONAL_USDC", "10.0"))        # USD hedef notional
ACCOUNT_LEVERAGE   = float(os.getenv("ACCOUNT_LEVERAGE", "10.0"))            # sadece log için
PRICE_HINT_USD     = float(os.getenv("PRICE_HINT_USD", "110000"))            # order book boşsa fallback
SAFETY_RATIO       = float(os.getenv("SAFETY_RATIO", "0.98"))                # küçük buffer

# TP / SL (yüzde, örn 0.02 = %2)
TP_PCT             = float(os.getenv("TP_PCT", "0.0004"))
SL_PCT             = float(os.getenv("SL_PCT", "0.0004"))
WATCH_INTERVAL_SEC = float(os.getenv("WATCH_INTERVAL_SEC", "1.0"))
WATCH_TIMEOUT_SEC  = float(os.getenv("WATCH_TIMEOUT_SEC", "3600"))

PRIVATE_KEY        = os.getenv("LIGHTER_MAINNET_PRIVATE_KEY", "").strip()    # 0x... (API key'in private'ı)
ACCOUNT_INDEX      = int(os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX", "0"))    # örn: 237163
API_KEY_INDEX      = int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX", "0"))    # örn: 3

# ========= logging =========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("lighter-mainnet-market-buy-tpsl")

# ========= sdk =========
import lighter   # pip install lighter-python

VERY_HIGH_CAP_CENTS = 2_147_483_647  # ~ $21,474,836.47 — BUY no-guard tavanı

def snap_down(x: float, step: float) -> float:
    if step <= 0: return x
    return math.floor(x / step) * step

async def fetch_mark_and_params(ord_api, market_id: int, price_hint: float):
    """Top-of-book + (opsiyonel) market params döndürür."""
    # top-of-book
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

    # params (opsiyonel)
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

async def place_market_buy_no_guard(signer, market_id: int, lots: int):
    """MARKET BUY (IOC), avg_execution_price = VERY_HIGH_CAP_CENTS (tavan çok yüksek), reduce_only=0."""
    coid = int(time.time() % 1_000_000)
    log.info("📝 Placing MARKET BUY (IOC, no-guard; very high cap)…")
    try:
        tx, tx_hash, err = await signer.create_market_order(
            market_index=market_id,
            client_order_index=coid,
            base_amount=lots,              # LOT SAYISI
            is_ask=0,                      # BUY
            avg_execution_price=VERY_HIGH_CAP_CENTS,  # <<< no-guard for BUY
            reduce_only=0,
        )
    except Exception as e:
        raise RuntimeError(f"BUY call raised: {e}") from e
    if err:
        raise RuntimeError(f"BUY rejected: {err}")
    log.info(f"✅ BUY accepted. tx_hash={tx_hash}")
    return tx_hash

async def market_sell_reduce_only_no_guard(signer, market_id: int, lots_to_close: int):
    """MARKET SELL reduce-only, avg_execution_price=1 (taban çok düşük); 5 deneme, artan backoff."""
    tries = 5
    for i in range(1, tries+1):
        coid = int(time.time() % 1_000_000) + 990 + i
        try:
            tx, txh, err = await signer.create_market_order(
                market_index=market_id,
                client_order_index=coid,
                base_amount=lots_to_close,
                is_ask=1,               # SELL
                avg_execution_price=1,  # <<< no-guard for SELL
                reduce_only=1,
            )
        except Exception as e:
            log.warning(f"MARKET SELL raised (try#{i}): {e}")
            await asyncio.sleep(0.25 * i)
            continue

        if err:
            log.warning(f"MARKET SELL rejected (try#{i}): {err}")
            await asyncio.sleep(0.25 * i)
        else:
            log.info(f"✅ MARKET SELL accepted (try#{i}) tx_hash={txh}")
            return True
    log.error("❌ MARKET SELL tüm denemelerde reddedildi.")
    return False

async def tp_sl_watcher_market_close(signer, ord_api, market_id, lots_to_close, tp_usd, sl_usd):
    """Mark izler; TP/SL vurunca market SELL reduce-only yollar."""
    log.info(f"👀 TP/SL watcher active (TP≥{tp_usd:.2f}, SL≤{sl_usd:.2f})")
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

            if mark >= tp_usd:
                log.info("🎯 TP hit → MARKET SELL reduce-only (no-guard)")
                ok = await market_sell_reduce_only_no_guard(signer, market_id, lots_to_close)
                return "tp_ok" if ok else "tp_fail"

            if mark <= sl_usd:
                log.info("🛑 SL hit → MARKET SELL reduce-only (no-guard)")
                ok = await market_sell_reduce_only_no_guard(signer, market_id, lots_to_close)
                return "sl_ok" if ok else "sl_fail"

        except Exception as e:
            log.warning(f"watcher error: {e}")

        await asyncio.sleep(WATCH_INTERVAL_SEC)

    log.warning("⌛ TP/SL watcher timeout.")
    return "timeout"

async def main():
    # ---- sanity checks
    if not MAINNET_URL:
        log.error("LIGHTER_MAINNET_URL boş olamaz.")
        sys.exit(1)
    if not PRIVATE_KEY.startswith("0x"):
        log.error("LIGHTER_MAINNET_PRIVATE_KEY 0x ile başlamalı (API key'in private key'i).")
        sys.exit(1)
    if TARGET_NOTIONAL <= 0:
        log.error("TARGET_NOTIONAL_USDC > 0 olmalı.")
        sys.exit(1)

    log.info("=" * 58)
    log.info("🚀 Lighter MAINNET — BTC MARKET BUY (dynamic) + TP/SL watcher (no-guard)")
    log.info("=" * 58)
    log.info(f"Endpoint        : {MAINNET_URL}")
    log.info(f"Account Index   : {ACCOUNT_INDEX}")
    log.info(f"API Key Index   : {API_KEY_INDEX}")
    log.info(f"Target Notional : ${TARGET_NOTIONAL}  | Expected leverage: {ACCOUNT_LEVERAGE}x")
    log.info(f"Market ID       : {MARKET_ID}")
    log.info(f"Fallback price  : ${PRICE_HINT_USD:,.2f}")
    log.info(f"SAFETY          : {SAFETY_RATIO:.2%}")
    log.info(f"TP/SL           : TP={TP_PCT:.2%}, SL={SL_PCT:.2%}")
    log.info("=" * 58)

    signer = None
    try:
        # ---- signer + APIs
        signer  = lighter.SignerClient(
            url=MAINNET_URL,
            private_key=PRIVATE_KEY,
            account_index=ACCOUNT_INDEX,
            api_key_index=API_KEY_INDEX,
        )
        ord_api = lighter.OrderApi(signer.api_client)

        # ---- 1) Market meta + mark
        mark, best_bid, best_ask, base_lot, price_tick = await fetch_mark_and_params(
            ord_api, MARKET_ID, PRICE_HINT_USD
        )
        log.info("🧱 Market params")
        log.info(f"   base_lot_size : {base_lot:.8f} BTC/lot")
        log.info(f"   price_tick    : ${price_tick:.2f}")

        # ---- 2) Sizing (lot bazlı)
        base_qty_btc = (TARGET_NOTIONAL / mark) * SAFETY_RATIO
        lots = max(1, int(base_qty_btc / base_lot))
        est_notional = lots * base_lot * mark
        est_margin   = est_notional / max(ACCOUNT_LEVERAGE, 1.0)

        log.info("🧮 Sizing (dynamic)")
        log.info(f"   mark         : ${mark:,.2f}")
        log.info(f"   Lots         : {lots}  (lot={base_lot:.8f} BTC)")
        log.info(f"   BTC Qty est. : {lots * base_lot:.8f} BTC")
        log.info(f"   Notional est.: ${est_notional:,.2f}")
        log.info(f"   Margin est.  : ~${est_margin:,.2f} at {ACCOUNT_LEVERAGE}x")

        # ---- 3) MARKET BUY (IOC) — BUY no-guard (very high cap)
        _ = await place_market_buy_no_guard(signer, MARKET_ID, lots)

        # ---- 4) TP/SL eşikleri & watcher
        tp_price = mark * (1.0 + TP_PCT)
        sl_price = mark * (1.0 - SL_PCT)
        log.info(f"🎯 TP target: ${tp_price:,.2f} | 🛑 SL target: ${sl_price:,.2f}")

        outcome = await tp_sl_watcher_market_close(
            signer, ord_api, MARKET_ID, lots_to_close=lots,
            tp_usd=tp_price, sl_usd=sl_price
        )
        log.info(f"Watcher outcome = {outcome}")

        # ---- 5) (opsiyonel) read-only kontroller
        await asyncio.sleep(2)
        try:
            txs = await signer.tx_api.account_txs(by="account_index", value=str(ACCOUNT_INDEX), index=0, limit=5)
            log.info(f"🧾 account_txs (last 5): {txs}")
        except Exception as e:
            log.warning(f"account_txs read skipped/failed: {e}")
        try:
            rt = await ord_api.recent_trades(market_id=MARKET_ID, limit=10)
            log.info(f"📈 recent_trades: {rt}")
        except Exception as e:
            log.warning(f"recent_trades read failed: {e}")

        log.info("🎉 Done.")

    except Exception as e:
        log.error(f"Flow failed: {e}")
        sys.exit(1)
    finally:
        if signer is not None:
            try:    await signer.close()
            except: pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
