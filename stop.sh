#!/bin/bash
# Wormrider Stop Script - Completely stop all processes

echo "🛑 Stopping all Wormrider processes..."

# Kill Python processes related to app.py
pkill -9 -f "python.*app.py" 2>/dev/null

# Kill any Wormrider-related processes
pkill -9 -f "Wormrider" 2>/dev/null

# Kill any processes using port 8060
echo "🔌 Killing port 8060..."
lsof -ti:8060 | xargs kill -9 2>/dev/null

# Wait a moment
sleep 1

# Verify everything is stopped
PORT_CHECK=$(lsof -ti:8060 2>/dev/null)
if [ -z "$PORT_CHECK" ]; then
    echo "✅ Wormrider stopped successfully. Port 8060 is free."
else
    echo "⚠️  Warning: Port 8060 still in use (PID: $PORT_CHECK)"
fi

PROCESS_CHECK=$(pgrep -f "python.*app.py" 2>/dev/null)
if [ -z "$PROCESS_CHECK" ]; then
    echo "✅ All Python processes stopped."
else
    echo "⚠️  Warning: Python processes still running (PID: $PROCESS_CHECK)"
fi

echo "🏁 Done."

# Usage:
# chmod +x stop.sh
# ./stop.sh

