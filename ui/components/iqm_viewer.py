"""IQM distribution viewer component for QC-Studio UI.
 
Displays grouped Image Quality Metric (IQM) distributions as interactive
Plotly box plots with the current subject highlighted. Supports
dataset-only and dataset-vs-reference comparison modes, with modality
(T1w / BOLD) and metric group selection.
 
Data sources
------------
- **Dataset group TSV** - path specified in the QC config JSON under the
  ``iqm_distribution`` key (e.g. ``derivatives/mriqc/group_T1w.tsv``).
- **Reference population TSV** - path defined in
  ``iqm_distribution_config.REFERENCE_DATA_PATHS``.
- **Current subject** - identified by ``participant_id`` (e.g.
  ``sub-ED01``) matched against the ``bids_name`` column in the dataset
  TSV.  A subject may have multiple rows (multiple runs).
"""

from pathlib import Path
from typing import Optional, Union
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from utils.data_loaders import (
    _load_scanner_metadata,
    load_iqm_config,
    resolve_iqm_data_path,
    resolve_reference_data_path,
    load_reference_iqm_data,
)
from constants import MESSAGES, ERROR_MESSAGES
from utils.iqm_distribution_config import IQM_DISTRIBUTION_GROUPS, REFERENCE_DATA_PATHS

MODALITY_KEYWORDS = {
    "bold": ("bold", "func", "sbref"),
    "t1w": ("anat", "t1w"),
}

DATASET_STYLE = dict(marker=dict(size=4, symbol='circle', color="rgba(31, 119, 180, 0.55)"),
                line=dict(color="rgba(31, 119, 180, 0.8)", width=1),
                fillcolor="rgba(31, 119, 180, 0.25)")
REFERENCE_STYLE = dict(marker=dict(size=4, symbol='circle', color="rgba(214, 39, 40, 0.55)"),
                line=dict(color="rgba(214, 39, 40, 1.0)", width=1),
                fillcolor="rgba(214, 39, 40, 0.25)")
SUBJECT_MARKER_STYLE = dict(size=12, symbol='diamond', color="rgba(255, 127, 14, 0.9)",
                        line=dict(color="rgba(255, 127, 14, 1.0)", width=2))
MAX_REFERENCE_ROWS = 50000


def _load_iqm_config(qc_config_path: str) -> dict:
    """Load IQM configuration from the QC config file."""
    iqm_config = load_iqm_config(qc_config_path)
    if not iqm_config:
        st.warning(ERROR_MESSAGES['iqm_config_missing'])
    return iqm_config


@st.cache_data(show_spinner="Loading reference data…")
def _load_reference_data(modality: str, scanner_meta: Optional[Union[dict, str]] = None) -> "pd.DataFrame":
    """Cached thin wrapper: resolves path + manufacturer, then delegates to load_reference_iqm_data."""
    ref_path = REFERENCE_DATA_PATHS.get(modality)
    if ref_path is None:
        raise ValueError(f"No reference data path defined for modality '{modality}'")

    if isinstance(scanner_meta, dict):
        manufacturer = scanner_meta.get("Manufacturer", "Unknown")
    elif isinstance(scanner_meta, str):
        manufacturer = scanner_meta or "Unknown"
    else:
        manufacturer = "Unknown"

    repo_root = Path(__file__).resolve().parents[2]
    resolved_ref_path = resolve_reference_data_path(ref_path, base_dir=repo_root)
    return load_reference_iqm_data(resolved_ref_path, manufacturer)

def _extract_subject_data(data: pd.DataFrame, participant_id: str, columns: list, session_id: str=None)-> pd.DataFrame:
    """Extract subject-specific data for the given participant ID and columns."""
    if "bids_name" not in data.columns:
        raise ValueError("Expected 'bids_name' column not found in data.")

    participant_mask = data["bids_name"].str.startswith(participant_id)
    mask = participant_mask
    if  session_id:
        if not session_id.startswith("ses-"):
            raise ValueError("session_id should start with 'ses-'.")

        session_mask = participant_mask & data["bids_name"].str.contains(session_id)
        # Some MRIQC files encode runs without session tags; in that case,
        # fall back to participant-only rows so subject markers remain visible.
        if session_mask.any():
            mask = session_mask

    data_subject = data.loc[mask, columns]
    return data_subject


def _coerce_numeric_columns(data: pd.DataFrame, columns: list) -> pd.DataFrame:
    """Convert target columns to numeric, coercing invalid values to NaN."""
    converted = data.copy()
    for col in columns:
        if col in converted.columns:
            converted[col] = pd.to_numeric(converted[col], errors='coerce')
    return converted


