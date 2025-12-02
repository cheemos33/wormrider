"""
Main Dash Application for Trading Terminal - Screen 1
"""
from dash import Dash, html, dcc, Input, Output, State, callback_context, ALL, MATCH
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from datetime import datetime

# Import local modules
from config import config
from data.hyperliquid_api import api_client, api_client_testnet
from data.watchlist_manager import watchlist_manager
from data.data_processor import prepare_spaghetti_data, get_current_prices_and_changes
from components.watchlist import create_watchlist_component
from components.spaghetti import create_spaghetti_chart, create_empty_chart
from components.signal_feed import create_signal_feed
from components.alerts import create_alerts_component
from components.val_plotter import create_val_plotter
from components.rsi_plotter import create_rsi_plotter
from components.important_placeholder import create_important_placeholder
from components.plotter_4 import create_plotter_4
from components.analytics_dashboard import create_analytics_layout, create_signals_table
from trading.signal_trader import SignalTrader
from data.analytics_db import analytics_db

# Initialize Dash app with dark Bootstrap theme
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True
)

app.title = "Crypto Trading Terminal"

# Global state
coin_universe = []
signal_trader = SignalTrader(api_client, budget=50.0, position_size=10.0)  # MAINNET - 4x leverage = $200 notional


def create_header():
    """Create the header section"""
    return dbc.Row([
        dbc.Col([
            html.Div([
                html.H2(
                    "🐼 terminal nrlns003",
                    style={'color': '#00ff41', 'fontSize': '32px', 'textShadow': '0 0 10px #00ff41', 'fontFamily': 'Courier New, monospace', 'letterSpacing': '2px', 'display': 'inline-block', 'marginRight': '20px'}
                ),
                html.Div(
                    id='update-countdown',
                    style={'display': 'inline-block', 'color': '#00ff41', 'fontSize': '12px', 'verticalAlign': 'middle', 'marginRight': '20px'}
                ),
                dcc.Link(
                    dbc.Button(
                        "🍌 ANALYTICS",
                        color='success',
                        outline=True,
                        size='sm',
                        style={
                            'fontSize': '10px',
                            'fontWeight': 'bold',
                            'padding': '4px 12px',
                            'backgroundColor': 'transparent',
                            'boxShadow': '0 0 10px #00ff41'
                        }
                    ),
                    href='/analytics',
                    style={'display': 'inline-block'}
                )
            ], style={'textAlign': 'center', 'marginTop': '10px', 'marginBottom': '10px'})
        ])
    ])


def create_layout():
    """Create the main application layout"""
    return dbc.Container([
        # Header
        create_header(),
        
        # Main Row - Spaghetti Chart + Stacked Components
        dbc.Row([
            # Left Column - Spaghetti Chart + VAL Plotter
            dbc.Col([
                # Spaghetti Chart (UNCHANGED)
                dcc.Graph(
                    id='spaghetti-chart',
                    figure=create_empty_chart(),
                    style={'height': '920px'}
                ),
                
                # Plotters Row (VAL + RSI + IMPORTANT + PLOTTER 4) - 4 equal columns
                dbc.Row([
                    dbc.Col([
                        html.Div(id='val-plotter-container')
                    ], width=3),
                    dbc.Col([
                        html.Div(id='rsi-plotter-container')
                    ], width=3),
                    dbc.Col([
                        html.Div(id='important-placeholder-container')
                    ], width=3),
                    dbc.Col([
                        html.Div(id='plotter-4-container')
                    ], width=3)
                ], style={'marginTop': '15px'})
            ], width=8, style={'paddingRight': '10px'}),
            
            # Right Column - Stacked: Bot Status, Watchlist, Signals (30%)
            dbc.Col([
                # 1. BOT STATUS / ALERTS (top)
                html.Div(id='alerts-container', style={'marginBottom': '15px'}),
                
                # 2. MY WATCHLIST (middle)
                html.Div(id='watchlist-container', style={'marginBottom': '15px'}),
                
                # 3. LATEST SIGNALS (bottom)
                html.Div(id='signal-feed-container')
            ], width=4, style={'paddingLeft': '10px'})
        ], style={'marginTop': '10px'}),
        
        # Update Interval (triggers every 1 minute)
        dcc.Interval(
            id='update-interval',
            interval=config.UPDATE_INTERVAL_SECONDS * 1000,  # in milliseconds
            n_intervals=0
        ),
        
        # Store for coin universe (loaded once)
        dcc.Store(id='coin-universe-store', data=[]),
        
        # Store for watchlist data
        dcc.Store(id='watchlist-store', data=[]),
        
        # Store for last update time
        dcc.Store(id='last-update-time', data=0),
        
        # Fast interval for countdown (every second)
        dcc.Interval(
            id='countdown-interval',
            interval=1000,  # 1 second
            n_intervals=0
        ),
        
    ], fluid=True, style={'backgroundColor': '#000000', 'minHeight': '100vh'})


