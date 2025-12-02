import asyncio
from hyperliquid_client import HyperliquidClient

async def test_testnet():
    try:
        client = HyperliquidClient()
        balance = await client.get_balance()
        print('✅ Testnet connection successful!')
        print(f'Testnet Balance: ${balance:.2f}')
    except Exception as e:
        print(f'❌ Testnet connection failed: {e}')

asyncio.run(test_testnet())