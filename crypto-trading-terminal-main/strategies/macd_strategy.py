"""
MACD trading strategy.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from .base_strategy import BaseStrategy, Signal

class MACDStrategy(BaseStrategy):
    """MACD trend following strategy."""
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "min_data_points": 30
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("MACD", default_params)
        
    def calculate_macd(self, prices: pd.Series, fast: int, slow: int, signal: int) -> tuple:
        """Calculate MACD indicators."""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """Generate signals based on MACD."""
        if len(data) < self.get_parameter("min_data_points"):
            return [Signal.HOLD] * len(data)
            
        fast = self.get_parameter("fast_period")
        slow = self.get_parameter("slow_period")
        signal = self.get_parameter("signal_period")
        
        # Calculate MACD
        macd_line, signal_line, histogram = self.calculate_macd(
            data['close'], fast, slow, signal
        )
        
        # Generate signals
        signals = []
        for i in range(len(data)):
            if i < slow:
                signals.append(Signal.HOLD)
                continue
                
            current_macd = macd_line.iloc[i]
            current_signal = signal_line.iloc[i]
            prev_macd = macd_line.iloc[i-1]
            prev_signal = signal_line.iloc[i-1]
            
            # MACD crosses above signal line
            if prev_macd <= prev_signal and current_macd > current_signal:
                signals.append(Signal.BUY)
            # MACD crosses below signal line
            elif prev_macd >= prev_signal and current_macd < current_signal:
                signals.append(Signal.SELL)
            else:
                signals.append(Signal.HOLD)
                
        return signals
    
    def should_enter_position(self, current_data: pd.Series) -> bool:
        """Check if we should enter a position."""
        if len(self.data) < self.get_parameter("slow_period"):
            return False
            
        signals = self.generate_signals(self.data)
        if not signals:
            return False
            
        return signals[-1] == Signal.BUY
    
    def should_exit_position(self, current_data: pd.Series, position: Dict[str, Any]) -> bool:
        """Check if we should exit a position."""
        if len(self.data) < self.get_parameter("slow_period"):
            return False
            
        signals = self.generate_signals(self.data)
        if not signals:
            return False
            
        return signals[-1] == Signal.SELL
    
    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        fast = self.get_parameter("fast_period")
        slow = self.get_parameter("slow_period")
        signal = self.get_parameter("signal_period")
        
        if fast >= slow:
            raise ValueError("Fast period must be less than slow period")
        if fast <= 0 or slow <= 0 or signal <= 0:
            raise ValueError("All periods must be positive")
            
        return True