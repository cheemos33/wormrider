"""
Real-time trading dashboard for the Hyperliquid trading bot.
"""
import asyncio
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
import pandas as pd
import plotly.graph_objs as go
import plotly.utils
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import dash
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc

from multi_strategy_bot import MultiStrategyBot
from config import get_config

class TradingDashboard:
    """Real-time trading dashboard."""
    
    def __init__(self, bot: MultiStrategyBot):
        self.bot = bot
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'trading_bot_secret'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Data storage
        self.price_data = []
        self.trade_data = []
        self.performance_data = []
        self.running = False
        
        # Setup routes
        self.setup_routes()
        self.setup_socket_events()
        
    def setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            return render_template('dashboard.html')
        
        @self.app.route('/api/status')
        def get_status():
            return jsonify(self.bot.get_status())
        
        @self.app.route('/api/price_data')
        def get_price_data():
            return jsonify(self.price_data[-100:])  # Last 100 data points
        
        @self.app.route('/api/trade_data')
        def get_trade_data():
            return jsonify(self.trade_data)
        
        @self.app.route('/api/performance')
        def get_performance():
            return jsonify(self.performance_data)
    
    def setup_socket_events(self):
        """Setup WebSocket events."""
        
        @self.socketio.on('connect')
        def handle_connect():
            print('Client connected')
            emit('status', self.bot.get_status())
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            print('Client disconnected')
    
    def start_data_collection(self):
        """Start collecting data for the dashboard."""
        self.running = True
        
def collect_data():
    while self.running:
        try:
            # Get current bot status
            status = self.bot.get_status()
            
            # Collect price data (with error handling)
            price_point = None
            if hasattr(self.bot, 'last_price') and self.bot.last_price:
                price_point = {
                    'timestamp': datetime.now().isoformat(),
                    'price': self.bot.last_price,
                    'balance': status['portfolio']['total_unrealized_pnl']
                }
                self.price_data.append(price_point)
                
                # Keep only last 1000 data points
                if len(self.price_data) > 1000:
                    self.price_data = self.price_data[-1000:]
            
            # Collect performance data
            performance_point = {
                'timestamp': datetime.now().isoformat(),
                'total_pnl': status['portfolio']['total_unrealized_pnl'],
                'daily_pnl': status['portfolio']['daily_pnl'],
                'positions': len(status['portfolio']['positions'])
            }
            self.performance_data.append(performance_point)
            
            # Keep only last 1000 data points
            if len(self.performance_data) > 1000:
                self.performance_data = self.performance_data[-1000:]
            
            # Emit real-time updates (only if price_point exists)
            if price_point:
                self.socketio.emit('price_update', price_point)
            self.socketio.emit('performance_update', performance_point)
            self.socketio.emit('status_update', status)
            
        except Exception as e:
            print(f"Error collecting data: {e}")
        
        time.sleep(5)  # Update every 5 seconds
        
        time.sleep(5)  # Update every 5 seconds        
        # Start data collection in a separate thread
        self.data_thread = threading.Thread(target=collect_data)
        self.data_thread.daemon = True
        self.data_thread.start()
    
def stop_data_collection(self):
        """Stop data collection."""
        self.running = False
    
def run(self, host='0.0.0.0', port=5001, debug=False):
        """Run the dashboard."""
        print(f"Starting dashboard at http://{host}:{port}")
        self.start_data_collection()
        self.socketio.run(self.app, host=host, port=port, debug=debug)

# Create Dash app for advanced charts
def create_dash_app(dashboard: TradingDashboard):
    """Create a Dash app for advanced charts."""
    
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
    
    app.layout = dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H1("Trading Bot Dashboard", className="text-center mb-4"),
                dbc.Card([
                    dbc.CardBody([
                        html.H4("Real-time Performance", className="card-title"),
                        dcc.Graph(id='performance-chart'),
                        dcc.Interval(
                            id='interval-component',
                            interval=5*1000,  # Update every 5 seconds
                            n_intervals=0
                        )
                    ])
                ])
            ], width=12)
        ])
    ])
    
    @app.callback(
        Output('performance-chart', 'figure'),
        Input('interval-component', 'n_intervals')
    )
    def update_performance_chart(n):
        """Update the performance chart."""
        if not dashboard.performance_data:
            return go.Figure()
        
        df = pd.DataFrame(dashboard.performance_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['total_pnl'],
            mode='lines',
            name='Total PnL',
            line=dict(color='green' if df['total_pnl'].iloc[-1] >= 0 else 'red')
        ))
        
        fig.update_layout(
            title="Portfolio Performance",
            xaxis_title="Time",
            yaxis_title="PnL ($)",
            hovermode='x unified'
        )
        
        return fig
    
    return app

# Main dashboard launcher
def run_dashboard():
    """Run the trading dashboard."""
    print("Starting Trading Bot Dashboard...")
    
    # Initialize the bot
    strategies = ["rsi", "bollinger_bands", "macd"]
    bot = MultiStrategyBot(strategies)
    
    # Create dashboard
    dashboard = TradingDashboard(bot)
    
    # Start bot in a separate thread
    def run_bot():
        asyncio.run(bot.start())
    
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Run dashboard
    dashboard.run(debug=True)

if __name__ == "__main__":
    run_dashboard()