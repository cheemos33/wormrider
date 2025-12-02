"""
Plotter 4 Placeholder Component
Placeholder for future features
"""
from dash import html


def create_plotter_4() -> html.Div:
    """
    Create a placeholder component for the 4th plotter
    Matches the style of other plotters (no container, 300px height)
    
    Returns:
        Dash component with placeholder content
    """
    component = html.Div([
        html.Div(
            "// PLOTTER 4 //",
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


