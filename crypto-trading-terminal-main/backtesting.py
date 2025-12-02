"""
Backtesting engine for trading strategies.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from strategies.base_strategy import BaseStrategy
from risk_management import RiskManager, Position
from logger import get_logger

@dataclass
class Trade:
    """Trade data structure for backtesting."""
    symbol: str
    side: str
    size: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    commission: float = 0.0

@dataclass
class BacktestResult:
    """Backtest results data structure."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    trades: List[Trade]
    equity_curve: pd.Series

class BacktestEngine:
    """Backtesting engine for trading strategies."""
    
    def __init__(self, initial_balance: float = 10000.0, commission: float = 0.001):
        self.initial_balance = initial_balance
        self.commission = commission
        self.logger = get_logger("backtest")
        
    def run_backtest(self, 
                    strategy: BaseStrategy, 
                    data: pd.DataFrame,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> BacktestResult:
        """
        Run backtest on a strategy with historical data.
        
        Args:
            strategy: Trading strategy to test
            data: Historical OHLCV data
            start_date: Start date for backtest (YYYY-MM-DD)
            end_date: End date for backtest (YYYY-MM-DD)
            
        Returns:
            BacktestResult object with performance metrics
        """
        # Filter data by date range if specified
        if start_date:
            data = data[data.index >= start_date]
        if end_date:
            data = data[data.index <= end_date]
        
        if data.empty:
            raise ValueError("No data available for the specified date range")
        
        # Initialize backtest state
        balance = self.initial_balance
        positions = []
        trades = []
        equity_curve = []
        
        # Update strategy with data
        strategy.update_data(data)
        
        # Run backtest
        for i, (timestamp, row) in enumerate(data.iterrows()):
            current_price = row['close']
            
            # Update existing positions
            for position in positions[:]:
                # Check stop loss and take profit
                should_exit = False
                exit_reason = ""
                
                if position.side == 'long':
                    if current_price <= position.stop_loss:
                        should_exit = True
                        exit_reason = "stop_loss"
                    elif current_price >= position.take_profit:
                        should_exit = True
                        exit_reason = "take_profit"
                else:  # short
                    if current_price >= position.stop_loss:
                        should_exit = True
                        exit_reason = "stop_loss"
                    elif current_price <= position.take_profit:
                        should_exit = True
                        exit_reason = "take_profit"
                
                # Check strategy exit signal
                if not should_exit and strategy.should_exit_position(row, {
                    'symbol': position.symbol,
                    'side': position.side,
                    'size': position.size,
                    'entry_price': position.entry_price
                }):
                    should_exit = True
                    exit_reason = "strategy_signal"
                
                if should_exit:
                    # Close position
                    pnl = self._calculate_pnl(position, current_price)
                    commission_cost = position.size * current_price * self.commission
                    net_pnl = pnl - commission_cost
                    
                    trade = Trade(
                        symbol=position.symbol,
                        side=position.side,
                        size=position.size,
                        entry_price=position.entry_price,
                        exit_price=current_price,
                        entry_time=position.entry_time,
                        exit_time=timestamp,
                        pnl=net_pnl,
                        commission=commission_cost
                    )
                    
                    trades.append(trade)
                    balance += net_pnl
                    positions.remove(position)
                    
                    self.logger.debug(f"Position closed: {position.symbol} {position.side} - PnL: {net_pnl:.2f}")
            
            # Check for new position entry
            if strategy.should_enter_position(row):
                # Calculate position size (simplified)
                position_size = min(0.1, balance * 0.1 / current_price)  # 10% of balance
                
                if position_size > 0:
                    # Create new position
                    stop_loss = self._calculate_stop_loss(current_price, 'long', 0.02)
                    take_profit = self._calculate_take_profit(current_price, 'long', 0.03)
                    
                    position = Position(
                        symbol='ETH',  # Default symbol
                        side='long',
                        size=position_size,
                        entry_price=current_price,
                        current_price=current_price,
                        entry_time=timestamp,
                        stop_loss=stop_loss,
                        take_profit=take_profit
                    )
                    
                    positions.append(position)
                    commission_cost = position_size * current_price * self.commission
                    balance -= commission_cost
                    
                    self.logger.debug(f"Position opened: {position.symbol} {position.side} at {current_price}")
            
            # Record equity
            total_equity = balance
            for position in positions:
                unrealized_pnl = self._calculate_pnl(position, current_price)
                total_equity += unrealized_pnl
            
            equity_curve.append(total_equity)
        
        # Close any remaining positions
        for position in positions:
            final_price = data['close'].iloc[-1]
            pnl = self._calculate_pnl(position, final_price)
            commission_cost = position.size * final_price * self.commission
            net_pnl = pnl - commission_cost
            
            trade = Trade(
                symbol=position.symbol,
                side=position.side,
                size=position.size,
                entry_price=position.entry_price,
                exit_price=final_price,
                entry_time=position.entry_time,
                exit_time=data.index[-1],
                pnl=net_pnl,
                commission=commission_cost
            )
            
            trades.append(trade)
            balance += net_pnl
        
        # Calculate performance metrics
        return self._calculate_metrics(trades, equity_curve)
    
    def _calculate_pnl(self, position: Position, current_price: float) -> float:
        """Calculate PnL for a position."""
        if position.side == 'long':
            return (current_price - position.entry_price) * position.size
        else:  # short
            return (position.entry_price - current_price) * position.size
    
    def _calculate_stop_loss(self, entry_price: float, side: str, percentage: float) -> float:
        """Calculate stop loss price."""
        if side == 'long':
            return entry_price * (1 - percentage)
        else:  # short
            return entry_price * (1 + percentage)
    
    def _calculate_take_profit(self, entry_price: float, side: str, percentage: float) -> float:
        """Calculate take profit price."""
        if side == 'long':
            return entry_price * (1 + percentage)
        else:  # short
            return entry_price * (1 - percentage)
    
    def _calculate_metrics(self, trades: List[Trade], equity_curve: List[float]) -> BacktestResult:
        """Calculate backtest performance metrics."""
        if not trades:
            return BacktestResult(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                trades=[],
                equity_curve=pd.Series(equity_curve)
            )
        
        # Basic metrics
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        total_pnl = sum(t.pnl for t in trades)
        
        # Calculate max drawdown
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # Calculate Sharpe ratio (simplified)
        if len(equity_curve) > 1:
            returns = pd.Series(equity_curve).pct_change().dropna()
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        return BacktestResult(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            trades=trades,
            equity_curve=equity_series
        )
    
    def print_results(self, result: BacktestResult):
        """Print backtest results in a formatted way."""
        print("\n" + "="*50)
        print("BACKTEST RESULTS")
        print("="*50)
        print(f"Total Trades: {result.total_trades}")
        print(f"Winning Trades: {result.winning_trades}")
        print(f"Losing Trades: {result.losing_trades}")
        print(f"Win Rate: {result.win_rate:.1%}")
        print(f"Total PnL: ${result.total_pnl:.2f}")
        print(f"Max Drawdown: {result.max_drawdown:.1%}")
        print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print("="*50)
