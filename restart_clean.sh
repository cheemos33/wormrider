#!/bin/bash
# Wormrider Clean Restart Script (with database cleanup)

echo "🛑 Stopping all Python processes..."
pkill -9 -f "python.*app.py" 2>/dev/null
pkill -9 -f "Wormrider" 2>/dev/null

echo "🔌 Killing port 8060..."
lsof -ti:8060 | xargs kill -9 2>/dev/null

echo "⏳ Waiting 2 seconds..."
sleep 2

echo "🧹 Cleaning up database..."
rm -f /Users/cheemos/Desktop/Wormrider/wormrider.db*

cd /Users/cheemos/Desktop/Wormrider

echo "🚀 Starting Wormrider (fresh database)..."
source .venv/bin/activate
python app.py

# Usage:
# chmod +x restart_clean.sh
# ./restart_clean.sh

