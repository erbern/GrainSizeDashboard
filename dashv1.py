# -*- coding: utf-8 -*-
"""
Grain Size Distribution – Master Dashboard with Mean ± SD and Ternary Plot
Optimized for speed with working dropdowns
Adapted for Render.com deployment
"""

import os
import numpy as np
import pandas as pd
import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go

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
F = os.path.join(os.path.dirname(__file__), "MS_continuous_Data_20260205.csv")
df = pd.read_csv(F)

df2 = df.melt(
    id_vars=["BoreholeID", "Formation", "SampleName", "depth"],
    value_vars=df.columns[24:124],
    var_name="Size",
    value_name="Percent_Volume"
)
df2["Size"] = pd.to_numeric(df2["Size"], errors="coerce")
df2["Percent_Volume"] = pd.to_numeric(df2["Percent_Volume"], errors="coerce")
df2["BoreholeID"] = df2["BoreholeID"].astype(str)

# -----------------------
# PRECOMPUTE STATS
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
            "BoreholeID": g["BoreholeID"].iloc[0]
        })
        sample_stats.append(d_vals)
df_stats = pd.DataFrame(sample_stats)

mean_sd_df = df2.groupby(["Formation", "Size"])["Percent_Volume"].agg(["mean", "std"]).reset_index()
formations_by_borehole = {str(k): v for k, v in df2.groupby("BoreholeID")["Formation"].unique().to_dict().items()}

# -----------------------
# DASH APP
# -----------------------
app = dash.Dash(__name__)

# -----------------------
# APP LAYOUT
# -----------------------
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
                        options=[{"label": b, "value": b} for b in sorted(df2["BoreholeID"].unique())],
                        value=sorted(df2["BoreholeID"].unique()),
                        multi=True
                    )
                ], style={"width": "350px"}),
                html.Div([
                    html.Label("Formation(s)"),
                    dcc.Dropdown(id="formation-dropdown", multi=True)
                ], style={"width": "450px"}),
            ]
        ),
        html.Div(
            style={"display": "flex", "flex": "1", "gap": "15px", "minHeight": "0"},
            children=[
                html.Div(
                    style={"flex": "2", "display": "flex", "flexDirection": "column", "gap": "15px", "minHeight": "0"},
                    children=[
                        dcc.Graph(id="grain-size-plot", style={"flex": "1", "minHeight": "0"}),
                        dcc.Graph(id="mean-sd-plot", style={"flex": "1", "minHeight": "0"})
                    ]
                ),
                html.Div(
                    style={"flex": "1", "display": "flex", "flexDirection": "column", "gap": "15px", "minHeight": "0"},
                    children=[
                        dcc.Graph(id="ternary-plot", style={"height": "400px", "flex": "0 0 auto"}),
                        html.Div(
                            style={
                                "flex": "1",
                                "padding": "10px",
                                "border": "1px solid #ccc",
                                "borderRadius": "6px",
                                "backgroundColor": "#fafafa",
                                "overflowY": "auto"
                            },
                            children=[html.H4("Summary Statistics"), html.Div(id="summary-panel")]
                        )
                    ]
                )
            ]
        )
    ]
)

# -----------------------
# FORMATION DROPDOWN CALLBACK
# -----------------------
@app.callback(
    Output("formation-dropdown", "options"),
    Output("formation-dropdown", "value"),
    Input("borehole-dropdown", "value")
)
def update_formation_options(selected_boreholes):
    if not selected_boreholes:
        return [], []
    selected_boreholes = [str(b) for b in selected_boreholes]
    formations = sorted({f for b in selected_boreholes for f in formations_by_borehole.get(b, [])})
    options = [{"label": f, "value": f} for f in formations]
    return options, [f["value"] for f in options]

