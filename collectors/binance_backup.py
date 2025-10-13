"""Binance data collector for continuous order book sampling."""

import time
import threading
from typing import Callable, List, Tuple
import httpx
import config
from indicators.orderbook_aggregation import aggregate_bids_asks
from database import db


def fetch_orderbook_snapshot(symbol: str) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]], float]:
    """
    Fetch order book snapshot via REST API.
    
    Returns:
        (bids, asks, mid_price) where bids/asks are lists of (price, quantity) tuples
    """
    url = f"{config.BINANCE_REST_URL}/fapi/v1/depth"
    params = {
        "symbol": symbol,
        "limit": config.ORDERBOOK_DEPTH_LIMIT
    }
    
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        bids = [(float(price), float(qty)) for price, qty in data['bids']]
        asks = [(float(price), float(qty)) for price, qty in data['asks']]
        
        # Calculate mid price
        best_bid = float(data['bids'][0][0]) if data['bids'] else 0.0
        best_ask = float(data['asks'][0][0]) if data['asks'] else 0.0
        mid_price = (best_bid + best_ask) / 2.0 if best_bid and best_ask else 0.0
        
        return bids, asks, mid_price
    
    except Exception as e:
        print(f"Error fetching order book for {symbol}: {e}")
        return [], [], 0.0


def start_collection(
    symbol: str,
    interval_seconds: int,
    callback: Callable[[str, int, List[Tuple[float, float]], List[Tuple[float, float]], float], None]
) -> threading.Thread:
    """
    Start background thread to collect order book data at regular intervals.
    Now also aggregates and stores data in the aggregated table.
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        interval_seconds: Sampling interval
        callback: Function to call with (symbol, timestamp_ms, bids, asks, mid_price)
                 (for backward compatibility with existing UI)
    
    Returns:
        The background thread (already started)
    """
    def _collect():
        print(f"Starting order book collection for {symbol} every {interval_seconds}s")
        print(f"Fetching {config.ORDERBOOK_DEPTH_LIMIT} levels, aggregating to ${config.DEFAULT_AGG_BIN_SIZE} bins")
        
        while True:
            try:
                timestamp_ms = int(time.time() * 1000)
                bids, asks, mid_price = fetch_orderbook_snapshot(symbol)
                
                if bids and asks:
                    # Call existing callback for backward compatibility (raw data)
                    callback(symbol, timestamp_ms, bids, asks, mid_price)
                    
                    # NEW: Aggregate and store in new table
                    agg_bids, agg_asks = aggregate_bids_asks(
                        bids, 
                        asks, 
                        config.DEFAULT_AGG_BIN_SIZE
                    )
                    
                    # Store aggregated data
                    db.insert_aggregated_snapshot(
                        symbol=symbol,
                        timestamp=timestamp_ms,
                        bin_size=config.DEFAULT_AGG_BIN_SIZE,
                        agg_bids=agg_bids,
                        agg_asks=agg_asks
                    )
                    
                    # Log stats every 10 snapshots (reduce noise)
                    if timestamp_ms % 50000 < interval_seconds * 1000:  # ~every 50 seconds
                        print(f"[{symbol}] Collected: {len(bids)}+{len(asks)} raw → {len(agg_bids)}+{len(agg_asks)} bins")
                else:
                    print(f"[{symbol}] Failed to fetch data, retrying...")
                
            except Exception as e:
                print(f"Error in collection loop: {e}")
                import traceback
                traceback.print_exc()
            
            time.sleep(interval_seconds)
    
    thread = threading.Thread(target=_collect, daemon=True)
    thread.start()
    return thread

