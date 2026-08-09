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
    load_reference_iqm_for_subject,
)
from constants import MESSAGES, ERROR_MESSAGES
from managers.session_manager import SessionManager
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
SUBJECT_MARKER_STYLE = dict(size=8, symbol='diamond', color="rgba(255, 127, 14, 0.9)",
                        line=dict(color="rgba(255, 127, 14, 1.0)", width=2))
MAX_REFERENCE_ROWS = 50000

CONTAINER_HEIGHT = 520
NUM_OVERVIEW_COLUMNS = 2

# Above this many rows in a series, Plotly's boxpoints='all' renders every
# point individually and becomes noticeably slow; fall back to outlier-only
# points instead.
MAX_ALL_BOXPOINTS_ROWS = 500


def _load_iqm_config(qc_config_path: str) -> dict:
    """Load IQM configuration from the QC config file."""
    iqm_config = load_iqm_config(qc_config_path)
    if not iqm_config:
        st.warning(ERROR_MESSAGES['iqm_config_missing'])
    return iqm_config


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


def _build_iqm_distribution_figure(
    metric_group_name: str,
    modality: str,
    iqm_data: pd.DataFrame,
    participant_id: str,
    session_id: str,
    metric_columns: list,
    display_mode: str,
    reference_data: Optional[pd.DataFrame] = None,
    compact: bool = False,
) -> Optional[go.Figure]:
    """Construct the Plotly figure for the IQM distribution panel."""

    #____________Filter data ___________
    if not metric_columns:
        st.error("None of the required columns for this group are present in the data.")
        return None

    #___________load data for plotting___________
    iqm_data_for_group = _coerce_numeric_columns(iqm_data, metric_columns)
    participant_columns = _extract_subject_data(
        iqm_data_for_group,
        participant_id,
        metric_columns,
        session_id=session_id,
    )
    dataset_plot_data = iqm_data_for_group[metric_columns]

    reference_plot_data = None
    group_display_mode = display_mode
    if display_mode == "Dataset + reference" and reference_data is not None:
        reference_plot_data = _coerce_numeric_columns(reference_data, metric_columns)
        reference_plot_data = reference_plot_data[metric_columns]
        if reference_plot_data.dropna(how='all').empty:
            st.warning("Reference data is empty after filtering; showing dataset-only distribution.")
            group_display_mode = "Dataset"

    #____________Render distribution plot___________
    fig = go.Figure()
    if compact:
        boxpoints = False
    else:
        largest_series_rows = max(
            len(dataset_plot_data),
            len(reference_plot_data) if reference_plot_data is not None else 0,
        )
        boxpoints = 'all' if largest_series_rows <= MAX_ALL_BOXPOINTS_ROWS else 'outliers'

    if group_display_mode == "Dataset":
        _add_box_traces(
            fig,
            dataset_plot_data,
            DATASET_STYLE,
            offsetgroup="Dataset",
            boxpoints=boxpoints,
        )
        _add_subject_overlay(fig, participant_columns, participant_id, offsetgroup="Dataset", label_suffix=" (dataset)")

    elif group_display_mode == "Dataset + reference":
        _add_box_traces(
            fig,
            dataset_plot_data,
            offsetgroup="Dataset",
            style=DATASET_STYLE,
            pointpos=-0.3,
            boxpoints=boxpoints,
        )
        _add_subject_overlay(fig, participant_columns, participant_id, offsetgroup="Dataset", label_suffix=" (dataset)")
        # Keep sampling for performance, but show reference points for parity with dataset view.
        _add_box_traces(
            fig,
            reference_plot_data,
            offsetgroup="Reference",
            style=REFERENCE_STYLE,
            pointpos=0.3,
            boxpoints=boxpoints,
        )
    
    fig.update_layout(
        title=f"IQM Distributions for {metric_group_name} ({modality})",
        xaxis_title="Metrics",
        yaxis_title="Values",
        boxmode='group',
        legend_title="Legend",
        template="plotly_white"
    )

    if compact:
        fig.update_layout(
            title=metric_group_name,
            height=220,
            showlegend=False,
            xaxis_title=None,
            yaxis_title=None,
            margin=dict(l=20, r=20, t=45, b=25),
        )

    if not fig.data:
        st.warning("No plottable numeric data found for the selected group.")
        return None
    
    return fig


