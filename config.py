# Basic settings
SYMBOLS = ["BTCUSDT"]  # Start with BTC, easily expandable
BINANCE_WS_URL = "wss://fstream.binance.com/ws"
BINANCE_REST_URL = "https://fapi.binance.com"

# Data collection
SAMPLE_INTERVAL_SECONDS = 10  # Sample every 10s
ORDERBOOK_DEPTH_LIMIT = 1000  # Top 1000 levels

# Storage
DB_PATH = "wormrider.db"
RETENTION_DAYS = 30  # Rolling 30-day window

# UI defaults
DEFAULT_BIN_SIZE = 50  # USD
BIN_SIZE_RANGE = (10, 1000)
AUTO_REFRESH_INTERVAL = 10000  # 10s in milliseconds

