# Basic settings
SYMBOLS = ["BTCUSDT"]  # Start with BTC, easily expandable
BINANCE_WS_URL = "wss://fstream.binance.com/ws"
BINANCE_REST_URL = "https://fapi.binance.com"

# Data collection
SAMPLE_INTERVAL_SECONDS = 5  # Sample every 5s (avoid Binance rate limit)
ORDERBOOK_DEPTH_LIMIT = 1000  # Top 1000 levels (Binance Futures API max - verified)

# Aggregation bin sizes (USD) for different timeframes
BIN_SIZES = {
    '5m': 10,      # $10 bins for 5-minute analysis
    '15m': 50,     # $50 bins for 15-minute analysis
    '1h': 100,     # $100 bins for 1-hour analysis (primary)
    '4h': 500      # $500 bins for 4-hour analysis
}
DEFAULT_AGG_BIN_SIZE = 100  # Primary aggregation bin size

# Storage
DB_PATH = "wormrider.db"
RETENTION_DAYS = 30  # Rolling 30-day window

# UI defaults
DEFAULT_BIN_SIZE = 50  # USD
BIN_SIZE_RANGE = (10, 1000)
AUTO_REFRESH_INTERVAL = 1000  # 1s in milliseconds (changed from 10s for real-time)

