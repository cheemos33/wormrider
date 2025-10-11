"""Main Wormrider application - Wall Trap Strategy."""

import threading
import time
from dash import Dash, Input, Output, html
import plotly.graph_objects as go
from datetime import datetime as dt

import config
from database import db
from collectors import binance
from collectors import binance_trades
from indicators import liquidity_walls
from indicators import cvd
from strategy import wall_trap
from alerts import manager

# Initialize database
db.init_db()

# Start background data collection
print("Starting background data collection...")
binance.start_collection(
    symbol="BTCUSDT",
    interval_seconds=config.SAMPLE_INTERVAL_SECONDS,
    callback=db.insert_snapshot
)

# Start trades collection
print("Starting trades collection...")
def on_trade_received(trade):
    db.insert_trade(
        symbol=trade['symbol'],
        timestamp=trade['timestamp'],
        price=trade['price'],
        quantity=trade['quantity'],
        is_buy=trade['is_buy']
    )

binance_trades.start_trades_collection(on_trade_received)

# Start background cleanup
def cleanup_task():
    while True:
        time.sleep(3600)
        db.cleanup_old_data(config.RETENTION_DAYS)

cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
cleanup_thread.start()

# Create Dash app
app = Dash(__name__)
app.title = "Wormrider"

# Layout
app.layout = html.Div([
    html.Div([
        html.H1("wormrider - BTCUSDT", style={'margin': '10px', 'color': '#e5e7eb'}),
    ], style={'background': '#1f2937', 'padding': '10px', 'borderRadius': '8px', 'marginBottom': '10px'}),
    
    html.Div([
        html.Div([
            html.Div([
                html.H3("Price Chart + Walls", style={'color': '#e5e7eb', 'fontSize': '14px'}),
                html.Div(id='price-info', style={'color': '#9ca3af', 'fontSize': '12px', 'marginBottom': '10px'})
            ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1', 'marginRight': '5px'}),
            
            html.Div([
                html.H3("CVD Analysis", style={'color': '#e5e7eb', 'fontSize': '14px'}),
                html.Div(id='cvd-info', style={'color': '#9ca3af', 'fontSize': '12px'})
            ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1', 'marginLeft': '5px'}),
        ], style={'display': 'flex', 'marginBottom': '10px'}),
        
        html.Div([
            html.Div([
                html.H3("Liquidity Walls", style={'color': '#e5e7eb', 'fontSize': '14px'}),
                html.Div(id='walls-info', style={'color': '#9ca3af', 'fontSize': '12px'})
            ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1', 'marginRight': '5px'}),
            
            html.Div([
                html.H3("Alert Log", style={'color': '#e5e7eb', 'fontSize': '14px'}),
                html.Div(id='alerts-info', style={'color': '#9ca3af', 'fontSize': '12px'})
            ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1', 'marginLeft': '5px'}),
        ], style={'display': 'flex'}),
    ]),
    
    html.Div(id='interval-trigger', children=0, style={'display': 'none'}),
    html.Button('⟳ Refresh', id='refresh-button', n_clicks=0, 
                style={'margin': '10px', 'padding': '10px 20px', 'fontSize': '16px', 
                       'background': '#0ea5e9', 'color': 'white', 'border': 'none', 
                       'borderRadius': '5px', 'cursor': 'pointer'})
], style={'padding': '20px', 'background': '#0b0f16', 'minHeight': '100vh'})


@app.callback(
    [Output('price-info', 'children'),
     Output('cvd-info', 'children'),
     Output('walls-info', 'children'),
     Output('alerts-info', 'children'),
     Output('interval-trigger', 'children')],
    [Input('refresh-button', 'n_clicks'),
     Input('interval-trigger', 'children')]
)
def update_dashboard(n_clicks, trigger):
    """Update all dashboard panels."""
    
    # Get latest snapshot
    snapshot = db.get_latest_snapshot("BTCUSDT")
    
    if not snapshot:
        return "No data yet", "No CVD data", "No walls detected", "No alerts yet", trigger + 1
    
    # 1. Price Info
    price_html = html.Div([
        html.P(f"💰 Price: ${snapshot['mid_price']:,.2f}", style={'fontSize': '18px', 'fontWeight': 'bold', 'color': '#0ea5e9'}),
        html.P(f"🕐 Updated: {dt.fromtimestamp(snapshot['timestamp']/1000).strftime('%H:%M:%S')}", 
               style={'fontSize': '12px', 'color': '#9ca3af'})
    ])
    
    # 2. Detect Liquidity Walls
    walls_data = liquidity_walls.detect_liquidity_walls(
        bids=snapshot['bids'],
        asks=snapshot['asks'],
        mid_price=snapshot['mid_price']
    )
    
    walls_html = []
    walls_html.append(html.P(f"📊 Total Walls: {walls_data['total_walls']}", style={'fontWeight': 'bold'}))
    walls_html.append(html.P(f"🟢 Bid Walls: {len(walls_data['bid_walls'])}"))
    walls_html.append(html.P(f"🔴 Ask Walls: {len(walls_data['ask_walls'])}"))
    
    if walls_data['strongest_bid_wall']:
        wall = walls_data['strongest_bid_wall']
        walls_html.append(html.P(
            f"🟢 Strongest BID: ${wall['price']:,.2f} ({wall['size']:.2f} BTC) - Ratio: {wall['asymmetry_ratio']:.2f}x",
            style={'color': '#16a34a', 'fontWeight': 'bold'}
        ))
    
    if walls_data['strongest_ask_wall']:
        wall = walls_data['strongest_ask_wall']
        walls_html.append(html.P(
            f"🔴 Strongest ASK: ${wall['price']:,.2f} ({wall['size']:.2f} BTC) - Ratio: {wall['asymmetry_ratio']:.2f}x",
            style={'color': '#ef4444', 'fontWeight': 'bold'}
        ))
    
    # 3. CVD Analysis
    current_time = int(time.time() * 1000)
    one_hour_ago = current_time - (60 * 60 * 1000)
    recent_trades = db.get_trades_range("btcusdt", one_hour_ago, current_time)
    
    if recent_trades:
        cvd_data = cvd.get_cvd_summary(recent_trades, window_minutes=60)
        
        slope_color = '#16a34a' if cvd_data['slope'] == 'positive' else '#ef4444' if cvd_data['slope'] == 'negative' else '#9ca3af'
        
        cvd_html = html.Div([
            html.P(f"📈 CVD: {cvd_data['current_cvd']:.2f}", style={'fontSize': '16px', 'fontWeight': 'bold'}),
            html.P(f"📊 Slope: {cvd_data['slope'].upper()}", 
                   style={'color': slope_color, 'fontWeight': 'bold'}),
            html.P(f"🟢 Buy Volume: {cvd_data['buy_volume']:.2f}"),
            html.P(f"🔴 Sell Volume: {cvd_data['sell_volume']:.2f}"),
            html.P(f"📝 Trades: {cvd_data['trade_count']}")
        ])
    else:
        cvd_html = html.P("⏳ Collecting trades data...", style={'color': '#f59e0b'})
    
    # 4. Check for Wall Trap Setup
    if recent_trades:
        setup_alert = wall_trap.detect_wall_trap_setup(
            orderbook_data=snapshot,
            trades_data=recent_trades,
            current_price=snapshot['mid_price']
        )
        
        if setup_alert:
            manager.process_alert(setup_alert)
    
    # 5. Get Recent Alerts
    alerts = manager.get_recent_alerts(limit=5)
    
    if alerts:
        alerts_html = []
        for alert in alerts:
            timestamp = dt.fromtimestamp(alert['timestamp'] / 1000).strftime('%H:%M:%S')
            direction_color = '#16a34a' if alert['direction'] == 'long' else '#ef4444'
            
            alerts_html.append(html.Div([
                html.Span(f"[{timestamp}] ", style={'color': '#9ca3af', 'fontSize': '11px'}),
                html.Span(f"🚨 {alert['direction'].upper()}", 
                         style={'color': direction_color, 'fontWeight': 'bold'}),
                html.Span(f" @ ${alert['wall_price']:,.2f}", style={'color': '#e5e7eb'}),
                html.Span(f" (Confidence: {alert['confidence']:.0%})", 
                         style={'color': '#f59e0b', 'fontSize': '11px'})
            ], style={'marginBottom': '5px', 'padding': '5px', 'background': '#1f2937', 'borderRadius': '3px'}))
        
        alerts_display = html.Div(alerts_html)
    else:
        alerts_display = html.P("✅ No alerts yet", style={'color': '#9ca3af'})
    
    return price_html, cvd_html, html.Div(walls_html), alerts_display, trigger + 1


if __name__ == '__main__':
    print("Starting Wormrider on http://127.0.0.1:8050")
    app.run(host='127.0.0.1', port=8050, debug=True)