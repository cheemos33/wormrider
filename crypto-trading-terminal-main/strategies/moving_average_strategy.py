"""
Moving Average Crossover Strategy.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from .base_strategy import BaseStrategy, Signal

class MovingAverageStrategy(BaseStrategy):
    """Moving Average Crossover Strategy."""
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            "short_window": 10,
            "long_window": 30,
            "min_data_points": 50
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("Moving Average Crossover", default_params)
        
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """Generate signals based on moving average crossover."""
        if len(data) < self.get_parameter("min_data_points"):
            return [Signal.HOLD] * len(data)
            
        short_window = self.get_parameter("short_window")
        long_window = self.get_parameter("long_window")
        
        # Calculate moving averages
        data['SMA_short'] = data['close'].rolling(window=short_window).mean()
        data['SMA_long'] = data['close'].rolling(window=long_window).mean()
        
        # Generate signals
        signals = []
        for i in range(len(data)):
            if i < long_window:
                signals.append(Signal.HOLD)
                continue
                
            current_short = data['SMA_short'].iloc[i]
            current_long = data['SMA_short'].iloc[i]
            prev_short = data['SMA_short'].iloc[i-1]
            prev_long = data['SMA_long'].iloc[i-1]
            
            # Bullish crossover
            if prev_short <= prev_long and current_short > current_long:
                signals.append(Signal.BUY)
            # Bearish crossover
            elif prev_short >= prev_long and current_short < current_long:
                signals.append(Signal.SELL)
            else:
                signals.append(Signal.HOLD)
                
        return signals
    
    def should_enter_position(self, current_data: pd.Series) -> bool:
        """Check if we should enter a position based on current data."""
        if len(self.data) < self.get_parameter("long_window"):
            return False
            
        # Get the latest signals
        signals = self.generate_signals(self.data)
        if not signals:
            return False
            
        return signals[-1] == Signal.BUY
    
    def should_exit_position(self, current_data: pd.Series, position: Dict[str, Any]) -> bool:
        """Check if we should exit a position."""
        if len(self.data) < self.get_parameter("long_window"):
            return False
            
        # Get the latest signals
        signals = self.generate_signals(self.data)
        if not signals:
            return False
            
        return signals[-1] == Signal.SELL
    
    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        short_window = self.get_parameter("short_window")
        long_window = self.get_parameter("long_window")
        
        if short_window >= long_window:
            raise ValueError("Short window must be less than long window")
        if short_window <= 0 or long_window <= 0:
            raise ValueError("Windows must be positive")
            
        return True
