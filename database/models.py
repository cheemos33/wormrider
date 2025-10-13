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

CREATE TABLE IF NOT EXISTS orderbook_aggregated (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    bin_size INTEGER NOT NULL,
    price_bin REAL NOT NULL,
    quantity REAL NOT NULL,
    side TEXT NOT NULL,
    UNIQUE(symbol, timestamp, bin_size, price_bin, side)
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    signal_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    tp_price REAL NOT NULL,
    sl_price REAL NOT NULL,
    bid_volume REAL,
    ask_volume REAL,
    imbalance_ratio REAL,
    cvd_slope TEXT,
    strength REAL,
    status TEXT DEFAULT 'pending',
    entry_time INTEGER,
    exit_time INTEGER,
    exit_price REAL,
    pnl REAL,
    UNIQUE(timestamp)
);

CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON orderbook_snapshots(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_timestamp ON orderbook_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_timestamp ON trades(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_orderbook_agg_symbol_timestamp ON orderbook_aggregated(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_orderbook_agg_bin_size ON orderbook_aggregated(bin_size);
CREATE INDEX IF NOT EXISTS idx_orderbook_agg_timestamp ON orderbook_aggregated(timestamp);
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp);
"""
