"""Main Wormrider application - Scalping Strategy with Minimal UI."""

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
from strategy.paper_trading import paper_monitor

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

# Start background cleanup
def cleanup_task():
    while True:
        time.sleep(3600)  # Every hour
        db.cleanup_old_data(config.RETENTION_DAYS)  # 30-day retention for snapshots
        db.cleanup_old_trades(hours=24)  # 24h retention for trades
        db.cleanup_old_aggregated(hours=24)  # 24h retention for aggregated order book

cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
cleanup_thread.start()

# Start paper trading monitor
paper_monitor.start()

# Create Dash app
app = Dash(__name__)
app.title = "Wormrider - Scalping"

# Global variable to track previous CVD slope for reversal detection
previous_cvd_slope = 'neutral'

# Layout - Minimal UI for Scalping Signals
app.layout = html.Div([
    html.Div([
        html.H1("wormrider - BTCUSDT Scalping", style={'margin': '10px', 'color': '#e5e7eb', 'flex': '1'}),
        html.Div(id='status-text', children='Loading...', 
                style={'margin': '10px', 'color': '#9ca3af', 'fontSize': '12px'}),
    ], style={'background': '#1f2937', 'padding': '10px', 'borderRadius': '8px', 'marginBottom': '10px', 'display': 'flex', 'alignItems': 'center'}),
    
    # Row 1: Market State & Active Signal
    html.Div([
        html.Div([
            html.H3("📊 Current Market State", style={'color': '#e5e7eb', 'fontSize': '16px', 'marginBottom': '15px'}),
            html.Div(id='market-state', children='Loading market data...',
                    style={'color': '#9ca3af', 'fontSize': '14px'})
        ], style={'background': '#0f172a', 'padding': '15px', 'borderRadius': '8px', 'flex': '1', 'marginRight': '5px'}),
        
        html.Div([
            html.H3("🎯 Active Signal", style={'color': '#e5e7eb', 'fontSize': '16px', 'marginBottom': '15px'}),
            html.Div(id='active-signal', children='No active signal',
                    style={'color': '#9ca3af', 'fontSize': '14px'})
        ], style={'background': '#0f172a', 'padding': '15px', 'borderRadius': '8px', 'flex': '1', 'marginLeft': '5px'})
    ], style={'display': 'flex', 'marginBottom': '10px'}),
    
    # Row 2: Recent Signals & Session Stats
    html.Div([
        html.Div([
            html.H3("📈 Recent Signals", style={'color': '#e5e7eb', 'fontSize': '16px', 'marginBottom': '15px'}),
            html.Div(id='recent-signals', children='No signals yet',
                    style={'color': '#9ca3af', 'fontSize': '14px'})
        ], style={'background': '#0f172a', 'padding': '15px', 'borderRadius': '8px', 'flex': '1', 'marginRight': '5px'}),
        
        html.Div([
            html.H3("📊 Session Stats", style={'color': '#e5e7eb', 'fontSize': '16px', 'marginBottom': '15px'}),
            html.Div(id='session-stats', children='No data yet',
                    style={'color': '#9ca3af', 'fontSize': '14px'})
        ], style={'background': '#0f172a', 'padding': '15px', 'borderRadius': '8px', 'flex': '1', 'marginLeft': '5px'})
    ], style={'display': 'flex', 'marginBottom': '10px'}),
    
    # Auto-refresh interval
    dcc.Interval(
        id='interval-component',
        interval=5000,  # 5 seconds
        n_intervals=0
    )
], style={'padding': '20px', 'background': '#0b0f16', 'minHeight': '100vh'})


