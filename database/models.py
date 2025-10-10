"""Database schema definitions for Wormrider."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS orderbook_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    bids TEXT NOT NULL,
    asks TEXT NOT NULL,
    mid_price REAL NOT NULL,
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON orderbook_snapshots(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_timestamp ON orderbook_snapshots(timestamp);
"""

