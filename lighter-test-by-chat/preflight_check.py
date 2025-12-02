#!/usr/bin/env python3
import os, asyncio
from dotenv import load_dotenv
import lighter  # paket: lighter-python

load_dotenv()

BASE_URL     = os.getenv("LIGHTER_MAINNET_URL", "").strip()
ACCOUNT_IDX  = int(os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX", "0"))
API_KEY_IDX  = int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX", "0"))

async def main():
    if not BASE_URL:
        raise SystemExit("Set LIGHTER_MAINNET_URL in .env")

    cfg = lighter.Configuration(host=BASE_URL)
    api_client = lighter.ApiClient(configuration=cfg)
    acct_api   = lighter.AccountApi(api_client)
    tx_api     = lighter.TransactionApi(api_client)

    try:
        # 1) Bu index gerçekten var mı?
        # SDK metod adı: 'account'  (get_account değil)
        acct = await acct_api.account(by="index", value=str(ACCOUNT_IDX))
        print("✅ account(): found account at index =", ACCOUNT_IDX)
        # L1 adresi alan adları build'e göre değişebilir:
        l1 = getattr(acct, "l1_address", None) or getattr(acct, "address", None)
        if l1:
            print("   L1 address:", l1)

            # 2) Bu L1 altında başka hesaplar var mı?
            try:
                lst = await acct_api.accounts_by_l1_address(by="l1Address", value=l1)
                print("ℹ️ accounts_by_l1_address count:", getattr(lst, "total", None) or "n/a")
            except Exception as e:
                print("accounts_by_l1_address not supported on this build:", e)

        # 3) Nonce: (SignerClient kurmadan) doğrudan TransactionApi ile deneyelim
        try:
            nn = await tx_api.next_nonce(account_index=ACCOUNT_IDX, api_key_index=API_KEY_IDX)
            print("✅ next_nonce():", nn)
        except Exception as e:
            print("❌ next_nonce failed:", e)

    finally:
        await api_client.close()

if __name__ == "__main__":
    asyncio.run(main())
