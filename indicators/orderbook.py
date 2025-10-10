"""Order book indicators and binning logic."""

import math
from typing import List, Tuple, Dict


def calculate_binned_profile(
    bids: List[Tuple[float, float]],
    asks: List[Tuple[float, float]],
    bin_size: float,
    window_pct: float,
    mid_price: float
) -> List[Dict]:
    """
    Aggregate order book into price bins for visualization.
    
    Args:
        bids: List of (price, quantity) tuples
        asks: List of (price, quantity) tuples
        bin_size: Bin size in USD (e.g., 50)
        window_pct: Window percentage around mid price (e.g., 2 means ±2%)
        mid_price: Mid price for centering the window
    
    Returns:
        List of dicts with keys: 'price' (bin center), 'size' (total quantity), 'side' ('bid'/'ask')
    """
    if not mid_price or not bids or not asks:
        return []
    
    # Calculate price window
    lower_bound = mid_price * (1.0 - window_pct / 100.0)
    upper_bound = mid_price * (1.0 + window_pct / 100.0)
    
    # Aggregate bids into bins
    bid_bins = {}
    for price, qty in bids:
        if price < lower_bound:
            continue
        bin_key = math.floor(price / bin_size) * bin_size
        bid_bins[bin_key] = bid_bins.get(bin_key, 0.0) + qty
    
    # Aggregate asks into bins
    ask_bins = {}
    for price, qty in asks:
        if price > upper_bound:
            continue
        bin_key = math.floor(price / bin_size) * bin_size
        ask_bins[bin_key] = ask_bins.get(bin_key, 0.0) + qty
    
    # Convert to list format for plotting
    result = []
    
    # Add bid bins (sorted by price)
    for bin_price in sorted(bid_bins.keys()):
        result.append({
            'price': bin_price + bin_size / 2.0,  # Center of bin
            'size': bid_bins[bin_price],
            'side': 'bid'
        })
    
    # Add ask bins (sorted by price)
    for bin_price in sorted(ask_bins.keys()):
        result.append({
            'price': bin_price + bin_size / 2.0,  # Center of bin
            'size': ask_bins[bin_price],
            'side': 'ask'
        })
    
    return result

