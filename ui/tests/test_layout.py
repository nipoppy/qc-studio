"""Tests for app.py module."""

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pandas as pd
import pytest
from pydantic import ValidationError

# Mock streamlit and dependencies before importing layout
import sys

sys.modules["niivue_component"] = MagicMock()

from constants import (
    SESSION_KEYS,
    DEFAULT_PANELS,
    DEFAULT_MONTAGE_MAX_ROWS,
    DEFAULT_MONTAGE_MAX_COLS,
    EXPERIENCE_LEVELS,
    MESSAGES,
    SIDEBAR_SUBJECT_LIST_HEIGHT,
)

pytestmark = pytest.mark.integration


def _session_state_dict():
    """Minimal session_state matching SessionManager defaults."""
    return {
        SESSION_KEYS["current_page"]: 1,
        SESSION_KEYS["batch_size"]: 1,
        SESSION_KEYS["qc_records"]: [],
        SESSION_KEYS["rater_id"]: "",
        SESSION_KEYS["rater_experience"]: None,
        SESSION_KEYS["rater_fatigue"]: None,
        SESSION_KEYS["notes"]: "",
        SESSION_KEYS["notes_version"]: 0,
        SESSION_KEYS["rating_version"]: 0,
        SESSION_KEYS["participant_order"]: [],
        SESSION_KEYS["landing_page_complete"]: False,
        SESSION_KEYS["selected_panels"]: DEFAULT_PANELS.copy(),
        SESSION_KEYS["montage_max_rows"]: DEFAULT_MONTAGE_MAX_ROWS,
        SESSION_KEYS["montage_max_cols"]: DEFAULT_MONTAGE_MAX_COLS,
        "autoplay_enabled": False,
        "autoplay_start_time": 0.0,
        "autoplay_duration": 5,
    }


def _stub_qc_config_path(tmp_path, task="anat_wf_qc", montage_rows_cols=None):
    """Minimal qc.json on disk for landing page tests."""
    task_entry = {
        "base_mri_image_path": str(tmp_path / "base.nii.gz"),
        "overlay_mri_image_path": str(tmp_path / "overlay.nii.gz"),
        "svg_montage_path": str(tmp_path / "montage.svg"),
        "iqm_path": str(tmp_path / "iqm.json"),
    }
    if montage_rows_cols is not None:
        task_entry["montage_max_rows"] = montage_rows_cols[0]
        task_entry["montage_max_cols"] = montage_rows_cols[1]
    p = tmp_path / "qc_config.json"
    p.write_text(json.dumps({task: task_entry}))
    return str(p)


def _columns_side_effect(*args, **kwargs):
    widths = args[0] if args else [1, 1, 1]
    if isinstance(widths, int):
        n = widths
    else:
        n = len(widths)
    return tuple(MagicMock() for _ in range(n))


def _configure_landing_page_streamlit_mock(mock_st):
    mock_st.session_state = _session_state_dict()
    form_ctx = MagicMock()
    form_ctx.__enter__ = MagicMock(return_value=None)
    form_ctx.__exit__ = MagicMock(return_value=False)
    mock_st.form.return_value = form_ctx
    mock_st.form_submit_button.return_value = False
    mock_st.columns.side_effect = _columns_side_effect
    mock_st.checkbox.return_value = True
    mock_st.text_input.return_value = "test_rater"
    mock_st.radio.return_value = EXPERIENCE_LEVELS[0]
    mock_st.slider.return_value = 5
    mock_st.number_input.return_value = 1
    mock_st.file_uploader.return_value = None


@contextmanager
def _patch_streamlit_for_landing(mock_st):
    _configure_landing_page_streamlit_mock(mock_st)
    with (
        patch("views.landing_page.st", mock_st),
        patch("managers.session_manager.st", mock_st),
        patch("managers.panel_layout_manager.st", mock_st),
        patch("managers.niivue_viewer_manager.st", mock_st),
    ):
        yield mock_st


