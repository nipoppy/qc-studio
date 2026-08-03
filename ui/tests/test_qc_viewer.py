"""Tests for qc_viewer helper utilities."""
import json

from components import qc_viewer
from components.qc_viewer import _clean_filename, _record_all_qc_tasks


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


class TestRecordAllQcTasks:
    """Tests for recording QC metadata from configured montage paths."""

    def test_records_task_and_run_from_svg_montage_path(self, monkeypatch, temp_dir):
        """Saved QC records should include unambiguous task/run metadata."""
        qc_config_path = temp_dir / "qc.json"
        qc_config_path.write_text(
            json.dumps({
                "func_wf_qc": {
                    "svg_montage_path": (
                        "derivatives/sub-01/ses-01/figures/"
                        "sub-01_ses-01_task-rest_run-02_desc-montage.svg"
                    )
                }
            })
        )
        session_state = {
            "qc_records": [],
            "rating_version": 0,
            "notes_version": 0,
            "qc_rating_func_wf_qc_0": "PASS",
            "qc_notes_func_wf_qc_0": "looks good",
            "rater_id": "test_rater",
            "rater_experience": "Expert",
            "rater_fatigue": "Rested",
        }
        monkeypatch.setattr(qc_viewer.st, "session_state", session_state)

        _record_all_qc_tasks(
            participant_id="sub-01",
            session_id="ses-01",
            qc_pipeline="fmriprep",
            qc_tasks=["func_wf_qc"],
            qc_config_path=qc_config_path,
        )

        assert len(session_state["qc_records"]) == 1
        record = session_state["qc_records"][0]
        assert record.task_id == "task-rest"
        assert record.run_id == "run-02"
