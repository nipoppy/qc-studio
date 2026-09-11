"""QC viewer component for displaying MRI, montage, and metrics panels."""

import math
import re
import streamlit as st
import streamlit.components.v1 as components
import time
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from constants import (
    MONTAGE_HEIGHT,
    MESSAGES,
    ERROR_MESSAGES,
    QC_RATINGS,
    NIIVUE_SECONDARY_RATIO,
    VIEW_MODES,
    OVERLAY_COLORMAPS,
    SUCCESS_MESSAGES,
    INFO_MESSAGES,
)
from utils.data_loaders import load_montage_data as _load_montage_data_uncached
from utils.config import parse_qc_config
from utils.cohort import compact_session_label
from utils.export import save_qc_results_to_csv
from utils.navigation import request_navigation_rerun
from managers.niivue_viewer_manager import NiivueViewerManager, NiivueViewerConfig
from managers.session_manager import SessionManager
from models import QCRecord
from components.iqm_viewer import _display_iqm_panel as display_iqm_distribution_panel

AUTOPLAY_RUN_CTX_KEY = "_autoplay_run_ctx"
QC_SAVE_PATH_KEY = "qc_save_path"
QC_SAVE_PATH_DEFAULT_KEY = "_qc_save_path_default"
PENDING_QC_SAVE_MSG_KEY = "pending_qc_save_msg"


def _should_refresh_qc_save_path_widget(current_value: str | None, previous_default: str | None, new_default: str | None) -> bool:
    """True when the widget still holds a stale default from a previous run."""
    if new_default is None or new_default == previous_default:
        return False
    if current_value is None:
        return True
    current_str = str(current_value).strip()
    previous_str = str(previous_default or "").strip()
    if not current_str or not previous_str:
        return False
    if current_str == previous_str:
        return True
    try:
        current_path = Path(current_str).expanduser().resolve()
        previous_path = Path(previous_str).expanduser().resolve()
        if current_path.name == previous_path.name and current_path.parent == previous_path.parent:
            return True
    except Exception:
        pass
    return False


# Extra wait past the configured autoplay duration before advancing, so a rating click
# made right at the boundary has time to reach the server and self-save via on_change
# before the poll treats the interval as elapsed.
AUTOPLAY_ADVANCE_GRACE_SECONDS = 0.3


def _clean_filename(filename: str) -> str:
    """Return a compact tab label from an internal image key."""
    # Functional-style names: ses/task/run are the most informative tokens.
    pattern = r"((?:ses-[^_]+_)?(?:task-[^_]+_?)?(?:run-[^_]+)?)"
    match = re.search(pattern, filename)
    if match and match.group(1):
        clean_label = match.group(1).strip("_")
        if clean_label:
            return clean_label

    # Remove extension suffix added during key construction.
    clean = re.sub(r"_(svg|png|jpeg)$", "", filename)
    # For anatomy-like keys, strip subject-prefixed path fragments.
    if "sub-" in clean:
        clean = re.sub(r"^.*sub-[^_]+_", "", clean)
    return clean or filename


def try_autoplay_advance_if_due(
    participant_id: str | None,
    session_id: str | None,
    qc_pipeline: str | None,
    qc_task: str | None,
    qc_tasks: list | None,
    total_participants: int | None,
    qc_cohort: list | None = None,
    participant_ids: list | None = None,
) -> None:
    """If autoplay interval elapsed, save ratings and go to next page (or stop at end).

    Called from the autoplay sidebar fragment. Uses ``st.rerun()`` when it advances or
    stops so the full app reloads on a new cohort row.
    """
    if participant_id is None or not total_participants:
        return
    if not SessionManager.is_autoplay_enabled():
        return
    start_time = SessionManager.get_autoplay_start_time()
    if start_time <= 0:
        return
    elapsed = time.time() - start_time
    duration = SessionManager.get_autoplay_duration()
    if elapsed < duration + AUTOPLAY_ADVANCE_GRACE_SECONDS:
        return
    tasks = list(qc_tasks or [])
    if not tasks:
        tasks = [qc_task] if qc_task else ["anat_wf_qc"]

    current_page = SessionManager.get_current_page()
    _, next_page = _filtered_adjacent_pages(
        current_page=current_page, total_participants=total_participants, participant_ids=participant_ids, qc_cohort=qc_cohort, session_id=session_id
    )

    if next_page is not None:
        _record_all_qc_tasks(participant_id, session_id, qc_pipeline, tasks)
        SessionManager.set_current_page(next_page)
        SessionManager.set_autoplay_start_time(time.time())
    else:
        _record_all_qc_tasks(participant_id, session_id, qc_pipeline, tasks)
        if not _has_active_subject_filter() and (
            qc_cohort
            and SessionManager.all_qc_cohort_pages_complete_for_tasks(tasks, qc_cohort)
            or not qc_cohort
            and participant_ids
            and session_id
            and _cohort_entries_for_filter(qc_cohort, participant_ids, session_id, total_participants)
            and SessionManager.all_qc_cohort_pages_complete_for_tasks(
                tasks, _cohort_entries_for_filter(qc_cohort, participant_ids, session_id, total_participants)
            )
        ):
            SessionManager.set_current_page(total_participants + 1)
        SessionManager.set_autoplay_enabled(False)
        SessionManager.set_autoplay_start_time(0.0)
    request_navigation_rerun(st)


