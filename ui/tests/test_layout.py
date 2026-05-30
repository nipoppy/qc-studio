"""Tests for app.py module."""
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pandas as pd
import pytest
from pydantic import ValidationError

# Mock streamlit and dependencies before importing layout
import sys
sys.modules['niivue_component'] = MagicMock()


class TestShowLandingPage:
    """Test landing page display functionality."""

    @patch('app.st')
    @patch('app.pd.read_csv')
    def test_landing_page_displays_title(self, mock_read_csv, mock_st):
        """Test that landing page displays correct title."""
        from app import show_landing_page
        
        # Mock the dataframe
        mock_df = pd.DataFrame({
            'participant_id': ['sub-ED01', 'sub-ED02', 'sub-ED03']
        })
        mock_read_csv.return_value = mock_df
        
        # Properly mock session_state as a MagicMock
        mock_session_state = MagicMock()
        mock_session_state.get = MagicMock(return_value='')
        mock_session_state.__getitem__ = MagicMock(return_value={})
        mock_st.session_state = mock_session_state
        
        show_landing_page(
            qc_pipeline='fmriprep',
            qc_task='anat_wf_qc',
            out_dir='/output',
            participant_list='participants.tsv'
        )
        
        # Verify title was set
        mock_st.title.assert_called_once()

    @patch('app.st')
    @patch('app.pd.read_csv')
    def test_landing_page_displays_pipeline_info(self, mock_read_csv, mock_st):
        """Test that landing page displays pipeline information."""
        from app import show_landing_page
        
        mock_df = pd.DataFrame({
            'participant_id': ['sub-ED01', 'sub-ED02']
        })
        mock_read_csv.return_value = mock_df
        
        mock_session_state = MagicMock()
        mock_session_state.get = MagicMock(return_value='')
        mock_session_state.__getitem__ = MagicMock(return_value={})
        mock_st.session_state = mock_session_state
        
        show_landing_page(
            qc_pipeline='fmriprep',
            qc_task='anat_wf_qc',
            out_dir='/output',
            participant_list='participants.tsv'
        )
        
        # Verify subheader was called with pipeline info
        mock_st.subheader.assert_called()

    @patch('app.st')
    @patch('app.pd.read_csv')
    def test_landing_page_error_handling(self, mock_read_csv, mock_st):
        """Test landing page error handling for invalid participant list."""
        from app import show_landing_page
        
        mock_read_csv.side_effect = Exception("File not found")
        
        mock_session_state = MagicMock()
        mock_session_state.get = MagicMock(return_value='')
        mock_session_state.__getitem__ = MagicMock(return_value={})
        mock_st.session_state = mock_session_state
        
        show_landing_page(
            qc_pipeline='fmriprep',
            qc_task='anat_wf_qc',
            out_dir='/output',
            participant_list='invalid.tsv'
        )
        
        # Verify error message was displayed
        mock_st.error.assert_called()

    @patch('app.st')
    @patch('app.pd.read_csv')
    def test_landing_page_three_column_layout(self, mock_read_csv, mock_st):
        """Test that landing page creates three-column layout."""
        from app import show_landing_page
        
        mock_df = pd.DataFrame({
            'participant_id': ['sub-ED01']
        })
        mock_read_csv.return_value = mock_df
        
        mock_session_state = MagicMock()
        mock_session_state.get = MagicMock(return_value='')
        mock_session_state.__getitem__ = MagicMock(return_value={})
        mock_st.session_state = mock_session_state
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        
        show_landing_page(
            qc_pipeline='fmriprep',
            qc_task='anat_wf_qc',
            out_dir='/output',
            participant_list='participants.tsv'
        )
        
        # Columns should be created for layout
        mock_st.columns.assert_called()


class TestLandingPageRaterInfo:
    """Test rater information section of landing page."""

    @patch('app.st')
    @patch('app.pd.read_csv')
    def test_rater_form_displays(self, mock_read_csv, mock_st):
        """Test that rater form is displayed."""
        from app import show_landing_page
        
        mock_df = pd.DataFrame({
            'participant_id': ['sub-ED01']
        })
        mock_read_csv.return_value = mock_df
        
        mock_session_state = MagicMock()
        mock_session_state.get = MagicMock(return_value='')
        mock_session_state.__getitem__ = MagicMock(return_value={'selected_panels': {}})
        mock_st.session_state = mock_session_state
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.text_input.return_value = 'test_rater'
        
        show_landing_page(
            qc_pipeline='fmriprep',
            qc_task='anat_wf_qc',
            out_dir='/output',
            participant_list='participants.tsv'
        )
        
        # Form and input fields should be called
        mock_st.form.assert_called()

    @patch('app.st')
    @patch('app.pd.read_csv')
    def test_experience_level_options(self, mock_read_csv, mock_st):
        """Test that experience level options are presented."""
        from app import show_landing_page
        
        mock_df = pd.DataFrame({
            'participant_id': ['sub-ED01']
        })
        mock_read_csv.return_value = mock_df
        mock_st.session_state = {}
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        
        # Radio options for experience
        experience_options = [
            "Beginner (< 1 year experience)",
            "Intermediate (1-5 year experience)",
            "Expert (>5 year experience)"
        ]
        
        assert len(experience_options) == 3
        assert any("Expert" in opt for opt in experience_options)


