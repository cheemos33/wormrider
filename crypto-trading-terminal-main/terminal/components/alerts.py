"""
Alerts Component for Trading Terminal
Displays bot status, positions, and trade log
"""
from dash import html
import dash_bootstrap_components as dbc


def create_alerts_component(bot_status: dict, current_prices: dict = None):
    """
    Create the alerts/trading status component
    
    Args:
        bot_status: Dict with bot state, positions, trades, budget
        current_prices: Dict of {coin: current_price} for P&L calculation
    
    Returns:
        Dash component (dbc.Card)
    """
    
    if not bot_status:
        bot_status = {
            'is_active': False,
            'budget_total': 50.0,
            'budget_spent': 0.0,
            'budget_remaining': 50.0,
            'notional_total': 200.0,
            'notional_spent': 0.0,
            'notional_remaining': 200.0,
            'total_coins': 0,
            'total_entries': 0,
            'positions': [],
            'recent_trades': []
        }
    
    if current_prices is None:
        current_prices = {}
    
    # Bot status indicator
    if bot_status['is_active']:
        status_color = '#00ff00'
        status_text = "● ACTIVE"
        status_glow = '0 0 10px #00ff00'
    else:
        status_color = '#666'
        status_text = "○ INACTIVE"
        status_glow = 'none'
    
    # Budget bar and P&L calculation (use notional budget)
    notional_total = bot_status.get('notional_total', bot_status['budget_total'] * 4)
    notional_spent = bot_status.get('notional_spent', bot_status['budget_spent'])
    budget_pct = (notional_spent / notional_total) * 100 if notional_total > 0 else 0
    
    # Calculate total P&L from all positions
    total_pnl_usd = 0
    total_pnl_pct = 0
    if bot_status['positions']:
        for pos in bot_status['positions']:
            if pos['pnl_usd'] is not None:
                total_pnl_usd += pos['pnl_usd']
        
        # Calculate percentage: (total_pnl / budget_spent) * 100
        if bot_status['budget_spent'] > 0:
            total_pnl_pct = (total_pnl_usd / bot_status['budget_spent']) * 100
    
    # Position list
    position_rows = []
    print(f"🟢 Rendering positions: {len(bot_status['positions'])} positions")
    if bot_status['positions']:
        for pos in bot_status['positions']:
            print(f"  🟢 Position: {pos['coin']} - creating CLOSE button")
            # Build position display
            avg_price = pos['avg_price']
            current_price = pos['current_price']
            
            # Format entry price
            entry_price_str = f"${avg_price:,.2f}" if avg_price >= 1 else f"${avg_price:.4f}"
            
            # Format current price
            if current_price:
                current_price_str = f"${current_price:,.2f}" if current_price >= 1 else f"${current_price:.4f}"
            else:
                current_price_str = entry_price_str  # Fallback to entry if no current price
            
            row_elements = [
                html.Span(f"{pos['coin']} ", style={'color': '#00ff41', 'fontWeight': 'bold', 'marginRight': '3px', 'fontSize': '10px'}),
                html.Span("(", style={'color': '#888', 'fontSize': '11px'}),
                html.Span(f"{entry_price_str}", style={'color': '#00ff00', 'fontSize': '11px'}),
                html.Span(" entry) ", style={'color': '#888', 'fontSize': '11px', 'marginRight': '3px'}),
                html.Span("(", style={'color': '#888', 'fontSize': '11px'}),
                html.Span(f"{current_price_str}", style={'color': '#00ff00', 'fontSize': '11px'}),
                html.Span(" now) ", style={'color': '#888', 'fontSize': '11px', 'marginRight': '3px'}),
                html.Span("(", style={'color': '#888', 'fontSize': '11px'}),
                html.Span(f"{pos['entries']}/3", style={'color': '#00ff00', 'fontSize': '11px'}),
                html.Span(") ", style={'color': '#888', 'fontSize': '11px', 'marginRight': '3px'}),
                html.Span(" | ", style={'color': '#888', 'fontSize': '11px', 'marginRight': '3px'}),
                html.Span("Size: ", style={'color': '#888', 'fontSize': '11px'}),
                html.Span(f"${pos['total_size']:.2f} ", style={'color': '#00ff00', 'fontSize': '11px', 'marginRight': '3px'}),
            ]
            
            # Add P&L if available
            if pos['pnl_usd'] is not None and pos['pnl_pct'] is not None:
                row_elements.append(html.Span(" | ", style={'color': '#888', 'fontSize': '11px', 'marginRight': '3px'}))
                row_elements.append(html.Span("P&L: ", style={'color': '#888', 'fontSize': '11px'}))
                
                pnl_color = '#00ff00' if pos['pnl_usd'] > 0 else '#ff0000' if pos['pnl_usd'] < 0 else '#888'
                pnl_glow = '0 0 5px #00ff00' if pos['pnl_usd'] > 0 else '0 0 5px #ff0000' if pos['pnl_usd'] < 0 else 'none'
                pnl_sign = '+' if pos['pnl_usd'] > 0 else ''
                
                row_elements.append(html.Span([
                    html.Span(f"{pnl_sign}${pos['pnl_usd']:.2f} ", style={'color': pnl_color, 'fontWeight': 'bold', 'fontSize': '11px', 'textShadow': pnl_glow}),
                    html.Span(f"({pnl_sign}{pos['pnl_pct']:.2f}%)", style={'color': pnl_color, 'fontSize': '11px'})
                ]))
            
            # Add CLOSE button
            row_elements.append(
                dbc.Button(
                    "CLOSE",
                    id={'type': 'close-position-btn', 'coin': pos['coin']},
                    size='sm',
                    color='danger',
                    style={
                        'fontSize': '8px',
                        'padding': '2px 8px',
                        'marginLeft': '8px',
                        'fontWeight': 'bold'
                    }
                )
            )
            
            position_rows.append(
                html.Div(row_elements, style={
                    'padding': '4px 8px',
                    'borderBottom': '1px solid #003311',
                    'fontSize': '10px'
                })
            )
    else:
        position_rows.append(
            html.Div(
                "(No positions)",
                style={'textAlign': 'center', 'color': '#666', 'padding': '10px', 'fontStyle': 'italic', 'fontSize': '12px'}
            )
        )
    
    # Trade log with P&L
    trade_rows = []
    if bot_status['recent_trades']:
        # Get list of active position coins
        active_coins = [pos['coin'] for pos in bot_status['positions']]
        
        # Reverse order to show newest first (top to bottom)
        for trade in reversed(bot_status['recent_trades'][-20:]):  # Last 20 trades, newest first
            # Calculate P&L if current price available
            coin = trade['coin']
            entry_price = trade['price']
            trade_size = trade['size']
            
            # Check if position is closed (coin not in active positions)
            is_closed = coin not in active_coins
            
            pnl_element = None
            if coin in current_prices:
                current_price = current_prices.get(coin, entry_price)
                pnl_usd = (current_price - entry_price) / entry_price * trade_size
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                
                if pnl_usd > 0:
                    pnl_element = html.Span([
                        html.Span(f"+${pnl_usd:.2f} ⬆ ", style={'color': '#00ff00', 'fontWeight': 'bold', 'fontSize': '11px', 'textShadow': '0 0 5px #00ff00'}),
                        html.Span(f"+{pnl_pct:.2f}%", style={'color': '#00ff00', 'fontSize': '11px'})
                    ], style={'marginLeft': '5px'})
                elif pnl_usd < 0:
                    pnl_element = html.Span([
                        html.Span(f"${pnl_usd:.2f} ⬇ ", style={'color': '#ff0000', 'fontWeight': 'bold', 'fontSize': '11px', 'textShadow': '0 0 5px #ff0000'}),
                        html.Span(f"{pnl_pct:.2f}%", style={'color': '#ff0000', 'fontSize': '11px'})
                    ], style={'marginLeft': '5px'})
                else:
                    pnl_element = html.Span([
                        html.Span(f"$0.00 → ", style={'color': '#888', 'fontSize': '11px'}),
                        html.Span(f"0.00%", style={'color': '#888', 'fontSize': '11px'})
                    ], style={'marginLeft': '5px'})
            
            row_elements = [
                html.Span(f"{trade['time']} ", style={'color': '#888', 'marginRight': '5px', 'fontSize': '11px'}),
                html.Span(f"{coin} ", style={'color': '#00ff41', 'fontWeight': 'bold', 'marginRight': '3px', 'fontSize': '10px'}),
                html.Span(f"${entry_price:,.2f} " if entry_price >= 1 else f"${entry_price:.4f} ", style={'color': '#00ff00', 'marginRight': '3px', 'fontSize': '11px'}),
                html.Span(f"({trade['entry_num']}/3)", style={'color': '#666', 'fontSize': '11px'})
            ]
            
            if pnl_element:
                row_elements.append(pnl_element)
            
            # Add [CLOSED] indicator with realized P&L if position is closed
            if is_closed:
                # Check if exit data is saved
                if 'exit_pnl_usd' in trade and 'exit_pnl_pct' in trade:
                    # Show realized P&L from saved exit data
                    exit_pnl_usd = trade['exit_pnl_usd']
                    exit_pnl_pct = trade['exit_pnl_pct']
                    pnl_sign = '+' if exit_pnl_usd >= 0 else ''
                    row_elements.append(
                        html.Span(
                            f" [CLOSED {pnl_sign}${exit_pnl_usd:.2f} {pnl_sign}{exit_pnl_pct:.2f}%]",
                            style={'color': '#666', 'fontSize': '10px', 'fontWeight': 'bold', 'marginLeft': '5px'}
                        )
                    )
                else:
                    # No exit data saved, just show CLOSED
                    row_elements.append(
                        html.Span(" [CLOSED]", style={'color': '#666', 'fontSize': '10px', 'fontWeight': 'bold', 'marginLeft': '5px'})
                    )
            
            trade_rows.append(
                html.Div(row_elements, style={
                    'padding': '3px 8px',
                    'borderBottom': '1px solid #003311',
                    'fontSize': '10px'
                })
            )
    else:
        trade_rows.append(
            html.Div(
                "(No trades yet)",
                style={'textAlign': 'center', 'color': '#666', 'padding': '10px', 'fontStyle': 'italic', 'fontSize': '12px'}
            )
        )
    
    component = dbc.Card([
        dbc.CardHeader([
            dbc.Row([
                dbc.Col([
                    html.H6(
                        "BOT STATUS",
                        className="mb-0",
                        style={
                            'color': '#00ff41',
                            'fontSize': '12px',
                            'fontWeight': 'bold',
                            'textShadow': '0 0 8px #00ff41'
                        }
                    )
                ], width=7),
                dbc.Col([
                    dbc.Button(
                        "START" if not bot_status['is_active'] else "STOP",
                        id='bot-toggle-button',
                        size='sm',
                        color='success' if not bot_status['is_active'] else 'danger',
                        style={
                            'fontSize': '10px',
                            'padding': '2px 10px',
                            'fontWeight': 'bold'
                        }
                    )
                ], width=5, className="text-end")
            ], align="center")
        ], style={'padding': '6px', 'backgroundColor': '#000000', 'borderBottom': '2px solid #00ff41'}),
        
        dbc.CardBody([
            # Bot Status
            html.Div([
                html.Span(status_text, style={
                    'color': status_color,
                    'fontSize': '14px',
                    'fontWeight': 'bold',
                    'textShadow': status_glow
                })
            ], style={'textAlign': 'center', 'marginBottom': '10px'}),
            
            # Budget Display
            html.Div([
                html.Div("BUDGET", style={'color': '#00ff41', 'fontSize': '10px', 'fontWeight': 'bold', 'marginBottom': '5px'}),
                html.Div([
                    html.Span(f"${bot_status.get('notional_spent', 0):.2f}", style={'color': '#ff6666', 'fontSize': '13px', 'fontWeight': 'bold'}),
                    html.Span(" / ", style={'color': '#666', 'fontSize': '12px'}),
                    html.Span(f"${bot_status.get('notional_total', 0):.2f}", style={'color': '#00ff41', 'fontSize': '13px', 'fontWeight': 'bold'}),
                    html.Span(" / ", style={'color': '#666', 'fontSize': '12px'}),
                    html.Span(
                        f"{'+' if total_pnl_usd >= 0 else ''}${total_pnl_usd:.2f}",
                        style={
                            'color': '#00ff00' if total_pnl_usd > 0 else '#ff0000' if total_pnl_usd < 0 else '#888',
                            'fontSize': '11px',
                            'fontWeight': 'bold',
                            'textShadow': '0 0 5px #00ff00' if total_pnl_usd > 0 else '0 0 5px #ff0000' if total_pnl_usd < 0 else 'none'
                        }
                    ),
                    html.Span(" / ", style={'color': '#666', 'fontSize': '10px'}),
                    html.Span(
                        f"{'+' if total_pnl_pct >= 0 else ''}{total_pnl_pct:.2f}% {'⬆' if total_pnl_pct > 0 else '⬇' if total_pnl_pct < 0 else '→'}",
                        style={
                            'color': '#00ff00' if total_pnl_pct > 0 else '#ff0000' if total_pnl_pct < 0 else '#888',
                            'fontSize': '11px',
                            'fontWeight': 'bold'
                        }
                    )
                ], style={'marginBottom': '5px'}),
                # Budget bar
                html.Div([
                    html.Div(style={
                        'width': f'{budget_pct}%',
                        'height': '8px',
                        'backgroundColor': '#00ff41' if budget_pct < 80 else '#ff6666',
                        'borderRadius': '4px',
                        'boxShadow': f'0 0 10px {"#00ff41" if budget_pct < 80 else "#ff6666"}',
                        'transition': 'width 0.3s ease'
                    })
                ], style={
                    'width': '100%',
                    'height': '8px',
                    'backgroundColor': '#003311',
                    'borderRadius': '4px',
                    'border': '1px solid #00ff41',
                    'marginBottom': '10px'
                })
            ], style={'marginBottom': '15px'}),
            
            # Active Positions
            html.Div([
                html.Div(
                    f"POSITIONS ({bot_status['total_coins']} coins, {bot_status['total_entries']} entries)",
                    style={'color': '#00ff41', 'fontSize': '10px', 'fontWeight': 'bold', 'marginBottom': '5px'}
                ),
                html.Div(
                    position_rows,
                    style={
                        'maxHeight': '450px',
                        'overflowY': 'hidden',
                        'border': '1px solid #003311',
                        'borderRadius': '3px',
                        'marginBottom': '15px'
                    }
                )
            ]),
            
            # Recent Trades
            html.Div([
                html.Div(
                    "RECENT TRADES",
                    style={'color': '#00ff41', 'fontSize': '10px', 'fontWeight': 'bold', 'marginBottom': '5px'}
                ),
                html.Div(
                    trade_rows,
                    style={
                        'maxHeight': '450px',
                        'overflowY': 'hidden',
                        'border': '1px solid #003311',
                        'borderRadius': '3px'
                    }
                )
            ])
            
        ], style={'padding': '10px', 'backgroundColor': '#000000'})
        
    ], style={
        'backgroundColor': '#000000',
        'border': '2px solid #00ff41',
        'boxShadow': '0 0 15px #00ff41',
        'height': '100%'
    })
    
    return component