# Main layout with URL routing
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])


# URL routing callback
@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname')]
)
def display_page(pathname):
    """Route to correct page based on URL"""
    if pathname == '/analytics':
        return create_analytics_layout()
    else:  # Default to trading terminal
        return create_layout()


@app.callback(
    Output('coin-universe-store', 'data'),
    [Input('update-interval', 'n_intervals')],
    [State('coin-universe-store', 'data')],
    prevent_initial_call=False
)
def load_coin_universe(n, current_coins):
    """Load coin universe once on startup and keep it"""
    if n == 0 or not current_coins:  # Load on first run or if empty
        print("Loading coin universe from Hyperliquid...")
        coins = api_client.fetch_coin_universe()
        print(f"Loaded {len(coins)} coins")
        print(f"First 20 coins: {coins[:20]}")
        print(f"Last 20 coins: {coins[-20:]}")
        return coins
    return current_coins  # Keep returning the same list


@app.callback(
    [Output('watchlist-container', 'children'),
     Output('watchlist-store', 'data'),
     Output('signal-feed-container', 'children'),
     Output('alerts-container', 'children'),
     Output('val-plotter-container', 'children'),
     Output('rsi-plotter-container', 'children'),
     Output('important-placeholder-container', 'children'),
     Output('plotter-4-container', 'children'),
     Output('last-update-time', 'data')],
    [Input('update-interval', 'n_intervals'),
     Input({'type': 'watchlist-table', 'index': ALL}, 'active_cell'),
     Input({'type': 'add-coin-button', 'index': ALL}, 'n_clicks')],
    [State('coin-universe-store', 'data'),
     State({'type': 'watchlist-table', 'index': ALL}, 'data'),
     State({'type': 'coin-search-dropdown', 'index': ALL}, 'value')],
    prevent_initial_call=False
)
def update_watchlist(n_intervals, active_cells, add_clicks, coin_universe, table_data_list, dropdown_values):
    """Update watchlist component, signal feed, and bot status"""
    
    ctx = callback_context
    
    # Load current active coins
    active_coins = watchlist_manager.load_active_coins()
    
    # Handle add coin button
    if ctx.triggered and any('add-coin-button' in str(t['prop_id']) for t in ctx.triggered):
        if dropdown_values and dropdown_values[0]:
            selected_coin = dropdown_values[0]
            success, message = watchlist_manager.add_coin(selected_coin)
            if success:
                # Auto-activate newly added coin
                active_coins = watchlist_manager.load_active_coins()
                if selected_coin not in active_coins:
                    active_coins.append(selected_coin)
                    watchlist_manager.save_active_coins(active_coins)
            print(f"➕ {message}")
    
    # Handle checkbox toggle (click on Show column)
    if ctx.triggered and any('watchlist-table' in str(t['prop_id']) for t in ctx.triggered):
        if active_cells and active_cells[0] and table_data_list and table_data_list[0]:
            try:
                active_cell = active_cells[0]
                table_data = table_data_list[0]
                row_idx = active_cell['row']
                col_idx = active_cell['column']
                
                # Check if clicked on Show column (checkbox)
                if col_idx == 0:  # Show column is index 0
                    clicked_coin = table_data[row_idx]['Coin']
                    if clicked_coin in active_coins:
                        active_coins.remove(clicked_coin)
                        print(f"☐ {clicked_coin} hidden from chart")
                    else:
                        active_coins.append(clicked_coin)
                        print(f"☑ {clicked_coin} shown on chart")
                    watchlist_manager.save_active_coins(active_coins)
                
                # Check if clicked on Remove column
                elif col_idx == 9:  # Remove column is now index 9 (Show=0, Signal=1, Coin=2, ..., Remove=9)
                    coin_to_remove = table_data[row_idx]['Coin']
                    success, message = watchlist_manager.remove_coin(coin_to_remove)
                    # Also remove from active coins
                    if coin_to_remove in active_coins:
                        active_coins.remove(coin_to_remove)
                        watchlist_manager.save_active_coins(active_coins)
                    print(f"✕ {message}")
            except Exception as e:
                print(f"Error handling table click: {e}")
    
    # Load current watchlist
    watchlist = watchlist_manager.load_watchlist()
    
    # Get current prices and changes
    watchlist_data = get_current_prices_and_changes(watchlist)
    
    # Get coin universe - use from store, or fetch fresh if empty
    if not coin_universe or len(coin_universe) == 0:
        print("Coin universe empty, fetching from API...")
        coin_universe = api_client.fetch_coin_universe()
        if not coin_universe:
            coin_universe = api_client._get_fallback_coins()
    
    print(f"Using coin universe with {len(coin_universe)} coins")
    print(f"Active coins: {len(active_coins)}/{len(watchlist)}")
    
    # Detect new signals and add to history (only 3★ and 4★)
    for item in watchlist_data:
        rsi = item.get('rsi', 50)
        val = item.get('val_distance', 0)
        rvwap_1d = item.get('rvwap_1d_distance', 0)
        rvwap_7d = item.get('rvwap_7d_distance', 0)
        
        # Calculate star rating based on 4 criteria
        criteria_met = 0
        if rsi < 20:  # RSI oversold threshold (PRODUCTION)
            criteria_met += 1
        if val < 0:  # VAL threshold (below VAL line - PRODUCTION)
            criteria_met += 1
        if rvwap_1d < 0:
            criteria_met += 1
        if rvwap_7d < 0:
            criteria_met += 1
        
        stars = criteria_met  # 0-4 stars based on criteria
        
        # Save all 4★ signal instances (no duplicate filtering)
        if stars == 4:
            price = item.get('price', 0)
            change_24h = item.get('change_24h', 0)
            watchlist_manager.add_signal(
                item['coin'], stars, rsi, val, price,
                rvwap_1d, rvwap_7d, change_24h
            )
    
    # Bot Logic: Check BTC position and process signals
    print("🔧 DEBUG: Bot logic section starting...")
    try:
        # Check if BTC position exists on mainnet
        print("🔧 DEBUG: About to call check_btc_position()")
        btc_pos = signal_trader.check_btc_position()
        print(f"🔧 DEBUG: check_btc_position() returned: {btc_pos}")
        
        # Auto-activate if BTC position found and bot not active
        if btc_pos and not signal_trader.is_active:
            signal_trader.activate()
            signal_trader.btc_position = btc_pos
        
        # Auto-deactivate if BTC position closed and bot is active
        if not btc_pos and signal_trader.is_active:
            signal_trader.deactivate()
            signal_trader.btc_position = None
        
        # Process signals if bot is active
        if signal_trader.is_active:
            # Get 4★ signals from watchlist data (recalculate stars)
            four_star_signals = []
            for item in watchlist_data:
                rsi = item.get('rsi', 50)
                val = item.get('val_distance', 0)
                rvwap_1d = item.get('rvwap_1d_distance', 0)
                rvwap_7d = item.get('rvwap_7d_distance', 0)
                
                # Check if this is a 4★ signal
                # NOTE: If you change RSI threshold here, also update RSI plotter line in rsi_plotter.py
                criteria_met = 0
                if rsi < 20:  # RSI oversold threshold (PRODUCTION)
                    criteria_met += 1
                if val < 0:  # VAL threshold (below VAL line - PRODUCTION)
                    criteria_met += 1
                if rvwap_1d < 0:
                    criteria_met += 1
                if rvwap_7d < 0:
                    criteria_met += 1
                
                if criteria_met == 4:
                    # Add all needed data for dip score calculation
                    signal_data = {
                        'coin': item['coin'],
                        'price': item['price'],
                        'rsi': rsi,
                        'val_distance': val,
                        'rvwap_1d_distance': rvwap_1d,
                        'rvwap_7d_distance': rvwap_7d,
                        'timestamp': datetime.now().isoformat()
                    }
                    four_star_signals.append(signal_data)
            
            if four_star_signals:
                # Process signals (will execute 1 trade if conditions met)
                trade_result = signal_trader.process_signals(four_star_signals)
                if trade_result:
                    print(f"✅ Trade executed: {trade_result}")
    
    except Exception as e:
        print(f"Bot error: {e}")
    
    # Create watchlist component
    component = create_watchlist_component(watchlist_data, coin_universe, active_coins)
    
    # Create signal feed with current prices for % change calculation
    signal_history = watchlist_manager.load_signal_history()
    # Create a dict of current prices for easy lookup
    current_prices = {item['coin']: item['price'] for item in watchlist_data}
    # Show last 60 signals (scrollable)
    signal_feed = create_signal_feed(signal_history, current_prices, 'all', 60)
    
    # Get bot status and create alerts component (pass current_prices for P&L)
    bot_status = signal_trader.get_status(current_prices)
    alerts_component = create_alerts_component(bot_status, current_prices)
    
    # Create VAL plotter component
    val_plotter = create_val_plotter(watchlist_data)
    
    # Create RSI plotter component
    rsi_plotter = create_rsi_plotter(watchlist_data)
    
    # Create IMPORTANT placeholder component
    important_placeholder = create_important_placeholder()
    
    # Create PLOTTER 4 placeholder component
    plotter_4 = create_plotter_4()
    
    # Store current time for countdown
    import time
    current_time = time.time()
    
    return component, watchlist_data, signal_feed, alerts_component, val_plotter, rsi_plotter, important_placeholder, plotter_4, current_time