def _render_autoplay_countdown_main_banner() -> None:
    """Large, visible countdown above the QC viewer (client-side ticks; no fragment redraw)."""
    if not SessionManager.is_autoplay_enabled():
        return
    t0 = SessionManager.get_autoplay_start_time()
    if t0 <= 0:
        return
    duration = float(SessionManager.get_autoplay_duration())
    deadline_ms = int((t0 + duration) * 1000)
    secs_now = max(0, int(math.ceil(duration - (time.time() - t0) - 1e-9)))
    components.html(
        f"""
		<div style="font-family:system-ui,sans-serif;padding:10px 14px;background:#153448;
		  color:#f8fafc;border-radius:10px;margin:0 0 12px 0;display:flex;align-items:center;
		  gap:10px;flex-wrap:wrap;">
		  <span style="font-size:1.35rem;">⏱️</span>
		  <span style="opacity:0.95;">Next page in</span>
		  <span id="qc_autoplay_sec" style="font-size:1.75rem;font-weight:700;min-width:2ch;
		    text-align:center;">{secs_now}</span>
		  <span style="opacity:0.95;">s</span>
		</div>
		<script>
		(function() {{
		  const deadline = {deadline_ms};
		  const el = document.getElementById("qc_autoplay_sec");
		  function tick() {{
		    if (!el) return;
		    const sec = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
		    el.textContent = sec;
		  }}
		  tick();
		  setInterval(tick, 150);
		}})();
		</script>
		""",
        height=76,
    )


@st.fragment(run_every=timedelta(milliseconds=400))
def _autoplay_fragment_advance_only() -> None:
    """Periodic server check to advance when the interval elapses (sidebar; no countdown UI here)."""
    ctx = st.session_state.get(AUTOPLAY_RUN_CTX_KEY)
    if not ctx or not SessionManager.is_autoplay_enabled():
        return
    try_autoplay_advance_if_due(
        participant_id=ctx.get("participant_id"),
        session_id=ctx.get("session_id"),
        qc_pipeline=ctx.get("qc_pipeline"),
        qc_task=ctx.get("qc_task"),
        qc_tasks=ctx.get("qc_tasks"),
        total_participants=ctx.get("total_participants"),
        qc_cohort=ctx.get("qc_cohort"),
        participant_ids=ctx.get("participant_ids"),
    )


def display_qc_viewers(
    dataset_dir,
    qc_config_path: str,
    substitution_values: dict,
    participant_id: str = None,
    session_id: str = None,
    qc_pipeline: str = None,
    qc_task: str = None,
    qc_tasks: list | None = None,
    total_participants: int = None,
    participant_ids: list | None = None,
    qc_cohort: list | None = None,
) -> None:
    """Display QC viewers (Niivue, MONTAGE, IQM) for one or more tasks from ``qc.json``."""
    cohort_eff = qc_cohort
    if cohort_eff is None and participant_ids:
        sid = session_id or "ses-01"
        cohort_eff = []
        for p in participant_ids:
            ps = str(p).strip()
            if not ps.startswith("sub-"):
                ps = f"sub-{ps}"
            cohort_eff.append({"participant_id": ps, "session_id": sid})

    tasks = list(qc_tasks or [])
    if not tasks:
        tasks = [qc_task] if qc_task else ["anat_wf_qc"]

    multi_task = len(tasks) > 1

    selected_panels = SessionManager.get_selected_panels()
    selected_panels = {
        "niivue": selected_panels.get("niivue_col", selected_panels.get("niivue", True)),
        "montage": selected_panels.get("montage_col", selected_panels.get("montage", True)),
        "iqm": selected_panels.get("iqm_col", selected_panels.get("iqm", False)),
    }

    show_niivue = selected_panels.get("niivue", True)
    show_montage = selected_panels.get("montage", True)
    show_iqm = selected_panels.get("iqm", False)

    _render_autoplay_countdown_main_banner()

    st.markdown(f"**{compact_session_label(participant_id, session_id)}**")

    for i, tname in enumerate(tasks):
        qc_config = parse_qc_config(qc_config_path, tname, substitution_values)
        display_label = qc_config.get("display_name") or tname
        if multi_task and i > 0:
            st.divider()
        st.subheader(display_label)
        task_has_niivue = show_niivue and bool(qc_config.get("base_mri_image_path"))
        if task_has_niivue and show_montage and show_iqm:
            _display_niivue_with_secondary_panel(
                dataset_dir,
                selected_panels,
                qc_config,
                participant_id,
                session_id,
                tname,
                qc_config_path=qc_config_path,
            )
        elif task_has_niivue and show_montage:
            _display_niivue_with_secondary_panel(
                dataset_dir, selected_panels, qc_config, participant_id, session_id, tname, qc_config_path=qc_config_path
            )
        elif task_has_niivue and show_iqm:
            _display_niivue_with_secondary_panel(
                dataset_dir, selected_panels, qc_config, participant_id, session_id, tname, qc_config_path=qc_config_path
            )
        elif task_has_niivue:
            _display_niivue_full_width(dataset_dir, qc_config, participant_id, session_id, tname)
        elif show_montage and show_iqm:
            _display_montage_panel(dataset_dir, qc_config)
            st.divider()
            display_iqm_distribution_panel(
                qc_config,
                qc_config_path,
                participant_id,
                session_id,
                dataset_dir,
            )
        elif show_montage:
            _display_montage_panel(dataset_dir, qc_config)
        elif show_iqm:
            display_iqm_distribution_panel(
                qc_config,
                qc_config_path,
                participant_id,
                session_id,
                dataset_dir,
            )

        _display_qc_rating_for_task(
            participant_id=participant_id,
            session_id=session_id,
            qc_pipeline=qc_pipeline,
            qc_task=tname,
            display_label=display_label,
            notes_height=88 if multi_task else 120,
        )


