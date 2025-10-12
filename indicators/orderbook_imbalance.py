"""Order book bid-ask imbalance analysis."""

from typing import List, Tuple, Dict, Any


def calculate_imbalance_at_distances(
    bids: List[Tuple[float, float]], 
    asks: List[Tuple[float, float]], 
    mid_price: float,
    distances_pct: List[float] = [0.0005, 0.001, 0.0025, 0.005, 0.0075, 0.01]  # 0.05% to 1% (within Binance depth)
) -> Tuple[List[Dict[str, Any]], str, float]:
    """
    Calculate bid-ask imbalance at various percentage-based price distances.
    
    Args:
        bids: List of (price, size) tuples
        asks: List of (price, size) tuples
        mid_price: Current mid price
        distances_pct: List of percentage distances (e.g., 0.01 = 1%)
    
    Returns:
        Tuple of (results list, confluence status, confluence strength)
    """
    
    results = []
    
    for pct_distance in distances_pct:
        # Convert percentage to absolute price
        distance = mid_price * pct_distance
        
        lower_bound = mid_price - distance
        upper_bound = mid_price + distance
        
        # Calculate bid volume within range (below mid price)
        bid_volume = sum(size for price, size in bids if lower_bound <= price < mid_price)
        
        # Calculate ask volume within range (above mid price)
        ask_volume = sum(size for price, size in asks if mid_price < price <= upper_bound)
        
        # Determine imbalance
        total_volume = bid_volume + ask_volume
        
        if total_volume > 0:
            bid_pct = (bid_volume / total_volume) * 100
            ask_pct = (ask_volume / total_volume) * 100
            
            # Threshold for significant imbalance (> 55%)
            if bid_pct > 55:
                imbalance = 'BID'
                strength = bid_pct - 50  # How much > 50%
            elif ask_pct > 55:
                imbalance = 'ASK'
                strength = ask_pct - 50
            else:
                imbalance = 'NEUTRAL'
                strength = abs(bid_pct - 50)
        else:
            imbalance = 'NEUTRAL'
            bid_pct = 50
            ask_pct = 50
            strength = 0
        
        ratio = bid_volume / ask_volume if ask_volume > 0 else (float('inf') if bid_volume > 0 else 1.0)
        
        results.append({
            'distance_pct': pct_distance * 100,  # Store as percentage (e.g., 1.0 for 1%)
            'distance_usd': distance,  # Store absolute USD distance for reference
            'bid_volume': bid_volume,
            'ask_volume': ask_volume,
            'bid_pct': bid_pct,
            'ask_pct': ask_pct,
            'imbalance': imbalance,
            'ratio': ratio,
            'strength': strength
        })
    
    # Check confluence (all levels showing same imbalance)
    imbalances = [r['imbalance'] for r in results]
    
    bid_count = sum(1 for i in imbalances if i == 'BID')
    ask_count = sum(1 for i in imbalances if i == 'ASK')
    neutral_count = sum(1 for i in imbalances if i == 'NEUTRAL')
    
    total = len(imbalances)
    
    if bid_count == total:
        confluence = 'ALL BID'
        confluence_strength = 1.0
    elif ask_count == total:
        confluence = 'ALL ASK'
        confluence_strength = 1.0
    elif bid_count >= total * 0.75:
        confluence = 'MOSTLY BID'
        confluence_strength = bid_count / total
    elif ask_count >= total * 0.75:
        confluence = 'MOSTLY ASK'
        confluence_strength = ask_count / total
    else:
        confluence = 'MIXED'
        confluence_strength = max(bid_count, ask_count) / total
    
    return results, confluence, confluence_strength


def get_imbalance_signal(imbalance_data: List[Dict[str, Any]], confluence: str) -> str:
    """
    Get trading signal from imbalance data.
    
    Returns:
        'BULLISH', 'BEARISH', or 'NEUTRAL'
    """
    
    if confluence == 'ALL BID' or confluence == 'MOSTLY BID':
        return 'BULLISH'
    elif confluence == 'ALL ASK' or confluence == 'MOSTLY ASK':
        return 'BEARISH'
    else:
        return 'NEUTRAL'
