"""
Bollinger Bands trading strategy.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from .base_strategy import BaseStrategy, Signal

class BollingerBandsStrategy(BaseStrategy):
    """Bollinger Bands mean reversion strategy."""
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            "period": 20,
            "std_dev": 2.0,
            "min_data_points": 25
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("Bollinger Bands", default_params)
        
    def calculate_bollinger_bands(self, prices: pd.Series, period: int, std_dev: float) -> tuple:
        """Calculate Bollinger Bands."""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band, sma, lower_band
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """Generate signals based on Bollinger Bands."""
        if len(data) < self.get_parameter("min_data_points"):
            return [Signal.HOLD] * len(data)
            
        period = self.get_parameter("period")
        std_dev = self.get_parameter("std_dev")
        
        # Calculate Bollinger Bands
        upper_band, middle_band, lower_band = self.calculate_bollinger_bands(
            data['close'], period, std_dev
        )
        
        # Generate signals
        signals = []
        for i in range(len(data)):
            if i < period:
                signals.append(Signal.HOLD)
                continue
                
            current_price = data['close'].iloc[i]
            current_upper = upper_band.iloc[i]
            current_lower = lower_band.iloc[i]
            prev_price = data['close'].iloc[i-1]
            
            # Price touches lower band and starts to rise
            if current_price <= current_lower and current_price > prev_price:
                signals.append(Signal.BUY)
            # Price touches upper band and starts to fall
            elif current_price >= current_upper and current_price < prev_price:
                signals.append(Signal.SELL)
            else:
                signals.append(Signal.HOLD)
                
        return signals
    
    def should_enter_position(self, current_data: pd.Series) -> bool:
        """Check if we should enter a position."""
        if len(self.data) < self.get_parameter("period"):
            return False
            
        signals = self.generate_signals(self.data)
        if not signals:
            return False
            
        return signals[-1] == Signal.BUY
    
    def should_exit_position(self, current_data: pd.Series, position: Dict[str, Any]) -> bool:
        """Check if we should exit a position."""
        if len(self.data) < self.get_parameter("period"):
            return False
            
        signals = self.generate_signals(self.data)
        if not signals:
            return False
            
        return signals[-1] == Signal.SELL
    
    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        period = self.get_parameter("period")
        std_dev = self.get_parameter("std_dev")
        
        if period <= 0:
            raise ValueError("Period must be positive")
        if std_dev <= 0:
            raise ValueError("Standard deviation must be positive")
            
        return True