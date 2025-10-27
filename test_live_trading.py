"""
Test live trading integration
"""

import os
from dotenv import load_dotenv

load_dotenv()

print("="*60)
print("LIVE TRADING INTEGRATION TEST")
print("="*60)

# Check environment
use_mainnet = os.getenv('USE_LIGHTER_MAINNET', 'false').lower() == 'true'
live_trading = os.getenv('LIGHTER_LIVE_TRADING', 'false').lower() == 'true'

print(f"\n🌐 Network: {'MAINNET' if use_mainnet else 'TESTNET'}")
print(f"💰 Live Trading: {'ENABLED' if live_trading else 'DISABLED'}")
print(f"💵 Position Size: ${os.getenv('LIGHTER_POSITION_SIZE', '500')}")

if not live_trading:
    print("\n⚠️  Live trading is disabled in .env")
    print("   Set LIGHTER_LIVE_TRADING=true to enable")
else:
    print("\n⚠️  LIVE TRADING IS ENABLED!")
    print("   Real trades will be executed on Lighter")
    
print("\n" + "="*60)

# Test live trading import
try:
    from strategy import live_trading
    print("✅ Live trading module imported successfully")
    print(f"   Trading enabled: {live_trading.live_trading.trading_enabled}")
except Exception as e:
    print(f"❌ Error importing live trading: {e}")
    import traceback
    traceback.print_exc()

print("="*60)
