import asyncio
from hyperliquid_client import HyperliquidClient

async def debug_market_data():
    client = HyperliquidClient()
    try:
        market_data = await client.get_market_data("ETH")
        print("Raw market data response:")
        print(market_data)
        print("\n" + "="*50)
        
        # Try to find the price in different ways
        if 'levels' in market_data:
            print("Levels found:")
            print(market_data['levels'])
            
        if 'bids' in market_data:
            print("Bids found:")
            print(market_data['bids'])
            
        if 'asks' in market_data:
            print("Asks found:")
            print(market_data['asks'])
            
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(debug_market_data())