"""Wall trap setup detection logic."""

import time
from typing import Dict, Any, Optional, List
from indicators import liquidity_walls, cvd


class WallTrapDetector:
    """Detects wall trap setups with CVD confirmation."""
    
    def __init__(self):
        self.last_cvd_slope = 'neutral'
        self.setup_state = {
            'wall_detected': False,
            'trap_phase': False,
            'cvd_confirmation': False,
            'wall_price': None,
            'wall_direction': None,
            'trap_start_time': None
        }
    
    def detect_setup(self, 
                    orderbook_data: Dict[str, Any],
                    trades_data: List[Dict[str, Any]],
                    current_price: float) -> Optional[Dict[str, Any]]:
        """
        Detect wall trap setup.
        
        Args:
            orderbook_data: Order book snapshot
            trades_data: Recent trades for CVD calculation
            current_price: Current market price
            
        Returns:
            Setup detection result or None
        """
        
        # 1. Detect liquidity walls
        walls = liquidity_walls.detect_liquidity_walls(
            bids=orderbook_data['bids'],
            asks=orderbook_data['asks'],
            mid_price=current_price,
            depth_range_pct=0.5,  # ±0.5%
            threshold_multiplier=3.0  # 3x average
        )
        
        # 2. Check if wall exists
        strongest_bid = walls['strongest_bid_wall']
        strongest_ask = walls['strongest_ask_wall']
        
        if not strongest_bid and not strongest_ask:
            self._reset_setup_state()
            return None
        
        # 3. Determine wall and expected direction
        if strongest_bid and (not strongest_ask or strongest_bid['size'] > strongest_ask['size']):
            wall = strongest_bid
            expected_direction = 'long'  # Expect price to bounce up from support
            wall_type = 'bid'
        else:
            wall = strongest_ask
            expected_direction = 'short'  # Expect price to drop from resistance
            wall_type = 'ask'
        
        wall_price = wall['price']
        
        # 4. Check trap phase (price moved away from wall)
        distance_pct = abs(current_price - wall_price) / wall_price * 100
        
        if distance_pct < 0.3:  # Too close to wall
            self._reset_setup_state()
            return None
        
        # 5. Calculate CVD
        cvd_data = cvd.get_cvd_summary(trades_data, window_minutes=60)
        current_slope = cvd_data['slope']
        
        # 6. Check CVD confirmation (trap building)
        required_slope = 'negative' if expected_direction == 'long' else 'positive'
        
        if current_slope != required_slope:
            # CVD not in trap phase yet
            return None
        
        # 7. Check CVD reversal
        slope_change = cvd.detect_slope_change(current_slope, self.last_cvd_slope)
        
        if slope_change == 'no_change':
            # Update last slope and continue monitoring
            self.last_cvd_slope = current_slope
            return None
        
        # 8. Check price direction (returning to wall)
        price_direction = self._get_price_direction(current_price, wall_price, wall_type)
        
        if not price_direction:
            return None
        
        # All conditions met - ALERT!
        alert = {
            'timestamp': int(time.time() * 1000),
            'type': 'wall_trap',
            'direction': expected_direction,
            'wall_price': wall_price,
            'wall_size': wall['size'],
            'asymmetry_ratio': wall['asymmetry_ratio'],
            'current_price': current_price,
            'distance_pct': distance_pct,
            'cvd_slope': current_slope,
            'cvd_reversal': slope_change,
            'strength': wall['strength'],
            'setup_confidence': self._calculate_confidence(wall, cvd_data, distance_pct)
        }
        
        # Reset state after alert
        self._reset_setup_state()
        self.last_cvd_slope = current_slope
        
        return alert
    
    def _reset_setup_state(self):
        """Reset setup detection state."""
        self.setup_state = {
            'wall_detected': False,
            'trap_phase': False,
            'cvd_confirmation': False,
            'wall_price': None,
            'wall_direction': None,
            'trap_start_time': None
        }
    
    def _get_price_direction(self, current_price: float, wall_price: float, wall_type: str) -> bool:
        """Check if price is returning toward wall."""
        if wall_type == 'bid':  # Support wall
            # Price should be dropping toward support
            return current_price < wall_price * 1.001  # Within 0.1% of wall
        else:  # Ask wall (resistance)
            # Price should be rising toward resistance
            return current_price > wall_price * 0.999  # Within 0.1% of wall
    
    def _calculate_confidence(self, wall: Dict[str, Any], cvd_data: Dict[str, Any], distance_pct: float) -> float:
        """Calculate setup confidence score (0-1)."""
        confidence = 0.0
        
        # Wall strength (0.4 weight)
        if wall['strength'] == 'strong':
            confidence += 0.4
        else:
            confidence += 0.2
        
        # Asymmetry ratio (0.3 weight)
        if wall['asymmetry_ratio'] > 2.0:
            confidence += 0.3
        elif wall['asymmetry_ratio'] > 1.5:
            confidence += 0.2
        else:
            confidence += 0.1
        
        # CVD strength (0.2 weight)
        cvd_strength = cvd_data['analysis']['strength']
        if 'strong' in cvd_strength:
            confidence += 0.2
        elif 'moderate' in cvd_strength:
            confidence += 0.1
        
        # Distance (0.1 weight)
        if 0.3 <= distance_pct <= 1.0:  # Good trap distance
            confidence += 0.1
        
        return min(confidence, 1.0)


# Global detector instance
wall_trap_detector = WallTrapDetector()


def detect_wall_trap_setup(orderbook_data: Dict[str, Any], 
                          trades_data: List[Dict[str, Any]], 
                          current_price: float) -> Optional[Dict[str, Any]]:
    """Global function to detect wall trap setup."""
    return wall_trap_detector.detect_setup(orderbook_data, trades_data, current_price)
