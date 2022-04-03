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
    for filename in os.listdir("./nodelogs"):
        with open(os.path.join("./nodelogs",filename),'r') as f:
            text = f.read()
            lines = text.splitlines( )
            # print(lines)
            nodes = filename.split("-")[0]
            batchSize = filename.split("-")[1]
            latency = lines[-3].split()[-1]
            throughput = lines[-2].split()[-1]
            # print(nodes + " - " + batchSize)
            df = df.append({'Nodes' : int(nodes), 'BatchSize' : int(batchSize), 'Latency' : float(latency), 'Throughput' : float(throughput)}, ignore_index = True)
    df2 = df.sort_values(by=['BatchSize'])
    df = df2
    # print(df2)

def createGraphs():
    global figTB
    figTB = px.line(df, x="BatchSize", y="Throughput", color = "Nodes", title="Batch Size Vs Throughput")
    figTB.update_layout(
        plot_bgcolor=colors2['background'],
        paper_bgcolor=colors2['background'],
        font_color=colors2['text']
    )

    global figLB
    figLB = px.line(df, x="BatchSize", y="Latency", color = "Nodes", title="Batch Size Vs Latency")
    figLB.update_layout(
        plot_bgcolor=colors2['background'],
        paper_bgcolor=colors2['background'],
        font_color=colors2['text']
    )

    bSize = 100000
    rslt_df = df[df['BatchSize'] == bSize]
    rslt_df = rslt_df.sort_values(by=['Nodes'])
    figName = "Nodes Vs Latency For B=" + str(bSize)

    global figLN
    figLN = px.line(rslt_df, x="Nodes", y="Latency", title=figName)
    figLN.update_layout(
        plot_bgcolor=colors2['background'],
        paper_bgcolor=colors2['background'],
        font_color=colors2['text']
    )

    figName = "Nodes Vs Throughput For B=" + str(bSize)

    global figTN
    figTN = px.line(rslt_df, x="Nodes", y="Throughput", title=figName)
    figTN.update_layout(
        plot_bgcolor=colors2['background'],
        paper_bgcolor=colors2['background'],
        font_color=colors2['text']
    )

    global figLT
    allNodes = 1
    numOfNodes = 85
    

    if (allNodes == 0):
        rslt_df = df.sort_values(by=['Throughput'])
        
        figLT = px.line(rslt_df, x="Throughput", y="Latency", color = "Nodes", title="Throughput Vs Latency")
        figLT.update_layout(
            plot_bgcolor=colors2['background'],
            paper_bgcolor=colors2['background'],
            font_color=colors2['text']
        )
    else:
        rslt_df = df[df['Nodes'] == numOfNodes]
        rslt_df = rslt_df.sort_values(by=['Throughput'])
        figName = "Throughput Vs Latency For Nodes=" + str(numOfNodes)
        print(rslt_df)
        figLT = px.line(rslt_df, x="Throughput", y="Latency", title=figName)
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
