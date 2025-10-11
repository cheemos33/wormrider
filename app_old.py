"""Main Wormrider application - Dash entry point."""

import threading
import time
from dash import Dash, Input, Output
import plotly.graph_objects as go

import config
from database import db
from collectors import binance
from collectors import binance_trades
from indicators import orderbook
from indicators import cvd
from indicators import liquidity_walls
from strategy import wall_trap
from alerts import manager
from layouts import new_main


# Initialize database
db.init_db()

# Start background data collection
print("Starting background data collection...")
collection_thread = binance.start_collection(
    symbol="BTCUSDT",
    interval_seconds=config.SAMPLE_INTERVAL_SECONDS,
    callback=db.insert_snapshot
)

# Start trades collection
print("Starting trades collection...")
def on_trade_received(trade):
    """Callback for new trade data."""
    db.insert_trade(
        symbol=trade['symbol'],
        timestamp=trade['timestamp'],
        price=trade['price'],
        quantity=trade['quantity'],
        is_buy=trade['is_buy']
    )

binance_trades.start_trades_collection(on_trade_received)

# Start background cleanup task
def cleanup_task():
    """Periodic cleanup of old data."""
    while True:
        time.sleep(3600)  # Every hour
        db.cleanup_old_data(config.RETENTION_DAYS)

cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
cleanup_thread.start()

# Create Dash app
app = Dash(__name__)
app.title = "Wormrider"
app.layout = new_main.create_layout()


def slider_to_bin_size(slider_value):
    """
    Convert logarithmic slider position (0-100) to actual bin size (10-1000 USD).
    
    Logarithmic scale for smooth control:
    - 0-40: 10-50 USD (more precision for small bins)
    - 40-70: 50-200 USD (medium range)
    - 70-100: 200-1000 USD (coarse for large bins)
    """
    import math
    # Exponential mapping: 10 * (10 ^ (slider/50))
    # slider=0 → 10, slider=50 → 100, slider=100 → 1000
    bin_size = 10 * math.pow(10, slider_value / 50)
    
    # Round to nice values
    if bin_size < 50:
        return round(bin_size / 5) * 5  # Round to nearest 5
    elif bin_size < 100:
        return round(bin_size / 10) * 10  # Round to nearest 10
    elif bin_size < 500:
        return round(bin_size / 25) * 25  # Round to nearest 25
    else:
        return round(bin_size / 50) * 50  # Round to nearest 50


@app.callback(
    [Output('price-chart', 'figure'),
     Output('cvd-chart', 'figure'),
     Output('walls-list', 'children'),
     Output('alert-table', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n_intervals):
    """Update dashboard with price chart, CVD chart, walls, and alerts."""
    
    # Fetch latest snapshot
    snapshot = db.get_latest_snapshot("BTCUSDT")
    
    if not snapshot:
        # Return empty figures if no data yet
        empty_fig = go.Figure()
        empty_fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#0f172a',
            plot_bgcolor='#0f172a',
            margin=dict(l=40, r=40, t=40, b=40)
        )
        return empty_fig, empty_fig, "No data yet", "No alerts yet"
    
    # 1. Detect liquidity walls
    walls_data = liquidity_walls.detect_liquidity_walls(
        bids=snapshot['bids'],
        asks=snapshot['asks'],
        mid_price=snapshot['mid_price']
    )
    
    # 2. Get recent trades for CVD
    current_time = int(time.time() * 1000)
    one_hour_ago = current_time - (60 * 60 * 1000)
    recent_trades = db.get_trades_range("btcusdt", one_hour_ago, current_time)
    
    # 3. Calculate CVD
    cvd_data = cvd.get_cvd_summary(recent_trades, window_minutes=60)
    
    # 4. Check for wall trap setup
    setup_alert = wall_trap.detect_wall_trap_setup(
        orderbook_data=snapshot,
        trades_data=recent_trades,
        current_price=snapshot['mid_price']
    )
    
    # 5. Process alert if detected
    if setup_alert:
        manager.process_alert(setup_alert)
    
    # 6. Create price chart with walls
    price_fig = create_price_chart_with_walls(snapshot, walls_data)
    
    # 7. Create CVD chart
    cvd_fig = create_cvd_chart(cvd_data)
    
    # 8. Create walls list
    walls_list = create_walls_list(walls_data)
    
    # 9. Create alert table
    alert_table = create_alert_table()
    
    return price_fig, cvd_fig, walls_list, alert_table


def create_price_chart_with_walls(snapshot, walls_data):
    """Create price chart with wall markers."""
    fig = go.Figure()
    
    # Add price line (5-minute history)
    current_time = int(time.time() * 1000)
    five_min_ago = current_time - (5 * 60 * 1000)
    historical_data = db.get_snapshots_range("BTCUSDT", five_min_ago, current_time)
    
    if historical_data:
        timestamps = [dt.fromtimestamp(d['timestamp'] / 1000) for d in historical_data]
        prices = [d['mid_price'] for d in historical_data]
        
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=prices,
            mode='lines',
            name='Price',
            line=dict(color='#0ea5e9', width=2)
        ))
    
    # Add wall markers
    for wall in walls_data['bid_walls']:
        fig.add_hline(
            y=wall['price'],
            line_dash="dash",
            line_color="green",
            annotation_text=f"BID: ${wall['price']:.2f}",
            annotation_position="bottom right"
        )
    
    for wall in walls_data['ask_walls']:
        fig.add_hline(
            y=wall['price'],
            line_dash="dash", 
            line_color="red",
            annotation_text=f"ASK: ${wall['price']:.2f}",
            annotation_position="top right"
        )
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0f172a',
        plot_bgcolor='#0f172a',
        showlegend=False,
        margin=dict(l=60, r=40, t=20, b=60),
        xaxis=dict(title='Time'),
        yaxis=dict(title='Price (USD)')
    )
    
    return fig


