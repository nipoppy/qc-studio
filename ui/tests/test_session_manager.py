"""Unit tests for SessionManager."""
import pytest
import streamlit as st
from unittest.mock import MagicMock, patch
from managers.session_manager import SessionManager
from constants import SESSION_KEYS, DEFAULT_PANELS


@pytest.fixture
def mock_session_state():
    """Fixture to mock streamlit session state."""
    with patch.object(st, 'session_state', new_callable=lambda: MagicMock(spec=dict)) as mock_state:
        # Make it behave like a dict
        mock_state.__getitem__ = MagicMock(side_effect=lambda key: mock_state.get(key, None))
        mock_state.__setitem__ = MagicMock(side_effect=lambda key, value: mock_state.update({key: value}))
        mock_state.get = MagicMock(side_effect=lambda key, default=None: mock_state.data.get(key, default))
        mock_state.data = {}
        yield mock_state


class TestSessionManagerInit:
    """Tests for SessionManager initialization."""
    
    def test_init_session_state_creates_defaults(self, mock_session_state):
        """Test that init_session_state creates all default session variables."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        # Verify all keys are initialized
        assert SESSION_KEYS['current_page'] in st.session_state
        assert SESSION_KEYS['batch_size'] in st.session_state
        assert SESSION_KEYS['qc_records'] in st.session_state
        assert SESSION_KEYS['rater_id'] in st.session_state
        assert SESSION_KEYS['selected_panels'] in st.session_state
    
    def test_init_session_state_sets_correct_defaults(self, mock_session_state):
        """Test that init_session_state sets correct default values."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        assert st.session_state[SESSION_KEYS['current_page']] == 1
        assert st.session_state[SESSION_KEYS['batch_size']] == 1
        assert st.session_state[SESSION_KEYS['qc_records']] == []
        assert st.session_state[SESSION_KEYS['rater_id']] == ''
        assert st.session_state[SESSION_KEYS['landing_page_complete']] is False


class TestRaterMethods:
    """Tests for rater information methods."""
    
    def test_set_and_get_rater_id(self, mock_session_state):
        """Test setting and getting rater ID."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        SessionManager.set_rater_id('test_rater')
        assert SessionManager.get_rater_id() == 'test_rater'
    
    def test_set_and_get_rater_experience(self, mock_session_state):
        """Test setting and getting rater experience level."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        exp_level = "Expert (>5 year experience)"
        SessionManager.set_rater_experience(exp_level)
        assert SessionManager.get_rater_experience() == exp_level
    
    def test_set_and_get_rater_fatigue(self, mock_session_state):
        """Test setting and getting rater fatigue level."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        fatigue_level = "Very tired ☕☕"
        SessionManager.set_rater_fatigue(fatigue_level)
        assert SessionManager.get_rater_fatigue() == fatigue_level
    
    def test_get_rater_id_default_empty_string(self, mock_session_state):
        """Test that get_rater_id returns empty string when not set."""
        st.session_state = mock_session_state.data
        assert SessionManager.get_rater_id() == ''


class TestPanelMethods:
    """Tests for panel selection methods."""
    
    def test_get_selected_panels_default(self, mock_session_state):
        """Test that get_selected_panels returns default panels."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        panels = SessionManager.get_selected_panels()
        # Verify structure contains expected keys
        assert isinstance(panels, dict)
        # Should have panel configuration
        assert panels is not None
    
    def test_set_panel_selection_with_dict(self, mock_session_state):
        """Test setting multiple panel selections at once."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        new_panels = {'niivue': True, 'svg': False, 'iqm': True}
        SessionManager.set_panel_selection(new_panels)
        
        result = SessionManager.get_selected_panels()
        assert result == new_panels
    
    def test_is_panel_selected(self, mock_session_state):
        """Test checking if a specific panel is selected."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        panels = {'niivue': True, 'svg': False, 'iqm': True}
        SessionManager.set_panel_selection(panels)
        
        assert SessionManager.is_panel_selected('niivue') is True
        assert SessionManager.is_panel_selected('svg') is False
        assert SessionManager.is_panel_selected('iqm') is True
    
    def test_get_panel_count(self, mock_session_state):
        """Test counting selected panels."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        panels = {'niivue': True, 'svg': False, 'iqm': True}
        SessionManager.set_panel_selection(panels)
        
        assert SessionManager.get_panel_count() == 2
    
    def test_get_panel_count_zero(self, mock_session_state):
        """Test panel count when no panels selected."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        panels = {'niivue': False, 'svg': False, 'iqm': False}
        SessionManager.set_panel_selection(panels)
        
        assert SessionManager.get_panel_count() == 0


