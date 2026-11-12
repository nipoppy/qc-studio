"""Shared look for the admin dashboard's Plotly charts.

Colours: one blue ramp for every magnitude (heatmaps, coverage), a neutral grey for "no data",
and fixed QC-outcome colours (green = pass, blue = mixed, orange = uncertain, red = fail).
The outcome set was checked for colour-vision-deficiency separation; Missing is a deliberate
light grey that recedes behind the outcomes.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# Sequential blue, light -> dark (light end = near zero).
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#104281"]
NO_DATA = "#e1e0d9"

QC_COLORS = {"All-Pass": "#0ca30c", "Mixed": "#5598e7", "All-Uncertain": "#ec835a", "All-Fail": "#d03b3b", "All-Missing": "#c9c8c1"}
VALUE_COLORS = {"PASS": "#0ca30c", "UNCERTAIN": "#ec835a", "FAIL": "#d03b3b", "MISSING": "#c9c8c1"}
COVERAGE_COLORS = {"0": NO_DATA, "1": BLUE_RAMP[1], "2": BLUE_RAMP[3], "3+": BLUE_RAMP[5]}


def _surface() -> str:
    """App background, used for the 2px gaps between stacked segments."""
    try:
        return "#0e1117" if st.context.theme.type == "dark" else "#ffffff"
    except Exception:  # outside a running app (tests)
        return "#ffffff"


def style_bars(fig, height: int | None = None):
    """Horizontal bars: rounded ends, 2px gaps, value grid only, one-row legend on top."""
    fig.update_traces(marker_line_color=_surface(), marker_line_width=2)
    fig.update_layout(
        barcornerradius=4,
        bargap=0.3,
        legend=dict(orientation="h", yref="container", y=1, yanchor="top", xanchor="left", x=0, title_text=""),
        margin=dict(t=70, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, zeroline=False, automargin=True)
    fig.update_yaxes(showgrid=False, automargin=True)
    if height:
        fig.update_layout(height=height)
    return fig


def style_heatmap(fig, z=None, height: int | None = None):
    """Heatmap: blue ramp, white cell gaps, no grid; cells where ``z`` (a DataFrame) is NaN drawn grey."""
    fig.update_traces(xgap=2, ygap=2)
    if z is not None and z.isna().to_numpy().any():
        mask = z.isna().astype(float).where(z.isna())  # 1 where empty, else NaN (not drawn)
        under = go.Heatmap(
            z=mask.values,
            x=list(z.columns),
            y=list(z.index),
            colorscale=[[0, NO_DATA], [1, NO_DATA]],
            showscale=False,
            hoverinfo="skip",
            xgap=2,
            ygap=2,
        )
        fig.add_trace(under)
        fig.data = (fig.data[-1],) + fig.data[:-1]  # grey layer underneath
    fig.update_layout(
        coloraxis_colorscale=BLUE_RAMP,
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False, automargin=True)
    if height:
        fig.update_layout(height=height)
    return fig
