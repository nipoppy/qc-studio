"""QC viewer component for displaying MRI, SVG, and metrics panels."""
import streamlit as st
import time
from datetime import datetime
from constants import SVG_HEIGHT, MESSAGES, ERROR_MESSAGES, QC_RATINGS, NIIVUE_SECONDARY_RATIO, VIEW_MODES, OVERLAY_COLORMAPS
from utils.data_loaders import load_svg_data
from managers.niivue_viewer_manager import NiivueViewerManager, NiivueViewerConfig
from managers.session_manager import SessionManager
from models import QCRecord
from components.iqm_viewer import _display_iqm_panel as display_iqm_distribution_panel


def display_qc_viewers(
	dataset_dir,
	qc_config,
	qc_config_path: str = None,
	participant_id: str = None,
	session_id: str = None,
	qc_pipeline: str = None,
	qc_task: str = None,
	total_participants: int = None
) -> None:
	"""Display QC viewers (Niivue, SVG, IQM panels) based on user selection.
	
	Layout: Fixed QC rating form on left | Viewer panels on right
	
	The QC rating column is always visible on the left regardless of panel selection.
	Viewer panels adjust on the right based on selected panels.
	
	Args:
		dataset_dir: Root dataset directory
		qc_config: QC configuration object
		participant_id: Current participant ID
		session_id: Current session ID
		qc_pipeline: QC pipeline name
		qc_task: QC task name
		total_participants: Total number of participants
	"""
	st.title("🧠 QC-Studio")
	
	# Autoplay: if the countdown timer has expired, advance page BEFORE rendering
	# This ensures the NEW participant's qc_config is loaded on the next rerun
	if SessionManager.is_autoplay_enabled():
		start_time = SessionManager.get_autoplay_start_time()
		if start_time > 0:
			elapsed = time.time() - start_time
			duration = SessionManager.get_autoplay_duration()
			if elapsed >= duration:
				if SessionManager.get_current_page() < total_participants:
					# Save the current participant's QC record before advancing
					_record_qc_for_current_participant(
						participant_id, session_id, qc_pipeline, qc_task,
						rating=st.session_state.get('qc_rating', QC_RATINGS[0]),
						notes=SessionManager.get_notes()
					)
					SessionManager.next_page()
					SessionManager.set_autoplay_start_time(time.time())  # Restart timer for next page
				else:
					SessionManager.set_autoplay_enabled(False)
					SessionManager.set_autoplay_start_time(0.0)
				st.rerun()  # Rerun now loads new participant's qc_config
	
	# Get selected panels and normalize naming for backward compatibility
	selected_panels = SessionManager.get_selected_panels()
	selected_panels = {
		'niivue': selected_panels.get('niivue_col', selected_panels.get('niivue', True)),
		'svg': selected_panels.get('svg_col', selected_panels.get('svg', True)),
		'iqm': selected_panels.get('iqm_col', selected_panels.get('iqm', False))
	}
	show_niivue = selected_panels.get('niivue', True)
	show_svg = selected_panels.get('svg', True)
	show_iqm = selected_panels.get('iqm', False)
	
	# Main layout: Rating column on left, viewer panels on right
	rating_col, panels_col = st.columns([0.25, 0.75], gap="medium")
	
	# Left column: QC Rating form + Pagination (fixed, always visible)
	with rating_col:
		_display_qc_rating_form(
			participant_id=participant_id,
			session_id=session_id,
			qc_pipeline=qc_pipeline,
			qc_task=qc_task,
			total_participants=total_participants
		)
		
		st.divider()
		
		_display_pagination_in_sidebar(
			current_page=SessionManager.get_current_page(),
			total_participants=total_participants,
			participant_id=participant_id,
			session_id=session_id,
			qc_pipeline=qc_pipeline,
			qc_task=qc_task
		)

	# Right column: Viewer panels based on selection
	with panels_col:
		# All three panels selected
		if show_niivue and show_svg and show_iqm:
			_display_niivue_with_secondary_panel(
				dataset_dir,
				selected_panels,
				qc_config,
				qc_config_path=qc_config_path,
				participant_id=participant_id,
				session_id=session_id,
			)
			st.divider()
			display_iqm_distribution_panel(qc_config, qc_config_path, participant_id, session_id, dataset_dir)
		# Niivue + SVG (no IQM)
		elif show_niivue and show_svg:
			_display_niivue_with_secondary_panel(
				dataset_dir,
				selected_panels,
				qc_config,
				qc_config_path=qc_config_path,
				participant_id=participant_id,
				session_id=session_id,
			)
		# Niivue + IQM (no SVG)
		elif show_niivue and show_iqm:
			_display_niivue_with_secondary_panel(
				dataset_dir,
				selected_panels,
				qc_config,
				qc_config_path=qc_config_path,
				participant_id=participant_id,
				session_id=session_id,
			)
		# Full-width Niivue only
		elif show_niivue:
			_display_niivue_full_width(dataset_dir, qc_config, participant_id, session_id)
		# Full-width SVG only
		elif show_svg:
			_display_svg_panel(dataset_dir, qc_config)
		# Full-width IQM only
		elif show_iqm:
			display_iqm_distribution_panel(qc_config, qc_config_path, participant_id, session_id, dataset_dir)
	
	# Autoplay rerun loop: panels have now rendered; keep refreshing so the
	# countdown display stays live and the timer expiry check fires on time
	if SessionManager.is_autoplay_enabled():
		start_time = SessionManager.get_autoplay_start_time()
		if start_time > 0:
			time.sleep(0.1)
			st.rerun()