def create_cvd_chart(cvd_data):
    """Create CVD chart with slope indicators."""
    fig = go.Figure()
    
    if cvd_data['cvd_series']:
        timestamps = [dt.fromtimestamp(point['timestamp'] / 1000) for point in cvd_data['cvd_series']]
        cvd_values = [point['cvd'] for point in cvd_data['cvd_series']]
        
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=cvd_values,
            mode='lines',
            name='CVD',
            line=dict(color='#f59e0b', width=2),
            fill='tonexty'
        ))
        
        # Add slope indicator
        slope_color = 'green' if cvd_data['slope'] == 'positive' else 'red' if cvd_data['slope'] == 'negative' else 'gray'
        fig.add_annotation(
            x=timestamps[-1],
            y=cvd_values[-1],
            text=f"Slope: {cvd_data['slope'].upper()}",
            showarrow=True,
            arrowcolor=slope_color,
            font=dict(color=slope_color)
        )
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0f172a',
        plot_bgcolor='#0f172a',
        showlegend=False,
        margin=dict(l=60, r=40, t=20, b=60),
        xaxis=dict(title='Time'),
        yaxis=dict(title='CVD')
    )
    
    return fig


def create_walls_list(walls_data):
    """Create walls list for display."""
    if not walls_data['bid_walls'] and not walls_data['ask_walls']:
        return "No walls detected"
    
    walls_html = []
    
    # Bid walls
    for wall in walls_data['bid_walls'][:3]:  # Show top 3
        walls_html.append(html.Div([
            html.Span(f"BID: ${wall['price']:.2f}", style={'color': 'green', 'fontWeight': 'bold'}),
            html.Span(f" | Size: {wall['size']:.2f}", style={'color': '#e5e7eb'}),
            html.Span(f" | Ratio: {wall['asymmetry_ratio']:.2f}", style={'color': '#9ca3af'})
        ], style={'marginBottom': '5px', 'fontSize': '12px'}))
    
    # Ask walls
    for wall in walls_data['ask_walls'][:3]:  # Show top 3
        walls_html.append(html.Div([
            html.Span(f"ASK: ${wall['price']:.2f}", style={'color': 'red', 'fontWeight': 'bold'}),
            html.Span(f" | Size: {wall['size']:.2f}", style={'color': '#e5e7eb'}),
            html.Span(f" | Ratio: {wall['asymmetry_ratio']:.2f}", style={'color': '#9ca3af'})
        ], style={'marginBottom': '5px', 'fontSize': '12px'}))
    
    return walls_html


def create_alert_table():
    """Create alert table for display."""
    alerts = manager.get_recent_alerts(limit=5)
    
    if not alerts:
        return "No alerts yet"
    
    alert_html = []
    for alert in alerts:
        timestamp = dt.fromtimestamp(alert['timestamp'] / 1000).strftime('%H:%M:%S')
        direction_color = 'green' if alert['direction'] == 'long' else 'red'
        
        alert_html.append(html.Div([
            html.Span(f"[{timestamp}]", style={'color': '#9ca3af', 'fontSize': '10px'}),
            html.Span(f" {alert['direction'].upper()}", style={'color': direction_color, 'fontWeight': 'bold'}),
            html.Span(f" @ ${alert['wall_price']:.2f}", style={'color': '#e5e7eb'}),
            html.Span(f" ({alert['confidence']:.1f})", style={'color': '#f59e0b'})
        ], style={'marginBottom': '3px', 'fontSize': '11px'}))
    
    return alert_html


