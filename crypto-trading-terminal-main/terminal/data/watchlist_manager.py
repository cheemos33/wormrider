"""
Watchlist Manager for Trading Terminal
Handles loading, saving, and managing the 20-coin watchlist
"""
import json
import os
from typing import List, Tuple
from config import config


class WatchlistManager:
    """Manages the user's coin watchlist"""
    
    def __init__(self, filepath: str = None):
        self.filepath = filepath or config.WATCHLIST_FILE
        self.max_coins = config.MAX_WATCHLIST_COINS
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create watchlist file with defaults if it doesn't exist"""
        if not os.path.exists(self.filepath):
            self.save_watchlist(config.DEFAULT_WATCHLIST)
            print(f"Created new watchlist with {len(config.DEFAULT_WATCHLIST)} default coins")
    
    def load_watchlist(self) -> List[str]:
        """
        Load watchlist from JSON file
        
        Returns:
            List of coin symbols
        """
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
                
            # Handle both list and dict format
            if isinstance(data, list):
                coins = data
            elif isinstance(data, dict) and 'watchlist' in data:
                coins = data['watchlist']
            else:
                print("Invalid watchlist format, using defaults")
                return config.DEFAULT_WATCHLIST.copy()
            
            # Validate and clean
            coins = [coin.upper() for coin in coins if isinstance(coin, str)]
            coins = list(dict.fromkeys(coins))  # Remove duplicates
            
            return coins[:self.max_coins]  # Limit to max
            
        except FileNotFoundError:
            print("Watchlist file not found, creating with defaults")
            self._ensure_file_exists()
            return config.DEFAULT_WATCHLIST.copy()
        except json.JSONDecodeError:
            print("Invalid JSON in watchlist file, using defaults")
            return config.DEFAULT_WATCHLIST.copy()
        except Exception as e:
            print(f"Error loading watchlist: {e}")
            return config.DEFAULT_WATCHLIST.copy()
    
    def load_active_coins(self) -> List[str]:
        """
        Load active (checked) coins from JSON file
        
        Returns:
            List of active coin symbols (defaults to all if not set)
        """
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'active_coins' in data:
                active = data['active_coins']
                # Validate
                active = [coin.upper() for coin in active if isinstance(coin, str)]
                return list(dict.fromkeys(active))
            else:
                # Default: all coins are active
                return self.load_watchlist()
                
        except Exception as e:
            print(f"Error loading active coins: {e}")
            return self.load_watchlist()
    
    def save_active_coins(self, active_coins: List[str]):
        """
        Save active (checked) coins to JSON file
        
        Args:
            active_coins: List of coin symbols that are checked
        """
        try:
            # Load current watchlist data
            with open(self.filepath, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                data = {'watchlist': data}
            
            # Update active coins
            data['active_coins'] = active_coins
            data['last_updated'] = str(pd.Timestamp.now())
            
            # Save
            with open(self.filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"Saved {len(active_coins)} active coins")
            
        except Exception as e:
            print(f"Error saving active coins: {e}")
    
    def load_signal_history(self) -> list:
        """Load signal history from JSON file"""
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'signal_history' in data:
                return data['signal_history']  # Return all signals (up to 100)
            return []
        except Exception as e:
            print(f"Error loading signal history: {e}")
            return []
    
    def add_signal(self, coin: str, stars: int, rsi: float, val: float, price: float, 
                   rvwap_1d: float, rvwap_7d: float, change_24h: float):
        """
        Add a new signal to the history (only 3★ and 4★ signals)
        
        Args:
            coin: Coin symbol
            stars: Signal strength (3 or 4 only)
            rsi: RSI value
            val: VAL distance %
            price: Coin price at time of signal
            rvwap_1d: 1-day RVWAP distance %
            rvwap_7d: 7-day RVWAP distance %
            change_24h: 24-hour % change
        """
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                data = {'watchlist': data}
            
            if 'signal_history' not in data:
                data['signal_history'] = []
            
            # Create signal entry with complete market data
            now = pd.Timestamp.now()
            signal = {
                'time': now.strftime('%H:%M'),
                'timestamp': now.isoformat(),  # Full timestamp for time-ago calculation
                'coin': coin,
                'stars': stars,
                'rsi': rsi,
                'val': val,
                'price': price,
                'rvwap_1d': rvwap_1d,
                'rvwap_7d': rvwap_7d,
                'change_24h': change_24h
            }
            
            # Add to history (keep last 10000 signals for extended history)
            data['signal_history'].append(signal)
            data['signal_history'] = data['signal_history'][-10000:]
            
            # Save
            with open(self.filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"🔔 NEW SIGNAL: {coin} {'🍌' * stars} (RSI {rsi:.0f}, VAL {val:+.1f}%)")
            
        except Exception as e:
            print(f"Error saving signal: {e}")
    
    def save_watchlist(self, coins: List[str]):
        """
        Save watchlist to JSON file
        
        Args:
            coins: List of coin symbols to save
        """
        try:
            # Clean and validate
            coins = [coin.upper() for coin in coins if isinstance(coin, str)]
            coins = list(dict.fromkeys(coins))  # Remove duplicates
            coins = coins[:self.max_coins]  # Limit to max
            
            data = {
                'watchlist': coins,
                'last_updated': str(pd.Timestamp.now())
            }
            
            with open(self.filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"Saved watchlist with {len(coins)} coins")
            
        except Exception as e:
            print(f"Error saving watchlist: {e}")
    
    def add_coin(self, coin: str) -> Tuple[bool, str]:
        """
        Add a coin to the watchlist
        
        Args:
            coin: Coin symbol to add
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        coin = coin.upper().strip()
        
        if not coin:
            return False, "Invalid coin symbol"
        
        current = self.load_watchlist()
        
        if coin in current:
            return False, f"{coin} is already in watchlist"
        
        if len(current) >= self.max_coins:
            return False, f"Watchlist is full ({self.max_coins} coins max)"
        
        current.append(coin)
        self.save_watchlist(current)
        
        return True, f"{coin} added to watchlist"
    
    def remove_coin(self, coin: str) -> Tuple[bool, str]:
        """
        Remove a coin from the watchlist
        
        Args:
            coin: Coin symbol to remove
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        coin = coin.upper().strip()
        
        current = self.load_watchlist()
        
        if coin not in current:
            return False, f"{coin} is not in watchlist"
        
        current.remove(coin)
        self.save_watchlist(current)
        
        return True, f"{coin} removed from watchlist"
    
    def get_coin_count(self) -> int:
        """Get current number of coins in watchlist"""
        return len(self.load_watchlist())
    
    def is_full(self) -> bool:
        """Check if watchlist is at max capacity"""
        return self.get_coin_count() >= self.max_coins


# Create a global watchlist manager instance
watchlist_manager = WatchlistManager()


# Fix import for pandas
import pandas as pd