@app.callback(
    Output('update-countdown', 'children'),
    [Input('countdown-interval', 'n_intervals')],
    [State('last-update-time', 'data')]
)
def update_countdown(n, last_update):
    """Update the countdown timer"""
    import time
    
    if not last_update or last_update == 0:
        return "Updating..."
    
    # Calculate time since last update
    elapsed = time.time() - last_update
    remaining = max(0, 60 - int(elapsed))
    
    if remaining == 0:
        return "Updating..."
    
    return f"Next: {remaining}s"


@app.callback(
    Output('spaghetti-chart', 'figure'),
    [Input('update-interval', 'n_intervals'),
     Input('watchlist-store', 'data')]
)
def update_chart(n_intervals, watchlist_data):
    """Update spaghetti chart with latest data (only active coins)"""
    
    if not watchlist_data:
        return create_empty_chart()
    
    # Load active coins (those with checkboxes checked)
    active_coins = watchlist_manager.load_active_coins()
    
    # Filter to only active coins
    active_coin_names = [item['coin'] for item in watchlist_data if item['coin'] in active_coins]
    
    if not active_coin_names:
        # No coins selected, show empty chart with message
        fig = create_empty_chart()
        return fig
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Updating chart for {len(active_coin_names)} active coins...")
    
    # Fetch 24h data for active coins only
    all_coin_data = prepare_spaghetti_data(active_coin_names)
    
    if not all_coin_data:
        return create_empty_chart()
    
    # Create chart
    fig = create_spaghetti_chart(all_coin_data)
    
    print(f"Chart updated successfully with {len(all_coin_data)} coins")
    
    return fig


