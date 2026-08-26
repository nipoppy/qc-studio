"""Multipage sidebar: one control per subject with QC-done marker (Streamlit app sidebar)."""

import time

import streamlit as st

from constants import (
    MESSAGES,
    PENDING_SIDEBAR_RERUN_KEY,
    SESSION_KEYS,
    SIDEBAR_SEARCH_HOLD_KEY,
    SIDEBAR_SUBJECT_LIST_HEIGHT,
    SIDEBAR_SUBJECT_SEARCH_WIDGET_KEY,
)
from managers.session_manager import SessionManager

_MAX_PID_DISPLAY_LEN = 28
_SUBJECT_SEARCH_WIDGET_KEY = SIDEBAR_SUBJECT_SEARCH_WIDGET_KEY
_NAV_BUTTON_KEYS = ("pag_next", "pag_prev", "pag_confirm", "autoplay_play", "autoplay_pause")
_LAST_APPLIED_FILTER_KEY = "_sidebar_search_applied_query"


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
    """Add sidebar QC navigation, then a scrollable subject list.

    When ``prepend_navigation`` is True and ``navigation_kwargs`` is set, order is:
    **Navigation** / Page X of Y, Play/Pause, prev–confirm–next / save, then Subjects
    with the filter box directly above the scrollable list. The search widget is
    *created* before those buttons so Streamlit does not reset the filter; it is
    then placed visually above the subject scroller.

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

        # Search is instantiated before Play/Previous/Next so Streamlit does not
        # blank it. JS then places the box immediately above the subject scroller.
        query = _render_subject_search()
        snap_to = _page_after_filter_change(entries, query, session_id, SessionManager.get_current_page())
        if snap_to is not None:
            SessionManager.set_current_page(snap_to)
            st.rerun()
        if kw:
            _display_qc_pagination_controls(**kw)
            st.divider()
        _render_subject_list(
            entries=entries,
            session_id=session_id,
            tasks_eff=tasks_eff,
            entrypoint_rel_path=entrypoint_rel_path,
            query=query,
        )
        if st.session_state.get(PENDING_SIDEBAR_RERUN_KEY):
            del st.session_state[PENDING_SIDEBAR_RERUN_KEY]
            st.rerun()
        elif st.session_state.get(SIDEBAR_SEARCH_HOLD_KEY):
            del st.session_state[SIDEBAR_SEARCH_HOLD_KEY]


def get_subject_search_query() -> str:
    """Return the persisted subject-list filter (not the raw widget, which nav can blank)."""
    return str(st.session_state.get(SESSION_KEYS["sidebar_subject_search"], "") or "").strip()


def clear_subject_search() -> None:
    """Clear the subject filter."""
    st.session_state[SESSION_KEYS["sidebar_subject_search"]] = ""
    st.session_state[_SUBJECT_SEARCH_WIDGET_KEY] = ""
    st.session_state.pop(SIDEBAR_SEARCH_HOLD_KEY, None)
    st.session_state.pop(_LAST_APPLIED_FILTER_KEY, None)


def _nav_triggered() -> bool:
    return any(st.session_state.get(key) for key in _NAV_BUTTON_KEYS)


def _hold_search_across_nav() -> None:
    """Keep the filter when Previous/Next/Confirm blank the search widget."""
    persist = str(st.session_state.get(SESSION_KEYS["sidebar_subject_search"], "") or "")
    if _nav_triggered() or st.session_state.get(PENDING_SIDEBAR_RERUN_KEY):
        st.session_state[SIDEBAR_SEARCH_HOLD_KEY] = True
    if st.session_state.get(SIDEBAR_SEARCH_HOLD_KEY):
        st.session_state[_SUBJECT_SEARCH_WIDGET_KEY] = persist


def _enable_live_subject_search() -> None:
    """Commit the search box on each keystroke and keep it above the subject list."""
    st.components.v1.html(
        """
        <script>
        (function() {
          const doc = window.parent.document;
          const placeholder = "Filter by subject or session";
          const placeSearchAboveList = () => {
            const inputWrap = doc.querySelector(".st-key-sidebar_subject_search_input");
            const listBtn = doc.querySelector('[class*="st-key-sidebar_cohort_nav_"]');
            if (!inputWrap || !listBtn) return;
            const listWrap = listBtn.closest('[data-testid="stLayoutWrapper"]');
            if (!listWrap || !listWrap.parentNode) return;
            const nodes = [];
            const prev = inputWrap.previousElementSibling;
            if (prev && prev.querySelector('[data-testid="stCaption"]')) nodes.push(prev);
            nodes.push(inputWrap);
            const after = inputWrap.nextElementSibling;
            if (after && after.querySelector("iframe")) nodes.push(after);
            const last = nodes[nodes.length - 1];
            if (last.nextElementSibling === listWrap) return;
            nodes.forEach((node) => listWrap.parentNode.insertBefore(node, listWrap));
          };
          const bind = () => {
            placeSearchAboveList();
            const el = Array.from(doc.querySelectorAll("input")).find(
              (n) => n.getAttribute("placeholder") === placeholder
            );
            if (!el || el.dataset.qcLiveFilter === "1") return;
            el.dataset.qcLiveFilter = "1";
            let timer = null;
            el.addEventListener("input", () => {
              window.clearTimeout(timer);
              timer = window.setTimeout(() => {
                const start = el.selectionStart;
                const end = el.selectionEnd;
                el.blur();
                el.focus();
                try { el.setSelectionRange(start, end); } catch (err) {}
              }, 80);
            });
          };
          bind();
          new MutationObserver(bind).observe(doc.body, { childList: true, subtree: true });
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def _matching_subject_entries(entries: list, query: str, session_id: str) -> list[tuple[int, dict]]:
    """Return ``(original_index, entry)`` pairs whose subject or session contains ``query``."""
    needle = (query or "").strip().lower()
    matched: list[tuple[int, dict]] = []
    for i, entry in enumerate(entries):
        pid = str(entry.get("participant_id", ""))
        sid = str(entry.get("session_id", session_id))
        haystack = f"{pid} {sid}".lower()
        if not needle or needle in haystack:
            matched.append((i, entry))
    return matched


def matching_page_numbers(entries: list, query: str, session_id: str) -> list[int]:
    """1-based page numbers that match the current subject filter."""
    return [i + 1 for i, _ in _matching_subject_entries(entries, query, session_id)]


def next_visible_subject_page(entries: list, query: str, session_id: str, current_page: int) -> int | None:
    """Next 1-based page among filter matches, or ``None`` if this is the last match."""
    for page in matching_page_numbers(entries, query, session_id):
        if page > current_page:
            return page
    return None


def prev_visible_subject_page(entries: list, query: str, session_id: str, current_page: int) -> int | None:
    """Previous 1-based page among filter matches, or ``None`` if this is the first match."""
    previous = None
    for page in matching_page_numbers(entries, query, session_id):
        if page < current_page:
            previous = page
        else:
            break
    return previous


def page_if_filter_hides_current(entries: list, query: str, session_id: str, current_page: int) -> int | None:
    """First matching page if ``current_page`` is hidden by the filter; otherwise ``None``."""
    if current_page < 1 or current_page > len(entries):
        return None
    pages = matching_page_numbers(entries, query, session_id)
    if not pages or current_page in pages:
        return None
    return pages[0]


def first_visible_subject_page(entries: list, query: str, session_id: str) -> int | None:
    """1-based page of the first filter match, or ``None`` if nothing matches."""
    pages = matching_page_numbers(entries, query, session_id)
    return pages[0] if pages else None


def _page_after_filter_change(entries: list, query: str, session_id: str, current_page: int) -> int | None:
    """When the filter changes, go to the first visible subject (or if the current page is hidden)."""
    query = (query or "").strip()
    previous = st.session_state.get(_LAST_APPLIED_FILTER_KEY)
    st.session_state[_LAST_APPLIED_FILTER_KEY] = query
    first = first_visible_subject_page(entries, query, session_id)
    if query and previous != query and first is not None and first != current_page:
        return first
    return page_if_filter_hides_current(entries, query, session_id, current_page)


def _render_subject_search() -> str:
    """Create the subject filter before any nav buttons and persist its value."""
    st.caption(MESSAGES["sidebar_subjects_header"])
    _hold_search_across_nav()
    query = st.text_input(
        MESSAGES["sidebar_subjects_search"],
        key=_SUBJECT_SEARCH_WIDGET_KEY,
        placeholder=MESSAGES["sidebar_subjects_search_placeholder"],
        label_visibility="collapsed",
    )
    _enable_live_subject_search()
    query = "" if query is None else str(query)
    if st.session_state.get(SIDEBAR_SEARCH_HOLD_KEY):
        query = str(st.session_state.get(SESSION_KEYS["sidebar_subject_search"], "") or "")
    else:
        st.session_state[SESSION_KEYS["sidebar_subject_search"]] = query
    return query


def _render_subject_list(
    *,
    entries: list,
    session_id: str,
    tasks_eff: list,
    entrypoint_rel_path: str | None,
    query: str,
) -> None:
    """Render the cohort subject buttons inside a fixed-height scroller."""
    visible = _matching_subject_entries(entries, query, session_id)
    current_page = SessionManager.get_current_page()
    with st.container(height=SIDEBAR_SUBJECT_LIST_HEIGHT, border=True):
        if not visible:
            st.caption(MESSAGES["sidebar_subjects_search_empty"])
            return
        for i, entry in visible:
            page_num = i + 1
            pid = str(entry.get("participant_id", ""))
            sid = str(entry.get("session_id", session_id))
            done = all(SessionManager.participant_has_decided_qc(pid, sid, t) for t in tasks_eff)
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