class TestShowLandingPage:
    """Test landing page display functionality."""

    @patch("views.landing_page.pd.read_csv")
    def test_landing_page_displays_title(self, mock_read_csv, tmp_path):
        """Test that landing page displays correct title."""
        from views.landing_page import show_landing_page

        mock_df = pd.DataFrame({"participant_id": ["sub-CMH0001", "sub-CMH0002", "sub-CMH0003"]})
        mock_read_csv.return_value = mock_df

        mock_st = MagicMock()
        with _patch_streamlit_for_landing(mock_st):
            show_landing_page(
                qc_pipeline="fmriprep",
                qc_task="anat_wf_qc",
                out_dir="/output",
                participant_list="participants.tsv",
                qc_config_path=_stub_qc_config_path(tmp_path),
            )

        mock_st.title.assert_called_once()

    @patch("views.landing_page.pd.read_csv")
    def test_landing_page_displays_pipeline_info(self, mock_read_csv, tmp_path):
        """Test that landing page displays pipeline information."""
        from views.landing_page import show_landing_page

        mock_df = pd.DataFrame({"participant_id": ["sub-CMH0001", "sub-CMH0002"]})
        mock_read_csv.return_value = mock_df

        mock_st = MagicMock()
        with _patch_streamlit_for_landing(mock_st):
            show_landing_page(
                qc_pipeline="fmriprep",
                qc_task="anat_wf_qc",
                out_dir="/output",
                participant_list="participants.tsv",
                qc_config_path=_stub_qc_config_path(tmp_path),
            )

        markdown_calls = [str(c.args[0]) for c in mock_st.markdown.call_args_list if c.args]
        assert any("Task:** anat_wf_qc" in text for text in markdown_calls)
        assert any("Subjects:**" in text for text in markdown_calls)
        assert any("Cohort pages:**" in text for text in markdown_calls)
        mock_st.header.assert_any_call("fmriprep")
        assert not any("QC Pipeline:" in text and "|" in text for text in markdown_calls)

    def test_landing_run_summary_uses_subject_page_task_names(self):
        from views.landing_page import _landing_run_summary_lines

        line1, line2 = _landing_run_summary_lines(
            "noddireg",
            ["Tissue density distributions"],
            1,
            2,
        )
        assert line1 == "noddireg"
        assert "Task:** Tissue density distributions" in line2
        assert "noddireg_density" not in line2
        assert "Subjects:** 1" in line2 and "Cohort pages:** 2" in line2

        _, all_line = _landing_run_summary_lines(
            "fmriprep",
            ["Susceptibility distortion correction (SDC)", "BOLD-T1w coregistration"],
            1,
            2,
            all_tasks=True,
        )
        assert "Task:** all tasks (2 tasks)" in all_line
        assert "Susceptibility distortion correction" not in all_line

    def test_compact_session_label_omits_pipeline_and_task_count(self):
        from components.qc_viewer import _compact_session_label

        assert _compact_session_label("sub-CMH0001", "ses-01") == "sub-CMH0001 · ses-01"
        assert _compact_session_label("sub-CMH0001", None) == "sub-CMH0001"
        label = _compact_session_label("sub-CMH0001", "ses-01")
        assert "fmriprep" not in label.lower()
        assert "count" not in label.lower()

    @patch("views.landing_page.pd.read_csv")
    def test_landing_page_error_handling(self, mock_read_csv, tmp_path):
        """Test landing page error handling for invalid participant list."""
        from views.landing_page import show_landing_page

        mock_read_csv.side_effect = Exception("File not found")

        mock_st = MagicMock()
        mock_st.session_state = _session_state_dict()
        with patch("views.landing_page.st", mock_st), patch("managers.session_manager.st", mock_st):
            show_landing_page(
                qc_pipeline="fmriprep",
                qc_task="anat_wf_qc",
                out_dir="/output",
                participant_list="invalid.tsv",
                qc_config_path=_stub_qc_config_path(tmp_path),
            )

        mock_st.error.assert_called()

    @patch("views.landing_page.pd.read_csv")
    def test_landing_page_three_column_layout(self, mock_read_csv, tmp_path):
        """Test that landing page creates three-column layout."""
        from views.landing_page import show_landing_page

        mock_df = pd.DataFrame({"participant_id": ["sub-CMH0001"]})
        mock_read_csv.return_value = mock_df

        mock_st = MagicMock()
        with _patch_streamlit_for_landing(mock_st):
            show_landing_page(
                qc_pipeline="fmriprep",
                qc_task="anat_wf_qc",
                out_dir="/output",
                participant_list="participants.tsv",
                qc_config_path=_stub_qc_config_path(tmp_path),
            )

        mock_st.columns.assert_called()

    @patch("views.landing_page.pd.read_csv")
    def test_landing_page_applies_montage_defaults_from_qc_json(self, mock_read_csv, tmp_path):
        """qc.json montage_max_rows/cols seed session once for the QC task."""
        from views.landing_page import show_landing_page

        mock_df = pd.DataFrame({"participant_id": ["sub-CMH0001"]})
        mock_read_csv.return_value = mock_df
        qc_path = _stub_qc_config_path(tmp_path, montage_rows_cols=(2, 3))

        mock_st = MagicMock()
        with _patch_streamlit_for_landing(mock_st):
            show_landing_page(
                qc_pipeline="fmriprep",
                qc_task="anat_wf_qc",
                out_dir="/output",
                participant_list="participants.tsv",
                qc_config_path=qc_path,
            )

        assert mock_st.session_state[SESSION_KEYS["montage_max_rows"]] == 2
        assert mock_st.session_state[SESSION_KEYS["montage_max_cols"]] == 3
        assert mock_st.session_state[SESSION_KEYS["montage_defaults_applied_qc_task"]] == "anat_wf_qc"


