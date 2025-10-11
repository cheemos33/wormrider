"""CVD (Cumulative Volume Delta) calculation and analysis."""

import numpy as np
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta


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
