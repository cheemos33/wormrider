"""
VAL Score Bubble Plotter Component
Visualizes all coins' VAL scores as bubbles sorted by deepest dips
"""
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import html, dcc
from typing import List, Dict
from config import config


def create_val_plotter(watchlist_data: List[Dict]) -> dbc.Card:
    """
    Create VAL score bubble chart component
    
    Args:
        watchlist_data: List of coin data with VAL scores
    
    Returns:
        Dash component with VAL bubble chart
    """
    if not watchlist_data:
        return dbc.Card([
            dbc.CardBody([
                html.Div("No data available", style={'textAlign': 'center', 'color': '#666'})
            ])
        ])
    
    # Reorder so BTC, ETH, SOL appear last (on top in rendering)
    priority_coins = ['BTC', 'ETH', 'SOL']
    other_data = [item for item in watchlist_data if item['coin'] not in priority_coins]
    priority_data = [item for item in watchlist_data if item['coin'] in priority_coins]
    watchlist_data = other_data + priority_data
    
    # Keep coins in reordered watchlist order
    coins = [item['coin'] for item in watchlist_data]
    price_positions = [item.get('price_position', 50) for item in watchlist_data]  # 0-100%
    stars = [item.get('stars', 0) for item in watchlist_data]
    prices = [item.get('price', 0) for item in watchlist_data]
    rsi_values = [item.get('rsi', 0) for item in watchlist_data]
    val_distances = [item.get('val_distance', 0) for item in watchlist_data]
    
    # Get coin colors from config
    colors = [config.COIN_COLORS.get(coin, '#00ff41') for coin in coins]
    
    # Calculate bubble sizes based on stars (1-4)
    # Size range: 10 (1 star) to 40 (4 stars)
    sizes = [10 + (star * 7.5) for star in stars]
    
    # Create hover text
    hover_texts = []
    for i, coin in enumerate(coins):
        star_str = '🍌' * stars[i] if stars[i] > 0 else '○'
        price_str = f"${prices[i]:,.2f}" if prices[i] >= 1 else f"${prices[i]:.4f}"
        hover_text = (
            f"<b>{coin}</b><br>"
            f"Position: {price_positions[i]:.1f}%<br>"
            f"Price: {price_str}<br>"
            f"Bananas: {star_str}<br>"
            f"VAL: {val_distances[i]:.2f}%<br>"
            f"RSI: {rsi_values[i]:.1f}"
        )
        hover_texts.append(hover_text)
    
    # Create figure
    fig = go.Figure()
    
    # Add zone boundary lines (gray, no labels to avoid overlap)
    # VAL boundary (15%)
    fig.add_hline(
        y=15,  # VAL boundary - Important threshold
        line_dash="dot",
        line_color="#00ff41",  # Matrix green to stand out
        line_width=1,
        opacity=0.8  # More opaque
    )
    
    # VAH boundary (85%)
    fig.add_hline(
        y=85,
        line_dash="solid",
        line_color="#666",
        line_width=1,
        opacity=0.5
    )
    
    # Add bubbles (using price_positions 0-100%)
    fig.add_trace(go.Scatter(
        x=list(range(len(coins))),
        y=price_positions,
        mode='markers',
        marker=dict(
            size=sizes,
            color=colors,
            line=dict(color='#000000', width=1),
            opacity=0.8
        ),
        text=coins,
        hovertemplate='%{hovertext}<extra></extra>',
        hovertext=hover_texts,
        showlegend=False
    ))
    
    # Add coin name labels with VAL distance values next to their bubbles
    for i, (coin, price_pos, val_dist, color, size) in enumerate(zip(coins, price_positions, val_distances, colors, sizes)):
        # Calculate xshift based on bubble size
        # Bubble sizes range from ~17 to 40, so we need radius + spacing
        bubble_radius = size / 2
        label_shift = bubble_radius + 4  # bubble edge + 4px clear spacing
        
        fig.add_annotation(
            x=i,
            y=price_pos,
            text=f" {coin} {val_dist:+.1f}",  # Space before coin name for extra padding
            showarrow=False,
            xshift=label_shift,  # Position label to the right of bubble edge with spacing
            yshift=0,   # Same height as bubble
            xanchor='left',  # Anchor text from left side
            font=dict(
                size=13,
                color=color,
                family='Courier New, monospace'
            )
            # No frame around labels
        )
    
    # Update layout
    fig.update_layout(
        plot_bgcolor='#000000',
        paper_bgcolor='#000000',
        font=dict(color='#666', family='Courier New, monospace', size=14),
        margin=dict(l=40, r=20, t=30, b=40),
        height=300,
        xaxis=dict(
            showticklabels=False,  # Hide X-axis labels since we have labels next to bubbles
            showgrid=False,
            zeroline=False,
            color='#666'
        ),
        yaxis=dict(
            title=dict(text='Price Position (0-100%)', font=dict(size=14, color='#666')),
            range=[-2, 102],  # Minimal padding: -2 to 102 (tight fit with small buffer)
            showgrid=True,
            gridcolor='#222',
            gridwidth=1,
            zeroline=False,
            color='#666',
            tickmode='array',
            tickvals=[0, 15, 85, 100],
            ticktext=['0%', '15% VAL', '85% VAH', '100%']
        ),
        hovermode='closest'
    )
    
    # Create component (no container)
    component = html.Div([
        dcc.Graph(
            figure=fig,
            config={'displayModeBar': False},
            style={'height': '320px'}
        )
    ], style={'height': '100%', 'backgroundColor': '#000000'})
    
    return component

