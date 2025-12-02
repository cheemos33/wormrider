"""
Spaghetti Chart Component for Trading Terminal
Displays 24h price movements for all coins in one chart
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from config import config


def create_spaghetti_chart(all_coin_data):
    """
    Create a spaghetti chart showing % change for all coins over 24h
    WITH DYNAMIC Y-AXIS RANGE - Automatically adjusts to show extreme movements
    
    Args:
        all_coin_data: Dict mapping coin symbols to DataFrames with 'timestamp' and 'pct_change'
    
    Returns:
        Plotly figure object
    """
    
    fig = go.Figure()
    
    # Collect all percentage change values for dynamic range calculation
    all_pct_values = []
    
    # Separate priority coins (BTC, ETH, SOL) to render them last (on top)
    priority_coins = ['BTC', 'ETH', 'SOL']
    other_coins = [(coin, df) for coin, df in all_coin_data.items() if coin not in priority_coins]
    priority_coin_data = [(coin, df) for coin, df in all_coin_data.items() if coin in priority_coins]
    
    # Process in order: others first, then priority coins (so they appear on top)
    all_coins_ordered = other_coins + priority_coin_data
    
    # First pass: Add all traces and collect annotation data
    import pandas as pd
    annotation_data = []
    coin_index = 0
    
    for coin, df in all_coins_ordered:
        if df is None or df.empty:
            continue
        
        # Get color for this coin
        color = config.COIN_COLORS.get(coin)
        if not color:
            # Use fallback color based on index
            coins_list = list(all_coin_data.keys())
            idx = coins_list.index(coin) if coin in coins_list else 0
            color = config.FALLBACK_COLORS[idx % len(config.FALLBACK_COLORS)]
        
        # Calculate current % change
        current_pct = df.iloc[-1]['pct_change'] if 'pct_change' in df.columns else 0
        last_timestamp = df.iloc[-1]['timestamp']
        
        # Collect all percentage values for range calculation
        if 'pct_change' in df.columns:
            all_pct_values.extend(df['pct_change'].dropna().tolist())
        
        # Add line trace
        fig.add_trace(go.Scattergl(
            x=df['timestamp'],
            y=df['pct_change'],
            mode='lines',
            name=f"{coin} ({current_pct:+.2f}%)",
            line=dict(
                color=color,
                width=3 if coin in ['BTC', 'ETH', 'SOL'] else 0.5,
                shape='linear'  # Sharp lines without smoothing/glow
            ),
            hovertemplate=(
                f"<b>{coin}</b><br>" +
                "Time: %{x|%H:%M}<br>" +
                "Change: %{y:.2f}%<br>" +
                "<extra></extra>"
            )
        ))
        
        # Position tags in the dedicated tag area (24h05-24h50)
        # Calculate tag position: 5 minutes after line ends + offset based on coin index
        tag_start_time = last_timestamp + pd.Timedelta(minutes=5)
        tag_timestamp = tag_start_time + pd.Timedelta(minutes=coin_index * 2)  # Spread tags out evenly
        
        # Store annotation data for later rendering
        annotation_data.append({
            'coin': coin,
            'tag_timestamp': tag_timestamp,
            'current_pct': current_pct,
            'color': color
        })
        
        coin_index += 1  # Increment for next coin
    
    # Second pass: Add annotations for non-priority coins first
    for data in annotation_data:
        if data['coin'] not in priority_coins:
            fig.add_annotation(
                x=data['tag_timestamp'],
                y=data['current_pct'],
                text=f" {data['coin']} {data['current_pct']:+.1f}% ",
                showarrow=True,
                arrowhead=0,
                arrowsize=1,
                arrowwidth=1,
                arrowcolor=data['color'],
                ax=0,
                ay=0,
                xanchor='left',
                font=dict(
                    size=10,
                    color=data['color'],
                    family='Courier New, monospace'
                ),
                bgcolor='rgba(0,0,0,0.9)',
                bordercolor=data['color'],
                borderwidth=0.5,
                borderpad=1
            )
    
    # Third pass: Add BTC, ETH, SOL annotations LAST (on top of everything)
    for data in annotation_data:
        if data['coin'] in priority_coins:
            fig.add_annotation(
                x=data['tag_timestamp'],
                y=data['current_pct'],
                text=f" {data['coin']} {data['current_pct']:+.1f}% ",
                showarrow=True,
                arrowhead=0,
                arrowsize=1,
                arrowwidth=1,
                arrowcolor=data['color'],
                ax=0,
                ay=0,
                xanchor='left',
                font=dict(
                    size=10,
                    color=data['color'],
                    family='Courier New, monospace'
                ),
                bgcolor='rgba(0,0,0,0.9)',
                bordercolor=data['color'],
                borderwidth=0.5,
                borderpad=1
            )
    
    # Calculate dynamic Y-axis range based on actual data
    y_range = None
    if all_pct_values:
        min_pct = min(all_pct_values)
        max_pct = max(all_pct_values)
        
        # Add 10% buffer above and below the extremes
        range_buffer = max(2.0, (max_pct - min_pct) * 0.1)  # At least 2% buffer
        y_min = min_pct - range_buffer
        y_max = max_pct + range_buffer
        
        # Set reasonable safety limits to prevent chart breaking
        # Allow up to -50% for extreme dumps, but cap at reasonable levels
        y_min = max(y_min, -50.0)  # Don't go below -50%
        y_max = min(y_max, 20.0)   # Don't go above +20% (rare in crypto dumps)
        
        # Ensure we always show 0% if it's within our data range
        if y_min > 0:
            y_min = min(y_min, -1.0)  # Always show some negative space
        if y_max < 0:
            y_max = max(y_max, 1.0)   # Always show some positive space
            
        y_range = [y_min, y_max]
        print(f"📊 Dynamic Y-axis range: {y_min:.1f}% to {y_max:.1f}% (data range: {min_pct:.1f}% to {max_pct:.1f}%)")
    
    # Get the latest timestamp from data
    latest_time = None
    for coin, df in all_coin_data.items():
        if df is not None and not df.empty:
            latest_time = df.iloc[-1]['timestamp']
            break
    
    # Add vertical line at UTC 00:00 (daily open) using shapes
    from datetime import datetime, timezone
    import pandas as pd
    
    # Find today's UTC 00:00
    now_utc = datetime.now(timezone.utc)
    today_open = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Only show if today's open is within the 24h window
    earliest_time = now_utc - pd.Timedelta(hours=24)
    if today_open > earliest_time:
        # Add vertical line as a shape
        fig.add_shape(
            type="line",
            x0=today_open,
            x1=today_open,
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color="#00ff41", width=1, dash="solid")
        )
        
        # Add annotation
        fig.add_annotation(
            x=today_open,
            y=1,
            yref="paper",
            text=today_open.strftime('%A'),  # Full weekday name (Monday, Tuesday, etc.)
            showarrow=False,
            yanchor="top",
            font=dict(size=10, color='#00ff41'),
            bgcolor='rgba(0,0,0,0.8)',
            bordercolor='#00ff41',
            borderwidth=1,
            borderpad=3
        )
    
    # Add current time annotation at the end of the chart
    if latest_time:
        fig.add_annotation(
            x=latest_time,
            y=0,
            yref="paper",
            text=latest_time.strftime('%H:%M'),
            showarrow=False,
            yanchor="top",
            yshift=-5,
            font=dict(size=11, color='#00ff00', family='Courier New, monospace'),
            bgcolor='rgba(0,0,0,0.9)',
            bordercolor='#00ff00',
            borderwidth=1,
            borderpad=3
        )
    
    # Update layout
    fig.update_layout(
        title={
            'text': '24-Hour Price Movements',
            'font': {'size': 18, 'color': '#00ff41'},
            'x': 0.5,
            'xanchor': 'center',
            'y': 0.98,
            'yanchor': 'top'
        },
        template='plotly_dark',
        plot_bgcolor='#000000',
        paper_bgcolor='#000000',
        font=dict(color='#00ff41', family='Courier New, monospace'),
        hovermode='closest',
        showlegend=False,  # Remove legend since we have labels on chart
        xaxis=dict(
            gridcolor='#003311',
            showgrid=True,
            zeroline=False,
            color='#00ff41',
            tickformat='%H:%M',
            dtick=4*60*60*1000,  # Show tick every 4 hours
            range=[latest_time - pd.Timedelta(hours=24), latest_time + pd.Timedelta(hours=2)] if latest_time else None,  # Show 26 hours total
            domain=[0, 1]  # Use full width - no artificial gaps
        ),
        yaxis=dict(
            gridcolor='#003311',
            showgrid=True,
            zeroline=False,
            zerolinecolor='rgba(0,0,0,0)',  # Make zeroline invisible (transparent)
            zerolinewidth=0,
            ticksuffix='%',
            color='#00ff41',
            side='right',  # Move Y-axis to right side
            title='% Change from 24h Ago',
            dtick=2,  # Increment by 2% instead of 1% - this prevents gridline at 0%
            domain=[0, 1],  # Y-axis uses full height
            ticklabelposition='outside right',  # Move labels outside to avoid overlap
            tickfont=dict(size=10, color='#00ff41'),  # Smaller Y-axis percentage labels
            range=y_range,  # DYNAMIC RANGE - automatically adjusts to data extremes
            autorange=False  # Use our calculated range instead of auto
        ),
        margin=dict(l=40, r=60, t=50, b=50),  # Reduced margins to use full width
        height=900
    )
    
    return fig


def create_empty_chart():
    """Create an empty placeholder chart"""
    fig = go.Figure()
    
    fig.add_annotation(
        text="Loading data...",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=20, color='#00ff41')
    )
    
    fig.update_layout(
        template='plotly_dark',
        plot_bgcolor='#000000',
        paper_bgcolor='#000000',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=900
    )
    
    return fig

