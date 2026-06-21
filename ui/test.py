# import streamlit as st
# import pandas as pd
# import plotly.express as px

# df_st = pd.read_csv("./group_T1w.tsv", sep="\t")

# # Example data


# distribution_groups = {
#     "EFC": ["efc"],
#     "FBER": ["fber"],
#     "FWHM": ["fwhm_x", "fwhm_y", "fwhm_z"],
# }

# selected_group = st.selectbox("Choose distribution to display", list(distribution_groups.keys()))

# for col in distribution_groups[selected_group]:
#     st.subheader(col)
#     fig = px.histogram(df_st, x=col, nbins=30)
#     st.plotly_chart(fig, use_container_width=True)


# import streamlit as st
# import pandas as pd
# import numpy as np
# import matplotlib.pyplot as plt

# df = pd.read_csv("group_T1w.tsv", sep="\t")

# distribution_groups = {
#     "EFC": ["efc"],
#     "FBER": ["fber"],
#     "FWHM": ["fwhm_x", "fwhm_y", "fwhm_z"],
# }

# group_name = st.selectbox("Select group", list(distribution_groups.keys()))
# cols = distribution_groups[group_name]

# fig, ax = plt.subplots(figsize=(6, 6))

# positions = np.arange(1, len(cols) + 1)

# # boxplot (one per column)
# data = [df[c].dropna().values for c in cols]

# bp = ax.boxplot(
#     data,
#     positions=positions,
#     widths=0.2,
#     patch_artist=True,
#     showmeans=True
# )

# # style (optional but matches your look)
# for box in bp["boxes"]:
#     box.set(facecolor="lightgray", edgecolor="dimgray", linewidth=2)
# for whisker in bp["whiskers"]:
#     whisker.set(color="dimgray", linewidth=2)
# for cap in bp["caps"]:
#     cap.set(color="dimgray", linewidth=2)
# for median in bp["medians"]:
#     median.set(color="dimgray", linewidth=2)
# for mean in bp["means"]:
#     mean.set(marker="o", markerfacecolor="white", markeredgecolor="black", markersize=9)

# # scatter (one color per column)
# colors = ["tab:blue", "tab:orange", "tab:green"]

# for i, col in enumerate(cols):
#     y = df[col].dropna().values
#     x = np.random.normal(loc=positions[i], scale=0.05, size=len(y))  # jitter
#     ax.scatter(x, y, alpha=0.35, s=35, color=colors[i % len(colors)], edgecolors="none")

# ax.set_xticks(positions)
# ax.set_xticklabels(cols, rotation=45)
# ax.set_ylabel(group_name)
# ax.grid(axis="y", linestyle="--", alpha=0.4)

# plt.tight_layout()
# st.pyplot(fig)

# import streamlit as st
# import pandas as pd
# import plotly.graph_objects as go

# df = pd.read_csv("group_T1w.tsv", sep="\t")

# distribution_groups = {
#     "EFC": ["efc"],
#     "FBER": ["fber"],
#     "FWHM": ["fwhm_x", "fwhm_y", "fwhm_z"],
# }

# group_name = st.selectbox("Select group", list(distribution_groups.keys()))
# cols = distribution_groups[group_name]

# fig = go.Figure()

# for col in cols:
#     fig.add_trace(go.Violin(
#         y=df[col].dropna(),
#         name=col,
#         box_visible=True,
#         meanline_visible=True,
#         points="all"
#     ))

# fig.update_layout(
#     title=f"{group_name} distributions",
#     yaxis_title=group_name,
#     xaxis_title="Metric",
#     template="plotly_white",
#     height=600
# )

# st.plotly_chart(fig, use_container_width=True)
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

df = pd.read_csv("./group_T1w.tsv", sep="\t")
ref_df = pd.read_csv("./group_T1w.tsv", sep="\t")

distribution_groups = {
    "EFC": ["efc"],
    "FBER": ["fber"],
    "FWHM": ["fwhm_x", "fwhm_y", "fwhm_z"],
}

