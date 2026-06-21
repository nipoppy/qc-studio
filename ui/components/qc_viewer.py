"""QC viewer component for displaying MRI, SVG, and metrics panels."""
import math
import re
import streamlit as st
import streamlit.components.v1 as components
import time
from datetime import datetime, timedelta
from constants import SVG_HEIGHT, MESSAGES, ERROR_MESSAGES, QC_RATINGS, NIIVUE_SECONDARY_RATIO, VIEW_MODES, OVERLAY_COLORMAPS
from utils.data_loaders import load_svg_data
from utils.config import parse_qc_config
from managers.niivue_viewer_manager import NiivueViewerManager, NiivueViewerConfig
from managers.session_manager import SessionManager
from models import QCRecord
from components.iqm_viewer import _display_iqm_panel as display_iqm_distribution_panel

# Session key: current QC row for autoplay fragment (set from ``main`` before sidebar).
AUTOPLAY_RUN_CTX_KEY = "_autoplay_run_ctx"


def _clean_filename(filename: str) -> str:
	"""Return a compact tab label from an internal image key."""
	# Functional-style names: ses/task/run are the most informative tokens.
	pattern = r'((?:ses-[^_]+_)?(?:task-[^_]+_?)?(?:run-[^_]+)?)'
	match = re.search(pattern, filename)
	if match and match.group(1):
		clean_label = match.group(1).strip('_')
		if clean_label:
			return clean_label

	# Remove extension suffix added during key construction.
	clean = re.sub(r'_(svg|png|jpeg)$', '', filename)
	# For anatomy-like keys, strip subject-prefixed path fragments.
	if 'sub-' in clean:
		clean = re.sub(r'^.*sub-[^_]+_', '', clean)
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
	if elapsed < duration:
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
		elif (
			not qc_cohort
			and participant_ids
			and session_id
		):
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
	"""Display QC viewers (Niivue, SVG, IQM) for one or more tasks from ``qc.json``."""
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
		'niivue': selected_panels.get('niivue_col', selected_panels.get('niivue', True)),
		'svg': selected_panels.get('svg_col', selected_panels.get('svg', True)),
		'iqm': selected_panels.get('iqm_col', selected_panels.get('iqm', False))
	}

	show_niivue = selected_panels.get('niivue', True)
	show_svg = selected_panels.get('svg', True)
	show_iqm = selected_panels.get('iqm', False)

	_render_autoplay_countdown_main_banner()

	_display_qc_session_and_rater_header(
		participant_id=participant_id,
		session_id=session_id,
		qc_pipeline=qc_pipeline,
		qc_tasks=tasks,
		multi_task=multi_task,
	)

	for i, tname in enumerate(tasks):
		qc_config = parse_qc_config(qc_config_path, tname, substitution_values)
		if multi_task:
			if i > 0:
				st.divider()
			st.subheader(tname)
		if show_niivue and show_svg and show_iqm:
			_display_niivue_with_secondary_panel(
				dataset_dir,
				selected_panels,
				qc_config,
				participant_id,
				session_id,
				tname,
				qc_config_path=qc_config_path,
			)
		elif show_niivue and show_svg:
			_display_niivue_with_secondary_panel(
				dataset_dir, selected_panels, qc_config, participant_id, session_id, tname,  qc_config_path=qc_config_path,)
		elif show_niivue and show_iqm:
			_display_niivue_with_secondary_panel(
				dataset_dir, selected_panels, qc_config, participant_id, session_id, tname, qc_config_path=qc_config_path)
		elif show_niivue:
			_display_niivue_full_width(dataset_dir, qc_config, participant_id, session_id, tname)
		elif show_svg:
			_display_svg_panel(dataset_dir, qc_config)
		elif show_iqm:
			display_iqm_distribution_panel(
				qc_config,
				qc_config_path,
				participant_id,
				session_id,
				dataset_dir,
				qc_task=tname,
			)

		_display_qc_rating_for_task(
			participant_id=participant_id,
			session_id=session_id,
			qc_task=tname,
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
	Used when Niivue is selected with either SVG or IQM panel.
	
	Args:
		dataset_dir: Root dataset directory
		selected_panels: Dictionary of selected panels
		qc_config: QC configuration object
		participant_id: Current participant ID
		session_id: Current session ID
		qc_task: The QC task for which to display IQM distributions
	"""
	viewer_col, panel_col = st.columns([0.3, 0.7], gap="small")
	
	# Left column: Niivue viewer with hidden controls at bottom
	with viewer_col:
		# Get niivue config from session state or render_controls_panel
		niivue_config = _get_or_render_niivue_config(task_suffix)
		
		# Render viewer at top
		NiivueViewerManager.render_viewer(dataset_dir, qc_config, niivue_config, 
		                                   participant_id, session_id, task_suffix=task_suffix)
		
		# Render controls in expander at bottom
		with st.expander("🎮 Niivue Controls", expanded=False):
			NiivueViewerManager.render_controls_panel(state_suffix=task_suffix)
	
	# Right column: SVG or IQM panel
	with panel_col:
		if selected_panels.get('svg', False):
			_display_svg_panel(dataset_dir, qc_config)
		if selected_panels.get('iqm', False):
			if selected_panels.get('svg', False):
				st.divider()
			display_iqm_distribution_panel(
				qc_config,
				qc_config_path,
				participant_id,
				session_id,
				dataset_dir,
				qc_task=task_suffix,
			)

def _display_niivue_full_width(dataset_dir, qc_config,
                               participant_id: str = None, session_id: str = None,
                               task_suffix: str = "") -> None:
	"""Display Niivue in full width with hidden controls in an expander at bottom.
	
	Args:
		dataset_dir: Root dataset directory
		qc_config: QC configuration object
		participant_id: Current participant ID
		session_id: Current session ID
	"""
	# Get niivue config from session state or render_controls_panel
	niivue_config = _get_or_render_niivue_config(task_suffix)
	
	# Render viewer at top
	NiivueViewerManager.render_viewer(dataset_dir, qc_config, niivue_config,
	                                   participant_id, session_id, task_suffix=task_suffix)
	
	# Render controls in expander at bottom
	with st.expander("🎮 Niivue Controls", expanded=False):
		NiivueViewerManager.render_controls_panel(state_suffix=task_suffix)


def _get_or_render_niivue_config(state_suffix: str = ""):
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
			show_overlay=False
		)
		st.session_state[state_key] = default_config
	
	return st.session_state[state_key]


def _display_svg_panel(dataset_dir, qc_config) -> None:
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
	st.header(MESSAGES['svg_header'])
	
	# Get montage grid settings from session manager
	max_montage_rows = SessionManager.get_montage_max_rows()
	max_montage_cols = SessionManager.get_montage_max_cols()
	
	image_data = load_svg_data(dataset_dir, qc_config, max_montage_rows, max_montage_cols)
	
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
		st.info(ERROR_MESSAGES['svg_not_found'])


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
		st.components.v1.html(content, height=SVG_HEIGHT, scrolling=True)
	elif image_type in ["png", "jpeg"]:
		# Display PNG/JPEG as image
		st.image(content, width='stretch', caption=filename)
	else:
		st.warning(f"Unsupported image type: {image_type}")


def _display_qc_session_and_rater_header(
	participant_id: str | None,
	session_id: str | None,
	qc_pipeline: str | None,
	qc_tasks: list,
	multi_task: bool,
) -> None:
	"""Session / pipeline / rater summary once above all task blocks."""
	st.markdown("#### 📋 Session Info")
	st.write(f"**Participant:** {participant_id}")
	st.write(f"**Session:** {session_id}")
	st.write(f"**Pipeline:** {qc_pipeline}")
	if multi_task:
		st.write(f"**Tasks (this page):** {', '.join(qc_tasks)}")
	else:
		st.write(f"**Task:** {qc_tasks[0] if qc_tasks else ''}")
	st.markdown("#### 👤 Rater Info")
	st.write(f"**Rater:** {SessionManager.get_rater_id()}")
	st.write(f"**Experience:** {SessionManager.get_rater_experience().split('(')[0].strip()}")
	st.write(f"**Fatigue:** {SessionManager.get_rater_fatigue().split('☕')[0].strip()}")
	st.divider()


def _display_qc_rating_for_task(
	participant_id: str | None,
	session_id: str | None,
	qc_task: str,
	*,
	notes_height: int = 120,
) -> None:
	"""PASS/FAIL/UNCERTAIN and notes for one task (shown under that task's viewers)."""
	st.markdown(f"#### 📊 Rate `{qc_task}`")
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
		key=f"qc_rating_{qc_task}_{rver}",
		label_visibility="collapsed",
	)
	st.text_area(
		MESSAGES["qc_notes_prompt"],
		value=initial_notes,
		key=f"qc_notes_{qc_task}_{nver}",
		height=notes_height,
	)


def _record_all_qc_tasks(participant_id: str, session_id: str, qc_pipeline: str, qc_tasks: list) -> None:
	rver = SessionManager.get_rating_version()
	nver = SessionManager.get_notes_version()
	for t in qc_tasks:
		rating = st.session_state.get(f"qc_rating_{t}_{rver}")
		notes = st.session_state.get(f"qc_notes_{t}_{nver}", "")
		_record_qc_for_current_participant(participant_id, session_id, qc_pipeline, t, rating, notes)


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
) -> None:
	"""Sidebar: autoplay, page buttons, save CSV (call inside ``with st.sidebar:``)."""
	autoplay_col1, autoplay_col2 = st.columns([1, 1])
	with autoplay_col1:
		if st.button(MESSAGES['play_button'], width='stretch', key="autoplay_play"):
			SessionManager.set_autoplay_enabled(True)
			SessionManager.set_autoplay_start_time(time.time())
			st.rerun()
	
	with autoplay_col2:
		if st.button(MESSAGES['pause_button'], width='stretch', key="autoplay_pause"):
			SessionManager.set_autoplay_enabled(False)
			SessionManager.set_autoplay_start_time(0.0)
			st.rerun()
	
	if SessionManager.is_autoplay_enabled():
		if SessionManager.get_autoplay_start_time() > 0:
			_autoplay_fragment_advance_only()
		else:
			st.caption("Autoplay on — countdown starts on **Play**.")
	
	st.divider()
	
	pag_col1, pag_col2, pag_col3 = st.columns([1, 1, 1])

	with pag_col1:
		if current_page > 1:
			if st.button(
				MESSAGES['previous_button'],
				width='stretch',
				key="pag_prev",
				help=MESSAGES['nav_tooltip_previous'],
			):
				SessionManager.previous_page()
				if SessionManager.is_autoplay_enabled():
					SessionManager.set_autoplay_start_time(time.time())
				st.rerun()

	with pag_col2:
		if st.button(
			MESSAGES['confirm_next_button'],
			width='stretch',
			key="pag_confirm",
			help=MESSAGES['nav_tooltip_confirm_next'],
		):
			_record_all_qc_tasks(participant_id, session_id, qc_pipeline, qc_tasks)
			if SessionManager.is_autoplay_enabled():
				SessionManager.set_autoplay_start_time(time.time())
			elif current_page < total_participants:
				SessionManager.next_page()
			elif qc_cohort and SessionManager.all_qc_cohort_pages_complete_for_tasks(qc_tasks, qc_cohort):
				SessionManager.set_current_page(total_participants + 1)
			elif (
				not qc_cohort
				and participant_ids
				and session_id
			):
				temp_cohort = []
				for pid in participant_ids:
					p = str(pid).strip()
					if not p.startswith("sub-"):
						p = f"sub-{p}"
					temp_cohort.append({"participant_id": p, "session_id": session_id})
				if SessionManager.all_qc_cohort_pages_complete_for_tasks(qc_tasks, temp_cohort):
					SessionManager.set_current_page(total_participants + 1)
			st.rerun()

	with pag_col3:
		if current_page < total_participants:
			if st.button(
				MESSAGES['next_button'],
				width='stretch',
				key="pag_next",
				help=MESSAGES['nav_tooltip_next'],
			):
				SessionManager.next_page()
				if SessionManager.is_autoplay_enabled():
					SessionManager.set_autoplay_start_time(time.time())
				st.rerun()
	
	st.divider()
	
	if st.button(MESSAGES['save_csv_button'], width='content', key="pag_save_csv"):
		_save_qc_record(
			participant_id=participant_id,
			session_id=session_id,
			qc_pipeline=qc_pipeline,
			qc_tasks=qc_tasks,
			total_participants=total_participants,
			participant_ids=participant_ids,
			qc_cohort=qc_cohort,
		)


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
	"""Full navigation block (header + controls) for callers that do not inject Subjects between."""
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
) -> None:
	_record_all_qc_tasks(participant_id, session_id, qc_pipeline, qc_tasks)
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

	st.rerun()


def _record_qc_for_current_participant(participant_id: str, session_id: str,
										 qc_pipeline: str, qc_task: str,
										 rating: str, notes: str) -> None:
	"""Save a QC record for the current participant without navigating."""
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
