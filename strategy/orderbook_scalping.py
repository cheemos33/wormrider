"""Order book scalping strategy - contrarian liquidity absorption."""

from typing import List, Tuple, Dict, Any, Optional


def calculate_imbalance_first_bin_only(
    agg_bids: List[Tuple[float, float]],
    agg_asks: List[Tuple[float, float]],
    current_price: float,
    bin_size: int = 100
) -> Optional[Dict[str, Any]]:
    """
    Calculate imbalance using ONLY the first bin ($100) on each side.
    This is more sensitive to immediate order book pressure.
    
    Args:
        agg_bids: List of (price_bin_midpoint, quantity) for aggregated bids.
        agg_asks: List of (price_bin_midpoint, quantity) for aggregated asks.
        current_price: Current mid-price.
        bin_size: The size of each bin (default 100 for $100 bins).
        
    Returns:
        A dictionary with 'direction', 'bid_volume', 'ask_volume', 'imbalance_ratio',
        'first_bin_bid_volume', 'first_bin_ask_volume', 'first_bin_confirmed' if conditions met, else None.
    """
    if not agg_bids or not agg_asks:
        return None

    # Get ONLY the first bin on each side (closest to current price)
    first_bid_volume = 0.0
    for price, quantity in agg_bids:
        if price >= current_price - bin_size and price < current_price:
            first_bid_volume += quantity
    
    first_ask_volume = 0.0
    for price, quantity in agg_asks:
        if price > current_price and price <= current_price + bin_size:
            first_ask_volume += quantity
    
    # Require minimum volume
    total_volume = first_bid_volume + first_ask_volume
    if total_volume < 5.0:  # Minimum 5 BTC in first bins
        return None
    
    # Calculate imbalance ratio
    direction = None
    imbalance_ratio = 0.5
    
    if first_bid_volume > first_ask_volume:
        imbalance_ratio = first_bid_volume / (first_bid_volume + first_ask_volume)
        # CONTRARIAN: More bids → SHORT bias
        direction = 'short'
    elif first_ask_volume > first_bid_volume:
        imbalance_ratio = first_ask_volume / (first_bid_volume + first_ask_volume)
        # CONTRARIAN: More asks → LONG bias
        direction = 'long'
    else:
        imbalance_ratio = 0.5
        direction = None
    
    # Require minimum imbalance strength for signal generation (60-66% = strong signal threshold)
    # Note: This function is used for signal generation only
    # For display purposes, we'll check threshold in the calling code
    if direction and (imbalance_ratio < 0.60 or imbalance_ratio >= 0.66):
        return None
    
    # First bin confirmation (always true since we only use first bins)
    first_bin_confirmed = True
    
    return {
        'direction': direction,
        'bid_volume': first_bid_volume,
        'ask_volume': first_ask_volume,
        'imbalance_ratio': imbalance_ratio,
        'first_bid_volume': first_bid_volume,
        'first_ask_volume': first_ask_volume,
        'first_bin_confirmed': first_bin_confirmed
    }


def calculate_imbalance(
    agg_bids: List[Tuple[float, float]], 
    agg_asks: List[Tuple[float, float]], 
    current_price: float,
    num_bins: int = 2
) -> Optional[Dict[str, Any]]:
    """
    Calculate volume imbalance in 2 bins from current price.
    Uses CONTRARIAN approach: Bid volume > Ask → SHORT bias
    Threshold: 60-66% (sweet spot from analysis)
    
    Args:
        agg_bids: Aggregated bid levels [(price, quantity), ...]
        agg_asks: Aggregated ask levels [(price, quantity), ...]
        current_price: Current mid price
        num_bins: Number of $100 bins to analyze (default: 2 = $200 range)
    
    Returns:
        Signal dict or None if no signal
    """
    if not agg_bids or not agg_asks:
        return None
    
    # Calculate range (2 bins × $100 = $200)
    bin_range = num_bins * 100
    
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
    
    # SWEET SPOT: 60-66% imbalance (analysis showed best PnL)
    # Below 60%: too weak
    # Above 66%: counter-productive
    if direction and not (0.60 <= imbalance_ratio < 0.66):
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