@app.callback(
    Output('refresh-countdown', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_countdown(n_intervals):
    """Update countdown display."""
    seconds_left = config.AUTO_REFRESH_INTERVAL / 1000
    if seconds_left < 1:
        return f'Auto-refresh: {int(config.AUTO_REFRESH_INTERVAL)}ms'
    return f'Auto-refresh: {seconds_left:.1f}s'


if __name__ == '__main__':
    print("Starting Wormrider on http://127.0.0.1:8051")
    app.run(host='127.0.0.1', port=8051, debug=True)
    
    # Separate bids and asks
    bid_bins = [b for b in bins if b['side'] == 'bid']
    ask_bins = [b for b in bins if b['side'] == 'ask']
    
    # Create order book figure (VERTICAL BARS with width=volume, height=bin_size)
    orderbook_fig = go.Figure()
    
    # Combine all bins to find max size for scaling
    all_bins = bid_bins + ask_bins
    max_size = max([b['size'] for b in all_bins]) if all_bins else 1
    
    # Add individual rectangles for each bin (bids in green, asks in red)
    for b in bid_bins:
        # Bar width proportional to size, bar height = bin_size
        # Bars extend from left edge (x=0) to right (x=size) toward price chart
        orderbook_fig.add_trace(go.Bar(
            x=[b['size']],  # Positive width (extends right toward chart)
            y=[b['price']],
            orientation='h',
            width=bin_size,  # Height of horizontal bar = bin size
            marker_color='#16a34a',
            opacity=0.8,
            showlegend=False,
            hovertemplate=f"<b>Bid</b><br>Price: {b['price']:.2f}<br>Size: {b['size']:.4f}<extra></extra>"
        ))
        
    for b in ask_bins:
        orderbook_fig.add_trace(go.Bar(
            x=[b['size']],  # Positive width (extends right toward chart)
            y=[b['price']],
            orientation='h',
            width=bin_size,  # Height of horizontal bar = bin size
            marker_color='#ef4444',
            opacity=0.8,
            showlegend=False,
            hovertemplate=f"<b>Ask</b><br>Price: {b['price']:.2f}<br>Size: {b['size']:.4f}<extra></extra>"
        ))
        
    # Add legend traces (invisible, just for legend)
    orderbook_fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', 
                                       marker=dict(size=10, color='#16a34a'), 
                                       showlegend=True, name='Bids'))
    orderbook_fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', 
                                       marker=dict(size=10, color='#ef4444'), 
                                       showlegend=True, name='Asks'))
        
    orderbook_fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0f172a',
        plot_bgcolor='#0f172a',
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=60, r=40, t=30, b=60),
        yaxis=dict(title='Price (USD)'),
        xaxis=dict(title='Size', autorange='reversed', side='top'),  # Reverse axis so bars extend left from right edge
        barmode='overlay',
        bargap=0
    )
    
    # Create price chart with 5-minute history
    # Fetch last 5 minutes of data
    current_time = int(time.time() * 1000)
    five_min_ago = current_time - (5 * 60 * 1000)
    
    historical_data = db.get_snapshots_range("BTCUSDT", five_min_ago, current_time)
    
    if historical_data:
        from datetime import datetime as dt
        timestamps = [dt.fromtimestamp(d['timestamp'] / 1000) for d in historical_data]
        prices = [d['mid_price'] for d in historical_data]
        
        price_fig = go.Figure()
        price_fig.add_trace(go.Scatter(
            x=timestamps,
            y=prices,
            mode='lines+markers',
            name='Mid Price',
            line=dict(color='#0ea5e9', width=2),
            marker=dict(size=4)
        ))
        
        price_fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#0f172a',
            plot_bgcolor='#0f172a',
            showlegend=False,
            margin=dict(l=60, r=40, t=20, b=60),
            xaxis=dict(title='Time'),
            yaxis=dict(title='Price (USD)'),
            hovermode='x unified'
        )
    else:
        # Fallback to single point if no history yet
        price_fig = go.Figure()
        from datetime import datetime as dt
        price_fig.add_trace(go.Scatter(
            x=[dt.fromtimestamp(snapshot['timestamp'] / 1000)],
            y=[snapshot['mid_price']],
            mode='markers',
            name='Mid Price',
            marker=dict(color='#0ea5e9', size=8)
        ))
        
        price_fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#0f172a',
            plot_bgcolor='#0f172a',
            showlegend=False,
            margin=dict(l=60, r=40, t=20, b=60),
            xaxis=dict(title='Time'),
            yaxis=dict(title='Price (USD)')
        )
        
    return orderbook_fig, price_fig, f"{bin_size} USD"


@app.callback(
    Output('refresh-countdown', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_countdown(n_intervals):
    """Update countdown display."""
    seconds_left = config.AUTO_REFRESH_INTERVAL / 1000
    if seconds_left < 1:
        return f'Auto-refresh: {int(config.AUTO_REFRESH_INTERVAL)}ms'
    return f'Auto-refresh: {seconds_left:.1f}s'


if __name__ == '__main__':
    print("Starting Wormrider on http://127.0.0.1:8051")
    app.run(host='127.0.0.1', port=8051, debug=True)