def _display_niivue_with_secondary_panel(
    dataset_dir,
    selected_panels: dict,
    qc_config,
    participant_id: str = None,
    session_id: str = None,
    task_suffix: str = "",
    qc_config_path: str = None,
) -> None:
    """Display 3-column layout: Niivue with hidden controls | Secondary panel.

    Niivue controls are hidden in an expander attached to the Niivue viewer column.
    Used when Niivue is selected with either montage or IQM panel.

    Args:
        dataset_dir: Root dataset directory
        selected_panels: Dictionary of selected panels
        qc_config: QC configuration object
        participant_id: Current participant ID
        session_id: Current session ID
        qc_config_path: Path to the QC configuration file (needed to resolve IQM source paths)
    """
    viewer_col, panel_col = st.columns([0.3, 0.7], gap="small")

    # Left column: Niivue viewer with hidden controls at bottom
    with viewer_col:
        # Get niivue config from session state or render_controls_panel
        niivue_config = _get_or_render_niivue_config(
            task_suffix,
            has_overlay=bool(qc_config.get("overlay_mri_image_path")),
        )

        # Render viewer at top
        NiivueViewerManager.render_viewer(dataset_dir, qc_config, niivue_config, participant_id, session_id, task_suffix=task_suffix)

        # Render controls in expander at bottom
        with st.expander("🎮 Niivue Controls", expanded=False):
            NiivueViewerManager.render_controls_panel(state_suffix=task_suffix)

    # Right column: Montage or IQM panel
    with panel_col:
        if selected_panels.get("montage", False):
            _display_montage_panel(dataset_dir, qc_config)
        if selected_panels.get("iqm", False):
            if selected_panels.get("montage", False):
                st.divider()
            display_iqm_distribution_panel(
                qc_config,
                qc_config_path,
                participant_id,
                session_id,
                dataset_dir,
            )


def _display_niivue_full_width(dataset_dir, qc_config, participant_id: str = None, session_id: str = None, task_suffix: str = "") -> None:
    """Display Niivue in full width with hidden controls in an expander at bottom.

    Args:
            dataset_dir: Root dataset directory
            qc_config: QC configuration object
            participant_id: Current participant ID
            session_id: Current session ID
    """
    # Get niivue config from session state or render_controls_panel
    niivue_config = _get_or_render_niivue_config(
        task_suffix,
        has_overlay=bool(qc_config.get("overlay_mri_image_path")),
    )

    # Render viewer at top
    NiivueViewerManager.render_viewer(dataset_dir, qc_config, niivue_config, participant_id, session_id, task_suffix=task_suffix)

    # Render controls in expander at bottom
    with st.expander("🎮 Niivue Controls", expanded=False):
        NiivueViewerManager.render_controls_panel(state_suffix=task_suffix)


def _get_or_render_niivue_config(state_suffix: str = "", has_overlay: bool = False):
    """Return NiivueViewerConfig; use per-task session state when ``state_suffix`` is set."""
    state_key = "niivue_config" if not state_suffix else f"niivue_config_{state_suffix}"
    if state_key not in st.session_state:
        default_config = NiivueViewerConfig(
            view_mode=VIEW_MODES[0],
            overlay_colormap=OVERLAY_COLORMAPS[0],
            show_crosshair=False,
            radiological=False,
            show_colorbar=True,
            interpolation=True,
            show_overlay=has_overlay,
        )
        st.session_state[state_key] = default_config

    return st.session_state[state_key]


@st.cache_data(show_spinner=False, max_entries=128)
def _load_montage_data_cached(dataset_dir, qc_config, max_montage_rows, max_montage_cols):
    """Cached wrapper around ``data_loaders.load_montage_data``."""
    return _load_montage_data_uncached(dataset_dir, qc_config, max_montage_rows, max_montage_cols)


