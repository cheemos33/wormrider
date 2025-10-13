"""Main Wormrider application - Order Book Scalping (NO CVD)."""

import threading
import time
from dash import Dash, Input, Output, html, dcc
from datetime import datetime as dt

import config
from database import db
from collectors import binance
from collectors import binance_trades
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
        db.cleanup_old_data(config.RETENTION_DAYS)
        db.cleanup_old_trades(hours=24)
        db.cleanup_old_aggregated(hours=24)

cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
cleanup_thread.start()

# Start paper trading monitor
paper_monitor.start()

# Create Dash app
app = Dash(__name__)
app.title = "Wormrider - Scalping"

# Layout - Minimal UI
app.layout = html.Div([
    html.Div([
        html.H1("wormrider - BTCUSDT 2-Bin Scalping", style={'margin': '10px', 'color': '#e5e7eb', 'flex': '1'}),
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
    
    # ========== SIGNAL GENERATION ENGINE (ORDER BOOK ONLY) ==========
    active_signal = db.get_active_signal()
    pending_signal = db.get_pending_signal()
    
    if not active_signal and not pending_signal:
        # No active signals - try to generate new one
        
        # 1. Get aggregated order book (latest)
        agg_snapshot = db.get_latest_aggregated_snapshot("BTCUSDT", 100)
        
        if agg_snapshot:
            agg_bids = agg_snapshot['bids']
            agg_asks = agg_snapshot['asks']
            
            # 2. Calculate imbalance - 2 BINS (with 60% threshold for signals)
            imbalance_data = orderbook_scalping.calculate_imbalance(
                agg_bids=agg_bids,
                agg_asks=agg_asks,
                current_price=current_price,
                num_bins=2  # 2 bins = $200 range
            )
            
            # 3. Generate signal if imbalance detected (NO CVD CHECK)
            if imbalance_data:
                current_time_ms = int(time.time() * 1000)
                
                # Create signal directly from imbalance (no CVD required)
                signal = {
                    'signal_type': 'ORDERBOOK_SCALP',
                    'direction': imbalance_data['direction'],
                    'entry_price': current_price,
                    'tp_price': current_price + 50.0 if imbalance_data['direction'] == 'long' else current_price - 50.0,
                    'sl_price': current_price - 40.0 if imbalance_data['direction'] == 'long' else current_price + 40.0,
                    'bid_volume': imbalance_data['bid_volume'],
                    'ask_volume': imbalance_data['ask_volume'],
                    'imbalance_ratio': imbalance_data['imbalance_ratio'],
                    'cvd_slope': 'N/A',  # No CVD check
                    'strength': imbalance_data['imbalance_ratio'],
                    'status': 'pending',
                    'timestamp': current_time_ms,
                    'initial_bid_liquidity': imbalance_data['bid_volume'],
                    'initial_ask_liquidity': imbalance_data['ask_volume']
                }
                
                # Store signal in database
                db.insert_signal(signal)
                
                print(f"\n{'='*60}")
                print(f"🎯 NEW SIGNAL GENERATED (2 BINS - 60% threshold)")
                print(f"   Direction: {signal['direction'].upper()}")
                print(f"   Entry: ${signal['entry_price']:,.2f}")
                print(f"   TP: ${signal['tp_price']:,.2f} (+$50)")
                print(f"   SL: ${signal['sl_price']:,.2f} (-$40)")
                print(f"   Imbalance: {signal['imbalance_ratio']*100:.1f}%")
                print(f"   2-Bin Range: Bid={signal['initial_bid_liquidity']:.2f} Ask={signal['initial_ask_liquidity']:.2f}")
                print(f"{'='*60}\n")
    
    # ========== END SIGNAL GENERATION ==========
    
    # ========== UI UPDATES ==========
    
    # 1. Market State (display any imbalance, no threshold)
    agg_snapshot = db.get_latest_aggregated_snapshot("BTCUSDT", 100)
    market_state = html.Div([
        html.P(f"💰 Price: ${current_price:,.2f}"),
        html.P(f"🕒 Last Update: {dt.fromtimestamp(snapshot['timestamp'] / 1000).strftime('%H:%M:%S')}")
    ])
    
    if agg_snapshot:
        agg_bids = agg_snapshot['bids']
        agg_asks = agg_snapshot['asks']
        
        # Calculate imbalance for display - 2 BINS (no threshold)
        imbalance_data_display = orderbook_scalping.calculate_imbalance_display(
            agg_bids=agg_bids,
            agg_asks=agg_asks,
            current_price=current_price,
            num_bins=2  # 2 bins = $200 range
        )
        
        if imbalance_data_display:
            direction_emoji = "🔴" if imbalance_data_display['direction'] == 'long' else "🟢"
            imbalance_display = html.Div([
                html.P(f"{direction_emoji} Imbalance: {imbalance_data_display['direction'].upper()} ({imbalance_data_display['imbalance_ratio']*100:.1f}%)"),
                html.P(f"📊 Bid Vol: {imbalance_data_display['bid_volume']:,.2f}"),
                html.P(f"📊 Ask Vol: {imbalance_data_display['ask_volume']:,.2f}"),
                html.P(f"🎯 Signal Threshold: 60% (2 Bins = $200)", style={'fontSize': '11px', 'color': '#6b7280'}),
                html.P(f"{'✅ Would generate signal!' if imbalance_data_display['imbalance_ratio'] >= 0.60 else '❌ Below threshold'}", 
                       style={'fontSize': '11px', 'color': '#10b981' if imbalance_data_display['imbalance_ratio'] >= 0.60 else '#ef4444'})
            ])
            market_state = html.Div([market_state, imbalance_display])
        else:
            market_state = html.Div([market_state, html.P("⚪ No imbalance detected")])
    
    # 2. Active Signal
    active_signal = db.get_active_signal()
    if active_signal:
        direction_emoji = "📈" if active_signal['direction'] == 'long' else "📉"
        entry_price = active_signal['entry_price']
        position_size = 5000.0  # Updated to $5000
        
        # Calculate current unrealized PnL (based on $5000 position)
        if active_signal['direction'] == 'long':
            price_diff = current_price - entry_price
        else:
            price_diff = entry_price - current_price
        
        current_pnl = (price_diff / entry_price) * position_size
        
        # Calculate expected PnL for TP/SL
        expected_tp_pnl = (50.0 / entry_price) * position_size
        expected_sl_pnl = (40.0 / entry_price) * position_size  # Updated to $40 SL
        
        active_signal_display = html.Div([
            html.P(f"{direction_emoji} {active_signal['direction'].upper()}"),
            html.P(f"💰 Entry: ${entry_price:,.2f}"),
            html.P(f"🎯 TP: ${active_signal['tp_price']:,.2f} (+$50 = ${expected_tp_pnl:.2f} profit)"),
            html.P(f"🛑 SL: ${active_signal['sl_price']:,.2f} (-$40 = ${expected_sl_pnl:.2f} loss)"),
            html.P(f"📊 Strength: {active_signal['strength']*100:.1f}%"),
            html.P(f"💵 Current PnL: ${current_pnl:.2f} (${price_diff:.2f} price move)", 
                   style={'color': '#10b981' if current_pnl > 0 else '#ef4444' if current_pnl < 0 else '#9ca3af'})
        ])
    else:
        pending_signal = db.get_pending_signal()
        if pending_signal:
            direction_emoji = "📈" if pending_signal['direction'] == 'long' else "📉"
            active_signal_display = html.Div([
                html.P("⏳ PENDING SIGNAL"),
                html.P(f"{direction_emoji} {pending_signal['direction'].upper()}"),
                html.P(f"💰 Entry: ${pending_signal['entry_price']:,.2f}"),
                html.P(f"🎯 TP: ${pending_signal['tp_price']:,.2f} (+$50)"),
                html.P(f"🛑 SL: ${pending_signal['sl_price']:,.2f} (-$40)")
            ])
        else:
            active_signal_display = html.P("⏳ No active signal")
    
    # 3. Recent Signals (show ALL, not just last 3)
    recent_signals = db.get_recent_signals(limit=20)  # Show last 20 signals
    if recent_signals:
        signals_list = []
        for signal in recent_signals:
            direction_emoji = "📈" if signal['direction'] == 'long' else "📉"
            status_emoji = "✅" if signal['pnl'] and signal['pnl'] > 0 else "❌" if signal['pnl'] and signal['pnl'] <= 0 else "⏳"
            
            # Format timestamp
            time_str = dt.fromtimestamp(signal['timestamp'] / 1000).strftime('%H:%M:%S')
            
            # Get exit reason if available
            exit_reason = signal.get('exit_reason', 'Unknown')
            if not exit_reason:
                exit_reason = 'Manual close' if signal['status'] not in ['tp_hit', 'sl_hit'] else signal['status'].replace('_', ' ').upper()
            
            signals_list.append(
                html.P(
                    f"{status_emoji} {direction_emoji} {signal['direction'].upper()} @ {time_str} | " +
                    f"PnL: ${signal['pnl'] if signal['pnl'] is not None else 0:.2f} | {exit_reason}",
                    style={'fontSize': '12px', 'marginBottom': '5px'}
                )
            )
        recent_signals_display = html.Div(signals_list, style={'maxHeight': '300px', 'overflowY': 'auto'})
    else:
        recent_signals_display = html.P("📝 No signals generated yet")
    
    # 4. Session Stats
    stats = db.get_session_stats()
    if stats['total_signals'] > 0:
        session_stats_display = html.Div([
            html.P(f"📊 Total Signals: {stats['total_signals']}"),
            html.P(f"✅ Wins: {stats['wins']} ({stats['win_rate']:.1f}%)"),
            html.P(f"❌ Losses: {stats['losses']}"),
            html.P(f"💰 Net PnL: ${stats['net_pnl']:,.2f}", 
                   style={'color': '#10b981' if stats['net_pnl'] > 0 else '#ef4444' if stats['net_pnl'] < 0 else '#9ca3af'}),
            html.P(f"📈 Avg Win: ${stats['avg_win']:,.2f}"),
            html.P(f"📉 Avg Loss: ${stats['avg_loss']:,.2f}")
        ])
    else:
        session_stats_display = html.P("📊 No completed trades yet")
    
    # 5. Status with parameters
    status = f"Live: ${current_price:,.2f} | 📊 Threshold: 60% (2 Bins) | 💰 Position: $5000 (5x) | 🎯 TP: +$50 | 🛑 SL: -$40 | ⏱️ Refresh: 5s"
    
    return market_state, active_signal_display, recent_signals_display, session_stats_display, status


if __name__ == '__main__':
    print("Starting Wormrider on http://127.0.0.1:8060")
    print("="*60)
    print("Strategy: Order Book Imbalance - 2 BINS ($200)")
    print("Signal Threshold: 60%")
    print("Position Size: $5000 (5x leverage)")
    print("TP: +$50 price movement")
    print("SL: -$40 price movement")
    print("="*60)
    app.run(host='127.0.0.1', port=8060, debug=True)
