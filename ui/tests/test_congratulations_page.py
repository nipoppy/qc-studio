"""Tests for congratulations page export path helpers and export behavior."""

from unittest.mock import patch

import pytest
import streamlit as st

from models import QCRecord
from views.congratulations_page import (
    _default_congrats_export_path,
    _resolve_congrats_export_file_path,
    _export_qc_results,
)

pytestmark = pytest.mark.unit


def test_default_congrats_export_path_uses_out_dir_and_rater_id(tmp_path):
    path = _default_congrats_export_path(str(tmp_path), "rater42")
    assert path.endswith("rater42_QC_status.tsv")
    assert str(tmp_path) in path


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
