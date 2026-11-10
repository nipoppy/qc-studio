"""Tests for utils.ratings_report (collating every rater's current ratings)."""

import json

import pandas as pd
import pytest

from utils.ratings_report import (
    agreement_summary,
    assigned_ids,
    collate_ratings,
    consensus,
    dataset_coverage,
    facet_rating_counts,
    final_qc_counts,
    off_list_ratings,
    participant_level,
    rater_progress,
)

POOL = ["sub-01", "sub-02", "sub-03", "sub-04"]
COLS = ["pipeline", "qc_task", "participant_id", "session_id", "task_id", "run_id", "timestamp", "rater_id", "final_qc", "facet", "rating_value"]


def _rows(rater, pid, final_qc, values, ts="2026-11-01 10:00:00", task="FS_volume_workflow"):
    return [["fsqc", task, pid, "ses-BL", "", "", ts, rater, final_qc, f"facet{i}", v] for i, v in enumerate(values)]


def _save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=COLS).to_csv(path, sep="\t", index=False)


@pytest.fixture
def config(tmp_path):
    """alice (list sub-01..02) has a status file plus an older checkpoint; bob (list sub-02..03) has checkpoints only."""
    for rid, pids in {"alice": ["sub-01", "sub-02"], "bob": ["sub-02", "sub-03"], "carol": ["sub-04"]}.items():
        (tmp_path / rid).mkdir()
        pd.DataFrame({"participant_id": pids}).to_csv(tmp_path / rid / f"{rid}.tsv", sep="\t", index=False)
    a_out, b_out = tmp_path / "alice" / "qc-output", tmp_path / "bob" / "qc-output"
    _save(
        a_out / "alice_fsqc_fs_volume_workflow_qc_status.tsv",
        _rows("alice", "sub-01", "All-Pass", ["PASS", "PASS"]) + _rows("alice", "sub-02", "Mixed", ["PASS", "FAIL"]),
    )
    # older checkpoint has a participant the status file lacks -> flagged
    _save(a_out / "checkpoints" / "alice_fsqc_fs_volume_workflow_checkpoint_20261101T090000Z.tsv", _rows("alice", "sub-09", "All-Pass", ["PASS"]))
    _save(b_out / "checkpoints" / "bob_fsqc_fs_volume_workflow_checkpoint_20261101T090000Z.tsv", _rows("bob", "sub-02", "All-Fail", ["FAIL"]))
    _save(
        b_out / "checkpoints" / "bob_fsqc_fs_volume_workflow_checkpoint_20261102T090000Z.tsv",
        _rows("bob", "sub-02", "Mixed", ["PASS", "FAIL"]) + _rows("bob", "sub-03", "All-Pass", ["PASS", "PASS"]),
    )
    users = {f"{r}@x.org": {"participant_list": f"{r}.tsv"} for r in ["alice", "bob", "carol"]}
    path = tmp_path / "users.json"
    path.write_text(json.dumps({"users": users}))
    return path


def test_collate_picks_current_files(config):
    col = collate_ratings(config)
    src = col.sources.set_index("rater_id")
    assert src.loc["alice", "source_kind"] == "status"
    assert src.loc["alice", "in_latest_ckpt_not_in_status"] == 1
    assert src.loc["bob", "source_file"].endswith("20261102T090000Z.tsv")
    assert src.loc["bob", "n_checkpoints"] == 2
    assert col.raters_without_files == ["carol"]
    assert len(col.ratings) == 8


def test_collate_drops_repeats_keeping_latest(config, tmp_path):
    p = tmp_path / "alice" / "qc-output" / "alice_fsqc_fs_volume_workflow_qc_status.tsv"
    rows = _rows("alice", "sub-01", "All-Pass", ["PASS"]) + _rows("alice", "sub-01", "All-Fail", ["FAIL"], ts="2026-11-02 10:00:00")
    _save(p, rows)
    col = collate_ratings(config)
    alice = col.ratings[col.ratings["rater_id"] == "alice"]
    assert col.n_duplicates_dropped == 1
    assert alice["rating_value"].tolist() == ["FAIL"]


def test_collate_overwrites_wrong_rater_id(config, tmp_path):
    p = tmp_path / "alice" / "qc-output" / "alice_fsqc_fs_volume_workflow_qc_status.tsv"
    _save(p, _rows("mallory", "sub-01", "All-Pass", ["PASS"]))
    col = collate_ratings(config)
    assert set(col.ratings["rater_id"]) == {"alice", "bob"}
    assert any("mallory" in w for w in col.warnings)


def test_collate_skips_files_missing_columns(config, tmp_path):
    p = tmp_path / "alice" / "qc-output" / "alice_fsqc_fs_volume_workflow_qc_status.tsv"
    p.write_text("participant_id\nsub-01\n")
    col = collate_ratings(config)
    assert "alice" not in set(col.ratings["rater_id"])
    assert any("missing column" in w for w in col.warnings)


def test_reports(config):
    col = collate_ratings(config)
    qc = participant_level(col.ratings)
    assert len(qc) == 4
    assert qc.set_index(["rater_id", "participant_id"]).loc[("alice", "sub-02"), "n_fail"] == 1

    counts = final_qc_counts(qc)
    assert counts.loc[("fsqc", "FS_volume_workflow"), "Mixed"] == 2

    assigned = assigned_ids(config)
    progress = rater_progress(qc, assigned, POOL).set_index("rater_id")
    assert progress.loc["alice", "rated_assigned"] == 2 and progress.loc["alice", "pct_complete"] == 100.0
    assert progress.loc["bob", "rated"] == 2
    assert off_list_ratings(qc, assigned, POOL).empty

    cov = dataset_coverage(qc, POOL, assigned).iloc[0]
    assert (cov["rated_1+"], cov["rated_2+"], cov["not_rated"], cov["pct_rated"]) == (3, 1, 1, 75.0)
    assert cov["assigned_to_any_rater"] == 4

    cons = consensus(qc).set_index("participant_id")
    assert cons.loc["sub-02", "n_raters"] == 2 and bool(cons.loc["sub-02", "unanimous"])
    assert cons.loc["sub-02", "majority_qc"] == "Mixed"
    summary = agreement_summary(consensus(qc))
    assert summary.loc["FS_volume_workflow", "pct_unanimous"] == 100.0

    facets = facet_rating_counts(col.ratings, "FS_volume_workflow")
    assert facets.index[0] == "facet1"  # least passing first


def test_disagreement_has_no_majority():
    qc = pd.DataFrame(
        {
            "rater_id": ["a", "b"],
            "pipeline": "p",
            "qc_task": "t",
            "participant_id": "sub-01",
            "session_id": "",
            "task_id": "",
            "run_id": "",
            "final_qc": ["All-Pass", "All-Fail"],
        }
    )
    row = consensus(qc).iloc[0]
    assert not row["unanimous"] and row["majority_qc"] == "No majority"


def test_empty_config(tmp_path):
    path = tmp_path / "users.json"
    path.write_text(json.dumps({"users": {}}))
    col = collate_ratings(path)
    assert col.ratings.empty and col.sources.empty
    qc = participant_level(col.ratings)
    assert qc.empty and consensus(qc).empty
