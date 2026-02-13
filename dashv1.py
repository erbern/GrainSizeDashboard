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
                        dcc.Graph(id="mean-sd-pl
