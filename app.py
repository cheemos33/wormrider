"""Main Wormrider application - Dash entry point."""

import threading
import time
from dash import Dash, Input, Output, State
import plotly.graph_objects as go

import config
from database import db
from collectors import binance
from indicators import orderbook
from layouts import main


# Initialize database
db.init_db()

# Start background data collection
print("Starting background data collection...")
collection_thread = binance.start_collection(
    symbol="BTCUSDT",
    interval_seconds=config.SAMPLE_INTERVAL_SECONDS,
    callback=db.insert_snapshot
)

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
app.layout = main.create_layout()


@app.callback(
    [Output('orderbook-chart', 'figure'),
     Output('price-chart', 'figure'),
     Output('bin-size-display', 'children')],
    [Input('interval-component', 'n_intervals'),
     Input('bin-size-slider', 'value')]
)
def update_charts(n_intervals, bin_size):
    """Update order book profile and price chart."""
    
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
        return empty_fig, empty_fig, f"{bin_size} USD"
    
    # Calculate binned profile
    bins = orderbook.calculate_binned_profile(
        bids=snapshot['bids'],
        asks=snapshot['asks'],
        bin_size=bin_size,
        window_pct=2.0,
        mid_price=snapshot['mid_price']
    )
    
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
    
    # Calculate Y-axis range from order book bins for alignment
    if all_bins:
        prices_in_bins = [b['price'] for b in all_bins]
        y_min = min(prices_in_bins) - bin_size  # Add padding
        y_max = max(prices_in_bins) + bin_size
    else:
        # Fallback to mid price ± 2%
        y_min = snapshot['mid_price'] * 0.98
        y_max = snapshot['mid_price'] * 1.02
    
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
            yaxis=dict(title='Price (USD)', range=[y_min, y_max]),  # Align with order book
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
            yaxis=dict(title='Price (USD)', range=[y_min, y_max])  # Align with order book
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
    print("Starting Wormrider on http://127.0.0.1:8050")
    app.run(host='127.0.0.1', port=8050, debug=True)

