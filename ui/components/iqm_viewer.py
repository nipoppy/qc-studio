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

import re
import pandas as pd
import streamlit as st

from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Union

import plotly.graph_objects as go

from utils.data_loaders import (
    _load_scanner_metadata,
    resolve_iqm_data_path,
    _load_iqm_distribution_table,
    _load_iqm_metrics_subject_level,
    load_reference_iqm_for_subject,
)
from constants import MESSAGES, ERROR_MESSAGES
from managers.session_manager import SessionManager
from utils.iqm_distribution_config import (
    IQM_DISTRIBUTION_GROUPS,
    infer_pipeline_from_iqm_path,
    is_mriqc_pipeline,
)

DATASET_STYLE = dict(
    marker=dict(size=4, symbol="circle", color="rgba(31, 119, 180, 0.55)"),
    line=dict(color="rgba(31, 119, 180, 0.8)", width=1),
    fillcolor="rgba(31, 119, 180, 0.25)",
)
REFERENCE_STYLE = dict(
    marker=dict(size=4, symbol="circle", color="rgba(214, 39, 40, 0.55)"),
    line=dict(color="rgba(214, 39, 40, 1.0)", width=1),
    fillcolor="rgba(214, 39, 40, 0.25)",
)
SUBJECT_MARKER_STYLE = dict(size=8, symbol="diamond", color="rgba(255, 127, 14, 0.9)", line=dict(color="rgba(255, 127, 14, 1.0)", width=2))
MAX_REFERENCE_ROWS = 50000

CONTAINER_HEIGHT = 520
NUM_OVERVIEW_COLUMNS = 2

NON_METRIC_COLUMNS = {"bids_name", "subject", "subject_id", "participant_id"}

DISPLAY_MODE_OPTIONS = ["Dataset", "Dataset + Reference"]


@dataclass(frozen=True)
class DistributionSource:
    path: "Path"
    pipeline_name: str
    modality: "Optional[str]"
    iqm_data: "pd.DataFrame"
    valid_groups: dict


@dataclass(frozen=True)
class MetricsSource:
    path: "Path"
    pipeline_name: str
    metrics: dict


def _infer_modality_from_path(path: str) -> Optional[str]:
    """Infer the modality (t1w, bold, dwi) from the IQM path string."""
    if not path:
        return None

    path_str = str(path).lower()
    name = Path(path).name.lower()

    if "/func/" in path_str or re.search(r"_(bold|sbref)\.", path_str) or "bold" in name:
        return "bold"
    if "/dwi/" in path_str or re.search(r"_dwi\.", path_str) or "dwi" in name:
        return "dwi"
    if "/anat/" in path_str or "t1w" in name:
        return "t1w"

    return None


def _path_after_pipeline(path) -> str:
    """Path segments after derivatives/<pipeline>/, extension stripped -
    e.g. "23.1.0/group_T1w" for derivatives/mriqc/23.1.0/group_T1w.tsv.
    Distinguishes sibling sources that share both pipeline_name and
    modality but differ by a pipeline-version subdirectory. Falls back to
    the filename stem if there's no derivatives segment to anchor on."""
    parts = Path(path).parts
    if "derivatives" in parts:
        idx = parts.index("derivatives")
        remainder = parts[idx + 2 :]
        if remainder:
            return str(Path(*remainder).with_suffix(""))
    return Path(path).stem


def _disambiguate_tab_labels(sources) -> list:
    """Build a unique display label per source, in source order.

    pipeline_name alone isn't unique (MRIQC contributes both a T1w and a
    bold table). Escalates through increasingly specific disambiguators -
    modality, then the path segments after derivatives/<pipeline>/ (so two
    MRIQC pipeline-version folders emitting the same filename, e.g.
    derivatives/mriqc/23.1.0/group_T1w.tsv vs .../24.0.0/group_T1w.tsv,
    still get distinct labels even though pipeline_name AND modality
    match) - and numbers anything still colliding as a last resort.
    segmented_control breaks silently on duplicate option values (only the
    first is selectable), so uniqueness here is a hard requirement, not
    just cosmetic.
    """
    labels = [s.pipeline_name for s in sources]

    for discriminator in (
        lambda s: getattr(s, "modality", None),
        lambda s: _path_after_pipeline(s.path),
    ):
        counts = {}
        for label in labels:
            counts[label] = counts.get(label, 0) + 1
        if not any(count > 1 for count in counts.values()):
            break
        labels = [f"{s.pipeline_name} ({discriminator(s)})" if counts[label] > 1 and discriminator(s) else label for s, label in zip(sources, labels)]

    counts = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    if any(count > 1 for count in counts.values()):
        seen = {}
        numbered = []
        for label in labels:
            if counts[label] > 1:
                seen[label] = seen.get(label, 0) + 1
                numbered.append(f"{label} #{seen[label]}")
            else:
                numbered.append(label)
        labels = numbered

    return labels


