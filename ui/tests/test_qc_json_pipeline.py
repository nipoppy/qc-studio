"""``qc.json`` naming its own pipeline (issue #106): reserved ``__key__`` entries and pipeline resolution."""

import json

import pytest

from admin import core
from utils.config import PIPELINE_KEY, is_reserved_qc_key, list_qc_tasks_from_json, qc_pipeline_from_json


def _qc_json(tmp_path, data):
    p = tmp_path / "qc.json"
    p.write_text(json.dumps(data))
    return p


@pytest.mark.parametrize("key, reserved", [("__pipeline__", True), ("__x__", True), ("____", False), ("__task", False), ("anat_wf_qc", False)])
def test_is_reserved_qc_key(key, reserved):
    assert is_reserved_qc_key(key) is reserved


def test_reserved_keys_are_not_tasks(tmp_path):
    p = _qc_json(tmp_path, {PIPELINE_KEY: "fsqc", "task_a": {}, "__future__": {}, "task_b": {}})
    assert list_qc_tasks_from_json(p) == ["task_a", "task_b"]
    assert core.expected_tasks(p) == ["task_a", "task_b"]


@pytest.mark.parametrize("value, expected", [(" fsqc ", "fsqc"), ("", None), (5, None), (None, None)])
def test_qc_pipeline_from_json(tmp_path, value, expected):
    data = {"task_a": {}} if value is None else {PIPELINE_KEY: value, "task_a": {}}
    assert qc_pipeline_from_json(_qc_json(tmp_path, data)) == expected


def test_qc_pipeline_from_missing_or_invalid_file(tmp_path):
    assert qc_pipeline_from_json(tmp_path / "missing.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]")
    assert qc_pipeline_from_json(bad) is None


def test_resolve_pipeline_prefers_qc_json(tmp_path):
    p = _qc_json(tmp_path, {PIPELINE_KEY: "fsqc", "task_a": {}})
    assert core.resolve_qc_pipeline(None, p) == "fsqc"
    assert core.resolve_qc_pipeline("FSQC", p) == "fsqc"  # agreeing CLI value is fine


def test_resolve_pipeline_falls_back_to_cli(tmp_path):
    assert core.resolve_qc_pipeline(" fsqc ", _qc_json(tmp_path, {"task_a": {}})) == "fsqc"


def test_resolve_pipeline_conflict_or_missing(tmp_path):
    with pytest.raises(ValueError, match="does not match"):
        core.resolve_qc_pipeline("fmriprep", _qc_json(tmp_path, {PIPELINE_KEY: "fsqc", "task_a": {}}))
    with pytest.raises(ValueError, match="no pipeline"):
        core.resolve_qc_pipeline(None, _qc_json(tmp_path, {"task_a": {}}), env={})


def test_pipeline_from_env_when_no_cli_value(tmp_path):
    qc = _qc_json(tmp_path, {"task_a": {}})
    assert core.resolve_qc_pipeline(None, qc, env={"QC_PIPELINE": "fsqc"}) == "fsqc"
    assert core.resolve_qc_pipeline("mriqc", qc, env={"QC_PIPELINE": "fsqc"}) == "mriqc"  # the CLI value wins
    with pytest.raises(ValueError, match="does not match"):
        core.resolve_qc_pipeline(None, _qc_json(tmp_path, {PIPELINE_KEY: "fsqc", "task_a": {}}), env={"QC_PIPELINE": "mriqc"})


def test_no_pipeline_message_keeps_the_key_name(tmp_path):
    with pytest.raises(ValueError) as exc:
        core.resolve_qc_pipeline(None, _qc_json(tmp_path, {"task_a": {}}), env={})
    assert f'`"{PIPELINE_KEY}"' in str(exc.value)  # in backticks, so Streamlit markdown doesn't bold it
