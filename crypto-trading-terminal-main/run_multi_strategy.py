"""
Launcher for multi-strategy trading bot.
"""
import asyncio
import sys
from multi_strategy_bot import MultiStrategyBot

async def main():
    """Main entry point for multi-strategy bot."""
    print("Multi-Strategy Hyperliquid Trading Bot")
    print("=" * 50)
    
    # Define which strategies to run
    strategies = ["rsi", "bollinger_bands", "macd"]
    
    print(f"Running strategies: {', '.join(strategies)}")
    print("=" * 50)
    
    try:
        bot = MultiStrategyBot(strategies)
        await bot.start()
    except Exception as e:
        print(f"Bot failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())