def _display_montage_panel(dataset_dir, qc_config) -> None:
    """Display SVG/PNG/JPEG montage panel with tabs for multiple images.

    If multiple image files are available, renders them as separate tabs.
    If only one image file is available, displays it directly.

    Supports:
    - SVG: Rendered as HTML
    - PNG/JPEG: Displayed as images using st.image()

    Args:
            dataset_dir: Root dataset directory
            qc_config: QC configuration object
    """
    st.header(MESSAGES["montage_header"])

    # Get montage grid settings from session manager
    max_montage_rows = SessionManager.get_montage_max_rows()
    max_montage_cols = SessionManager.get_montage_max_cols()

    image_data = _load_montage_data_cached(dataset_dir, qc_config, max_montage_rows, max_montage_cols)

    if image_data:
        # If multiple images, create tabs
        if len(image_data) > 1:
            tab_names = [_clean_filename(f) for f in image_data.keys()]
            tabs = st.tabs(tab_names)
            for tab, (filename, data) in zip(tabs, image_data.items()):
                with tab:
                    _render_image(data, filename)
        else:
            # Single image - display directly
            filename, data = list(image_data.items())[0]
            _render_image(data, filename)
    else:
        st.info(ERROR_MESSAGES["montage_not_found"])


def _render_image(image_data: dict, filename: str) -> None:
    """Render a single image (SVG, PNG, or JPEG) in Streamlit.

    Args:
            image_data: Dict with keys 'type' and 'content'
            filename: Name of the image file for display
    """
    image_type = image_data.get("type")
    content = image_data.get("content")

    if image_type == "svg":
        # Render SVG as HTML
        st.components.v1.html(content, height=MONTAGE_HEIGHT, scrolling=True)
    elif image_type in ["png", "jpeg"]:
        # Display PNG/JPEG as image
        st.image(content, width="stretch", caption=filename)
    else:
        st.warning(f"Unsupported image type: {image_type}")


def _rating_widget_key(qc_task: str, rver: int) -> str:
    return f"qc_rating_{qc_task}_{rver}"


def _notes_widget_key(qc_task: str, nver: int) -> str:
    return f"qc_notes_{qc_task}_{nver}"


def _on_rating_change(participant_id, session_id, qc_pipeline, qc_task, rver, nver):
    """Callback to save rating and notes when changed."""
    rating = st.session_state.get(_rating_widget_key(qc_task, rver))
    notes = st.session_state.get(_notes_widget_key(qc_task, nver), "")
    _record_qc_for_current_participant(participant_id, session_id, qc_pipeline, qc_task, rating, notes)


def _display_qc_rating_for_task(
    participant_id: str | None,
    session_id: str | None,
    qc_pipeline: str | None,
    qc_task: str,
    *,
    display_label: str | None = None,
    notes_height: int = 120,
) -> None:
    """PASS/FAIL/UNCERTAIN and notes for one task (shown under that task's viewers)."""
    label = (display_label or qc_task).strip()
    st.markdown(f"#### 📊 Rate **{label}**")
    rver = SessionManager.get_rating_version()
    nver = SessionManager.get_notes_version()
    existing_record = SessionManager.get_qc_record_for_participant(participant_id, session_id, qc_task)
    if existing_record:
        existing_rating = existing_record.final_qc if hasattr(existing_record, "final_qc") else existing_record.get("final_qc")
        initial_rating = existing_rating if existing_rating in QC_RATINGS else None
        initial_notes = existing_record.notes if hasattr(existing_record, "notes") else existing_record.get("notes", "")
        initial_notes = initial_notes or ""
    else:
        initial_rating = None
        initial_notes = ""
    st.radio(
        " ",
        options=QC_RATINGS,
        index=QC_RATINGS.index(initial_rating) if initial_rating else None,
        key=_rating_widget_key(qc_task, rver),
        label_visibility="collapsed",
        on_change=_on_rating_change,
        args=(participant_id, session_id, qc_pipeline, qc_task, rver, nver),
    )
    st.text_area(
        MESSAGES["qc_notes_prompt"],
        value=initial_notes,
        key=_notes_widget_key(qc_task, nver),
        height=notes_height,
    )


def _record_all_qc_tasks(participant_id: str, session_id: str, qc_pipeline: str, qc_tasks: list) -> None:
    rver = SessionManager.get_rating_version()
    nver = SessionManager.get_notes_version()
    for t in qc_tasks:
        rating = st.session_state.get(_rating_widget_key(t, rver))
        notes = st.session_state.get(_notes_widget_key(t, nver), "")
        _record_qc_for_current_participant(participant_id, session_id, qc_pipeline, t, rating, notes)


def _cohort_entries_for_filter(
    qc_cohort: list | None,
    participant_ids: list | None,
    session_id: str,
    total_participants: int,
) -> list:
    limit = max(int(total_participants), 0)
    if qc_cohort is not None:
        return list(qc_cohort)[:limit]
    return [{"participant_id": str(pid), "session_id": session_id} for pid in list(participant_ids or [])][:limit]


