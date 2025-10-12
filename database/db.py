"""Database operations for Wormrider."""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
import config
from database.models import SCHEMA


def get_connection() -> sqlite3.Connection:
    """Get database connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(config.DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Initialize database with schema."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Database initialized at {config.DB_PATH}")


def insert_snapshot(
    symbol: str,
    timestamp: int,
    bids: List[Tuple[float, float]],
    asks: List[Tuple[float, float]],
    mid_price: float
) -> None:
    """Insert order book snapshot into database."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO orderbook_snapshots 
            (symbol, timestamp, bids, asks, mid_price)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                symbol,
                timestamp,
                json.dumps(bids),
                json.dumps(asks),
                mid_price
            )
        )
        conn.commit()
    except Exception as e:
        print(f"Error inserting snapshot: {e}")
    finally:
        conn.close()


def get_latest_snapshot(symbol: str) -> Optional[Dict[str, Any]]:
    """Get the most recent order book snapshot for a symbol."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT symbol, timestamp, bids, asks, mid_price
            FROM orderbook_snapshots
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (symbol,)
        )
        row = cursor.fetchone()
        if row:
            return {
                'symbol': row['symbol'],
                'timestamp': row['timestamp'],
                'bids': json.loads(row['bids']),
                'asks': json.loads(row['asks']),
                'mid_price': row['mid_price']
            }
        return None
    finally:
        conn.close()


def insert_trade(symbol: str, timestamp: int, price: float, quantity: float, is_buy: bool) -> None:
    """Insert a trade record into the database."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO trades (symbol, timestamp, price, quantity, is_buy)
            VALUES (?, ?, ?, ?, ?)
            """,
            (symbol, timestamp, price, quantity, 1 if is_buy else 0)
        )
        conn.commit()
    except Exception as e:
        print(f"Error inserting trade: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_trades_range(symbol: str, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    """Get trades within timestamp range."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT symbol, timestamp, price, quantity, is_buy
            FROM trades
            WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp
            """,
            (symbol, start_ts, end_ts)
        )
        rows = cursor.fetchall()
        return [{
            'symbol': row['symbol'],
            'timestamp': row['timestamp'],
            'price': row['price'],
            'quantity': row['quantity'],
            'is_buy': bool(row['is_buy'])
        } for row in rows]
    finally:
        conn.close()


def cleanup_old_data(retention_days: int) -> int:
    """Delete snapshots older than retention_days. Returns number of deleted rows."""
    cutoff_timestamp = int((datetime.now() - timedelta(days=retention_days)).timestamp() * 1000)
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM orderbook_snapshots WHERE timestamp < ?",
            (cutoff_timestamp,)
        )
        deleted_snapshots = cursor.rowcount
        
        cursor = conn.execute(
            "DELETE FROM trades WHERE timestamp < ?",
            (cutoff_timestamp,)
        )
        deleted_trades = cursor.rowcount
        
        conn.commit()
        total_deleted = deleted_snapshots + deleted_trades
        if total_deleted > 0:
            print(f"Cleaned up {deleted_snapshots} snapshots and {deleted_trades} trades")
        return total_deleted
    finally:
        conn.close()


def cleanup_old_trades(hours: int = 1) -> int:
    """Delete trades older than N hours. Returns number of deleted rows."""
    cutoff_timestamp = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM trades WHERE timestamp < ?",
            (cutoff_timestamp,)
        )
        deleted = cursor.rowcount
        conn.commit()
        if deleted > 0:
            print(f"Cleaned up {deleted} old trades")
        return deleted
    except Exception as e:
        print(f"Error during trades cleanup: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


def get_snapshots_range(
    symbol: str,
    start_ts: int,
    end_ts: int
) -> List[Dict[str, Any]]:
    """Get snapshots within a time range (for future analytics)."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT symbol, timestamp, bids, asks, mid_price
            FROM orderbook_snapshots
            WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
            """,
            (symbol, start_ts, end_ts)
        )
        rows = cursor.fetchall()
        return [
            {
                'symbol': row['symbol'],
                'timestamp': row['timestamp'],
                'bids': json.loads(row['bids']),
                'asks': json.loads(row['asks']),
                'mid_price': row['mid_price']
            }
            for row in rows
        ]
    finally:
        conn.close()