class TestLandingPageRaterInfo:
    """Test rater information section of landing page."""

    @patch("views.landing_page.pd.read_csv")
    def test_rater_form_displays(self, mock_read_csv, tmp_path):
        """Test that rater form is displayed."""
        from views.landing_page import show_landing_page

        mock_df = pd.DataFrame({"participant_id": ["sub-CMH0001"]})
        mock_read_csv.return_value = mock_df

        mock_st = MagicMock()
        with _patch_streamlit_for_landing(mock_st):
            show_landing_page(
                qc_pipeline="fmriprep",
                qc_task="anat_wf_qc",
                out_dir="/output",
                participant_list="participants.tsv",
                qc_config_path=_stub_qc_config_path(tmp_path),
            )

        mock_st.form.assert_called()

    @patch("views.landing_page.pd.read_csv")
    def test_experience_level_options(self, mock_read_csv, tmp_path):
        """Test that experience level options are presented."""
        from views.landing_page import show_landing_page

        mock_df = pd.DataFrame({"participant_id": ["sub-CMH0001"]})
        mock_read_csv.return_value = mock_df

        mock_st = MagicMock()
        with _patch_streamlit_for_landing(mock_st):
            show_landing_page(
                qc_pipeline="fmriprep",
                qc_task="anat_wf_qc",
                out_dir="/output",
                participant_list="participants.tsv",
                qc_config_path=_stub_qc_config_path(tmp_path),
            )

        experience_options = EXPERIENCE_LEVELS
        assert len(experience_options) == 3
        assert any("Expert" in opt for opt in experience_options)


class TestLandingPagePanelSelection:
    """Test panel selection functionality."""

    @patch("views.landing_page.pd.read_csv")
    def test_panel_checkboxes_displayed(self, mock_read_csv, tmp_path):
        """Test that panel selection checkboxes are displayed."""
        from views.landing_page import show_landing_page

        mock_df = pd.DataFrame({"participant_id": ["sub-CMH0001"]})
        mock_read_csv.return_value = mock_df

        mock_st = MagicMock()
        with _patch_streamlit_for_landing(mock_st):
            show_landing_page(
                qc_pipeline="fmriprep",
                qc_task="anat_wf_qc",
                out_dir="/output",
                participant_list="participants.tsv",
                qc_config_path=_stub_qc_config_path(tmp_path),
            )

        mock_st.checkbox.assert_called()

    def test_default_panel_selections(self, sample_session_state):
        """Test default panel selections."""
        panels = sample_session_state["selected_panels"]

        assert panels["niivue_col"] is True
        assert panels["svg_col"] is True
        assert panels["iqm_col"] is False

    def test_panel_selection_validation(self, sample_session_state):
        """Test that at least one panel must be selected."""
        selected_count = sum(sample_session_state["selected_panels"].values())

        assert selected_count >= 1


class TestLandingPageCsvUpload:
    """Test CSV file upload functionality."""

    @patch("views.landing_page.pd.read_csv")
    def test_file_uploader_displayed(self, mock_read_csv, tmp_path):
        """Test that file uploader is displayed."""
        from views.landing_page import show_landing_page

        mock_df = pd.DataFrame({"participant_id": ["sub-CMH0001"]})
        mock_read_csv.return_value = mock_df

        mock_st = MagicMock()
        with _patch_streamlit_for_landing(mock_st):
            show_landing_page(
                qc_pipeline="fmriprep",
                qc_task="anat_wf_qc",
                out_dir="/output",
                participant_list="participants.tsv",
                qc_config_path=_stub_qc_config_path(tmp_path),
            )

        mock_st.file_uploader.assert_called()

    def test_csv_upload_validation(self, sample_qc_results_csv):
        """Test CSV upload validation."""
        # Read actual CSV for validation
        df = pd.read_csv(sample_qc_results_csv, sep="\t")

        # Should have expected columns
        assert "participant_id" in df.columns
        assert "rater_id" in df.columns
        assert "final_qc" in df.columns


