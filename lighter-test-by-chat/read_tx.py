#!/usr/bin/env python3
# read_tx_by_hash.py
import os, asyncio, json
from dotenv import load_dotenv
import lighter

load_dotenv()
URL     = os.getenv("LIGHTER_MAINNET_URL", "https://mainnet.zklighter.elliot.ai").strip()
TX_HASH = os.getenv("LIGHTER_LAST_TX_HASH","").strip()

async def main():
    if not TX_HASH:
        raise SystemExit("Set LIGHTER_LAST_TX_HASH in .env (tx hash from your submit log)")

    cfg = lighter.Configuration(host=URL)
    api = lighter.ApiClient(configuration=cfg)
    txa = lighter.TransactionApi(api)

    tx = await txa.tx(by="hash", value=TX_HASH)
    try:
        print(json.dumps(tx.to_dict(), indent=2))
    except Exception:
        print(tx)

    await api.close()

if __name__ == "__main__":
    asyncio.run(main())
