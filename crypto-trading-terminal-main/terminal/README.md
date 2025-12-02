# 🚀 Crypto Trading Terminal - Screen 1

Personal trading terminal for monitoring cryptocurrency prices on Hyperliquid.

## Features

- **20-Coin Watchlist**: Customize your coin list with search and add/remove functionality
- **24-Hour Spaghetti Chart**: Visual overview of all coin price movements (% change)
- **Real-Time Updates**: Prices and chart update every 1 minute
- **Dark Professional Theme**: Easy on the eyes for long trading sessions
- **Interactive**: Hover, zoom, and click on charts for detailed information

## Quick Start

### 1. Install Dependencies

```bash
cd terminal
pip install -r requirements.txt
```

### 2. Configure API Keys

Make sure your `.env` file in the parent directory contains:

```
HYPERLIQUID_API_KEY=your_api_key
HYPERLIQUID_MAIN_WALLET_PUBKEY=your_wallet_address
```

### 3. Run the Terminal

```bash
python app.py
```

### 4. Open in Browser

Navigate to: `http://localhost:8050`

## Usage

### Adding Coins

1. Use the search dropdown to find a coin
2. Click the "+ Add" button
3. Maximum 20 coins in watchlist

### Removing Coins

Click the "✕" button next to any coin in the watchlist table

### Chart Interaction

- **Hover**: See coin name, time, and % change
- **Zoom**: Scroll to zoom in/out
- **Pan**: Click and drag to move around
- **Legend**: Click coin names to highlight/hide lines

## File Structure

```
terminal/
├── app.py                    # Main application
├── config.py                 # Configuration settings
├── my_watchlist.json         # Your saved coin list
├── data/
│   ├── hyperliquid_api.py    # API client
│   ├── watchlist_manager.py  # Watchlist management
│   └── data_processor.py     # Data processing
├── components/
│   ├── watchlist.py          # Watchlist UI
│   └── spaghetti.py          # Chart component
└── assets/
    └── style.css             # Custom styling
```

## Configuration

Edit `config.py` to customize:

- `MAX_WATCHLIST_COINS`: Maximum number of coins (default: 20)
- `UPDATE_INTERVAL_SECONDS`: Update frequency (default: 60)
- `CHART_TIMEFRAME_HOURS`: Chart time window (default: 24)
- `DASHBOARD_PORT`: Port number (default: 8050)

## Troubleshooting

### Port Already in Use

Change the port in `config.py`:

```python
DASHBOARD_PORT = 8051  # or any available port
```

### SSL Certificate Errors

The app disables SSL verification for Hyperliquid API (this is intentional and matches your existing setup).

### No Data Showing

- Check your API keys in `.env`
- Verify internet connection
- Check terminal output for error messages

## What's Next

This is Screen 1 - the foundation. Future screens will add:

- **Screen 2**: Detailed coin analysis (RSI, Volume Profile)
- **Screen 3**: BTC analysis workspace
- **Screen 4**: Trading scanners
- **Screen 5**: Position management and auto-trading

## Support

For issues or questions, check the PLAN.md file for complete documentation.

---

**Built with:** Python · Dash · Plotly · Pandas · Hyperliquid API


