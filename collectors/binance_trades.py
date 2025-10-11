"""Binance trades WebSocket collector for CVD calculation."""

import websocket
import json
import threading
import time
from typing import Callable, List, Dict, Any
import config


class BinanceTradesCollector:
    """Real-time trades collector from Binance WebSocket."""
    
    def __init__(self, symbol: str = "btcusdt"):
        self.symbol = symbol
        self.ws_url = f"wss://fstream.binance.com/ws/{symbol}@aggTrade"
        self.trades_buffer: List[Dict[str, Any]] = []
        self.callback: Callable = None
        self.running = False
        self.ws = None
        self.reconnect_count = 0
        self.max_reconnect = 10
        
    def start(self, callback: Callable):
        """Start WebSocket connection and trades collection."""
        self.callback = callback
        self.running = True
        print(f"Starting trades collection for {self.symbol.upper()}")
        self._connect()
        
    def stop(self):
        """Stop WebSocket connection."""
        self.running = False
        if self.ws:
            self.ws.close()
        print("Trades collection stopped")
        
    def _connect(self):
        """Establish WebSocket connection."""
        try:
            import ssl
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Run in separate thread with SSL context
            sslopt = {"cert_reqs": ssl.CERT_NONE}
            ws_thread = threading.Thread(target=lambda: self.ws.run_forever(sslopt=sslopt), daemon=True)
            ws_thread.start()
            
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            self._reconnect()
    
    def _on_open(self, ws):
        """WebSocket opened successfully."""
        print(f"Trades WebSocket connected for {self.symbol.upper()}")
        self.reconnect_count = 0
        
    def _on_message(self, ws, message):
        """Handle incoming trade message."""
        try:
            data = json.loads(message)
            
            # Parse trade data
            trade = {
                'symbol': data.get('s', '').lower(),
                'timestamp': int(data.get('T', 0)),  # Trade time
                'price': float(data.get('p', 0)),    # Price
                'quantity': float(data.get('q', 0)), # Quantity
                'is_buy': not data.get('m', True)    # m=True means seller is maker (sell), m=False means buyer is maker (buy)
            }
            
            # Add to rolling buffer
            self._add_to_buffer(trade)
            
            # Call callback if provided
            if self.callback:
                self.callback(trade)
                
        except Exception as e:
            print(f"Error parsing trade message: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket error."""
        print(f"Trades WebSocket error: {error}")
        
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        print(f"Trades WebSocket closed: {close_status_code} - {close_msg}")
        if self.running:
            self._reconnect()
    
    def _reconnect(self):
        """Reconnect with exponential backoff."""
        if self.reconnect_count >= self.max_reconnect:
            print("Max reconnection attempts reached")
            return
            
        self.reconnect_count += 1
        delay = min(2 ** self.reconnect_count, 60)  # Max 60 seconds
        print(f"Reconnecting in {delay} seconds... (attempt {self.reconnect_count})")
        
        time.sleep(delay)
        if self.running:
            self._connect()
    
    def _add_to_buffer(self, trade: Dict[str, Any]):
        """Add trade to rolling buffer and cleanup old trades."""
        self.trades_buffer.append(trade)
        
        # Keep only last 1 hour of trades
        cutoff_time = int(time.time() * 1000) - (60 * 60 * 1000)  # 1 hour ago
        
        # Remove old trades
        self.trades_buffer = [
            t for t in self.trades_buffer 
            if t['timestamp'] > cutoff_time
        ]
    
    def get_trades_range(self, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
        """Get trades within timestamp range."""
        return [
            t for t in self.trades_buffer
            if start_ts <= t['timestamp'] <= end_ts
        ]
    
    def get_recent_trades(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """Get trades from last N minutes."""
        cutoff_time = int(time.time() * 1000) - (minutes * 60 * 1000)
        return [
            t for t in self.trades_buffer
            if t['timestamp'] > cutoff_time
        ]
    
    def get_buffer_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        if not self.trades_buffer:
            return {'count': 0, 'oldest': None, 'newest': None}
            
        timestamps = [t['timestamp'] for t in self.trades_buffer]
        return {
            'count': len(self.trades_buffer),
            'oldest': min(timestamps),
            'newest': max(timestamps),
            'time_span_minutes': (max(timestamps) - min(timestamps)) / (1000 * 60)
        }


# Global instance
trades_collector = BinanceTradesCollector("btcusdt")


def start_trades_collection(callback: Callable):
    """Start global trades collection."""
    trades_collector.start(callback)


def stop_trades_collection():
    """Stop global trades collection."""
    trades_collector.stop()


def get_trades_data() -> BinanceTradesCollector:
    """Get global trades collector instance."""
    return trades_collector
