"""Tests for BIDS filename helpers."""
from pathlib import Path

import pytest

from utils.bids import (
    bare_bids_id,
    extract_bids_entities_from_path,
    extract_unique_task_run_from_paths,
    normalize_participant_id_bids,
    normalize_session_id_bids,
    parse_session_list,
)


class TestBidsIdHelpers:
    """Test BIDS ID normalization helpers."""

    def test_bare_bids_id_strips_prefix_and_leading_zeros(self):
        assert bare_bids_id("sub-0001", "sub-") == "1"
        assert bare_bids_id("ses-01", "ses-") == "1"

    def test_normalize_participant_id_bids_adds_missing_prefix(self):
        assert normalize_participant_id_bids("CMH0001") == "sub-CMH0001"
        assert normalize_participant_id_bids("sub-CMH0001") == "sub-CMH0001"

    def test_normalize_session_id_bids_adds_missing_prefix(self):
        assert normalize_session_id_bids("1") == "ses-01"
        assert normalize_session_id_bids("BL") == "ses-BL"
        assert normalize_session_id_bids("ses-02") == "ses-02"

    def test_normalize_session_id_bids_rejects_empty_value(self):
        with pytest.raises(ValueError):
            normalize_session_id_bids("")

    def test_parse_session_list_returns_unique_normalized_sessions(self):
        assert parse_session_list("1,ses-02,1") == ["ses-01", "ses-02"]
        assert parse_session_list("") is None


class TestExtractBidsEntitiesFromPath:
    """Test BIDS entity extraction from path-like filenames."""

    def test_extracts_all_entities_from_svg_path(self):
        entities = extract_bids_entities_from_path(
            "figures/sub-01_ses-01_task-rest_run-02_desc-montage.svg"
        )

        assert entities == {
            "sub": "01",
            "ses": "01",
            "task": "rest",
            "run": "02",
            "desc": "montage",
        }

    def test_extracts_entities_from_multi_suffix_path_without_file_existing(self):
        entities = extract_bids_entities_from_path(
            "sub-01/ses-01/func/sub-01_ses-01_task-rest_run-02_bold.nii.gz"
        )

        assert entities["sub"] == "01"
        assert entities["ses"] == "01"
        assert entities["task"] == "rest"
        assert entities["run"] == "02"

    def test_returns_missing_entities_absent(self):
        entities = extract_bids_entities_from_path("sub-01_ses-01_desc-montage.svg")

        assert entities.get("task") is None
        assert entities.get("run") is None

    def test_accepts_path_objects(self):
        entities = extract_bids_entities_from_path(
            Path("sub-01_ses-01_task-rest_run-02_desc-montage.svg")
        )

        assert entities["task"] == "rest"
        assert entities["run"] == "02"

    def test_empty_path_returns_empty_dict(self):
        assert extract_bids_entities_from_path(None) == {}
        assert extract_bids_entities_from_path("") == {}


class TestExtractUniqueTaskRunFromPaths:
    """Test extracting one task/run pair from one or more paths."""

    def test_extracts_unique_task_run_from_single_path(self):
        task_id, run_id = extract_unique_task_run_from_paths(
            "sub-01_ses-01_task-rest_run-02_desc-montage.svg"
        )

        assert task_id == "task-rest"
        assert run_id == "run-02"

    def test_extracts_unique_task_run_from_multiple_matching_paths(self):
        task_id, run_id = extract_unique_task_run_from_paths([
            "sub-01_ses-01_task-rest_run-02_desc-sdc.svg",
            "sub-01_ses-01_task-rest_run-02_desc-coreg.svg",
        ])

        assert task_id == "task-rest"
        assert run_id == "run-02"

    def test_returns_none_for_conflicting_runs(self):
        task_id, run_id = extract_unique_task_run_from_paths([
            "sub-01_ses-01_task-rest_run-01_desc-sdc.svg",
            "sub-01_ses-01_task-rest_run-02_desc-sdc.svg",
        ])

        assert task_id is None
        assert run_id is None

    def test_extracts_task_without_run(self):
        task_id, run_id = extract_unique_task_run_from_paths(
            "sub-01_ses-01_task-rest_desc-montage.svg"
        )

        assert task_id == "task-rest"
        assert run_id is None

    def test_returns_none_for_missing_entities(self):
        task_id, run_id = extract_unique_task_run_from_paths(
            "sub-01_ses-01_desc-montage.svg"
        )

        assert task_id is None
        assert run_id is None
