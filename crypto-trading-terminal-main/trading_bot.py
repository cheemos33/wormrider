"""
Main trading bot orchestrator.
"""
import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd

from config import get_config, validate_config
from hyperliquid_client import HyperliquidClient
from strategies import MovingAverageStrategy, MomentumStrategy, RSIStrategy
from risk_management import RiskManager, Position
from logger import get_logger
from backtesting import BacktestEngine

class TradingBot:
    """Main trading bot class that orchestrates all components."""
    
    def __init__(self, strategy_name: str = "moving_average", strategy_params: Optional[Dict] = None):
        self.config = get_config()
        self.logger = get_logger("trading_bot")
        
        # Validate configuration
        if not validate_config():
            raise ValueError("Invalid configuration. Please check your .env file.")
        
        # Initialize components
        self.client = HyperliquidClient()
        self.risk_manager = RiskManager()
        self.strategy = self._initialize_strategy(strategy_name, strategy_params)
        self.is_running = False
        self.last_update = None
        
        self.logger.info(f"Trading bot initialized with {strategy_name} strategy")
    
    def _initialize_strategy(self, strategy_name: str, params: Optional[Dict] = None) -> Any:
        """Initialize the trading strategy."""
        strategy_map = {
            "moving_average": MovingAverageStrategy,
            "momentum": MomentumStrategy,
            "rsi": RSIStrategy
        }
        
        if strategy_name not in strategy_map:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        
        strategy_class = strategy_map[strategy_name]
        return strategy_class(params or {})
    
    async def start(self):
        """Start the trading bot."""
        self.logger.info("Starting trading bot...")
        self.is_running = True
        
        try:
            # Initial setup
            await self._initial_setup()
            
            # Main trading loop
            while self.is_running:
                await self._trading_cycle()
                await asyncio.sleep(60)  # Wait 1 minute between cycles
                
        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
        except Exception as e:
            self.logger.error(f"Bot error: {e}")
        finally:
            await self._cleanup()
    
    async def stop(self):
        """Stop the trading bot."""
        self.logger.info("Stopping trading bot...")
        self.is_running = False
    
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
        """Execute one trading cycle."""
        try:
            self.logger.debug("Starting trading cycle...")
            
            # Get market data
            market_data = await self.client.get_market_data(self.config.default_symbol)
            if not market_data:
                self.logger.warning("No market data available")
                return
            
            # Convert to DataFrame (simplified - in real implementation, you'd get historical data)
            try:
                levels = market_data.get('levels', [])
                if levels and len(levels) >= 2:
                    # Get the best bid and ask prices
                    best_bid = float(levels[0][0]['px'])  # Highest bid
                    best_ask = float(levels[1][0]['px'])  # Lowest ask
                    # Use mid-price (average of bid and ask)
                    current_price = (best_bid + best_ask) / 2
                    self.logger.info(f"ETH Price: ${current_price:.2f} (Bid: ${best_bid:.2f}, Ask: ${best_ask:.2f})")
                else:
                    self.logger.warning("No price data available, using default")
                    current_price = 3000.0  # Default ETH price
            except (ValueError, TypeError, IndexError, KeyError) as e:
                self.logger.warning(f"Error parsing price data: {e}, using default")
                current_price = 3000.0  # Default ETH price
                            
            # Update risk manager
            self.risk_manager.reset_daily_metrics()
            
            # Check existing positions
            await self._check_existing_positions(current_price)
            
            # Check for new trading opportunities
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
            
            # Check strategy exit signal
            # Note: In a real implementation, you'd need historical data for the strategy
            # For now, we'll skip this check
    
    async def _check_trading_opportunities(self, current_price: float):
        """Check for new trading opportunities."""
        # Check if we can open new positions
        if not self.risk_manager.can_open_position(self.config.default_symbol, self.config.default_side):
            return
        
        # Create mock data for strategy (in real implementation, get historical data)
        # This is a simplified version - you'd typically fetch historical OHLCV data
        mock_data = pd.DataFrame({
            'close': [current_price] * 50,  # Mock historical data
            'volume': [1000] * 50
        })
        
        self.strategy.update_data(mock_data)
        
        # Check if strategy suggests entering a position
        if self.strategy.should_enter_position(mock_data.iloc[-1]):
            await self._open_position(current_price)
    
    async def _open_position(self, price: float):
        """Open a new position."""
        try:
            # Calculate position size
            position_size = self.risk_manager.calculate_position_size(
                self.config.default_symbol, 
                price
            )
            
            if position_size <= 0:
                self.logger.warning("Position size too small, skipping trade")
                return
            
            # Place order
            order_result = await self.client.place_order(
                symbol=self.config.default_symbol,
                side=self.config.default_side,
                size=position_size,
                price=price
            )
            
            if order_result.get('status') == 'ok':
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
                self.logger.trade_executed(
                    self.config.default_symbol,
                    self.config.default_side,
                    position_size,
                    price,
                    order_result.get('response', {}).get('data', 'unknown')
                )
            else:
                self.logger.error(f"Failed to place order: {order_result}")
                
        except Exception as e:
            self.logger.error(f"Error opening position: {e}")
    
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
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        summary = self.risk_manager.get_portfolio_summary()
        
        return {
            "is_running": self.is_running,
            "strategy": self.strategy.name,
            "last_update": self.last_update,
            "portfolio": summary,
            "config": {
                "default_symbol": self.config.default_symbol,
                "max_positions": self.config.max_open_positions,
                "leverage": self.config.leverage
            }
        }
