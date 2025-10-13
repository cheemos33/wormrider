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


def cleanup_old_trades(hours: int = 24) -> int:
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


# ==================== AGGREGATED ORDER BOOK FUNCTIONS ====================

def insert_aggregated_snapshot(
    symbol: str,
    timestamp: int,
    bin_size: int,
    agg_bids: List[Tuple[float, float]],
    agg_asks: List[Tuple[float, float]]
) -> None:
    """
    Insert aggregated order book snapshot into database.
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        timestamp: Unix timestamp in milliseconds
        bin_size: Bin size in USD (e.g., 100)
        agg_bids: List of (price_bin, quantity) for bids
        agg_asks: List of (price_bin, quantity) for asks
    """
    conn = get_connection()
    try:
        # Insert all bid bins
        for price_bin, quantity in agg_bids:
            conn.execute(
                """
                INSERT OR REPLACE INTO orderbook_aggregated
                (symbol, timestamp, bin_size, price_bin, quantity, side)
                VALUES (?, ?, ?, ?, ?, 'bid')
                """,
                (symbol, timestamp, bin_size, price_bin, quantity)
            )
        
        # Insert all ask bins
        for price_bin, quantity in agg_asks:
            conn.execute(
                """
                INSERT OR REPLACE INTO orderbook_aggregated
                (symbol, timestamp, bin_size, price_bin, quantity, side)
                VALUES (?, ?, ?, ?, ?, 'ask')
                """,
                (symbol, timestamp, bin_size, price_bin, quantity)
            )
        
        conn.commit()
    except Exception as e:
        print(f"Error inserting aggregated snapshot: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_aggregated_snapshots(
    symbol: str,
    bin_size: int,
    start_ts: int,
    end_ts: int
) -> List[Dict[str, Any]]:
    """
    Get aggregated order book snapshots within a time range.
    
    Args:
        symbol: Trading symbol
        bin_size: Bin size in USD
        start_ts: Start timestamp (ms)
        end_ts: End timestamp (ms)
    
    Returns:
        List of aggregated snapshot dictionaries
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT timestamp, price_bin, quantity, side
            FROM orderbook_aggregated
            WHERE symbol = ? AND bin_size = ? 
            AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp, side, price_bin
            """,
            (symbol, bin_size, start_ts, end_ts)
        )
        rows = cursor.fetchall()
        
        # Group by timestamp
        snapshots = {}
        for row in rows:
            ts = row['timestamp']
            if ts not in snapshots:
                snapshots[ts] = {'timestamp': ts, 'bids': [], 'asks': []}
            
            if row['side'] == 'bid':
                snapshots[ts]['bids'].append((row['price_bin'], row['quantity']))
            else:
                snapshots[ts]['asks'].append((row['price_bin'], row['quantity']))
        
        return list(snapshots.values())
    finally:
        conn.close()


def get_latest_aggregated_snapshot(symbol: str, bin_size: int) -> Optional[Dict[str, Any]]:
    """
    Get the most recent aggregated order book snapshot.
    
    Returns:
        Dictionary with 'timestamp', 'bids', 'asks' keys
    """
    conn = get_connection()
    try:
        # Get latest timestamp
        cursor = conn.execute(
            """
            SELECT MAX(timestamp) as latest_ts
            FROM orderbook_aggregated
            WHERE symbol = ? AND bin_size = ?
            """,
            (symbol, bin_size)
        )
        row = cursor.fetchone()
        if not row or not row['latest_ts']:
            return None
        
        latest_ts = row['latest_ts']
        
        # Get all bins for this timestamp
        cursor = conn.execute(
            """
            SELECT price_bin, quantity, side
            FROM orderbook_aggregated
            WHERE symbol = ? AND bin_size = ? AND timestamp = ?
            ORDER BY side, price_bin
            """,
            (symbol, bin_size, latest_ts)
        )
        
        bids = []
        asks = []
        for row in cursor.fetchall():
            if row['side'] == 'bid':
                bids.append((row['price_bin'], row['quantity']))
            else:
                asks.append((row['price_bin'], row['quantity']))
        
        return {
            'timestamp': latest_ts,
            'bids': bids,
            'asks': asks
        }
    finally:
        conn.close()


