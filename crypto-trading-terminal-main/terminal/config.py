"""
Configuration settings for Trading Terminal
"""
import os
from dotenv import load_dotenv

# Load environment variables from parent directory's .env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class Config:
    """Configuration class for terminal settings"""
    
    # Hyperliquid API Settings
    HYPERLIQUID_API_URL = "https://api.hyperliquid.xyz"
    HYPERLIQUID_API_KEY = os.getenv("HYPERLIQUID_API_KEY")
    HYPERLIQUID_SECRET_KEY = os.getenv("HYPERLIQUID_SECRET_KEY")
    HYPERLIQUID_WALLET = os.getenv("HYPERLIQUID_MAIN_WALLET_PUBKEY")
    
    # Terminal Settings
    MAX_WATCHLIST_COINS = 20
    UPDATE_INTERVAL_SECONDS = 60  # Update every 1 minute
    CHART_TIMEFRAME_HOURS = 24    # Show 24 hours of data
    CANDLE_INTERVAL = "5m"         # Use 5-minute candles (more sensitive RSI)
    
    # Dashboard Settings
    DASHBOARD_HOST = "0.0.0.0"
    DASHBOARD_PORT = 8050
    DASHBOARD_DEBUG = False  # Disabled to prevent path issues
    
    # File Paths
    WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "my_watchlist.json")
    
    # Default Watchlist (20 coins)
    DEFAULT_WATCHLIST = [
        "BTC", "ETH", "SOL", "AVAX", "MATIC",
        "ARB", "OP", "ATOM", "DOT", "LINK",
        "UNI", "AAVE", "LDO", "RNDR", "FET",
        "PEPE", "WIF", "IMX", "INJ", "DYDX"
    ]
    
    # Coin Colors (Official brand colors for spaghetti chart)
    COIN_COLORS = {
        # Your current watchlist (14 coins)
        "BTC": "#f7931a",    # Bitcoin Orange (official)
        "ETH": "#627eea",    # Ethereum Blue (official)
        "SOL": "#14f195",    # Solana Green (official)
        "AVAX": "#e84142",   # Avalanche Red (official)
        "HYPE": "#00d4ff",   # Hyperliquid Cyan (brand color)
        "KPEPE": "#00ff00",  # Pepe derivative - Bright green
        "WIF": "#e59a4f",    # Dogwifhat Beige/Orange
        "GRASS": "#7ed957",  # Grass Green (obvious choice)
        "KAITO": "#00ffff",  # Kaito Cyan/Aqua
        "FARTCOIN": "#8b4513", # Brown (humorous choice)
        "JUP": "#ffc845",    # Jupiter Yellow/Gold (official)
        "VIRTUAL": "#a855f7", # Virtual Protocol Purple
        "MOODENG": "#ff69b4", # Moo Deng Pink (hippo meme)
        "PENGU": "#00bfff",  # Pengu Blue (penguin theme)
        
        # Other popular coins (for when you add them)
        "POL": "#8247e5",    # Polygon Purple (official)
        "ARB": "#28a0f0",    # Arbitrum Blue (official)
        "OP": "#ff0420",     # Optimism Red (official)
        "ATOM": "#6f7390",   # Cosmos Gray-Blue (official)
        "DOT": "#e6007a",    # Polkadot Pink (official)
        "LINK": "#375bd2",   # Chainlink Blue (official)
        "UNI": "#ff007a",    # Uniswap Pink (official)
        "AAVE": "#b6509e",   # Aave Purple (official)
        "LDO": "#00a3ff",    # Lido Cyan (official)
        "RNDR": "#e8592e",   # Render Orange (official)
        "FET": "#0714fe",    # Fetch Blue (official)
        "PEPE": "#17c654",   # Pepe Green (official)
        "IMX": "#0ac2ff",    # Immutable Cyan (official)
        "INJ": "#00f2fe",    # Injective Cyan (official)
        "DYDX": "#6966ff",   # dYdX Purple (official)
        "DOGE": "#c2a633",   # Dogecoin Gold (official)
        "SHIB": "#f70808",   # Shiba Red (official)
        "ADA": "#0033ad",    # Cardano Blue (official)
        "XRP": "#939393",    # XRP Gray (for visibility on black)
        "TRX": "#ff060a",    # Tron Red (official)
        "LTC": "#345d9d",    # Litecoin Blue (official)
        "BCH": "#8dc351",    # Bitcoin Cash Green (official)
    }
    
    # Fallback colors for any coin not in the map above
    FALLBACK_COLORS = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8",
        "#F7DC6F", "#BB8FCE", "#85C1E2", "#F8B739", "#52B788"
    ]


# Create a global config instance
config = Config()

