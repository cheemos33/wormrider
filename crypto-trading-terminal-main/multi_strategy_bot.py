"""
Multi-strategy trading bot that runs multiple strategies in parallel.
"""
import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd

from config import get_config, validate_config
from hyperliquid_client import HyperliquidClient
from strategies import MovingAverageStrategy, MomentumStrategy, RSIStrategy, BollingerBandsStrategy, MACDStrategy, MeanReversionStrategy, DCAStrategy
from risk_management import RiskManager, Position
from logger import get_logger

class MultiStrategyBot:
    """Trading bot that runs multiple strategies in parallel."""
    
    def __init__(self, strategy_names: List[str] = None):
        self.config = get_config()
        self.logger = get_logger("multi_strategy_bot")
        
        # Validate configuration
        if not validate_config():
            raise ValueError("Invalid configuration. Please check your .env file.")
        
        # Initialize strategies
        self.strategy_map = {
            "moving_average": MovingAverageStrategy,
            "momentum": MomentumStrategy,
            "rsi": RSIStrategy,
            "bollinger_bands": BollingerBandsStrategy,
            "macd": MACDStrategy,
            "mean_reversion": MeanReversionStrategy,
            "dca": DCAStrategy
        }

        self.strategies = {} 
        
        # Balance and budget tracking
        self.initial_balance = 999.0  # Starting balance
        self.current_balance = 999.0  # Current balance
        self.dca_budget = 100.0  # DCA budget limit
        self.dca_spent = 0.0  # Amount spent on DCA
                
        # Default strategies if none specified
        if not strategy_names:
            strategy_names = []
        
        # Initialize each strategy
        for name in strategy_names:
            if name in self.strategy_map:
                self.strategies[name] = self.strategy_map[name]()
                self.logger.info(f"Initialized {name} strategy")
            else:
                self.logger.warning(f"Unknown strategy: {name}")
        
        # Initialize components
        self.client = HyperliquidClient()
        self.risk_manager = RiskManager()
        self.is_running = False
        self.last_update = None
        
        self.logger.info(f"Multi-strategy bot initialized with {len(self.strategies)} strategies")
    
    async def start(self):
        """Start the multi-strategy trading bot."""
        self.logger.info("Starting multi-strategy trading bot...")
        self.is_running = True
        
        try:
            # Initial setup
            await self._initial_setup()
            
            # Main trading loop
            while self.is_running:
                await self._trading_cycle()
                
                # Dynamic sleep based on shortest DCA interval
                sleep_time = self._get_optimal_sleep_time()
                await asyncio.sleep(sleep_time)
                
        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
        except Exception as e:
            self.logger.error(f"Bot error: {e}")
        finally:
            await self._cleanup()
    
    async def stop(self):
        """Stop the trading bot."""
        self.logger.info("Stopping multi-strategy trading bot...")
        self.is_running = False
    
    def _get_optimal_sleep_time(self) -> int:
        """Get optimal sleep time based on active DCA strategies."""
        if 'dca' not in self.strategies:
            return 60  # Default 1 minute if no DCA
        
        dca_strategy = self.strategies['dca']
        if not getattr(dca_strategy, 'is_active', True):
            return 60  # Default if DCA is inactive
        
        # Get DCA interval in minutes, convert to seconds
        interval_minutes = dca_strategy.get_parameter('interval_minutes')
        interval_seconds = int(interval_minutes * 60)
        
        # Use shorter of: DCA interval or 5 seconds minimum
        optimal_sleep = min(max(interval_seconds, 5), 60)  # Between 5-60 seconds
        
        self.logger.debug(f"DCA interval: {interval_minutes} min, Sleep time: {optimal_sleep} sec")
        return optimal_sleep
    
    async def _initial_setup(self):
        """Perform initial setup tasks."""
        self.logger.info("Performing initial setup...")
        
        # Test API connection
        try:
            balance = await self.client.get_balance()
            self.logger.info(f"Connected to Hyperliquid. Account balance: ${balance:.2f}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Hyperliquid: {e}")
            raise
        
        # Get current positions
        positions = await self.client.get_positions()
        self.logger.info(f"Current positions: {len(positions)}")
        
        # Initialize risk manager with existing positions
        for pos in positions:
            if float(pos.get('position', {}).get('szi', 0)) != 0:
                position = Position(
                    symbol=pos.get('position', {}).get('coin', ''),
                    side='long' if float(pos.get('position', {}).get('szi', 0)) > 0 else 'short',
                    size=abs(float(pos.get('position', {}).get('szi', 0))),
                    entry_price=float(pos.get('position', {}).get('entryPx', 0)),
                    current_price=float(pos.get('position', {}).get('entryPx', 0)),
                    entry_time=datetime.now()
                )
                self.risk_manager.add_position(position)
    
    async def _trading_cycle(self):
        """Execute one trading cycle for all strategies."""
        try:
            self.logger.debug("Starting trading cycle...")
            
            # Get market data
            market_data = await self.client.get_market_data(self.config.default_symbol)
            if not market_data:
                self.logger.warning("No market data available")
                return
            
            # Parse current price
            try:
                levels = market_data.get('levels', [])
                if levels and len(levels) >= 2:
                    best_bid = float(levels[0][0]['px'])
                    best_ask = float(levels[1][0]['px'])
                    current_price = (best_bid + best_ask) / 2
                    self.logger.info(f"ETH Price: ${current_price:.2f} (Bid: ${best_bid:.2f}, Ask: ${best_ask:.2f})")
                else:
                    self.logger.warning("No price data available, using default")
                    current_price = 3000.0
            except (ValueError, TypeError, IndexError, KeyError) as e:
                self.logger.warning(f"Error parsing price data: {e}, using default")
                current_price = 3000.0
            
            # Update risk manager
            self.risk_manager.reset_daily_metrics()
            
            # Check existing positions
            await self._check_existing_positions(current_price)
            
            # Check for new trading opportunities for each strategy
            await self._check_trading_opportunities(current_price)
            
            self.last_update = datetime.now()
            self.logger.debug("Trading cycle completed")
            
        except Exception as e:
            self.logger.error(f"Error in trading cycle: {e}")
    
    async def _check_existing_positions(self, current_price: float):
        """Check and manage existing positions."""
        for position in self.risk_manager.positions[:]:
            # Update position PnL
            self.risk_manager.update_position_pnl(position.symbol, current_price)
            
            # Check stop loss
            if self.risk_manager.check_stop_loss(position.symbol, current_price):
                await self._close_position(position, "stop_loss")
                continue
            
            # Check take profit
            if self.risk_manager.check_take_profit(position.symbol, current_price):
                await self._close_position(position, "take_profit")
                continue
    
    async def _check_trading_opportunities(self, current_price: float):
        """Check for new trading opportunities for each strategy."""
        for strategy_name, strategy in self.strategies.items():
            try:
                # Check if we can open new positions (allow DCA to accumulate)
                if strategy_name != 'dca' and not self.risk_manager.can_open_position(self.config.default_symbol, self.config.default_side):
                    continue
                
                # Create mock data for strategy (in real implementation, get historical data)
                mock_data = pd.DataFrame({
                    'close': [current_price] * 50,  # Mock historical data
                    'volume': [1000] * 50
                })
                
                strategy.update_data(mock_data)
                
                # Check if strategy suggests entering a position
                if strategy.should_enter_position(mock_data.iloc[-1]):
                    await self._open_position(current_price, strategy_name)
                    
            except Exception as e:
                self.logger.error(f"Error checking {strategy_name} strategy: {e}")
    
    async def _open_position(self, price: float, strategy_name: str):
        """Open a new position for a specific strategy."""
        try:
            # For DCA strategy, check budget limits
            if strategy_name == 'dca':
                dca_strategy = self.strategies.get('dca')
                if dca_strategy:
                    position_size = dca_strategy.get_position_size()
                    trade_cost = position_size * price
                    
                    # Check if we have enough budget left
                    total_cost = self.dca_spent + trade_cost
                    self.logger.debug(f"DCA Budget Check - Spent: ${self.dca_spent:.2f}, Trade Cost: ${trade_cost:.2f}, Total: ${total_cost:.2f}, Budget: ${self.dca_budget:.2f}")
                    
                    if total_cost > self.dca_budget:
                        self.logger.warning(f"DCA budget exceeded. Spent: ${self.dca_spent:.2f}, Budget: ${self.dca_budget:.2f}")
                        return
                    
                    # Check if we have enough balance
                    if trade_cost > self.current_balance:
                        self.logger.warning(f"Insufficient balance for DCA trade. Cost: ${trade_cost:.2f}, Balance: ${self.current_balance:.2f}")
                        return
            else:
                # Calculate position size for other strategies
                position_size = self.risk_manager.calculate_position_size(
                    self.config.default_symbol, 
                    price
                )
            
            if position_size <= 0:
                self.logger.warning(f"Position size too small for {strategy_name}, skipping trade")
                return
            
            # Place order (disabled for now due to API format issues)
            # TODO: Fix Hyperliquid API order format
            order_result = {"status": "ok", "response": {"data": "simulated_trade"}}
            
            # Uncomment below when API format is fixed:
            # order_result = await self.client.place_order(
            #     symbol=self.config.default_symbol,
            #     side=self.config.default_side,
            #     size=position_size,
            #     price=price
            # )
            
            if order_result.get('status') == 'ok':
                # Calculate trade cost
                trade_cost = position_size * price
                
                # Update balance tracking
                if strategy_name == 'dca':
                    self.dca_spent += trade_cost
                    self.current_balance -= trade_cost
                    self.logger.info(f"DCA Trade: ${trade_cost:.2f} spent, Budget remaining: ${self.dca_budget - self.dca_spent:.2f}")
                else:
                    self.current_balance -= trade_cost
                
                # Create position object
                position = Position(
                    symbol=self.config.default_symbol,
                    side=self.config.default_side,
                    size=position_size,
                    entry_price=price,
                    current_price=price,
                    entry_time=datetime.now(),
                    stop_loss=self.risk_manager.calculate_stop_loss_price(price, self.config.default_side),
                    take_profit=self.risk_manager.calculate_take_profit_price(price, self.config.default_side)
                )
                
                self.risk_manager.add_position(position)
                
                # Record DCA buy if it's a DCA strategy
                if strategy_name == 'dca':
                    self.strategies[strategy_name].record_buy()
                    self.logger.info(f"DCA Buy recorded - Total today: {self.strategies[strategy_name].today_buys}")
                
                self.logger.trade_executed(
                    self.config.default_symbol,
                    self.config.default_side,
                    position_size,
                    price,
                    f"{strategy_name}_{order_result.get('response', {}).get('data', 'unknown')}"
                )
            else:
                self.logger.error(f"Failed to place order for {strategy_name}: {order_result}")
                
        except Exception as e:
            self.logger.error(f"Error opening position for {strategy_name}: {e}")
    
    async def _close_position(self, position: Position, reason: str):
        """Close an existing position."""
        try:
            # Place closing order
            close_side = 'short' if position.side == 'long' else 'long'
            
            order_result = await self.client.place_order(
                symbol=position.symbol,
                side=close_side,
                size=position.size,
                price=position.current_price
            )
            
            if order_result.get('status') == 'ok':
                # Calculate PnL
                pnl = position.unrealized_pnl
                
                # Remove from risk manager
                self.risk_manager.remove_position(position.symbol, position.side)
                
                # Update daily PnL
                self.risk_manager.daily_pnl += pnl
                
                self.logger.position_closed(
                    position.symbol,
                    position.side,
                    position.size,
                    position.current_price,
                    pnl
                )
            else:
                self.logger.error(f"Failed to close position: {order_result}")
                
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
    
    async def _cleanup(self):
        """Cleanup when bot stops."""
        self.logger.info("Performing cleanup...")
        
        # Print final portfolio summary
        summary = self.risk_manager.get_portfolio_summary()
        self.logger.info(f"Final portfolio summary: {summary}")
    
    def update_strategies(self, strategy_names: List[str]):
        """Update the active strategies."""
        self.logger.info(f"Updating strategies to: {strategy_names}")
        
        # Clear existing strategies
        self.strategies = {}
        
        # Initialize new strategies
        for name in strategy_names:
            if name in self.strategy_map:
                self.strategies[name] = self.strategy_map[name]()
                self.logger.info(f"Initialized {name} strategy")
            else:
                self.logger.warning(f"Unknown strategy: {name}")
        
        self.logger.info(f"Updated to {len(self.strategies)} strategies")
    
    def update_dca_budget(self, budget: float):
        """Update DCA budget limit."""
        old_budget = self.dca_budget
        self.dca_budget = budget
        self.logger.info(f"DCA budget updated from ${old_budget:.2f} to ${budget:.2f}")
    
    def reset_dca_spending(self):
        """Reset DCA spending counter."""
        self.dca_spent = 0.0
        self.logger.info("DCA spending reset")

    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        summary = self.risk_manager.get_portfolio_summary()
        
        # Calculate current PnL from positions
        total_pnl = sum(pos.unrealized_pnl for pos in self.risk_manager.positions)
        updated_balance = self.initial_balance + total_pnl
        
        return {
            "is_running": self.is_running,
            "strategies": list(self.strategies.keys()),
            "last_update": self.last_update,
            "portfolio": summary,
            "balance": {
                "initial": self.initial_balance,
                "current": updated_balance,
                "pnl": total_pnl
            },
            "dca": {
                "budget": self.dca_budget,
                "spent": self.dca_spent,
                "remaining": self.dca_budget - self.dca_spent,
                "today_buys": self.strategies.get('dca', {}).today_buys if 'dca' in self.strategies else 0
            },
            "config": {
                "default_symbol": self.config.default_symbol,
                "max_positions": self.config.max_open_positions,
                "leverage": self.config.leverage
            }
        }