def _cohort_entries_for_active_filter(
    qc_cohort: list | None,
    participant_ids: list | None,
    session_id: str,
    total_participants: int,
) -> list:
    """Return the currently visible cohort subset under the active sidebar filter, if any."""
    from views.sidebar_cohort_nav import _matching_subject_entries, get_subject_search_query

    entries = _cohort_entries_for_filter(qc_cohort, participant_ids, session_id, total_participants)
    query = get_subject_search_query()
    if not query:
        return entries
    return [entry for _, entry in _matching_subject_entries(entries, query, session_id)]


def _has_active_subject_filter() -> bool:
    """True when a sidebar subject filter is currently active."""
    from views.sidebar_cohort_nav import get_subject_search_query

    return bool(get_subject_search_query())


def _filtered_cohort_complete_for_tasks(
    qc_tasks: list,
    qc_cohort: list | None,
    participant_ids: list | None,
    session_id: str,
    total_participants: int,
) -> bool:
    """True when the visible subset under the active filter is finished for all tasks."""
    active_entries = _cohort_entries_for_active_filter(qc_cohort, participant_ids, session_id, total_participants)
    if not active_entries:
        return False
    return SessionManager.all_qc_cohort_pages_complete_for_tasks(qc_tasks, active_entries)


def _filtered_adjacent_pages(
    current_page: int,
    total_participants: int,
    participant_ids: list | None,
    qc_cohort: list | None,
    session_id: str,
) -> tuple[int | None, int | None]:
    """Previous/next pages that match the subject filter. Empty filter → full cohort order."""
    from views.sidebar_cohort_nav import get_subject_search_query, next_visible_subject_page, prev_visible_subject_page

    entries = _cohort_entries_for_filter(qc_cohort, participant_ids, session_id, total_participants)
    # Fallback for direct calls (e.g., tests) where cohort data is not provided.
    # In that case, use simple contiguous pagination bounds.
    if not entries:
        prev_page = current_page - 1 if current_page > 1 else None
        next_page = current_page + 1 if current_page < total_participants else None
        return prev_page, next_page
    query = get_subject_search_query()
    return (
        prev_visible_subject_page(entries, query, session_id, current_page),
        next_visible_subject_page(entries, query, session_id, current_page),
    )


def _sanitize_qc_task_slug(qc_task: str | None) -> str:
    """Build a filepath-safe QC task slug; ``all`` stays explicit in the filename."""
    task = str(qc_task or "").strip()
    if not task:
        return "unknown_task"
    task_l = task.lower()
    if task_l == "all":
        return "all_tasks"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", task).strip("_") or "unknown_task"


def _default_qc_status_filename(rater_id: str | None, qc_task: str | None) -> str:
    """Stable status filename without timestamp/session-id suffixes."""
    rid = str(rater_id or "rater").strip().lower() or "rater"
    task_slug = _sanitize_qc_task_slug(qc_task)
    return f"{rid}_{task_slug}_status.tsv"


def _build_qc_session_label(
    rater_id: str,
    qc_pipeline: str | None,
    qc_task: str | None,
    qc_session_id: str | None = None,
) -> str:
    """Human-readable QC session label for file naming and UI state."""
    rid = str(rater_id or "rater").strip().lower() or "rater"
    pipe = str(qc_pipeline or "qc").strip().lower() or "qc"
    task_slug = _sanitize_qc_task_slug(qc_task)
    if qc_session_id and str(qc_session_id).strip():
        return f"{rid}_{pipe}_{task_slug}_{str(qc_session_id).strip()}"
    return f"{rid}_{pipe}_{task_slug}"


def _resolve_output_base_dir(out_dir: str | None) -> Path:
    """Resolve the CLI output directory to a stable absolute path regardless of cwd."""
    base_dir = Path(str(out_dir).strip()).expanduser() if out_dir and str(out_dir).strip() else Path(".").expanduser()
    return base_dir.resolve() if base_dir.is_absolute() else (Path.cwd() / base_dir).resolve()


def _default_qc_save_path(
    out_dir: str | None,
    qc_pipeline: str | None = None,
    qc_task: str | None = None,
    qc_session_id: str | None = None,
) -> str:
    """Default save path shown to users in the sidebar."""
    base_dir = _resolve_output_base_dir(out_dir)
    filename = _default_qc_status_filename(SessionManager.get_rater_id(), qc_task)
    return str((base_dir / filename).resolve())


def _checkpoint_dir_for_session(out_dir: str | None, qc_session_id: str | None = None) -> Path:
    """Directory for timestamped checkpoint snapshots associated with a QC session."""
    base_dir = _resolve_output_base_dir(out_dir)
    checkpoint_dir = base_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir.resolve()


