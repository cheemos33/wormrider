#!/usr/bin/env python3
import os, asyncio, logging
from dotenv import load_dotenv

# pip: lighter-python
import lighter

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BASE_URL     = os.getenv("LIGHTER_MAINNET_URL", "").strip()
ACCOUNT_IDX  = os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX", "").strip()  # örn "0"
L1_ADDRESS   = os.getenv("L1_ADDRESS", "").strip()  # opsiyonel; "0x..." ya da boş

# Kaç key index tarayalım? (UI'nda gördüklerin + biraz pay)
API_INDEX_SCAN_RANGE = range(0, 10)

async def main():
    if not BASE_URL:
        raise SystemExit("Set LIGHTER_MAINNET_URL in .env")

    cfg = lighter.Configuration(host=BASE_URL)
    api_client = lighter.ApiClient(configuration=cfg)

    acct_api = lighter.AccountApi(api_client)
    tx_api   = lighter.TransactionApi(api_client)

    # 1) Account doğrulama
    l1 = None
    if ACCOUNT_IDX != "":
        try:
            acct = await acct_api.account(by="index", value=str(ACCOUNT_IDX))
            logging.info(f"✅ account(by='index', value='{ACCOUNT_IDX}') OK")
            # bazı build'larda alan adı 'l1_address' olabilir; bazen 'address'
            l1 = getattr(acct, "l1_address", None) or getattr(acct, "address", None)
            if l1:
                logging.info(f"   L1 address from account(): {l1}")
            else:
                logging.info("   L1 address alanı bu build'da expose edilmiyor (None).")
        except Exception as e:
            logging.error(f"❌ account(by='index') failed: {e}")

    if not l1 and L1_ADDRESS:
        l1 = L1_ADDRESS
        logging.info(f"Using L1_ADDRESS from .env: {l1}")

    # 2) Aynı L1 altındaki tüm account'ları listele (varsa)
    if l1:
        try:
            group = await acct_api.accounts_by_l1_address(l1_address=l1)
            # SDK sürümüne göre items/data alan adı değişebiliyor
            items = getattr(group, "items", None) or getattr(group, "data", None) or group
            logging.info("Accounts under same L1:")
            found = False
            for it in (items or []):
                idx = getattr(it, "account_index", None) or getattr(it, "index", None)
                logging.info(f"  - account_index: {idx}")
                found = True
            if not found:
                logging.info("  (no explicit list returned by this build)")
        except Exception as e:
            logging.info(f"accounts_by_l1_address not available on this build: {e}")

    # 3) API key'leri ve nonce'ı probe et (trade YOK)
    #    'apikeys' endpoint'i için account_index gerekir; yoksa skip.
    if ACCOUNT_IDX != "":
        ai = int(ACCOUNT_IDX)

        # 3.a apikeys: tek tek dene, hangi index'te kayıt var?
        try:
            logging.info("Probing AccountApi.apikeys(account_index=?, api_key_index=K)")
            for k in API_INDEX_SCAN_RANGE:
                try:
                    resp = await acct_api.apikeys(account_index=ai, api_key_index=k)
                    # bazı build'larda sadece var/yok gibi cevap döner
                    logging.info(f"  ✅ apikeys OK for api_key_index={k} :: {resp}")
                except Exception as e:
                    logging.info(f"  ❌ apikeys FAIL for api_key_index={k} :: {e}")
        except Exception as e:
            logging.info(f"apikeys probing not supported on this build: {e}")

        # 3.b next_nonce: fiili eşleşme (server doğrulaması)
        try:
            logging.info("Probing TransactionApi.next_nonce(account_index=?, api_key_index=K)")
            for k in API_INDEX_SCAN_RANGE:
                try:
                    nn = await tx_api.next_nonce(account_index=ai, api_key_index=k)
                    logging.info(f"  ✅ next_nonce OK for api_key_index={k} :: {nn}")
                except Exception as e:
                    logging.info(f"  ❌ next_nonce FAIL for api_key_index={k} :: {e}")
        except Exception as e:
            logging.error(f"next_nonce probing failed: {e}")

    await api_client.close()
    logging.info("Done.")

if __name__ == "__main__":
    asyncio.run(main())
