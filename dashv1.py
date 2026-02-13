# -*- coding: utf-8 -*-
"""
Grain Size Distribution – Master Dashboard (Render-ready)
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
    return {"Clay_0_4": clay, "Silt_4_63": silt, "Sand_63_2000": sand}

# -----------------------
# LOAD DATA
# -----------------------
F = "MS_continuous_Data_20260205.csv"  # CSV in same folder
df = pd.read_csv(F)

df2 = df.melt(
    id_vars=["BoreholeID", "Formation", "SampleName", "depth"],
    value_vars=df.columns[24:124],
    var_name="Size",
    value_name="Percent_Volume"
)
df2["Size"] = pd.to_numeric(df2["Size"], errors="coerce")
df2["Percent_Volume"] = pd.to_numeric(df2["Percent_Volume"], errors="coerce")

# -----------------------
# DASH APP
# -----------------------
app = dash.Dash(__name__)

app.layout = html.Div(
    style={"height": "100vh", "display": "flex", "flexDirection": "column", "padding": "10px"},
    children=[

        html.H2("Grain Size Distribution – Master Dashboard"),

        # -------- CONTROLS --------
        html.Div(
            style={"display": "flex", "gap": "20px", "marginBottom": "10px", "flexWrap": "wrap"},
            children=[

                html.Div([
                    html.Label("Borehole(s)"),
                    dcc.Dropdown(
                        id="borehole-dropdown",
                        options=[{"label": b, "value": b} for b in sorted(df2["BoreholeID"].dropna().unique())],
                        value=sorted(df2["BoreholeID"].dropna().unique()),
                        multi=True
                    )
                ], style={"width": "350px"}),

                html.Div([
                    html.Label("Formation(s)"),
                    dcc.Dropdown(
                        id="formation-dropdown",
                        multi=True
                    )
                ], style={"width": "450px"}),

            ]
        ),

        # -------- MAIN CONTENT --------
        html.Div(
            style={"display": "flex", "flex": "1", "gap": "15px", "minHeight": "0"},
            children=[

                # ---- PLOTS ----
                html.Div(
                    style={"flex": "3", "minHeight": "0", "display": "flex", "flexDirection": "column", "gap": "15px"},
                    children=[
                        dcc.Graph(id="grain-size-plot", style={"flex": "1", "minHeight": "0"}),
                        dcc.Graph(id="mean-sd-plot", style={"flex": "1", "minHeight": "0"})
                    ]
                ),

                # ---- SUMMARY STATS ----
                html.Div(
                    style={"flex": "1", "padding": "10px", "border": "1px solid #ccc", "borderRadius": "6px", "backgroundColor": "#fafafa"},
                    children=[html.H4("Summary Statistics"), html.Div(id="summary-panel")]
                )
            ]
        )
    ]
)

# -----------------------
# DYNAMIC FORMATION DROPDOWN
# -----------------------
@app.callback(
    Output("formation-dropdown", "options"),
    Output("formation-dropdown", "value"),
    Input("borehole-dropdown", "value")
)
def update_formation_options(selected_boreholes):
    if not selected_boreholes:
        return [], []
    filtered = df2[df2["BoreholeID"].isin(selected_boreholes)]
    formations = sorted(filtered["Formation"].dropna().unique())
    return [{"label": f, "value": f} for f in formations], formations

# -----------------------
# UPDATE DASHBOARD
# -----------------------
@app.callback(
    Output("grain-size-plot", "figure"),
    Output("mean-sd-plot", "figure"),
    Output("summary-panel", "children"),
    Input("borehole-dropdown", "value"),
    Input("formation-dropdown", "value")
)
def update_dashboard(boreholes, formations):
    if not boreholes:
        return px.line(), px.line(), "No data selected"

    dff = df2[df2["BoreholeID"].isin(boreholes)]
    if formations:
        dff = dff[dff["Formation"].isin(formations)]

    # ---------------- PLOT 1: individual samples ----------------
    fig_samples = px.line(
        dff,
        x="Size",
        y="Percent_Volume",
        color="SampleName",
        line_group="SampleName",
        log_x=True,
        template="plotly_white"
    )
    fig_samples.update_layout(
        xaxis_title="Size (µm)",
        yaxis_title="Percent Volume",
        legend_title="SampleName",
        margin=dict(l=60, r=40, t=40, b=60)
    )
    fig_samples.update_xaxes(range=[-2, 3.7])

    # ---------------- PLOT 2: Mean ± SD ----------------
    stats_df = dff.groupby("Size")["Percent_Volume"].agg(["mean", "std"]).reset_index()
    stats_df["upper"] = stats_df["mean"] + stats_df["std"]
    stats_df["lower"] = stats_df["mean"] - stats_df["std"]

    fig_mean_sd = go.Figure()
    fig_mean_sd.add_trace(go.Scatter(
        x=stats_df["Size"], y=stats_df["upper"],
        line=dict(color='lightblue'),
        showlegend=False
    ))
    fig_mean_sd.add_trace(go.Scatter(
        x=stats_df["Size"], y=stats_df["lower"],
        line=dict(color='lightblue'),
        fill='tonexty',
        fillcolor='rgba(173,216,230,0.3)',
        showlegend=False
    ))
    fig_mean_sd.add_trace(go.Scatter(
        x=stats_df["Size"], y=stats_df["mean"],
        line=dict(color='blue', width=3),
        name="Mean"
    ))
    fig_mean_sd.update_layout(
        title="Mean ± Standard Deviation",
        xaxis_title="Size (µm)",
        yaxis_title="Percent Volume",
        template="plotly_white",
        margin=dict(l=60, r=40, t=40, b=60)
    )
    fig_mean_sd.update_xaxes(type="log", range=[-2, 3.7])

    # ---------------- SUMMARY STATS ----------------
    d_stats, tex_stats = [], []
    for sample, g in dff.groupby("SampleName"):
        if g["Percent_Volume"].sum() > 0:
            d_stats.append(compute_d_values(g))
            tex_stats.append(texture_fractions(g))

    d_df = pd.DataFrame(d_stats)
    t_df = pd.DataFrame(tex_stats)

    summary = [
        html.H5("Grain Size Percentiles (Mean)"),
        html.P(f"D10: {d_df['D10'].mean():.1f} µm"),
        html.P(f"D50: {d_df['D50'].mean():.1f} µm"),
        html.P(f"D90: {d_df['D90'].mean():.1f} µm"),
        html.Hr(),
        html.H5("Texture Fractions (Mean %)"),
        html.P(f"Clay (0–4 µm): {t_df['Clay_0_4'].mean():.1f}%"),
        html.P(f"Silt (4–63 µm): {t_df['Silt_4_63'].mean():.1f}%"),
        html.P(f"Sand (63–2000 µm): {t_df['Sand_63_2000'].mean():.1f}%"),
        html.Hr(),
        html.P(f"Samples: {dff['SampleName'].nunique()}"),
        html.P(f"Boreholes: {dff['BoreholeID'].nunique()}"),
        html.P(f"Formations: {dff['Formation'].nunique()}")
    ]

    return fig_samples, fig_mean_sd, summary

# -----------------------
# RUN APP
# -----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port)
