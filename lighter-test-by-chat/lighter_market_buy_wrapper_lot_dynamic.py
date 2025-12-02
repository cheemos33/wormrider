#!/usr/bin/env python3
# Lighter MAINNET — BTC MARKET BUY (dynamic mark, lot-based, IOC)
# Wrapper: await signer.create_market_order(...)  -> sign + publish

import os, sys, math, time, asyncio, logging
from dotenv import load_dotenv

# ========= .env =========
load_dotenv()
MAINNET_URL        = os.getenv("LIGHTER_MAINNET_URL", "").strip()
MARKET_ID          = int(os.getenv("LIGHTER_MAINNET_MARKET_ID", "1"))        # BTC genelde 1
TARGET_NOTIONAL    = float(os.getenv("TARGET_NOTIONAL_USDC", "10.0"))        # USD cinsinden hedef notional
ACCOUNT_LEVERAGE   = float(os.getenv("ACCOUNT_LEVERAGE", "10.0"))            # sadece log için
PRICE_HINT_USD     = float(os.getenv("PRICE_HINT_USD", "110000"))            # order book boşsa fallback
SAFETY_RATIO       = float(os.getenv("SAFETY_RATIO", "0.98"))                # küçük buffer
SLIPPAGE_PCT       = float(os.getenv("SLIPPAGE_PCT", "0.01"))                # %1 slippage guard

PRIVATE_KEY        = os.getenv("LIGHTER_MAINNET_PRIVATE_KEY", "").strip()    # 0x... (API key'in private'ı)
ACCOUNT_INDEX      = int(os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX", "0"))    # örn: 237163
API_KEY_INDEX      = int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX", "0"))    # örn: 3

# ========= logging =========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("lighter-mainnet-market-buy")

# ========= sdk =========
import lighter   # pip install lighter-python

def snap_down(x: float, step: float) -> float:
    if step <= 0: return x
    return math.floor(x / step) * step

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
    log.info("🚀 Lighter MAINNET — BTC MARKET BUY (dynamic mark, lot-bazlı @ IOC)")
    log.info("=" * 58)
    log.info(f"Endpoint        : {MAINNET_URL}")
    log.info(f"Account Index   : {ACCOUNT_INDEX}")
    log.info(f"API Key Index   : {API_KEY_INDEX}")
    log.info(f"Target Notional : ${TARGET_NOTIONAL}  | Expected leverage: {ACCOUNT_LEVERAGE}x")
    log.info(f"Market ID       : {MARKET_ID}")
    log.info(f"Fallback price  : ${PRICE_HINT_USD:,.2f}")
    log.info(f"Safety/Slippage : SAFETY={SAFETY_RATIO:.2%}, SLIPPAGE={SLIPPAGE_PCT:.2%}")
    log.info("=" * 58)

    signer = None
    try:
        # ---- signer + APIs (same client for reads)
        signer  = lighter.SignerClient(
            url=MAINNET_URL,
            private_key=PRIVATE_KEY,
            account_index=ACCOUNT_INDEX,
            api_key_index=API_KEY_INDEX,
        )
        ord_api = lighter.OrderApi(signer.api_client)

        # ---- 1) Market metadata: base_lot_size (lot adımı) & (opsiyonel) price_tick
        det = await ord_api.order_book_details(market_id=MARKET_ID)
        base_lot = float(
            getattr(det, "base_lot_size", None)
            or getattr(det, "base_step", None)
            or getattr(det, "baseLotSize", None)
            or 0.000001  # fallback (1e-6 BTC/lot)
        )
        price_tick = float(
            getattr(det, "price_tick_size", None)
            or getattr(det, "price_step", None)
            or getattr(det, "priceTickSize", None)
            or 0.01  # 1 cent fallback
        )
        log.info("🧱 Market params")
        log.info(f"   base_lot_size : {base_lot:.8f} BTC/lot")
        log.info(f"   price_tick    : ${price_tick:.2f}")

        # ---- 2) Dinamik fiyat (mid/mark: best bid/ask ortalaması)
        ob = await ord_api.order_book_orders(market_id=MARKET_ID, limit=1)
        if not getattr(ob, "bids", None) or not getattr(ob, "asks", None):
            mark = PRICE_HINT_USD  # fallback
            log.warning("⚠️  Order book boş/gap'li, PRICE_HINT_USD fallback kullanılıyor.")
        else:
            best_bid = float(ob.bids[0].price)
            best_ask = float(ob.asks[0].price)
            mark = (best_bid + best_ask) / 2.0

        # ---- 3) Sizing (lot bazlı): hedef notional → BTC → LOT adedi
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

        # ---- 4) MARKET BUY (IOC) — avg_execution_price = mark * (1 + slippage)
        client_order_id = int(time.time() % 1_000_000)
        avg_price_raw   = int(mark * (1.0 + SLIPPAGE_PCT) * 100)  # USD→cent

        log.info("📝 Placing MARKET BUY via wrapper (IOC)…")
        log.info(f"   market_index={MARKET_ID}, client_order_index={client_order_id}, base_amount(lots)={lots}")

        tx, tx_hash, err = await signer.create_market_order(
            market_index=MARKET_ID,
            client_order_index=client_order_id,
            base_amount=lots,                # LOT SAYISI (doğru ölçek)
            is_ask=0,                        # BUY
            avg_execution_price=avg_price_raw,
            reduce_only=0,
        )
        if err:
            log.error(f"❌ create_market_order rejected: {err}")
            sys.exit(1)

        log.info(f"📡 sent. tx_hash={tx_hash}")

        # ---- 5) Kısa bekleme + read-only kontroller
        await asyncio.sleep(2)

        try:
            # Not: bazı build'lar auth ister → by/value'lu sürüm daha yaygın
            txs = await signer.tx_api.account_txs(by="account_index", value=str(ACCOUNT_INDEX), index=0, limit=5)
            log.info(f"🧾 account_txs (last 5): {txs}")
        except Exception as e:
            log.warning(f"account_txs read skipped/failed (muhtemelen auth gerekli): {e}")

        try:
            rt = await ord_api.recent_trades(market_id=MARKET_ID, limit=10)
            log.info(f"📈 recent_trades: {rt}")
        except Exception as e:
            log.warning(f"recent_trades read failed: {e}")

        log.info("🎉 Done. Market order submitted.")

    except Exception as e:
        log.error(f"Order flow failed: {e}")
        sys.exit(1)
    finally:
        if signer is not None:
            try:
                await signer.close()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
