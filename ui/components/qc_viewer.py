"""QC viewer component for displaying MRI, montage, and metrics panels."""

import math
from pathlib import Path
import re
import streamlit as st
import streamlit.components.v1 as components
import time
from datetime import datetime, timedelta
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
    PENDING_SIDEBAR_RERUN_KEY,
)
from utils.data_loaders import load_montage_data
from utils.export import save_qc_results_to_csv
from utils.config import parse_qc_config
from managers.niivue_viewer_manager import NiivueViewerManager, NiivueViewerConfig
from managers.session_manager import SessionManager
from models import QCRecord

AUTOPLAY_RUN_CTX_KEY = "_autoplay_run_ctx"
PENDING_QC_SAVE_MSG_KEY = "_pending_qc_save_msg"
QC_SAVE_PATH_KEY = "qc_save_path"
QC_SAVE_PATH_DEFAULT_KEY = "_qc_save_path_default"

# Extra wait past the configured autoplay duration before advancing, so a rating click
# made right at the boundary has time to reach the server and self-save via on_change
# before the poll treats the interval as elapsed.
AUTOPLAY_ADVANCE_GRACE_SECONDS = 0.3


def _compact_session_label(participant_id: str | None, session_id: str | None) -> str:
    """One-line QC header: participant, plus session when present."""
    pid = participant_id or ""
    if session_id:
        return f"{pid} · {session_id}"
    return pid


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
    if SessionManager.get_current_page() < total_participants:
        _record_all_qc_tasks(participant_id, session_id, qc_pipeline, tasks)
        SessionManager.next_page()
        SessionManager.set_autoplay_start_time(time.time())
    else:
        _record_all_qc_tasks(participant_id, session_id, qc_pipeline, tasks)
        if qc_cohort and SessionManager.all_qc_cohort_pages_complete_for_tasks(tasks, qc_cohort):
            SessionManager.set_current_page(total_participants + 1)
        elif not qc_cohort and participant_ids and session_id:
            temp_cohort = []
            for pid in participant_ids:
                p = str(pid).strip()
                if not p.startswith("sub-"):
                    p = f"sub-{p}"
                temp_cohort.append({"participant_id": p, "session_id": session_id})
            if SessionManager.all_qc_cohort_pages_complete_for_tasks(tasks, temp_cohort):
                SessionManager.set_current_page(total_participants + 1)
        SessionManager.set_autoplay_enabled(False)
        SessionManager.set_autoplay_start_time(0.0)
    st.rerun()


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

    st.markdown(f"**{_compact_session_label(participant_id, session_id)}**")

    for i, tname in enumerate(tasks):
        qc_config = parse_qc_config(qc_config_path, tname, substitution_values)
        display_label = qc_config.get("display_name") or tname
        if multi_task and i > 0:
            st.divider()
        st.subheader(display_label)
        task_has_niivue = show_niivue and bool(qc_config.get("base_mri_image_path"))
        if task_has_niivue and show_montage and show_iqm:
            _display_niivue_with_secondary_panel(dataset_dir, selected_panels, qc_config, participant_id, session_id, tname)
            st.divider()
            _display_iqm_panel()
        elif task_has_niivue and show_montage:
            _display_niivue_with_secondary_panel(dataset_dir, selected_panels, qc_config, participant_id, session_id, tname)
        elif task_has_niivue and show_iqm:
            _display_niivue_with_secondary_panel(dataset_dir, selected_panels, qc_config, participant_id, session_id, tname)
        elif task_has_niivue:
            _display_niivue_full_width(dataset_dir, qc_config, participant_id, session_id, tname)
        elif show_montage:
            _display_montage_panel(dataset_dir, qc_config)
        elif show_iqm:
            _display_iqm_panel()

        _display_qc_rating_for_task(
            participant_id=participant_id,
            session_id=session_id,
            qc_pipeline=qc_pipeline,
            qc_task=tname,
            display_label=display_label,
            notes_height=88 if multi_task else 120,
        )


