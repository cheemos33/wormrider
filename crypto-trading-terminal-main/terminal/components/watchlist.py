"""
Watchlist UI Component for Trading Terminal
Displays the 20-coin watchlist with prices and controls
"""
from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc


def create_watchlist_component(watchlist_data, coin_universe, active_coins=None):
    """
    Create the watchlist UI component
    
    Args:
        watchlist_data: List of dicts with coin, price, change_24h, rsi, val_distance
        coin_universe: List of all available coins for search dropdown
        active_coins: List of coins that are checked (shown on chart)
    
    Returns:
        Dash component (dbc.Card)
    """
    
    # Default: all coins active if not specified
    if active_coins is None:
        active_coins = [item['coin'] for item in watchlist_data]
    
    # Format data for display
    formatted_data = []
    for item in watchlist_data:
        rsi_value = item.get('rsi', 50.0)
        val_dist = item.get('val_distance', 0.0)
        rvwap_1d_dist = item.get('rvwap_1d_distance', 0.0)
        rvwap_7d_dist = item.get('rvwap_7d_distance', 0.0)
        is_active = item['coin'] in active_coins
        
        # Calculate signal strength (stars) based on 4 criteria
        signal_score = 0
        
        # Criteria 1: RSI < 20 (oversold - PRODUCTION)
        if rsi_value < 20:
            signal_score += 1
        
        # Criteria 2: Price < VAL (below value area) - PRODUCTION
        if val_dist < 0:
            signal_score += 1
        
        # Criteria 3: Price < 1d RVWAP (below short-term average)
        if rvwap_1d_dist < 0:
            signal_score += 1
        
        # Criteria 4: Price < 7d RVWAP (below medium-term average)
        if rvwap_7d_dist < 0:
            signal_score += 1
        
        # Display bananas based on score
        if signal_score == 0:
            signal = ''  # Blank/empty
        elif signal_score == 1:
            signal = '🍌'
        elif signal_score == 2:
            signal = '🍌🍌'
        elif signal_score == 3:
            signal = '🍌🍌🍌'
        elif signal_score == 4:
            signal = '🍌🍌🍌🍌'
        
        # Create styled RSI value
        rsi_display = f"{rsi_value:.1f}"
        if rsi_value < 20:
            rsi_display = f'🍌{rsi_display}'  # Banana for oversold
        
        # Create styled VAL value
        val_display = f"{val_dist:+.2f}%"
        if val_dist < 0:  # PRODUCTION threshold
            val_display = f'🍌{val_display}'  # Banana for below value
        
        # Create styled 1d RVWAP value
        rvwap_1d_display = f"{rvwap_1d_dist:+.1f}%"
        if rvwap_1d_dist < 0:
            rvwap_1d_display = f'🍌{rvwap_1d_display}'  # Banana for below short-term
        
        # Create styled 7d RVWAP value
        rvwap_7d_display = f"{rvwap_7d_dist:+.1f}%"
        if rvwap_7d_dist < 0:
            rvwap_7d_display = f'🍌{rvwap_7d_display}'  # Banana for below medium-term
        
        formatted_data.append({
            'Show': '☑' if is_active else '☐',
            'Signal': signal,
            'Coin': item['coin'],
            'Price': f"${item['price']:,.2f}" if item['price'] >= 1 else f"${item['price']:.4f}",
            '24h %': f"{item['change_24h']:+.2f}%",
            'RSI': rsi_display,
            'VAL': val_display,
            '7d RVWAP': rvwap_7d_display,
            '1d RVWAP': rvwap_1d_display,
            'Remove': '✕',
            '_rsi_raw': rsi_value,  # Hidden column for filtering
            '_val_raw': val_dist,    # Hidden column for filtering
            '_rvwap_1d_raw': rvwap_1d_dist,  # Hidden column for filtering
            '_rvwap_7d_raw': rvwap_7d_dist,  # Hidden column for filtering
            '_signal_score': signal_score  # Hidden column for sorting
        })
    
    component = dbc.Card([
        dbc.CardHeader([
            html.H5(f"MY WATCHLIST ({len(watchlist_data)}/20)", className="text-center mb-0", style={'color': '#00ff41', 'fontSize': '14px', 'fontWeight': 'bold', 'textShadow': '0 0 8px #00ff41'})
        ], style={'padding': '10px', 'backgroundColor': '#000000', 'borderBottom': '2px solid #00ff41'}),
        
        dbc.CardBody([
            # Search and Add Section
            dbc.Row([
                dbc.Col([
                    dcc.Dropdown(
                        id={'type': 'coin-search-dropdown', 'index': 0},
                        options=[{'label': coin, 'value': coin} for coin in coin_universe],
                        placeholder="Search coin...",
                        style={
                            'backgroundColor': '#000000',
                            'color': '#00ff41',
                            'border': '1px solid #003311'
                        },
                        className='matrix-dropdown'
                    )
                ], width=8),
                dbc.Col([
                    dbc.Button(
                        "+ Add",
                        id={'type': 'add-coin-button', 'index': 0},
                        size="sm",
                        className="w-100",
                        style={
                            'backgroundColor': '#000000',
                            'color': '#00ff41',
                            'border': '1px solid #00ff41',
                            'fontWeight': 'bold'
                        }
                    )
                ], width=4)
            ], className="mb-3"),
            
            # Watchlist Table
            html.Div([
                dash_table.DataTable(
                    id={'type': 'watchlist-table', 'index': 0},
                    columns=[
                        {'name': '', 'id': 'Show'},
                        {'name': 'Signal', 'id': 'Signal'},
                        {'name': 'Coin', 'id': 'Coin'},
                        {'name': 'Price', 'id': 'Price'},
                        {'name': '24h %', 'id': '24h %', 'type': 'numeric'},
                        {'name': 'RSI (<20)', 'id': 'RSI', 'type': 'numeric'},
                        {'name': 'VAL', 'id': 'VAL', 'type': 'numeric'},
                        {'name': '7d RVWAP', 'id': '7d RVWAP', 'type': 'numeric'},
                        {'name': '1d RVWAP', 'id': '1d RVWAP', 'type': 'numeric'},
                        {'name': '', 'id': 'Remove'},
                    ],
                    data=formatted_data,
                    sort_action='native',  # Enable sorting
                    sort_mode='single',    # Sort by one column at a time
                    style_table={
                        'overflowY': 'hidden',  # No scroll - fits exactly 20 rows
                        'height': 'auto'
                    },
                    style_header={
                        'backgroundColor': '#000000',
                        'color': '#00ff41',
                        'fontWeight': 'bold',
                        'border': '1px solid #00ff41',
                        'textAlign': 'center',
                        'fontSize': '10px',
                        'padding': '6px'
                    },
                    style_data={
                        'backgroundColor': '#000000',
                        'color': '#00ff41',
                        'border': '1px solid #003311',
                    },
                    style_data_conditional=[
                        # Bright green for positive changes
                        {
                            'if': {
                                'filter_query': '{24h %} contains "+"',
                                'column_id': '24h %'
                            },
                            'color': '#00ff00',
                            'fontWeight': 'bold',
                            'textShadow': '0 0 5px #00ff00'
                        },
                        # Dark red for negative changes
                        {
                            'if': {
                                'filter_query': '{24h %} contains "-"',
                                'column_id': '24h %'
                            },
                            'color': '#ff0000',
                            'fontWeight': 'bold',
                            'textShadow': '0 0 5px #ff0000'
                        },
                        # RSI Oversold (< 50) - Bright red with glow
                        {
                            'if': {
                                'filter_query': '{RSI} < 50',
                                'column_id': 'RSI'
                            },
                            'color': '#ff0000',
                            'fontWeight': 'bold',
                            'textShadow': '0 0 8px #ff0000',
                            'backgroundColor': '#330000'
                        },
                        # RSI Overbought (> 70) - Yellow with glow
                        {
                            'if': {
                                'filter_query': '{RSI} > 70',
                                'column_id': 'RSI'
                            },
                            'color': '#ffff00',
                            'fontWeight': 'bold',
                            'textShadow': '0 0 8px #ffff00',
                            'backgroundColor': '#333300'
                        },
                        # Dim inactive (unchecked) coins
                        {
                            'if': {
                                'filter_query': '{Show} = "☐"'
                            },
                            'opacity': 0.4
                        },
                        # Signal Column - 4 Bananas ONLY (shiny effect)
                        {
                            'if': {
                                'filter_query': '{Signal} = "🍌🍌🍌🍌"',
                                'column_id': 'Signal'
                            },
                            'color': '#00ff00',
                            'fontWeight': 'bold',
                            'textShadow': '0 0 10px #00ff00',
                            'backgroundColor': '#003300'
                        },
                        # Style remove button
                        {
                            'if': {'column_id': 'Remove'},
                            'textAlign': 'center',
                            'cursor': 'pointer',
                            'fontWeight': 'bold',
                            'color': '#ff0000',
                        },
                    ],
                    style_cell={
                        'textAlign': 'center',
                        'padding': '4px 6px',
                        'fontFamily': 'monospace',
                        'fontSize': '11px',
                        'height': '30px',
                        'lineHeight': '1.2'
                    },
                    style_cell_conditional=[
                        {'if': {'column_id': 'Show'}, 'textAlign': 'center', 'width': '40px', 'cursor': 'pointer', 'fontSize': '14px'},
                        {'if': {'column_id': 'Signal'}, 'textAlign': 'center', 'width': '90px', 'fontSize': '7px'},
                        {'if': {'column_id': 'Coin'}, 'textAlign': 'left', 'fontWeight': 'bold', 'color': '#00ff41', 'textShadow': '0 0 5px #00ff41'},
                        {'if': {'column_id': 'Price'}, 'textAlign': 'right', 'color': '#00ff41', 'textShadow': '0 0 5px #00ff41'},
                        {'if': {'column_id': '24h %'}, 'textAlign': 'right', 'color': '#00ff41', 'textShadow': '0 0 5px #00ff41'},
                        {'if': {'column_id': 'RSI'}, 'textAlign': 'center', 'fontWeight': 'bold', 'width': '60px'},
                        {'if': {'column_id': 'VAL'}, 'textAlign': 'center', 'fontWeight': 'bold', 'width': '70px'},
                        {'if': {'column_id': '1d RVWAP'}, 'textAlign': 'center', 'fontWeight': 'bold', 'width': '80px', 'color': '#00ff41'},
                        {'if': {'column_id': '7d RVWAP'}, 'textAlign': 'center', 'fontWeight': 'bold', 'width': '80px', 'color': '#00ff41'},
                        {'if': {'column_id': 'Remove'}, 'width': '50px'},
                        {'if': {'column_id': '_rsi_raw'}, 'display': 'none'},
                        {'if': {'column_id': '_val_raw'}, 'display': 'none'},
                        {'if': {'column_id': '_rvwap_1d_raw'}, 'display': 'none'},
                        {'if': {'column_id': '_rvwap_7d_raw'}, 'display': 'none'},
                        {'if': {'column_id': '_signal_score'}, 'display': 'none'},
                    ],
                )
            ]),
        ], style={'padding': '15px'})
    ], style={
        'backgroundColor': '#000000',
        'border': '2px solid #00ff41',
        'height': '100%',
        'boxShadow': '0 0 20px #00ff41'
    })
    
    return component