class TestQCRecordsMethods:
    """Tests for QC records management."""
    
    def test_get_qc_records_default_empty(self, mock_session_state):
        """Test that get_qc_records returns empty list by default."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        records = SessionManager.get_qc_records()
        assert records == []
    
    def test_add_qc_record(self, mock_session_state):
        """Test adding a QC record."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        # Create a mock record object
        mock_record = MagicMock()
        mock_record.participant_id = 'sub-01'
        
        SessionManager.add_qc_record(mock_record)
        records = SessionManager.get_qc_records()
        
        assert len(records) == 1
        assert records[0].participant_id == 'sub-01'
    
    def test_set_qc_records(self, mock_session_state):
        """Test setting multiple QC records at once."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        mock_records = [MagicMock(), MagicMock(), MagicMock()]
        SessionManager.set_qc_records(mock_records)
        
        records = SessionManager.get_qc_records()
        assert len(records) == 3
        assert records == mock_records
    
    def test_get_qc_record_count(self, mock_session_state):
        """Test getting count of QC records."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        mock_records = [MagicMock(), MagicMock()]
        SessionManager.set_qc_records(mock_records)
        
        assert SessionManager.get_qc_record_count() == 2


class TestNotesMethods:
    """Tests for notes management."""
    
    def test_set_and_get_notes(self, mock_session_state):
        """Test setting and getting notes."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        test_notes = "This is a test note"
        SessionManager.set_notes(test_notes)
        
        assert SessionManager.get_notes() == test_notes
    
    def test_get_notes_default_empty(self, mock_session_state):
        """Test that get_notes returns empty string by default."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        assert SessionManager.get_notes() == ''


class TestLandingPageMethods:
    """Tests for landing page state management."""
    
    def test_set_and_check_landing_page_complete(self, mock_session_state):
        """Test setting and checking landing page completion."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        assert SessionManager.is_landing_page_complete() is False
        
        SessionManager.set_landing_page_complete(True)
        assert SessionManager.is_landing_page_complete() is True


class TestPaginationMethods:
    """Tests for pagination methods."""
    
    def test_get_current_page_default(self, mock_session_state):
        """Test that get_current_page returns 1 by default."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        assert SessionManager.get_current_page() == 1
    
    def test_set_current_page(self, mock_session_state):
        """Test setting current page."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        SessionManager.set_current_page(5)
        assert SessionManager.get_current_page() == 5
    
    def test_next_page(self, mock_session_state):
        """Test advancing to next page."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        SessionManager.set_current_page(3)
        SessionManager.next_page()
        assert SessionManager.get_current_page() == 4
    
    def test_previous_page(self, mock_session_state):
        """Test going to previous page."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        SessionManager.set_current_page(3)
        SessionManager.previous_page()
        assert SessionManager.get_current_page() == 2
    
    def test_get_batch_size_default(self, mock_session_state):
        """Test that get_batch_size returns 1 by default."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        assert SessionManager.get_batch_size() == 1
    
    def test_set_batch_size(self, mock_session_state):
        """Test setting batch size."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        SessionManager.set_batch_size(5)
        assert SessionManager.get_batch_size() == 5


class TestSessionManagerIntegration:
    """Integration tests for multiple SessionManager operations."""
    
    def test_complete_workflow(self, mock_session_state):
        """Test a complete workflow of session management."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()
        
        # Rater setup
        SessionManager.set_rater_id('rater_001')
        SessionManager.set_rater_experience('Expert (>5 year experience)')
        SessionManager.set_rater_fatigue('A bit tired ☕')
        
        # Panel selection
        panels = {'niivue': True, 'svg': True, 'iqm': False}
        SessionManager.set_panel_selection(panels)
        
        # Complete landing page
        SessionManager.set_landing_page_complete(True)
        
        # Add QC records
        mock_records = [MagicMock(), MagicMock()]
        SessionManager.set_qc_records(mock_records)
        
        # Verify all state
        assert SessionManager.get_rater_id() == 'rater_001'
        assert SessionManager.is_landing_page_complete() is True
        assert SessionManager.get_panel_count() == 2
        assert SessionManager.get_qc_record_count() == 2


class TestTaskAwareRecordLookup:
    """Tests for task-aware participant/session record lookup."""

    def test_lookup_filters_by_qc_task(self, mock_session_state):
        """Lookup should return the matching task record when tasks share the same session."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()

        rec_task_a = {
            'participant_id': 'sub-ED01',
            'session_id': 'ses-01',
            'qc_task': 'anat_wf_qc',
            'final_qc': 'PASS',
        }
        rec_task_b = {
            'participant_id': 'sub-ED01',
            'session_id': 'ses-01',
            'qc_task': 'func_wf_qc',
            'final_qc': 'FAIL',
        }
        SessionManager.set_qc_records([rec_task_a, rec_task_b])

        record = SessionManager.get_qc_record_for_participant('sub-ED01', 'ses-01', 'anat_wf_qc')
        assert record is not None
        assert record.get('qc_task') == 'anat_wf_qc'
        assert record.get('final_qc') == 'PASS'

    def test_lookup_without_qc_task_keeps_backwards_compat(self, mock_session_state):
        """Lookup without task should still return the latest matching record."""
        st.session_state = mock_session_state.data
        SessionManager.init_session_state()

        older_record = {'participant_id': 'sub-ED02', 'session_id': 'ses-01', 'qc_task': 'anat_wf_qc'}
        newer_record = {'participant_id': 'sub-ED02', 'session_id': 'ses-01', 'qc_task': 'func_wf_qc'}
        SessionManager.set_qc_records([older_record, newer_record])

        record = SessionManager.get_qc_record_for_participant('sub-ED02', 'ses-01')
        assert record is not None
        assert record.get('qc_task') == 'func_wf_qc'