group_name = st.selectbox("Select group", list(distribution_groups.keys()))
cols = distribution_groups[group_name]

mode = st.radio("Display mode", ["Dataset only", "Dataset + reference", "Reference only"], horizontal=True)

fig = go.Figure()

if mode == "Dataset only":
    for i, col in enumerate(cols):
        if col not in df.columns:
            continue

        fig.add_trace(
            go.Box(
                y=df[col].dropna(),
                name=col,
                boxpoints="all",
                jitter=0.45,
                pointpos=0,
                marker_size=4,
                opacity=0.6,
                legendgroup="dataset",
                showlegend=(i == 0),
                legendgrouptitle_text="Source",
                marker=dict(symbol="circle"),
                hovertemplate=f"Source: Dataset<br>Metric: {col}<br>Value: %{{y}}<extra></extra>",
            )
        )

else:
    for i, col in enumerate(cols):
        if col in df.columns:
            fig.add_trace(
                go.Box(
                    y=df[col].dropna(),
                    name=col,
                    boxpoints="all",
                    jitter=0.45,
                    pointpos=-0.3,
                    marker_size=4,
                    opacity=0.6,
                    legendgroup="dataset",
                    showlegend=(i == 0),
                    legendgrouptitle_text="Source",
                    marker=dict(symbol="circle"),
                    hovertemplate=f"Source: Dataset<br>Metric: {col}<br>Value: %{{y}}<extra></extra>",
                )
            )

        if col in ref_df.columns:
            fig.add_trace(
                go.Box(
                    y=ref_df[col].dropna(),
                    name=col,
                    boxpoints="all",
                    jitter=0.45,
                    pointpos=0.3,
                    marker_size=4,
                    opacity=0.6,
                    legendgroup="reference",
                    showlegend=(i == 0),
                    marker=dict(symbol="diamond"),
                    hovertemplate=f"Source: Reference<br>Metric: {col}<br>Value: %{{y}}<extra></extra>",
                )
            )

fig.update_layout(
    title=f"{group_name} distributions",
    xaxis_title="Metric",
    yaxis_title="Value",
    template="plotly_white",
    height=650,
    boxmode="group",
    legend_title="Source",
)

st.plotly_chart(fig, use_container_width=True)


"""QC viewer component for displaying MRI, SVG, and metrics panels."""
import streamlit as st
from constants import SVG_HEIGHT, MESSAGES, ERROR_MESSAGES, QC_RATINGS, NIIVUE_SECONDARY_RATIO
from utils import load_svg_data
from niivue_viewer_manager import NiivueViewerManager
from session_manager import SessionManager
from ui.components.iqm_viewer import display_iqm_panel
from models import QCRecord
from datetime import datetime


