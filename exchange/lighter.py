import ssl
ssl._create_default_https_context = ssl._create_unverified_context

"""
Lighter.xyz exchange integration - Using working async code
"""

import os
import time
import math
import asyncio
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

# Lighter SDK
import lighter

# Configuration
VERY_HIGH_CAP_CENTS = 2_147_483_647  # Very high cap for no-guard buy

USE_MAINNET = os.getenv('USE_LIGHTER_MAINNET', 'false').lower() == 'true'

if USE_MAINNET:
    LIGHTER_BASE_URL = os.getenv('LIGHTER_MAINNET_URL')
    PRIVATE_KEY = os.getenv('LIGHTER_MAINNET_PRIVATE_KEY')
    NETWORK_NAME = 'MAINNET'
    MARKET_ID = int(os.getenv('LIGHTER_MAINNET_MARKET_ID', '1'))
    ACCOUNT_INDEX = int(os.getenv('LIGHTER_MAINNET_ACCOUNT_INDEX', '0'))
    API_KEY_INDEX = int(os.getenv('LIGHTER_MAINNET_API_KEY_INDEX', '0'))
else:
    LIGHTER_BASE_URL = os.getenv('LIGHTER_TESTNET_URL')
    PRIVATE_KEY = os.getenv('LIGHTER_TESTNET_PRIVATE_KEY')
    NETWORK_NAME = 'TESTNET'
    MARKET_ID = int(os.getenv('LIGHTER_TESTNET_MARKET_ID', '1'))
    ACCOUNT_INDEX = int(os.getenv('LIGHTER_TESTNET_ACCOUNT_INDEX', '0'))
    API_KEY_INDEX = int(os.getenv('LIGHTER_TESTNET_API_KEY_INDEX', '0'))

print(f"🌐 Lighter Network: {NETWORK_NAME}")
print(f"🔗 API URL: {LIGHTER_BASE_URL}")

# Global signer
signer = None


async def init_clients():
    """Initialize Lighter signer client."""
    global signer
    
    if not PRIVATE_KEY:
        raise ValueError(f"LIGHTER_{NETWORK_NAME}_PRIVATE_KEY not set in environment")
    
    if not PRIVATE_KEY.startswith("0x"):
        raise ValueError("Private key must start with 0x")
    
    signer = lighter.SignerClient(
        url=LIGHTER_BASE_URL,
        private_key=PRIVATE_KEY,
        account_index=ACCOUNT_INDEX,
        api_key_index=API_KEY_INDEX,
    )
    
    print("✅ Lighter clients initialized")
    return signer


async def fetch_mark_and_params(ord_api, price_hint: float = 110000):
    """Fetch mark price and market parameters."""
    try:
        ob = await ord_api.order_book_orders(market_id=MARKET_ID, limit=1)
        if getattr(ob, "bids", None) and getattr(ob, "asks", None):
            best_bid = float(ob.bids[0].price)
            best_ask = float(ob.asks[0].price)
            mark = (best_bid + best_ask) / 2.0
        else:
            mark = price_hint
    except Exception:
        mark = price_hint
    
    base_lot = 0.000001
    price_tick = 0.01
    
    try:
        det = await ord_api.order_book_details(market_id=MARKET_ID)
        base_lot = float(getattr(det, "base_lot_size", base_lot))
        price_tick = float(getattr(det, "price_tick_size", price_tick))
    except Exception:
        pass
    
    return mark, base_lot, price_tick


async def place_market_order_async(symbol: str, side: str, size: float, reduce_only: bool = False) -> Optional[Dict[str, Any]]:
    """Place a market order on Lighter using working async code."""
    if not signer:
        await init_clients()
    
    ord_api = lighter.OrderApi(signer.api_client)
    mark, base_lot, _ = await fetch_mark_and_params(ord_api)
    
    # Calculate lots
    lots = max(1, int((size / mark) / base_lot))
    
    # Client order ID
    coid = int(time.time() % 1_000_000)
    
    try:
        is_ask = 1 if side == 'sell' else 0
        exec_price = 1 if reduce_only and is_ask else VERY_HIGH_CAP_CENTS
        
        tx, tx_hash, err = await signer.create_market_order(
            market_index=MARKET_ID,
            client_order_index=coid,
            base_amount=lots,
            is_ask=is_ask,
            avg_execution_price=exec_price,
            reduce_only=1 if reduce_only else 0,
        )
        
        if err:
            print(f"Error placing order: {err}")
            return None
        
        return {
            'order_id': str(tx_hash),
            'status': 'filled',
            'timestamp': int(time.time() * 1000)
        }
    except Exception as e:
        print(f"Error placing market order: {e}")
        return None


# Sync wrapper for async functions
def place_market_order(symbol: str, side: str, size: float, reduce_only: bool = False) -> Optional[Dict[str, Any]]:
    """Sync wrapper for async market order."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(place_market_order_async(symbol, side, size, reduce_only))
        return result
    finally:
        loop.close()


def close_position(symbol: str, current_side: str, size: float) -> Optional[Dict[str, Any]]:
    """Close an existing position."""
    close_side = 'sell' if current_side == 'long' else 'buy'
    return place_market_order(symbol, close_side, size, reduce_only=True)
