#!/usr/bin/env python3
import os, asyncio
from dotenv import load_dotenv
import lighter  # pip: lighter-python

load_dotenv()

BASE_URL = os.getenv("LIGHTER_MAINNET_URL", "").strip()
ACCOUNT_IDX = int(os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX", "0"))

async def main():
    if not BASE_URL:
        raise SystemExit("Set LIGHTER_MAINNET_URL in .env")

    cfg = lighter.Configuration(host=BASE_URL)
    api_client = lighter.ApiClient(configuration=cfg)
    acct_api = lighter.AccountApi(api_client)

    try:
        acct = await acct_api.account(by="index", value=str(ACCOUNT_IDX))
        print(f"✅ account index {ACCOUNT_IDX} exists")
        l1 = getattr(acct, "l1_address", None) or getattr(acct, "address", None)
        print("L1 address:", l1)

        try:
            group = await acct_api.accounts_by_l1_address(by="l1Address", value=l1)
            # group.items veya benzeri bir koleksiyon dönebilir; SDK sürümüne göre uyarlıyoruz:
            items = getattr(group, "items", None) or getattr(group, "data", None) or group
            print("Accounts under same L1:")
            for it in (items or []):
                idx = getattr(it, "account_index", None) or getattr(it, "index", None)
                print("  - account_index:", idx)
        except Exception as e:
            print("accounts_by_l1_address unsupported on this build:", e)

    finally:
        await api_client.close()

if __name__ == "__main__":
    asyncio.run(main())
