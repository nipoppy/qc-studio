"""Tests for congratulations page export path helpers and export behavior."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import streamlit as st

from models import QCRecord
from views.congratulations_page import (
    _default_congrats_export_path,
    _resolve_congrats_export_file_path,
    _export_qc_results,
    _require_overwrite_confirmation,
    _display_session_summary,
)

pytestmark = pytest.mark.unit


def _mock_columns(*args, **kwargs):
    spec = args[0] if args else 1
    n = spec if isinstance(spec, int) else len(spec)
    cols = []
    for _ in range(n):
        col = MagicMock()
        col.__enter__.return_value = None
        col.__exit__.return_value = False
        cols.append(col)
    return tuple(cols)


def test_default_congrats_export_path_uses_out_dir_and_rater_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _default_congrats_export_path("relative/run", "Rater42")
    assert path.endswith("rater42_all_tasks_status.tsv")
    assert path == str((tmp_path / "relative" / "run" / "rater42_all_tasks_status.tsv").resolve())


def test_require_overwrite_confirmation_prompts_before_overwriting_existing_file(tmp_path):
    existing = tmp_path / "existing.tsv"
    existing.write_text("already here")
    state = {}

    with patch.object(st, "session_state", state):
        assert _require_overwrite_confirmation(existing, "Exported QC results") is False
        assert state["_pending_overwrite_path"] == str(existing)


def test_require_overwrite_confirmation_allows_confirmed_overwrite(tmp_path):
    existing = tmp_path / "existing.tsv"
    existing.write_text("already here")
    state = {"_pending_overwrite_path": str(existing)}

    with patch.object(st, "session_state", state):
        assert _require_overwrite_confirmation(existing, "Exported QC results") is True
        assert "_pending_overwrite_path" not in state


def test_overwrite_confirm_button_resets_pending_state_after_export(tmp_path):
    existing = tmp_path / "existing.tsv"
    existing.write_text("already here")
    state = {"_pending_overwrite_path": str(existing)}

    with patch.object(st, "session_state", state):
        assert _require_overwrite_confirmation(existing, "Exported QC results") is True
        assert "_pending_overwrite_path" not in state


def test_resolve_congrats_export_file_path_honors_custom_file_path(tmp_path):
    custom_file = tmp_path / "custom" / "QC_status.csv"
    resolved = _resolve_congrats_export_file_path(str(tmp_path), "rater42", str(custom_file))
    assert resolved == custom_file


def test_export_qc_results_uses_custom_path_and_sets_success_message(tmp_path):
    state = {}
    record = QCRecord(
        participant_id="sub-CMH0001",
        session_id="ses-01",
        qc_task="anat_wf_qc",
        pipeline="fmriprep",
        timestamp="2026-09-03 12:00:00",
        rater_id="rater42",
        rater_experience="Expert (>5 year experience)",
        rater_fatigue="Not at all",
        final_qc="PASS",
        notes="",
    )
    custom_file = tmp_path / "saved" / "QC_status.csv"

    with patch.object(st, "session_state", state):
        _export_qc_results(
            "rater42",
            str(tmp_path),
            [record],
            True,
            save_file_path=str(custom_file),
        )

    assert custom_file.exists()
    kind, msg = state["_pending_export_msg"]
    assert kind == "success"
    assert str(custom_file) in msg


def test_display_session_summary_renders_duration_histogram_when_durations_present():
    state = {}
    records = [
        QCRecord(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_task="anat_wf_qc",
            pipeline="fmriprep",
            timestamp="2026-09-03 12:00:00",
            rater_id="rater42",
            final_qc="PASS",
            duration=10,
            notes="",
        ),
        QCRecord(
            participant_id="sub-CMH0002",
            session_id="ses-01",
            qc_task="anat_wf_qc",
            pipeline="fmriprep",
            timestamp="2026-09-03 12:01:00",
            rater_id="rater42",
            final_qc="FAIL",
            duration=15,
            notes="",
        ),
    ]

    with (
        patch.object(st, "session_state", state),
        patch.object(st, "columns", side_effect=_mock_columns),
        patch.object(st, "subheader"),
        patch.object(st, "write"),
        patch.object(st, "dataframe"),
        patch.object(st, "plotly_chart") as mock_plot,
    ):
        _display_session_summary("rater42", "anat_wf_qc", records)

    mock_plot.assert_called_once()


def test_display_session_summary_renders_decision_duration_metrics_when_present():
    state = {}
    records = [
        QCRecord(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_task="anat_wf_qc",
            pipeline="fmriprep",
            timestamp="2026-09-03 12:00:00",
            rater_id="rater42",
            final_qc="PASS",
            duration=10,
            decision_duration=7,
            notes="",
        ),
        QCRecord(
            participant_id="sub-CMH0002",
            session_id="ses-01",
            qc_task="anat_wf_qc",
            pipeline="fmriprep",
            timestamp="2026-09-03 12:01:00",
            rater_id="rater42",
            final_qc="FAIL",
            duration=15,
            decision_duration=11,
            notes="",
        ),
    ]

    with (
        patch.object(st, "session_state", state),
        patch.object(st, "columns", side_effect=_mock_columns),
        patch.object(st, "subheader"),
        patch.object(st, "write") as mock_write,
        patch.object(st, "dataframe"),
        patch.object(st, "plotly_chart") as mock_plot,
    ):
        _display_session_summary("rater42", "anat_wf_qc", records)

    # Review-duration and decision-duration charts should both render.
    assert mock_plot.call_count == 2
    write_texts = [str(c.args[0]) for c in mock_write.call_args_list if c.args]
    assert any("Total final-decision duration" in text for text in write_texts)
    assert any("Average final-decision time per participant" in text for text in write_texts)


def test_display_session_summary_skips_histogram_when_durations_missing():
    state = {}
    records = [
        QCRecord(
            participant_id="sub-CMH0001",
            session_id="ses-01",
            qc_task="anat_wf_qc",
            pipeline="fmriprep",
            timestamp="2026-09-03 12:00:00",
            rater_id="rater42",
            final_qc="PASS",
            notes="",
        )
    ]

    with (
        patch.object(st, "session_state", state),
        patch.object(st, "columns", side_effect=_mock_columns),
        patch.object(st, "subheader"),
        patch.object(st, "write"),
        patch.object(st, "dataframe"),
        patch.object(st, "plotly_chart") as mock_plot,
    ):
        _display_session_summary("rater42", "anat_wf_qc", records)

    mock_plot.assert_not_called()
