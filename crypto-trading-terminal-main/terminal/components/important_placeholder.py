"""
Important Placeholder Component
Placeholder for future features - matches VAL/RSI plotter style
"""
import dash_bootstrap_components as dbc
from dash import html


def create_important_placeholder() -> dbc.Card:
    """
    Create a placeholder component for future features
    Matches the style of VAL and RSI plotters
    
    Returns:
        Dash component with placeholder content
    """
    component = html.Div([
        html.Div(
            "// PLACEHOLDER //",
            style={
                'textAlign': 'center',
                'color': '#666',
                'fontSize': '14px',
                'padding': '20px',
                'height': '320px',
                'display': 'flex',
                'alignItems': 'center',
                'justifyContent': 'center',
                'fontFamily': 'Courier New, monospace',
                'letterSpacing': '2px',
                'backgroundColor': '#000000'
            }
        )
    ], style={'height': '100%', 'backgroundColor': '#000000'})
    
    return component