def calculate_imbalance_display_first_bin(
    agg_bids: List[Tuple[float, float]],
    agg_asks: List[Tuple[float, float]],
    current_price: float,
    bin_size: int = 100
) -> Optional[Dict[str, Any]]:
    """
    Calculate imbalance for display using ONLY first bin (no threshold filter).
    """
    if not agg_bids or not agg_asks:
        return None

    # Get ONLY the first bin on each side
    first_bid_volume = 0.0
    for price, quantity in agg_bids:
        if price >= current_price - bin_size and price < current_price:
            first_bid_volume += quantity
    
    first_ask_volume = 0.0
    for price, quantity in agg_asks:
        if price > current_price and price <= current_price + bin_size:
            first_ask_volume += quantity
    
    total_volume = first_bid_volume + first_ask_volume
    if total_volume < 5.0:
        return None
    
    # Calculate imbalance ratio
    if first_bid_volume > first_ask_volume:
        imbalance_ratio = first_bid_volume / (first_bid_volume + first_ask_volume)
        direction = 'short'
    elif first_ask_volume > first_bid_volume:
        imbalance_ratio = first_ask_volume / (first_bid_volume + first_ask_volume)
        direction = 'long'
    else:
        imbalance_ratio = 0.5
        direction = None
    
    # No threshold filter for display
    return {
        'direction': direction,
        'bid_volume': first_bid_volume,
        'ask_volume': first_ask_volume,
        'imbalance_ratio': imbalance_ratio
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


def calculate_hybrid_sq_imbalance(
    agg_bids: List[Tuple[float, float]], 
    agg_asks: List[Tuple[float, float]], 
    current_price: float,
    historical_agg_bids: List[Tuple[float, float]],
    historical_agg_asks: List[Tuple[float, float]],
    snapshot_history: List[Dict[str, Any]],
    num_bins: int = 2
) -> Optional[Dict[str, Any]]:
    """
    Calculate HYBRID_SQ imbalance - requires 2 consecutive snapshot signals + historical confluence.
    
    HYBRID_SQ Logic:
    1. Two consecutive snapshot imbalances in same direction (55-66% threshold)
    2. Historical aggregated data confluence (60-66% threshold)
    3. All must be same direction
    
    Args:
        agg_bids: Current snapshot aggregated bids
        agg_asks: Current snapshot aggregated asks
        current_price: Current mid price
        historical_agg_bids: Historical aggregated bids
        historical_agg_asks: Historical aggregated asks
        snapshot_history: List of recent snapshot imbalances
        num_bins: Number of bins to analyze (default: 2)
    
    Returns:
        HYBRID_SQ signal dict or None
    """
    if not agg_bids or not agg_asks:
        return None
    
    # Step 1: Check current snapshot imbalance (55-66% threshold)
    current_imbalance = calculate_imbalance(agg_bids, agg_asks, current_price, num_bins)
    if not current_imbalance:
        return None
    
    # Override threshold for HYBRID_SQ (55-66% instead of 60-66%)
    current_ratio = current_imbalance['imbalance_ratio']
    if not (0.55 <= current_ratio < 0.66):
        return None
    
    # Step 2: Check if we have a previous snapshot in same direction (55-66% threshold)
    if len(snapshot_history) < 1:
        return None
    
    previous_imbalance = snapshot_history[-1]
    if (previous_imbalance['direction'] != current_imbalance['direction'] or
        not (0.55 <= previous_imbalance['imbalance_ratio'] < 0.66)):
        return None
    
    # Step 3: Check historical aggregated data confluence (60-66% threshold)
    if not historical_agg_bids or not historical_agg_asks:
        return None
    
    historical_imbalance = calculate_imbalance(
        historical_agg_bids, historical_agg_asks, current_price, num_bins
    )
    if not historical_imbalance:
        return None
    
    # Historical must be same direction and meet 60-66% threshold
    if (historical_imbalance['direction'] != current_imbalance['direction'] or
        not (0.60 <= historical_imbalance['imbalance_ratio'] < 0.66)):
        return None
    
    # HYBRID_SQ confluence confirmed!
    # Use average of current and historical ratios
    avg_ratio = (current_imbalance['imbalance_ratio'] + historical_imbalance['imbalance_ratio']) / 2
    
    return {
        'direction': current_imbalance['direction'],
        'bid_volume': current_imbalance['bid_volume'],
        'ask_volume': current_imbalance['ask_volume'],
        'imbalance_ratio': avg_ratio,
        'first_bid_volume': current_imbalance['first_bid_volume'],
        'first_ask_volume': current_imbalance['first_ask_volume'],
        'first_bin_confirmed': current_imbalance['first_bin_confirmed'],
        'signal_type': 'HYBRID_SQ',
        'snapshot_ratio': current_imbalance['imbalance_ratio'],
        'historical_ratio': historical_imbalance['imbalance_ratio'],
        'confluence_confirmed': True
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

