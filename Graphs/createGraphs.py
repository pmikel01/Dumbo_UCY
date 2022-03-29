# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

from dash import Dash, html, dcc
import plotly.express as px
import pandas as pd
import os

df = pd.DataFrame(columns=['Nodes','BatchSize','Latency','Throughput'])
figTB = px.line()
figLB = px.line()
figLN = px.line()
figTN = px.line()
figLT = px.line()

colors = {
    'background': '#1e2130',
    'text': '#7FDBFF'
}

colors2 = {
    'background': '#ffffff',
    'text': '#1e2130'
}

def readLogs():
    global df
    for filename in os.listdir("files"):
        with open(os.path.join("files",filename),'r') as f:
            text = f.read()
            lines = text.splitlines( )
            nodes = filename.split("-")[0]
            batchSize = filename.split("-")[1]
            latency = lines[-5].split()[-1]
            throughput = lines[-4].split()[-1]
            df = df.append({'Nodes' : nodes, 'BatchSize' : batchSize, 'Latency' : latency, 'Throughput' : throughput}, ignore_index = True)

def createGraphs():
    global figTB
    figTB = px.line(df, x="BatchSize", y="Throughput", color = "Nodes")
    figTB.update_layout(
        plot_bgcolor=colors2['background'],
        paper_bgcolor=colors2['background'],
        font_color=colors2['text']
    )

    global figLB
    figLB = px.line(df, x="BatchSize", y="Latency", color = "Nodes")
    figLB.update_layout(
        plot_bgcolor=colors2['background'],
        paper_bgcolor=colors2['background'],
        font_color=colors2['text']
    )

    global figLN
    figLN = px.line(df.query('BatchSize == 100000', inplace=True), x="Nodes", y="Latency")
    figLN.update_layout(
        plot_bgcolor=colors2['background'],
        paper_bgcolor=colors2['background'],
        font_color=colors2['text']
    )

    global figTN
    figTN = px.line(df.query('BatchSize == 100000', inplace=True), x="Nodes", y="Throughput")
    figTN.update_layout(
        plot_bgcolor=colors2['background'],
        paper_bgcolor=colors2['background'],
        font_color=colors2['text']
    )

    global figLT
    figLT = px.line(df, x="BatchSize", y="Throughput", color = "Nodes")
    figLT.update_layout(
        plot_bgcolor=colors2['background'],
        paper_bgcolor=colors2['background'],
        font_color=colors2['text']
    )


app = Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
app.title = "Graphs"
server = app.server
app.config["suppress_callback_exceptions"] = True

# app.css.append_css({'external_url': '/static/reset.css'})
# app.server.static_folder = 'static'

# see https://plotly.com/python/px-arguments/ for more options

readLogs()
createGraphs()

app.layout = html.Div(style={'backgroundColor': colors['background']}, children=[
    html.H1(
        children='Dumbo Protocol Results',
        style={
            'textAlign': 'center',
            'color': colors['text']
        }
    ),

    html.Div(children='Dash: A web application framework for your data.', style={
        'textAlign': 'center',
        'color': colors['text']
    }),

    dcc.Graph(
        id='example-graph-1',
        figure=figTB, 
        style={'color': colors['text']}
    ),
    dcc.Graph(
        id='example-graph-2',
        figure=figLB, 
        style={'color': colors['text']}
    ),
    dcc.Graph(
        id='example-graph-3',
        figure=figLN, 
        style={'color': colors['text']}
    ),
    dcc.Graph(
        id='example-graph-4',
        figure=figTN, 
        style={'color': colors['text']}
    ),
        dcc.Graph(
        id='example-graph-5',
        figure=figLT, 
        style={'color': colors['text']}
    )
])

if __name__ == '__main__':
    app.run_server(debug=True)
