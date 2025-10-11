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

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    is_buy INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON orderbook_snapshots(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_timestamp ON orderbook_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_timestamp ON trades(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
"""

