"""
Signal Feed Component for Trading Terminal
Displays signals in a sortable table
"""
from dash import html, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime


def create_signal_feed(signal_history, current_prices=None, star_filter='all', count_limit=15):
    """
    Create the signal feed component showing filtered signals (4★ only)
    
    Args:
        signal_history: List of dicts with time, coin, price, stars, rsi, val, rvwap, etc.
        current_prices: Dict of {coin: current_price} for % change calculation
        star_filter: Filter by star rating ('all', '2', '3', '4')
        count_limit: Number of signals to display
    
    Returns:
        Dash component (dbc.Card)
    """
    
    if not signal_history:
        signal_history = []
    
    if current_prices is None:
        current_prices = {}
    
    # No filtering needed - we only store 4★ signals
    filtered_signals = signal_history
    
    # Apply count limit and reverse order (newest first)
    display_signals = list(reversed(filtered_signals[-count_limit:]))
    
    # Format signals for DataTable
    table_data = []
    for signal in display_signals:
        coin = signal['coin']
        signal_price = signal.get('price', 0)
        
        # Format price
        if signal_price >= 1:
            price_str = f"${signal_price:,.2f}"
        else:
            price_str = f"${signal_price:.4f}"
        
        # Calculate time ago
        time_ago_str = ""
        if 'timestamp' in signal:
            try:
                signal_time = pd.Timestamp(signal['timestamp'])
                now = pd.Timestamp.now()
                time_diff = now - signal_time
                minutes = int(time_diff.total_seconds() / 60)
                
                if minutes < 1:
                    time_ago_str = "NOW"
                elif minutes < 60:
                    time_ago_str = f"{minutes}m"
                else:
                    hours = minutes // 60
                    mins = minutes % 60
                    time_ago_str = f"{hours}h{mins}m"
            except:
                time_ago_str = ""
        
        # Calculate % change from signal price to current price
        pct_change_str = ""
        pct_change_raw = 0
        if coin in current_prices and signal_price > 0:
            current_price = current_prices[coin]
            pct_change = ((current_price - signal_price) / signal_price) * 100
            pct_change_raw = pct_change
            
            # Format with arrow
            if pct_change > 0:
                pct_change_str = f"+{pct_change:.1f}% ⬆"
            elif pct_change < 0:
                pct_change_str = f"{pct_change:.1f}% ⬇"
            else:
                pct_change_str = f"{pct_change:.1f}% →"
        
        # Add to table data
        table_data.append({
            'Time': signal['time'],
            'Coin': coin,
            'Price': price_str,
            'Stars': '🍌🍌🍌🍌',
            'RSI': f"{signal['rsi']:.0f}",
            'VAL': f"{signal['val']:+.1f}%",
            '1d': f"{signal.get('rvwap_1d', 0):+.1f}%",
            '7d': f"{signal.get('rvwap_7d', 0):+.1f}%",
            'Gain': pct_change_str,
            'Age': time_ago_str,
            '_gain_raw': pct_change_raw,  # Hidden for sorting
            '_price_raw': signal_price,  # Hidden for sorting
            '_rsi_raw': signal['rsi'],  # Hidden for sorting
            '_val_raw': signal['val'],  # Hidden for sorting
            '_rvwap_1d_raw': signal.get('rvwap_1d', 0),  # Hidden for sorting
            '_rvwap_7d_raw': signal.get('rvwap_7d', 0),  # Hidden for sorting
        })
    
    # Count signals
    signal_count = len(table_data)
    
    # Create DataTable
    signal_table = dash_table.DataTable(
        id={'type': 'signal-table', 'index': 0},
        columns=[
            {'name': 'Time', 'id': 'Time'},
            {'name': 'Coin', 'id': 'Coin'},
            {'name': 'Price', 'id': 'Price', 'type': 'numeric'},
            {'name': '🍌', 'id': 'Stars'},
            {'name': 'RSI (<50)', 'id': 'RSI', 'type': 'numeric'},
            {'name': 'VAL', 'id': 'VAL'},
            {'name': '1d', 'id': '1d'},
            {'name': '7d', 'id': '7d'},
            {'name': 'Gain', 'id': 'Gain'},
            {'name': 'Age', 'id': 'Age'},
        ],
        data=table_data,
        sort_action='native',  # Enable sorting
        sort_mode='single',
        sort_by=[{'column_id': 'Time', 'direction': 'desc'}],  # Default sort by time
        style_table={
            'overflowY': 'auto',
            'overflowX': 'hidden',
            'maxHeight': '500px',
            'backgroundColor': '#000000'
        },
        style_header={
            'backgroundColor': '#000000',
            'color': '#00ff41',
            'fontWeight': 'bold',
            'textAlign': 'center',
            'border': '1px solid #00ff41',
            'fontSize': '10px',
            'padding': '6px',
            'fontFamily': 'Courier New, monospace',
        },
        style_cell={
            'backgroundColor': '#000000',
            'color': '#00ff41',
            'textAlign': 'center',
            'border': '1px solid #003311',
            'fontSize': '10px',
            'padding': '4px 6px',
            'fontFamily': 'Courier New, monospace',
            'minWidth': '50px',
            'maxWidth': '120px',
            'whiteSpace': 'normal'
        },
        style_cell_conditional=[
            {'if': {'column_id': 'Stars'}, 'fontSize': '6px'},  # 40% smaller bananas
        ],
        style_data_conditional=[
            # All 4★ signals get green glow
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': '#000000'
            },
            {
                'if': {'row_index': 'even'},
                'backgroundColor': '#000000'
            },
            # Highlight positive gains in green
            {
                'if': {
                    'filter_query': '{_gain_raw} > 0',
                    'column_id': 'Gain'
                },
                'color': '#00ff00',
                'fontWeight': 'bold',
                'textShadow': '0 0 5px #00ff00'
            },
            # Highlight negative gains in red
            {
                'if': {
                    'filter_query': '{_gain_raw} < 0',
                    'column_id': 'Gain'
                },
                'color': '#ff0000',
                'fontWeight': 'bold',
                'textShadow': '0 0 5px #ff0000'
            },
        ]
    )
    
    component = dbc.Card([
        dbc.CardHeader([
            html.H6(
                f"LATEST SIGNALS ({signal_count})",
                className="text-center mb-0",
                style={
                    'color': '#00ff41',
                    'fontSize': '12px',
                    'fontWeight': 'bold',
                    'textShadow': '0 0 8px #00ff41'
                }
            )
        ], style={'padding': '6px', 'backgroundColor': '#000000', 'borderBottom': '2px solid #00ff41'}),
        
        dbc.CardBody([
            signal_table
        ], style={'padding': '0', 'backgroundColor': '#000000'})
        
    ], style={
        'backgroundColor': '#000000',
        'border': '2px solid #00ff41',
        'marginTop': '15px',
        'boxShadow': '0 0 20px #00ff41'
    })
    
    return component