def _generic_groups_from_columns(iqm_data) -> dict:
    # need to expand this based on the pipeline and modality, but for now just return all numeric columns as a single group
    """Return a generic IQM group for any modality with all numeric columns."""
    metric_columns = [col for col in iqm_data.columns if (pd.api.types.is_numeric_dtype(iqm_data[col]) and col.lower() not in NON_METRIC_COLUMNS)]

    return {col: [col] for col in metric_columns}


def _row_to_metrics(row) -> dict:
    """Flatten a single-row Series into a metrics dict, dropping non-metric/index columns."""
    return {col: value for col, value in row.items() if str(col).lower() not in NON_METRIC_COLUMNS and not str(col).startswith("Unnamed:")}


def _load_distribution_source(path, resolved, pipeline_name):
    """Load a TSV/CSV distribution source and return a DistributionSource or MetricsSource object."""
    try:
        iqm_data = _load_iqm_distribution_table(resolved)
    except Exception as e:
        st.error(ERROR_MESSAGES["iqm_data_load_error"].format(modality=pipeline_name, error=e))
        return None

    if len(iqm_data) == 0:
        st.warning(
            ERROR_MESSAGES.get(
                "iqm_no_valid_groups",
                f"No rows found in {pipeline_name} ({path}).",
            )
        )
        return None

    if len(iqm_data) == 1:
        return MetricsSource(
            path=resolved,
            pipeline_name=pipeline_name,
            metrics=_row_to_metrics(iqm_data.iloc[0]),
        )

    modality = None
    distribution_groups = {}

    if is_mriqc_pipeline(pipeline_name):
        modality = _infer_modality_from_path(path)
        if modality is not None:
            distribution_groups = IQM_DISTRIBUTION_GROUPS.get(modality, {})
            if callable(distribution_groups):
                distribution_groups = distribution_groups(iqm_data.columns)

    if distribution_groups:
        valid_groups = _get_valid_iqm_groups(distribution_groups, iqm_data)

    else:
        valid_groups = _generic_groups_from_columns(iqm_data)  # already guaranteed valid.

    if not valid_groups:
        st.warning(
            ERROR_MESSAGES.get(
                "iqm_no_valid_groups",
                f"No usable metric columns found in {pipeline_name} ({path}).",
            )
        )
        return None

    return DistributionSource(
        path=resolved,
        pipeline_name=pipeline_name,
        modality=modality,
        iqm_data=iqm_data,
        valid_groups=valid_groups,
    )


def _load_metrics_source(path, resolved, pipeline_name):
    """JSON branch: a single per-subject metrics dict, rendered as one tab of a plain table."""
    try:
        metrics = _load_iqm_metrics_subject_level(resolved)
    except Exception as e:
        st.error(ERROR_MESSAGES["iqm_data_load_error"].format(modality=pipeline_name, error=e))
        return None

    return MetricsSource(
        path=resolved,
        pipeline_name=pipeline_name,
        metrics=metrics,
    )


def _load_iqm_sources(iqm_paths, qc_config_path=None, dataset_dir=None) -> list:
    """Resolve and load every configured IQM source. Skips (with a UI warning)
    any path that fails to load, so one bad source doesn't take down the
    other tabs."""
    sources = []
    for path in iqm_paths:
        resolved = resolve_iqm_data_path(path, qc_config_path, dataset_dir)
        pipeline_name = infer_pipeline_from_iqm_path(path)
        suffix = Path(path).suffix.lower()

        if suffix == ".json":
            source = _load_metrics_source(path, resolved, pipeline_name)
        else:
            source = _load_distribution_source(path, resolved, pipeline_name)

        if source is not None:
            sources.append(source)
    return sources