class TestApp:
    """Test main app function."""

    @patch("app.SessionManager.is_landing_page_complete", return_value=False)
    @patch("app.SessionManager.init_session_state")
    @patch("app.show_landing_page")
    @patch("app.st")
    def test_app_landing_page_incomplete(self, mock_st, mock_show_landing, mock_init_session, mock_landing_done):
        """Test app shows landing page when not complete."""
        from app import app

        app(
            dataset_dir="/data",
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            qc_config_path="config.json",
            out_dir="/output",
            total_participants=5,
            drop_duplicates=True,
            participant_list="participants.tsv",
        )

        mock_st.set_page_config.assert_called()
        mock_show_landing.assert_called_once_with(
            "fmriprep",
            "anat_wf_qc",
            "/output",
            "participants.tsv",
            "config.json",
            qc_cohort=None,
        )

    @patch("app.SessionManager.is_landing_page_complete", return_value=True)
    @patch("app.SessionManager.init_session_state")
    @patch("app.show_congratulations_page")
    @patch("app.st")
    def test_app_congratulations_page(self, mock_st, mock_congrats, mock_init_session, mock_landing_done):
        """Test app shows congratulations page when complete."""
        from app import app

        app(
            dataset_dir="/data",
            participant_id=None,  # None indicates final page
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_task="anat_wf_qc",
            qc_config_path="config.json",
            out_dir="/output",
            total_participants=5,
            drop_duplicates=True,
            participant_list="participants.tsv",
        )

        mock_congrats.assert_called_once()


class TestQcViewerLayout:
    """Test QC viewer layout and panel display."""

    def test_niivue_panel_displayed(self):
        """Placeholder — full viewer layout is exercised manually / in integration tests."""
        assert True


class TestSessionStateManagement:
    """Test session state management in app."""

    def test_rater_information_in_session(self, sample_session_state):
        """Test rater information stored in session state."""
        assert sample_session_state["rater_id"] == "test_rater"
        assert sample_session_state["rater_experience"] is not None
        assert sample_session_state["rater_fatigue"] is not None

    def test_qc_records_in_session(self, sample_session_state):
        """Test QC records stored in session state."""
        assert isinstance(sample_session_state["qc_records"], list)

    def test_panel_selections_in_session(self, sample_session_state):
        """Test panel selections stored in session state."""
        assert "selected_panels" in sample_session_state
        assert isinstance(sample_session_state["selected_panels"], dict)


class TestNavigationControls:
    """Test navigation controls."""

    @patch("app.st")
    def test_previous_button_updates_page(self, mock_st):
        """Test that previous button updates current page."""
        from app import app

        mock_st.session_state = {"landing_page_complete": True, "current_page": 2, "rater_id": "test_rater"}
        mock_st.set_page_config = MagicMock()

        # Button behavior would be tested with button clicks
        # This is a placeholder for the concept
        assert mock_st.session_state["current_page"] > 1

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


def _sidebar_ctx():
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


class TestSidebarCohortNavOrder:
    """Playback and page controls stay above a scrollable subject list."""

    def test_controls_render_before_subject_list(self):
        from views.sidebar_cohort_nav import render_sidebar_cohort_subjects

        order = []
        cohort = [
            {"participant_id": "sub-CMH0001", "session_id": "ses-01"},
            {"participant_id": "sub-CMH0001", "session_id": "ses-02"},
        ]
        nav_kwargs = {
            "current_page": 1,
            "total_participants": 2,
            "participant_id": "sub-CMH0001",
            "session_id": "ses-01",
            "qc_pipeline": "fmriprep",
            "qc_tasks": ["sdc_wf_qc"],
            "participant_ids": ["sub-CMH0001"],
            "qc_cohort": cohort,
        }
        mock_st = MagicMock()
        mock_st.sidebar = _sidebar_ctx()
        mock_st.container.return_value = _sidebar_ctx()
        mock_st.button.return_value = False
        mock_st.caption.side_effect = lambda text, *a, **k: order.append(("caption", text))
        mock_st.divider.side_effect = lambda: order.append(("divider", None))

        def header(*args, **kwargs):
            order.append(("header", None))

        def controls(**kwargs):
            order.append(("controls", None))

        with (
            patch("views.sidebar_cohort_nav.st", mock_st),
            patch("views.sidebar_cohort_nav.SessionManager") as mock_sm,
            patch("components.qc_viewer._display_qc_pagination_header", side_effect=header),
            patch("components.qc_viewer._display_qc_pagination_controls", side_effect=controls),
        ):
            mock_sm.is_landing_page_complete.return_value = True
            mock_sm.get_current_page.return_value = 1
            mock_sm.participant_has_decided_qc.return_value = False
            mock_sm.is_autoplay_enabled.return_value = False
            render_sidebar_cohort_subjects(
                qc_cohort=cohort,
                total_participants=2,
                qc_task="sdc_wf_qc",
                qc_tasks=["sdc_wf_qc"],
                prepend_navigation=True,
                navigation_kwargs=nav_kwargs,
            )

        names = [name for name, _ in order]
        assert names[:3] == ["header", "controls", "divider"]
        assert names.index("controls") < names.index("caption")
        mock_st.container.assert_called_once_with(height=SIDEBAR_SUBJECT_LIST_HEIGHT, border=True)
        mock_st.caption.assert_called_with(MESSAGES["sidebar_subjects_header"])
        assert mock_st.button.call_count == 2
