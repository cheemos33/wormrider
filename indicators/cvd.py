"""CVD (Cumulative Volume Delta) calculation and analysis."""

import numpy as np
import warnings
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

# Suppress numpy warnings for polyfit
warnings.filterwarnings('ignore')


def calculate_cvd(trades: List[Dict[str, Any]], window_minutes: int = 60) -> Dict[str, Any]:
    """
    Calculate Cumulative Volume Delta from trades data.
    
    Args:
        trades: List of trade dictionaries with keys: timestamp, price, quantity, is_buy
        window_minutes: Time window for CVD calculation
    
    Returns:
        Dictionary with CVD data and statistics
    """
    if not trades:
        return {
            'cvd_series': [],
            'current_cvd': 0.0,
            'buy_volume': 0.0,
            'sell_volume': 0.0,
            'total_volume': 0.0,
            'window_minutes': window_minutes
        }
    
    # Sort trades by timestamp
    sorted_trades = sorted(trades, key=lambda x: x['timestamp'])
    
    # Calculate cutoff time
    if sorted_trades:
        latest_time = sorted_trades[-1]['timestamp']
        cutoff_time = latest_time - (window_minutes * 60 * 1000)  # Convert to milliseconds
    else:
        cutoff_time = 0
    
    # Filter trades within window
    window_trades = [t for t in sorted_trades if t['timestamp'] >= cutoff_time]
    
    # Calculate buy and sell volumes
    buy_volume = sum(t['quantity'] for t in window_trades if t['is_buy'])
    sell_volume = sum(t['quantity'] for t in window_trades if not t['is_buy'])
    total_volume = buy_volume + sell_volume
    
    # Calculate CVD (buy - sell)
    current_cvd = buy_volume - sell_volume
    
    # Create CVD time series (cumulative)
    cvd_series = []
    running_cvd = 0.0
    
    for trade in window_trades:
        if trade['is_buy']:
            running_cvd += trade['quantity']
        else:
            running_cvd -= trade['quantity']
        
        cvd_series.append({
            'timestamp': trade['timestamp'],
            'cvd': running_cvd,
            'price': trade['price'],
            'volume': trade['quantity']
        })
    
    return {
        'cvd_series': cvd_series,
        'current_cvd': current_cvd,
        'buy_volume': buy_volume,
        'sell_volume': sell_volume,
        'total_volume': total_volume,
        'window_minutes': window_minutes,
        'trade_count': len(window_trades)
    }


def calculate_cvd_slope(cvd_series: List[Dict[str, Any]], lookback_periods: int = 5) -> str:
    """
    Calculate CVD slope using linear regression on recent data points.
    
    Args:
        cvd_series: List of CVD data points with 'timestamp' and 'cvd' keys
        lookback_periods: Number of recent periods to analyze
    
    Returns:
        'positive', 'negative', or 'neutral'
    """
    if len(cvd_series) < lookback_periods:
        return 'neutral'
    
    # Get recent data points
    recent_data = cvd_series[-lookback_periods:]
    
    if len(recent_data) < 2:
        return 'neutral'
    
    # Extract timestamps and CVD values
    timestamps = [point['timestamp'] for point in recent_data]
    cvd_values = [point['cvd'] for point in recent_data]
    
    # Convert timestamps to relative time (seconds from first point)
    base_time = timestamps[0]
    relative_times = [(t - base_time) / 1000.0 for t in timestamps]  # Convert to seconds
    
    # Linear regression: y = mx + b
    # x = time, y = CVD
    try:
        slope, _ = np.polyfit(relative_times, cvd_values, 1)
        
        # Determine slope direction
        if slope > 0.01:  # Positive threshold
            return 'positive'
        elif slope < -0.01:  # Negative threshold
            return 'negative'
        else:
            return 'neutral'
            
    except (ValueError, np.linalg.LinAlgError):
        return 'neutral'


