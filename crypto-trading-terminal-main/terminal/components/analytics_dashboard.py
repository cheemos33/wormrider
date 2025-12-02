"""
Analytics Dashboard Component
Displays signal and trade analytics
"""
import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table
from data.analytics_db import analytics_db
from typing import List, Dict


def create_analytics_layout():
    """Create the analytics dashboard layout"""
    
    # Fetch data from database
    signals = analytics_db.get_all_signals(limit=1000)
    stats = analytics_db.get_summary_stats()
    
    return dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.Div([
                    dcc.Link(
                        dbc.Button(
                            "← BACK TO TERMINAL",
                            color='success',
                            outline=True,
                            size='sm',
                            style={
                                'fontSize': '10px',
                                'fontWeight': 'bold',
                                'padding': '4px 12px',
                                'backgroundColor': 'transparent'
                            }
                        ),
                        href='/',
                        style={'display': 'inline-block', 'marginRight': '20px'}
                    ),
                    html.H2(
                        "🍌 ANALYTICS DASHBOARD",
                        style={
                            'color': '#00ff41',
                            'fontSize': '24px',
                            'textShadow': '0 0 10px #00ff41',
                            'fontFamily': 'Courier New, monospace',
                            'letterSpacing': '2px',
                            'display': 'inline-block',
                            'marginRight': '20px'
                        }
                    ),
                    dbc.Button(
                        "🌳 REFRESH",
                        id='analytics-refresh-btn',
                        color='primary',
                        outline=True,
                        size='sm',
                        style={
                            'fontSize': '10px',
                            'fontWeight': 'bold',
                            'padding': '4px 12px',
                            'marginRight': '10px',
                            'backgroundColor': 'transparent'
                        }
                    ),
                    dbc.Checklist(
                        id='analytics-live-mode',
                        options=[{'label': ' LIVE MODE', 'value': 'live'}],
                        value=[],
                        inline=True,
                        style={
                            'display': 'inline-block',
                            'color': '#00ff41',
                            'fontSize': '10px',
                            'verticalAlign': 'middle'
                        }
                    )
                ], style={'textAlign': 'center', 'marginTop': '10px', 'marginBottom': '20px'})
            ])
        ]),
        
        # Summary Stats (Placeholder)
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H6(
                            "SUMMARY STATS",
                            style={
                                'color': '#00ff41',
                                'fontSize': '12px',
                                'fontWeight': 'bold',
                                'textAlign': 'center',
                                'textShadow': '0 0 8px #00ff41',
                                'marginBottom': '0'
                            }
                        )
                    ], style={'padding': '6px', 'backgroundColor': '#000000', 'borderBottom': '2px solid #00ff41'}),
                    dbc.CardBody([
                        dbc.Row([
                            # Column 1 - Overview Stats
                            dbc.Col([
                                html.Div([
                                    html.Div("OVERVIEW", style={'color': '#00ff41', 'fontSize': '10px', 'fontWeight': 'bold', 'marginBottom': '8px', 'borderBottom': '1px solid #003311', 'paddingBottom': '3px'}),
                                    html.Div([
                                        html.Span("Total Signals: ", style={'color': '#888', 'fontSize': '11px'}),
                                        html.Span(f"{stats['total_signals']}", style={'color': '#00ff41', 'fontSize': '13px', 'fontWeight': 'bold'})
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Span("Traded: ", style={'color': '#888', 'fontSize': '11px'}),
                                        html.Span(f"{stats['total_traded']}", style={'color': '#00ff00', 'fontSize': '13px', 'fontWeight': 'bold'})
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Span("Open: ", style={'color': '#888', 'fontSize': '11px'}),
                                        html.Span(f"{stats['total_open']}", style={'color': '#ffff00', 'fontSize': '13px', 'fontWeight': 'bold'})
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Span("Closed: ", style={'color': '#888', 'fontSize': '11px'}),
                                        html.Span(f"{stats['total_closed']}", style={'color': '#888', 'fontSize': '13px', 'fontWeight': 'bold'})
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Span("Win Rate: ", style={'color': '#888', 'fontSize': '11px'}),
                                        html.Span(f"{stats['win_rate']:.1f}%", style={'color': '#00ff00' if stats['win_rate'] > 50 else '#ff0000' if stats['win_rate'] > 0 else '#888', 'fontSize': '13px', 'fontWeight': 'bold'})
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Span("Total P&L: ", style={'color': '#888', 'fontSize': '11px'}),
                                        html.Span(f"${stats['total_pnl']:.2f}", style={'color': '#00ff00' if stats['total_pnl'] > 0 else '#ff0000' if stats['total_pnl'] < 0 else '#888', 'fontSize': '13px', 'fontWeight': 'bold', 'textShadow': '0 0 5px #00ff00' if stats['total_pnl'] > 0 else '0 0 5px #ff0000' if stats['total_pnl'] < 0 else 'none'})
                                    ])
                                ], style={'padding': '5px'})
                            ], width=3),
                            
                            # Column 2 - Rejection Stats
                            dbc.Col([
                                html.Div([
                                    html.Div("REJECTIONS", style={'color': '#00ff41', 'fontSize': '10px', 'fontWeight': 'bold', 'marginBottom': '8px', 'borderBottom': '1px solid #003311', 'paddingBottom': '3px'}),
                                    html.Div([
                                        html.Span("Total Rejected: ", style={'color': '#888', 'fontSize': '11px'}),
                                        html.Span(f"{stats['total_rejected']}", style={'color': '#ff8800', 'fontSize': '13px', 'fontWeight': 'bold'})
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Span("Position Cap: ", style={'color': '#888', 'fontSize': '11px'}),
                                        html.Span(f"{stats['rejected_position_cap']}", style={'color': '#ffaa00', 'fontSize': '13px', 'fontWeight': 'bold'}),
                                        html.Span(f" ({stats['rejected_position_cap']/stats['total_rejected']*100:.0f}%)" if stats['total_rejected'] > 0 else " (0%)", style={'color': '#666', 'fontSize': '10px'})
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Span("No Liquidity: ", style={'color': '#888', 'fontSize': '11px'}),
                                        html.Span(f"{stats['rejected_no_liquidity']}", style={'color': '#ff4400', 'fontSize': '13px', 'fontWeight': 'bold'}),
                                        html.Span(f" ({stats['rejected_no_liquidity']/stats['total_rejected']*100:.0f}%)" if stats['total_rejected'] > 0 else " (0%)", style={'color': '#666', 'fontSize': '10px'})
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Span("Exchange Error: ", style={'color': '#888', 'fontSize': '11px'}),
                                        html.Span(f"{stats['rejected_exchange_error']}", style={'color': '#ff0000', 'fontSize': '13px', 'fontWeight': 'bold'}),
                                        html.Span(f" ({stats['rejected_exchange_error']/stats['total_rejected']*100:.0f}%)" if stats['total_rejected'] > 0 else " (0%)", style={'color': '#666', 'fontSize': '10px'})
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Span("Budget Issues: ", style={'color': '#888', 'fontSize': '11px'}),
                                        html.Span(f"{stats['rejected_insufficient_funds']}", style={'color': '#aa44ff', 'fontSize': '13px', 'fontWeight': 'bold'}),
                                        html.Span(f" ({stats['rejected_insufficient_funds']/stats['total_rejected']*100:.0f}%)" if stats['total_rejected'] > 0 else " (0%)", style={'color': '#666', 'fontSize': '10px'})
                                    ], style={'marginBottom': '5px'}),
                                ], style={'padding': '5px'})
                            ], width=3),
                            
                            # Column 3 - Coin Performance
                            dbc.Col([
                                html.Div([
                                    html.Div("COIN PERFORMANCE", style={'color': '#00ff41', 'fontSize': '10px', 'fontWeight': 'bold', 'marginBottom': '8px', 'borderBottom': '1px solid #003311', 'paddingBottom': '3px'}),
                                    html.Div([
                                        # Show top coins by activity (trades or rejections)
                                        html.Div([
                                            html.Span(f"{coin_stat['coin']}: ", style={'color': '#888', 'fontSize': '10px'}),
                                            html.Span(
                                                f"{coin_stat['trades']} trades" if coin_stat['trades'] > 0 
                                                else f"0 ({coin_stat['rejections']} blocks)" if coin_stat['rejections'] > 0
                                                else "0 trades",
                                                style={
                                                    'color': '#00ff00' if coin_stat['trades'] > 0 else '#ff6666' if coin_stat['rejections'] > 0 else '#666',
                                                    'fontSize': '11px',
                                                    'fontWeight': 'bold' if coin_stat['trades'] > 0 or coin_stat['rejections'] > 0 else 'normal'
                                                }
                                            )
                                        ], style={'marginBottom': '3px'})
                                        for coin_stat in stats.get('coin_stats', [])[:8]  # Show top 8 coins
                                    ])
                                ], style={'padding': '5px'})
                            ], width=3),
                            
                            # Column 4 - Coin Performance (placeholder)
                            dbc.Col([
                                html.Div([
                                    html.Div("TOP COINS", style={'color': '#00ff41', 'fontSize': '10px', 'fontWeight': 'bold', 'marginBottom': '8px', 'borderBottom': '1px solid #003311', 'paddingBottom': '3px'}),
                                    html.Div([
                                        html.Span("Best Performer: ", style={'color': '#444', 'fontSize': '10px', 'fontStyle': 'italic'}),
                                        html.Span("--", style={'color': '#444', 'fontSize': '11px'})
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Span("Most Traded: ", style={'color': '#444', 'fontSize': '10px', 'fontStyle': 'italic'}),
                                        html.Span("--", style={'color': '#444', 'fontSize': '11px'})
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Span("Win Rate Leader: ", style={'color': '#444', 'fontSize': '10px', 'fontStyle': 'italic'}),
                                        html.Span("--", style={'color': '#444', 'fontSize': '11px'})
                                    ], style={'marginBottom': '5px'}),
                                ], style={'padding': '5px'})
                            ], width=3)
                        ])
                    ], style={'padding': '10px', 'backgroundColor': '#000000'})
                ], style={
                    'backgroundColor': '#000000',
                    'border': '2px solid #00ff41',
                    'boxShadow': '0 0 15px #00ff41',
                    'marginBottom': '20px'
                })
            ])
        ]),
        
        # Filters
        dbc.Row([
            dbc.Col([
                dbc.Label("Coin:", style={'color': '#00ff41', 'fontSize': '10px', 'marginRight': '5px'}),
                dcc.Dropdown(
                    id='analytics-coin-filter',
                    options=[{'label': 'All Coins', 'value': 'all'}] + 
                            [{'label': coin, 'value': coin} for coin in sorted(set(s['coin'] for s in signals if s['coin']))],
                    value='all',
                    clearable=False,
                    style={'width': '150px', 'display': 'inline-block', 'marginRight': '15px', 'fontSize': '10px'}
                )
            ], width=3),
            dbc.Col([
                dbc.Label("Traded:", style={'color': '#00ff41', 'fontSize': '10px', 'marginRight': '5px'}),
                dcc.Dropdown(
                    id='analytics-traded-filter',
                    options=[
                        {'label': 'All', 'value': 'all'},
                        {'label': 'Traded', 'value': 'traded'},
                        {'label': 'Not Traded', 'value': 'not_traded'}
                    ],
                    value='all',
                    clearable=False,
                    style={'width': '150px', 'display': 'inline-block', 'marginRight': '15px', 'fontSize': '10px'}
                )
            ], width=3),
            dbc.Col([
                dbc.Label("Status:", style={'color': '#00ff41', 'fontSize': '10px', 'marginRight': '5px'}),
                dcc.Dropdown(
                    id='analytics-status-filter',
                    options=[
                        {'label': 'All', 'value': 'all'},
                        {'label': 'Open', 'value': 'open'},
                        {'label': 'Closed', 'value': 'closed'}
                    ],
                    value='all',
                    clearable=False,
                    style={'width': '150px', 'display': 'inline-block', 'fontSize': '10px'}
                )
            ], width=3)
        ], style={'marginBottom': '15px'}),
        
        # Signals Table
        dbc.Row([
            dbc.Col([
                html.Div(id='analytics-table-container')
            ])
        ]),
        
        # Live mode interval (30s refresh when enabled)
        dcc.Interval(
            id='analytics-live-interval',
            interval=30000,  # 30 seconds
            n_intervals=0,
            disabled=True  # Disabled by default
        )
        
    ], fluid=True, style={'backgroundColor': '#000000', 'minHeight': '100vh', 'padding': '20px'})


