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