def _add_box_traces(
    fig:go.Figure,
    data:pd.DataFrame,
    style: dict,
    offsetgroup: str = "",
    pointpos: float = 0,
    boxpoints: Union[str, bool] = 'all'
    )-> None:
    """Add one box trace per metric column to the figure."""
    first_shown = True
    cols = data.columns
    for col in cols:
        values = data[col].dropna()
        if values.empty:
            continue
        fig.add_trace(go.Box(
            x = [col] * len(values),
            y = values,
            name=offsetgroup,
            pointpos=pointpos,
            offsetgroup=offsetgroup.lower(),
            showlegend=first_shown,
            boxpoints=boxpoints,
            jitter=0.45,
            marker=style['marker'],
            line=style['line'],
            fillcolor=style['fillcolor'],
            hovertemplate=(
                f"Source: {offsetgroup}<br>Metric: {col}<br>Value: %{{y}}<extra></extra>"
            )
             
        ))
        first_shown = False


def _add_subject_overlay(
        fig: go.Figure,
        subject_rows: pd.Series,
        participant_id: str,
        style: dict = SUBJECT_MARKER_STYLE,
        offsetgroup: str = "",
        label_suffix: str = "", 
        show_legend: bool =True)-> None:
    
    """Overlay subject data on the plot.
    When a subject has multiple runs, each run is shown as a separate
    star at the same x position so the rater can see run-to-run
    variability.
 
    In comparison mode, call this twice with different ``offsetgroup``
    values (``"dataset"`` and ``"reference"``) so the stars align on
    top of the correct box plot group.
    """

    for _, rows in subject_rows.iterrows():
        participant_values = rows.dropna()
        if participant_values.empty:
            continue
        for col, value in participant_values.items():
            fig.add_trace(go.Scatter(
                x=[col],
                y=[value],
                mode='markers',
                name=f"{participant_id}{label_suffix}",
                marker=style,
                showlegend=show_legend,
                offsetgroup=offsetgroup.lower(),
                hovertemplate=(
                    f"Source: {participant_id}{label_suffix}<br>Metric: {col}<br>Value: %{{y}}<extra></extra>"
                )
            ))
            show_legend = False     
 

def _get_valid_iqm_groups(distribution_groups: dict, iqm_data: pd.DataFrame) -> dict:
    """Return IQM groups with at least one column present in the data."""
    valid_groups = {}
    for group_name, columns in distribution_groups.items():
        valid_columns = [col for col in columns if col in iqm_data.columns]

        if valid_columns:
            valid_groups[group_name] = valid_columns
    return valid_groups


# def _render_iqm_detail_tab():
#     """Render the Detail tab: select one IQM group and show its full-size plot."""

