"""
Multi-Page Dash Application for Trading Terminal + Analytics
"""
from dash import Dash, html, dcc, Input, Output
import dash_bootstrap_components as dbc

# Import config
from config import config

# Import page modules
from pages import trading, analytics

# Initialize Dash app with dark Bootstrap theme
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True
)

app.title = "Crypto Trading Terminal"

# Main layout with URL routing
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

# URL routing callback
@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname')]
)
def display_page(pathname):
    """Route to correct page based on URL"""
    if pathname == '/analytics':
        return analytics.layout
    else:  # Default to trading terminal
        return trading.layout

# Register callbacks from pages
trading.register_callbacks(app)
analytics.register_callbacks(app)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🐻 CRYPTO TRADING TERMINAL - nrlns003")
    print("="*60)
    print(f"Dashboard starting at http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}")
    print("Trading Terminal: http://localhost:8050/")
    print("Analytics: http://localhost:8050/analytics")
    print("="*60 + "\n")
    
    app.run_server(
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        debug=config.DASHBOARD_DEBUG
    )