def create_signals_table(signals: List[Dict], current_prices: Dict = None) -> dash_table.DataTable:
    """Create the signals data table with current price data for gain calculation
    
    Args:
        signals: List of signal dictionaries from database
        current_prices: Dict of {coin: current_price} for % change calculation
    """
    
    if not signals:
        return html.Div(
            "No signals found",
            style={'textAlign': 'center', 'color': '#666', 'padding': '20px', 'fontSize': '12px'}
        )
    
    if current_prices is None:
        current_prices = {}
    
    print(f"📊 Analytics Dashboard: Received {len(current_prices)} prices, processing {len(signals)} signals")
    
    # Prepare data for table - MATCH LATEST SIGNALS STRUCTURE + TRADE COLUMNS
    table_data = []
    for sig in signals:
        coin = sig['coin']
        signal_price = sig.get('price_at_signal', 0)
        
        # Determine status with rejection reasons
        status = '-'
        if sig['traded']:
            # Traded signal
            if sig['trade_status'] == 'open':
                status = 'Open'
            elif sig['trade_status'] == 'closed':
                pnl = sig.get('pnl_pct', 0)
                if pnl > 0:
                    status = f"Closed +{pnl:.1f}%"
                else:
                    status = f"Closed {pnl:.1f}%"
        else:
            # Not traded signal
            if sig.get('rejection_reason'):
                status = sig['rejection_reason']
            else:
                status = 'Pending'
        
        # Calculate Gain (% change from signal price to current price)
        gain_str = '-'
        gain_raw = 0
        if coin in current_prices and signal_price > 0:
            current_price = current_prices[coin]
            pct_change = ((current_price - signal_price) / signal_price) * 100
            gain_raw = pct_change
            
            # Format with arrow
            if pct_change > 0:
                gain_str = f"+{pct_change:.1f}% ⬆"
            elif pct_change < 0:
                gain_str = f"{pct_change:.1f}% ⬇"
            else:
                gain_str = f"{pct_change:.1f}% →"
        
        # Calculate Age (time since signal)
        age_str = '-'
        if sig.get('timestamp'):
            try:
                import pandas as pd
                signal_time = pd.Timestamp(sig['timestamp'])
                now = pd.Timestamp.now()
                time_diff = now - signal_time
                minutes = int(time_diff.total_seconds() / 60)
                
                if minutes < 1:
                    age_str = "NOW"
                elif minutes < 60:
                    age_str = f"{minutes}m"
                else:
                    hours = minutes // 60
                    mins = minutes % 60
                    age_str = f"{hours}h{mins}m"
            except:
                age_str = '-'
        
        row = {
            # Signal columns (match Latest Signals exactly)
            'Time': sig['timestamp'][:16] if sig['timestamp'] else '-',
            'Coin': sig['coin'],
            'Price': f"${sig['price_at_signal']:.2f}" if sig['price_at_signal'] else '-',
            '🍌': '🍌' * (sig['stars'] if sig['stars'] else 0),
            'RSI (<20)': f"{sig['rsi']:.1f}" if sig['rsi'] else '-',
            'VAL': f"{sig['val']:.1f}%" if sig['val'] is not None else '-',
            '1d': f"{sig['rvwap_1d']:.1f}%" if sig['rvwap_1d'] is not None else '-',
            '7d': f"{sig['rvwap_7d']:.1f}%" if sig['rvwap_7d'] is not None else '-',
            'Gain': gain_str,
            'Age': age_str,
            # ID column (after signal columns)
            'ID': sig['signal_id'],
            # Trade columns
            'Traded': '✓' if sig['traded'] else '✗',
            'Entry Price': f"${sig['entry_price']:.2f}" if sig['entry_price'] else '-',
            'Entry Time': sig['entry_time'][:16] if sig['entry_time'] else '-',
            'Exit Price': f"${sig['exit_price']:.2f}" if sig['exit_price'] else '-',
            'Exit Time': sig['exit_time'][:16] if sig['exit_time'] else '-',
            'P&L USD': f"${sig['pnl_usd']:.2f}" if sig['pnl_usd'] is not None else '-',
            'P&L %': f"{sig['pnl_pct']:.1f}%" if sig['pnl_pct'] is not None else '-',
            'Status': status,
            # Hidden fields for sorting/filtering
            '_gain_raw': gain_raw
        }
        table_data.append(row)
    
    return dash_table.DataTable(
        data=table_data,
        columns=[
            # Signal columns (match Latest Signals exactly)
            {'name': 'Time', 'id': 'Time'},
            {'name': 'Coin', 'id': 'Coin'},
            {'name': 'Price', 'id': 'Price'},
            {'name': '🍌', 'id': '🍌'},
            {'name': 'RSI (<20)', 'id': 'RSI (<20)'},
            {'name': 'VAL', 'id': 'VAL'},
            {'name': '1d', 'id': '1d'},
            {'name': '7d', 'id': '7d'},
            {'name': 'Gain', 'id': 'Gain'},
            {'name': 'Age', 'id': 'Age'},
            # ID column (after signal columns)
            {'name': 'ID', 'id': 'ID'},
            # Trade columns
            {'name': 'Traded', 'id': 'Traded'},
            {'name': 'Entry Price', 'id': 'Entry Price'},
            {'name': 'Entry Time', 'id': 'Entry Time'},
            {'name': 'Exit Price', 'id': 'Exit Price'},
            {'name': 'Exit Time', 'id': 'Exit Time'},
            {'name': 'P&L USD', 'id': 'P&L USD'},
            {'name': 'P&L %', 'id': 'P&L %'},
            {'name': 'Status', 'id': 'Status'}
        ],
        style_table={
            'overflowX': 'auto',
            'backgroundColor': '#000000'
        },
        style_header={
            'backgroundColor': '#003311',
            'color': '#00ff41',
            'fontWeight': 'bold',
            'fontSize': '10px',
            'textAlign': 'center',
            'border': '1px solid #00ff41'
        },
        style_cell={
            'backgroundColor': '#000000',
            'color': '#00ff41',
            'fontSize': '10px',
            'textAlign': 'center',
            'padding': '8px',
            'border': '1px solid #003311'
        },
        style_data_conditional=[
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
            {
                'if': {'column_id': 'P&L USD', 'filter_query': '{P&L USD} contains "-"'},
                'color': '#ff0000'
            },
            {
                'if': {'column_id': 'P&L USD', 'filter_query': '{P&L USD} contains "$"'},
                'color': '#00ff00'
            },
            {
                'if': {'column_id': 'P&L %', 'filter_query': '{P&L %} contains "-"'},
                'color': '#ff0000'
            },
            {
                'if': {'column_id': 'Traded', 'filter_query': '{Traded} = "✓"'},
                'color': '#00ff00'
            },
            {
                'if': {'column_id': 'Status', 'filter_query': '{Status} = "open"'},
                'color': '#ffff00',
                'fontWeight': 'bold'
            }
        ],
        page_size=50,
        sort_action='native',
        filter_action='native'
    )