def _display_niivue_with_secondary_panel(
    dataset_dir, selected_panels: dict, qc_config, participant_id: str = None, session_id: str = None, task_suffix: str = ""
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
        else:
            _display_iqm_panel()


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

    image_data = load_montage_data(dataset_dir, qc_config, max_montage_rows, max_montage_cols)

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


def _request_navigation_rerun() -> None:
    """Request an app refresh after navigation/playback actions.

    Streamlit's real ``st.rerun()`` raises internally to stop execution and rerun.
    In test contexts where rerun is mocked/no-op, fall back to the deferred sidebar key.
    """
    rerun = getattr(st, "rerun", None)
    if callable(rerun):
        rerun()
        return
    st.session_state[PENDING_SIDEBAR_RERUN_KEY] = True


def _default_qc_save_path(out_dir: str | None) -> str:
    """Default save path shown to users in the sidebar."""
    base_dir = Path(out_dir) if out_dir else Path(".")
    rater_id = SessionManager.get_rater_id() or "rater"
    return str(base_dir / f"{rater_id}_QC_status.tsv")


def _resolve_qc_save_file_path(out_dir: str | None, save_file_path: str | None) -> Path:
    """Resolve the final export path from optional user input.

    If the user provides a directory-like path (no suffix), append the default file name.
    """
    if save_file_path and str(save_file_path).strip():
        candidate = Path(str(save_file_path).strip()).expanduser()
        if candidate.suffix:
            return candidate
        rater_id = SessionManager.get_rater_id() or "rater"
        return candidate / f"{rater_id}_QC_status.tsv"
    return Path(_default_qc_save_path(out_dir))


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
        _request_navigation_rerun()


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
        _request_navigation_rerun()


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
            _request_navigation_rerun()

    with autoplay_col2:
        if st.button(MESSAGES["pause_button"], width="stretch", key="autoplay_pause"):
            SessionManager.set_autoplay_enabled(False)
            SessionManager.set_autoplay_start_time(0.0)
            _request_navigation_rerun()

    if SessionManager.is_autoplay_enabled():
        if SessionManager.get_autoplay_start_time() > 0:
            _autoplay_fragment_advance_only()
        else:
            st.caption("Autoplay on — countdown starts on **Play**.")

    st.divider()

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
        elif qc_cohort and SessionManager.all_qc_cohort_pages_complete_for_tasks(qc_tasks, qc_cohort):
            SessionManager.set_current_page(total_participants + 1)
        elif not qc_cohort and participant_ids and session_id:
            temp_cohort = []
            for pid in participant_ids:
                p = str(pid).strip()
                if not p.startswith("sub-"):
                    p = f"sub-{p}"
                temp_cohort.append({"participant_id": p, "session_id": session_id})
            if SessionManager.all_qc_cohort_pages_complete_for_tasks(qc_tasks, temp_cohort):
                SessionManager.set_current_page(total_participants + 1)
        _request_navigation_rerun()

    st.divider()

    default_save_path = _default_qc_save_path(out_dir)
    if QC_SAVE_PATH_KEY not in st.session_state:
        st.session_state[QC_SAVE_PATH_KEY] = default_save_path
        st.session_state[QC_SAVE_PATH_DEFAULT_KEY] = default_save_path
    else:
        prev_default = st.session_state.get(QC_SAVE_PATH_DEFAULT_KEY)
        current_value = st.session_state.get(QC_SAVE_PATH_KEY, "")
        if prev_default and current_value == prev_default and default_save_path != prev_default:
            st.session_state[QC_SAVE_PATH_KEY] = default_save_path
        st.session_state[QC_SAVE_PATH_DEFAULT_KEY] = default_save_path

    st.caption(f"Default path: {default_save_path}")
    st.text_input(
        "QC status file path",
        key=QC_SAVE_PATH_KEY,
        help="Set a custom file path for Save QC (for example, /path/to/QC_status.csv).",
    )

    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] .st-key-pag_save_csv button {
            width: 100% !important;
            white-space: nowrap !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        MESSAGES["save_csv_button"],
        width="stretch",
        key="pag_save_csv",
        help=MESSAGES["save_csv_help"],
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
        )

    if pending := st.session_state.pop(PENDING_QC_SAVE_MSG_KEY, None):
        kind, msg = pending
        (st.success if kind == "success" else st.info)(msg)


def _display_qc_pagination(
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
        out_dir=out_dir,
        drop_duplicates=drop_duplicates,
    )


def _display_iqm_panel() -> None:
    """Display IQM metrics panel."""
    st.caption(MESSAGES["metrics_header"])
    st.write("Add QC metrics here (e.g., SNR, motion). This is a placeholder area.")


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
) -> None:
    _record_all_qc_tasks(participant_id, session_id, qc_pipeline, qc_tasks)

    export_rows = SessionManager.get_latest_qc_records_per_dedup(None)
    if export_rows:
        out_file = _resolve_qc_save_file_path(out_dir, save_file_path)
        saved_path, dropped, _ = save_qc_results_to_csv(out_file, export_rows, drop_duplicates)
        record_count = len(export_rows)
        unique_participants = len(
            {
                str(r.participant_id if hasattr(r, "participant_id") else r.get("participant_id", ""))
                for r in export_rows
            }
        )
        msg = SUCCESS_MESSAGES["records_saved"].format(path=saved_path)
        msg += f" Saved {record_count} record(s) across {unique_participants} unique participant(s)."
        if dropped:
            msg += f" ({dropped} duplicate record(s) removed)"
        st.session_state[PENDING_QC_SAVE_MSG_KEY] = ("success", msg)
    else:
        st.session_state[PENDING_QC_SAVE_MSG_KEY] = ("info", INFO_MESSAGES["no_export_records"])

    if qc_cohort and SessionManager.all_qc_cohort_pages_complete_for_tasks(qc_tasks, qc_cohort):
        SessionManager.set_current_page(total_participants + 1)
    elif not qc_cohort and participant_ids and session_id:
        temp_cohort = []
        for pid in participant_ids:
            p = str(pid).strip()
            if not p.startswith("sub-"):
                p = f"sub-{p}"
            temp_cohort.append({"participant_id": p, "session_id": session_id})
        if SessionManager.all_qc_cohort_pages_complete_for_tasks(qc_tasks, temp_cohort):
            SessionManager.set_current_page(total_participants + 1)
    _request_navigation_rerun()


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