def _render_montage_of_iqm_groups(
    valid_groups,
    iqm_data,
    reference_data,
    participant_id,
    session_id,
    modality,
    display_mode,
):
    """Render compact plots for all available IQM groups."""
    overview_columns = st.columns(NUM_OVERVIEW_COLUMNS)

    for index, (group_name, metric_columns) in enumerate(valid_groups.items()):
        fig = _build_iqm_distribution_figure(
            metric_group_name=group_name,
            modality=modality,
            iqm_data=iqm_data,
            participant_id=participant_id,
            session_id=session_id,
            metric_columns=metric_columns,
            display_mode=display_mode,
            reference_data=reference_data,
            compact=True,
        )

        if fig is not None:
            column = overview_columns[index % NUM_OVERVIEW_COLUMNS]
            with column:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"iqm_overview_{modality}_{group_name}",
                )


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

    #____________Display mode selection___________
    # Same st.switch_page-vs-widget-state issue as "iqm_view_mode" below: the
    # sidebar's subject switcher aborts the script before this widget runs,
    # so "iqm_display_mode" gets wiped and silently reverts to "Dataset" on
    # every subject switch (making the reference box disappear). Mirror the
    # selection via SessionManager so it survives.
    display_mode_options = ["Dataset", "Dataset + reference"]

    def _remember_iqm_display_mode():
        SessionManager.set_iqm_display_mode_selection(st.session_state["iqm_display_mode"])

    mode = st.radio(
        "Display mode",
        options=display_mode_options,
        index=display_mode_options.index(SessionManager.get_iqm_display_mode_selection()),
        key="iqm_display_mode",
        on_change=_remember_iqm_display_mode,
        horizontal=True
    )
  
   #____________Load TSV file ____________
    try:
        resolved_modality_path = resolve_iqm_data_path(modality_path, qc_config_path, dataset_dir)
        iqm_data = pd.read_csv(resolved_modality_path, sep='\t')
    except Exception as e:
        st.error(ERROR_MESSAGES['iqm_data_load_error'].format(modality=modality, error=e))
        return
    
    reference_data = None
    try:
        if mode == "Dataset + reference":
            manufacturer = scanner_metadata.get("Manufacturer", "Unknown") if isinstance(scanner_metadata, dict) else scanner_metadata
            field_strength = scanner_metadata.get("MagneticFieldStrength") if isinstance(scanner_metadata, dict) else None
            reference_data = load_reference_iqm_for_subject(
                modality=modality,
                manufacturer=manufacturer,
                field_strength=field_strength,
                max_rows=MAX_REFERENCE_ROWS,
            )
    except Exception as e:
        st.error(ERROR_MESSAGES['reference_data_load_error'].format(modality=modality, error=e))
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

    #____________Select Tab____________
    # st.segmented_control (unlike st.tabs) is a real widget backed by
    # session state, so only the selected branch below actually executes.
    # st.tabs renders both branches on every rerun regardless of which tab
    # is visually active, which was rebuilding the expensive Detail plot
    # (up to MAX_REFERENCE_ROWS points) even while viewing Overview.
    #
    # The sidebar's subject/session switcher calls st.rerun()/st.switch_page()
    # mid-script, which aborts the run before this widget is ever created.
    # Streamlit garbage-collects widget state for keys not touched during a
    # run, so "iqm_view_mode" itself gets wiped on every subject switch and
    # silently reverts to "Overview". Mirror the selection via SessionManager
    # (a plain session_state entry not tied to this widget's lifecycle), and
    # re-seed the widget's default from it every run so the selection
    # survives switches.
    def _remember_iqm_view_selection():
        SessionManager.set_iqm_view_selection(st.session_state["iqm_view_mode"])

    view = st.segmented_control(
        "IQM view",
        options=["Overview", "Detail"],
        default=SessionManager.get_iqm_view_selection(),
        key="iqm_view_mode",
        on_change=_remember_iqm_view_selection,
        label_visibility="collapsed",
    )
    if view is None:
        # Clicking the active pill again deselects it; fall back rather
        # than rendering nothing.
        view = "Overview"

    if view == "Overview":
        st.write("Overview of IQM distributions across the dataset, with current subject highlighted.")
        with st.container(height=CONTAINER_HEIGHT, border=False):
            _render_montage_of_iqm_groups(
                valid_groups=valid_groups,
                iqm_data=iqm_data,
                reference_data=reference_data,
                participant_id=participant_id,
                session_id=session_id,
                modality=modality,
                display_mode=mode,
            )
    elif view == "Detail":
        st.write("Detailed view of a single IQM group with full-size plot and subject overlay.")
        group_options = list(valid_groups.keys())
        remembered_group = SessionManager.get_iqm_group_select_selection()
        if remembered_group not in group_options:
            remembered_group = group_options[0]
        SessionManager.set_iqm_group_select_selection(remembered_group)

        def _remember_iqm_group_select():
            SessionManager.set_iqm_group_select_selection(st.session_state["iqm_group_select"])

        group = st.selectbox(
            "Select metric group",
            options=group_options,
            index=group_options.index(remembered_group),
            key="iqm_group_select",
            on_change=_remember_iqm_group_select,
        )

        fig = _build_iqm_distribution_figure(
            metric_group_name=group,
            modality=modality,
            iqm_data=iqm_data,
            participant_id=participant_id,
            session_id=session_id,
            metric_columns=valid_groups[group],
            display_mode=mode,
            reference_data=reference_data,
        )

        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)


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