@app.callback(
    [Output('market-state', 'children'),
     Output('active-signal', 'children'),
     Output('recent-signals', 'children'),
     Output('session-stats', 'children'),
     Output('status-text', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n_intervals):
    """Update all dashboard components."""
    global previous_cvd_slope
    
    # Get latest snapshot
    snapshot = db.get_latest_snapshot("BTCUSDT")
    
    if not snapshot:
        return (
            "⏳ Waiting for data...",
            "⏳ No active signal",
            "📝 No signals yet",
            "📊 No data yet",
            "Waiting for data..."
        )
    
    # Update paper monitor with current price
    current_price = snapshot['mid_price']
    paper_monitor.update_price(current_price)
    
    # ========== SIGNAL GENERATION ENGINE ==========
    # Check if we already have an active or pending signal
    active_signal = db.get_active_signal()
    pending_signal = db.get_pending_signal()
    
    if not active_signal and not pending_signal:
        # No active signals - try to generate new one
        
        # 1. Get aggregated order book (latest)
        agg_snapshot = db.get_latest_aggregated_snapshot("BTCUSDT", 100)
        
        if agg_snapshot:
            agg_bids = agg_snapshot['bids']
            agg_asks = agg_snapshot['asks']
            
            # 2. Calculate imbalance (with 54% threshold for signals)
            imbalance_data = orderbook_scalping.calculate_imbalance(
                agg_bids=agg_bids,
                agg_asks=agg_asks,
                current_price=current_price,
                num_bins=2  # 2 bins = $200 range
            )
            
            # 3. Get CVD for 5-minute window
            five_min_ago = int(time.time() * 1000) - (5 * 60 * 1000)
            current_time_ms = int(time.time() * 1000)
            trades_5m = db.get_trades_range("BTCUSDT", five_min_ago, current_time_ms)
            
            if trades_5m:
                cvd_data = cvd.calculate_cvd(trades_5m, window_minutes=5)
                current_cvd_slope = cvd_data['slope']
                
                # 4. Check CVD reversal
                cvd_reversal_data = orderbook_scalping.check_cvd_reversal(
                    current_slope=current_cvd_slope,
                    previous_slope=previous_cvd_slope
                )
                
                # 5. Generate signal if conditions met
                if imbalance_data and cvd_reversal_data:
                    signal = orderbook_scalping.generate_signal(
                        imbalance_data=imbalance_data,
                        cvd_reversal_data=cvd_reversal_data,
                        current_price=current_price,
                        tp_distance=120.0,
                        sl_distance=130.0
                    )
                    
                    if signal:
                        # Store signal in database
                        signal['timestamp'] = current_time_ms
                        db.insert_signal(signal)
                        
                        print(f"\n{'='*60}")
                        print(f"🎯 NEW SIGNAL GENERATED")
                        print(f"   Direction: {signal['direction'].upper()}")
                        print(f"   Entry: ${signal['entry_price']:,.2f}")
                        print(f"   TP: ${signal['tp_price']:,.2f} | SL: ${signal['sl_price']:,.2f}")
                        print(f"   Imbalance: {signal['imbalance_ratio']*100:.1f}%")
                        print(f"   CVD: {signal['cvd_slope']}")
                        print(f"{'='*60}\n")
                
                # Update previous CVD slope for next iteration
                previous_cvd_slope = current_cvd_slope
    
    # ========== END SIGNAL GENERATION ==========
    
    # 1. Market State (display any imbalance, no threshold)
    agg_snapshot = db.get_latest_aggregated_snapshot("BTCUSDT", 100)
    if agg_snapshot:
        agg_bids = agg_snapshot['bids']
        agg_asks = agg_snapshot['asks']
        
        # Calculate 2-bin imbalance for display (no threshold)
        imbalance_data = orderbook_scalping.calculate_imbalance_display(
            agg_bids=agg_bids,
            agg_asks=agg_asks,
            current_price=current_price,
            num_bins=2
        )
        
        if imbalance_data:
            direction_emoji = "🔴" if imbalance_data['direction'] == 'long' else "🟢"
            market_state = f"""
            💰 Price: ${current_price:,.2f}<br>
            {direction_emoji} Imbalance: {imbalance_data['direction'].upper()} ({imbalance_data['imbalance_ratio']*100:.1f}%)<br>
            📊 Bid Volume: {imbalance_data['bid_volume']:,.2f}<br>
            📊 Ask Volume: {imbalance_data['ask_volume']:,.2f}
            """
        else:
            market_state = f"💰 Price: ${current_price:,.2f}<br>⚪ No imbalance detected"
    else:
        market_state = f"💰 Price: ${current_price:,.2f}<br>⏳ Waiting for order book data..."
    
    # 2. Active Signal
    active_signal = db.get_active_signal()
    if active_signal:
        direction_emoji = "📈" if active_signal['direction'] == 'long' else "📉"
        active_signal_display = f"""
        {direction_emoji} {active_signal['direction'].upper()}<br>
        💰 Entry: ${active_signal['entry_price']:,.2f}<br>
        🎯 TP: ${active_signal['tp_price']:,.2f}<br>
        🛑 SL: ${active_signal['sl_price']:,.2f}<br>
        📊 Strength: {active_signal['strength']*100:.1f}%
        """
    else:
        pending_signal = db.get_pending_signal()
        if pending_signal:
            direction_emoji = "📈" if pending_signal['direction'] == 'long' else "📉"
            active_signal_display = f"""
            ⏳ PENDING SIGNAL<br>
            {direction_emoji} {pending_signal['direction'].upper()}<br>
            💰 Entry: ${pending_signal['entry_price']:,.2f}<br>
            🎯 TP: ${pending_signal['tp_price']:,.2f}<br>
            🛑 SL: ${pending_signal['sl_price']:,.2f}
            """
        else:
            active_signal_display = "⏳ No active signal"
    
    # 3. Recent Signals
    recent_signals = db.get_recent_signals(limit=3)
    if recent_signals:
        signals_html = ""
        for signal in recent_signals:
            direction_emoji = "📈" if signal['direction'] == 'long' else "📉"
            status_emoji = "✅" if signal['pnl'] and signal['pnl'] > 0 else "❌" if signal['pnl'] and signal['pnl'] <= 0 else "⏳"
            signals_html += f"""
            {status_emoji} {direction_emoji} {signal['direction'].upper()} - {signal['status']}<br>
            """
        recent_signals_display = signals_html
    else:
        recent_signals_display = "📝 No signals generated yet"
    
    # 4. Session Stats
    stats = db.get_session_stats()
    if stats['total_signals'] > 0:
        session_stats_display = f"""
        📊 Total Signals: {stats['total_signals']}<br>
        ✅ Wins: {stats['wins']} ({stats['win_rate']:.1f}%)<br>
        ❌ Losses: {stats['losses']}<br>
        💰 Net PnL: ${stats['net_pnl']:,.2f}<br>
        📈 Avg Win: ${stats['avg_win']:,.2f}<br>
        📉 Avg Loss: ${stats['avg_loss']:,.2f}
        """
    else:
        session_stats_display = "📊 No completed trades yet"
    
    # 5. Status
    status = f"Live: ${current_price:,.2f} | Auto-refresh: 5s"
    
    return market_state, active_signal_display, recent_signals_display, session_stats_display, status


if __name__ == '__main__':
    print("Starting Wormrider on http://127.0.0.1:8060")
    app.run(host='127.0.0.1', port=8060, debug=True)