def _default_qc_checkpoint_path(
    out_dir: str | None,
    qc_pipeline: str | None = None,
    qc_task: str | None = None,
    qc_session_id: str | None = None,
    timestamp: str | None = None,
) -> str:
    """Timestamped checkpoint snapshot filename for the current QC session."""
    stamp = str(timestamp or datetime.now().strftime("%Y%m%dT%H%M%SZ"))
    session_label = _build_qc_session_label(
        SessionManager.get_rater_id(),
        qc_pipeline,
        qc_task,
        qc_session_id or SessionManager.get_qc_session_id(),
    )
    checkpoint_dir = _checkpoint_dir_for_session(out_dir, qc_session_id or SessionManager.get_qc_session_id())
    return str((checkpoint_dir / f"{session_label}_checkpoint_{stamp}.tsv").resolve())


def _create_qc_checkpoint(
    records: list,
    out_dir: str | None,
    qc_pipeline: str | None,
    qc_task: str | None,
    *,
    qc_session_id: str | None = None,
    timestamp: str | None = None,
) -> Path:
    """Create a time-stamped checkpoint file for the current QC session; does not overwrite prior checkpoints."""
    checkpoint_path = Path(
        _default_qc_checkpoint_path(
            out_dir,
            qc_pipeline=qc_pipeline,
            qc_task=qc_task,
            qc_session_id=qc_session_id,
            timestamp=timestamp,
        )
    )
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for rec in records:
        if hasattr(rec, "model_dump"):
            rows.append(rec.model_dump())
        elif hasattr(rec, "dict"):
            rows.append(rec.dict())
        elif isinstance(rec, dict):
            rows.append(rec)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "pipeline",
                "qc_task",
                "participant_id",
                "session_id",
                "task_id",
                "run_id",
                "timestamp",
                "rater_id",
                "rater_experience",
                "rater_fatigue",
                "final_qc",
                "notes",
            ]
        )
    df.to_csv(checkpoint_path, sep="\t", index=False)
    return checkpoint_path


def _require_overwrite_confirmation(file_path: str | Path, label: str) -> bool:
    """Require a second explicit click before overwriting an existing export file."""
    target = Path(str(file_path)).expanduser()
    if not target.exists():
        st.session_state.pop("_pending_overwrite_path", None)
        return True
    current = st.session_state.get("_pending_overwrite_path")
    if current == str(target):
        st.session_state.pop("_pending_overwrite_path", None)
        return True
    st.session_state["_pending_overwrite_path"] = str(target)
    st.warning(f"⚠️ {label} will overwrite the existing file: {target}")
    return False


def _resolve_qc_save_file_path(out_dir: str | None, save_file_path: str | None, qc_pipeline: str | None = None, qc_task: str | None = None) -> Path:
    """Resolve the final export path from optional user input.

    If the user provides a directory-like path (no suffix), append the default file name.
    """
    if save_file_path and str(save_file_path).strip():
        candidate = Path(str(save_file_path).strip()).expanduser()
        if candidate.suffix:
            return candidate
        task_name = qc_task or "all_tasks"
        return candidate / _default_qc_status_filename(SessionManager.get_rater_id(), task_name)
    return Path(_default_qc_save_path(out_dir, qc_pipeline=qc_pipeline, qc_task=qc_task, qc_session_id=SessionManager.get_qc_session_id()))


def _render_previous_page_button(target_page: int) -> None:
    """Sidebar Previous control; no-ops visually when omitted by the caller."""
    if st.button(
        MESSAGES["previous_button"],
        width="stretch",
        key="pag_prev",
        help=MESSAGES["nav_tooltip_previous"],
    ):
        SessionManager.set_current_page(target_page)
        if SessionManager.is_autoplay_enabled():
            SessionManager.set_autoplay_start_time(time.time())
        request_navigation_rerun(st)


def _render_next_page_button(target_page: int) -> None:
    """Sidebar Next control (does not save ratings)."""
    if st.button(
        MESSAGES["next_button"],
        width="stretch",
        key="pag_next",
        help=MESSAGES["nav_tooltip_next"],
    ):
        SessionManager.set_current_page(target_page)
        if SessionManager.is_autoplay_enabled():
            SessionManager.set_autoplay_start_time(time.time())
        request_navigation_rerun(st)


def _display_qc_pagination_header(current_page: int, total_participants: int) -> None:
    """Sidebar: Navigation title and page counter (call inside ``with st.sidebar:``)."""
    st.markdown("#### 📄 Navigation")
    st.write(f"**Page {current_page} of {total_participants}**")