def display_qc_viewers(
    dataset_dir,
    qc_config,
    qc_config_path: str = None,
    participant_id: str = None,
    session_id: str = None,
    qc_pipeline: str = None,
    qc_task: str = None,
    total_participants: int = None,
) -> None:
    """Display QC viewers (Niivue, SVG, IQM panels) based on user selection.

    Layout strategy:
    - If all three panels (Niivue + SVG + IQM): 3-column (controls | Niivue | SVG), then IQM and rating in 2-columns
    - If Niivue + SVG selected: 3-column layout (controls | Niivue | SVG)
    - If SVG only selected: Full-width SVG
    - If Niivue + IQM selected: 3-column layout (controls | Niivue | IQM)
    - If Niivue only selected: Full-width Niivue

    Args:
            dataset_dir: Root dataset directory
            qc_config: Parsed QC configuration dictionary
            qc_config_path: Path to the raw QC JSON file (needed for IQM distributions)
            participant_id: Current participant ID
            session_id: Current session ID
            qc_pipeline: QC pipeline name
            qc_task: QC task name
            total_participants: Total number of participants
    """
    st.container()

    # Get selected panels and normalize naming for backward compatibility
    selected_panels = SessionManager.get_selected_panels()
    selected_panels = {
        "niivue": selected_panels.get("niivue_col", selected_panels.get("niivue", True)),
        "svg": selected_panels.get("svg_col", selected_panels.get("svg", True)),
        "iqm": selected_panels.get("iqm_col", selected_panels.get("iqm", False)),
    }

    show_niivue = selected_panels.get("niivue", True)
    show_svg = selected_panels.get("svg", True)
    show_iqm = selected_panels.get("iqm", False)

    # All three panels selected: 3-column on top, IQM and QC rating in 2-columns below
    if show_niivue and show_svg and show_iqm:
        _display_niivue_with_secondary_panel(dataset_dir, selected_panels, qc_config, qc_config_path)
        st.divider()
        _display_iqm_and_rating_side_by_side(
            dataset_dir=dataset_dir,
            qc_config_path=qc_config_path,
            participant_id=participant_id,
            session_id=session_id,
            qc_pipeline=qc_pipeline,
            qc_task=qc_task,
            total_participants=total_participants,
        )
    # 3-column layout: Niivue + SVG (no IQM)
    elif show_niivue and show_svg:
        _display_niivue_with_secondary_panel(dataset_dir, selected_panels, qc_config, qc_config_path)
    # 3-column layout: Niivue + IQM (no SVG)
    elif show_niivue and show_iqm:
        _display_niivue_with_secondary_panel(dataset_dir, selected_panels, qc_config, qc_config_path)
    # Full-width Niivue only
    elif show_niivue:
        _display_niivue_full_width(dataset_dir, qc_config)
    # Full-width SVG only
    elif show_svg:
        _display_svg_panel(dataset_dir, qc_config)
    # Full-width IQM only
    elif show_iqm:
        display_iqm_panel(qc_config_path)


def _display_niivue_with_secondary_panel(dataset_dir, selected_panels: dict, qc_config, qc_config_path: str = None) -> None:
    """Display 3-column layout: controls | Niivue viewer | Secondary panel (SVG or IQM).

    Used when Niivue is selected with either SVG or IQM panel.

    Args:
            dataset_dir: Root dataset directory
            selected_panels: Dictionary of selected panels
            qc_config: QC configuration object
            qc_config_path: Path to the raw QC JSON file (needed for IQM distributions)
    """
    ctrl_col, viewer_col, panel_col = st.columns(NIIVUE_SECONDARY_RATIO, gap="small")

    # Left column: Niivue controls
    with ctrl_col:
        niivue_config = NiivueViewerManager.render_controls_panel()

    # Middle column: Niivue viewer (header rendered by render_viewer)
    with viewer_col:
        NiivueViewerManager.render_viewer(dataset_dir, qc_config, niivue_config)

    # Right column: SVG or IQM panel
    with panel_col:
        if selected_panels.get("svg", False):
            _display_svg_panel(dataset_dir, qc_config)
        else:
            display_iqm_panel(qc_config_path)


def _display_niivue_full_width(dataset_dir, qc_config) -> None:
    """Display Niivue in full width with controls on the left.

    Args:
            dataset_dir: Root dataset directory
            qc_config: QC configuration object
    """
    left_col, right_col = st.columns([0.32, 0.68], gap="small")

    with left_col:
        niivue_config = NiivueViewerManager.render_controls_panel()

    with right_col:
        NiivueViewerManager.render_viewer(dataset_dir, qc_config, niivue_config)


def _display_svg_panel(dataset_dir, qc_config) -> None:
    """Display montage panel.

    Args:
            qc_config: QC configuration object
    """
    st.header(MESSAGES["svg_header"])
    svg_data = load_svg_data(dataset_dir, qc_config)
    if svg_data:
        st.components.v1.html(svg_data, height=SVG_HEIGHT, scrolling=True)
    else:
        st.info(ERROR_MESSAGES["svg_not_found"])


