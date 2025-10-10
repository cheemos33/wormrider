"""Dash UI layout and components."""

from dash import html, dcc
import config


def create_layout():
    """Create the main Dash layout."""
    return html.Div([
        # Header
        html.Div([
            html.H1("wormrider - BTCUSDT", style={'margin': '10px', 'color': '#e5e7eb'}),
            html.Div([
                html.Label(f"Bin Size (USD): ", style={'marginRight': '10px', 'color': '#9ca3af'}),
                html.Span(id='bin-size-display', children=str(config.DEFAULT_BIN_SIZE), 
                         style={'marginRight': '20px', 'color': '#e5e7eb', 'fontWeight': 'bold'}),
                dcc.Slider(
                    id='bin-size-slider',
                    min=config.BIN_SIZE_RANGE[0],
                    max=config.BIN_SIZE_RANGE[1],
                    step=10,
                    value=config.DEFAULT_BIN_SIZE,
                    marks={
                        10: '10',
                        250: '250',
                        500: '500',
                        750: '750',
                        1000: '1000'
                    },
                    tooltip={"placement": "bottom", "always_visible": False}
                ),
            ], style={'display': 'flex', 'alignItems': 'center', 'margin': '10px', 'width': '600px'}),
            html.Div(id='refresh-countdown', children='Auto-refresh in: 10s',
                    style={'margin': '10px', 'color': '#9ca3af', 'fontSize': '12px'}),
        ], style={'background': '#1f2937', 'padding': '10px', 'borderRadius': '8px', 'marginBottom': '10px'}),
        
        # Panel 1: Price Line (placeholder for now)
        html.Div([
            html.H3("Price Line", style={'color': '#e5e7eb', 'fontSize': '14px', 'marginBottom': '10px'}),
            dcc.Graph(
                id='price-chart',
                config={'displayModeBar': False},
                style={'height': '250px'}
            )
        ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'marginBottom': '10px'}),
        
        # Panel 2: Order Book Profile
        html.Div([
            html.H3("Order Book Profile - Bids (Green) / Asks (Red)", 
                   style={'color': '#e5e7eb', 'fontSize': '14px', 'marginBottom': '10px'}),
            dcc.Graph(
                id='orderbook-chart',
                config={'displayModeBar': False},
                style={'height': '450px'}
            )
        ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px'}),
        
        # Interval component for auto-refresh
        dcc.Interval(
            id='interval-component',
            interval=config.AUTO_REFRESH_INTERVAL,  # 10 seconds
            n_intervals=0
        )
    ], style={'padding': '20px', 'background': '#0b0f16', 'minHeight': '100vh'})

