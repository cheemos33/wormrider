"""Hello World Dash App."""

from dash import Dash, html

app = Dash(__name__)

app.layout = html.Div([
    html.H1("Hello World from Wormrider!", style={'color': 'white'}),
    html.P("If you see this, Dash is working!", style={'color': 'green', 'fontSize': '20px'})
], style={'background': 'black', 'padding': '50px'})

if __name__ == '__main__':
    print("Starting Hello World on http://127.0.0.1:8053")
    app.run(host='127.0.0.1', port=8053, debug=False)