def _display_iqm_and_rating_side_by_side(
    dataset_dir,
    qc_config_path: str = None,
    participant_id: str = None,
    session_id: str = None,
    qc_pipeline: str = None,
    qc_task: str = None,
    total_participants: int = None,
) -> None:
    """Display IQM metrics panel in 2-column layout.

    Left column shows IQM metrics. Right column shows QC rating form.

    Args:
            dataset_dir: Root dataset directory
            qc_config_path: Path to the raw QC JSON file (needed for IQM distributions)
            participant_id: Current participant ID
            session_id: Current session ID
            qc_pipeline: QC pipeline name
            qc_task: QC task name
            total_participants: Total number of participants
    """
    metrics_col, rating_col = st.columns([0.5, 0.5], gap="small")

    # Left column: IQM metrics
    with metrics_col:
        display_iqm_panel(qc_config_path)

    # Right column: QC rating form
    with rating_col:
        st.subheader(MESSAGES["qc_rating_header"])
        rating = st.radio(MESSAGES["qc_rating_prompt"], options=QC_RATINGS, index=0, key="side_by_side_rating")
        notes = st.text_area(MESSAGES["qc_notes_prompt"], value=SessionManager.get_notes(), key="side_by_side_notes", height=120)
        SessionManager.set_notes(notes)

        # Save button
        if st.button(MESSAGES["save_csv_button"], use_container_width=True, key="side_by_side_save"):
            _save_qc_record(
                participant_id=participant_id,
                session_id=session_id,
                qc_pipeline=qc_pipeline,
                qc_task=qc_task,
                rating=rating,
                notes=notes,
                total_participants=total_participants,
            )


def _save_qc_record(participant_id: str, session_id: str, qc_pipeline: str, qc_task: str, rating: str, notes: str, total_participants: int) -> None:
    """Save a QC record and mark as complete.

    Args:
            participant_id: Participant ID
            session_id: Session ID
            qc_pipeline: QC pipeline name
            qc_task: QC task name
            rating: QC rating value
            notes: QC notes
            total_participants: Total participants (used to detect end of QC)
    """
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    record = QCRecord(
        participant_id=participant_id,
        session_id=session_id,
        qc_task=qc_task,
        pipeline=qc_pipeline,
        timestamp=timestamp,
        rater_id=SessionManager.get_rater_id(),
        rater_experience=SessionManager.get_rater_experience(),
        rater_fatigue=SessionManager.get_rater_fatigue(),
        final_qc=rating,
        notes=notes,
    )

    SessionManager.add_qc_record(record)
    SessionManager.set_current_page(total_participants + 1)
    st.rerun()


"""IQM distribution viewer component for QC-Studio UI.

Displays grouped Image Quality Metric (IQM) distributions as interactive
Plotly box plots. Supports dataset-only and dataset-vs-reference comparison
modes, with modality (T1w / BOLD) and metric group selection.

Ported from the iqm-distributions PR into the refactored module architecture.
"""
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.utils.iqm_distribution_config import IQM_DISTRIBUTION_GROUPS, REFERENCE_DATA_PATHS
from constants import MESSAGES, ERROR_MESSAGES

logger = logging.getLogger(__name__)

# ── Plot styling ────────────────────────────────────────────────────────────

DATASET_STYLE = {
    "marker": dict(size=4, symbol="circle", color="rgba(31, 119, 180, 0.55)"),
    "line": dict(color="rgba(31, 119, 180, 1.0)"),
    "fillcolor": "rgba(31, 119, 180, 0.25)",
}

REFERENCE_STYLE = {
    "marker": dict(size=4, symbol="diamond", color="rgba(214, 39, 40, 0.55)"),
    "line": dict(color="rgba(214, 39, 40, 1.0)"),
    "fillcolor": "rgba(214, 39, 40, 0.25)",
}

PLOT_HEIGHT = 650


# ── Public entry point ──────────────────────────────────────────────────────


