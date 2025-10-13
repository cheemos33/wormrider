"""Order book aggregation logic for binning price levels."""

from typing import List, Tuple, Dict
from collections import defaultdict


def aggregate_orderbook(
    levels: List[Tuple[float, float]], 
    bin_size: int
) -> List[Tuple[float, float]]:
    """
    Aggregate raw order book levels into price bins.
    
    Args:
        levels: List of (price, quantity) tuples - raw levels from API
        bin_size: Price bin size in USD (e.g., 100)
    
    Returns:
        List of (bin_center_price, total_quantity) tuples - aggregated bins
        Sorted by price (ascending for bids, descending for asks)
    
    Example:
        Input: [(50045.2, 1.5), (50067.8, 2.3), (50102.1, 0.8)]
        bin_size: 100
        Output: [(50050.0, 3.8), (50100.0, 0.8)]
    """
    if not levels:
        return []
    
    # Dictionary to accumulate quantities per bin
    bins: Dict[float, float] = defaultdict(float)
    
    for price, quantity in levels:
        # Round price to nearest bin center
        # Example: 50045.2 with bin_size=100 → 50000 + 50 = 50050
        bin_center = round(price / bin_size) * bin_size
        
        # Accumulate quantity in this bin
        bins[bin_center] += quantity
    
    # Convert to sorted list
    aggregated = sorted(bins.items(), key=lambda x: x[0])
    
    return aggregated


def aggregate_bids_asks(
    bids: List[Tuple[float, float]], 
    asks: List[Tuple[float, float]], 
    bin_size: int
) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    """
    Aggregate both bids and asks separately.
    
    Args:
        bids: Raw bid levels (higher price = better bid)
        asks: Raw ask levels (lower price = better ask)
        bin_size: Price bin size in USD
    
    Returns:
        (aggregated_bids, aggregated_asks) - both sorted appropriately
    """
    agg_bids = aggregate_orderbook(bids, bin_size)
    agg_asks = aggregate_orderbook(asks, bin_size)
    
    # Bids should be sorted descending (highest price first)
    agg_bids.sort(key=lambda x: x[0], reverse=True)
    
    # Asks should be sorted ascending (lowest price first)
    agg_asks.sort(key=lambda x: x[0])
    
    return agg_bids, agg_asks


def get_aggregation_stats(
    raw_levels: List[Tuple[float, float]], 
    aggregated_levels: List[Tuple[float, float]]
) -> Dict[str, any]:
    """
    Get statistics about the aggregation process.
    
    Returns:
        Dictionary with compression ratio, total volume, etc.
    """
    raw_count = len(raw_levels)
    agg_count = len(aggregated_levels)
    
    raw_volume = sum(qty for _, qty in raw_levels)
    agg_volume = sum(qty for _, qty in aggregated_levels)
    
    compression_ratio = raw_count / agg_count if agg_count > 0 else 0
    
    return {
        'raw_levels': raw_count,
        'aggregated_bins': agg_count,
        'compression_ratio': compression_ratio,
        'raw_volume': raw_volume,
        'aggregated_volume': agg_volume,
        'volume_preserved': abs(raw_volume - agg_volume) < 0.01  # Should be equal
    }
