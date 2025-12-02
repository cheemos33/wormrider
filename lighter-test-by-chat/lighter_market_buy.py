#!/usr/bin/env python3
import os, sys, json, math, time, asyncio, logging
from dotenv import load_dotenv

load_dotenv()

# ====== ENV ======
MAINNET_URL        = os.getenv("LIGHTER_MAINNET_URL", "").strip()
MARKET_ID          = int(os.getenv("LIGHTER_MAINNET_MARKET_ID", "1"))       # BTC market (örn 1)
TARGET_NOTIONAL    = float(os.getenv("TARGET_NOTIONAL_USDC", "80.0"))       # $10 notional
ACCOUNT_LEVERAGE   = float(os.getenv("ACCOUNT_LEVERAGE", "10.0"))           # bilgi amaçlı
BASE_DECIMALS      = int(os.getenv("BASE_DECIMALS", "8"))                   # BTC için 8
BASE_LOT           = float(os.getenv("BASE_LOT", "0.000001"))               # lot step
PRICE_HINT_USD     = float(os.getenv("PRICE_HINT_USD", "110000"))           # piyasa ipucu

PRIVATE_KEY        = os.getenv("LIGHTER_MAINNET_PRIVATE_KEY", "").strip()   # 0x...
ACCOUNT_INDEX      = int(os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX", "0"))   # ÖRN: 237163
API_KEY_INDEX      = int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX", "0"))   # ÖRN: 3

# ====== LOG ======
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("lighter-mainnet-market-buy")

# ====== IMPORT (pip: lighter-python) ======
import lighter

def snap_down(x: float, step: float) -> float:
    if step <= 0:
        return x
    return math.floor(x / step) * step

async def main():
    # ---- sanity checks
    if not PRIVATE_KEY or not PRIVATE_KEY.startswith("0x"):
        log.error("LIGHTER_MAINNET_PRIVATE_KEY .env'de 0x ile başlamalı.")
        sys.exit(1)
    if not MAINNET_URL:
        log.error("LIGHTER_MAINNET_URL .env'de set edilmeli.")
        sys.exit(1)
    if PRICE_HINT_USD <= 0:
        log.error("PRICE_HINT_USD .env'de set edilmeli (örn 110000).")
        sys.exit(1)

    log.info("=" * 59)
    log.info("🚀 Lighter MAINNET — BTC MARKET BUY ($10 notional @ 10x)")
    log.info("=" * 59)
    log.info(f"Endpoint        : {MAINNET_URL}")
    log.info(f"Account Index   : {ACCOUNT_INDEX}")
    log.info(f"API Key Index   : {API_KEY_INDEX}")
    log.info(f"Target Notional : ${TARGET_NOTIONAL} USDC  | Expected leverage: {ACCOUNT_LEVERAGE}x")
    log.info(f"Market ID       : {MARKET_ID}")
    log.info(f"Price hint USD  : ${PRICE_HINT_USD:,.2f}")
    log.info("=" * 59)

    # ---- sizing (orderbook'suz)
    base_qty  = TARGET_NOTIONAL / PRICE_HINT_USD
    base_qty  = snap_down(base_qty, BASE_LOT)
    if base_qty <= 0:
        log.error("Hesaplanan base miktar <= 0; PRICE_HINT_USD veya TARGET_NOTIONAL'ı ayarla.")
        sys.exit(1)

    base_raw  = int(round(base_qty * (10 ** BASE_DECIMALS)))
    # IMPORTANT: MARKET olsa da validasyon gereği price >= 1 (cent). 1 -> $0.01
    price_raw = 1

    spend_est  = base_qty * PRICE_HINT_USD
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

        log.info("📝 Placing MARKET BUY (IOC, expiry=0)…")
        log.info(f"   market_index={MARKET_ID}, client_order_index={client_order_id}, base_raw={base_raw}")

        order = signer.sign_create_order(
            market_index=MARKET_ID,
            client_order_index=client_order_id,
            base_amount=base_raw,                             # satoshis
            price=price_raw,                                  # 1 cent (validation için)
            is_ask=0,                                         # BUY
            order_type=signer.ORDER_TYPE_MARKET,
            time_in_force=signer.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
            order_expiry=0,                                   # MARKET -> 0
            reduce_only=0,
            trigger_price=0,
        )

                # ... sign_create_order sonrası:
        if isinstance(order, tuple):
            json_str, err = order[0], order[1]
            log.info("✅ Placement response:")
            log.info(f"   json (trunc): {json_str[:400] if json_str else None}")
            log.info(f"   error       : {err}")
            if err:
                log.error(f"❌ Order rejected: {err}")
                sys.exit(1)

            # 🔥 ASIL NOKTA: imzalı işlemi yayınla
            try:
                send_resp = await signer.tx_api.send_tx(tx=json_str)   # <— YAYIN
                log.info(f"📡 sendTx -> {send_resp}")
            except Exception as e:
                log.error(f"❌ sendTx failed: {e}")
                sys.exit(1)
        else:
            log.info(f"✅ Placement returned: {type(order)}")


        # küçük bekleme (opsiyonel)
        await asyncio.sleep(1)
        log.info("🎉 Done. Market order sent (validation passed).")

    except Exception as e:
        log.error(f"Order placement failed: {e}")
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