def cleanup_old_aggregated(hours: int = 24) -> int:
    """
    Delete aggregated order book data older than N hours.
    
    Args:
        hours: Retention period in hours (default 24h)
    
    Returns:
        Number of deleted rows
    """
    cutoff_timestamp = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM orderbook_aggregated WHERE timestamp < ?",
            (cutoff_timestamp,)
        )
        deleted = cursor.rowcount
        conn.commit()
        if deleted > 0:
            print(f"Cleaned up {deleted} aggregated order book rows")
        return deleted
    except Exception as e:
        print(f"Error during aggregated cleanup: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()



# ==================== SIGNALS FUNCTIONS ====================

def insert_signal(signal_data: Dict[str, Any]) -> None:
    """Insert a new signal into the database."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO signals (
                timestamp, signal_type, direction, entry_price, tp_price, sl_price,
                bid_volume, ask_volume, imbalance_ratio, cvd_slope, strength, status,
                initial_bid_liquidity, initial_ask_liquidity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_data['timestamp'], signal_data['signal_type'], signal_data['direction'],
                signal_data['entry_price'], signal_data['tp_price'], signal_data['sl_price'],
                signal_data.get('bid_volume'), signal_data.get('ask_volume'),
                signal_data.get('imbalance_ratio'), signal_data.get('cvd_slope'),
                signal_data.get('strength'), signal_data.get('status', 'pending'),
                signal_data.get('initial_bid_liquidity'), signal_data.get('initial_ask_liquidity')
            )
        )
        conn.commit()
    except Exception as e:
        print(f"Error inserting signal: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_active_signal() -> Optional[Dict[str, Any]]:
    """Get the currently active signal (status='active')."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT * FROM signals
            WHERE status = 'active'
            ORDER BY timestamp DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_pending_signal() -> Optional[Dict[str, Any]]:
    """Get the currently pending signal (status='pending')."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT * FROM signals
            WHERE status = 'pending'
            ORDER BY timestamp DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def update_signal_entry(signal_id: int, entry_price: float, entry_time: int) -> None:
    """Update a signal's status to 'active' with entry details."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE signals
            SET status = 'active', entry_price = ?, entry_time = ?
            WHERE id = ?
            """,
            (entry_price, entry_time, signal_id)
        )
        conn.commit()
    except Exception as e:
        print(f"Error updating signal entry: {e}")
        conn.rollback()
    finally:
        conn.close()

def update_signal_exit(signal_id: int, exit_price: float, exit_time: int, pnl: float, status: str, exit_reason: str = None) -> None:
    """Update a signal's status to 'closed' with exit details."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE signals
            SET status = ?, exit_price = ?, exit_time = ?, pnl = ?, exit_reason = ?
            WHERE id = ?
            """,
            (status, exit_price, exit_time, pnl, exit_reason, signal_id)
        )
        conn.commit()
    except Exception as e:
        print(f"Error updating signal exit: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_recent_signals(limit: int = 5) -> List[Dict[str, Any]]:
    """Get a list of recent signals, excluding 'pending' and 'active'."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT * FROM signals
            WHERE status != 'pending' AND status != 'active'
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_session_stats() -> Dict[str, Any]:
    """Calculate session statistics for closed signals."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT
                COUNT(id) as total_signals,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as total_win_pnl,
                SUM(CASE WHEN pnl <= 0 THEN pnl ELSE 0 END) as total_loss_pnl,
                SUM(pnl) as net_pnl
            FROM signals
            WHERE status != 'pending' AND status != 'active'
            """
        )
        stats = cursor.fetchone()
        if stats:
            total_signals = stats['total_signals']
            wins = stats['wins']
            losses = stats['losses']
            total_win_pnl = stats['total_win_pnl'] or 0
            total_loss_pnl = stats['total_loss_pnl'] or 0
            net_pnl = stats['net_pnl'] or 0

            win_rate = (wins / total_signals * 100) if total_signals > 0 else 0
            avg_win = (total_win_pnl / wins) if wins > 0 else 0
            avg_loss = (total_loss_pnl / losses) if losses > 0 else 0

            return {
                'total_signals': total_signals,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'net_pnl': net_pnl
            }
        return {
            'total_signals': 0, 'wins': 0, 'losses': 0,
            'win_rate': 0, 'avg_win': 0, 'avg_loss': 0, 'net_pnl': 0
        }
    finally:
        conn.close()


