"""
Position Manager for Trading Bot
Tracks positions, entries per coin, and budget
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class PositionManager:
    """Manages trading positions and budget"""
    
    def __init__(self, budget: float = 50.0, position_size: float = 2.5, max_entries_per_coin: int = 3, leverage: int = 4):
        """
        Initialize position manager
        
        Args:
            budget: Total trading budget in USD (base capital)
            position_size: Size per entry in USD (base capital)
            max_entries_per_coin: Maximum entries allowed per coin
            leverage: Trading leverage (default 4x)
        """
        self.total_budget = budget
        self.position_size = position_size
        self.max_entries_per_coin = max_entries_per_coin
        self.leverage = leverage
        
        # Storage file
        self.filepath = Path(__file__).parent.parent / 'data' / 'positions.json'
        self.filepath.parent.mkdir(exist_ok=True)
        
        # Load or initialize positions
        self.positions = self._load_positions()
    
    def _load_positions(self) -> Dict:
        """Load positions from file"""
        try:
            if self.filepath.exists():
                with open(self.filepath, 'r') as f:
                    return json.load(f)
            return {
                'active_positions': {},  # {coin: [entry1, entry2, ...]}
                'trade_history': [],  # List of all trades
                'total_spent': 0.0
            }
        except Exception as e:
            print(f"Error loading positions: {e}")
            return {
                'active_positions': {},
                'trade_history': [],
                'total_spent': 0.0
            }
    
    def _save_positions(self):
        """Save positions to file"""
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self.positions, f, indent=2)
        except Exception as e:
            print(f"Error saving positions: {e}")
    
    def can_open_position(self, coin: str) -> tuple[bool, str]:
        """
        Check if can open a new position for this coin
        
        Returns:
            (can_trade, reason)
        """
        # Check notional budget (position_size is already notional)
        remaining_notional = self.get_remaining_notional()
        if remaining_notional < self.position_size:
            return False, f"Insufficient budget (${remaining_notional:.2f} < ${self.position_size})"
        
        # Check entries per coin
        entries = self.get_entry_count(coin)
        if entries >= self.max_entries_per_coin:
            return False, f"Max entries reached for {coin} ({entries}/{self.max_entries_per_coin})"
        
        return True, "OK"
    
    def add_position(self, coin: str, price: float, size: float, leverage: int = None) -> bool:
        """
        Add a new position entry
        
        Args:
            coin: Coin symbol
            price: Entry price
            size: Position size in USD (base capital)
            leverage: Leverage used (defaults to self.leverage)
        
        Returns:
            Success boolean
        """
        try:
            if leverage is None:
                leverage = self.leverage
            
            # Create entry
            entry = {
                'timestamp': datetime.now().isoformat(),
                'price': price,
                'size': size,
                'leverage': leverage,
                'notional': size * leverage,
                'entry_num': self.get_entry_count(coin) + 1
            }
            
            # Add to active positions
            if coin not in self.positions['active_positions']:
                self.positions['active_positions'][coin] = []
            
            self.positions['active_positions'][coin].append(entry)
            
            # Update total spent
            self.positions['total_spent'] += size
            
            # Add to trade history
            trade = {
                'timestamp': datetime.now().isoformat(),
                'time': datetime.now().strftime('%H:%M:%S'),
                'coin': coin,
                'action': 'LONG',
                'price': price,
                'size': size,
                'leverage': leverage,
                'notional': size * leverage,
                'entry_num': entry['entry_num']
            }
            self.positions['trade_history'].append(trade)
            
            # Keep last 100 trades
            self.positions['trade_history'] = self.positions['trade_history'][-100:]
            
            # Save
            self._save_positions()
            
            print(f"✅ LONGED {coin} ${size} @ ${price} (Entry {entry['entry_num']}/3)")
            return True
            
        except Exception as e:
            print(f"❌ Error adding position: {e}")
            return False
    
    def get_entry_count(self, coin: str) -> int:
        """Get number of entries for a coin"""
        return len(self.positions['active_positions'].get(coin, []))
    
    def get_remaining_budget(self) -> float:
        """Get remaining budget (base capital)"""
        return self.total_budget - self.positions['total_spent']
    
    def get_notional_budget(self) -> float:
        """Get total notional budget (base × leverage)"""
        return self.total_budget * self.leverage
    
    def get_notional_spent(self) -> float:
        """Get total notional spent (positions already tracked as notional)"""
        return self.positions['total_spent']
    
    def get_remaining_notional(self) -> float:
        """Get remaining notional budget"""
        return self.get_notional_budget() - self.get_notional_spent()
    
    def get_active_positions(self) -> Dict:
        """Get all active positions"""
        return self.positions['active_positions']
    
    def get_trade_history(self, limit: int = 10) -> List:
        """Get recent trade history"""
        return self.positions['trade_history'][-limit:]
    
    def get_position_summary(self, current_prices: Dict[str, float] = None) -> Dict:
        """
        Get summary of all positions with P&L
        
        Args:
            current_prices: Dict of {coin: current_price} for P&L calculation
        """
        summary = {
            'total_coins': len(self.positions['active_positions']),
            'total_entries': sum(len(entries) for entries in self.positions['active_positions'].values()),
            'total_spent': self.positions['total_spent'],
            'remaining_budget': self.get_remaining_budget(),
            'positions': []
        }
        
        for coin, entries in self.positions['active_positions'].items():
            avg_price = sum(e['price'] for e in entries) / len(entries)
            total_size = sum(e['size'] for e in entries)
            
            position = {
                'coin': coin,
                'entries': len(entries),
                'avg_price': avg_price,
                'total_size': total_size,
                'current_price': None,
                'pnl_usd': None,
                'pnl_pct': None
            }
            
            # Calculate P&L if current price available
            if current_prices and coin in current_prices:
                current_price = current_prices[coin]
                position['current_price'] = current_price
                
                # Calculate total quantity from all entries
                total_quantity = sum(e['size'] / e['price'] for e in entries)
                
                # P&L = (current_price - avg_price) * total_quantity
                position['pnl_usd'] = (current_price - avg_price) * total_quantity
                
                # P&L % = ((current_price - avg_price) / avg_price) * 100
                position['pnl_pct'] = ((current_price - avg_price) / avg_price) * 100
            
            summary['positions'].append(position)
        
        return summary
    
    def sync_with_exchange(self, exchange_positions: List[Dict]) -> Dict:
        """
        Sync local positions with Hyperliquid exchange positions
        Removes any positions that were closed on the exchange
        
        Args:
            exchange_positions: List of positions from Hyperliquid API
                                Each dict should have 'coin' and 'size' keys
        
        Returns:
            Dict with sync results (closed_coins, freed_budget)
        """
        # Get coins that have positions on exchange
        exchange_coins = {pos['coin'] for pos in exchange_positions if pos.get('size', 0) != 0}
        
        # Get coins we're tracking locally
        local_coins = set(self.positions['active_positions'].keys())
        
        # Find coins that were closed (in local but not on exchange)
        closed_coins = local_coins - exchange_coins
        
        freed_budget = 0.0
        
        if closed_coins:
            print(f"🔄 Syncing positions: {len(closed_coins)} closed on exchange")
            
            # Import API to fetch fills
            from data.hyperliquid_api import HyperliquidAPI
            from data.analytics_db import analytics_db
            from datetime import datetime
            import os
            
            api = HyperliquidAPI()
            wallet = os.getenv('HYPERLIQUID_WALLET_ADDRESS')
            
            for coin in closed_coins:
                # Calculate freed budget
                entries = self.positions['active_positions'][coin]
                coin_budget = sum(e['size'] for e in entries)
                freed_budget += coin_budget
                
                # Fetch fills for this coin to get real exit price and P&L
                fills = api.get_user_fills(wallet, coin=coin) if wallet else []
                
                # Find the most recent sell fills (closing trades)
                exit_fills = []
                if fills:
                    # Look for sell fills (closedPnl indicates a closing trade)
                    for fill in fills:
                        if 'closedPnl' in fill:
                            exit_fills.append(fill)
                    
                    # Sort by time, most recent first
                    if exit_fills:
                        exit_fills = sorted(exit_fills, key=lambda x: x.get('time', 0), reverse=True)
                
                # Update analytics database
                for entry in entries:
                    entry_time = entry.get('timestamp')
                    entry_price = entry.get('price', 0)
                    
                    if entry_time:
                        # Try to get exit data from fills
                        exit_price = 0.0
                        pnl_usd = 0.0
                        pnl_pct = 0.0
                        
                        if exit_fills:
                            # Use the first (most recent) exit fill
                            recent_fill = exit_fills[0]
                            exit_price = float(recent_fill.get('px', 0))
                            pnl_usd = float(recent_fill.get('closedPnl', 0))
                            
                            # Calculate percentage P&L
                            if entry_price > 0 and exit_price > 0:
                                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                            
                            print(f"   📊 Found exit fill for {coin}: ${exit_price:.2f} (P&L: ${pnl_usd:.2f}, {pnl_pct:.2f}%)")
                        else:
                            print(f"   ⚠️ No exit fills found for {coin}, using zeros")
                        
                        # Update analytics database with real or zero data
                        try:
                            analytics_db.update_signal_exit(
                                coin=coin,
                                entry_time=entry_time,
                                exit_price=exit_price,
                                exit_time=datetime.now().isoformat(),
                                pnl_usd=pnl_usd,
                                pnl_pct=pnl_pct
                            )
                            print(f"   ✅ Analytics updated for {coin}")
                        except Exception as e:
                            print(f"   ⚠️ Failed to update analytics for {coin}: {e}")
                
                # Remove from active positions
                del self.positions['active_positions'][coin]
                print(f"   ✅ {coin} removed (freed ${coin_budget:.2f})")
            
            # Update total spent
            self.positions['total_spent'] -= freed_budget
            
            # Save changes
            self._save_positions()
            
            print(f"💰 Budget freed: ${freed_budget:.2f}")
        
        return {
            'closed_coins': list(closed_coins),
            'freed_budget': freed_budget
        }
    
    def close_position(self, coin: str, exit_price: float = None, exit_pnl_usd: float = None, exit_pnl_pct: float = None) -> bool:
        """
        Close a specific position (remove from tracking) and save exit data
        
        Args:
            coin: Coin symbol to close
            exit_price: Price at which position was closed (optional)
            exit_pnl_usd: Realized P&L in USD (optional)
            exit_pnl_pct: Realized P&L in percentage (optional)
        
        Returns:
            Success boolean
        """
        try:
            if coin not in self.positions['active_positions']:
                print(f"⚠️ No position found for {coin}")
                return False
            
            # Calculate freed budget
            entries = self.positions['active_positions'][coin]
            freed_budget = sum(e['size'] for e in entries)
            
            # If exit data provided, update all trades for this coin in trade_history
            if exit_price is not None and exit_pnl_usd is not None and exit_pnl_pct is not None:
                closed_at = datetime.now().isoformat()
                for trade in self.positions['trade_history']:
                    if trade['coin'] == coin and 'exit_price' not in trade:
                        trade['exit_price'] = exit_price
                        trade['exit_pnl_usd'] = exit_pnl_usd
                        trade['exit_pnl_pct'] = exit_pnl_pct
                        trade['closed_at'] = closed_at
            
            # Remove from active positions
            del self.positions['active_positions'][coin]
            
            # Update total spent
            self.positions['total_spent'] -= freed_budget
            
            # Save
            self._save_positions()
            
            print(f"✅ {coin} position closed (freed ${freed_budget:.2f})")
            return True
            
        except Exception as e:
            print(f"❌ Error closing position: {e}")
            return False
    
    def reset_positions(self):
        """Reset all positions (for testing or manual reset)"""
        self.positions = {
            'active_positions': {},
            'trade_history': [],
            'total_spent': 0.0
        }
        self._save_positions()
        print("🔄 Positions reset")


