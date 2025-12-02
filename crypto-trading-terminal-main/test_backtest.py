import pandas as pd
import numpy as np
from strategies.rsi_strategy import RSIStrategy
from strategies.base_strategy import Signal

# Create test data with clear trends
dates = pd.date_range('2024-01-01', periods=200, freq='1h')
np.random.seed(42)

prices = []
current_price = 100
for i in range(200):
    if i < 50:  # Strong uptrend
        change = np.random.normal(0.5, 0.3)
    elif i < 100:  # Strong downtrend  
        change = np.random.normal(-0.5, 0.3)
    elif i < 150:  # Another uptrend
        change = np.random.normal(0.3, 0.2)
    else:  # Another downtrend
        change = np.random.normal(-0.3, 0.2)
    
    current_price += change
    prices.append(current_price)

# Create OHLCV data
data = pd.DataFrame({
    'open': prices,
    'high': [p * 1.01 for p in prices],
    'low': [p * 0.99 for p in prices],
    'close': prices,
    'volume': [1000] * 200
}, index=dates)

# Test strategy signals
strategy = RSIStrategy()
strategy.update_data(data)
signals = strategy.generate_signals(data)

# Count signals
buy_signals = [i for i, s in enumerate(signals) if s == Signal.BUY]
sell_signals = [i for i, s in enumerate(signals) if s == Signal.SELL]

print(f"Total data points: {len(data)}")
print(f"Buy signals: {len(buy_signals)}")
print(f"Sell signals: {len(sell_signals)}")
print(f"First 10 buy signal indices: {buy_signals[:10]}")
print(f"First 10 sell signal indices: {sell_signals[:10]}")

# Simple backtest simulation
balance = 10000
trades = []
position = None

for i, (timestamp, row) in enumerate(data.iterrows()):
    current_price = row['close']
    
    # Close existing position on sell signal
    if position and i in sell_signals:
        pnl = (current_price - position['entry_price']) * position['size']
        trades.append({
            'entry_time': position['entry_time'],
            'exit_time': timestamp,
            'entry_price': position['entry_price'],
            'exit_price': current_price,
            'size': position['size'],
            'pnl': pnl
        })
        balance += pnl
        
        position = None
    
    # Open new position on buy signal
    elif not position and i in buy_signals:
        position_size = min(0.1, balance * 0.1 / current_price)
        position = {
            'entry_time': timestamp,
            'entry_price': current_price,
            'size': position_size
        }
        print(f"Trade opened: Entry {current_price:.2f}, Size: {position_size:.4f}")

# Close final position if exists
if position:
    final_price = data['close'].iloc[-1]
    pnl = (final_price - position['entry_price']) * position['size']
    trades.append({
        'entry_time': position['entry_time'],
        'exit_time': data.index[-1],
        'entry_price': position['entry_price'],
        'exit_price': final_price,
        'size': position['size'],
        'pnl': pnl
    })
    balance += pnl

# Print results
print(f"\n=== SIMPLE BACKTEST RESULTS ===")
print(f"Total Trades: {len(trades)}")
if trades:
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] < 0]
    total_pnl = sum(t['pnl'] for t in trades)
    win_rate = len(winning_trades) / len(trades) * 100
    
    print(f"Winning Trades: {len(winning_trades)}")
    print(f"Losing Trades: {len(losing_trades)}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Total PnL: ${total_pnl:.2f}")
    print(f"Final Balance: ${balance:.2f}")
    
    # Show first few trades
    print(f"\nFirst 5 trades:")
    for i, trade in enumerate(trades[:5]):
        print(f"Trade {i+1}: Entry ${trade['entry_price']:.2f}, Exit ${trade['exit_price']:.2f}, PnL: ${trade['pnl']:.2f}")
else:
    print("No trades executed")