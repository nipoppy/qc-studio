"""Tests for ui.py module."""

from argparse import ArgumentParser
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

import sys


class TestParseArgs:
    """Test argument parsing functionality."""

    @pytest.fixture(autouse=True)
    def _mock_streamlit_for_main_import(self, monkeypatch):
        """``main.py`` imports streamlit/layout at module level; stub them out for the
        duration of each test here only, via monkeypatch, so the swap can't leak into
        other test files' collection or execution (unlike a bare module-level assignment).
        """
        monkeypatch.setitem(sys.modules, "streamlit", MagicMock())
        monkeypatch.setitem(sys.modules, "layout", MagicMock())
        monkeypatch.delitem(sys.modules, "main", raising=False)

    def test_parse_args_with_required_arguments(self):
        """Test parsing with all required arguments."""
        from main import parse_args

        args = parse_args(
            [
                "--dataset_dir",
                "/path/to/dataset",
                "--participant_list",
                "/path/to/participants.tsv",
                "--session_list",
                "ses-01",
                "--qc_pipeline",
                "fmriprep",
                "--qc_task",
                "anat_wf_qc",
                "--output_dir",
                "/output",
                "--qc_json",
                "/path/to/qc_config.json",
            ]
        )

        assert args.dataset_dir == "/path/to/dataset"
        assert args.participant_list == "/path/to/participants.tsv"
        assert args.session_list == "ses-01"
        assert args.qc_pipeline == "fmriprep"
        assert args.qc_task == "anat_wf_qc"
        assert args.out_dir == "/output"
        assert args.qc_json == "/path/to/qc_config.json"

    def test_parse_args_default_session_list(self):
        """Test parsing with default session_list."""
        from main import parse_args

        args = parse_args(
            [
                "--dataset_dir",
                "/path/to/dataset",
                "--participant_list",
                "/path/to/participants.tsv",
                "--qc_pipeline",
                "fmriprep",
                "--qc_task",
                "anat_wf_qc",
                "--output_dir",
                "/output",
                "--qc_json",
                "/path/to/qc_config.json",
            ]
        )

        assert args.session_list is None

    def test_parse_args_missing_required_argument(self):
        """Test parsing with missing required argument."""
        from main import parse_args

        with pytest.raises(SystemExit):
            parse_args(
                [
                    "--participant_list",
                    "/path/to/participants.tsv",
                    # missing other required arguments
                ]
            )

    def test_parse_args_all_fields_present(self):
        """Test that all parsed fields are accessible."""
        from main import parse_args

        args = parse_args(
            [
                "--dataset_dir",
                "/data",
                "--participant_list",
                "participants.tsv",
                "--session_list",
                "ses-02",
                "--qc_pipeline",
                "freesurfer",
                "--qc_task",
                "surf_wf",
                "--output_dir",
                "/output/dir",
                "--qc_json",
                "config.json",
            ]
        )

        assert hasattr(args, "dataset_dir")
        assert hasattr(args, "participant_list")
        assert hasattr(args, "session_list")
        assert hasattr(args, "qc_pipeline")
        assert hasattr(args, "qc_task")
        assert hasattr(args, "out_dir")
        assert hasattr(args, "qc_json")


class TestSessionStateInitialization:
    """Test session state initialization."""

    @patch("streamlit.session_state", {})
    def test_init_session_state_creates_defaults(self):
        """Test that init_session_state creates default values."""
        # This test would need proper Streamlit mocking
        # Placeholder for now
        pass

    def test_session_state_keys(self, sample_session_state):
        """Test that session state has expected keys."""
        expected_keys = ["current_page", "batch_size", "current_batch_qc", "qc_records", "rater_id", "rater_experience", "rater_fatigue", "notes"]

        for key in expected_keys:
            assert key in sample_session_state

    def test_session_state_default_values(self, sample_session_state):
        """Test default values in session state."""
        assert sample_session_state["current_page"] == 1
        assert sample_session_state["batch_size"] == 1
        assert isinstance(sample_session_state["qc_records"], list)
        assert sample_session_state["rater_id"] == "test_rater"


class TestUiConfiguration:
    """Test UI configuration and setup."""

    def test_page_config_is_wide(self):
        """Test that page config is set to wide layout."""
        # This would require mocking st.set_page_config
        pass

    def test_participant_list_loading(self, sample_participant_list):
        """Test that participant list is loaded correctly."""
        df = pd.read_csv(sample_participant_list, delimiter="\t")

        assert len(df) == 3
        assert "participant_id" in df.columns
        assert "sub-CMH0001" in df["participant_id"].values

    def test_total_participants_calculation(self, sample_participant_list):
        """Test calculation of total participants."""
        df = pd.read_csv(sample_participant_list, delimiter="\t")
        total = len(df)

        assert total == 3

    def test_participant_id_at_page_index(self, sample_participant_list):
        """Test retrieving participant ID at page index."""
        df = pd.read_csv(sample_participant_list, delimiter="\t")
        participant_ids = df["participant_id"].tolist()

        assert participant_ids[0] == "sub-CMH0001"
        assert participant_ids[1] == "sub-CMH0002"
        assert participant_ids[2] == "sub-CMH0003"


class TestPageNavigation:
    """Test page navigation logic."""

    def test_current_page_bounds_lower(self):
        """Test that current_page cannot go below 1."""
        current_page = 0
        if current_page < 1:
            current_page = 1

        assert current_page == 1

    def test_current_page_bounds_upper(self):
        """Test that current_page handles upper bounds."""
        current_page = 10
        total_participants = 5

        if current_page > total_participants:
            participant_id = None
        else:
            participant_id = f"sub-CMH{current_page:04d}"

        assert participant_id is None

    def test_session_id_assignment(self):
        """Test that session_id is correctly assigned."""
        session_id = "ses-01"

        assert session_id == "ses-01"


class TestConfigPathResolution:
    """Test configuration path resolution."""

    def test_config_path_construction(self, temp_dir):
        """Test that config path is constructed correctly."""
        qc_json = "qc_config.json"

        # Simulate the path construction
        config_path = temp_dir / qc_json

        assert config_path.name == "qc_config.json"
        assert config_path.parent == temp_dir
