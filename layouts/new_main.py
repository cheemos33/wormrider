"""New UI layout with price chart, CVD chart, walls, and alerts."""

from dash import html, dcc
import config


def create_layout():
    """Create the new 2x2 grid layout."""
    return html.Div([
        # Header
        html.Div([
            html.H1("wormrider - BTCUSDT", style={'margin': '10px', 'color': '#e5e7eb', 'flex': '1'}),
            html.Div(id='refresh-countdown', children='Auto-refresh: 1.0s',
                    style={'margin': '10px', 'color': '#9ca3af', 'fontSize': '12px'}),
        ], style={'background': '#1f2937', 'padding': '10px', 'borderRadius': '8px', 'marginBottom': '10px', 'display': 'flex', 'alignItems': 'center'}),
        
        # 2x2 Grid Layout
        html.Div([
            # Row 1
            html.Div([
                # Price Chart (Top Left)
                html.Div([
                    html.H3("Price Chart + Walls", style={'color': '#e5e7eb', 'fontSize': '14px', 'marginBottom': '10px'}),
                    dcc.Graph(
                        id='price-chart',
                        config={'displayModeBar': False},
                        style={'height': '300px'}
                    )
                ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1', 'marginRight': '5px'}),
                
                # CVD Chart (Top Right)
                html.Div([
                    html.H3("CVD Chart", style={'color': '#e5e7eb', 'fontSize': '14px', 'marginBottom': '10px'}),
                    dcc.Graph(
                        id='cvd-chart',
                        config={'displayModeBar': False},
                        style={'height': '300px'}
                    )
                ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1', 'marginLeft': '5px'}),
            ], style={'display': 'flex', 'marginBottom': '10px'}),
            
            # Row 2
            html.Div([
                # Liquidity Walls (Bottom Left)
                html.Div([
                    html.H3("Liquidity Walls", style={'color': '#e5e7eb', 'fontSize': '14px', 'marginBottom': '10px'}),
                    html.Div(id='walls-list', children='No walls detected', 
                           style={'color': '#9ca3af', 'fontSize': '12px'})
                ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1', 'marginRight': '5px'}),
                
                # Alert Table (Bottom Right)
                html.Div([
                    html.H3("Alert Log", style={'color': '#e5e7eb', 'fontSize': '14px', 'marginBottom': '10px'}),
                    html.Div(id='alert-table', children='No alerts yet', 
                           style={'color': '#9ca3af', 'fontSize': '12px'})
                ], style={'background': '#0f172a', 'padding': '12px', 'borderRadius': '8px', 'flex': '1', 'marginLeft': '5px'}),
            ], style={'display': 'flex'}),
        ]),
        
        # Interval component for auto-refresh
        dcc.Interval(
            id='interval-component',
            interval=config.AUTO_REFRESH_INTERVAL,  # 1 second
            n_intervals=0
        )
    ], style={'padding': '20px', 'background': '#0b0f16', 'minHeight': '100vh'})