def _display_qc_pagination_controls(
    current_page: int,
    total_participants: int,
    participant_id: str,
    session_id: str,
    qc_pipeline: str,
    qc_tasks: list,
    participant_ids: list | None = None,
    qc_cohort: list | None = None,
    out_dir: str | None = None,
    drop_duplicates: bool = True,
) -> None:
    """Sidebar: autoplay, page buttons, save CSV (call inside ``with st.sidebar:``)."""
    autoplay_col1, autoplay_col2 = st.columns([1, 1])
    with autoplay_col1:
        if st.button(MESSAGES["play_button"], width="stretch", key="autoplay_play"):
            SessionManager.set_autoplay_enabled(True)
            SessionManager.set_autoplay_start_time(time.time())
            request_navigation_rerun(st)

    with autoplay_col2:
        if st.button(MESSAGES["pause_button"], width="stretch", key="autoplay_pause"):
            SessionManager.set_autoplay_enabled(False)
            SessionManager.set_autoplay_start_time(0.0)
            request_navigation_rerun(st)

    if SessionManager.is_autoplay_enabled():
        if SessionManager.get_autoplay_start_time() > 0:
            _autoplay_fragment_advance_only()
        else:
            st.caption("Autoplay on — countdown starts on **Play**.")

    if pending := st.session_state.pop(PENDING_QC_SAVE_MSG_KEY, None):
        kind, msg = pending
        (st.success if kind == "success" else st.info)(msg)
    if pending := st.session_state.pop("_pending_filtered_subject_msg", None):
        st.info(pending)

    st.divider()

    active_task_label = "all" if len(qc_tasks) > 1 else (qc_tasks[0] if qc_tasks else qc_pipeline)
    default_save_path = _default_qc_save_path(
        out_dir,
        qc_pipeline=qc_pipeline,
        qc_task=active_task_label,
        qc_session_id=SessionManager.get_qc_session_id(),
    )
    if QC_SAVE_PATH_KEY not in st.session_state:
        st.session_state[QC_SAVE_PATH_KEY] = default_save_path
        st.session_state[QC_SAVE_PATH_DEFAULT_KEY] = default_save_path
    else:
        prev_default = st.session_state.get(QC_SAVE_PATH_DEFAULT_KEY)
        current_value = st.session_state.get(QC_SAVE_PATH_KEY, "")
        if _should_refresh_qc_save_path_widget(current_value, prev_default, default_save_path):
            st.session_state[QC_SAVE_PATH_KEY] = default_save_path
        st.session_state[QC_SAVE_PATH_DEFAULT_KEY] = default_save_path
    st.caption(f"Default save dir: {out_dir}")
    st.text_input(
        "QC status file path",
        key=QC_SAVE_PATH_KEY,
        help="Active QC session export. This is the main save file and will warn before overwriting.",
    )

    save_col, checkpoint_col = st.columns(2)
    with save_col:
        if st.button(
            MESSAGES["save_progress_button"],
            width="stretch",
            key="save_progress",
            help=MESSAGES["save_progress_help"],
        ):
            _save_qc_record(
                participant_id=participant_id,
                session_id=session_id,
                qc_pipeline=qc_pipeline,
                qc_tasks=qc_tasks,
                total_participants=total_participants,
                participant_ids=participant_ids,
                qc_cohort=qc_cohort,
                out_dir=out_dir,
                drop_duplicates=drop_duplicates,
                save_file_path=st.session_state.get(QC_SAVE_PATH_KEY),
                allow_overwrite=True,
                trigger_rerun=False,
                allow_completion_navigation=False,
            )

    with checkpoint_col:
        if st.button(
            MESSAGES["create_checkpoint_button"],
            width="stretch",
            key="create_checkpoint",
            help=MESSAGES["create_checkpoint_help"],
        ):
            records = SessionManager.get_latest_qc_records_per_dedup(None)
            if not records:
                st.info(INFO_MESSAGES["no_export_records"])
            else:
                checkpoint_path = _create_qc_checkpoint(
                    records=records,
                    out_dir=out_dir,
                    qc_pipeline=qc_pipeline,
                    qc_task=active_task_label,
                    qc_session_id=SessionManager.get_qc_session_id(),
                )
                st.success(f"Checkpoint saved to: {checkpoint_path}")

    prev_page, next_page = _filtered_adjacent_pages(
        current_page=current_page,
        total_participants=total_participants,
        participant_ids=participant_ids,
        qc_cohort=qc_cohort,
        session_id=session_id,
    )
    if prev_page is not None and next_page is not None:
        prev_col, next_col = st.columns(2)
        with prev_col:
            _render_previous_page_button(prev_page)
        with next_col:
            _render_next_page_button(next_page)
    elif prev_page is not None:
        _render_previous_page_button(prev_page)
    elif next_page is not None:
        _render_next_page_button(next_page)

    if st.button(
        MESSAGES["confirm_next_button"],
        width="stretch",
        key="pag_confirm",
        help=MESSAGES["nav_tooltip_confirm_next"],
    ):
        _record_all_qc_tasks(participant_id, session_id, qc_pipeline, qc_tasks)
        if SessionManager.is_autoplay_enabled():
            SessionManager.set_autoplay_start_time(time.time())
        elif next_page is not None:
            SessionManager.set_current_page(next_page)
        elif (
            qc_cohort
            and SessionManager.all_qc_cohort_pages_complete_for_tasks(qc_tasks, qc_cohort)
            or not qc_cohort
            and participant_ids
            and session_id
            and _cohort_entries_for_filter(qc_cohort, participant_ids, session_id, total_participants)
            and SessionManager.all_qc_cohort_pages_complete_for_tasks(
                qc_tasks, _cohort_entries_for_filter(qc_cohort, participant_ids, session_id, total_participants)
            )
        ):
            SessionManager.set_current_page(total_participants + 1)
        elif _has_active_subject_filter() and _filtered_cohort_complete_for_tasks(
            qc_tasks, qc_cohort, participant_ids, session_id, total_participants
        ):
            msg = "✅ The active filtered subject list is fully rated. Remove the filter to continue rating any remaining unrated subjects."
            st.info(msg)
            st.session_state["_pending_filtered_subject_msg"] = msg
        request_navigation_rerun(st)

    st.divider()