def display_iqm_panel(qc_config_path: Optional[str] = None) -> None:
    """Display the IQM metrics panel.

    If *qc_config_path* is provided and its JSON contains an
    ``iqm_distribution`` key, interactive distribution plots are rendered.
    Otherwise a placeholder message is shown.

    This function is the drop-in replacement for the former
    ``_display_iqm_panel()`` placeholder in ``qc_viewer.py``.

    Args:
        qc_config_path: Path to the pipeline's ``*_qc.json`` file.  The file
            is expected to contain an ``iqm_distribution`` mapping of
            ``{modality: tsv_path}`` alongside the normal QC-task entries.
    """
    st.subheader(MESSAGES["metrics_header"])

    iqm_cfg = _load_iqm_config(qc_config_path)
    if iqm_cfg is None:
        st.info(
            MESSAGES.get(
                "iqm_no_config",
                "No IQM distribution configuration found in qc_config.",
            )
        )
        return

    _render_iqm_distributions(iqm_cfg)


# ── Config loading ──────────────────────────────────────────────────────────


def _load_iqm_config(qc_config_path: Optional[str]) -> Optional[dict]:
    """Read the ``iqm_distribution`` block from the QC config JSON.

    Returns the mapping ``{modality: tsv_path}`` or *None* when the config
    is missing, unreadable, or does not contain the key.
    """
    if not qc_config_path:
        return None

    config_file = Path(qc_config_path)
    if not config_file.is_file():
        logger.warning("IQM config path does not exist: %s", config_file)
        return None

    try:
        data = json.loads(config_file.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read IQM config: %s", exc)
        return None

    iqm_cfg = data.get("iqm_distribution")
    if not iqm_cfg:
        return None

    return iqm_cfg


# ── Controls + plotting ────────────────────────────────────────────────────


def _render_iqm_distributions(iqm_cfg: dict) -> None:
    """Render modality / group selectors and the Plotly box-plot figure."""

    # ── Modality selector ───────────────────────────────────────────────
    available_modalities = [m for m in IQM_DISTRIBUTION_GROUPS if m in iqm_cfg]
    if not available_modalities:
        st.warning(
            ERROR_MESSAGES.get(
                "iqm_no_modalities",
                "No matching modalities between config and IQM_DISTRIBUTION_GROUPS.",
            )
        )
        return

    modality = st.selectbox(
        "Select modality for IQM distributions",
        options=available_modalities,
        key="iqm_modality_select",
    )

    modality_path = iqm_cfg.get(modality, "")
    if not modality_path:
        st.warning(f"No data path configured for modality '{modality}'.")
        return

    # ── Load dataset TSV ────────────────────────────────────────────────
    try:
        df = _read_tsv(modality_path)
    except Exception as exc:
        st.error(
            ERROR_MESSAGES.get(
                "iqm_data_load_error",
                "Failed to read IQM distribution data from {path}: {error}",
            ).format(path=modality_path, error=exc)
        )
        return

    distribution_groups = IQM_DISTRIBUTION_GROUPS[modality]

    # ── Group selector ──────────────────────────────────────────────────
    group_name = st.selectbox(
        "Select metric group",
        options=list(distribution_groups.keys()),
        key="iqm_group_name_select",
    )

    # ── Display mode ────────────────────────────────────────────────────
    mode = st.radio(
        "Display mode",
        ["Dataset only", "Dataset + reference"],
        horizontal=True,
        key="iqm_display_mode",
    )

    cols = distribution_groups[group_name]

    # ── Build figure ────────────────────────────────────────────────────
    if mode == "Dataset only":
        fig = _build_dataset_only_figure(df, cols)
    else:
        ref_df = _load_reference_data(modality)
        fig = _build_comparison_figure(df, ref_df, cols)

    fig.update_layout(
        title=f"{group_name} distributions",
        xaxis_title="Metric",
        yaxis_title="Value",
        template="plotly_white",
        height=PLOT_HEIGHT,
        boxmode="group",
        legend_title="Source",
    )

    st.plotly_chart(fig, use_container_width=True)


# ── Figure builders ─────────────────────────────────────────────────────────


def _build_dataset_only_figure(
    df: pd.DataFrame,
    cols: list[str],
) -> go.Figure:
    """Build a box-plot figure showing only the dataset distribution."""
    fig = go.Figure()
    first_shown = True

    for col in cols:
        if col not in df.columns:
            continue

        values = df[col].dropna()
        fig.add_trace(
            go.Box(
                x=[col] * len(values),
                y=values,
                name="Dataset",
                legendgroup="dataset",
                showlegend=first_shown,
                boxpoints="all",
                jitter=0.45,
                pointpos=0,
                marker=DATASET_STYLE["marker"],
                line=DATASET_STYLE["line"],
                fillcolor=DATASET_STYLE["fillcolor"],
                hovertemplate=(f"Source: Dataset<br>Metric: {col}<br>" "Value: %{y}<extra></extra>"),
            )
        )
        first_shown = False

    return fig


def _build_comparison_figure(
    df: pd.DataFrame,
    ref_df: Optional[pd.DataFrame],
    cols: list[str],
) -> go.Figure:
    """Build a grouped box-plot comparing dataset and reference distributions."""
    fig = go.Figure()
    first_dataset = True
    first_reference = True

    for col in cols:
        # Dataset trace
        if col in df.columns:
            values = df[col].dropna()
            fig.add_trace(
                go.Box(
                    x=[col] * len(values),
                    y=values,
                    name="Dataset",
                    legendgroup="dataset",
                    showlegend=first_dataset,
                    offsetgroup="dataset",
                    boxpoints="all",
                    jitter=0.45,
                    pointpos=-0.3,
                    marker=DATASET_STYLE["marker"],
                    line=DATASET_STYLE["line"],
                    fillcolor=DATASET_STYLE["fillcolor"],
                    hovertemplate=(f"Source: Dataset<br>Metric: {col}<br>" "Value: %{y}<extra></extra>"),
                )
            )
            first_dataset = False

        # Reference trace
        if ref_df is not None and col in ref_df.columns:
            values = ref_df[col].dropna()
            fig.add_trace(
                go.Box(
                    x=[col] * len(values),
                    y=values,
                    name="Reference",
                    legendgroup="reference",
                    showlegend=first_reference,
                    offsetgroup="reference",
                    boxpoints="all",
                    jitter=0.45,
                    pointpos=0.3,
                    marker=REFERENCE_STYLE["marker"],
                    line=REFERENCE_STYLE["line"],
                    fillcolor=REFERENCE_STYLE["fillcolor"],
                    hovertemplate=(f"Source: Reference<br>Metric: {col}<br>" "Value: %{y}<extra></extra>"),
                )
            )
            first_reference = False

    return fig


# ── Cached data loading ─────────────────────────────────────────────────────


@st.cache_data(show_spinner="Loading IQM data…")
def _read_tsv(path: str) -> pd.DataFrame:
    """Read a TSV file and cache the result.

    Streamlit caches the returned DataFrame by the *path* argument.  The
    data is only re-read when the path changes or the cache is manually
    cleared.  This matters because the reference population files (e.g.
    ``group_T1w.tsv`` at ~3 MB) and the dataset-level MRIQC outputs are
    both static for the lifetime of a QC session.
    """
    return pd.read_csv(path, sep="\t")


# ── Reference data loading ──────────────────────────────────────────────────


def _load_reference_data(modality: str) -> Optional[pd.DataFrame]:
    """Load the reference TSV for a given modality.

    Returns the DataFrame or *None* (with a Streamlit warning) on failure.
    The heavy read is delegated to ``_read_tsv`` so that repeated calls
    with the same modality hit Streamlit's data cache.
    """
    ref_path = REFERENCE_DATA_PATHS.get(modality, "")
    if not ref_path:
        st.warning(f"No reference data path configured for modality '{modality}'.")
        return None

    try:
        return _read_tsv(ref_path)
    except Exception as exc:
        st.warning(f"Failed to read reference data from {ref_path}: {exc}")
        return None
