# Signal-related database functions
from typing import Dict, Any, List, Optional
import sqlite3
from datetime import datetime, timedelta

def get_connection():
    """Get database connection (import from main db.py)"""
    from database.db import get_connection as _get_connection
    return _get_connection()


def get_active_signal(signal_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get the currently active signal.
    
    Args:
        signal_type: Filter by signal type ('HISTORICAL', 'INSTANT', 'HYBRID'). None = any type.
    """
    conn = get_connection()
    try:
        if signal_type:
            cursor = conn.execute(
                """
                SELECT * FROM signals
                WHERE status = 'active' AND signal_type = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (signal_type,)
            )
        else:
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


def get_pending_signal(signal_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get the currently pending signal.
    
    Args:
        signal_type: Filter by signal type ('HISTORICAL', 'INSTANT', 'HYBRID'). None = any type.
    """
    conn = get_connection()
    try:
        if signal_type:
            cursor = conn.execute(
                """
                SELECT * FROM signals
                WHERE status = 'pending' AND signal_type = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (signal_type,)
            )
        else:
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


def get_recent_signals(limit: int = 20, signal_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get recent signals (excluding pending and active).
    
    Args:
        limit: Maximum number of signals to return
        signal_type: Filter by signal type. None = all types.
    """
    conn = get_connection()
    try:
        if signal_type:
            cursor = conn.execute(
                """
                SELECT * FROM signals
                WHERE status != 'pending' AND status != 'active' AND signal_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (signal_type, limit)
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM signals
                WHERE status != 'pending' AND status != 'active'
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,)
            )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_session_stats(signal_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get session statistics.
    
    Args:
        signal_type: Filter by signal type. None = all types.
    """
    conn = get_connection()
    try:
        if signal_type:
            cursor = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN status = 'tp_hit' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN status = 'sl_hit' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN pnl IS NOT NULL THEN pnl ELSE 0 END) as total_pnl
                FROM signals
                WHERE status IN ('tp_hit', 'sl_hit') AND signal_type = ?
                """,
                (signal_type,)
            )
        else:
            cursor = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN status = 'tp_hit' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN status = 'sl_hit' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN pnl IS NOT NULL THEN pnl ELSE 0 END) as total_pnl
                FROM signals
                WHERE status IN ('tp_hit', 'sl_hit')
                """
            )
        row = cursor.fetchone()
        
        total_trades = row['total_trades'] or 0
        wins = row['wins'] or 0
        losses = row['losses'] or 0
        total_pnl = row['total_pnl'] or 0
        
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl': total_pnl
        }
    finally:
        conn.close()


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
    """Update a signal's status to closed with exit details."""
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

def get_recent_signals_by_type(signal_type, limit=10):
    """Get recent signals by type."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM signals 
        WHERE signal_type = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    """, (signal_type, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Convert to list of dicts
    signals = []
    for row in rows:
        signal = {
            'id': row[0],
            'signal_type': row[1],
            'direction': row[2],
            'entry_price': row[3],
            'tp_price': row[4],
            'sl_price': row[5],
            'bid_volume': row[6],
            'ask_volume': row[7],
            'imbalance_ratio': row[8],
            'cvd_slope': row[9],
            'strength': row[10],
            'status': row[11],
            'timestamp': row[12],
            'pnl': row[13],
            'initial_bid_liquidity': row[14],
            'initial_ask_liquidity': row[15]
        }
        signals.append(signal)
    
    return signals