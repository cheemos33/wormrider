"""
Base strategy class for all trading strategies.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import pandas as pd
from enum import Enum

class Signal(Enum):
    """Trading signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class BaseStrategy(ABC):
    """Base class for all trading strategies."""
    
    def __init__(self, name: str, parameters: Dict[str, Any] = None):
        self.name = name
        self.parameters = parameters or {}
        self.data = pd.DataFrame()
        self.signals = []
        
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """
        Generate trading signals based on market data.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            List of trading signals
        """
        pass
    
    @abstractmethod
    def should_enter_position(self, current_data: pd.Series) -> bool:
        """
        Determine if we should enter a position.
        
        Args:
            current_data: Current market data point
            
        Returns:
            True if should enter position
        """
        pass
    
    @abstractmethod
    def should_exit_position(self, current_data: pd.Series, position: Dict[str, Any]) -> bool:
        """
        Determine if we should exit a position.
        
        Args:
            current_data: Current market data point
            position: Current position information
            
        Returns:
            True if should exit position
        """
        pass
    
    def update_data(self, data: pd.DataFrame):
        """Update strategy data."""
        self.data = data
        
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get strategy parameter."""
        return self.parameters.get(key, default)
    
    def set_parameter(self, key: str, value: Any):
        """Set strategy parameter."""
        self.parameters[key] = value
        
    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        return True
        
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information."""
        return {
            "name": self.name,
            "parameters": self.parameters,
            "data_points": len(self.data) if not self.data.empty else 0
        }