@app.callback(
    Output('alerts-container', 'children', allow_duplicate=True),
    [Input('bot-toggle-button', 'n_clicks')],
    [State('alerts-container', 'children')],
    prevent_initial_call=True
)
def toggle_bot(n_clicks, current_alerts):
    """Toggle bot activation manually"""
    if n_clicks:
        if signal_trader.is_active:
            signal_trader.deactivate()
        else:
            # Manually activate bot (bypasses BTC check)
            success = signal_trader.activate()
            if not success:
                print("❌ Bot activation failed - check balance")
        
        # Return updated alerts component
        bot_status = signal_trader.get_status()
        return create_alerts_component(bot_status, {})
    
    return current_alerts


@app.callback(
    Output('alerts-container', 'children', allow_duplicate=True),
    [Input({'type': 'close-position-btn', 'coin': ALL}, 'n_clicks')],
    [State('watchlist-store', 'data')],
    prevent_initial_call=True
)
def close_position(n_clicks_list, watchlist_data):
    """Close a specific position"""
    print(f"🔵🔵🔵 CLOSE CALLBACK ENTERED! 🔵🔵🔵")
    from dash import ctx
    
    print(f"🔵 Close callback triggered! n_clicks_list: {n_clicks_list}")
    print(f"🔵 ctx.triggered: {ctx.triggered if ctx.triggered else 'None'}")
    
    if not ctx.triggered or not any(n_clicks_list):
        print(f"⚠️ Close callback prevented - no trigger or no clicks")
        raise PreventUpdate
    
    # Get which button was clicked
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    import json
    button_data = json.loads(button_id)
    coin = button_data['coin']
    
    print(f"🔴 Close button clicked for {coin}")
    
    # Close position on Hyperliquid and update tracking
    success = signal_trader.close_position(coin)
    
    if success:
        print(f"✅ {coin} position closed successfully")
    else:
        print(f"❌ Failed to close {coin} position")
    
    # Get current prices for P&L
    current_prices = {item['coin']: item['price'] for item in watchlist_data}
    
    # Return updated alerts component
    bot_status = signal_trader.get_status(current_prices)
    return create_alerts_component(bot_status, current_prices)


