"""Order book scalping strategy - contrarian liquidity absorption."""

from typing import List, Tuple, Dict, Any, Optional


def calculate_imbalance(
    agg_bids: List[Tuple[float, float]], 
    agg_asks: List[Tuple[float, float]], 
    current_price: float,
    num_bins: int = 2
) -> Optional[Dict[str, Any]]:
    """
    Calculate volume imbalance in N bins from current price.
    Uses CONTRARIAN approach: Bid volume > Ask → SHORT bias
    
    Args:
        agg_bids: Aggregated bid levels [(price, quantity), ...]
        agg_asks: Aggregated ask levels [(price, quantity), ...]
        current_price: Current mid price
        num_bins: Number of $100 bins to analyze (default: 2 = $200 range)
    
    Returns:
        {
            'bias': 'short' | 'long' | None,
            'bid_volume': float,
            'ask_volume': float,
            'imbalance_ratio': float,  # Ratio of dominant side
            'first_bid_volume': float,
            'first_ask_volume': float,
            'first_bin_confirmed': bool
        }
        or None if insufficient data
    """
    if not agg_bids or not agg_asks:
        return None
    
    # Calculate range (num_bins × $100)
    bin_range = num_bins * 100  # e.g., 2 bins = $200
    
    # Filter bids within range (below current price)
    bid_volume = 0.0
    first_bid_volume = 0.0
    for price, quantity in agg_bids:
        if current_price - bin_range <= price < current_price:
            bid_volume += quantity
            # First bin is closest to current price
            if price >= current_price - 100:
                first_bid_volume += quantity
    
    # Filter asks within range (above current price)
    ask_volume = 0.0
    first_ask_volume = 0.0
    for price, quantity in agg_asks:
        if current_price < price <= current_price + bin_range:
            ask_volume += quantity
            # First bin is closest to current price
            if price <= current_price + 100:
                first_ask_volume += quantity
    
    # Require minimum volume
    total_volume = bid_volume + ask_volume
    if total_volume < 10.0:  # Minimum 10 BTC total
        return None
    
    # Calculate imbalance ratio
    if bid_volume > ask_volume:
        imbalance_ratio = bid_volume / (bid_volume + ask_volume)
        # CONTRARIAN: More bids → SHORT bias
        direction = 'short'
    elif ask_volume > bid_volume:
        imbalance_ratio = ask_volume / (bid_volume + ask_volume)
        # CONTRARIAN: More asks → LONG bias
        direction = 'long'
    else:
        imbalance_ratio = 0.5
        direction = None
    
    # Require minimum imbalance strength for signal generation (59% = moderate signal threshold)
    # Note: This function is used for signal generation only
    # For display purposes, we'll check threshold in the calling code
    if direction and imbalance_ratio < 0.59:
        return None
    
    # First bin confirmation
    if direction == 'short':
        first_bin_confirmed = first_bid_volume > first_ask_volume
    elif direction == 'long':
        first_bin_confirmed = first_ask_volume > first_bid_volume
    else:
        first_bin_confirmed = False
    
    return {
        'direction': direction,
        'bid_volume': bid_volume,
        'ask_volume': ask_volume,
        'imbalance_ratio': imbalance_ratio,
        'first_bid_volume': first_bid_volume,
        'first_ask_volume': first_ask_volume,
        'first_bin_confirmed': first_bin_confirmed
    }


def calculate_imbalance_display(
    agg_bids: List[Tuple[float, float]],
    agg_asks: List[Tuple[float, float]],
    current_price: float,
    num_bins: int = 2,  # Number of $100 bins to consider on each side
    bin_size: int = 100 # Default bin size
) -> Optional[Dict[str, Any]]:
    """
    Calculate imbalance for display purposes (no threshold filter).
    Shows any imbalance, even weak ones.
    """
    if not agg_bids or not agg_asks:
        return None

    # Calculate bin range
    bin_range = num_bins * bin_size  # e.g., 2 * 100 = $200 range

    # Filter bids within range (below current price)
    bid_volume = 0.0
    for price, quantity in agg_bids:
        if current_price - bin_range <= price < current_price:
            bid_volume += quantity
    
    # Filter asks within range (above current price)
    ask_volume = 0.0
    for price, quantity in agg_asks:
        if current_price < price <= current_price + bin_range:
            ask_volume += quantity
    
    # Require minimum volume
    total_volume = bid_volume + ask_volume
    if total_volume < 10.0:  # Minimum 10 BTC total
        return None
    
    # Calculate imbalance ratio
    if bid_volume > ask_volume:
        imbalance_ratio = bid_volume / (bid_volume + ask_volume)
        direction = 'short'
    elif ask_volume > bid_volume:
        imbalance_ratio = ask_volume / (bid_volume + ask_volume)
        direction = 'long'
    else:
        imbalance_ratio = 0.5
        direction = None
    
    # No threshold filter for display - show any imbalance
    return {
        'direction': direction,
        'bid_volume': bid_volume,
        'ask_volume': ask_volume,
        'imbalance_ratio': imbalance_ratio
    }