def detect_cvd_trend_segments(cvd_series: List[Dict[str, Any]], 
                              min_segment_size: int = 10,
                              slope_threshold: float = 0.1) -> List[Dict[str, Any]]:
    """
    Detect CVD trend segments using piecewise linear regression.
    Breaks CVD into segments with distinct trendlines.
    
    Args:
        cvd_series: List of CVD data points
        min_segment_size: Minimum number of points per segment
        slope_threshold: Threshold for detecting slope change
    
    Returns:
        List of segments with start, end, slope, direction
    """
    if len(cvd_series) < min_segment_size * 2:
        return []
    
    segments = []
    
    # Convert to numpy arrays
    timestamps = np.array([point['timestamp'] for point in cvd_series])
    cvd_values = np.array([point['cvd'] for point in cvd_series])
    
    # Normalize time (seconds from start)
    relative_times = (timestamps - timestamps[0]) / 1000.0
    
    # Simple segmentation: sliding window with slope change detection
    i = 0
    while i < len(cvd_values) - min_segment_size:
        # Start new segment
        segment_start = i
        
        # Calculate initial slope
        window_times = relative_times[i:i+min_segment_size]
        window_cvd = cvd_values[i:i+min_segment_size]
        
        try:
            current_slope, _ = np.polyfit(window_times, window_cvd, 1)
        except (ValueError, np.linalg.LinAlgError):
            i += min_segment_size
            continue
        
        # Extend segment while slope is consistent
        j = i + min_segment_size
        while j < len(cvd_values):
            # Check if adding next point changes slope significantly
            window_times = relative_times[i:j+1]
            window_cvd = cvd_values[i:j+1]
            
            try:
                new_slope, _ = np.polyfit(window_times, window_cvd, 1)
                
                # If slope changed significantly, end segment
                if abs(new_slope - current_slope) > slope_threshold:
                    break
                
                current_slope = new_slope
                j += 1
            except (ValueError, np.linalg.LinAlgError):
                break
        
        # Finalize segment
        segment_end = j
        
        # Calculate final slope for this segment
        segment_times = relative_times[segment_start:segment_end]
        segment_cvd = cvd_values[segment_start:segment_end]
        
        if len(segment_times) >= min_segment_size:
            try:
                final_slope, intercept = np.polyfit(segment_times, segment_cvd, 1)
                
                # Determine direction
                if final_slope > slope_threshold:
                    direction = 'upward'
                elif final_slope < -slope_threshold:
                    direction = 'downward'
                else:
                    direction = 'sideways'
                
                segments.append({
                    'start_idx': segment_start,
                    'end_idx': segment_end,
                    'start_time': timestamps[segment_start],
                    'end_time': timestamps[segment_end - 1],
                    'slope': final_slope,
                    'direction': direction,
                    'intercept': intercept,
                    'start_cvd': cvd_values[segment_start],
                    'end_cvd': cvd_values[segment_end - 1]
                })
            except (ValueError, np.linalg.LinAlgError):
                pass
        
        i = segment_end
    
    return segments


def detect_momentum_change(segments: List[Dict[str, Any]]) -> str:
    """
    Detect momentum changes from CVD trend segments.
    
    Returns:
        'upward_momentum', 'downward_momentum', 'sideways', or 'no_change'
    """
    if len(segments) < 2:
        return 'no_change'
    
    # Get last two segments
    prev_segment = segments[-2]
    current_segment = segments[-1]
    
    prev_dir = prev_segment['direction']
    curr_dir = current_segment['direction']
    
    # Detect transitions
    if prev_dir != 'upward' and curr_dir == 'upward':
        return 'upward_momentum'
    elif prev_dir != 'downward' and curr_dir == 'downward':
        return 'downward_momentum'
    elif curr_dir == 'sideways':
        return 'sideways'
    else:
        return 'no_change'


def detect_slope_change(current_slope: str, previous_slope: str) -> str:
    """
    Detect CVD slope direction change.
    
    Args:
        current_slope: Current slope ('positive', 'negative', 'neutral')
        previous_slope: Previous slope ('positive', 'negative', 'neutral')
    
    Returns:
        'negative_to_positive', 'positive_to_negative', or 'no_change'
    """
    if current_slope == 'positive' and previous_slope == 'negative':
        return 'negative_to_positive'
    elif current_slope == 'negative' and previous_slope == 'positive':
        return 'positive_to_negative'
    else:
        return 'no_change'


def analyze_cvd_strength(cvd_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze CVD strength and provide trading signals.
    
    Args:
        cvd_data: Output from calculate_cvd()
    
    Returns:
        Analysis dictionary with strength indicators
    """
    if not cvd_data['cvd_series']:
        return {
            'strength': 'neutral',
            'signal': 'none',
            'ratio': 0.0,
            'volume_ratio': 0.0
        }
    
    current_cvd = cvd_data['current_cvd']
    buy_volume = cvd_data['buy_volume']
    sell_volume = cvd_data['sell_volume']
    total_volume = cvd_data['total_volume']
    
    # Calculate ratios
    if total_volume > 0:
        volume_ratio = buy_volume / sell_volume if sell_volume > 0 else float('inf')
        cvd_ratio = abs(current_cvd) / total_volume if total_volume > 0 else 0
    else:
        volume_ratio = 1.0
        cvd_ratio = 0.0
    
    # Determine strength
    if cvd_ratio > 0.1:  # CVD is >10% of total volume
        if current_cvd > 0:
            strength = 'strong_buy'
            signal = 'bullish'
        else:
            strength = 'strong_sell'
            signal = 'bearish'
    elif cvd_ratio > 0.05:  # CVD is >5% of total volume
        if current_cvd > 0:
            strength = 'moderate_buy'
            signal = 'bullish'
        else:
            strength = 'moderate_sell'
            signal = 'bearish'
    else:
        strength = 'neutral'
        signal = 'none'
    
    return {
        'strength': strength,
        'signal': signal,
        'cvd_ratio': cvd_ratio,
        'volume_ratio': volume_ratio,
        'current_cvd': current_cvd,
        'buy_volume': buy_volume,
        'sell_volume': sell_volume
    }


def get_cvd_summary(trades: List[Dict[str, Any]], window_minutes: int = 60) -> Dict[str, Any]:
    """
    Get comprehensive CVD analysis summary.
    
    Args:
        trades: List of trade dictionaries
        window_minutes: Analysis window
    
    Returns:
        Complete CVD analysis including slope and strength
    """
    # Calculate CVD
    cvd_data = calculate_cvd(trades, window_minutes)
    
    # Calculate slope
    slope = calculate_cvd_slope(cvd_data['cvd_series'])
    
    # Analyze strength
    analysis = analyze_cvd_strength(cvd_data)
    
    return {
        **cvd_data,
        'slope': slope,
        'analysis': analysis
    }
