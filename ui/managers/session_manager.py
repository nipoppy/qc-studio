"""Session state management for QC-Studio UI."""
import streamlit as st
from constants import DEFAULT_PANELS, SESSION_KEYS, DEFAULT_MONTAGE_MAX_ROWS, DEFAULT_MONTAGE_MAX_COLS


class SessionManager:
    """Manages session state access with type safety and defaults."""
    
    @staticmethod
    def init_session_state():
        """Initialize all required session state variables."""
        defaults = {
            SESSION_KEYS['current_page']: 1,
            SESSION_KEYS['batch_size']: 1,
            SESSION_KEYS['qc_records']: [],
            SESSION_KEYS['rater_id']: '',
            SESSION_KEYS['rater_experience']: None,
            SESSION_KEYS['rater_fatigue']: None,
            SESSION_KEYS['notes']: '',
            SESSION_KEYS['notes_version']: 0,
            SESSION_KEYS['rating_version']: 0,
            SESSION_KEYS['participant_order']: [],
            SESSION_KEYS['landing_page_complete']: False,
            SESSION_KEYS['selected_panels']: DEFAULT_PANELS.copy(),
            SESSION_KEYS['montage_max_rows']: DEFAULT_MONTAGE_MAX_ROWS,
            SESSION_KEYS['montage_max_cols']: DEFAULT_MONTAGE_MAX_COLS,
            'autoplay_enabled': False,
            'autoplay_start_time': 0.0,
            'autoplay_duration': 5
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    # Rater Information Methods
    @staticmethod
    def get_rater_id() -> str:
        """Get current rater ID."""
        return st.session_state.get(SESSION_KEYS['rater_id'], '')
    
    @staticmethod
    def set_rater_id(rater_id: str):
        """Set rater ID."""
        st.session_state[SESSION_KEYS['rater_id']] = rater_id
    
    @staticmethod
    def get_rater_experience() -> str:
        """Get current rater experience level."""
        return st.session_state.get(SESSION_KEYS['rater_experience'], '')
    
    @staticmethod
    def set_rater_experience(experience: str):
        """Set rater experience level."""
        st.session_state[SESSION_KEYS['rater_experience']] = experience
    
    @staticmethod
    def get_rater_fatigue() -> str:
        """Get current rater fatigue level."""
        return st.session_state.get(SESSION_KEYS['rater_fatigue'], '')
    
    @staticmethod
    def set_rater_fatigue(fatigue: str):
        """Set rater fatigue level."""
        st.session_state[SESSION_KEYS['rater_fatigue']] = fatigue
    
    # Panel Selection Methods
    @staticmethod
    def get_selected_panels() -> dict:
        """Get selected panels configuration."""
        if SESSION_KEYS['selected_panels'] not in st.session_state:
            st.session_state[SESSION_KEYS['selected_panels']] = DEFAULT_PANELS.copy()
        return st.session_state[SESSION_KEYS['selected_panels']]
    
    @staticmethod
    def set_panel_selection(panels_data):
        """Set panel selections.
        
        Args:
            panels_data: Either a dict of {panel_key: bool} or a single panel name (str) with next param as bool.
                        If dict, replaces all panel selections.
                        For backward compatibility with single panel updates.
        """
        if isinstance(panels_data, dict):
            # Full panel dictionary provided
            st.session_state[SESSION_KEYS['selected_panels']] = panels_data
        else:
            # Assume it's a panel_key string; this is for single updates (backward compatibility)
            panels = SessionManager.get_selected_panels()
            panels[panels_data] = panels_data  # This shouldn't happen, but keeping for safety
            st.session_state[SESSION_KEYS['selected_panels']] = panels
    
    @staticmethod
    def get_panel_count() -> int:
        """Get count of selected panels."""
        panels = SessionManager.get_selected_panels()
        return sum(panels.values())
    
    @staticmethod
    def is_panel_selected(panel_key: str) -> bool:
        """Check if a specific panel is selected."""
        panels = SessionManager.get_selected_panels()
        return panels.get(panel_key, False)
    
    # QC Records Management
    @staticmethod
    def get_qc_records() -> list:
        """Get all QC records."""
        if SESSION_KEYS['qc_records'] not in st.session_state:
            st.session_state[SESSION_KEYS['qc_records']] = []
        return st.session_state[SESSION_KEYS['qc_records']]
    
    @staticmethod
    def add_qc_record(record):
        """Add a QC record to the session."""
        records = SessionManager.get_qc_records()
        records.append(record)
        st.session_state[SESSION_KEYS['qc_records']] = records
    
    @staticmethod
    def set_qc_records(records: list):
        """Replace all QC records."""
        st.session_state[SESSION_KEYS['qc_records']] = records
    
    @staticmethod
    def get_qc_record_count() -> int:
        """Get number of QC records."""
        return len(SessionManager.get_qc_records())
    
    # Notes Management
    @staticmethod
    def get_notes() -> str:
        """Get current notes."""
        return st.session_state.get(SESSION_KEYS['notes'], '')
    
    @staticmethod
    def set_notes(notes: str):
        """Set notes."""
        st.session_state[SESSION_KEYS['notes']] = notes
    
    # Landing Page Management
    @staticmethod
    def is_landing_page_complete() -> bool:
        """Check if landing page has been completed."""
        return st.session_state.get(SESSION_KEYS['landing_page_complete'], False)
    
    @staticmethod
    def set_landing_page_complete(complete: bool):
        """Set landing page completion status."""
        st.session_state[SESSION_KEYS['landing_page_complete']] = complete
    
    # Pagination Management
    @staticmethod
    def get_current_page() -> int:
        """Get current page number."""
        return st.session_state.get(SESSION_KEYS['current_page'], 1)
    
    @staticmethod
    def set_current_page(page: int):
        """Set current page number."""
        st.session_state[SESSION_KEYS['current_page']] = page
        SessionManager.reset_for_new_participant()
    
    @staticmethod
    def next_page():
        """Move to next page."""
        st.session_state[SESSION_KEYS['current_page']] += 1
        SessionManager.reset_for_new_participant()
    
    @staticmethod
    def previous_page():
        """Move to previous page."""
        st.session_state[SESSION_KEYS['current_page']] -= 1
        SessionManager.reset_for_new_participant()
    
    @staticmethod
    def get_batch_size() -> int:
        """Get batch size."""
        return st.session_state.get(SESSION_KEYS['batch_size'], 1)
    
    @staticmethod
    def set_batch_size(size: int):
        """Set batch size."""
        st.session_state[SESSION_KEYS['batch_size']] = size
    
    # Utility Methods
    @staticmethod
    def get_rater_summary() -> dict:
        """Get all rater information as a dict."""
        return {
            'rater_id': SessionManager.get_rater_id(),
            'experience': SessionManager.get_rater_experience(),
            'fatigue': SessionManager.get_rater_fatigue()
        }
    
    @staticmethod
    def get_notes_version() -> int:
        """Get the current notes widget version counter."""
        return st.session_state.get(SESSION_KEYS['notes_version'], 0)

    @staticmethod
    def get_rating_version() -> int:
        """Get the current qc_rating widget version counter."""
        return st.session_state.get(SESSION_KEYS['rating_version'], 0)

    @staticmethod
    def get_participant_ids() -> list:
        """Get the stored (optionally sorted) participant ID list."""
        return st.session_state.get(SESSION_KEYS['participant_order'], [])

    @staticmethod
    def set_participant_ids(ids: list):
        """Store the participant ID list (used to persist sort order after CSV upload)."""
        st.session_state[SESSION_KEYS['participant_order']] = ids

    @staticmethod
    def get_qc_record_for_participant(participant_id: str, session_id: str, qc_task: str = None):
        """Return the most recent QCRecord for a given participant/session/task, or None.
        
        Normalises sub-/ses- prefixes and leading zeros so that records saved
        during a session (e.g. sub-QPNNC000421 / ses-01) match records loaded
        from a CSV (e.g. QPNNC000421 / 1).
        """
        def _bare(val: str, prefix: str) -> str:
            val = str(val)
            if val.startswith(prefix):
                val = val[len(prefix):]
            return val.lstrip("0") or "0"

        bare_pid = _bare(participant_id, "sub-")
        bare_sid = _bare(session_id, "ses-")
        for record in reversed(SessionManager.get_qc_records()):
            rec_pid = record.participant_id if hasattr(record, 'participant_id') else record.get('participant_id', '')
            rec_sid = record.session_id if hasattr(record, 'session_id') else record.get('session_id', '')
            rec_task = record.qc_task if hasattr(record, 'qc_task') else record.get('qc_task', '')
            if qc_task is not None and str(rec_task) != str(qc_task):
                continue
            if _bare(str(rec_pid), "sub-") == bare_pid and _bare(str(rec_sid), "ses-") == bare_sid:
                return record
        return None

    @staticmethod
    def reset_for_new_participant():
        """Reset session state for next participant."""
        st.session_state[SESSION_KEYS['notes']] = ''
        st.session_state[SESSION_KEYS['notes_version']] = SessionManager.get_notes_version() + 1
        st.session_state[SESSION_KEYS['rating_version']] = SessionManager.get_rating_version() + 1
    
    # Montage Grid Settings Methods
    @staticmethod
    def get_montage_max_rows() -> int | None:
        """Get maximum rows for montage grid (None means auto-calculate)."""
        return st.session_state.get(SESSION_KEYS['montage_max_rows'], DEFAULT_MONTAGE_MAX_ROWS)
    
    @staticmethod
    def set_montage_max_rows(rows: int | None):
        """Set maximum rows for montage grid."""
        st.session_state[SESSION_KEYS['montage_max_rows']] = rows
    
    @staticmethod
    def get_montage_max_cols() -> int | None:
        """Get maximum columns for montage grid (None means auto-calculate)."""
        return st.session_state.get(SESSION_KEYS['montage_max_cols'], DEFAULT_MONTAGE_MAX_COLS)
    
    @staticmethod
    def set_montage_max_cols(cols: int | None):
        """Set maximum columns for montage grid."""
        st.session_state[SESSION_KEYS['montage_max_cols']] = cols
    
    # Autoplay Methods
    @staticmethod
    def is_autoplay_enabled() -> bool:
        """Check if autoplay is enabled."""
        return st.session_state.get('autoplay_enabled', False)
    
    @staticmethod
    def set_autoplay_enabled(enabled: bool):
        """Set autoplay state."""
        st.session_state['autoplay_enabled'] = enabled

    @staticmethod
    def get_autoplay_start_time() -> float:
        """Get the timestamp when the autoplay countdown started (0 = not running)."""
        return st.session_state.get('autoplay_start_time', 0.0)

    @staticmethod
    def set_autoplay_start_time(t: float):
        """Set the autoplay countdown start timestamp."""
        st.session_state['autoplay_start_time'] = t

    @staticmethod
    def get_autoplay_duration() -> int:
        """Get the autoplay countdown duration in seconds (2–10)."""
        return st.session_state.get('autoplay_duration', 5)

    @staticmethod
    def set_autoplay_duration(seconds: int):
        """Set the autoplay countdown duration in seconds (2–10)."""
        st.session_state['autoplay_duration'] = max(2, min(10, seconds))
