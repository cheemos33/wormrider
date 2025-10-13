"""Binance WebSocket order book collector - Hybrid approach."""

import time
import threading
import json
import asyncio
from typing import Callable, List, Tuple, Dict
import httpx
import websockets
import ssl
import config
from indicators.orderbook_aggregation import aggregate_bids_asks
from database import db


class OrderBookManager:
    """Manages order book state with WebSocket updates."""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: Dict[float, float] = {}  # price -> quantity
        self.asks: Dict[float, float] = {}
        self.last_update_id = 0
        self.lock = threading.Lock()
        self.initialized = False
    
    def initialize_snapshot(self, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]):
        """Initialize order book with REST snapshot."""
        with self.lock:
            self.bids = {float(price): float(qty) for price, qty in bids}
            self.asks = {float(price): float(qty) for price, qty in asks}
            self.initialized = True
            print(f"[{self.symbol}] Order book initialized: {len(self.bids)} bids, {len(self.asks)} asks")
    
    def apply_diff(self, bids_update: List[List[str]], asks_update: List[List[str]]):
        """Apply incremental diff from WebSocket."""
        with self.lock:
            # Update bids
            for price_str, qty_str in bids_update:
                price = float(price_str)
                qty = float(qty_str)
                if qty == 0.0:
                    self.bids.pop(price, None)  # Remove
                else:
                    self.bids[price] = qty  # Update/Add
            
            # Update asks
            for price_str, qty_str in asks_update:
                price = float(price_str)
                qty = float(qty_str)
                if qty == 0.0:
                    self.asks.pop(price, None)
                else:
                    self.asks[price] = qty
    
    def get_snapshot(self, limit: int = 1000) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]], float]:
        """
        Get current order book snapshot.
        
        Returns:
            (bids, asks, mid_price) sorted by price
        """
        with self.lock:
            if not self.initialized:
                return [], [], 0.0
            
            # Sort and limit
            bids_sorted = sorted(self.bids.items(), key=lambda x: x[0], reverse=True)[:limit]
            asks_sorted = sorted(self.asks.items(), key=lambda x: x[0])[:limit]
            
            # Calculate mid price
            best_bid = bids_sorted[0][0] if bids_sorted else 0.0
            best_ask = asks_sorted[0][0] if asks_sorted else 0.0
            mid_price = (best_bid + best_ask) / 2.0 if best_bid and best_ask else 0.0
            
            return bids_sorted, asks_sorted, mid_price


async def websocket_listener(ob_manager: OrderBookManager, symbol: str):
    # Create SSL context that bypasses certificate verification
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    """Listen to WebSocket depth updates."""
    ws_url = f"{config.BINANCE_WS_URL}/{symbol.lower()}@depth@100ms"
    
    print(f"[{symbol}] Connecting to WebSocket: {ws_url}")
    
    reconnect_delay = 1
    max_reconnect_delay = 60
    
    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10, ssl=ssl_context) as ws:
                print(f"[{symbol}] WebSocket connected")
                reconnect_delay = 1  # Reset on successful connection
                
                async for message in ws:
                    try:
                        data = json.loads(message)
                        
                        # Skip if not initialized yet
                        if not ob_manager.initialized:
                            continue
                        
                        # Apply diff
                        bids_update = data.get('b', [])
                        asks_update = data.get('a', [])
                        ob_manager.apply_diff(bids_update, asks_update)
                        
                    except json.JSONDecodeError as e:
                        print(f"[{symbol}] JSON decode error: {e}")
                    except Exception as e:
                        print(f"[{symbol}] Error processing message: {e}")
        
        except websockets.exceptions.WebSocketException as e:
            print(f"[{symbol}] WebSocket error: {e}")
        except Exception as e:
            print(f"[{symbol}] Unexpected error: {e}")
        
        # Reconnect with exponential backoff
        print(f"[{symbol}] Reconnecting in {reconnect_delay}s...")
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)


def fetch_initial_snapshot(symbol: str) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    """Fetch initial snapshot via REST API."""
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
        
        return bids, asks
    
    except Exception as e:
        print(f"Error fetching initial snapshot for {symbol}: {e}")
        return [], []


def start_websocket_collection(
    symbol: str,
    interval_seconds: int,
    callback: Callable[[str, int, List[Tuple[float, float]], List[Tuple[float, float]], float], None]
) -> threading.Thread:
    """
    Start WebSocket-based order book collection.
    
    HYBRID APPROACH:
    1. Fetch initial snapshot via REST (once)
    2. Listen to WebSocket for real-time updates
    3. Save aggregated snapshot every N seconds
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        interval_seconds: How often to save snapshot to database
        callback: Function to call with (symbol, timestamp_ms, bids, asks, mid_price)
    
    Returns:
        The background thread (already started)
    """
    ob_manager = OrderBookManager(symbol)
    
    def _run_async_loop():
        """Run asyncio event loop in background thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start WebSocket listener
        loop.create_task(websocket_listener(ob_manager, symbol))
        loop.run_forever()
    
    def _save_snapshots():
        """Periodically save order book snapshots."""
        print(f"Starting order book collection for {symbol} (WebSocket + {interval_seconds}s saves)")
        print(f"Real-time updates via WebSocket, aggregating to ${config.DEFAULT_AGG_BIN_SIZE} bins")
        
        # 1. Fetch initial snapshot via REST
        print(f"[{symbol}] Fetching initial REST snapshot...")
        bids, asks = fetch_initial_snapshot(symbol)
        if bids and asks:
            ob_manager.initialize_snapshot(bids, asks)
        else:
            print(f"[{symbol}] Failed to fetch initial snapshot, retrying...")
            time.sleep(5)
            return _save_snapshots()  # Retry
        
        # 2. Periodically save snapshots
        while True:
            try:
                time.sleep(interval_seconds)
                
                # Get current state
                timestamp_ms = int(time.time() * 1000)
                bids, asks, mid_price = ob_manager.get_snapshot(limit=config.ORDERBOOK_DEPTH_LIMIT)
                
                if bids and asks:
                    # Call callback for backward compatibility
                    callback(symbol, timestamp_ms, bids, asks, mid_price)
                    
                    # Aggregate and store
                    agg_bids, agg_asks = aggregate_bids_asks(
                        bids, 
                        asks, 
                        config.DEFAULT_AGG_BIN_SIZE
                    )
                    
                    db.insert_aggregated_snapshot(
                        symbol=symbol,
                        timestamp=timestamp_ms,
                        bin_size=config.DEFAULT_AGG_BIN_SIZE,
                        agg_bids=agg_bids,
                        agg_asks=agg_asks
                    )
                    
                    # Log stats
                    if timestamp_ms % 50000 < interval_seconds * 1000:
                        print(f"[{symbol}] Saved: {len(bids)}+{len(asks)} raw → {len(agg_bids)}+{len(agg_asks)} bins (WebSocket)")
                
            except Exception as e:
                print(f"Error in save loop: {e}")
                import traceback
                traceback.print_exc()
    
    # Start WebSocket listener thread
    ws_thread = threading.Thread(target=_run_async_loop, daemon=True)
    ws_thread.start()
    
    # Start snapshot saver thread
    save_thread = threading.Thread(target=_save_snapshots, daemon=True)
    save_thread.start()
    
    return save_thread


# Backward compatibility: alias for easy migration
start_collection = start_websocket_collection
