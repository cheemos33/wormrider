"""Debug version of Wormrider app."""

import threading
import time
from dash import Dash, Input, Output, html, dcc
from datetime import datetime as dt

import config
from database import db
from collectors import binance
from collectors import binance_trades
from indicators import cvd
from strategy import orderbook_scalping

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

# Create Dash app
app = Dash(__name__)
app.title = "Wormrider - Debug"

# Simple layout
app.layout = html.Div([
    html.H1("Wormrider Debug", style={'color': '#e5e7eb', 'textAlign': 'center'}),
    html.Div(id='debug-info', children='Loading...', style={'color': '#9ca3af', 'padding': '20px'}),
    dcc.Interval(
        id='interval-component',
        interval=2000,  # 2 seconds
        n_intervals=0
    )
], style={'padding': '20px', 'background': '#0b0f16', 'minHeight': '100vh'})


@app.callback(
    Output('debug-info', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_debug(n_intervals):
    """Debug callback to see what's happening."""
    try:
        # Get latest snapshot
        snapshot = db.get_latest_snapshot("BTCUSDT")
        
        if not snapshot:
            return "❌ No snapshot data available"
        
        current_price = snapshot['mid_price']
        
        # Get aggregated data
        agg_snapshot = db.get_latest_aggregated_snapshot("BTCUSDT", 100)
        
        if not agg_snapshot:
            return f"✅ Price: ${current_price:,.2f}<br>❌ No aggregated data"
        
        # Calculate imbalance
        imbalance_data = orderbook_scalping.calculate_imbalance_display(
            agg_bids=agg_snapshot['bids'],
            agg_asks=agg_snapshot['asks'],
            current_price=current_price,
            num_bins=2
        )
        
        if imbalance_data:
            direction_emoji = "🔴" if imbalance_data['direction'] == 'long' else "🟢"
            return f"""
            ✅ Price: ${current_price:,.2f}<br>
            ✅ Aggregated data: {len(agg_snapshot['bids'])} bids, {len(agg_snapshot['asks'])} asks<br>
            {direction_emoji} Imbalance: {imbalance_data['direction'].upper()} ({imbalance_data['imbalance_ratio']*100:.1f}%)<br>
            📊 Bid Volume: {imbalance_data['bid_volume']:,.2f}<br>
            📊 Ask Volume: {imbalance_data['ask_volume']:,.2f}<br>
            <br>
            🎯 Signal threshold: 54%<br>
            {'✅ Would generate signal!' if imbalance_data['imbalance_ratio'] >= 0.54 else '❌ Below signal threshold'}
            """
        else:
            return f"""
            ✅ Price: ${current_price:,.2f}<br>
            ✅ Aggregated data: {len(agg_snapshot['bids'])} bids, {len(agg_snapshot['asks'])} asks<br>
            ⚪ No imbalance detected<br>
            <br>
            🔍 Raw data:<br>
            Bids: {agg_snapshot['bids']}<br>
            Asks: {agg_snapshot['asks']}
            """
            
    except Exception as e:
        return f"❌ Error: {str(e)}"


if __name__ == '__main__':
    print("Starting Debug App on http://127.0.0.1:8060")
    app.run(host='127.0.0.1', port=8060, debug=True)
