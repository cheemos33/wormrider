"""Dash UI layout and components."""

from dash import html, dcc
import config


def create_layout():
    """Create the main Dash layout."""
    return html.Div([
        # Header
        html.Div([
            html.H1("wormrider - BTCUSDT", style={'margin': '10px', 'color': '#e5e7eb', 'flex': '1'}),
            html.Div(id='refresh-countdown', children='Auto-refresh: 1.0s',
                    style={'margin': '10px', 'color': '#9ca3af', 'fontSize': '12px'}),
        ], style={'background': '#1f2937', 'padding': '10px', 'borderRadius': '8px', 'marginBottom': '10px', 'display': 'flex', 'alignItems': 'center'}),
        
        # Two-panel layout: Price chart (left) + Order Book (right)
        html.Div([
            # Left Panel: Price Line Chart
            html.Div([
                html.H3("Price (5min)", style={'color': '#e5e7eb', 'fontSize': '14px', 'marginBottom': '10px'}),
                dcc.Graph(
                    id='price-chart',
                    config={'displayModeBar': False},
                    style={'height': '650px'}
                )
            ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1', 'marginRight': '10px'}),
            
                # Right Panel: Order Book Profile (vertical bars)
                html.Div([
                    html.Div([
                        html.H3("Order Book Profile", style={'color': '#e5e7eb', 'fontSize': '14px', 'marginBottom': '15px'}),
                        html.Div([
                            html.Label("Bin Size: ", style={'marginRight': '10px', 'color': '#9ca3af', 'fontSize': '12px'}),
                            html.Span(id='bin-size-display', children=f"{config.DEFAULT_BIN_SIZE} USD", 
                                     style={'marginRight': '15px', 'color': '#e5e7eb', 'fontWeight': 'bold', 'fontSize': '12px'}),
                        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '15px'}),
                        html.Div([
                            dcc.Slider(
                                id='bin-size-slider',
                                min=0,
                                max=100,
                                step=1,
                                value=50,  # Logarithmic position for 50 USD
                                marks={
                                    0: '10',
                                    25: '25',
                                    50: '50',
                                    75: '150',
                                    100: '1000'
                                },
                                tooltip={"placement": "bottom", "always_visible": False}
                            )
                        ], style={'marginBottom': '20px'}),
                    ], style={'marginBottom': '10px'}),
                dcc.Graph(
                    id='orderbook-chart',
                    config={'displayModeBar': False},
                    style={'height': '620px'}
                )
            ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1'}),
        ], style={'display': 'flex', 'gap': '0px'}),
        
            # Interval component for auto-refresh
            dcc.Interval(
                id='interval-component',
                interval=config.AUTO_REFRESH_INTERVAL,  # 1 second
                n_intervals=0
            )
        ], style={'padding': '20px', 'background': '#0b0f16', 'minHeight': '100vh'})