# -----------------------
# UPDATE DASHBOARD CALLBACK
# -----------------------
@app.callback(
    Output("grain-size-plot", "figure"),
    Output("mean-sd-plot", "figure"),
    Output("ternary-plot", "figure"),
    Output("summary-panel", "children"),
    Input("borehole-dropdown", "value"),
    Input("formation-dropdown", "value")
)
def update_dashboard(boreholes, formations):
    if not boreholes:
        empty_fig = px.line(title="No data selected")
        return empty_fig, empty_fig, empty_fig, "No data selected"

    boreholes = [str(b) for b in boreholes]
    dff = df2[df2["BoreholeID"].isin(boreholes)]
    if formations:
        dff = dff[dff["Formation"].isin(formations)]
        stats_filtered = df_stats[df_stats["Formation"].isin(formations) & df_stats["BoreholeID"].isin(boreholes)]
        mean_sd_filtered = mean_sd_df[mean_sd_df["Formation"].isin(formations)]
    else:
        stats_filtered = df_stats[df_stats["BoreholeID"].isin(boreholes)]
        mean_sd_filtered = mean_sd_df

    if dff.empty or stats_filtered.empty:
        empty_fig = px.line(title="No data for selection")
        return empty_fig, empty_fig, empty_fig, "No data for selected boreholes/formations"

    # Grain size plot
    fig_samples = go.Figure()
    colors = px.colors.qualitative.Dark24

    for i, formation in enumerate(mean_sd_filtered["Formation"].unique()):
        f_data = mean_sd_filtered[mean_sd_filtered["Formation"] == formation]
        if f_data.empty:
            continue

        fig_samples.add_trace(go.Scattergl(
            x=f_data["Size"],
            y=f_data["mean"],
            mode="lines",
            line=dict(width=2, color=colors[i % len(colors)]),
            name=formation
            ))

    fig_samples.update_layout(
        xaxis_title="Size (µm)",
        yaxis_title="Percent Volume",
        legend_title="Formation",
        template="plotly_white",
        margin=dict(l=60, r=40, t=40, b=60)
        )
    fig_samples.update_xaxes(type="log", range=[-2, 3.7])

        
    fig_samples.update_layout(xaxis_title="Size (µm)", yaxis_title="Percent Volume", legend_title="Formation", margin=dict(l=60, r=40, t=40, b=60))
    fig_samples.update_xaxes(range=[-2, 3.7])

    # Mean ± SD plot
    fig_mean_sd = go.Figure()
    colors = px.colors.qualitative.Dark24
    for i, formation in enumerate(mean_sd_filtered["Formation"].unique()):
        f_data = mean_sd_filtered[mean_sd_filtered["Formation"] == formation]
        if f_data.empty:
            continue
        color = colors[i % len(colors)]
        fig_mean_sd.add_trace(go.Scatter(x=f_data["Size"], y=f_data["mean"], line=dict(color=color, width=3), name=f"{formation} Mean"))
        fig_mean_sd.add_trace(go.Scatter(x=f_data["Size"], y=f_data["mean"] + f_data["std"], line=dict(color=color), showlegend=False))
        fig_mean_sd.add_trace(go.Scatter(x=f_data["Size"], y=f_data["mean"] - f_data["std"], line=dict(color=color), fill='tonexty', fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.3)", showlegend=False))
    fig_mean_sd.update_layout(title="Mean ± Standard Deviation per Formation", xaxis_title="Size (µm)", yaxis_title="Percent Volume", template="plotly_white", margin=dict(l=60, r=40, t=40, b=60))
    fig_mean_sd.update_xaxes(type="log", range=[-2, 3.7])

    # Ternary plot
    if not stats_filtered.empty:
        stats_filtered = stats_filtered[(stats_filtered["Clay"] + stats_filtered["Silt"] + stats_filtered["Sand"]) > 0]
        if not stats_filtered.empty:
            formations_in_data = stats_filtered["Formation"].dropna().unique()
            color_map = {f: colors[i % len(colors)] for i, f in enumerate(formations_in_data)}
            fig_tern = px.scatter_ternary(stats_filtered, a="Clay", b="Sand", c="Silt", color="Formation", color_discrete_map=color_map, hover_name="SampleName", template="plotly_white", title="Sand-Silt-Clay Composition")
            fig_tern.update_layout(ternary=dict(sum=100, baxis=dict(title='Sand', min=0), caxis=dict(title='Silt', min=0), aaxis=dict(title='Clay', min=0)), margin=dict(l=40, r=40, t=60, b=40))
        else:
            fig_tern = px.scatter_ternary(title="No data for ternary plot")
    else:
        fig_tern = px.scatter_ternary(title="No data for ternary plot")

    # Summary
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
            html.P(f"Clay (0–4 µm): {fg['Clay'].mean():.1f}%"),
            html.P(f"Silt (4–63 µm): {fg['Silt'].mean():.1f}%"),
            html.P(f"Sand (63–2000 µm): {fg['Sand'].mean():.1f}%"),
            html.Hr()
        ])

    return fig_samples, fig_mean_sd, fig_tern, summary

# -----------------------
# RUN APP (Render.com)
# -----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=True, host="0.0.0.0", port=port)