def _render_iqm_distributions(iqm_config, scanner_metadata, participant_id, session_id,
                              qc_config_path: str = None, dataset_dir: str = None,
                              qc_task: str = None, qc_config: dict = None):
    #___________Modality selection___________
    available_modalities = [
        m for m in IQM_DISTRIBUTION_GROUPS if m in iqm_config
    ]
    if not available_modalities:
        st.warning(ERROR_MESSAGES.get(
            "iqm_no_modalities",
            "No matching modalities between config and IQM_DISTRIBUTION_GROUPS.",
        ))
        return
    
    st.subheader(MESSAGES['iqm_distribution_header'])
    modality = _infer_iqm_modality(qc_task, qc_config, iqm_config)
    if modality is None:
        st.warning(
            f"Could not infer IQM modality from QC task '{qc_task}'. "
            "Please make the task name or configured paths indicate anat/t1w or bold/func."
        )
        return

    if hasattr(st, "caption"):
        st.caption(f"IQM modality: {modality}")
    else:
        st.info(f"IQM modality: {modality}")
    modality_path = iqm_config.get(modality)

    if modality_path is None:
        st.error(ERROR_MESSAGES['iqm_modality_path_error'].format(modality=modality))
        return 
      
   #____________Load TSV file ____________
    try:
        resolved_modality_path = resolve_iqm_data_path(modality_path, qc_config_path, dataset_dir)
        iqm_data = pd.read_csv(resolved_modality_path, sep='\t')
    except Exception as e:
        st.error(ERROR_MESSAGES['iqm_data_load_error'].format(modality=modality, error=e))
        return
    
    #____________Group selection___________
    distribution_groups = IQM_DISTRIBUTION_GROUPS.get(modality, [])
    if not distribution_groups:
        st.warning(ERROR_MESSAGES.get(
            "iqm_no_groups",
            f"No distribution groups defined for modality '{modality}'.",
        ))
        return
    valid_groups = _get_valid_iqm_groups(distribution_groups, iqm_data)
    if not valid_groups:
        st.warning(ERROR_MESSAGES.get(
            "iqm_no_valid_groups",
            "None of the defined IQM groups have valid columns in the data.",
        ))
        return

    #____________Display mode selection___________
    mode = st.radio(
        "Display mode",
        options=["Dataset", "Dataset + reference"],
        key="iqm_display_mode",
        horizontal=True
    )

    #____________Select Tab____________
    overview_tab, detail_tab = st.tabs(["Overview", "Detail"])
    with overview_tab:
        st.write("Overview of IQM distributions across the dataset, with current subject highlighted.")
    with detail_tab:
        st.write("Detailed view of a single IQM group with full-size plot and subject overlay.")
        group = st.selectbox("Select metric group", options=list(valid_groups.keys()),key="iqm_group_select")

        #____________Filter data ___________

        valid_columns = valid_groups.get(group, [])
        if not valid_columns:
            st.error("None of the required columns for this group are present in the data.")
            return

    # columns = distribution_groups[group]
    # missing_columns = [col for col in columns if col not in iqm_data.columns]
    # st.warning("Missing columns: {}".format(", ".join(missing_columns))) if missing_columns else None
    # valid_columns = [col for col in columns if col in iqm_data.columns]
    # if not valid_columns:
    #     st.error("None of the required columns for this group are present in the data.")
    #     return
    

        #___________load data for plotting___________
        iqm_data_for_group = _coerce_numeric_columns(iqm_data, valid_columns)
        participant_columns = _extract_subject_data(iqm_data_for_group, participant_id, valid_columns, session_id=session_id)
        iqm_data_plot = iqm_data_for_group[valid_columns]
        if mode == "Dataset + reference":
            reference_data = _load_reference_data(modality, scanner_metadata)
            if len(reference_data) > MAX_REFERENCE_ROWS:
                reference_data = reference_data.sample(n=MAX_REFERENCE_ROWS, random_state=42)
            reference_data = _coerce_numeric_columns(reference_data, valid_columns)
            reference_data = reference_data[valid_columns]
            if reference_data.dropna(how='all').empty:
                st.warning("Reference data is empty after filtering; showing dataset-only distribution.")
                mode = "Dataset"

        #____________Render distribution plot___________
        fig = go.Figure()

        if mode == "Dataset":
            _add_box_traces(fig, iqm_data_plot, DATASET_STYLE, offsetgroup="Dataset")
            _add_subject_overlay(fig, participant_columns, participant_id, offsetgroup="Dataset", label_suffix=" (dataset)")

        elif mode == "Dataset + reference":
            _add_box_traces(fig, iqm_data_plot, offsetgroup="Dataset", style=DATASET_STYLE, pointpos=-0.3)
            _add_subject_overlay(fig, participant_columns, participant_id, offsetgroup="Dataset", label_suffix=" (dataset)")
            # Keep sampling for performance, but show reference points for parity with dataset view.
            _add_box_traces(fig, reference_data, offsetgroup="Reference", style=REFERENCE_STYLE, pointpos=0.3, boxpoints='all')
        
        fig.update_layout(
            title=f"IQM Distributions for {group} ({modality})",
            xaxis_title="Metrics",
            yaxis_title="Values",
            boxmode='group',
            legend_title="Legend",
            template="plotly_white"
        )

        if not fig.data:
            st.warning("No plottable numeric data found for the selected group.")
            return

        st.plotly_chart(fig, use_container_width=True)


def _display_iqm_panel(qc_config: dict, qc_config_path: str, participant_id: str, session_id: str,
                       dataset_dir: str = None, qc_task: str = None) -> None:
    """Display the IQM distribution panel.
    
    Args:
        qc_config: QC configuration object
        qc_config_path: Path to the QC configuration file
        participant_id: ID of the participant whose data to display
        qc_task: The QC task for which to display IQM distributions
    """


    iqm_config = _load_iqm_config(qc_config_path)
    if not iqm_config:
        st.error(ERROR_MESSAGES['iqm_config_load_error'])
        return

    scanner_metadata = _load_scanner_metadata(
        qc_config.get("base_mri_image_path"),
        participant_id=participant_id,
        session_id=session_id,
    )

    _render_iqm_distributions(
        iqm_config,
        scanner_metadata,
        participant_id,
        session_id,
        qc_config_path=qc_config_path,
        dataset_dir=dataset_dir,
        qc_task=qc_task,
        qc_config=qc_config,
    )


def _infer_iqm_modality(qc_task: str, qc_config: dict, iqm_config: dict) -> Optional[str]:
    """Infer IQM modality from the selected QC task/config."""
    task_name = str(qc_task or "").lower()

    # First try to infer modality from the QC task name itself, as this is most likely to reflect the rater's intent.
    for modality, keywords in MODALITY_KEYWORDS.items():
        if modality in iqm_config and any(keyword in task_name for keyword in keywords):
            return modality
    
    # If that fails, look for modality keywords in the paths of the selected QC task config, as a secondary signal.
    path_values = []
    for value in (qc_config or {}).values():
        if isinstance(value, list):
            path_values.extend(str(item) for item in value if item)
        elif value:
            path_values.append(str(value))
    path_text = " ".join(path_values).lower()
    for modality, keywords in MODALITY_KEYWORDS.items():
        if modality in iqm_config and any(keyword in path_text for keyword in keywords):
            return modality
    # If that also fails, but there's only one modality available in the config, return that one as a last resort since it's the only option.
    available_modalities = [m for m in IQM_DISTRIBUTION_GROUPS if m in iqm_config]
    if len(available_modalities) == 1:
        return available_modalities[0]
    return None
