"""Enhanced liquidity wall detection with asymmetry analysis."""

from typing import List, Dict, Any, Tuple
import config


def detect_liquidity_walls(bids: List[Tuple[float, float]], 
                          asks: List[Tuple[float, float]], 
                          mid_price: float,
                          depth_range_pct: float = 0.5,
                          threshold_multiplier: float = 3.0) -> Dict[str, Any]:
    """
    Detect liquidity walls with asymmetry analysis.
    
    Args:
        bids: List of (price, size) tuples
        asks: List of (price, size) tuples  
        mid_price: Current mid price
        depth_range_pct: Depth range around mid (default 0.5%)
        threshold_multiplier: Wall = avg_size × multiplier (default 3x)
    
    Returns:
        Dictionary with wall analysis results
    """
    
    # Define depth range
    depth_min = mid_price * (1 - depth_range_pct / 100)
    depth_max = mid_price * (1 + depth_range_pct / 100)
    
    # Filter orders within depth range
    filtered_bids = [(p, s) for p, s in bids if depth_min <= p <= depth_max]
    filtered_asks = [(p, s) for p, s in asks if depth_min <= p <= depth_max]
    
    # Calculate average size
    all_sizes = [s for _, s in filtered_bids + filtered_asks]
    avg_size = sum(all_sizes) / len(all_sizes) if all_sizes else 0
    
    # Find walls (levels > threshold)
    threshold = avg_size * threshold_multiplier
    
    bid_walls = []
    ask_walls = []
    
    # Detect bid walls
    for price, size in filtered_bids:
        if size >= threshold:
            asymmetry_ratio = calculate_asymmetry_ratio(
                price, size, filtered_bids, filtered_asks, mid_price
            )
            bid_walls.append({
                'price': price,
                'size': size,
                'asymmetry_ratio': asymmetry_ratio,
                'strength': 'strong' if asymmetry_ratio > 2.0 else 'medium'
            })
    
    # Detect ask walls  
    for price, size in filtered_asks:
        if size >= threshold:
            asymmetry_ratio = calculate_asymmetry_ratio(
                price, size, filtered_bids, filtered_asks, mid_price
            )
            ask_walls.append({
                'price': price,
                'size': size,
                'asymmetry_ratio': asymmetry_ratio,
                'strength': 'strong' if asymmetry_ratio > 2.0 else 'medium'
            })
    
    # Sort walls by size (strongest first)
    bid_walls.sort(key=lambda x: x['size'], reverse=True)
    ask_walls.sort(key=lambda x: x['size'], reverse=True)
    
    # Find strongest walls
    strongest_bid = bid_walls[0] if bid_walls else None
    strongest_ask = ask_walls[0] if ask_walls else None
    
    return {
        'bid_walls': bid_walls,
        'ask_walls': ask_walls,
        'strongest_bid_wall': strongest_bid,
        'strongest_ask_wall': strongest_ask,
        'depth_range': (depth_min, depth_max),
        'avg_size': avg_size,
        'threshold': threshold,
        'total_walls': len(bid_walls) + len(ask_walls)
    }


def calculate_asymmetry_ratio(wall_price: float, 
                             wall_size: float,
                             bids: List[Tuple[float, float]], 
                             asks: List[Tuple[float, float]], 
                             mid_price: float) -> float:
    """
    Calculate asymmetry ratio for a wall.
    
    Asymmetry = (Wall side cumulative volume) / (Opposite side cumulative volume)
    Higher ratio = stronger wall (more imbalance)
    """
    
    # Calculate distance from mid price
    distance = abs(wall_price - mid_price)
    
    # Wall side (same side as wall)
    if wall_price < mid_price:  # Bid wall
        wall_side_volume = sum(size for price, size in bids 
                              if abs(price - mid_price) <= distance)
    else:  # Ask wall
        wall_side_volume = sum(size for price, size in asks 
                              if abs(price - mid_price) <= distance)
    
    # Opposite side (same distance from mid)
    if wall_price < mid_price:  # Bid wall -> check ask side
        opposite_side_volume = sum(size for price, size in asks 
                                  if abs(price - mid_price) <= distance)
    else:  # Ask wall -> check bid side
        opposite_side_volume = sum(size for price, size in bids 
                                  if abs(price - mid_price) <= distance)
    
    # Calculate ratio
    if opposite_side_volume > 0:
        return wall_side_volume / opposite_side_volume
    else:
        return float('inf') if wall_side_volume > 0 else 1.0


def analyze_wall_strength(walls_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze overall wall strength and market structure.
    
    Returns:
        Analysis with market bias and strength indicators
    """
    
    bid_walls = walls_data['bid_walls']
    ask_walls = walls_data['ask_walls']
    
    # Calculate total wall strength
    total_bid_strength = sum(w['size'] * w['asymmetry_ratio'] for w in bid_walls)
    total_ask_strength = sum(w['size'] * w['asymmetry_ratio'] for w in ask_walls)
    
    # Market bias
    if total_bid_strength > total_ask_strength * 1.5:
        bias = 'bullish'
    elif total_ask_strength > total_bid_strength * 1.5:
        bias = 'bearish'
    else:
        bias = 'neutral'
    
    # Overall strength
    total_strength = total_bid_strength + total_ask_strength
    if total_strength > walls_data['avg_size'] * 10:
        strength_level = 'high'
    elif total_strength > walls_data['avg_size'] * 5:
        strength_level = 'medium'
    else:
        strength_level = 'low'
    
    return {
        'bias': bias,
        'strength_level': strength_level,
        'total_bid_strength': total_bid_strength,
        'total_ask_strength': total_ask_strength,
        'wall_count': walls_data['total_walls'],
        'strongest_bid': walls_data['strongest_bid_wall'],
        'strongest_ask': walls_data['strongest_ask_wall']
    }