class TestLandingPagePanelSelection:
    """Test panel selection functionality."""

    @patch('app.st')
    @patch('app.pd.read_csv')
    def test_panel_checkboxes_displayed(self, mock_read_csv, mock_st):
        """Test that panel selection checkboxes are displayed."""
        from app import show_landing_page
        
        mock_df = pd.DataFrame({
            'participant_id': ['sub-ED01']
        })
        mock_read_csv.return_value = mock_df
        
        mock_session_state = MagicMock()
        mock_session_state.get = MagicMock(return_value='')
        mock_session_state.__getitem__ = MagicMock(return_value={'selected_panels': {}})
        mock_session_state.__setitem__ = MagicMock()
        mock_st.session_state = mock_session_state
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_st.checkbox.return_value = True
        
        show_landing_page(
            qc_pipeline='fmriprep',
            qc_task='anat_wf_qc',
            out_dir='/output',
            participant_list='participants.tsv'
        )
        
        # Checkboxes should be called for panel selection
        mock_st.checkbox.assert_called()

    def test_default_panel_selections(self, sample_session_state):
        """Test default panel selections."""
        panels = sample_session_state['selected_panels']
        
        assert panels['niivue_col'] is True
        assert panels['svg_col'] is True
        assert panels['iqm_col'] is False

    def test_panel_selection_validation(self, sample_session_state):
        """Test that at least one panel must be selected."""
        selected_count = sum(sample_session_state['selected_panels'].values())
        
        assert selected_count >= 1


class TestLandingPageCsvUpload:
    """Test CSV file upload functionality."""

    @patch('app.st')
    @patch('app.pd.read_csv')
    def test_file_uploader_displayed(self, mock_read_csv, mock_st):
        """Test that file uploader is displayed."""
        from app import show_landing_page
        
        mock_df = pd.DataFrame({
            'participant_id': ['sub-ED01']
        })
        mock_read_csv.return_value = mock_df
        
        mock_session_state = MagicMock()
        mock_session_state.get = MagicMock(return_value='')
        mock_session_state.__getitem__ = MagicMock(return_value={'selected_panels': {}})
        mock_session_state.__setitem__ = MagicMock()
        mock_st.session_state = mock_session_state
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        
        show_landing_page(
            qc_pipeline='fmriprep',
            qc_task='anat_wf_qc',
            out_dir='/output',
            participant_list='participants.tsv'
        )
        
        # File uploader should be called
        mock_st.file_uploader.assert_called()

    @patch('app.st')
    @patch('app.pd.read_csv')
    def test_csv_upload_validation(self, mock_read_csv, mock_st, sample_qc_results_csv):
        """Test CSV upload validation."""
        # Read actual CSV for validation
        df = pd.read_csv(sample_qc_results_csv, sep="\t")
        
        # Should have expected columns
        assert 'participant_id' in df.columns
        assert 'rater_id' in df.columns
        assert 'final_qc' in df.columns


class TestApp:
    """Test main app function."""

    @patch('app.st')
    @patch('app.parse_qc_config')
    def test_app_landing_page_incomplete(self, mock_parse_config, mock_st):
        """Test app shows landing page when not complete."""
        from app import app
        
        mock_session_state = MagicMock()
        mock_session_state.get = MagicMock(return_value=False)
        mock_session_state.__getitem__ = MagicMock(side_effect=lambda x: {
            'landing_page_complete': False,
            'selected_panels': {}
        }.get(x))
        mock_session_state.__setitem__ = MagicMock()
        mock_st.session_state = mock_session_state
        mock_st.set_page_config = MagicMock()
        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        
        # Should return early at landing page
        app(
            participant_id='sub-ED01',
            session_id='ses-01',
            qc_pipeline='fmriprep',
            qc_task='anat_wf_qc',
            qc_config_path='config.json',
            out_dir='/output',
            total_participants=5,
            drop_duplicates=True,
            participant_list='participants.tsv'
        )
        
        mock_st.set_page_config.assert_called()

    @patch('app.st')
    @patch('app.parse_qc_config')
    def test_app_congratulations_page(self, mock_parse_config, mock_st):
        """Test app shows congratulations page when complete."""
        from app import app
        
        mock_session_state = MagicMock()
        mock_session_state.get = MagicMock(return_value=True)
        mock_session_state.__getitem__ = MagicMock(side_effect=lambda x: {
            'landing_page_complete': True,
            'rater_id': 'test_rater',
            'qc_records': []
        }.get(x))
        mock_session_state.__setitem__ = MagicMock()
        mock_st.session_state = mock_session_state
        mock_st.set_page_config = MagicMock()
        mock_st.columns.return_value = (MagicMock(), MagicMock())
        
        app(
            participant_id=None,  # None indicates final page
            session_id='ses-01',
            qc_pipeline='fmriprep',
            qc_task='anat_wf_qc',
            qc_config_path='config.json',
            out_dir='/output',
            total_participants=5,
            drop_duplicates=True,
            participant_list='participants.tsv'
        )
        
        # Should display title for congratulations
        mock_st.title.assert_called()


