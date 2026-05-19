"""Tests for qc_viewer helper utilities."""

from components.qc_viewer import _clean_filename


class TestCleanFilename:
    """Tests for compact tab label generation."""

    def test_extracts_session_task_run_tokens(self):
        """Functional keys should prefer ses/task/run tokens."""
        filename = "figures_sub-ED01_ses-01_task-rest_run-01_svg"
        assert _clean_filename(filename) == "ses-01_task-rest_run-01"

    def test_strips_subject_prefix_for_anatomical_keys(self):
        """Anatomical keys should remove noisy subject-prefixed fragments."""
        filename = "figures_sub-ED01_figure_sub-ED01_dseg_svg"
        assert _clean_filename(filename) == "dseg"

    def test_removes_extension_suffix_when_no_structured_tokens(self):
        """Fallback path should remove synthetic image-type suffixes."""
        filename = "summary_plot_png"
        assert _clean_filename(filename) == "summary_plot"
