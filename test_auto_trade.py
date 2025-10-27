"""
Test script: Automatically place a LONG order on Lighter
and monitor TP/SL.
"""

import os
import time
from dotenv import load_dotenv

# Load environment
load_dotenv()

print("=" * 60)
print("LIGHTER AUTO TRADE TEST")
print("=" * 60)

# Check if live trading is enabled
trading_enabled = os.getenv('LIGHTER_LIVE_TRADING', 'false').lower() == 'true'
if not trading_enabled:
    print("❌ LIGHTER_LIVE_TRADING is not enabled in .env")
    print("   Set LIGHTER_LIVE_TRADING=true to execute real trades")
    exit(1)

print("✅ Live trading ENABLED")
print()

# Get current price
import httpx
response = httpx.get('https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT', timeout=5)
current_price = float(response.json()['price'])

# Test signal (simulating INSTANT_XL LONG signal)
test_signal = {
    'id': 'test_001',
    'direction': 'long',
    'entry_price': current_price,
    'tp_price': current_price * (1 + 0.001327),  # TP
    'sl_price': current_price * (1 - 0.001062),  # SL
    'strategy': 'INSTANT_XL',
    'imbalance_ratio': 0.65
}

print(f"Current BTC Price: ${current_price:,.2f}")
print(f"TP Target: ${test_signal['tp_price']:,.2f} (+0.1327%)")
print(f"SL Target: ${test_signal['sl_price']:,.2f} (-0.1062%)")
print()

print("Placing market buy order...")
print("=" * 60)

# Execute the signal
from strategy import live_trading

try:
    success = live_trading.live_trading.execute_signal(test_signal)
    
    if success:
        print()
        print("✅ Order placed successfully!")
        print()
        print("📊 Monitoring position for TP/SL...")
        print("=" * 60)
        print()
        
        # Keep script running to monitor
        try:
            while True:
                time.sleep(10)
                # Print status every 10 seconds
                open_positions = live_trading.live_trading.open_positions
                if len(open_positions) == 0:
                    print("✅ All positions closed")
                    break
                else:
                    print(f"⏳ Monitoring {len(open_positions)} open position(s)...")
        except KeyboardInterrupt:
            print("\n👋 Script stopped by user")
    else:
        print()
        print("❌ Failed to place order")
        print("Check your .env configuration and Lighter credentials")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

