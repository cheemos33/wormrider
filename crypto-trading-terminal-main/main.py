"""
Main entry point for the Hyperliquid trading bot.
"""
from strategies import MovingAverageStrategy, MomentumStrategy, RSIStrategy, BollingerBandsStrategy, MACDStrategy
import asyncio
import argparse
import sys
from typing import Dict, Any
import pandas as pd

from config import get_config
from trading_bot import TradingBot
from backtesting import BacktestEngine
from strategies import MovingAverageStrategy, MomentumStrategy, RSIStrategy
from logger import get_logger

def create_sample_data() -> pd.DataFrame:
    """Create sample data for backtesting."""
    import numpy as np
    
    # Generate sample OHLCV data with more realistic price movements
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='1h')
    np.random.seed(42)
    
    # Create more realistic price data with trends and volatility
    n_points = len(dates)
    
    # Generate trend component
    trend = np.linspace(100, 150, n_points)  # Upward trend
    
    # Generate cyclical component
    cycle = 20 * np.sin(np.linspace(0, 4*np.pi, n_points))
    
    # Generate random noise
    noise = np.random.normal(0, 5, n_points)
    
    # Combine components
    base_prices = trend + cycle + noise
    
    # Generate OHLC data
    data = pd.DataFrame(index=dates)
    data['close'] = base_prices
    
    # Generate open prices (close of previous period with small gap)
    data['open'] = data['close'].shift(1).fillna(data['close'].iloc[0])
    data['open'] += np.random.normal(0, 1, n_points)
    
    # Generate high and low prices
    data['high'] = np.maximum(data['open'], data['close']) + np.abs(np.random.normal(0, 2, n_points))
    data['low'] = np.minimum(data['open'], data['close']) - np.abs(np.random.normal(0, 2, n_points))
    
    # Generate volume with some correlation to price movement
    price_change = np.abs(data['close'].pct_change().fillna(0))
    data['volume'] = (1000 + price_change * 5000 + np.random.randint(0, 2000, n_points)).astype(int)
    
    return data

async def run_live_trading(strategy_name: str, strategy_params: Dict[str, Any]):
    """Run live trading bot."""
    logger = get_logger("main")
    logger.info("Starting live trading bot...")
    
    try:
        bot = TradingBot(strategy_name, strategy_params)
        await bot.start()
    except Exception as e:
        logger.error(f"Live trading failed: {e}")
        sys.exit(1)

def run_backtest(strategy_name: str, strategy_params: Dict[str, Any]):
    """Run backtest on a strategy."""
    logger = get_logger("main")
    logger.info(f"Running backtest for {strategy_name} strategy...")
    
    try:
        # Create sample data
        data = create_sample_data()
        
        # Initialize strategy
        strategy_map = {
    "moving_average": MovingAverageStrategy,
    "momentum": MomentumStrategy,
    "rsi": RSIStrategy,
    "bollinger_bands": BollingerBandsStrategy,
    "macd": MACDStrategy
}
        
        if strategy_name not in strategy_map:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        
        strategy = strategy_map[strategy_name](strategy_params)
        
        # Run backtest
        engine = BacktestEngine()
        result = engine.run_backtest(strategy, data)
        
        # Print results
        engine.print_results(result)
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        sys.exit(1)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Hyperliquid Trading Bot")
    parser.add_argument("--mode", choices=["live", "backtest"], default="backtest",
                       help="Run mode: live trading or backtest")
    parser.add_argument("--strategy", choices=["moving_average", "momentum", "rsi", "bollinger_bands", "macd"], 
                   default="moving_average", help="Trading strategy to use")
    parser.add_argument("--params", type=str, default="{}",
                       help="Strategy parameters as JSON string")
    
    args = parser.parse_args()
    
    # Parse strategy parameters
    import json
    try:
        strategy_params = json.loads(args.params)
    except json.JSONDecodeError:
        print("Error: Invalid JSON in --params argument")
        sys.exit(1)
    
    print(f"Hyperliquid Trading Bot")
    print(f"Mode: {args.mode}")
    print(f"Strategy: {args.strategy}")
    print(f"Parameters: {strategy_params}")
    print("-" * 50)
    
    if args.mode == "live":
        # Validate configuration for live trading
        config = get_config()
        if not config.hyperliquid_api_key or config.hyperliquid_api_key == "your_api_key_here":
            print("Error: Please configure your Hyperliquid API credentials in .env file")
            print("Copy config.env.example to .env and fill in your API keys")
            sys.exit(1)
        
        asyncio.run(run_live_trading(args.strategy, strategy_params))
    else:
        run_backtest(args.strategy, strategy_params)

if __name__ == "__main__":
    main()