def check_cvd_reversal(
    current_slope: str,
    previous_slope: str
) -> Optional[Dict[str, Any]]:
    """
    Check if CVD slope changed direction.
    
    Args:
        current_slope: 'positive' | 'negative' | 'neutral'
        previous_slope: 'positive' | 'negative' | 'neutral'
    
    Returns:
        {
            'reversal': bool,
            'reversal_direction': 'to_positive' | 'to_negative' | None
        }
    """
    reversal = False
    reversal_direction = None
    
    # Detect reversals
    if previous_slope == 'negative' and current_slope == 'positive':
        reversal = True
        reversal_direction = 'to_positive'
    elif previous_slope == 'positive' and current_slope == 'negative':
        reversal = True
        reversal_direction = 'to_negative'
    
    return {
        'reversal': reversal,
        'reversal_direction': reversal_direction,
        'current_slope': current_slope,
        'previous_slope': previous_slope
    }


def generate_signal(
    imbalance_data: Dict[str, Any],
    cvd_reversal_data: Dict[str, Any],
    current_price: float,
    tp_distance: float = 120.0,
    sl_distance: float = 130.0
) -> Optional[Dict[str, Any]]:
    """
    Combine imbalance + CVD reversal to generate entry signal.
    
    Strategy Rules:
    - SHORT: Bid volume > Ask (contrarian) + CVD reverses to negative
    - LONG: Ask volume > Bid (contrarian) + CVD reverses to positive
    
    Args:
        imbalance_data: Output from calculate_imbalance()
        cvd_reversal_data: Output from check_cvd_reversal()
        current_price: Current mid price
        tp_distance: Take profit distance in USD (default: $120)
        sl_distance: Stop loss distance in USD (default: $130)
    
    Returns:
        Signal dictionary or None if no signal
    """
    if not imbalance_data or not cvd_reversal_data:
        return None
    
    # Check if imbalance is present
    bias = imbalance_data['bias']
    if not bias:
        return None
    
    # Check first bin confirmation
    if not imbalance_data['first_bin_confirmed']:
        return None
    
    # Check CVD reversal
    if not cvd_reversal_data['reversal']:
        return None
    
    # Match bias with CVD reversal direction
    reversal_dir = cvd_reversal_data['reversal_direction']
    
    if bias == 'short' and reversal_dir == 'to_negative':
        # SHORT signal confirmed
        direction = 'short'
        tp_price = current_price - tp_distance
        sl_price = current_price + sl_distance
    elif bias == 'long' and reversal_dir == 'to_positive':
        # LONG signal confirmed
        direction = 'long'
        tp_price = current_price + tp_distance
        sl_price = current_price - sl_distance
    else:
        # Bias and CVD reversal don't match
        return None
    
    # Calculate signal strength (based on imbalance ratio)
    strength = imbalance_data['imbalance_ratio']
    
    return {
        'signal_type': 'ORDERBOOK_SCALP',
        'direction': direction,
        'entry_price': current_price,
        'tp_price': tp_price,
        'sl_price': sl_price,
        'strength': strength,
        'bid_volume': imbalance_data['bid_volume'],
        'ask_volume': imbalance_data['ask_volume'],
        'imbalance_ratio': imbalance_data['imbalance_ratio'],
        'first_bid_volume': imbalance_data['first_bid_volume'],
        'first_ask_volume': imbalance_data['first_ask_volume'],
        'cvd_slope': cvd_reversal_data['current_slope']
    }

