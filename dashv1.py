# -*- coding: utf-8 -*-
"""
Created on Fri Feb 13 13:44:58 2026

@author: nhz3915
"""

# -*- coding: utf-8 -*-
"""
Grain Size Distribution – Master Dashboard with Mean ± SD and Ternary Plot
With Borehole, Formation, and Binned Depth Filters
"""

import numpy as np
import pandas as pd
import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go
import webbrowser

# -----------------------
# FUNCTIONS
# -----------------------
def compute_d_values(df_sample):
    d = df_sample.sort_values("Size").dropna(subset=["Size", "Percent_Volume"])
    d["cum_pct"] = d["Percent_Volume"].cumsum()

    def interp_d(target):
        return np.interp(target, d["cum_pct"], d["Size"])

    return {"D10": interp_d(10), "D50": interp_d(50), "D90": interp_d(90)}

def texture_fractions(df_sample):
    clay = df_sample.loc[df_sample["Size"] < 4, "Percent_Volume"].sum()
    silt = df_sample.loc[(df_sample["Size"] >= 4) & (df_sample["Size"] < 63), "Percent_Volume"].sum()
    sand = df_sample.loc[(df_sample["Size"] >= 63) & (df_sample["Size"] <= 2000), "Percent_Volume"].sum()
    return {"Clay": clay, "Silt": silt, "Sand": sand}

# -----------------------
# LOAD DATA
# -----------------------
F = "MS_continuous_Data_20260205.csv"
df = pd.read_csv(F)

df2 = df.melt(
    id_vars=["BoreholeID", "Formation", "SampleName", "depth"],
    value_vars=df.columns[24:124],
    var_name="Size",
    value_name="Percent_Volume"
)

df2["Size"] = pd.to_numeric(df2["Size"], errors="coerce")
df2["Percent_Volume"] = pd.to_numeric(df2["Percent_Volume"], errors="coerce")

DEFAULT_BOREHOLE = sorted(df2["BoreholeID"].dropna().unique())[0]

# -----------------------
# DEPTH BINNING (NEW)
# -----------------------
DEPTH_BIN_SIZE = 5  # feet

df2["DepthBin"] = (np.floor(df2["depth"] / DEPTH_BIN_SIZE) * DEPTH_BIN_SIZE).astype(int)
df2["DepthBinLabel"] = (
    df2["DepthBin"].astype(str) + "–" +
    (df2["DepthBin"] + DEPTH_BIN_SIZE).astype(str) + " ft"
)

# -----------------------
# PRECOMPUTE STATS (UNCHANGED LOGIC)
# -----------------------
sample_stats = []

for sample_name, g in df2.groupby("SampleName"):
    if g["Percent_Volume"].sum() > 0:
        d_vals = compute_d_values(g)
        tex_vals = texture_fractions(g)
        d_vals.update(tex_vals)
        d_vals.update({
            "SampleName": sample_name,
            "Formation": g["Formation"].iloc[0],
            "BoreholeID": g["BoreholeID"].iloc[0],
            "DepthBinLabel": g["DepthBinLabel"].iloc[0]  # NEW
        })
        sample_stats.append(d_vals)

df_stats = pd.DataFrame(sample_stats)



formations_by_borehole = df2.groupby("BoreholeID")["Formation"].unique().to_dict()

# -----------------------
# DASH APP
# -----------------------
app = dash.Dash(__name__)

app.layout = html.Div(
    style={"height": "100vh", "display": "flex", "flexDirection": "column", "padding": "10px"},
    children=[

        html.H2("Grain Size Distribution – Master Dashboard"),

        html.Div(
            style={"display": "flex", "gap": "20px", "marginBottom": "10px", "flexWrap": "wrap"},
            children=[

                html.Div([
                    html.Label("Borehole(s)"),
                    dcc.Dropdown(
                        id="borehole-dropdown",
                        options=[{"label": b, "value": b}
                                 for b in sorted(df2["BoreholeID"].dropna().unique())],
                        value=[DEFAULT_BOREHOLE],  # <-- only one borehole on load
                        multi=True
                    )
                ], style={"width": "320px"}),

                html.Div([
                    html.Label("Formation(s)"),
                    dcc.Dropdown(id="formation-dropdown", multi=True)
                ], style={"width": "420px"}),

                html.Div([
                    html.Label("Depth Bin(s)"),
                    dcc.Dropdown(
                        id="depthbin-dropdown",
                        options=[{"label": d, "value": d}
                                 for d in sorted(df2["DepthBinLabel"].unique())],
                        value=sorted(df2["DepthBinLabel"].unique()),
                        multi=True
                    )
                ], style={"width": "320px"})
            ]
        ),

        html.Div(
            style={"display": "flex", "flex": "1", "gap": "15px", "minHeight": "0"},
            children=[

                html.Div(
                    style={"flex": "2", "display": "flex", "flexDirection": "column", "gap": "15px"},
                    children=[
                        dcc.Graph(id="grain-size-plot"),
                        dcc.Graph(id="mean-sd-plot")
                    ]
                ),

                html.Div(
                    style={"flex": "1", "display": "flex", "flexDirection": "column", "gap": "15px"},
                    children=[
                        dcc.Graph(id="ternary-plot", style={"height": "400px"}),
                        html.Div(
                            style={"overflowY": "auto", "border": "1px solid #ccc", "padding": "10px"},
                            children=[html.H4("Summary Statistics"), html.Div(id="summary-panel")]
                        )
                    ]
                )
            ]
        )
    ]
)