# Analytics page callbacks
@app.callback(
    [Output('analytics-table-container', 'children'),
     Output('analytics-live-interval', 'disabled')],
    [Input('analytics-refresh-btn', 'n_clicks'),
     Input('analytics-live-interval', 'n_intervals'),
     Input('analytics-coin-filter', 'value'),
     Input('analytics-traded-filter', 'value'),
     Input('analytics-status-filter', 'value'),
     Input('analytics-live-mode', 'value')],
    prevent_initial_call=False
)
def update_analytics_table(n_clicks, n_intervals, coin_filter, traded_filter, status_filter, live_mode):
    """Update analytics table based on filters and refresh"""
    
    # Apply filters
    coin = None if coin_filter == 'all' else coin_filter
    traded = None if traded_filter == 'all' else (True if traded_filter == 'traded' else False)
    status = None if status_filter == 'all' else status_filter
    
    # Fetch filtered data
    signals = analytics_db.get_filtered_signals(
        coin=coin,
        traded=traded,
        trade_status=status,
        limit=1000
    )
    
    # Fetch current prices for gain calculation
    try:
        # Get watchlist with current prices
        watchlist = watchlist_manager.load_watchlist()
        watchlist_data = get_current_prices_and_changes(watchlist)
        current_prices = {item['coin']: item['price'] for item in watchlist_data}
        print(f"📊 Analytics: Fetched {len(current_prices)} coin prices for gain calculation")
    except Exception as e:
        print(f"❌ Error fetching prices for analytics: {e}")
        current_prices = {}
    
    # Create table with current prices
    table = create_signals_table(signals, current_prices)
    
    # Enable/disable live mode interval
    interval_disabled = 'live' not in live_mode
    
    return table, interval_disabled


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🐻 CRYPTO TRADING TERMINAL - nrlns003")
    print("="*60)
    print(f"Dashboard starting at http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}")
    print("Trading Terminal: http://localhost:8050/")
    print("Analytics: http://localhost:8050/analytics")
    print("="*60 + "\n")
    
    app.run(
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        debug=config.DASHBOARD_DEBUG
    )

