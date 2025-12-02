"""
RSI-based trading strategy.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from .base_strategy import BaseStrategy, Signal

class RSIStrategy(BaseStrategy):
    """RSI-based trading strategy."""
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "min_data_points": 20
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("RSI Strategy", default_params)
        
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """Generate signals based on RSI indicator."""
        if len(data) < self.get_parameter("min_data_points"):
            return [Signal.HOLD] * len(data)
            
        rsi_period = self.get_parameter("rsi_period")
        oversold = self.get_parameter("oversold_threshold")
        overbought = self.get_parameter("overbought_threshold")
        
        # Calculate RSI
        data['rsi'] = self.calculate_rsi(data['close'], rsi_period)
        
        # Generate signals
        signals = []
        for i in range(len(data)):
            if i < rsi_period:
                signals.append(Signal.HOLD)
                continue
                
            current_rsi = data['rsi'].iloc[i]
            prev_rsi = data['rsi'].iloc[i-1] if i > 0 else current_rsi
            
            # RSI oversold and starting to rise
            if current_rsi < oversold and current_rsi > prev_rsi:
                signals.append(Signal.BUY)
            # RSI overbought and starting to fall
            elif current_rsi > overbought and current_rsi < prev_rsi:
                signals.append(Signal.SELL)
            else:
                signals.append(Signal.HOLD)
                
        return signals
    
    def should_enter_position(self, current_data: pd.Series) -> bool:
        """Check if we should enter a position based on RSI."""
        if len(self.data) < self.get_parameter("rsi_period"):
            return False
            
        signals = self.generate_signals(self.data)
        if not signals:
            return False
            
        return signals[-1] == Signal.BUY
    
    def should_exit_position(self, current_data: pd.Series, position: Dict[str, Any]) -> bool:
        """Check if we should exit a position."""
        if len(self.data) < self.get_parameter("rsi_period"):
            return False
            
        signals = self.generate_signals(self.data)
        if not signals:
            return False
            
        return signals[-1] == Signal.SELL
    
    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        rsi_period = self.get_parameter("rsi_period")
        oversold = self.get_parameter("oversold_threshold")
        overbought = self.get_parameter("overbought_threshold")
        
        if rsi_period <= 0:
            raise ValueError("RSI period must be positive")
        if oversold >= overbought:
            raise ValueError("Oversold threshold must be less than overbought threshold")
        if oversold < 0 or overbought > 100:
            raise ValueError("RSI thresholds must be between 0 and 100")
            
        return True