# ==================== SIGNALS FUNCTIONS ====================

def insert_signal(signal_data: Dict[str, Any]) -> None:
    """Insert a new signal into the database."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO signals (
                timestamp, signal_type, direction, entry_price, tp_price, sl_price,
                bid_volume, ask_volume, imbalance_ratio, cvd_slope, strength, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_data['timestamp'], signal_data['signal_type'], signal_data['direction'],
                signal_data['entry_price'], signal_data['tp_price'], signal_data['sl_price'],
                signal_data.get('bid_volume'), signal_data.get('ask_volume'),
                signal_data.get('imbalance_ratio'), signal_data.get('cvd_slope'),
                signal_data.get('strength'), signal_data.get('status', 'pending')
            )
        )
        conn.commit()
    except Exception as e:
        print(f"Error inserting signal: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_active_signal() -> Optional[Dict[str, Any]]:
    """Get the currently active signal (status='active')."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT * FROM signals
            WHERE status = 'active'
            ORDER BY timestamp DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_pending_signal() -> Optional[Dict[str, Any]]:
    """Get the currently pending signal (status='pending')."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT * FROM signals
            WHERE status = 'pending'
            ORDER BY timestamp DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def update_signal_entry(signal_id: int, entry_price: float, entry_time: int) -> None:
    """Update a signal's status to 'active' with entry details."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE signals
            SET status = 'active', entry_price = ?, entry_time = ?
            WHERE id = ?
            """,
            (entry_price, entry_time, signal_id)
        )
        conn.commit()
    except Exception as e:
        print(f"Error updating signal entry: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_recent_signals(limit: int = 5) -> List[Dict[str, Any]]:
    """Get a list of recent signals, excluding 'pending' and 'active'."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT * FROM signals
            WHERE status != 'pending' AND status != 'active'
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_session_stats() -> Dict[str, Any]:
    """Calculate session statistics for closed signals."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT
                COUNT(id) as total_signals,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as total_win_pnl,
                SUM(CASE WHEN pnl <= 0 THEN pnl ELSE 0 END) as total_loss_pnl,
                SUM(pnl) as net_pnl
            FROM signals
            WHERE status != 'pending' AND status != 'active'
            """
        )
        stats = cursor.fetchone()
        if stats:
            total_signals = stats['total_signals'] or 0
            wins = stats['wins'] or 0
            losses = stats['losses'] or 0
            total_win_pnl = stats['total_win_pnl'] or 0
            total_loss_pnl = stats['total_loss_pnl'] or 0
            net_pnl = stats['net_pnl'] or 0

            win_rate = (wins / total_signals * 100) if total_signals > 0 else 0
            avg_win = (total_win_pnl / wins) if wins > 0 else 0
            avg_loss = (total_loss_pnl / losses) if losses > 0 else 0

            return {
                'total_signals': total_signals,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'net_pnl': net_pnl
            }
        return {
            'total_signals': 0, 'wins': 0, 'losses': 0,
            'win_rate': 0, 'avg_win': 0, 'avg_loss': 0, 'net_pnl': 0
        }
    finally:
        conn.close()
