"""
Simple test: Call Lighter API directly
"""
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_lighter():
    from lighter import Configuration, ApiClient, SignerClient
    
    USE_MAINNET = os.getenv('USE_LIGHTER_MAINNET', 'false').lower() == 'true'
    
    if USE_MAINNET:
        LIGHTER_BASE_URL = os.getenv('LIGHTER_MAINNET_URL')
        PRIVATE_KEY = os.getenv('LIGHTER_MAINNET_PRIVATE_KEY')
    else:
        LIGHTER_BASE_URL = os.getenv('LIGHTER_TESTNET_URL')
        PRIVATE_KEY = os.getenv('LIGHTER_TESTNET_PRIVATE_KEY')
    
    print(f"Network: {'MAINNET' if USE_MAINNET else 'TESTNET'}")
    print(f"URL: {LIGHTER_BASE_URL}")
    print(f"Private Key: {'*' * 10}...")
    print()
    
    configuration = Configuration(host=LIGHTER_BASE_URL)
    configuration.verify_ssl = False
    
    api_client = ApiClient(configuration)
    signer_client = SignerClient(private_key=PRIVATE_KEY, api_client=api_client)
    
    print("Initializing clients...")
    
    # Test order
    try:
        order_response = await signer_client.create_order(
            symbol='BTCUSD',
            side=1,  # buy
            order_type=0,  # market
            price=0,
            quantity=1000,  # $10 notional
            order_expiry=0,
            reduce_only=0,
            trigger_price=0
        )
        print(f"✅ Order placed: {order_response}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_lighter())
