"""Multipage sidebar: one control per subject with QC-done marker (Streamlit app sidebar)."""

import time

import streamlit as st

from constants import MESSAGES
from managers.session_manager import SessionManager

_MAX_PID_DISPLAY_LEN = 28
def render_sidebar_cohort_subjects(
	*,
	qc_cohort: list | None = None,
	total_participants: int,
	qc_task: str = "anat_wf_qc",
	qc_tasks: list | None = None,
	entrypoint_rel_path: str | None = None,
	participant_ids: list | None = None,
	session_id: str = "ses-01",
	prepend_navigation: bool = False,
	navigation_kwargs: dict | None = None,
) -> None:
	"""Add sidebar content: **Navigation** (page count), **Subjects**, then nav controls.

	When ``prepend_navigation`` is True and ``navigation_kwargs`` is set, renders the
	``#### 📄 Navigation`` header and **Page X of Y** line, then the subject list with
	checkmarks, then autoplay / prev–confirm–next / save. Call **before** main-column
	content so Streamlit shows the sidebar reliably.

	Each subject row is a full-width button: ✅ if QC saved for all active tasks, ⬜ otherwise.
	When ``entrypoint_rel_path`` is set (e.g. ``\"main.py\"``), uses ``st.switch_page``.
	"""
	if not SessionManager.is_landing_page_complete():
		return

	tasks_eff = list(qc_tasks) if qc_tasks else [qc_task]

	if qc_cohort is None:
		ids = list(participant_ids or [])[: max(int(total_participants), 0)]
		if not ids:
			return
		entries = [{"participant_id": str(pid), "session_id": session_id} for pid in ids]
	else:
		entries = list(qc_cohort or [])[: max(int(total_participants), 0)]
	if not entries:
		return

	with st.sidebar:
		kw = navigation_kwargs if (prepend_navigation and navigation_kwargs) else None
		if kw:
			from components.qc_viewer import (
				_display_qc_pagination_controls,
				_display_qc_pagination_header,
			)

			_display_qc_pagination_header(kw["current_page"], kw["total_participants"])
		st.caption(MESSAGES["sidebar_subjects_header"])
		current_page = SessionManager.get_current_page()
		for i, entry in enumerate(entries):
			page_num = i + 1
			pid = str(entry.get("participant_id", ""))
			sid = str(entry.get("session_id", session_id))
			done = all(
				SessionManager.participant_has_decided_qc(pid, sid, t) for t in tasks_eff
			)
			mark = "✅" if done else "⬜"
			display_pid = pid if len(pid) <= _MAX_PID_DISPLAY_LEN else f"{pid[:_MAX_PID_DISPLAY_LEN - 3]}..."
			label_core = f"{display_pid} · {sid}" if sid is not None else display_pid
			suffix = " — current" if page_num == current_page else ""
			label = f"{mark} {label_core}{suffix}"
			if st.button(label, key=f"sidebar_cohort_nav_{i}", width="stretch"):
				SessionManager.set_current_page(page_num)
				if SessionManager.is_autoplay_enabled():
					SessionManager.set_autoplay_start_time(time.time())
				if entrypoint_rel_path:
					st.switch_page(entrypoint_rel_path)
				else:
					st.rerun()
		if kw:
			st.divider()
			_display_qc_pagination_controls(**kw)