# -----------------------
# FORMATION DROPDOWN
# -----------------------
@app.callback(
    Output("formation-dropdown", "options"),
    Output("formation-dropdown", "value"),
    Input("borehole-dropdown", "value")
)
def update_formation_options(boreholes):
    if not boreholes:
        return [], []
    formations = sorted({f for b in boreholes for f in formations_by_borehole.get(b, [])})
    return [{"label": f, "value": f} for f in formations], formations

# -----------------------
# MAIN CALLBACK
# -----------------------
@app.callback(
    Output("grain-size-plot", "figure"),
    Output("mean-sd-plot", "figure"),
    Output("ternary-plot", "figure"),
    Output("summary-panel", "children"),
    Input("borehole-dropdown", "value"),
    Input("formation-dropdown", "value"),
    Input("depthbin-dropdown", "value")
)
def update_dashboard(boreholes, formations, depthbins):

    if not boreholes:
        return px.line(), px.line(), px.line(), "No data selected"

    dff = df2[df2["BoreholeID"].isin(boreholes)]
    if formations:
        dff = dff[dff["Formation"].isin(formations)]
    if depthbins:
        dff = dff[dff["DepthBinLabel"].isin(depthbins)]

    stats_filtered = df_stats[df_stats["BoreholeID"].isin(boreholes)]
    if formations:
        stats_filtered = stats_filtered[stats_filtered["Formation"].isin(formations)]
    if depthbins:
        stats_filtered = stats_filtered[stats_filtered["DepthBinLabel"].isin(depthbins)]

    # --- COMPUTE MEAN ± SD FROM WHAT IS ACTUALLY PLOTTED ---
    mean_sd_filtered = (
        dff
        .groupby(["Formation", "Size"])["Percent_Volume"]
        .agg(mean="mean", std="std")
        .reset_index()
        )


    # -------- GRAIN SIZE --------
    fig_samples = px.line(
        dff, x="Size", y="Percent_Volume",
        color="Formation", line_group="SampleName",
        log_x=True, template="plotly_white"
    )
    fig_samples.update_xaxes(range=[-2, 3.7])

    # -------- MEAN ± SD PLOT --------
    # -------- MEAN ± SD PLOT (MATCHES PLOT 1) --------
    fig_mean_sd = go.Figure()
    colors = px.colors.qualitative.Dark24
    
    for i, formation in enumerate(mean_sd_filtered["Formation"].unique()):
        f_data = mean_sd_filtered[mean_sd_filtered["Formation"] == formation]
        color = colors[i % len(colors)]
        
        fig_mean_sd.add_trace(go.Scatter(
            x=f_data["Size"],
            y=f_data["mean"],
            line=dict(color=color, width=3),
            name=f"{formation} Mean"
            ))
        
        fig_mean_sd.add_trace(go.Scatter(
            x=f_data["Size"],
            y=f_data["mean"] + f_data["std"],
            line=dict(color=color),
            showlegend=False
            ))
        
        fig_mean_sd.add_trace(go.Scatter(
            x=f_data["Size"],
            y=f_data["mean"] - f_data["std"],
            fill="tonexty",
            fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.3)",
            line=dict(color=color),
            showlegend=False
            ))
        
        fig_mean_sd.update_layout(
            title="Mean ± Standard Deviation (Filtered Samples)",
            xaxis_title="Size (µm)",
            yaxis_title="Percent Volume",
            template="plotly_white",
            margin=dict(l=60, r=40, t=40, b=60)
            )
        
        fig_mean_sd.update_xaxes(type="log", range=[-2, 3.7])


    # -------- TERNARY --------
    fig_tern = px.scatter_ternary(
        stats_filtered,
        a="Clay", b="Sand", c="Silt",
        color="Formation",
        hover_name="SampleName",
        template="plotly_white"
    )

    # -------- SUMMARY --------
    summary = [
        html.P(f"Total Boreholes selected: {stats_filtered['BoreholeID'].nunique()}"),
        html.P(f"Total Samples selected: {stats_filtered['SampleName'].nunique()}"),
        html.Hr()
    ]

    for formation, fg in stats_filtered.groupby("Formation"):
        summary.extend([
            html.H5(f"Formation: {formation}"),
            html.P(f"D10: {fg['D10'].mean():.1f} µm"),
            html.P(f"D50: {fg['D50'].mean():.1f} µm"),
            html.P(f"D90: {fg['D90'].mean():.1f} µm"),
            html.P(f"Clay: {fg['Clay'].mean():.1f}%"),
            html.P(f"Silt: {fg['Silt'].mean():.1f}%"),
            html.P(f"Sand: {fg['Sand'].mean():.1f}%"),
            html.Hr()
        ])

    return fig_samples, fig_mean_sd, fig_tern, summary

# -----------------------
# RUN APP
# -----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port)

