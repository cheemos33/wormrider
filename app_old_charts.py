"""Main Wormrider application - Wall Trap Strategy with Charts."""

import threading
import time
from dash import Dash, Input, Output, html, dcc
import plotly.graph_objects as go
from datetime import datetime as dt

import config
from database import db
from collectors import binance
from collectors import binance_trades
from indicators import liquidity_walls
from indicators import cvd
from indicators import orderbook_imbalance
from strategy import wall_trap
from strategy import orderbook_scalping
from strategy.paper_trading import paper_monitor
from alerts import manager

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

# Layout
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
        empty_fig = go.Figure()
        empty_fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#0f172a',
            plot_bgcolor='#0f172a',
            xaxis_title="Time",
            yaxis_title="Value"
        )
        return empty_fig, empty_fig, "No data yet", "No alerts yet", "Waiting for data..."
    
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
            
            # 2. Calculate imbalance
            imbalance_data = orderbook_scalping.calculate_imbalance_display(
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
    
    # 1. Price Chart - Last 5 minutes
    current_time = int(time.time() * 1000)
    five_min_ago = current_time - (5 * 60 * 1000)
    historical_data = db.get_snapshots_range("BTCUSDT", five_min_ago, current_time)
    
    price_fig = go.Figure()
    if historical_data:
        timestamps = [dt.fromtimestamp(d['timestamp'] / 1000) for d in historical_data]
        prices = [d['mid_price'] for d in historical_data]
        
        price_fig.add_trace(go.Scatter(
            x=timestamps,
            y=prices,
            mode='lines',
            name='Price',
            line=dict(color='#0ea5e9', width=2)
        ))
    
    price_fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0f172a',
        plot_bgcolor='#0f172a',
        showlegend=False,
        margin=dict(l=50, r=20, t=20, b=40),
        xaxis_title="Time",
        yaxis_title="Price (USD)",
        hovermode='x unified'
    )
    
    # 2. Detect Liquidity Walls
    walls_data = liquidity_walls.detect_liquidity_walls(
        bids=snapshot['bids'],
        asks=snapshot['asks'],
        mid_price=snapshot['mid_price']
    )
    
    # Add wall lines to price chart (thickness proportional to volume)
    # Calculate max wall size for scaling
    all_walls = walls_data['bid_walls'] + walls_data['ask_walls']
    max_wall_size = max([w['size'] for w in all_walls]) if all_walls else 1
    
    for wall in walls_data['bid_walls'][:5]:  # Top 5 bid walls
        # Line width: 1-5 based on wall size
        line_width = 1 + (wall['size'] / max_wall_size) * 4  # Scale 1-5
        
        price_fig.add_hline(
            y=wall['price'],
            line_dash="solid",
            line_color="#16a34a",
            line_width=line_width,
            annotation_text=f"{wall['size']:.1f}",
            annotation_position="right",
            annotation_font_size=10
        )
    
    for wall in walls_data['ask_walls'][:5]:  # Top 5 ask walls
        # Line width: 1-5 based on wall size
        line_width = 1 + (wall['size'] / max_wall_size) * 4  # Scale 1-5
        
        price_fig.add_hline(
            y=wall['price'],
            line_dash="solid",
            line_color="#ef4444",
            line_width=line_width,
            annotation_text=f"{wall['size']:.1f}",
            annotation_position="right",
            annotation_font_size=10
        )
    
    # Orderbook Imbalance Table (percentage-based)
    imbalance_results, confluence, conf_strength = orderbook_imbalance.calculate_imbalance_at_distances(
        bids=snapshot['bids'],
        asks=snapshot['asks'],
        mid_price=snapshot['mid_price']
    )
    
    walls_html = []
    walls_html.append(html.P("📊 Bid-Ask Imbalance (Depth Analysis)", 
                            style={'fontWeight': 'bold', 'marginBottom': '10px', 'fontSize': '14px'}))
    
    # Imbalance table
    for result in imbalance_results:
        distance_pct = result['distance_pct']
        distance_usd = result['distance_usd']
        bid_vol = result['bid_volume']
        ask_vol = result['ask_volume']
        bid_pct = result['bid_pct']
        ask_pct = result['ask_pct']
        imbalance = result['imbalance']
        
        # Visual bar (10 segments)
        bar_segments = 10
        bid_segments = int((bid_pct / 100) * bar_segments)
        ask_segments = bar_segments - bid_segments
        
        # Create visual bar
        bar = "█" * bid_segments + "░" * ask_segments
        
        # Color based on imbalance
        if imbalance == 'BID':
            bar_color = '#16a34a'  # Green
            indicator = '🟢'
        elif imbalance == 'ASK':
            bar_color = '#ef4444'  # Red
            indicator = '🔴'
        else:
            bar_color = '#9ca3af'  # Gray
            indicator = '⚪'
        
        walls_html.append(html.Div([
            html.Div([
                html.Span(f"±{distance_pct:.2f}%", style={'color': '#e5e7eb', 'fontSize': '11px', 'width': '65px', 'display': 'inline-block'}),
                html.Span(f"(${distance_usd:.0f})", style={'color': '#6b7280', 'fontSize': '9px', 'width': '70px', 'display': 'inline-block'}),
                html.Span(f"{bar}", style={'color': bar_color, 'fontSize': '12px', 'letterSpacing': '-1px', 'marginLeft': '5px'}),
                html.Span(f" {indicator}", style={'color': bar_color, 'fontSize': '10px', 'marginLeft': '5px'}),
            ], style={'marginBottom': '3px'}),
            html.Div([
                html.Span(f"Bid: {bid_vol:.1f} BTC", style={'color': '#16a34a', 'fontSize': '9px', 'marginLeft': '140px'}),
                html.Span(f" | Ask: {ask_vol:.1f} BTC", style={'color': '#ef4444', 'fontSize': '9px'}),
                html.Span(f" | {bid_pct:.0f}%/{ask_pct:.0f}%", style={'color': '#9ca3af', 'fontSize': '9px'})
            ], style={'marginBottom': '8px'})
        ]))
    
    # Confluence indicator
    if confluence == 'ALL BID':
        conf_color = '#16a34a'
        conf_text = f'✅ CONFLUENCE: ALL BID ({conf_strength:.0%})'
    elif confluence == 'ALL ASK':
        conf_color = '#ef4444'
        conf_text = f'✅ CONFLUENCE: ALL ASK ({conf_strength:.0%})'
    elif confluence == 'MOSTLY BID':
        conf_color = '#16a34a'
        conf_text = f'⚠️ CONFLUENCE: MOSTLY BID ({conf_strength:.0%})'
    elif confluence == 'MOSTLY ASK':
        conf_color = '#ef4444'
        conf_text = f'⚠️ CONFLUENCE: MOSTLY ASK ({conf_strength:.0%})'
    else:
        conf_color = '#9ca3af'
        conf_text = f'❌ CONFLUENCE: MIXED ({conf_strength:.0%})'
    
    walls_html.append(html.Div([
        html.P(conf_text, style={'color': conf_color, 'fontWeight': 'bold', 'fontSize': '12px', 'marginTop': '10px', 'padding': '8px', 'background': '#1f2937', 'borderRadius': '5px'})
    ]))
    
    # 3. CVD Chart - Last 1 hour
    one_hour_ago = current_time - (60 * 60 * 1000)
    recent_trades = db.get_trades_range("btcusdt", one_hour_ago, current_time)
    
    cvd_fig = go.Figure()
    if recent_trades:
        cvd_data = cvd.get_cvd_summary(recent_trades, window_minutes=60)
        
        if cvd_data['cvd_series']:
            timestamps = [dt.fromtimestamp(point['timestamp'] / 1000) for point in cvd_data['cvd_series']]
            cvd_values = [point['cvd'] for point in cvd_data['cvd_series']]
            
            cvd_fig.add_trace(go.Scatter(
                x=timestamps,
                y=cvd_values,
                mode='lines',
                name='CVD',
                line=dict(color='#f59e0b', width=2),
                fill='tonexty',
                fillcolor='rgba(245, 158, 11, 0.1)'
            ))
            
            # Detect CVD trend segments
            segments = cvd.detect_cvd_trend_segments(cvd_data['cvd_series'], min_segment_size=10, slope_threshold=0.05)
            
            # Draw trendlines for each segment
            if segments:
                for segment in segments:
                    segment_start_dt = dt.fromtimestamp(segment['start_time'] / 1000)
                    segment_end_dt = dt.fromtimestamp(segment['end_time'] / 1000)
                    
                    # Color based on direction
                    if segment['direction'] == 'upward':
                        line_color = '#16a34a'  # Green
                    elif segment['direction'] == 'downward':
                        line_color = '#ef4444'  # Red
                    else:
                        line_color = '#9ca3af'  # Gray
                    
                    # Draw trendline
                    cvd_fig.add_trace(go.Scatter(
                        x=[segment_start_dt, segment_end_dt],
                        y=[segment['start_cvd'], segment['end_cvd']],
                        mode='lines',
                        name=segment['direction'].capitalize(),
                        line=dict(color=line_color, width=3, dash='solid'),
                        showlegend=False,
                        opacity=0.8
                    ))
                
                # Get current segment status
                current_segment = segments[-1]
                current_status = current_segment['direction']
                
                # Print current status
                status_emoji = "📈" if current_status == 'upward' else "📉" if current_status == 'downward' else "↔️"
                print(f"{status_emoji} [CVD SEGMENT] {current_status.upper()} | Slope: {current_segment['slope']:.4f} | CVD: {cvd_data['current_cvd']:.2f}")
            else:
                current_status = 'neutral'
                print(f"[CVD] Not enough data for segmentation")
        else:
            current_status = 'neutral'
    else:
        current_status = 'neutral'
    
    cvd_fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0f172a',
        plot_bgcolor='#0f172a',
        showlegend=False,
        margin=dict(l=50, r=20, t=20, b=40),
        xaxis_title="Time",
        yaxis_title="CVD",
        hovermode='x unified'
    )
    
    # 4. Check for Wall Trap Setup
    if recent_trades:
        setup_alert = wall_trap.detect_wall_trap_setup(
            orderbook_data=snapshot,
            trades_data=recent_trades,
            current_price=snapshot['mid_price']
        )
        
        if setup_alert:
            manager.process_alert(setup_alert)
    
    # 5. Alerts Panel with CVD Status
    alerts_html = []
    
    # Current CVD Trend Status (Top of panel)
    status_color = '#16a34a' if current_status == 'upward' else '#ef4444' if current_status == 'downward' else '#9ca3af'
    status_text = "TRENDING UP 📈" if current_status == 'upward' else "TRENDING DOWN 📉" if current_status == 'downward' else "RANGING ↔️"
    
    alerts_html.append(html.Div([
        html.P("CVD Status:", style={'fontSize': '11px', 'color': '#9ca3af', 'marginBottom': '5px'}),
        html.P(status_text, style={'color': status_color, 'fontWeight': 'bold', 'fontSize': '14px'}),
    ], style={'padding': '8px', 'background': '#1f2937', 'borderRadius': '5px', 'marginBottom': '10px'}))
    
    # Wall Trap Alerts
    alerts = manager.get_recent_alerts(limit=3)
    
    if alerts:
        alerts_html.append(html.P("Wall Trap Alerts:", 
                                  style={'fontSize': '11px', 'color': '#9ca3af', 'marginBottom': '5px'}))
        for alert in alerts:
            timestamp = dt.fromtimestamp(alert['timestamp'] / 1000).strftime('%H:%M:%S')
            direction_color = '#16a34a' if alert['direction'] == 'long' else '#ef4444'
            
            alerts_html.append(html.Div([
                html.Span(f"[{timestamp}] ", style={'color': '#9ca3af', 'fontSize': '10px'}),
                html.Span(f"{alert['direction'].upper()}", 
                         style={'color': direction_color, 'fontWeight': 'bold', 'fontSize': '11px'}),
                html.Span(f" @ ${alert['wall_price']:,.2f}", style={'color': '#e5e7eb', 'fontSize': '10px'})
            ], style={'marginBottom': '2px', 'padding': '3px'}))
    
    alerts_display = html.Div(alerts_html)
    
    # Status text
    status = f"💰 ${snapshot['mid_price']:,.2f} | 🔄 Auto-refresh: 5s | 📊 {len(recent_trades) if recent_trades else 0} trades"
    
    return price_fig, cvd_fig, html.Div(walls_html), alerts_display, status


if __name__ == '__main__':
    print("Starting Wormrider on http://127.0.0.1:8060")
    app.run(host='127.0.0.1', port=8060, debug=True)