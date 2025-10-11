"""Main Wormrider application - Wall Trap Strategy with Charts."""

import threading
import time
from dash import Dash, Input, Output, html, dcc
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
    print(f"[TRADE] {trade['symbol']} @ ${trade['price']} - {'BUY' if trade['is_buy'] else 'SELL'} {trade['quantity']}")
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
        html.H1("wormrider - BTCUSDT", style={'margin': '10px', 'color': '#e5e7eb', 'flex': '1'}),
        html.Div(id='status-text', children='Auto-refresh: 5s', 
                style={'margin': '10px', 'color': '#9ca3af', 'fontSize': '12px'}),
    ], style={'background': '#1f2937', 'padding': '10px', 'borderRadius': '8px', 'marginBottom': '10px', 'display': 'flex', 'alignItems': 'center'}),
    
    # Row 1: Charts
    html.Div([
        html.Div([
            html.H3("Price Chart (5min)", style={'color': '#e5e7eb', 'fontSize': '14px', 'marginBottom': '5px'}),
            dcc.Graph(id='price-chart', config={'displayModeBar': False}, style={'height': '300px'})
        ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1', 'marginRight': '5px'}),
        
        html.Div([
            html.H3("CVD Chart (1hour)", style={'color': '#e5e7eb', 'fontSize': '14px', 'marginBottom': '5px'}),
            dcc.Graph(id='cvd-chart', config={'displayModeBar': False}, style={'height': '300px'})
        ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1', 'marginLeft': '5px'}),
    ], style={'display': 'flex', 'marginBottom': '10px'}),
    
    # Row 2: Info Panels
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
    
    # Auto-refresh interval
    dcc.Interval(
        id='interval-component',
        interval=5000,  # 5 seconds
        n_intervals=0
    )
], style={'padding': '20px', 'background': '#0b0f16', 'minHeight': '100vh'})


@app.callback(
    [Output('price-chart', 'figure'),
     Output('cvd-chart', 'figure'),
     Output('walls-info', 'children'),
     Output('alerts-info', 'children'),
     Output('status-text', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n_intervals):
    """Update all dashboard components."""
    
    # Get latest snapshot
    snapshot = db.get_latest_snapshot("BTCUSDT")
    
    if not snapshot:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#0f172a',
            plot_bgcolor='#0f172a',
            xaxis_title="Time",
            yaxis_title="Value"
        )
        return empty_fig, empty_fig, "No data yet", "No alerts yet", "Waiting for data..."
    
    # 1. Price Chart - Last 5 minutes
    current_time = int(time.time() * 1000)
    five_min_ago = current_time - (5 * 60 * 1000)
    historical_data = db.get_snapshots_range("BTCUSDT", five_min_ago, current_time)
    
    price_fig = go.Figure()
    if historical_data:
        timestamps = [dt.fromtimestamp(d['timestamp'] / 1000) for d in historical_data]
        prices = [d['mid_price'] for d in historical_data]
        
        price_fig.add_trace(go.Scatter(
            x=timestamps,
            y=prices,
            mode='lines',
            name='Price',
            line=dict(color='#0ea5e9', width=2)
        ))
    
    price_fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0f172a',
        plot_bgcolor='#0f172a',
        showlegend=False,
        margin=dict(l=50, r=20, t=20, b=40),
        xaxis_title="Time",
        yaxis_title="Price (USD)",
        hovermode='x unified'
    )
    
    # 2. Detect Liquidity Walls
    walls_data = liquidity_walls.detect_liquidity_walls(
        bids=snapshot['bids'],
        asks=snapshot['asks'],
        mid_price=snapshot['mid_price']
    )
    
    # Add wall lines to price chart
    for wall in walls_data['bid_walls'][:3]:  # Top 3 bid walls
        price_fig.add_hline(
            y=wall['price'],
            line_dash="dash",
            line_color="#16a34a",
            line_width=1,
            annotation_text=f"BID {wall['size']:.1f}",
            annotation_position="right"
        )
    
    for wall in walls_data['ask_walls'][:3]:  # Top 3 ask walls
        price_fig.add_hline(
            y=wall['price'],
            line_dash="dash",
            line_color="#ef4444",
            line_width=1,
            annotation_text=f"ASK {wall['size']:.1f}",
            annotation_position="right"
        )
    
    # Walls info panel
    walls_html = []
    walls_html.append(html.P(f"📊 Total: {walls_data['total_walls']} walls", style={'fontWeight': 'bold'}))
    
    if walls_data['strongest_bid_wall']:
        wall = walls_data['strongest_bid_wall']
        walls_html.append(html.P(
            f"🟢 BID: ${wall['price']:,.2f} ({wall['size']:.1f} BTC) - {wall['asymmetry_ratio']:.1f}x",
            style={'color': '#16a34a'}
        ))
    
    if walls_data['strongest_ask_wall']:
        wall = walls_data['strongest_ask_wall']
        walls_html.append(html.P(
            f"🔴 ASK: ${wall['price']:,.2f} ({wall['size']:.1f} BTC) - {wall['asymmetry_ratio']:.1f}x",
            style={'color': '#ef4444'}
        ))
    
    # 3. CVD Chart - Last 1 hour
    one_hour_ago = current_time - (60 * 60 * 1000)
    recent_trades = db.get_trades_range("btcusdt", one_hour_ago, current_time)
    
    cvd_fig = go.Figure()
    if recent_trades:
        cvd_data = cvd.get_cvd_summary(recent_trades, window_minutes=60)
        
        if cvd_data['cvd_series']:
            timestamps = [dt.fromtimestamp(point['timestamp'] / 1000) for point in cvd_data['cvd_series']]
            cvd_values = [point['cvd'] for point in cvd_data['cvd_series']]
            
            cvd_fig.add_trace(go.Scatter(
                x=timestamps,
                y=cvd_values,
                mode='lines',
                name='CVD',
                line=dict(color='#f59e0b', width=2),
                fill='tonexty',
                fillcolor='rgba(245, 158, 11, 0.1)'
            ))
            
            # Detect CVD trend segments
            segments = cvd.detect_cvd_trend_segments(cvd_data['cvd_series'], min_segment_size=10, slope_threshold=0.05)
            
            # Draw trendlines for each segment
            if segments:
                for segment in segments:
                    segment_start_dt = dt.fromtimestamp(segment['start_time'] / 1000)
                    segment_end_dt = dt.fromtimestamp(segment['end_time'] / 1000)
                    
                    # Color based on direction
                    if segment['direction'] == 'upward':
                        line_color = '#16a34a'  # Green
                    elif segment['direction'] == 'downward':
                        line_color = '#ef4444'  # Red
                    else:
                        line_color = '#9ca3af'  # Gray
                    
                    # Draw trendline
                    cvd_fig.add_trace(go.Scatter(
                        x=[segment_start_dt, segment_end_dt],
                        y=[segment['start_cvd'], segment['end_cvd']],
                        mode='lines',
                        name=segment['direction'].capitalize(),
                        line=dict(color=line_color, width=3, dash='solid'),
                        showlegend=False,
                        opacity=0.8
                    ))
                
                # Get current segment status
                current_segment = segments[-1]
                current_status = current_segment['direction']
                
                # Print current status
                status_emoji = "📈" if current_status == 'upward' else "📉" if current_status == 'downward' else "↔️"
                print(f"{status_emoji} [CVD SEGMENT] {current_status.upper()} | Slope: {current_segment['slope']:.4f} | CVD: {cvd_data['current_cvd']:.2f}")
            else:
                current_status = 'neutral'
                print(f"[CVD] Not enough data for segmentation")
        else:
            current_status = 'neutral'
    else:
        current_status = 'neutral'
    
    cvd_fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0f172a',
        plot_bgcolor='#0f172a',
        showlegend=False,
        margin=dict(l=50, r=20, t=20, b=40),
        xaxis_title="Time",
        yaxis_title="CVD",
        hovermode='x unified'
    )
    
    # 4. Check for Wall Trap Setup
    if recent_trades:
        setup_alert = wall_trap.detect_wall_trap_setup(
            orderbook_data=snapshot,
            trades_data=recent_trades,
            current_price=snapshot['mid_price']
        )
        
        if setup_alert:
            manager.process_alert(setup_alert)
    
    # 5. Alerts Panel with CVD Status
    alerts_html = []
    
    # Current CVD Trend Status (Top of panel)
    status_color = '#16a34a' if current_status == 'upward' else '#ef4444' if current_status == 'downward' else '#9ca3af'
    status_text = "TRENDING UP 📈" if current_status == 'upward' else "TRENDING DOWN 📉" if current_status == 'downward' else "RANGING ↔️"
    
    alerts_html.append(html.Div([
        html.P("CVD Status:", style={'fontSize': '11px', 'color': '#9ca3af', 'marginBottom': '5px'}),
        html.P(status_text, style={'color': status_color, 'fontWeight': 'bold', 'fontSize': '14px'}),
    ], style={'padding': '8px', 'background': '#1f2937', 'borderRadius': '5px', 'marginBottom': '10px'}))
    
    # Wall Trap Alerts
    alerts = manager.get_recent_alerts(limit=3)
    
    if alerts:
        alerts_html.append(html.P("Wall Trap Alerts:", 
                                  style={'fontSize': '11px', 'color': '#9ca3af', 'marginBottom': '5px'}))
        for alert in alerts:
            timestamp = dt.fromtimestamp(alert['timestamp'] / 1000).strftime('%H:%M:%S')
            direction_color = '#16a34a' if alert['direction'] == 'long' else '#ef4444'
            
            alerts_html.append(html.Div([
                html.Span(f"[{timestamp}] ", style={'color': '#9ca3af', 'fontSize': '10px'}),
                html.Span(f"{alert['direction'].upper()}", 
                         style={'color': direction_color, 'fontWeight': 'bold', 'fontSize': '11px'}),
                html.Span(f" @ ${alert['wall_price']:,.2f}", style={'color': '#e5e7eb', 'fontSize': '10px'})
            ], style={'marginBottom': '2px', 'padding': '3px'}))
    
    alerts_display = html.Div(alerts_html)
    
    # Status text
    status = f"💰 ${snapshot['mid_price']:,.2f} | 🔄 Auto-refresh: 5s | 📊 {len(recent_trades) if recent_trades else 0} trades"
    
    return price_fig, cvd_fig, html.Div(walls_html), alerts_display, status


if __name__ == '__main__':
    print("Starting Wormrider on http://127.0.0.1:8050")
    app.run(host='127.0.0.1', port=8050, debug=True)