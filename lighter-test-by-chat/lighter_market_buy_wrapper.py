#!/usr/bin/env python3
# Lighter MAINNET — BTC MARKET BUY ($10 notional @ 10x)
# Wrapper kullanır: await signer.create_market_order(...)  -> imzalar ve YAYINLAR.

import os, sys, math, time, asyncio, logging
from dotenv import load_dotenv

# ===== env =====
load_dotenv()
MAINNET_URL        = os.getenv("LIGHTER_MAINNET_URL", "").strip()
MARKET_ID          = int(os.getenv("LIGHTER_MAINNET_MARKET_ID", "1"))       # BTC genelde 1
TARGET_NOTIONAL    = float(os.getenv("TARGET_NOTIONAL_USDC", "4.0"))       # $10 notional
ACCOUNT_LEVERAGE   = float(os.getenv("ACCOUNT_LEVERAGE", "10.0"))           # bilgi amaçlı
BASE_DECIMALS      = int(os.getenv("BASE_DECIMALS", "8"))                   # BTC: 8
BASE_LOT           = float(os.getenv("BASE_LOT", "0.000001"))               # lot step
PRICE_HINT_USD     = float(os.getenv("PRICE_HINT_USD", "110000"))           # fiyat ipucu (sadece sizing)

PRIVATE_KEY        = os.getenv("LIGHTER_MAINNET_PRIVATE_KEY", "").strip()   # 0x...
ACCOUNT_INDEX      = int(os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX", "0"))   # ÖRN: 237163
API_KEY_INDEX      = int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX", "0"))   # ÖRN: 3

# ===== log =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("lighter-mainnet-market-buy")

# ===== sdk =====
import lighter   # pip: lighter-python

def snap_down(x: float, step: float) -> float:
    if step <= 0:
        return x
    return math.floor(x / step) * step

async def main():
    # ---- sanity
    if not MAINNET_URL:
        log.error("LIGHTER_MAINNET_URL boş olamaz.")
        sys.exit(1)
    if not PRIVATE_KEY.startswith("0x"):
        log.error("LIGHTER_MAINNET_PRIVATE_KEY 0x ile başlamalı (API key'in private key'i).")
        sys.exit(1)
    if PRICE_HINT_USD <= 0:
        log.error("PRICE_HINT_USD > 0 olmalı (örn 110000).")
        sys.exit(1)

    log.info("=" * 58)
    log.info("🚀 Lighter MAINNET — BTC MARKET BUY ($10 notional @ 10x)")
    log.info("=" * 58)
    log.info(f"Endpoint        : {MAINNET_URL}")
    log.info(f"Account Index   : {ACCOUNT_INDEX}")
    log.info(f"API Key Index   : {API_KEY_INDEX}")
    log.info(f"Target Notional : ${TARGET_NOTIONAL}  | Expected leverage: {ACCOUNT_LEVERAGE}x")
    log.info(f"Market ID       : {MARKET_ID}")
    log.info(f"Price hint USD  : ${PRICE_HINT_USD:,.2f}")
    log.info("=" * 58)

    # ---- sizing (orderbook gerekmez)
    base_qty  = TARGET_NOTIONAL / PRICE_HINT_USD          # BTC miktarı
    base_qty  = snap_down(base_qty, BASE_LOT)             # lot'a oturt
    if base_qty <= 0:
        log.error("Hesaplanan BTC miktarı <= 0; PRICE_HINT_USD veya TARGET_NOTIONAL'ı artır.")
        sys.exit(1)

    base_raw  = int(round(base_qty * (10 ** BASE_DECIMALS)))  # satoshi
    spend_est = base_qty * PRICE_HINT_USD
    margin_est = spend_est / max(ACCOUNT_LEVERAGE, 1.0)

    log.info("🧮 Sizing")
    log.info(f"   Base Qty      : {base_qty:.8f} BTC  (raw={base_raw})")
    log.info(f"   Est. Notional : ${spend_est:,.2f} (target ${TARGET_NOTIONAL})")
    log.info(f"   Est. Margin   : ~${margin_est:,.2f} at {ACCOUNT_LEVERAGE}x")

    # ---- signer
    signer = None
    try:
        signer = lighter.SignerClient(
            url=MAINNET_URL,
            private_key=PRIVATE_KEY,
            account_index=ACCOUNT_INDEX,   # örn: 237163
            api_key_index=API_KEY_INDEX,   # örn: 3
        )

        client_order_id = int(time.time() % 1_000_000)

        log.info("📝 Placing MARKET BUY via wrapper (IOC)…")
        log.info(f"   market_index={MARKET_ID}, client_order_index={client_order_id}, base_raw={base_raw}")

        # >>> SIGN + PUBLISH in one go <<<
        tx, tx_hash, err = await signer.create_market_order(
        market_index=MARKET_ID,
        client_order_index=client_order_id,
        base_amount=base_raw,      # satoshi
        is_ask=0,                  # BUY
        avg_execution_price=int(PRICE_HINT_USD * 100),  # USD→cent
        reduce_only=0,
        )


        if err:
            log.error(f"❌ create_market_order rejected: {err}")
            sys.exit(1)

        log.info(f"📡 sent. tx_hash={tx_hash}")
        # küçük bekleme
        await asyncio.sleep(2)

        # --- read-only doğrulamalar (opsiyonel) ---
        try:
            txs = await signer.tx_api.account_txs(account_index=ACCOUNT_INDEX, index=0, limit=5)
            log.info(f"🧾 account_txs (last 5): {txs}")
        except Exception as e:
            log.warning(f"account_txs read failed: {e}")

        try:
            ord_api = lighter.OrderApi(signer.api_client)
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