# for now I have decided to return a table if the user put participant level json metrics, and a distribution plot if the user put group level tsv metrics.
# this behaviour might change in the future, but for now it is a simple way to handle both types of metrics.
def _render_iqm_metrics_table(metrics: dict, participant_id: str) -> None:
    """Render a single JSON/single-row metrics source as a plain key/value table."""
    scalar_metrics = {k: v for k, v in metrics.items() if not isinstance(v, (dict, list))}
    if not scalar_metrics:
        st.warning("No metrics found in this IQM source.")
        return
    st.write(f"QC metrics for {participant_id}.")
    st.table(pd.DataFrame(sorted(scalar_metrics.items()), columns=["Metric", "Value"]))


def _extract_run_identifier(base_mri_image_path, participant_id: str, session_id: str = None) -> Optional[str]:
    """Pull whatever BIDS entities identify a specific run/task out of the
    current QC task's base_mri_image_path filename, once participant_id and
    session_id are stripped out - e.g. "task-rest_run-1_bold" from
    ..._task-rest_run-1_bold.nii.gz. Used to scope the subject-overlay
    markers to the exact acquisition being reviewed elsewhere on the page,
    instead of every run this subject/session has in the group table."""
    if not base_mri_image_path:
        return None

    name = Path(base_mri_image_path).name
    for suffix in (".nii.gz", ".nii", ".json"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break

    if participant_id:
        name = name.replace(participant_id, "")
    if session_id:
        name = name.replace(session_id, "")

    name = re.sub(r"_+", "_", name).strip("_")
    return name or None


def _extract_subject_data(data: pd.DataFrame, participant_id: str, columns: list, session_id: str = None, run_identifier: str = None) -> pd.DataFrame:
    """Extract subject-specific data for the given participant ID and columns."""
    if "bids_name" not in data.columns:
        raise ValueError("Expected 'bids_name' column not found in data.")

    participant_mask = data["bids_name"].str.startswith(participant_id)
    mask = participant_mask
    if session_id:
        if not session_id.startswith("ses-"):
            raise ValueError("session_id should start with 'ses-'.")

        session_mask = participant_mask & data["bids_name"].str.contains(session_id)

        # Some MRIQC files encode runs without session tags; in that case,fall back to participant-only rows so subject markers remain visible.
        if session_mask.any():
            mask = session_mask

    if run_identifier:
        # Narrow further to the specific run/task being reviewed, but only if that actually matches something
        run_mask = mask & data["bids_name"].str.contains(run_identifier, regex=False)
        if run_mask.any():
            mask = run_mask

    select_columns = columns if "bids_name" in columns else ["bids_name"] + list(columns)
    data_subject = data.loc[mask, select_columns]
    return data_subject


def _coerce_numeric_columns(data: pd.DataFrame, columns: list) -> pd.DataFrame:
    """Convert target columns to numeric, coercing invalid values to NaN."""
    converted = data.copy()
    for col in columns:
        if col in converted.columns:
            converted[col] = pd.to_numeric(converted[col], errors="coerce")
    return converted


def _add_violin_traces(
    fig: go.Figure,
    data: pd.DataFrame,
    style: dict,
    name: str = "",
    side: str = "both",
    points: Union[bool, str] = False,
) -> None:
    """Add one violin trace per metric column to the figure.

    side="both" draws a full violin (dataset-only mode). side="negative"/
    "positive" draws just the left/right half - call twice with the same
    metric columns (once per side) and violinmode="overlay" to get a split
    violin comparing dataset (left) against reference (right).
    """
    first_shown = True
    cols = data.columns

    for col in cols:
        values = data[col].dropna()
        if values.empty:
            continue
        fig.add_trace(
            go.Violin(
                x=[col] * len(values),
                y=values,
                side=side,
                name=name,
                scalegroup=col,
                legendgroup=name,
                spanmode="hard",
                showlegend=first_shown,
                points=points,
                jitter=0.45,
                marker=style["marker"],
                line=style["line"],
                fillcolor=style["fillcolor"],
                hovertemplate=(f"Source: {name}<br>Metric: {col}<br>Value: %{{y}}<extra></extra>"),
            )
        )
        first_shown = False


def _add_subject_overlay(
    fig: go.Figure,
    subject_rows: pd.Series,
    participant_id: str,
    style: dict = SUBJECT_MARKER_STYLE,
    offsetgroup: str = "",
    label_suffix: str = "",
    show_legend: bool = True,
) -> None:
    """Overlay subject data on the plot.
    When a subject has multiple runs, each run is shown as a separate
    star at the same x position so the rater can see run-to-run
    variability.

    In comparison mode, call this twice with different ``offsetgroup``
    values (``"dataset"`` and ``"reference"``) so the stars align on
    top of the correct violin half.
    """

    for _, row in subject_rows.iterrows():
        run_label = row.get("bids_name") or f"{participant_id}{label_suffix}"
        participant_values = row.drop(labels=["bids_name"], errors="ignore").dropna()
        if participant_values.empty:
            continue
        for col, value in participant_values.items():
            fig.add_trace(
                go.Scatter(
                    x=[col],
                    y=[value],
                    mode="markers",
                    name=f"{participant_id}{label_suffix}",
                    marker=style,
                    showlegend=show_legend,
                    offsetgroup=offsetgroup.lower(),
                    hovertemplate=(f"Run: {run_label}<br>Value: %{{y}}<extra></extra>"),
                )
            )
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
    run_identifier: Optional[str] = None,
) -> Optional[go.Figure]:
    """Construct the Plotly figure for the IQM distribution panel."""

    # ____________Filter data ___________
    if not metric_columns:
        st.error("None of the required columns for this group are present in the data.")
        return None

    # ___________load data for plotting___________
    iqm_data_for_group = _coerce_numeric_columns(iqm_data, metric_columns)
    participant_columns = _extract_subject_data(
        iqm_data_for_group,
        participant_id,
        metric_columns,
        session_id=session_id,
        run_identifier=run_identifier,
    )
    dataset_plot_data = iqm_data_for_group[metric_columns]

    reference_plot_data = None
    group_display_mode = display_mode
    if display_mode == DISPLAY_MODE_OPTIONS[1]:
        if reference_data is not None:
            reference_plot_data = _coerce_numeric_columns(reference_data, metric_columns)
            reference_plot_data = reference_plot_data[metric_columns]
        if reference_plot_data is None or reference_plot_data.dropna(how="all").empty:
            group_display_mode = DISPLAY_MODE_OPTIONS[0]

    # ____________Render distribution plot___________
    fig = go.Figure()

    if group_display_mode == DISPLAY_MODE_OPTIONS[0]:
        _add_violin_traces(
            fig,
            dataset_plot_data,
            DATASET_STYLE,
            name=DISPLAY_MODE_OPTIONS[0],
            side="both",
            points=False,
        )
        _add_subject_overlay(fig, participant_columns, participant_id, offsetgroup="Dataset", label_suffix=" (dataset)")

    elif group_display_mode == DISPLAY_MODE_OPTIONS[1]:
        _add_violin_traces(
            fig,
            dataset_plot_data,
            DATASET_STYLE,
            name="Dataset",
            side="negative",
            points=False,
        )
        _add_subject_overlay(fig, participant_columns, participant_id, offsetgroup="Dataset", label_suffix=" (dataset)")
        # Keep sampling for performance, but show reference points for parity with dataset view.
        _add_violin_traces(
            fig,
            reference_plot_data,
            REFERENCE_STYLE,
            name="Reference",
            side="positive",
            points=False,
        )

    fig.update_layout(
        title=metric_group_name,
        height=220,
        showlegend=False,
        xaxis_title=None,
        yaxis_title=None,
        violinmode="overlay",
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
    run_identifier=None,
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
            run_identifier=run_identifier,
        )

        if fig is not None:
            column = overview_columns[index % NUM_OVERVIEW_COLUMNS]
            with column:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"iqm_overview_{modality}_{group_name}",
                )


