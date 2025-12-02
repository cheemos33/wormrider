"""
Configuration management for the Hyperliquid trading bot.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class TradingConfig(BaseSettings):
    """Trading configuration settings."""
    
    # Hyperliquid API Configuration
    hyperliquid_api_key: str = Field(..., env="HYPERLIQUID_API_KEY")
    hyperliquid_secret_key: str = Field(..., env="HYPERLIQUID_SECRET_KEY")
    hyperliquid_main_wallet_pubkey: str = Field(..., env="HYPERLIQUID_MAIN_WALLET_PUBKEY")
    
    # Trading Configuration
    default_symbol: str = Field(default="ETH", env="DEFAULT_SYMBOL")
    default_side: str = Field(default="long", env="DEFAULT_SIDE")
    default_size: float = Field(default=0.01, env="DEFAULT_SIZE")
    max_position_size: float = Field(default=0.1, env="MAX_POSITION_SIZE")
    stop_loss_percentage: float = Field(default=2.0, env="STOP_LOSS_PERCENTAGE")
    take_profit_percentage: float = Field(default=3.0, env="TAKE_PROFIT_PERCENTAGE")
    
    # Risk Management
    max_daily_loss: float = Field(default=100.0, env="MAX_DAILY_LOSS")
    max_open_positions: int = Field(default=3, env="MAX_OPEN_POSITIONS")
    leverage: float = Field(default=1.0, env="LEVERAGE")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/trading_bot.log", env="LOG_FILE")
    
    # Backtesting
    backtest_start_date: str = Field(default="2024-01-01", env="BACKTEST_START_DATE")
    backtest_end_date: str = Field(default="2024-12-31", env="BACKTEST_END_DATE")
    backtest_initial_balance: float = Field(default=10000.0, env="BACKTEST_INITIAL_BALANCE")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global configuration instance
config = TradingConfig()

def get_config() -> TradingConfig:
    """Get the global configuration instance."""
    return config

def validate_config() -> bool:
    """Validate that all required configuration is present."""
    required_fields = [
        'hyperliquid_api_key',
        'hyperliquid_secret_key', 
        'hyperliquid_main_wallet_pubkey'
    ]
    
    for field in required_fields:
        if not getattr(config, field) or getattr(config, field) == f"your_{field}_here":
            print(f"Error: {field} is not properly configured")
            return False
    
    return True
