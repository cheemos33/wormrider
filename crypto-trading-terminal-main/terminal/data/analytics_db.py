"""
Analytics Database Manager
Handles all signal and trade data storage for analytics dashboard
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


class AnalyticsDB:
    """Manages SQLite database for signal and trade analytics"""
    
    def __init__(self, db_path: str = None):
        """
        Initialize database connection
        
        Args:
            db_path: Path to SQLite database file (default: terminal/data/analytics.db)
        """
        if db_path is None:
            # Default to terminal/data/analytics.db
            db_path = os.path.join(os.path.dirname(__file__), 'analytics.db')
        
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        # Enable WAL mode for concurrent reads/writes
        conn.execute('PRAGMA journal_mode=WAL')
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create signals_analytics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals_analytics (
                    signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    
                    -- Signal Identity
                    coin TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    
                    -- Signal Indicators
                    stars INTEGER NOT NULL,
                    rsi REAL NOT NULL,
                    val REAL NOT NULL,
                    rvwap_1d REAL NOT NULL,
                    rvwap_7d REAL NOT NULL,
                    price_at_signal REAL NOT NULL,
                    
                    -- Trade Decision
                    traded INTEGER DEFAULT 0,
                    skip_reason TEXT,
                    rejection_reason TEXT,
                    
                    -- Entry Data (if traded)
                    entry_price REAL,
                    entry_time TEXT,
                    
                    -- Exit Data (if closed)
                    exit_price REAL,
                    exit_time TEXT,
                    
                    -- Performance Data (if closed)
                    pnl_usd REAL,
                    pnl_pct REAL,
                    trade_status TEXT
                )
            ''')
            
            # Create indexes for fast queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON signals_analytics(timestamp DESC)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_coin 
                ON signals_analytics(coin)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_traded 
                ON signals_analytics(traded)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_trade_status 
                ON signals_analytics(trade_status)
            ''')
            
            conn.commit()
    
    def insert_signal(
        self,
        coin: str,
        timestamp: str,
        stars: int,
        rsi: float,
        val: float,
        rvwap_1d: float,
        rvwap_7d: float,
        price_at_signal: float,
        skip_reason: Optional[str] = None,
        rejection_reason: Optional[str] = None
    ) -> int:
        """
        Insert a new 4-star signal
        
        Args:
            coin: Coin symbol (e.g., 'BTC')
            timestamp: Signal timestamp (ISO format)
            stars: Star rating (should be 4)
            rsi: RSI value
            val: VAL distance
            rvwap_1d: 1-day RVWAP distance
            rvwap_7d: 7-day RVWAP distance
            price_at_signal: Price when signal detected
            skip_reason: Reason if not traded (optional)
            rejection_reason: Exchange rejection reason (optional)
        
        Returns:
            signal_id of inserted record
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals_analytics (
                    coin, timestamp, stars, rsi, val, rvwap_1d, rvwap_7d,
                    price_at_signal, traded, skip_reason, rejection_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            ''', (coin, timestamp, stars, rsi, val, rvwap_1d, rvwap_7d, 
                  price_at_signal, skip_reason, rejection_reason))
            
            return cursor.lastrowid
    
    def update_signal_entry(
        self,
        coin: str,
        timestamp: str,
        entry_price: float,
        entry_time: str
    ) -> bool:
        """
        Update signal when bot enters trade
        
        Args:
            coin: Coin symbol
            timestamp: Original signal timestamp (to find record)
            entry_price: Entry price
            entry_time: Entry timestamp
        
        Returns:
            True if updated, False if signal not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE signals_analytics
                SET traded = 1,
                    entry_price = ?,
                    entry_time = ?,
                    trade_status = 'open',
                    skip_reason = NULL
                WHERE coin = ? AND timestamp = ?
            ''', (entry_price, entry_time, coin, timestamp))
            
            return cursor.rowcount > 0
    
    def update_signal_rejection(
        self,
        coin: str,
        timestamp: str,
        rejection_reason: str
    ) -> bool:
        """
        Update signal with rejection reason when trade fails
        
        Args:
            coin: Coin symbol
            timestamp: Original signal timestamp (to find record)
            rejection_reason: Why the order was rejected
        
        Returns:
            True if updated, False if signal not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE signals_analytics
                SET rejection_reason = ?
                WHERE coin = ? AND timestamp = ? AND traded = 0
            ''', (rejection_reason, coin, timestamp))
            
            return cursor.rowcount > 0
    
    def update_signal_exit(
        self,
        coin: str,
        entry_time: str,
        exit_price: float,
        exit_time: str,
        pnl_usd: float,
        pnl_pct: float
    ) -> bool:
        """
        Update signal when position closes
        
        Args:
            coin: Coin symbol
            entry_time: Entry timestamp (to find record - used for matching)
            exit_price: Exit price
            exit_time: Exit timestamp
            pnl_usd: P&L in USD
            pnl_pct: P&L in percentage
        
        Returns:
            True if updated, False if record not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Match by coin and open status, update the OLDEST open position first
            # (FIFO - first in, first out)
            cursor.execute('''
                UPDATE signals_analytics
                SET exit_price = ?,
                    exit_time = ?,
                    pnl_usd = ?,
                    pnl_pct = ?,
                    trade_status = 'closed'
                WHERE signal_id = (
                    SELECT signal_id 
                    FROM signals_analytics 
                    WHERE coin = ? AND trade_status = 'open' AND traded = 1
                    ORDER BY entry_time ASC
                    LIMIT 1
                )
            ''', (exit_price, exit_time, pnl_usd, pnl_pct, coin))
            
            rows_updated = cursor.rowcount
            if rows_updated > 0:
                print(f"✅ Analytics updated: {coin} position closed")
            return rows_updated > 0
    
    def get_all_signals(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all signals ordered by timestamp (newest first)
        
        Args:
            limit: Maximum number of records (optional)
            offset: Number of records to skip (optional)
        
        Returns:
            List of signal dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM signals_analytics ORDER BY timestamp DESC'
            params = []
            
            if limit is not None:
                query += ' LIMIT ?'
                params.append(limit)
                
                if offset is not None:
                    query += ' OFFSET ?'
                    params.append(offset)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_filtered_signals(
        self,
        coin: Optional[str] = None,
        traded: Optional[bool] = None,
        trade_status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get signals with filters
        
        Args:
            coin: Filter by coin (optional)
            traded: Filter by traded status (optional)
            trade_status: Filter by trade status ('open', 'closed') (optional)
            limit: Maximum number of records (optional)
        
        Returns:
            List of signal dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM signals_analytics WHERE 1=1'
            params = []
            
            if coin is not None:
                query += ' AND coin = ?'
                params.append(coin)
            
            if traded is not None:
                query += ' AND traded = ?'
                params.append(1 if traded else 0)
            
            if trade_status is not None:
                query += ' AND trade_status = ?'
                params.append(trade_status)
            
            query += ' ORDER BY timestamp DESC'
            
            if limit is not None:
                query += ' LIMIT ?'
                params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics for analytics
        
        Returns:
            Dictionary with summary stats
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Total signals
            cursor.execute('SELECT COUNT(*) FROM signals_analytics')
            total_signals = cursor.fetchone()[0]
            
            # Total traded
            cursor.execute('SELECT COUNT(*) FROM signals_analytics WHERE traded = 1')
            total_traded = cursor.fetchone()[0]
            
            # Total closed
            cursor.execute('SELECT COUNT(*) FROM signals_analytics WHERE trade_status = "closed"')
            total_closed = cursor.fetchone()[0]
            
            # Total open
            cursor.execute('SELECT COUNT(*) FROM signals_analytics WHERE trade_status = "open"')
            total_open = cursor.fetchone()[0]
            
            # Win rate (closed trades with positive P&L)
            cursor.execute('''
                SELECT COUNT(*) FROM signals_analytics 
                WHERE trade_status = "closed" AND pnl_usd > 0
            ''')
            total_wins = cursor.fetchone()[0]
            
            # Total P&L
            cursor.execute('''
                SELECT SUM(pnl_usd) FROM signals_analytics 
                WHERE trade_status = "closed"
            ''')
            total_pnl = cursor.fetchone()[0] or 0.0
            
            # Rejection statistics
            cursor.execute('SELECT COUNT(*) FROM signals_analytics WHERE rejection_reason IS NOT NULL')
            total_rejected = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM signals_analytics WHERE rejection_reason = "Position Cap"')
            rejected_position_cap = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM signals_analytics WHERE rejection_reason = "No Liquidity"')
            rejected_no_liquidity = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM signals_analytics WHERE rejection_reason = "Exchange Error"')
            rejected_exchange_error = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM signals_analytics WHERE rejection_reason = "Insufficient Funds"')
            rejected_insufficient_funds = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM signals_analytics WHERE rejection_reason = "Unknown Error"')
            rejected_unknown = cursor.fetchone()[0]
            
            # Calculate rates
            conversion_rate = (total_traded / total_signals * 100) if total_signals > 0 else 0
            win_rate = (total_wins / total_closed * 100) if total_closed > 0 else 0
            
            # Coin-level performance (trades and rejections per coin)
            cursor.execute('''
                SELECT 
                    coin,
                    SUM(CASE WHEN traded = 1 THEN 1 ELSE 0 END) as trades,
                    SUM(CASE WHEN rejection_reason IS NOT NULL THEN 1 ELSE 0 END) as rejections
                FROM signals_analytics
                GROUP BY coin
                ORDER BY trades DESC, rejections DESC
            ''')
            coin_stats = [{'coin': row[0], 'trades': row[1], 'rejections': row[2]} 
                         for row in cursor.fetchall()]
            
            return {
                'total_signals': total_signals,
                'total_traded': total_traded,
                'total_closed': total_closed,
                'total_open': total_open,
                'total_wins': total_wins,
                'total_pnl': total_pnl,
                'conversion_rate': conversion_rate,
                'win_rate': win_rate,
                'total_rejected': total_rejected,
                'rejected_position_cap': rejected_position_cap,
                'rejected_no_liquidity': rejected_no_liquidity,
                'rejected_exchange_error': rejected_exchange_error,
                'rejected_insufficient_funds': rejected_insufficient_funds,
                'rejected_unknown': rejected_unknown,
                'coin_stats': coin_stats
            }
    
    def close(self):
        """Close database connection (for cleanup)"""
        pass  # Connections are handled in context manager


# Global instance
analytics_db = AnalyticsDB()

