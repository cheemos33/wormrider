"""
Logging configuration for the trading bot.
"""
import logging
import os
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler
from config import get_config

class TradingLogger:
    """Custom logger for the trading bot."""
    
    def __init__(self, name: str = "trading_bot"):
        self.config = get_config()
        self.console = Console()
        self.logger = self._setup_logger(name)
        
    def _setup_logger(self, name: str) -> logging.Logger:
        """Set up the logger with file and console handlers."""
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(self.config.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # File handler
        file_handler = logging.FileHandler(self.config.log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console handler with rich formatting
        console_handler = RichHandler(
            console=self.console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True
        )
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
        
        return logger
    
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)
    
    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)
    
    def critical(self, message: str):
        """Log critical message."""
        self.logger.critical(message)
    
    def trade_signal(self, symbol: str, signal: str, price: float, reason: str):
        """Log trading signal."""
        message = f"TRADE SIGNAL: {symbol} - {signal.upper()} at {price} - {reason}"
        self.logger.info(f"🎯 {message}")
    
    def trade_executed(self, symbol: str, side: str, size: float, price: float, order_id: str):
        """Log trade execution."""
        message = f"TRADE EXECUTED: {symbol} - {side.upper()} {size} at {price} - Order ID: {order_id}"
        self.logger.info(f"✅ {message}")
    
    def trade_cancelled(self, symbol: str, order_id: str, reason: str):
        """Log trade cancellation."""
        message = f"TRADE CANCELLED: {symbol} - Order ID: {order_id} - Reason: {reason}"
        self.logger.warning(f"❌ {message}")
    
    def position_opened(self, symbol: str, side: str, size: float, entry_price: float):
        """Log position opening."""
        message = f"POSITION OPENED: {symbol} - {side.upper()} {size} at {entry_price}"
        self.logger.info(f"📈 {message}")
    
    def position_closed(self, symbol: str, side: str, size: float, exit_price: float, pnl: float):
        """Log position closing."""
        pnl_emoji = "💰" if pnl > 0 else "💸"
        message = f"POSITION CLOSED: {symbol} - {side.upper()} {size} at {exit_price} - PnL: {pnl:.2f}"
        self.logger.info(f"{pnl_emoji} {message}")
    
    def risk_alert(self, alert_type: str, message: str):
        """Log risk management alert."""
        self.logger.warning(f"🚨 RISK ALERT [{alert_type}]: {message}")
    
    def strategy_update(self, strategy_name: str, update: str):
        """Log strategy update."""
        self.logger.info(f"📊 STRATEGY [{strategy_name}]: {update}")
    
    def performance_update(self, total_pnl: float, daily_pnl: float, win_rate: float):
        """Log performance update."""
        message = f"PERFORMANCE: Total PnL: {total_pnl:.2f}, Daily PnL: {daily_pnl:.2f}, Win Rate: {win_rate:.1%}"
        self.logger.info(f"📈 {message}")

# Global logger instance
logger = TradingLogger()

def get_logger(name: Optional[str] = None) -> TradingLogger:
    """Get logger instance."""
    if name:
        return TradingLogger(name)
    return logger
