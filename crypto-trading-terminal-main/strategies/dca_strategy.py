"""
Dollar Cost Averaging (DCA) trading strategy.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from datetime import datetime, timedelta
from .base_strategy import BaseStrategy, Signal

class DCAStrategy(BaseStrategy):
    """Dollar Cost Averaging strategy - buys at regular intervals regardless of price."""
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            "interval_minutes": 30,      # Buy every 30 minutes
            "position_size": 0.01,       # Buy 0.01 ETH each time
            "max_positions": 10,         # Maximum number of DCA positions
            "price_threshold": 0.05,     # 5% price drop triggers extra buy
            "min_data_points": 5         # Need at least 5 data points
        }
        if parameters:
            default_params.update(parameters)
        super().__init__("DCA", default_params)
        
        # Track last buy time and today's buys
        self.last_buy_time = None
        self.today_buys = 0
        self.is_active = True
        
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """Generate signals based on DCA logic."""
        if len(data) < self.get_parameter("min_data_points"):
            return [Signal.HOLD] * len(data)
            
        interval_minutes = self.get_parameter("interval_minutes")
        price_threshold = self.get_parameter("price_threshold")
        
        # Generate signals
        signals = []
        for i in range(len(data)):
            if i < 1:
                signals.append(Signal.HOLD)
                continue
                
            current_price = data['close'].iloc[i]
            prev_price = data['close'].iloc[i-1]
            
            # Calculate time since last buy (simulate with data index)
            time_since_last = i * 5  # Assume 5 minutes per data point
            
            # Regular DCA buy (every interval_minutes)
            if time_since_last >= interval_minutes:
                signals.append(Signal.BUY)
            # Extra buy on significant price drop
            elif current_price < prev_price * (1 - price_threshold):
                signals.append(Signal.BUY)
            else:
                signals.append(Signal.HOLD)
                
        return signals
    
    def should_enter_position(self, current_data: pd.Series) -> bool:
        """Check if we should enter a DCA position."""
        # Check if DCA is active
        if not getattr(self, 'is_active', True):
            return False
            
        now = datetime.now()
        interval_minutes = self.get_parameter("interval_minutes")
        
        # Debug logging
        print(f"DCA Check - Active: {getattr(self, 'is_active', True)}, Interval: {interval_minutes} min")
        
        # Check if enough time has passed since last buy
        if self.last_buy_time is None:
            print("DCA: First buy - returning True")
            return True
            
        time_since_last = (now - self.last_buy_time).total_seconds() / 60
        should_buy = time_since_last >= interval_minutes
        
        print(f"DCA: Time since last buy: {time_since_last:.2f} min, Interval: {interval_minutes} min, Should buy: {should_buy}")
        
        return should_buy
    
    def should_exit_position(self, current_data: pd.Series, position: Dict[str, Any]) -> bool:
        """DCA typically doesn't exit positions automatically."""
        return False
    
    def get_position_size(self) -> float:
        """Get the fixed position size for DCA."""
        return self.get_parameter("position_size")
    
    def record_buy(self):
        """Record that a buy was executed."""
        self.last_buy_time = datetime.now()
        self.today_buys += 1
    
    def validate_parameters(self) -> bool:
        """Validate strategy parameters."""
        interval = self.get_parameter("interval_minutes")
        size = self.get_parameter("position_size")
        max_pos = self.get_parameter("max_positions")
        
        if interval <= 0:
            raise ValueError("Interval must be positive")
        if size <= 0:
            raise ValueError("Position size must be positive")
        if max_pos <= 0:
            raise ValueError("Max positions must be positive")
            
        return True