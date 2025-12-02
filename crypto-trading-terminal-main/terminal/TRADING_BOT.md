# Trading Bot - Signal-Based Execution

## Overview

The trading bot automatically executes 4★ signals on Hyperliquid testnet after you manually long BTC.

## How It Works

### 1. Activation
- **Manual:** Click "START" button in BOT STATUS section
- **Automatic:** Bot detects when you open a BTC long position (coming soon)
- Bot verifies testnet balance ≥ $50

### 2. Signal Processing
- Bot monitors for NEW 4★ signals (signals that appear AFTER activation)
- Calculates "dip score" for each signal:
  ```
  Dip Score = |RSI - 18| + |VAL| + |1d RVWAP| + |7d RVWAP|
  ```
- Higher score = deeper dip = higher priority

### 3. Trade Execution
- **Frequency:** 1 trade per minute
- **Selection:** Picks signal with highest dip score
- **Position size:** $2.50 per entry
- **Leverage:** 1x (no leverage)
- **Max entries per coin:** 3 (can accumulate if same coin keeps signaling)

### 4. Budget Management
- **Total budget:** $50
- **Max positions:** 20 entries total ($2.50 × 20)
- **Max per coin:** 3 entries ($2.50 × 3 = $7.50)
- Bot stops trading when budget exhausted

### 5. Deactivation
- **Manual:** Click "STOP" button
- **Automatic:** When BTC position closes (coming soon)
- **Existing positions:** Remain open (manual exit)

## 4★ Signal Criteria

All 4 must be true:
1. ✅ RSI < 18 (extremely oversold)
2. ✅ Price < VAL (below value area low)
3. ✅ Price < 1d RVWAP (below 1-day average)
4. ✅ Price < 7d RVWAP (below 7-day average)

## BOT STATUS Display

### Status Indicator
- **● ACTIVE** (green) - Bot is trading
- **○ INACTIVE** (gray) - Bot is idle

### Budget Bar
- Visual bar showing spent/remaining budget
- Green: < 80% used
- Red: ≥ 80% used

### Active Positions
- List of longed coins
- Shows: Coin, avg price, entries (X/3)
- Scrollable list

### Recent Trades
- Last 5 trades executed
- Shows: Time, coin, price, entry number

## Files

- `trading/position_manager.py` - Tracks positions and budget
- `trading/signal_trader.py` - Main bot logic
- `components/alerts.py` - UI display
- `data/positions.json` - Stores positions and trade history

## Current Status

### ✅ Implemented:
- Position tracking
- Budget management
- Dip score calculation
- Trade logging
- UI display
- Manual START/STOP

### 🚧 TODO (Needs API Integration):
- BTC position detection via Hyperliquid API
- Actual order placement on Hyperliquid
- Balance verification
- Async execution in background

### 📝 Notes:
- Currently runs in manual mode (click START)
- Order execution is simulated (placeholder)
- Ready for Hyperliquid API integration
- All logic is complete, just needs API hookup

## Testing

1. Click "START" button
2. Bot activates (status shows ● ACTIVE)
3. Wait for 4★ signals to appear
4. Bot will simulate trades (logs in terminal)
5. See positions and trades in BOT STATUS
6. Click "STOP" to deactivate

## Next Steps

1. Implement Hyperliquid position checking
2. Implement actual order placement
3. Add async background task for bot
4. Test on testnet with real orders


