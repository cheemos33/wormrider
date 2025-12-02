"""
Risk management module for the trading bot.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from config import get_config

@dataclass
class Position:
    """Position data structure."""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0

class RiskManager:
    """Risk management system for the trading bot."""
    
    def __init__(self):
        self.config = get_config()
        self.positions: List[Position] = []
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
        self.logger = logging.getLogger(__name__)
        
    def reset_daily_metrics(self):
        """Reset daily metrics if it's a new day."""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_pnl = 0.0
            self.last_reset_date = current_date
            self.logger.info("Daily metrics reset for new trading day")
    
    def calculate_position_size(self, 
                              symbol: str, 
                              price: float, 
                              risk_percentage: float = 1.0) -> float:
        """
        Calculate position size based on risk management rules.
        
        Args:
            symbol: Trading symbol
            price: Current price
            risk_percentage: Risk percentage of account balance
            
        Returns:
            Position size
        """
        try:
            # Get account balance (this would need to be injected or fetched)
            account_balance = 10000.0  # Placeholder - should be fetched from API
            
            # Calculate risk amount
            risk_amount = account_balance * (risk_percentage / 100)
            
            # Calculate position size based on stop loss
            stop_loss_percentage = self.config.stop_loss_percentage / 100
            position_size = risk_amount / (price * stop_loss_percentage)
            
            # Apply maximum position size limit
            max_size = self.config.max_position_size
            position_size = min(position_size, max_size)
            
            return round(position_size, 6)
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0.0
    
    def can_open_position(self, symbol: str, side: str) -> bool:
        """
        Check if we can open a new position based on risk rules.
        
        Args:
            symbol: Trading symbol
            side: Position side ('long' or 'short')
            
        Returns:
            True if position can be opened
        """
        self.reset_daily_metrics()
        
        # Check daily loss limit
        if self.daily_pnl <= -self.config.max_daily_loss:
            self.logger.warning(f"Daily loss limit reached: {self.daily_pnl}")
            return False
        
        # Check maximum open positions
        if len(self.positions) >= self.config.max_open_positions:
            self.logger.warning(f"Maximum open positions reached: {len(self.positions)}")
            return False
        
        # Check if we already have a position in this symbol
        for position in self.positions:
            if position.symbol == symbol:
                self.logger.warning(f"Position already exists for {symbol}")
                return False
        
        return True
    
    def add_position(self, position: Position):
        """Add a new position to tracking."""
        self.positions.append(position)
        self.logger.info(f"Added position: {position.symbol} {position.side} {position.size}")
    
    def remove_position(self, symbol: str, side: str):
        """Remove a position from tracking."""
        self.positions = [p for p in self.positions if not (p.symbol == symbol and p.side == side)]
        self.logger.info(f"Removed position: {symbol} {side}")
    
    def update_position_pnl(self, symbol: str, current_price: float):
        """Update unrealized PnL for a position."""
        for position in self.positions:
            if position.symbol == symbol:
                if position.side == 'long':
                    position.unrealized_pnl = (current_price - position.entry_price) * position.size
                else:  # short
                    position.unrealized_pnl = (position.entry_price - current_price) * position.size
                position.current_price = current_price
                break
    
    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """
        Check if stop loss should be triggered.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            
        Returns:
            True if stop loss should be triggered
        """
        for position in self.positions:
            if position.symbol == symbol and position.stop_loss:
                if position.side == 'long' and current_price <= position.stop_loss:
                    self.logger.warning(f"Stop loss triggered for {symbol} long position")
                    return True
                elif position.side == 'short' and current_price >= position.stop_loss:
                    self.logger.warning(f"Stop loss triggered for {symbol} short position")
                    return True
        return False
    
    def check_take_profit(self, symbol: str, current_price: float) -> bool:
        """
        Check if take profit should be triggered.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            
        Returns:
            True if take profit should be triggered
        """
        for position in self.positions:
            if position.symbol == symbol and position.take_profit:
                if position.side == 'long' and current_price >= position.take_profit:
                    self.logger.info(f"Take profit triggered for {symbol} long position")
                    return True
                elif position.side == 'short' and current_price <= position.take_profit:
                    self.logger.info(f"Take profit triggered for {symbol} short position")
                    return True
        return False
    
    def calculate_stop_loss_price(self, 
                                 entry_price: float, 
                                 side: str, 
                                 stop_loss_percentage: Optional[float] = None) -> float:
        """
        Calculate stop loss price.
        
        Args:
            entry_price: Entry price
            side: Position side
            stop_loss_percentage: Stop loss percentage (uses config if None)
            
        Returns:
            Stop loss price
        """
        if stop_loss_percentage is None:
            stop_loss_percentage = self.config.stop_loss_percentage / 100
        
        if side == 'long':
            return entry_price * (1 - stop_loss_percentage)
        else:  # short
            return entry_price * (1 + stop_loss_percentage)
    
    def calculate_take_profit_price(self, 
                                   entry_price: float, 
                                   side: str, 
                                   take_profit_percentage: Optional[float] = None) -> float:
        """
        Calculate take profit price.
        
        Args:
            entry_price: Entry price
            side: Position side
            take_profit_percentage: Take profit percentage (uses config if None)
            
        Returns:
            Take profit price
        """
        if take_profit_percentage is None:
            take_profit_percentage = self.config.take_profit_percentage / 100
        
        if side == 'long':
            return entry_price * (1 + take_profit_percentage)
        else:  # short
            return entry_price * (1 - take_profit_percentage)
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary."""
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions)
        
        return {
            "total_positions": len(self.positions),
            "total_unrealized_pnl": total_unrealized_pnl,
            "daily_pnl": self.daily_pnl,
            "positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "size": p.size,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.unrealized_pnl,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit
                }
                for p in self.positions
            ]
        }
