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
        return empty_fig, empty_fig, str(bin_size)
    
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
    
    # Create order book figure
    orderbook_fig = go.Figure()
    
    # Add bid bars (green, pointing left)
    if bid_bins:
        orderbook_fig.add_trace(go.Bar(
            y=[b['price'] for b in bid_bins],
            x=[-b['size'] for b in bid_bins],  # Negative for left direction
            orientation='h',
            name='Bids',
            marker_color='#16a34a',
            opacity=0.9
        ))
    
    # Add ask bars (red, pointing left)
    if ask_bins:
        orderbook_fig.add_trace(go.Bar(
            y=[b['price'] for b in ask_bins],
            x=[-b['size'] for b in ask_bins],  # Negative for left direction
            orientation='h',
            name='Asks',
            marker_color='#ef4444',
            opacity=0.9
        ))
    
    orderbook_fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0f172a',
        plot_bgcolor='#0f172a',
        showlegend=True,
        margin=dict(l=60, r=40, t=20, b=40),
        xaxis=dict(title='Size', autorange='reversed'),  # Reverse x-axis so bars point left
        yaxis=dict(title='Price (USD)'),
        barmode='overlay'
    )
    
    # Create placeholder price chart
    price_fig = go.Figure()
    price_fig.add_trace(go.Scatter(
        x=[snapshot['timestamp']],
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
        margin=dict(l=60, r=40, t=20, b=40),
        xaxis=dict(title='Time'),
        yaxis=dict(title='Price (USD)')
    )
    
    return orderbook_fig, price_fig, str(bin_size)


@app.callback(
    Output('refresh-countdown', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_countdown(n_intervals):
    """Update countdown display."""
    seconds_left = config.AUTO_REFRESH_INTERVAL // 1000
    return f'Auto-refresh in: {seconds_left}s'


if __name__ == '__main__':
    print("Starting Wormrider on http://127.0.0.1:8050")
    app.run(host='127.0.0.1', port=8050, debug=True)

