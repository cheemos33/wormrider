"""
Live trading integration with Lighter.xyz
Executes real trades based on paper trading signals.
"""

import os
import time
import threading
from typing import Optional, Dict, Any
from exchange import lighter


class LiveTrading:
    """Manage live trading with Lighter.xyz"""
    
    def __init__(self):
        self.trading_enabled = os.getenv('LIGHTER_LIVE_TRADING', 'false').lower() == 'true'
        self.symbol = 'BTCUSD'
        self.position_size = float(os.getenv('LIGHTER_POSITION_SIZE', '500'))  # $500 notional
        self.tp_pct = float(os.getenv('LIGHTER_TP_PCT', '0.001327'))  # +0.1327%
        self.sl_pct = float(os.getenv('LIGHTER_SL_PCT', '0.001062'))  # -0.1062%
        
        # Track open positions
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.watcher_running = False
        self.watcher_thread = None
        
    def start_watcher(self):
        """Start TP/SL watcher in background thread."""
        if not self.watcher_running:
            self.watcher_running = True
            self.watcher_thread = threading.Thread(target=self._watch_positions, daemon=True)
            self.watcher_thread.start()
            print("📊 Live Trading Watcher started")
    
    def _watch_positions(self):
        """Monitor open positions and close when TP/SL hit."""
        while self.watcher_running:
            try:
                # Check each open position
                for position_id, position in list(self.open_positions.items()):
                    direction = position['direction']
                    entry_price = position['entry_price']
                    current_price = self._get_current_price()
                    
                    if not current_price:
                        continue
                    
                    # Calculate P&L
                    if direction == 'long':
                        price_change_pct = (current_price - entry_price) / entry_price
                        hit_tp = price_change_pct >= self.tp_pct
                        hit_sl = price_change_pct <= -self.sl_pct
                    else:  # short
                        price_change_pct = (entry_price - current_price) / entry_price
                        hit_tp = price_change_pct >= self.tp_pct
                        hit_sl = price_change_pct <= -self.sl_pct
                    
                    # Close if TP or SL hit
                    if hit_tp or hit_sl:
                        reason = "TP" if hit_tp else "SL"
                        print(f"\n🎯 {reason} HIT - Closing position")
                        print(f"   Entry: ${entry_price:,.2f} → Exit: ${current_price:,.2f}")
                        print(f"   P&L: {price_change_pct*100:.2f}%")
                        
                        # Close position
                        self.close_position(position)
                        
                        # Remove from tracking
                        del self.open_positions[position_id]
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                print(f"Error in position watcher: {e}")
                time.sleep(5)
    
    def _get_current_price(self) -> Optional[float]:
        """Get current BTC price."""
        try:
            import httpx
            response = httpx.get('https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT', timeout=5)
            data = response.json()
            return float(data['price'])
        except Exception as e:
            print(f"Error getting current price: {e}")
            return None
    
    def execute_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Execute a live trade based on paper signal.
        
        Args:
            signal: Signal dict from paper trading
        
        Returns:
            True if order placed successfully
        """
        if not self.trading_enabled:
            return False
        
        try:
            direction = signal['direction']  # 'long' or 'short'
            side = 'buy' if direction == 'long' else 'sell'
            
            # Place market order
            order_result = lighter.place_market_order(
                symbol=self.symbol,
                side=side,
                size=self.position_size
            )
            
            if order_result:
                print(f"✅ LIVE ORDER EXECUTED: {direction.upper()} @ ${signal['entry_price']:,.2f}")
                print(f"   Order ID: {order_result['order_id']}")
                
                # Track position
                position_id = f"{signal['id']}"
                self.open_positions[position_id] = {
                    'direction': direction,
                    'entry_price': signal['entry_price'],
                    'tp_price': signal.get('tp_price'),
                    'sl_price': signal.get('sl_price'),
                    'timestamp': int(time.time() * 1000)
                }
                
                # Start watcher if not running
                if not self.watcher_running:
                    self.start_watcher()
                
                return True
            else:
                print(f"❌ LIVE ORDER FAILED: {direction.upper()}")
                return False
                
        except Exception as e:
            print(f"Error executing live trade: {e}")
            return False
    
    def close_position(self, signal: Dict[str, Any]) -> bool:
        """
        Close a live position.
        
        Args:
            signal: Signal dict with direction and size
        
        Returns:
            True if position closed successfully
        """
        if not self.trading_enabled:
            return False
        
        try:
            direction = signal.get('direction', 'long')
            
            # Close position
            order_result = lighter.close_position(
                symbol=self.symbol,
                current_side=direction,
                size=self.position_size
            )
            
            if order_result:
                print(f"✅ POSITION CLOSED: {direction.upper()}")
                return True
            else:
                print(f"❌ CLOSE FAILED: {direction.upper()}")
                return False
                
        except Exception as e:
            print(f"Error closing position: {e}")
            return False


# Global instance
live_trading = LiveTrading()
