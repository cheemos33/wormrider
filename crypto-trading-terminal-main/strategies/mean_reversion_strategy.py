"""
Mean Reversion trading strategy.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from .base_strategy import BaseStrategy, Signal

class MeanReversionStrategy(BaseStrategy):
    """Mean Reversion strategy - trades against price movements."""
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            "threshold_percentage": 0.2,  # 0.2% price movement threshold
            "lookback_period": 10,        # Look back 10 periods for mean
            "min_data_points": 15         # Need at least 15 data points
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("Mean Reversion", default_params)
        
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """Generate signals based on mean reversion logic."""
        if len(data) < self.get_parameter("min_data_points"):
            return [Signal.HOLD] * len(data)
            
        threshold = self.get_parameter("threshold_percentage") / 100
        lookback = self.get_parameter("lookback_period")
        
        # Calculate rolling mean
        data['rolling_mean'] = data['close'].rolling(window=lookback).mean()
        
        # Generate signals
        signals = []
        for i in range(len(data)):
            if i < lookback:
                signals.append(Signal.HOLD)
                continue
                
            current_price = data['close'].iloc[i]
            rolling_mean = data['rolling_mean'].iloc[i]
            
            # Calculate percentage deviation from mean
            deviation = (current_price - rolling_mean) / rolling_mean
            
            # Mean reversion logic: trade against the deviation
            if deviation > threshold:
                # Price is above mean by threshold% -> SELL (expecting it to fall back)
                signals.append(Signal.SELL)
            elif deviation < -threshold:
                # Price is below mean by threshold% -> BUY (expecting it to rise back)
                signals.append(Signal.BUY)
            else:
                # Price is close to mean -> HOLD
                signals.append(Signal.HOLD)
                
        return signals
    
    def should_enter_position(self, current_data: pd.Series) -> bool:
        """Check if we should enter a position."""
        if len(self.data) < self.get_parameter("lookback_period"):
            return False
            
        signals = self.generate_signals(self.data)
        if not signals:
            return False
            
        return signals[-1] == Signal.BUY
    
    def should_exit_position(self, current_data: pd.Series, position: Dict[str, Any]) -> bool:
        """Check if we should exit a position."""
        if len(self.data) < self.get_parameter("lookback_period"):
            return False
            
        signals = self.generate_signals(self.data)
        if not signals:
            return False
            
        return signals[-1] == Signal.SELL
    
    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        threshold = self.get_parameter("threshold_percentage")
        lookback = self.get_parameter("lookback_period")
        
        if threshold <= 0:
            raise ValueError("Threshold percentage must be positive")
        if lookback <= 0:
            raise ValueError("Lookback period must be positive")
            
        return True