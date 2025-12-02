#!/bin/bash
# Wormrider Clean Restart Script

echo "🛑 Stopping all Python processes..."
pkill -9 -f "python.*app.py" 2>/dev/null
pkill -9 -f "Wormrider" 2>/dev/null

echo "🔌 Killing port 8060..."
lsof -ti:8060 | xargs kill -9 2>/dev/null

echo "⏳ Waiting 2 seconds..."
sleep 2

echo "🧹 Cleaning up database (optional)..."
# Uncomment the line below to clear database on restart
# rm -f /Users/cheemos/Desktop/Wormrider/wormrider.db*

cd /Users/cheemos/Desktop/Wormrider

echo "🚀 Starting Wormrider..."
source .venv/bin/activate
python app.py

# Usage:
# chmod +x restart.sh
# ./restart.sh


.venv/bin/activate    
pip install --upgrade pip       
pip install lighter-sdk python-dotenv
python lighter_market_buy.py


PYTHONPATH=. dotenv -f .env.lighter run -- python lighter_trade_trailing_time_.py


sqlite3 -cmd ".headers on" -cmd ".mode column" wormrider.db "
SELECT
  datetime(timestamp/1000,'unixepoch','localtime') AS ts_local,
  id, signal_type, direction,
  entry_price, tp_price, sl_price, exit_reason
FROM signals
WHERE signal_type = 'HYBRID'
ORDER BY timestamp DESC;
">hybrid_signals_nov10.csv