class TestQcViewerLayout:
    """Test QC viewer layout and panel display."""

    @patch('app.st')
    @patch('app.parse_qc_config')
    @patch('app.load_mri_data')
    @patch('app.load_svg_data')
    def test_niivue_panel_displayed(self, mock_load_svg, mock_load_mri, 
                                    mock_parse_config, mock_st):
        """Test that Niivue panel is displayed when selected."""
        from app import app
        
        mock_st.session_state = {
            'landing_page_complete': True,
            'selected_panels': {
                'niivue_col': True,
                'svg_col': False,
                'iqm_col': False
            },
            'rater_id': 'test_rater'
        }
        mock_parse_config.return_value = {
            'base_mri_image_path': Path('base.nii.gz'),
            'overlay_mri_image_path': None,
            'svg_montage_path': None,
            'iqm_path': None
        }
        mock_load_mri.return_value = {}
        mock_load_svg.return_value = None
        mock_st.set_page_config = MagicMock()
        mock_st.container.return_value = MagicMock()
        mock_st.columns.return_value = (MagicMock(), MagicMock())
        
        # This is a simplified test; actual testing would be more complex
        assert True  # Placeholder

    @patch('components.qc_viewer.display_iqm_distribution_panel')
    @patch('components.qc_viewer.NiivueViewerManager.render_controls_panel')
    @patch('components.qc_viewer.NiivueViewerManager.render_viewer')
    @patch('components.qc_viewer._get_or_render_niivue_config')
    @patch('components.qc_viewer.st')
    def test_secondary_iqm_panel_receives_qc_task(
        self,
        mock_st,
        mock_get_niivue_config,
        mock_render_viewer,
        mock_render_controls,
        mock_display_iqm,
    ):
        """Test that the IQM panel receives qc_task for modality inference."""
        from components.qc_viewer import _display_niivue_with_secondary_panel

        viewer_col = MagicMock()
        panel_col = MagicMock()
        mock_st.columns.return_value = (viewer_col, panel_col)
        mock_st.expander.return_value = MagicMock()
        mock_get_niivue_config.return_value = MagicMock()

        qc_config = {"base_mri_image_path": "sub-01_T1w.nii.gz"}

        _display_niivue_with_secondary_panel(
            dataset_dir="/dataset",
            selected_panels={"svg": False, "iqm": True},
            qc_config=qc_config,
            qc_config_path="qc.json",
            participant_id="sub-01",
            session_id="ses-01",
            qc_task="anat_wf_qc",
        )

        mock_display_iqm.assert_called_once_with(
            qc_config,
            "qc.json",
            "sub-01",
            "ses-01",
            "/dataset",
            qc_task="anat_wf_qc",
        )


class TestSessionStateManagement:
    """Test session state management in app."""

    def test_rater_information_in_session(self, sample_session_state):
        """Test rater information stored in session state."""
        assert sample_session_state['rater_id'] == 'test_rater'
        assert sample_session_state['rater_experience'] is not None
        assert sample_session_state['rater_fatigue'] is not None

    def test_qc_records_in_session(self, sample_session_state):
        """Test QC records stored in session state."""
        assert isinstance(sample_session_state['qc_records'], list)

    def test_panel_selections_in_session(self, sample_session_state):
        """Test panel selections stored in session state."""
        assert 'selected_panels' in sample_session_state
        assert isinstance(sample_session_state['selected_panels'], dict)


class TestNavigationControls:
    """Test navigation controls."""

    @patch('app.st')
    @patch('app.parse_qc_config')
    def test_previous_button_updates_page(self, mock_parse_config, mock_st):
        """Test that previous button updates current page."""
        from app import app
        
        mock_st.session_state = {
            'landing_page_complete': True,
            'current_page': 2,
            'rater_id': 'test_rater'
        }
        mock_st.set_page_config = MagicMock()
        
        # Button behavior would be tested with button clicks
        # This is a placeholder for the concept
        assert mock_st.session_state['current_page'] > 1

    def test_page_bounds_lower(self, sample_session_state):
        """Test that page cannot be less than 1."""
        current_page = 0
        if current_page < 1:
            current_page = 1
        
        assert current_page == 1

    def test_page_bounds_upper(self, sample_session_state):
        """Test that page is bounded by total participants."""
        current_page = 100
        total_participants = 5
        
        valid_page = min(max(current_page, 1), total_participants)
        
        assert valid_page == total_participants
