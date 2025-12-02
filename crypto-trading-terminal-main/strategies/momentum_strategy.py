"""
Momentum-based trading strategy.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from .base_strategy import BaseStrategy, Signal

class MomentumStrategy(BaseStrategy):
    """Momentum-based trading strategy using price and volume momentum."""
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            "lookback_period": 14,
            "momentum_threshold": 0.02,
            "volume_threshold": 1.5,
            "min_data_points": 20
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("Momentum Strategy", default_params)
        
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """Generate signals based on momentum indicators."""
        if len(data) < self.get_parameter("min_data_points"):
            return [Signal.HOLD] * len(data)
            
        lookback = self.get_parameter("lookback_period")
        momentum_threshold = self.get_parameter("momentum_threshold")
        volume_threshold = self.get_parameter("volume_threshold")
        
        # Calculate momentum indicators
        data['price_momentum'] = data['close'].pct_change(lookback)
        data['volume_ma'] = data['volume'].rolling(window=lookback).mean()
        data['volume_ratio'] = data['volume'] / data['volume_ma']
        
        # Generate signals
        signals = []
        for i in range(len(data)):
            if i < lookback:
                signals.append(Signal.HOLD)
                continue
                
            price_momentum = data['price_momentum'].iloc[i]
            volume_ratio = data['volume_ratio'].iloc[i]
            
            # Strong bullish momentum with high volume
            if price_momentum > momentum_threshold and volume_ratio > volume_threshold:
                signals.append(Signal.BUY)
            # Strong bearish momentum with high volume
            elif price_momentum < -momentum_threshold and volume_ratio > volume_threshold:
                signals.append(Signal.SELL)
            else:
                signals.append(Signal.HOLD)
                
        return signals
    
    def should_enter_position(self, current_data: pd.Series) -> bool:
        """Check if we should enter a position based on momentum."""
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
        lookback = self.get_parameter("lookback_period")
        momentum_threshold = self.get_parameter("momentum_threshold")
        volume_threshold = self.get_parameter("volume_threshold")
        
        if lookback <= 0:
            raise ValueError("Lookback period must be positive")
        if momentum_threshold <= 0:
            raise ValueError("Momentum threshold must be positive")
        if volume_threshold <= 0:
            raise ValueError("Volume threshold must be positive")
            
        return True
