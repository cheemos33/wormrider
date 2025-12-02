"""
Simple trading dashboard.
"""
import asyncio
import threading
import time
from datetime import datetime
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

from multi_strategy_bot import MultiStrategyBot

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trading_bot_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global bot instance
bot = None
running = False

@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Trading Bot Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .metric { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .strategy-section { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .strategy-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 15px 0; }
        .strategy-item { display: flex; align-items: center; padding: 10px; border: 2px solid #e0e0e0; border-radius: 5px; cursor: pointer; transition: all 0.3s; }
        .strategy-item:hover { border-color: #3498db; }
        .strategy-item.active { border-color: #27ae60; background: #e8f5e8; }
        .strategy-item input[type="checkbox"] { margin-right: 8px; }
        .preset-buttons { display: flex; gap: 10px; margin: 15px 0; }
        .preset-btn { padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
        .preset-btn.aggressive { background: #e74c3c; color: white; }
        .preset-btn.conservative { background: #3498db; color: white; }
        .preset-btn.all { background: #9b59b6; color: white; }
        .preset-btn.custom { background: #f39c12; color: white; }
        .profit { color: #27ae60; font-weight: bold; }
        .loss { color: #e74c3c; font-weight: bold; }
        .status { padding: 10px; border-radius: 5px; margin: 10px 0; }
        .status.running { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .status.stopped { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        
        /* DCA Controls Styles */
        .dca-controls { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .control-group { display: flex; flex-direction: column; gap: 8px; }
        .control-group label { font-weight: bold; color: #2c3e50; }
        
        .interval-buttons { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }
        .interval-btn { padding: 8px 10px; border: 2px solid #e0e0e0; border-radius: 5px; background: white; cursor: pointer; transition: all 0.3s; font-size: 14px; }
        .interval-btn:hover { border-color: #3498db; }
        .interval-btn.active { border-color: #27ae60; background: #e8f5e8; color: #27ae60; font-weight: bold; }
        
        #position-size-input { padding: 8px; border: 2px solid #e0e0e0; border-radius: 5px; font-size: 16px; }
        #position-size-input:focus { border-color: #3498db; outline: none; }
        
        .toggle-btn { padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; transition: all 0.3s; }
        .toggle-btn.active { background: #27ae60; color: white; }
        .toggle-btn.inactive { background: #e74c3c; color: white; }
        
        .timer { font-size: 18px; font-weight: bold; color: #3498db; padding: 8px; background: #f8f9fa; border-radius: 5px; text-align: center; }
        #today-buys { font-size: 16px; font-weight: bold; color: #27ae60; padding: 8px; background: #f8f9fa; border-radius: 5px; text-align: center; }
        
        .reset-btn { padding: 8px 16px; background: #f39c12; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; margin: 5px; }
        .reset-btn:hover { background: #e67e22; }
        
        .close-btn { padding: 8px 16px; background: #e74c3c; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; margin: 5px; }
        .close-btn:hover { background: #c0392b; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
    <h1>🚀 Trading Bot Dashboard</h1>
            <p>Multi-Strategy Trading System</p>
        </div>

        <div class="metrics">
            <div class="metric">
                <h3>Account Balance</h3>
                <div id="account-balance" class="profit">$999.00</div>
            </div>
            <div class="metric">
                <h3>DCA Budget</h3>
                <div id="dca-budget" class="profit">$100.00</div>
            </div>
            <div class="metric">
                <h3>DCA Spent</h3>
                <div id="dca-spent" class="profit">$0.00</div>
            </div>
            <div class="metric">
                <h3>Total PnL</h3>
                <div id="total-pnl" class="profit">$0.00</div>
            </div>
            <div class="metric">
                <h3>Open Positions</h3>
                <div id="positions">0</div>
            </div>
    <div class="metric">
                <h3>Position Size</h3>
                <div id="position-size">$0.00</div>
            </div>
        </div>

        <div class="strategy-section">
            <h2>🎯 Strategy Selection</h2>
            <p>Choose which strategies to run:</p>
            
            <div class="preset-buttons">
                <button class="preset-btn aggressive" onclick="selectPreset('aggressive')">Aggressive</button>
                <button class="preset-btn conservative" onclick="selectPreset('conservative')">Conservative</button>
                <button class="preset-btn all" onclick="selectPreset('all')">All Strategies</button>
                <button class="preset-btn custom" onclick="selectPreset('custom')">Custom</button>
            </div>

            <div class="strategy-grid">
                <div class="strategy-item" onclick="toggleStrategy('rsi')">
                    <input type="checkbox" id="rsi" onchange="updateStrategies()">
                    <label for="rsi">RSI Strategy</label>
                </div>
                <div class="strategy-item" onclick="toggleStrategy('mean_reversion')">
                    <input type="checkbox" id="mean_reversion" onchange="updateStrategies()">
                    <label for="mean_reversion">Mean Reversion</label>
                </div>
                <div class="strategy-item" onclick="toggleStrategy('bollinger_bands')">
                    <input type="checkbox" id="bollinger_bands" onchange="updateStrategies()">
                    <label for="bollinger_bands">Bollinger Bands</label>
                </div>
                <div class="strategy-item" onclick="toggleStrategy('macd')">
                    <input type="checkbox" id="macd" onchange="updateStrategies()">
                    <label for="macd">MACD</label>
                </div>
                <div class="strategy-item" onclick="toggleStrategy('moving_average')">
                    <input type="checkbox" id="moving_average" onchange="updateStrategies()">
                    <label for="moving_average">Moving Average</label>
                </div>
                <div class="strategy-item" onclick="toggleStrategy('momentum')">
                    <input type="checkbox" id="momentum" onchange="updateStrategies()">
                    <label for="momentum">Momentum</label>
                </div>
                <div class="strategy-item" onclick="toggleStrategy('dca')">
                    <input type="checkbox" id="dca" onchange="updateStrategies()">
                    <label for="dca">DCA Strategy</label>
                </div>
            </div>

            <div class="status running">
                <strong>Status:</strong> <span id="status">Running</span>
            </div>
        </div>

        <div class="strategy-section">
            <h2>🎛️ DCA Strategy Controls</h2>
            <div class="dca-controls">
                <div class="control-group">
                    <label>Buy Interval:</label>
                    <div class="interval-buttons">
                        <button class="interval-btn" onclick="setDCAInterval(0.25)">15sec</button>
                        <button class="interval-btn" onclick="setDCAInterval(0.5)">30sec</button>
                        <button class="interval-btn" onclick="setDCAInterval(1)">1min</button>
                        <button class="interval-btn" onclick="setDCAInterval(2)">2min</button>
                        <button class="interval-btn" onclick="setDCAInterval(5)">5min</button>
                        <button class="interval-btn" onclick="setDCAInterval(15)">15min</button>
                        <button class="interval-btn active" onclick="setDCAInterval(30)">30min</button>
                    </div>
                </div>
                
                <div class="control-group">
                    <label>Position Size ($):</label>
                    <input type="number" id="position-size-input" value="50" step="5" min="5" max="1000" onchange="updatePositionSize()">
                </div>
                <div class="control-group">
                    <label>DCA Budget ($):</label>
                    <input type="number" id="dca-budget-input" value="100" step="10" min="10" max="1000" onchange="updateDCABudget()">
    </div>
    
                <div class="control-group">
                    <label>DCA Status:</label>
                    <button id="dca-toggle" class="toggle-btn active" onclick="toggleDCA()">● Active</button>
    </div>
    
                <div class="control-group">
                    <label>Next Buy In:</label>
                    <div id="next-buy-timer" class="timer">--:--</div>
    </div>
    
                <div class="control-group">
                    <label>Today's Buys:</label>
                    <div id="today-buys">0</div>
    </div>
    
                <div class="control-group">
                    <label>Current Timer:</label>
                    <div id="current-timer" class="timer">00:00</div>
    </div>
    
                <div class="control-group">
                    <button class="reset-btn" onclick="resetDCA()">Reset Timer</button>
                    <button class="close-btn" onclick="closeAllPositions()">Close All Positions</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        
        // Strategy presets
        const presets = {
            aggressive: ['mean_reversion', 'rsi', 'bollinger_bands'],
            conservative: ['macd', 'moving_average', 'dca'],
            all: ['rsi', 'mean_reversion', 'bollinger_bands', 'macd', 'moving_average', 'momentum', 'dca'],
            custom: []
        };

        function selectPreset(presetName) {
            // Clear all checkboxes
            document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
            
            // Check selected strategies
            if (presetName !== 'custom') {
                presets[presetName].forEach(strategy => {
                    document.getElementById(strategy).checked = true;
                });
            }
            
            updateStrategies();
        }

        function toggleStrategy(strategy) {
            const checkbox = document.getElementById(strategy);
            checkbox.checked = !checkbox.checked;
            updateStrategies();
        }

        function updateStrategies() {
            const selected = [];
            document.querySelectorAll('input[type="checkbox"]:checked').forEach(cb => {
                selected.push(cb.id);
            });
            
            // Send strategy update to server
            socket.emit('update_strategies', { strategies: selected });
            
            // Update visual state
            document.querySelectorAll('.strategy-item').forEach(item => {
                const checkbox = item.querySelector('input[type="checkbox"]');
                if (checkbox && checkbox.checked) {
                    item.classList.add('active');
                } else if (checkbox) {
                    item.classList.remove('active');
                }
            });
        }
        
        socket.on('status_update', function(data) {
            // Update current ETH price (extract from portfolio data if available)
            if (data.portfolio && data.portfolio.positions && data.portfolio.positions.length > 0) {
                // Use the entry price of the first position as current ETH price estimate
                currentETHPrice = parseFloat(data.portfolio.positions[0].entry_price || 4500);
            }
            
            // Update balance information
            if (data.balance) {
                const accountBalanceEl = document.getElementById('account-balance');
                const totalPnlEl = document.getElementById('total-pnl');
                if (accountBalanceEl) accountBalanceEl.textContent = `$${data.balance.current.toFixed(2)}`;
                if (totalPnlEl) totalPnlEl.textContent = `$${data.balance.pnl.toFixed(2)}`;
            }
            
            // Update DCA budget information
            if (data.dca) {
                const dcaBudgetEl = document.getElementById('dca-budget');
                const dcaSpentEl = document.getElementById('dca-spent');
                const todayBuysEl = document.getElementById('today-buys');
                if (dcaBudgetEl) dcaBudgetEl.textContent = `$${data.dca.budget.toFixed(2)}`;
                if (dcaSpentEl) dcaSpentEl.textContent = `$${data.dca.spent.toFixed(2)}`;
                if (todayBuysEl) todayBuysEl.textContent = data.dca.today_buys || 0;
            }
            const dailyPnlEl = document.getElementById('daily-pnl');
            const positionsEl = document.getElementById('positions');
            if (dailyPnlEl) dailyPnlEl.textContent = '$' + data.portfolio.daily_pnl.toFixed(2);
            if (positionsEl) positionsEl.textContent = data.portfolio.total_positions;
            
            // Calculate and display total position size in dollars
            let totalSizeETH = 0;
            let totalSizeDollars = 0;
            if (data.portfolio.positions && data.portfolio.positions.length > 0) {
                data.portfolio.positions.forEach(position => {
                    const sizeETH = parseFloat(position.size || 0);
                    const entryPrice = parseFloat(position.entry_price || 4500); // Use entry price or current ETH price
                    totalSizeETH += sizeETH;
                    totalSizeDollars += sizeETH * entryPrice;
                });
            }
            const positionSizeEl = document.getElementById('position-size');
            if (positionSizeEl) positionSizeEl.textContent = '$' + totalSizeDollars.toFixed(2);
            
            // Update colors
            const totalPnlColorEl = document.getElementById('total-pnl');
            const dailyPnlColorEl = document.getElementById('daily-pnl');
            
            if (totalPnlColorEl) totalPnlColorEl.className = data.portfolio.total_unrealized_pnl >= 0 ? 'profit' : 'loss';
            if (dailyPnlColorEl) dailyPnlColorEl.className = data.portfolio.daily_pnl >= 0 ? 'profit' : 'loss';
        });
        
        socket.on('connect', function() {
            console.log('Connected to dashboard');
            // Start with no strategies selected
            selectPreset('custom');
            
            // Initialize DCA controls
            initializeDCA();
            
            // Start simple timer immediately
            startSimpleTimer();
        });
        
        function startSimpleTimer() {
            // Simple working timer
            setInterval(function() {
                try {
                    const now = new Date();
                    
                    // Update current timer (time since page load)
                    if (window.startTime) {
                        const timeSinceStart = Math.floor((now - window.startTime) / 1000);
                        const minutes = Math.floor(timeSinceStart / 60);
                        const seconds = timeSinceStart % 60;
                        const currentTimerEl = document.getElementById('current-timer');
                        if (currentTimerEl) {
                            currentTimerEl.textContent = 
                                minutes.toString().padStart(2, '0') + ':' + seconds.toString().padStart(2, '0');
                        }
                    }
                    
                    // Update next buy timer (use selected interval)
                    if (window.startTime) {
                        const timeSinceStart = Math.floor((now - window.startTime) / 1000);
                        const intervalSeconds = dcaSettings.interval * 60; // Convert minutes to seconds
                        const timeLeft = Math.max(0, intervalSeconds - (timeSinceStart % intervalSeconds));
                        const buyMinutes = Math.floor(timeLeft / 60);
                        const buySeconds = timeLeft % 60;
                        const nextBuyTimerEl = document.getElementById('next-buy-timer');
                        if (nextBuyTimerEl) {
                            nextBuyTimerEl.textContent = 
                                buyMinutes.toString().padStart(2, '0') + ':' + buySeconds.toString().padStart(2, '0');
                        }
                    }
                } catch (error) {
                    console.log('Timer error:', error);
                }
            }, 1000);
        }
        
        // Set start time when page loads
        window.startTime = new Date();
        
        function startAllTimers() {
            // Start current timer (counts up from when DCA was activated)
            setInterval(function() {
                const now = new Date();
                
                if (dcaSettings.isActive && dcaSettings.startTime) {
                    const timeSinceStart = now - new Date(dcaSettings.startTime);
                    const minutes = Math.floor(timeSinceStart / 60000);
                    const seconds = Math.floor((timeSinceStart % 60000) / 1000);
                    const currentTimerEl = document.getElementById('current-timer');
                    if (currentTimerEl) currentTimerEl.textContent = 
                        minutes.toString().padStart(2, '0') + ':' + seconds.toString().padStart(2, '0');
                } else {
                    const currentTimerEl = document.getElementById('current-timer');
                    if (currentTimerEl) currentTimerEl.textContent = '--:--';
                }
            }, 1000);
            
            // Start next buy timer (countdown to next buy)
            setInterval(function() {
                const now = new Date();
                
                if (dcaSettings.isActive && dcaSettings.nextBuyTime) {
                    const timeLeft = dcaSettings.nextBuyTime - now;
                    
                    if (timeLeft > 0) {
                        const minutes = Math.floor(timeLeft / 60000);
                        const seconds = Math.floor((timeLeft % 60000) / 1000);
                        const nextBuyTimerEl = document.getElementById('next-buy-timer');
                        if (nextBuyTimerEl) nextBuyTimerEl.textContent = 
                            minutes.toString().padStart(2, '0') + ':' + seconds.toString().padStart(2, '0');
                    } else {
                        const nextBuyTimerEl = document.getElementById('next-buy-timer');
                        if (nextBuyTimerEl) nextBuyTimerEl.textContent = 'BUY NOW!';
                        dcaSettings.nextBuyTime = new Date(now.getTime() + dcaSettings.interval * 60000);
                    }
                } else {
                    const nextBuyTimerEl = document.getElementById('next-buy-timer');
                    if (nextBuyTimerEl) nextBuyTimerEl.textContent = '--:--';
                }
            }, 1000);
        }

        // Global variables
        let currentETHPrice = 4500; // Will be updated with real price
        
        // DCA Control Functions
        let dcaSettings = {
            interval: 30, // minutes
            positionSize: 0.011, // ETH amount (calculated from $50)
            positionSizeDollars: 50, // Dollar amount for display
            isActive: true,
            nextBuyTime: null,
            lastBuyTime: null,
            startTime: null, // When DCA was activated
            todayBuys: 0
        };

        function initializeDCA() {
            // Set start time when DCA is first activated
            if (!dcaSettings.startTime) {
                dcaSettings.startTime = new Date();
            }
            updateNextBuyTime();
        }

        function setDCAInterval(minutes) {
            dcaSettings.interval = minutes;
            
            // Update button states
            document.querySelectorAll('.interval-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            // Update next buy time
            updateNextBuyTime();
            
            // Send update to server
            socket.emit('update_dca_settings', dcaSettings);
        }

        function updatePositionSize() {
            const input = document.getElementById('position-size-input');
            const dollarAmount = parseFloat(input.value);
            
            // Store dollar amount for display
            dcaSettings.positionSizeDollars = dollarAmount;
            
            // Convert to ETH amount for bot using current ETH price
            const ethAmount = dollarAmount / currentETHPrice;
            dcaSettings.positionSize = ethAmount;
            
            console.log(`Position size: $${dollarAmount} = ${ethAmount.toFixed(6)} ETH (ETH Price: $${currentETHPrice})`);
            
            // Send update to server
            socket.emit('update_dca_settings', dcaSettings);
        }
        
        function updateDCABudget() {
            const input = document.getElementById('dca-budget-input');
            const budget = parseFloat(input.value);
            
            // Send update to server
            socket.emit('update_dca_budget', budget);
        }

        function toggleDCA() {
            dcaSettings.isActive = !dcaSettings.isActive;
            const toggle = document.getElementById('dca-toggle');
            
            if (dcaSettings.isActive) {
                toggle.textContent = '● Active';
                toggle.className = 'toggle-btn active';
                // Set start time when DCA is activated
                if (!dcaSettings.startTime) {
                    dcaSettings.startTime = new Date();
                }
            } else {
                toggle.textContent = '● Inactive';
                toggle.className = 'toggle-btn inactive';
            }
            
            // Send update to server
            socket.emit('update_dca_settings', dcaSettings);
        }

        function resetDCA() {
            // Reset the dashboard timers
            dcaSettings.startTime = new Date(); // Reset current timer
            dcaSettings.nextBuyTime = new Date(Date.now() + dcaSettings.interval * 60000); // Reset next buy timer
            
            // Update display immediately
            const currentTimerEl = document.getElementById('current-timer');
            if (currentTimerEl) currentTimerEl.textContent = '00:00';
            
            const nextBuyTimerEl = document.getElementById('next-buy-timer');
            if (nextBuyTimerEl) nextBuyTimerEl.textContent = '00:01'; // Show 1 second for immediate feedback
            
            console.log('DCA timer reset - dashboard updated');
            
            // Send update to server
            socket.emit('reset_dca_timer');
        }

        function updateNextBuyTime() {
            if (!dcaSettings.nextBuyTime) {
                dcaSettings.nextBuyTime = new Date(Date.now() + dcaSettings.interval * 60000);
            }
        }

        function startTimer() {
            setInterval(function() {
                const now = new Date();
                
                // Next Buy Timer - Shows countdown to next buy
                if (dcaSettings.isActive && dcaSettings.nextBuyTime) {
                    const timeLeft = dcaSettings.nextBuyTime - now;
                    
                    if (timeLeft > 0) {
                        const minutes = Math.floor(timeLeft / 60000);
                        const seconds = Math.floor((timeLeft % 60000) / 1000);
                        const nextBuyTimerEl = document.getElementById('next-buy-timer');
                        if (nextBuyTimerEl) nextBuyTimerEl.textContent = 
                            minutes.toString().padStart(2, '0') + ':' + seconds.toString().padStart(2, '0');
                    } else {
                        // Time for next buy
                        const nextBuyTimerEl = document.getElementById('next-buy-timer');
                        if (nextBuyTimerEl) nextBuyTimerEl.textContent = 'BUY NOW!';
                        dcaSettings.nextBuyTime = new Date(now.getTime() + dcaSettings.interval * 60000);
                    }
                } else {
                    const nextBuyTimerEl = document.getElementById('next-buy-timer');
                    if (nextBuyTimerEl) nextBuyTimerEl.textContent = '--:--';
                }
            }, 1000);
        }

        function closeAllPositions() {
            if (confirm('Are you sure you want to close all DCA positions?')) {
                socket.emit('close_all_positions');
            }
        }

        // Listen for DCA updates from server
        socket.on('dca_updated', function(data) {
            dcaSettings.todayBuys = data.todayBuys || 0;
            dcaSettings.lastBuyTime = data.lastBuyTime || null;
            const todayBuysEl = document.getElementById('today-buys');
            if (todayBuysEl) todayBuysEl.textContent = dcaSettings.todayBuys;
        });
    </script>
</body>
</html>
    ''')

@socketio.on('connect')
def handle_connect(auth=None):
    print('Client connected')
    if bot:
        try:
            status = bot.get_status()
            
            # Create a simple status object with only JSON-serializable data
            simple_status = {
                'portfolio': {
                    'total_unrealized_pnl': status['portfolio']['total_unrealized_pnl'],
                    'daily_pnl': status['portfolio']['daily_pnl'],
                    'total_positions': status['portfolio']['total_positions']
                }
            }
            
            emit('status_update', simple_status)
        except Exception as e:
            print(f"Error sending initial status: {e}")

@socketio.on('update_strategies')
def handle_strategy_update(data):
    global bot
    strategies = data.get('strategies', [])
    print(f'Updating strategies to: {strategies}')
    
    if bot:
        # Update bot strategies
        bot.update_strategies(strategies)
        emit('strategies_updated', {'strategies': strategies})

@socketio.on('update_dca_settings')
def handle_dca_update(data):
    global bot
    print(f'Updating DCA settings: {data}')
    
    if bot and 'dca' in bot.strategies:
        # Update DCA strategy parameters
        dca_strategy = bot.strategies['dca']
        
        # Debug: show current values before update
        old_interval = dca_strategy.get_parameter('interval_minutes')
        print(f'DCA Before Update - Interval: {old_interval} min')
        
        # Convert interval from minutes to the parameter the strategy expects
        dca_strategy.set_parameter('interval_minutes', data['interval'])
        dca_strategy.set_parameter('position_size', data['positionSize'])
        dca_strategy.is_active = data['isActive']
        
        # Debug: show values after update
        new_interval = dca_strategy.get_parameter('interval_minutes')
        print(f'DCA After Update - Interval: {new_interval} min')
        
        # Also update the strategy's internal state
        dca_strategy.last_buy_time = None  # Reset timer when settings change
        print(f'DCA Strategy updated - Interval: {data["interval"]} min, Size: {data["positionSize"]}, Active: {data["isActive"]}')
        
        emit('dca_updated', {
            'todayBuys': getattr(dca_strategy, 'today_buys', 0),
            'lastBuyTime': dca_strategy.last_buy_time.isoformat() if dca_strategy.last_buy_time else None
        })

@socketio.on('update_dca_budget')
def handle_dca_budget_update(budget):
    global bot
    print(f'Updating DCA budget to: ${budget}')
    
    if bot:
        old_budget = bot.dca_budget
        bot.update_dca_budget(budget)
        print(f'DCA budget changed from ${old_budget} to ${bot.dca_budget}')
        emit('dca_budget_updated', {'budget': budget})

@socketio.on('reset_dca_timer')
def handle_dca_reset():
    global bot
    print('Resetting DCA timer')
    
    if bot and 'dca' in bot.strategies:
        dca_strategy = bot.strategies['dca']
        dca_strategy.last_buy_time = None
        print('DCA timer reset - next buy will be immediate')
        emit('dca_updated', {
            'todayBuys': getattr(dca_strategy, 'today_buys', 0),
            'lastBuyTime': None
        })

@socketio.on('close_all_positions')
def handle_close_all_positions():
    global bot
    print('Closing all positions')
    
    if bot:
        # Clear all positions from risk manager
        bot.risk_manager.positions.clear()
        bot.risk_manager.daily_pnl = 0
        emit('positions_closed', {'message': 'All positions closed'})

def collect_data():
    global running
    while running:
        try:
            if bot:
                status = bot.get_status()
                
                # Convert datetime objects to strings for JSON serialization
                if 'last_update' in status and status['last_update']:
                    status['last_update'] = status['last_update'].isoformat()
                
                # Convert position datetime objects
                if 'portfolio' in status and 'positions' in status['portfolio']:
                    for position in status['portfolio']['positions']:
                        if 'entry_time' in position and position['entry_time']:
                            position['entry_time'] = position['entry_time'].isoformat()
                
                socketio.emit('status_update', status)
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(5)
        
def run_bot():
    global bot
    strategies = ["rsi", "bollinger_bands", "macd"]
    bot = MultiStrategyBot(strategies)
    asyncio.run(bot.start())

if __name__ == "__main__":
    print("Starting Simple Trading Dashboard...")
    
    # Start bot in separate thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start data collection
    running = True
    data_thread = threading.Thread(target=collect_data)
    data_thread.daemon = True
    data_thread.start()
    
    # Run dashboard
    print("Dashboard available at: http://localhost:5001")
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)