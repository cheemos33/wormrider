"""
Hyperliquid API client for trading operations.
"""
import asyncio
import json
import time
import hmac
import hashlib
from typing import Dict, List, Optional, Any
import aiohttp
import requests
from config import get_config

class HyperliquidClient:
    """Client for interacting with Hyperliquid API."""
    
    def __init__(self):
        self.config = get_config()
        self.base_url = "https://api.hyperliquid-testnet.xyz"
        self.ws_url = "wss://api.hyperliquid-testnet.xyz/ws"
        self.api_key = self.config.hyperliquid_api_key
        self.secret_key = self.config.hyperliquid_secret_key
        self.wallet_pubkey = self.config.hyperliquid_main_wallet_pubkey
        
    def _generate_signature(self, data: str) -> str:
        """Generate HMAC signature for API requests."""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_headers(self, data: str) -> Dict[str, str]:
        """Get headers for API requests."""
        signature = self._generate_signature(data)
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Signature": signature
        }
    async def get_user_state(self) -> Dict[str, Any]:
        """Get user account state."""
        url = f"{self.base_url}/info"
        data = {
            "type": "clearinghouseState",
            "user": self.wallet_pubkey
        }
        
        # Disable SSL verification
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get user state: {response.status}")   
    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get open orders for the user."""
        url = f"{self.base_url}/info"
        data = {
            "type": "openOrders",
            "user": self.wallet_pubkey
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result if isinstance(result, list) else []
                else:
                    raise Exception(f"Failed to get open orders: {response.status}")
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        user_state = await self.get_user_state()
        return user_state.get("assetPositions", [])
    
    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data for a symbol."""
        url = f"{self.base_url}/info"
        data = {
            "type": "l2Book",
            "coin": symbol
        }
        
        # Create SSL context that doesn't verify certificates
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get market data: {response.status}")
    
    async def place_order(self, 
                         symbol: str, 
                         side: str, 
                         size: float, 
                         price: Optional[float] = None,
                         order_type: str = "market") -> Dict[str, Any]:
        """Place an order."""
        url = f"{self.base_url}/exchange"
        
        # Generate nonce
        nonce = int(time.time() * 1000)
        
        # Hyperliquid API order format
        order_data = {
            "coin": symbol,
            "is_buy": side.lower() == "long" or side.lower() == "buy",
            "sz": str(size),
            "limit_px": str(price) if price else "0",
            "order_type": {"market": {}} if order_type == "market" else {"limit": {"tif": "Ioc"}},
            "reduce_only": False,
            "post_only": False
        }
        
        # Create action with proper structure
        action = {
            "type": "order",
            "orders": [order_data]
        }
        
        # Generate signature for the action
        action_json = json.dumps(action, separators=(',', ':'))
        signature_data = action_json + str(nonce)
        signature = self._generate_signature(signature_data)
        
        data = {
            "action": action,
            "nonce": nonce,
            "signature": signature
        }
        
        headers = self._get_headers(json.dumps(data))
        
        # Create SSL context that doesn't verify certificates
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to place order: {response.status} - {error_text}")
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order."""
        url = f"{self.base_url}/exchange"
        
        nonce = int(time.time() * 1000)
        
        cancel_data = {
            "action": {
                "type": "cancel",
                "cancels": [{"oid": order_id}]
            },
            "nonce": nonce,
            "signature": self._generate_signature(json.dumps({"oid": order_id}) + str(nonce))
        }
        
        headers = self._get_headers(json.dumps(cancel_data))
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=cancel_data, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to cancel order: {response.status} - {error_text}")
    
    async def get_balance(self) -> float:
        """Get account balance."""
        user_state = await self.get_user_state()
        return float(user_state.get("marginSummary", {}).get("accountValue", 0))
    
    async def get_available_balance(self) -> float:
        """Get available balance for trading."""
        user_state = await self.get_user_state()
        return float(user_state.get("marginSummary", {}).get("totalMarginUsed", 0))
