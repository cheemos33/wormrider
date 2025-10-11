"""Simple test app - just price chart and walls."""

import threading
import time
from dash import Dash, Input, Output, html
import plotly.graph_objects as go
from datetime import datetime as dt

import config
from database import db
from collectors import binance
from indicators import liquidity_walls

# Initialize database
db.init_db()

# Start background data collection
print("Starting background data collection...")
binance.start_collection(
    symbol="BTCUSDT",
    interval_seconds=config.SAMPLE_INTERVAL_SECONDS,
    callback=db.insert_snapshot
)

# Create Dash app
app = Dash(__name__)
app.title = "Wormrider Simple"

app.layout = html.Div([
    html.H1("Wormrider - Simple Test"),
    html.Div([
        html.Div([
            html.H3("Price Chart"),
            html.Div(id='price-display', style={'color': 'white'})
        ]),
        html.Div([
            html.H3("Liquidity Walls"),
            html.Div(id='walls-display', style={'color': 'white'})
        ])
    ]),
    html.Div(id='interval-trigger', children=0, style={'display': 'none'}),
    html.Button('Refresh', id='refresh-button', n_clicks=0)
])


@app.callback(
    [Output('price-display', 'children'),
     Output('walls-display', 'children'),
     Output('interval-trigger', 'children')],
    [Input('refresh-button', 'n_clicks'),
     Input('interval-trigger', 'children')]
)
def update_display(n_clicks, trigger):
    """Update display with current data."""
    
    snapshot = db.get_latest_snapshot("BTCUSDT")
    
    if not snapshot:
        return "No data yet", "No walls yet", trigger + 1
    
    # Price info
    price_text = f"Price: ${snapshot['mid_price']:,.2f}"
    
    # Detect walls
    walls_data = liquidity_walls.detect_liquidity_walls(
        bids=snapshot['bids'],
        asks=snapshot['asks'],
        mid_price=snapshot['mid_price']
    )
    
    # Walls text
    walls_text = []
    walls_text.append(f"Total walls: {walls_data['total_walls']}")
    walls_text.append(f"Bid walls: {len(walls_data['bid_walls'])}")
    walls_text.append(f"Ask walls: {len(walls_data['ask_walls'])}")
    
    if walls_data['strongest_bid_wall']:
        wall = walls_data['strongest_bid_wall']
        walls_text.append(f"Strongest BID: ${wall['price']:.2f} ({wall['size']:.2f} BTC)")
    
    if walls_data['strongest_ask_wall']:
        wall = walls_data['strongest_ask_wall']
        walls_text.append(f"Strongest ASK: ${wall['price']:.2f} ({wall['size']:.2f} BTC)")
    
    walls_html = html.Div([html.P(text) for text in walls_text])
    
    return price_text, walls_html, trigger + 1


if __name__ == '__main__':
    print("Starting Simple Wormrider on http://127.0.0.1:8052")
    app.run(host='127.0.0.1', port=8052, debug=True)