def _display_niivue_with_secondary_panel(dataset_dir, selected_panels: dict, qc_config, qc_config_path: str = None,
                                           participant_id: str = None, session_id: str = None) -> None:
	"""Display 3-column layout: Niivue with hidden controls | Secondary panel.
	
	Niivue controls are hidden in an expander attached to the Niivue viewer column.
	Used when Niivue is selected with either SVG or IQM panel.
	
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
		niivue_config = _get_or_render_niivue_config()
		
		# Render viewer at top
		NiivueViewerManager.render_viewer(dataset_dir, qc_config, niivue_config, 
		                                   participant_id, session_id)
		
		# Render controls in expander at bottom
		with st.expander("🎮 Niivue Controls", expanded=False):
			NiivueViewerManager.render_controls_panel()
	
	# Right column: SVG or IQM panel
	with panel_col:
		if selected_panels.get('svg', False):
			_display_svg_panel(dataset_dir, qc_config)
		else:
			display_iqm_distribution_panel(qc_config, qc_config_path, participant_id, session_id, dataset_dir)


def _display_niivue_full_width(dataset_dir, qc_config,
                               participant_id: str = None, session_id: str = None) -> None:
	"""Display Niivue in full width with hidden controls in an expander at bottom.
	
	Args:
		dataset_dir: Root dataset directory
		qc_config: QC configuration object
		participant_id: Current participant ID
		session_id: Current session ID
	"""
	# Get niivue config from session state or render_controls_panel
	niivue_config = _get_or_render_niivue_config()
	
	# Render viewer at top
	NiivueViewerManager.render_viewer(dataset_dir, qc_config, niivue_config,
	                                   participant_id, session_id)
	
	# Render controls in expander at bottom
	with st.expander("🎮 Niivue Controls", expanded=False):
		NiivueViewerManager.render_controls_panel()


def _get_or_render_niivue_config():
	"""Get niivue config from session state or render default config.
	
	This function allows the Niivue viewer to be displayed before the controls expander.
	On first run, it returns a default config. On subsequent runs after user changes controls,
	it returns the updated config from session state (which render_controls_panel also updates).
	
	Returns:
		NiivueViewerConfig: Configuration object for the Niivue viewer
	"""
	# Check if we have a stored config from previous control panel interaction
	if 'niivue_config' not in st.session_state:
		# First run: create and store a default config
		default_config = NiivueViewerConfig(
			view_mode=VIEW_MODES[0],
			overlay_colormap=OVERLAY_COLORMAPS[0],
			show_crosshair=False,
			radiological=False,
			show_colorbar=True,
			interpolation=True,
			show_overlay=False
		)
		st.session_state.niivue_config = default_config
	
	return st.session_state.niivue_config


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
			tabs = st.tabs(list(image_data.keys()))
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


def _display_qc_rating_form(
	participant_id: str = None,
	session_id: str = None,
	qc_pipeline: str = None,
	qc_task: str = None,
	total_participants: int = None
) -> None:
	"""Display participant info and QC rating form in fixed left column.
	
	Args:
		participant_id: Current participant ID
		session_id: Current session ID
		qc_pipeline: QC pipeline name
		qc_task: QC task name
		total_participants: Total number of participants
	"""
	# Display participant information
	st.markdown("#### 📋 Session Info")
	st.write(f"**Participant:** {participant_id}")
	st.write(f"**Session:** {session_id}")
	st.write(f"**Pipeline:** {qc_pipeline}")
	st.write(f"**Task:** {qc_task}")
	
	# Display rater information
	st.markdown("#### 👤 Rater Info")
	st.write(f"**Rater:** {SessionManager.get_rater_id()}")
	st.write(f"**Experience:** {SessionManager.get_rater_experience().split('(')[0].strip()}")
	st.write(f"**Fatigue:** {SessionManager.get_rater_fatigue().split('☕')[0].strip()}")
	
	st.divider()
	
	# QC Rating section
	st.markdown("#### 📊 QC Rating")
	rating = st.radio(MESSAGES['qc_rating_prompt'], options=QC_RATINGS, index=0, key="qc_rating")
	notes = st.text_area(MESSAGES['qc_notes_prompt'], value=SessionManager.get_notes(), key="qc_notes", height=120)
	SessionManager.set_notes(notes)


def _display_pagination_in_sidebar(
	current_page: int,
	total_participants: int,
	participant_id: str,
	session_id: str,
	qc_pipeline: str,
	qc_task: str
) -> None:
	"""Display pagination controls in the left sidebar with autoplay support.
	
	Args:
		current_page: Current page number
		total_participants: Total number of participants
		participant_id: Current participant ID
		session_id: Current session ID
		qc_pipeline: QC pipeline name
		qc_task: QC task name
	"""
	st.markdown("#### 📄 Navigation")
	st.write(f"**Participant {current_page} of {total_participants}**")
	
	# Autoplay controls (play/pause buttons)
	autoplay_col1, autoplay_col2 = st.columns([1, 1])
	with autoplay_col1:
		if st.button(MESSAGES['play_button'], use_container_width=True, key="autoplay_play"):
			SessionManager.set_autoplay_enabled(True)
			SessionManager.set_autoplay_start_time(time.time())  # Start countdown immediately
			st.rerun()
	
	with autoplay_col2:
		if st.button(MESSAGES['pause_button'], use_container_width=True, key="autoplay_pause"):
			SessionManager.set_autoplay_enabled(False)
			SessionManager.set_autoplay_start_time(0.0)  # Reset timer
			st.rerun()
	
	# Display countdown timer if autoplay is active
	if SessionManager.is_autoplay_enabled():
		start_time = SessionManager.get_autoplay_start_time()
		if start_time > 0:
			elapsed = time.time() - start_time
			duration = SessionManager.get_autoplay_duration()
			countdown = max(0, duration - int(elapsed))
			st.markdown(f"## ⏱️ Next page in: **{countdown}s**")
		else:
			st.info("⏸️ Autoplay active")
	
	st.divider()
	
	# Main pagination controls
	pag_col1, pag_col2, pag_col3 = st.columns([1, 1, 1])
	
	with pag_col1:
		if st.button(MESSAGES['previous_button'], use_container_width=True, key="pag_prev"):
			SessionManager.previous_page()
			st.rerun()
	
	with pag_col2:
		if st.button(MESSAGES['confirm_next_button'], use_container_width=True, key="pag_confirm"):
			rating = st.session_state.get('qc_rating', QC_RATINGS[0])
			notes = SessionManager.get_notes()
			_record_qc_for_current_participant(
				participant_id, session_id, qc_pipeline, qc_task, rating, notes
			)
			if SessionManager.is_autoplay_enabled():
				# Start the countdown timer; autoplay logic advances the page when it expires
				SessionManager.set_autoplay_start_time(time.time())
			else:
				SessionManager.next_page()
			st.rerun()
	
	with pag_col3:
		if st.button(MESSAGES['next_button'], use_container_width=True, key="pag_next"):
			SessionManager.next_page()
			st.rerun()
	
	st.divider()
	
	# Save QC results to CSV button
	if st.button(MESSAGES['save_csv_button'], use_container_width=True, key="pag_save_csv"):
		rating = st.session_state.get('qc_rating', QC_RATINGS[0])
		notes = SessionManager.get_notes()
		_save_qc_record(
			participant_id=participant_id,
			session_id=session_id,
			qc_pipeline=qc_pipeline,
			qc_task=qc_task,
			rating=rating,
			notes=notes,
			total_participants=total_participants
		)
	
	st.divider()
	if st.button(MESSAGES['back_landing_button'], use_container_width=True, key="pag_landing"):
		SessionManager.set_landing_page_complete(False)
		st.rerun()


def _save_qc_record(participant_id: str, session_id: str, qc_pipeline: str, 
					 qc_task: str, rating: str, notes: str, total_participants: int) -> None:
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
	_record_qc_for_current_participant(participant_id, session_id, qc_pipeline, qc_task, rating, notes)
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
