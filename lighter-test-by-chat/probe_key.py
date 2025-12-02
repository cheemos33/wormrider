#!/usr/bin/env python3
import os, asyncio
from dotenv import load_dotenv
import lighter  # pip: lighter-python

load_dotenv()
BASE_URL = os.getenv("LIGHTER_MAINNET_URL","").strip()
ACC = int(os.getenv("LIGHTER_MAINNET_ACCOUNT_INDEX","0"))
K   = int(os.getenv("LIGHTER_MAINNET_API_KEY_INDEX","0"))

async def main():
    cfg = lighter.Configuration(host=BASE_URL)
    cli = lighter.ApiClient(configuration=cfg)
    acct = lighter.AccountApi(cli)
    tx   = lighter.TransactionApi(cli)

    try:
        a = await acct.account(by="index", value=str(ACC))
        print("✅ account(by='index') OK for", ACC)
    except Exception as e:
        print("❌ account() failed:", e)

    try:
        nn = await tx.next_nonce(account_index=ACC, api_key_index=K)
        print(f"✅ next_nonce OK: account_index={ACC}, api_key_index={K} ->", nn)
    except Exception as e:
        print("❌ next_nonce failed:", e)

    await cli.close()

if __name__ == "__main__":
    asyncio.run(main())
