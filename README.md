# Wormrider - Trading Analytics Tool

Data-focused crypto trading analytics tool with live Binance order book collection and visualization.

## Features

- **Real-time Order Book Collection**: Continuous sampling from Binance Futures (10s intervals)
- **SQLite Storage**: 30-day rolling retention with efficient indexing
- **Interactive Dashboard**: Dash/Plotly UI with live updates
- **Order Book Profile**: Binned visualization with adjustable bin size (10-1000 USD)
- **Auto-refresh**: 10-second automatic updates

## Quick Start

### Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run

```bash
python app.py
```

Open **http://127.0.0.1:8050** in your browser.

## Project Structure

```
wormrider/
├── app.py                 # Main application entry point
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── database/
│   ├── models.py         # Database schema
│   └── db.py             # Database operations
├── collectors/
│   └── binance.py        # Binance data collector
├── indicators/
│   └── orderbook.py      # Order book analysis
└── layouts/
    └── main.py           # Dash UI layout
```

## Configuration

Edit `config.py` to customize:

- `SYMBOLS`: Trading pairs to track
- `SAMPLE_INTERVAL_SECONDS`: Data collection frequency
- `RETENTION_DAYS`: How long to keep historical data
- `DEFAULT_BIN_SIZE`: Default order book bin size

## Roadmap

- [ ] Historical price line chart
- [ ] Net long/short calculations
- [ ] CVD (Cumulative Volume Delta)
- [ ] FRVP (Funding Rate vs Price)
- [ ] Multi-symbol support
- [ ] Alert system

## License

MIT

