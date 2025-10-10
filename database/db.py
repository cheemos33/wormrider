"""Database operations for Wormrider."""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
import config
from database.models import SCHEMA


def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.Connection(config.DB_PATH)
    conn.row_factory = sqlite3.Row
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


def cleanup_old_data(retention_days: int) -> int:
    """Delete snapshots older than retention_days. Returns number of deleted rows."""
    cutoff_timestamp = int((datetime.now() - timedelta(days=retention_days)).timestamp() * 1000)
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM orderbook_snapshots WHERE timestamp < ?",
            (cutoff_timestamp,)
        )
        deleted = cursor.rowcount
        conn.commit()
        if deleted > 0:
            print(f"Cleaned up {deleted} old snapshots")
        return deleted
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

