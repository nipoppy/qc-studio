"""Tests for qc_viewer helper utilities."""

import pytest

from components.qc_viewer import _clean_filename, _compact_session_label

pytestmark = pytest.mark.unit


class TestCompactSessionLabel:
    """Tests for the compact QC page header."""

    def test_includes_participant_and_session(self):
        assert _compact_session_label("sub-CMH0001", "ses-01") == "sub-CMH0001 · ses-01"

    def test_omits_pipeline_and_task_count(self):
        label = _compact_session_label("sub-CMH0001", "ses-01")
        assert "fmriprep" not in label.lower()
        assert "task" not in label.lower()
        assert "count" not in label.lower()

    def test_omits_session_when_missing(self):
        assert _compact_session_label("sub-CMH0001", None) == "sub-CMH0001"


class TestCleanFilename:
    """Tests for compact tab label generation."""

    def test_extracts_session_task_run_tokens(self):
        """Functional keys should prefer ses/task/run tokens."""
        filename = "figures_sub-CMH0001_ses-01_task-rest_run-01_svg"
        assert _clean_filename(filename) == "ses-01_task-rest_run-01"

    def test_strips_subject_prefix_for_anatomical_keys(self):
        """Anatomical keys should remove noisy subject-prefixed fragments."""
        filename = "figures_sub-CMH0001_figure_sub-CMH0001_dseg_svg"
        assert _clean_filename(filename) == "dseg"

    def test_removes_extension_suffix_when_no_structured_tokens(self):
        """Fallback path should remove synthetic image-type suffixes."""
        filename = "summary_plot_png"
        assert _clean_filename(filename) == "summary_plot"
