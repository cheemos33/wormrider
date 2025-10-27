"""
Lighter.xyz exchange integration for live trading.
Supports both Testnet and Mainnet.
"""

import os
import time
from typing import Dict, Optional, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Detect network from environment
USE_MAINNET = os.getenv('USE_LIGHTER_MAINNET', 'false').lower() == 'true'

if USE_MAINNET:
    # Mainnet configuration
    LIGHTER_BASE_URL = os.getenv('LIGHTER_MAINNET_URL', 'https://api.lighter.xyz')
    PRIVATE_KEY = os.getenv('LIGHTER_MAINNET_PRIVATE_KEY', '')
    NETWORK_NAME = 'MAINNET'
else:
    # Testnet configuration
    LIGHTER_BASE_URL = os.getenv('LIGHTER_TESTNET_URL', 'https://lighter-api-testnet.publicnode.com')
    PRIVATE_KEY = os.getenv('LIGHTER_TESTNET_PRIVATE_KEY', '')
    NETWORK_NAME = 'TESTNET'

print(f"🌐 Lighter Network: {NETWORK_NAME}")
print(f"🔗 API URL: {LIGHTER_BASE_URL}")

# Initialize Lighter clients
from lighter import Configuration, ApiClient, SignerClient
configuration = Configuration(host=LIGHTER_BASE_URL)
configuration.verify_ssl = False

# Global clients
api_client = None
signer_client = None


def init_clients():
    """Initialize Lighter API and Signer clients."""
    global api_client, signer_client
    
    if not PRIVATE_KEY:
        raise ValueError(f"LIGHTER_{NETWORK_NAME}_PRIVATE_KEY not set in environment")
    
    # Disable SSL verification globally (only for testnet)
    if not USE_MAINNET:
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context
    
    api_client = ApiClient(configuration)
    signer_client = SignerClient(private_key=PRIVATE_KEY, api_client=api_client)
    
    return api_client, signer_client


def get_account_info():
    """Get account information from Lighter."""
    try:
        if not signer_client:
            init_clients()
        
        from lighter.api_client import AccountApi
        account_api = AccountApi(api_client)
        account_info = account_api.get_account()
        return account_info
    except Exception as e:
        print(f"Error getting account info: {e}")
        return None


def place_market_order(symbol: str, side: str, size: float, reduce_only: bool = False) -> Optional[Dict[str, Any]]:
    """Place a market order on Lighter."""
    try:
        if not signer_client:
            init_clients()
        
        order_response = signer_client.create_order(
            symbol=symbol,
            side=1 if side == 'buy' else 0,
            order_type=0,  # Market order
            price=0,
            quantity=int(size * 100),
            order_expiry=0,  # Market orders use 0
            reduce_only=0,
            trigger_price=0
        )
        
        return {
            'order_id': order_response.get('orderId'),
            'status': 'filled' if order_response else 'pending',
            'timestamp': int(time.time() * 1000)
        }
    except Exception as e:
        print(f"Error placing market order: {e}")
        return None


def close_position(symbol: str, current_side: str, size: float) -> Optional[Dict[str, Any]]:
    """Close an existing position."""
    close_side = 'sell' if current_side == 'long' else 'buy'
    return place_market_order(symbol, close_side, size, reduce_only=True)