def _render_iqm_distributions(
    iqm_paths, scanner_metadata, participant_id, session_id, qc_config_path: str = None, dataset_dir: str = None, run_identifier: str = None
):

    if not iqm_paths:
        st.warning(ERROR_MESSAGES["iqm_no_sources_configured"])
        return

    st.subheader(MESSAGES["iqm_distribution_header"])

    manufacturer = scanner_metadata.get("Manufacturer", "Unknown") if isinstance(scanner_metadata, dict) else scanner_metadata
    field_strength = scanner_metadata.get("MagneticFieldStrength") if isinstance(scanner_metadata, dict) else None
    protocol = scanner_metadata.get("ProtocolName", "Unknown") if isinstance(scanner_metadata, dict) else "Unknown"
    field_strength_label = f"{field_strength}T" if str(field_strength).replace(".", "", 1).isdigit() else (field_strength or "Unknown")
    scanner_summary = f"Vendor: {manufacturer or 'Unknown'}  ·  Protocol: {protocol or 'Unknown'}  ·  Field strength: {field_strength_label}"

    sources = _load_iqm_sources(iqm_paths, qc_config_path, dataset_dir)
    if not sources:
        return  # per-source errors/warnings already surfaced above

    # ____________Display mode selection___________
    tab_options = _disambiguate_tab_labels(sources)

    remembered_tab = SessionManager.get_iqm_view_selection()
    if remembered_tab not in tab_options:
        remembered_tab = tab_options[0]
        SessionManager.set_iqm_view_selection(remembered_tab)

    def _remember_iqm_view_selection():
        SessionManager.set_iqm_view_selection(st.session_state["iqm_view_mode"])

    selected_label = st.segmented_control(
        "IQM source",
        options=tab_options,
        default=remembered_tab,
        key="iqm_view_mode",
        on_change=_remember_iqm_view_selection,
        label_visibility="collapsed",
    )
    if selected_label is None:
        selected_label = remembered_tab

    # find the selected source
    source = next((s for s, label in zip(sources, tab_options) if label == selected_label), None)

    source_modality = getattr(source, "modality", None)
    caption = f"{scanner_summary}  ·  Modality: {source_modality}" if source_modality else scanner_summary
    if hasattr(st, "caption"):
        st.caption(caption)
    else:
        st.info(caption)

    if isinstance(source, MetricsSource):
        _render_iqm_metrics_table(source.metrics, participant_id)
        return

    can_compare_reference = is_mriqc_pipeline(source.pipeline_name) and source.modality is not None

    mode = DISPLAY_MODE_OPTIONS[0]
    reference_data = None
    if can_compare_reference:

        def _remember_iqm_display_mode():
            SessionManager.set_iqm_display_mode_selection(st.session_state["iqm_display_mode"])

        mode = st.radio(
            "Display mode",
            options=DISPLAY_MODE_OPTIONS,
            index=DISPLAY_MODE_OPTIONS.index(SessionManager.get_iqm_display_mode_selection()),
            key="iqm_display_mode",
            on_change=_remember_iqm_display_mode,
            horizontal=True,
        )
        if mode == DISPLAY_MODE_OPTIONS[1]:
            try:
                reference_data = load_reference_iqm_for_subject(
                    modality=source.modality,
                    manufacturer=manufacturer,
                    field_strength=field_strength,
                    max_rows=MAX_REFERENCE_ROWS,
                )
            except Exception as e:
                st.error(ERROR_MESSAGES["reference_data_load_error"].format(modality=source.modality, error=e))
                reference_data = None
            else:
                if reference_data is None or reference_data.empty:
                    st.warning("No reference data available for this scanner/field strength; showing dataset-only distribution.")
                    reference_data = None

    st.write("Overview of IQM distributions across the dataset, with current subject highlighted.")
    with st.container(height=CONTAINER_HEIGHT, border=False):
        _render_montage_of_iqm_groups(
            valid_groups=source.valid_groups,
            iqm_data=source.iqm_data,
            reference_data=reference_data,
            participant_id=participant_id,
            session_id=session_id,
            modality=source.modality or source.pipeline_name,
            display_mode=mode,
            run_identifier=run_identifier,
        )


def _display_iqm_panel(
    qc_config: dict, qc_config_path: str, participant_id: str, session_id: str, dataset_dir: str = None, qc_task: str = None
) -> None:
    """Display the IQM distribution panel.

    Args:
        qc_config: QC configuration object
        qc_config_path: Path to the QC configuration file
        participant_id: ID of the participant whose data to display
        qc_task: The QC task for which to display IQM distributions
    """

    iqm_config = qc_config.get("iqm_path", {})

    scanner_metadata = _load_scanner_metadata(
        qc_config.get("base_mri_image_path"),
        participant_id=participant_id,
        session_id=session_id,
        dataset_dir=dataset_dir,
    )

    run_identifier = _extract_run_identifier(
        qc_config.get("base_mri_image_path"),
        participant_id,
        session_id,
    )

    _render_iqm_distributions(
        iqm_config,
        scanner_metadata,
        participant_id,
        session_id,
        qc_config_path=qc_config_path,
        dataset_dir=dataset_dir,
        run_identifier=run_identifier,
    )
