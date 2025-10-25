"""Main Wormrider application - Order Book Scalping (NO CVD)."""

import threading
import time
from dash import Dash, Input, Output, html, dcc
from datetime import datetime as dt

import config
from database import db
from database import db_signals
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
    
    # ========== SIGNAL GENERATION ENGINE
    # Initialize instant_imbalance for all strategies
    instant_imbalance = None
    # ========== SIGNAL GENERATION ENGINE (3 PARALLEL STRATEGIES) ==========
    
    # Check active/pending signals for each strategy separately
    active_instant_xl = db_signals.get_active_signal('INSTANT_XL')
    pending_instant_xl = db_signals.get_pending_signal('INSTANT_XL')
    
    active_instant = db_signals.get_active_signal('INSTANT')
    pending_instant = db_signals.get_pending_signal('INSTANT')
    
    active_hybrid = db_signals.get_active_signal('HYBRID')
    pending_hybrid = db_signals.get_pending_signal('HYBRID')
    
    # Generate signals for each strategy independently
    if not active_instant_xl and not pending_instant_xl:
        # === STRATEGY 1: INSTANT_XL (Instant Snapshot) ===
        from collectors.binance import fetch_orderbook_snapshot
        instant_bids, instant_asks, _ = fetch_orderbook_snapshot("BTCUSDT")
        
        if instant_bids and instant_asks:
            from indicators.orderbook_aggregation import aggregate_bids_asks
            agg_instant_bids, agg_instant_asks = aggregate_bids_asks(instant_bids, instant_asks, 100)
            
            instant_imbalance = orderbook_scalping.calculate_imbalance(
                agg_bids=agg_instant_bids,
                agg_asks=agg_instant_asks,
                current_price=current_price,
                num_bins=2
            )
        agg_snapshot = db.get_latest_aggregated_snapshot("BTCUSDT", 100)
        historical_imbalance = None
        
        if agg_snapshot:
                historical_imbalance = orderbook_scalping.calculate_imbalance(
                    agg_bids=agg_snapshot['bids'],
                    agg_asks=agg_snapshot['asks'],
                    current_price=current_price,
                    num_bins=2
                )
                
                if instant_imbalance:
                    current_time_ms = int(time.time() * 1000)
                    signal = {
                        'signal_type': 'INSTANT_XL',
                        'direction': instant_imbalance['direction'],
                        'entry_price': current_price,
                        'tp_price': current_price + 150.0 if instant_imbalance["direction"] == "long" else current_price - 150.0,
                        'sl_price': current_price - 120.0 if instant_imbalance["direction"] == "long" else current_price + 120.0,
                        'bid_volume': instant_imbalance['bid_volume'],
                        'ask_volume': instant_imbalance['ask_volume'],
                        'imbalance_ratio': instant_imbalance['imbalance_ratio'],
                        'cvd_slope': 'N/A',
                        'strength': instant_imbalance['imbalance_ratio'],
                        'status': 'pending',
                        'timestamp': current_time_ms,
                        'initial_bid_liquidity': instant_imbalance['bid_volume'],
                        'initial_ask_liquidity': instant_imbalance['ask_volume']
                    }
                    db_signals.insert_signal(signal)
                    print(f"\n{'='*60}")
                    print(f"📊 STRATEGY 1: INSTANT_XL SIGNAL")
                    print(f"   Direction: {signal['direction'].upper()}")
                    print(f"   Imbalance: {signal['imbalance_ratio']*100:.1f}%")
                    print(f"{'='*60}\n")
        
        if not active_instant and not pending_instant:
            # === STRATEGY 2: INSTANT (REST Snapshot) ===
            from collectors.binance import fetch_orderbook_snapshot
            instant_bids, instant_asks, _ = fetch_orderbook_snapshot("BTCUSDT")
            instant_imbalance = None
            
            if instant_bids and instant_asks:
                # Aggregate instant snapshot
                from indicators.orderbook_aggregation import aggregate_bids_asks
                agg_instant_bids, agg_instant_asks = aggregate_bids_asks(instant_bids, instant_asks, 100)
                
                instant_imbalance = orderbook_scalping.calculate_imbalance(
                    agg_bids=agg_instant_bids,
                    agg_asks=agg_instant_asks,
                    current_price=current_price,
                    num_bins=2
                )
                
                if instant_imbalance:
                    current_time_ms = int(time.time() * 1000)
                    signal = {
                        'signal_type': 'INSTANT',
                        'direction': instant_imbalance['direction'],
                        'entry_price': current_price,
                        'tp_price': current_price + 50.0 if instant_imbalance["direction"] == "long" else current_price - 50.0,
                        'sl_price': current_price - 40.0 if instant_imbalance["direction"] == "long" else current_price + 40.0,
                        'bid_volume': instant_imbalance['bid_volume'],
                        'ask_volume': instant_imbalance['ask_volume'],
                        'imbalance_ratio': instant_imbalance['imbalance_ratio'],
                        'cvd_slope': 'N/A',
                        'strength': instant_imbalance['imbalance_ratio'],
                        'status': 'pending',
                        'timestamp': current_time_ms,
                        'initial_bid_liquidity': instant_imbalance['bid_volume'],
                        'initial_ask_liquidity': instant_imbalance['ask_volume']
                    }
                    db_signals.insert_signal(signal)
                    print(f"\n{'='*60}")
                    print(f"⚡ STRATEGY 2: INSTANT SIGNAL")
                    print(f"   Direction: {signal['direction'].upper()}")
                    print(f"   Imbalance: {signal['imbalance_ratio']*100:.1f}%")
                    print(f"{'='*60}\n")
        
        if not active_hybrid and not pending_hybrid:
            # === STRATEGY 3: HYBRID (Both must agree) ===
            # Need to calculate both for hybrid
            agg_snapshot = db.get_latest_aggregated_snapshot("BTCUSDT", 100)
            historical_imbalance = None
            if agg_snapshot:
                historical_imbalance = orderbook_scalping.calculate_imbalance(
                    agg_bids=agg_snapshot['bids'],
                    agg_asks=agg_snapshot['asks'],
                    current_price=current_price,
                    num_bins=2
                )
            
            from collectors.binance import fetch_orderbook_snapshot
            instant_bids, instant_asks, _ = fetch_orderbook_snapshot("BTCUSDT")
            instant_imbalance = None
            if instant_bids and instant_asks:
                from indicators.orderbook_aggregation import aggregate_bids_asks
                agg_instant_bids, agg_instant_asks = aggregate_bids_asks(instant_bids, instant_asks, 100)
                instant_imbalance = orderbook_scalping.calculate_imbalance(
                    agg_bids=agg_instant_bids,
                    agg_asks=agg_instant_asks,
                    current_price=current_price,
                    num_bins=2
                )
            
            # === STRATEGY 3: HYBRID (Both must agree) ===
            if historical_imbalance and instant_imbalance:
                # Both must have same direction and both > 60%
                if (historical_imbalance['direction'] == instant_imbalance['direction'] and
                    historical_imbalance['imbalance_ratio'] >= 0.60 and
                    instant_imbalance['imbalance_ratio'] >= 0.60):
                    
                    current_time_ms = int(time.time() * 1000)
                    # Use average of both for hybrid signal
                    avg_bid_vol = (historical_imbalance['bid_volume'] + instant_imbalance['bid_volume']) / 2
                    avg_ask_vol = (historical_imbalance['ask_volume'] + instant_imbalance['ask_volume']) / 2
                    avg_ratio = (historical_imbalance['imbalance_ratio'] + instant_imbalance['imbalance_ratio']) / 2
                    
                    signal = {
                        'signal_type': 'HYBRID',
                        'direction': historical_imbalance['direction'],
                        'entry_price': current_price,
                        'tp_price': current_price + 150.0 if historical_imbalance["direction"] == "long" else current_price - 150.0,
                        'sl_price': current_price - 120.0 if historical_imbalance["direction"] == "long" else current_price + 120.0,
                        'bid_volume': avg_bid_vol,
                        'ask_volume': avg_ask_vol,
                        'imbalance_ratio': avg_ratio,
                        'cvd_slope': 'N/A',
                        'strength': avg_ratio,
                        'status': 'pending',
                        'timestamp': current_time_ms,
                        'initial_bid_liquidity': avg_bid_vol,
                        'initial_ask_liquidity': avg_ask_vol
                    }
                    db_signals.insert_signal(signal)
                    print(f"\n{'='*60}")
                    print(f"🔥 STRATEGY 3: HYBRID SIGNAL (CONFLUENCE!)")
                    print(f"   Direction: {signal['direction'].upper()}")
                    print(f"   Historical: {historical_imbalance['imbalance_ratio']*100:.1f}% | Instant: {instant_imbalance['imbalance_ratio']*100:.1f}%")
                    print(f"   Average: {avg_ratio*100:.1f}%")
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
    
    # 2. Active Signal (any strategy)
    active_signal = db_signals.get_active_signal()  # Returns any active signal
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
        pending_signal = db_signals.get_pending_signal()  # Returns any pending signal
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
    recent_signals = db_signals.get_recent_signals(limit=20)  # Show last 20 signals
    if recent_signals:
        signals_list = []
        for signal in recent_signals:
            direction_emoji = "📈" if signal['direction'] == 'long' else "📉"
            status_emoji = "✅" if signal['pnl'] and signal['pnl'] > 0 else "❌" if signal['pnl'] and signal['pnl'] <= 0 else "⏳"
            
            # Format timestamp
            time_str = dt.fromtimestamp(signal['timestamp'] / 1000).strftime('%H:%M:%S')
            
            # Get strategy type and format with color
            signal_type = signal.get('signal_type', 'UNKNOWN')
            if signal_type == 'INSTANT_XL':
                strategy_emoji = "🟡"  # Yellow
            elif signal_type == 'INSTANT':
                strategy_emoji = "🔴"  # Red
            elif signal_type == 'HYBRID':
                strategy_emoji = "🟠"  # Orange
            else:
                strategy_emoji = "⚪"  # White
            
            signals_list.append(
                html.P(
                    f"{status_emoji} {direction_emoji} {signal['direction'].upper()} @ {time_str} | " +
                    f"PnL: ${signal['pnl'] if signal['pnl'] is not None else 0:.2f} | {strategy_emoji} {signal_type}",
                    style={'fontSize': '12px', 'marginBottom': '5px'}
                )
            )
        recent_signals_display = html.Div(signals_list, style={'maxHeight': '300px', 'overflowY': 'auto'})
    else:
        recent_signals_display = html.P("📝 No signals generated yet")
    
    # 4. Session Stats (3 strategies separated by commas with color emojis)
    stats_instant_xl = db_signals.get_session_stats('INSTANT_XL')
    stats_instant = db_signals.get_session_stats('INSTANT')
    stats_hybrid = db_signals.get_session_stats('HYBRID')
    
    # Format as "🟡strategy1, 🔴strategy2, 🟠strategy3"
    total_trades = f"🟡{stats_instant_xl['total_trades']}, 🔴{stats_instant['total_trades']}, 🟠{stats_hybrid['total_trades']}"
    wins = f"🟡{stats_instant_xl['wins']}, 🔴{stats_instant['wins']}, 🟠{stats_hybrid['wins']}"
    losses = f"🟡{stats_instant_xl['losses']}, 🔴{stats_instant['losses']}, 🟠{stats_hybrid['losses']}"
    total_pnl = f"🟡${stats_instant_xl['total_pnl']:.2f}, 🔴${stats_instant['total_pnl']:.2f}, 🟠${stats_hybrid['total_pnl']:.2f}"
    
    # Calculate overall stats for win rate
    total_all_trades = stats_instant_xl['total_trades'] + stats_instant['total_trades'] + stats_hybrid['total_trades']
    total_all_wins = stats_instant_xl['wins'] + stats_instant['wins'] + stats_hybrid['wins']
    overall_win_rate = (total_all_wins / total_all_trades * 100) if total_all_trades > 0 else 0
    
    if total_all_trades > 0:
        session_stats_display = html.Div([
            html.P(f"📊 Total Signals: {total_trades}"),
            html.P(f"✅ Wins: {wins} ({overall_win_rate:.1f}% overall)"),
            html.P(f"❌ Losses: {losses}"),
            html.P(f"💰 Total PnL: {total_pnl}", 
                   style={'color': '#10b981' if sum([stats_instant_xl['total_pnl'], stats_instant['total_pnl'], stats_hybrid['total_pnl']]) > 0 else '#ef4444'})
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