def _display_qc_pagination(
    current_page: int,
    total_participants: int,
    participant_id: str,
    session_id: str,
    qc_pipeline: str,
    qc_tasks: list,
    participant_ids: list | None = None,
    qc_cohort: list | None = None,
) -> None:
    """Full navigation block (header + playback / page controls)."""
    _display_qc_pagination_header(current_page, total_participants)
    st.divider()
    _display_qc_pagination_controls(
        current_page=current_page,
        total_participants=total_participants,
        participant_id=participant_id,
        session_id=session_id,
        qc_pipeline=qc_pipeline,
        qc_tasks=qc_tasks,
        participant_ids=participant_ids,
        qc_cohort=qc_cohort,
    )


def _save_qc_record(
    participant_id: str,
    session_id: str,
    qc_pipeline: str,
    qc_tasks: list,
    total_participants: int,
    participant_ids: list | None = None,
    qc_cohort: list | None = None,
    out_dir: str | None = None,
    drop_duplicates: bool = True,
    save_file_path: str | None = None,
    allow_overwrite: bool = False,
    trigger_rerun: bool = True,
    allow_completion_navigation: bool = True,
) -> str | None:
    _record_all_qc_tasks(participant_id, session_id, qc_pipeline, qc_tasks)

    export_rows = SessionManager.get_latest_qc_records_per_dedup(None)
    if export_rows:
        task_label = "all_tasks" if len(qc_tasks) > 1 else (qc_tasks[0] if qc_tasks else "unknown_task")
        out_file = _resolve_qc_save_file_path(
            out_dir,
            save_file_path,
            qc_pipeline=qc_pipeline,
            qc_task=task_label,
        )
        saved_path, dropped, _ = save_qc_results_to_csv(out_file, export_rows, drop_duplicates)
        record_count = len(export_rows)
        unique_participants = len({str(r.participant_id if hasattr(r, "participant_id") else r.get("participant_id", "")) for r in export_rows})
        msg = SUCCESS_MESSAGES["records_saved"].format(path=saved_path)
        msg += f"\n\nSaved {record_count} record(s) across {unique_participants} unique participant(s)."
        kind = "success"
    else:
        msg = INFO_MESSAGES["no_export_records"]
        kind = "info"

    if trigger_rerun:
        st.session_state[PENDING_QC_SAVE_MSG_KEY] = (kind, msg)
    else:
        st.session_state.pop(PENDING_QC_SAVE_MSG_KEY, None)
        (st.success if kind == "success" else st.info)(msg)

    cohort_is_complete = False
    if qc_cohort:
        cohort_is_complete = SessionManager.all_qc_cohort_pages_complete_for_tasks(qc_tasks, qc_cohort)
    elif participant_ids and session_id:
        temp_cohort = []
        for pid in participant_ids:
            p = str(pid).strip()
            if not p.startswith("sub-"):
                p = f"sub-{p}"
            temp_cohort.append({"participant_id": p, "session_id": session_id})
        cohort_is_complete = SessionManager.all_qc_cohort_pages_complete_for_tasks(qc_tasks, temp_cohort)

    if cohort_is_complete and allow_completion_navigation:
        SessionManager.set_current_page(total_participants + 1)
        if trigger_rerun:
            request_navigation_rerun(st)
        return msg

    if _has_active_subject_filter():
        if _filtered_cohort_complete_for_tasks(qc_tasks, qc_cohort, participant_ids, session_id, total_participants):
            info = "✅ The active filtered subject list is fully rated. Remove the filter to continue rating any remaining unrated subjects."
            st.info(info)
            st.session_state["_pending_filtered_subject_msg"] = info
        else:
            info = "✅ QC results saved for the active filtered view."
            st.info(info)
            st.session_state["_pending_filtered_subject_msg"] = info

    if trigger_rerun:
        request_navigation_rerun(st)
    return msg


def _record_qc_for_current_participant(participant_id: str, session_id: str, qc_pipeline: str, qc_task: str, rating: str, notes: str) -> None:
    """Save a QC record for the current participant without navigating."""
    # A stale/rotated widget key (e.g. the autoplay poll reading a key from before the
    # page advanced) reads back None; ignore it instead of overwriting a saved rating.
    if rating is None:
        return

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
