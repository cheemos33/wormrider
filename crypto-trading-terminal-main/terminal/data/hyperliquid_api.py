"""
Hyperliquid API Client for Trading Terminal
Handles all API calls to Hyperliquid exchange
"""
import requests
import ssl
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from eth_account import Account
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


class HyperliquidAPI:
    """Client for Hyperliquid API interactions"""
    
    def __init__(self, base_url: str = "https://api.hyperliquid-testnet.xyz", testnet: bool = False):
        self.base_url = base_url
        self.session = requests.Session()
        self.testnet = testnet
        
        # Disable SSL verification (like existing hyperliquid_client.py)
        self.session.verify = False
        
        # Suppress SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Initialize Hyperliquid SDK components (for trading)
        self.exchange = None
        self.info = None
        self._init_trading_client()
    
    def _init_trading_client(self):
        """Initialize Hyperliquid SDK for trading operations"""
        try:
            # Load secret key from environment
            secret_key = os.getenv('HYPERLIQUID_SECRET_KEY')
            if not secret_key:
                print("⚠️ HYPERLIQUID_SECRET_KEY not found in environment")
                return
            
            # Create account from private key
            account = Account.from_key(secret_key)
            
            # Initialize Exchange and Info objects
            # For testnet, pass the base_url; for mainnet, pass None (default)
            api_url = self.base_url if self.testnet else None
            
            self.info = Info(api_url)
            self.exchange = Exchange(account, api_url)
            
            print(f"✅ Hyperliquid SDK initialized for {'testnet' if self.testnet else 'mainnet'}")
            print(f"   Using API URL: {api_url if api_url else 'mainnet (default)'}")
            
        except Exception as e:
            print(f"⚠️ Failed to initialize trading client: {e}")
            self.exchange = None
            self.info = None
    
    def _post_request(self, endpoint: str, data: dict) -> dict:
        """Make a POST request to Hyperliquid API"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return None
    
    def fetch_coin_universe(self) -> List[str]:
        """
        Fetch all available perpetual coins on Hyperliquid
        
        Returns:
            List of coin symbols (e.g., ['BTC', 'ETH', 'SOL', ...])
        """
        try:
            data = {"type": "meta"}
            response = self._post_request("/info", data)
            
            if response and "universe" in response:
                # Extract coin names from universe
                coins = [item["name"] for item in response["universe"]]
                return sorted(coins)
            else:
                print("Failed to fetch coin universe, using fallback")
                return self._get_fallback_coins()
        except Exception as e:
            print(f"Error fetching coin universe: {e}")
            return self._get_fallback_coins()
    
    def _get_fallback_coins(self) -> List[str]:
        """Fallback list of common Hyperliquid coins"""
        return [
            "BTC", "ETH", "SOL", "AVAX", "MATIC", "ARB", "OP", "ATOM",
            "DOT", "LINK", "UNI", "AAVE", "LDO", "RNDR", "FET", "PEPE",
            "WIF", "IMX", "INJ", "DYDX", "APT", "SUI", "SEI", "TIA",
            "BONK", "JUP", "WLD", "STRK", "PYTH", "BLUR", "MKR", "LTC",
            "BCH", "XRP", "ADA", "DOGE", "SHIB", "TRX", "TON", "XLM"
        ]
    
    def fetch_7day_price_data(self, coin: str) -> Optional[pd.DataFrame]:
        """
        Fetch 7 days of price data for Volume Profile calculation
        
        Args:
            coin: Coin symbol (e.g., 'BTC')
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        try:
            # Calculate timestamps
            end_time = int(time.time() * 1000)  # Now in milliseconds
            start_time = end_time - (7 * 24 * 60 * 60 * 1000)  # 7 days ago
            
            data = {
                "type": "candleSnapshot",
                "req": {
                    "coin": coin,
                    "interval": "30m",  # 30-minute candles for VP
                    "startTime": start_time,
                    "endTime": end_time
                }
            }
            
            response = self._post_request("/info", data)
            
            if response and isinstance(response, list) and len(response) > 0:
                # Parse candle data
                candles = []
                for candle in response:
                    candles.append({
                        'timestamp': pd.to_datetime(candle['t'], unit='ms'),
                        'open': float(candle['o']),
                        'high': float(candle['h']),
                        'low': float(candle['l']),
                        'close': float(candle['c']),
                        'volume': float(candle['v'])
                    })
                
                df = pd.DataFrame(candles)
                df = df.sort_values('timestamp')
                return df
            else:
                print(f"No 7-day data received for {coin}")
                return None
                
        except Exception as e:
            print(f"Error fetching 7-day data for {coin}: {e}")
            return None
    
    def fetch_24h_price_data(self, coin: str) -> Optional[pd.DataFrame]:
        """
        Fetch 24 hours of price data for a coin
        
        Args:
            coin: Coin symbol (e.g., 'BTC')
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        try:
            # Calculate timestamps
            end_time = int(time.time() * 1000)  # Now in milliseconds
            start_time = end_time - (24 * 60 * 60 * 1000)  # 24 hours ago
            
            data = {
                "type": "candleSnapshot",
                "req": {
                    "coin": coin,
                    "interval": "5m",  # 5-minute candles
                    "startTime": start_time,
                    "endTime": end_time
                }
            }
            
            response = self._post_request("/info", data)
            
            if response and isinstance(response, list) and len(response) > 0:
                # Parse candle data
                candles = []
                for candle in response:
                    candles.append({
                        'timestamp': pd.to_datetime(candle['t'], unit='ms'),
                        'open': float(candle['o']),
                        'high': float(candle['h']),
                        'low': float(candle['l']),
                        'close': float(candle['c']),
                        'volume': float(candle['v'])
                    })
                
                df = pd.DataFrame(candles)
                df = df.sort_values('timestamp')
                return df
            else:
                print(f"No data received for {coin}")
                return None
                
        except Exception as e:
            print(f"Error fetching 24h data for {coin}: {e}")
            return None
    
    def fetch_current_price(self, coin: str) -> Optional[float]:
        """
        Fetch current price for a coin
        
        Args:
            coin: Coin symbol (e.g., 'BTC')
        
        Returns:
            Current price as float, or None if failed
        """
        try:
            data = {
                "type": "l2Book",
                "coin": coin
            }
            
            response = self._post_request("/info", data)
            
            if response and "levels" in response:
                levels = response["levels"]
                if len(levels) >= 2:
                    # Get best bid and ask
                    bids = levels[0]  # Bid side
                    asks = levels[1]  # Ask side
                    
                    if bids and asks:
                        best_bid = float(bids[0]['px'])
                        best_ask = float(asks[0]['px'])
                        mid_price = (best_bid + best_ask) / 2
                        return mid_price
            
            # Fallback: try to get from recent candle
            df = self.fetch_24h_price_data(coin)
            if df is not None and not df.empty:
                return df.iloc[-1]['close']
            
            return None
            
        except Exception as e:
            print(f"Error fetching current price for {coin}: {e}")
            return None
    
    def fetch_multiple_current_prices(self, coins: List[str]) -> Dict[str, float]:
        """
        Fetch current prices for multiple coins
        
        Args:
            coins: List of coin symbols
        
        Returns:
            Dictionary mapping coin symbols to prices
        """
        prices = {}
        for coin in coins:
            price = self.fetch_current_price(coin)
            if price is not None:
                prices[coin] = price
        return prices
    
    def get_user_positions(self, wallet_address: str) -> List[Dict]:
        """
        Get user's open positions from Hyperliquid
        
        Args:
            wallet_address: User's wallet address
        
        Returns:
            List of position dicts
        """
        try:
            print(f"🔍 Checking positions for wallet: {wallet_address[:10]}...")
            
            data = {
                "type": "clearinghouseState",
                "user": wallet_address
            }
            response = self._post_request("/info", data)
            
            if not response:
                print("⚠️ No response from API")
                return []
            
            print(f"📡 API response keys: {list(response.keys())}")
            
            if "assetPositions" in response:
                print(f"📊 Found {len(response['assetPositions'])} asset positions")
                positions = []
                for pos in response["assetPositions"]:
                    if pos.get("position"):
                        position_data = pos["position"]
                        # Only include positions with non-zero size
                        size = float(position_data.get("szi", 0))
                        coin = position_data.get("coin", "")
                        print(f"  - {coin}: size={size}")
                        if size != 0:
                            positions.append({
                                'coin': coin,
                                'size': size,
                                'entry_price': float(position_data.get("entryPx", 0)),
                                'unrealized_pnl': float(position_data.get("unrealizedPnl", 0)),
                                'leverage': float(position_data.get("leverage", {}).get("value", 1))
                            })
                print(f"✅ Returning {len(positions)} non-zero positions")
                return positions
            else:
                print("⚠️ No assetPositions in response")
            
            return []
            
        except Exception as e:
            print(f"❌ Error fetching positions: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_user_fills(self, wallet_address: str, coin: Optional[str] = None) -> List[Dict]:
        """
        Get user's recent trade fills (executed trades)
        
        Args:
            wallet_address: User's wallet address
            coin: Optional coin filter (e.g., 'DOGE')
        
        Returns:
            List of fill dictionaries with trade execution details
        """
        try:
            print(f"📜 Fetching user fills for wallet: {wallet_address[:10]}...")
            
            data = {
                "type": "userFills",
                "user": wallet_address
            }
            
            response = self._post_request("/info", data)
            
            if not response:
                print("⚠️ No fills response from API")
                return []
            
            # Filter by coin if specified
            fills = response if isinstance(response, list) else []
            if coin:
                fills = [fill for fill in fills if fill.get('coin') == coin]
                print(f"📊 Found {len(fills)} fills for {coin}")
            else:
                print(f"📊 Found {len(fills)} total fills")
            
            return fills
            
        except Exception as e:
            print(f"❌ Error fetching user fills: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def place_market_order(self, wallet_address: str, coin: str, is_buy: bool, size_usd: float, leverage: int = 1) -> Optional[Dict]:
        """
        Place a market order on Hyperliquid
        
        Args:
            wallet_address: User's wallet address
            coin: Coin to trade
            is_buy: True for long, False for short
            size_usd: Position size in USD
            leverage: Leverage (1-50)
        
        Returns:
            Order result dict or None
        """
        try:
            if not self.exchange:
                print("❌ Exchange client not initialized - check API keys")
                return None
            
            print(f"🔄 Placing market order: {'LONG' if is_buy else 'SHORT'} {coin} ${size_usd} @ {leverage}x")
            
            # Step 1: Get current price
            current_price = self.fetch_current_price(coin)
            if not current_price:
                print(f"❌ Failed to get current price for {coin}")
                return None
            
            # Step 2: Get asset info for proper sizing and pricing
            asset_info = self.info.meta()
            sz_decimals = 3  # Default
            px_decimals = 5  # Default
            
            # Find the coin's size and price decimals
            if asset_info and 'universe' in asset_info:
                for asset in asset_info['universe']:
                    if asset.get('name') == coin:
                        sz_decimals = asset.get('szDecimals', 3)
                        # Try to get price decimals from the asset
                        # Some APIs use 'pxDecimals', check the structure
                        px_decimals = 5  # Will adjust based on actual API response
                        break
            
            # Calculate size in coins
            # Add 5% buffer to ensure order value stays above $10 at current price
            size_coins = (size_usd * 1.05) / current_price
            
            # Round to the coin's specific decimal places
            rounded_size = round(size_coins, sz_decimals)
            
            # Step 3: Set leverage to 1x (isolated, no leverage)
            print(f"🔧 Setting leverage to 1x for {coin}")
            try:
                leverage_result = self.exchange.update_leverage(leverage, coin, is_cross=False)
                print(f"   Leverage set: {leverage_result}")
            except Exception as e:
                print(f"   ⚠️ Leverage setting: {e}")
            
            # Step 4: Place market order using Hyperliquid SDK
            # Market order: use limit order at extreme price to ensure fill
            # For buy: set limit price very high, for sell: set limit price very low
            if is_buy:
                limit_price = round(current_price * 1.05, 1)  # 5% above, rounded to 1 decimal
            else:
                limit_price = round(current_price * 0.95, 1)  # 5% below, rounded to 1 decimal
            
            print(f"📊 {coin} @ ${current_price:.4f} | Size: {rounded_size} coins (${size_usd}) | Limit: ${limit_price} | Leverage: {leverage}x")
            
            # Place the order (use rounded size)
            order_result = self.exchange.order(
                coin,
                is_buy,
                rounded_size,
                limit_price,
                {"limit": {"tif": "Ioc"}}  # Immediate or Cancel for market-like execution
            )
            
            print(f"📤 Order result: {order_result}")
            
            # Check for errors in response
            if order_result and isinstance(order_result, dict):
                if order_result.get('status') == 'ok':
                    response_data = order_result.get('response', {}).get('data', {})
                    statuses = response_data.get('statuses', [])
                    
                    # Check if any status has an error
                    if statuses and len(statuses) > 0:
                        if 'error' in statuses[0]:
                            error_msg = statuses[0]['error']
                            print(f"❌ Order rejected: {error_msg}")
                            return {
                                'status': 'rejected',
                                'error': error_msg,
                                'coin': coin
                            }
                    
                    print(f"✅ Order placed successfully!")
                    return {
                        'status': 'success',
                        'coin': coin,
                        'size_usd': size_usd,
                        'size_coins': rounded_size,
                        'price': current_price,
                        'result': order_result
                    }
            
            print(f"❌ Order failed: unexpected response format")
            return {
                'status': 'error',
                'error': 'Unexpected response format',
                'coin': coin
            }
            
        except Exception as e:
            print(f"❌ Error placing order: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_account_balance(self, wallet_address: str) -> float:
        """
        Get account balance from Hyperliquid
        
        Args:
            wallet_address: User's wallet address
        
        Returns:
            Balance in USD
        """
        try:
            data = {
                "type": "clearinghouseState",
                "user": wallet_address
            }
            response = self._post_request("/info", data)
            
            if response and "marginSummary" in response:
                # Get account value
                account_value = float(response["marginSummary"].get("accountValue", 0))
                return account_value
            
            return 0.0
            
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return 0.0


# Create API instances
api_client = HyperliquidAPI(base_url="https://api.hyperliquid.xyz", testnet=False)  # Mainnet for price data
api_client_testnet = HyperliquidAPI(base_url="https://api.hyperliquid-testnet.xyz", testnet=True)  # Testnet for trading

