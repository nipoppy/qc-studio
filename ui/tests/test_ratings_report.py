"""Tests for utils.ratings_report (collating every rater's current ratings)."""

import json

import pandas as pd
import pytest

from utils.ratings_report import (
    coverage_buckets,
    split_expected,
    ALL_TASKS,
    dataset_sessions,
    expected_records,
    records_rated,
    IN_PROGRESS,
    NOT_EXPECTED,
    NOT_STARTED,
    agreement_summary,
    assigned_ids,
    assignment_completion,
    collate_ratings,
    consensus,
    dataset_coverage,
    facet_rating_counts,
    final_qc_counts,
    off_list_ratings,
    pace_summary,
    progress_grid,
    participant_level,
    rating_durations,
    rater_progress,
    split_expected,
    task_status,
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


def test_assignment_completion(config):
    qc = participant_level(collate_ratings(config).ratings)
    comp = assignment_completion(qc, assigned_ids(config)).set_index("qc_task")
    task = comp.loc["FS_volume_workflow"]
    # lists: alice 2, bob 2, carol 1 (no ratings) -> 5 assigned; alice rated 2, bob 2 of his own
    assert (task["assigned"], task["rated_assigned"], task["pct_complete"]) == (5, 4, 80.0)
    assert (task["raters_started"], task["raters_with_list"]) == (2, 3)
    assert comp.loc[ALL_TASKS, "assigned"] == 5 and comp.loc[ALL_TASKS, "pct_complete"] == 80.0


def test_assignment_completion_pools_tasks(config, tmp_path):
    rows = _rows("alice", "sub-01", "All-Pass", ["PASS"], task="FS_surface_workflow")
    _save(tmp_path / "alice" / "qc-output" / "alice_fsqc_fs_surface_workflow_qc_status.tsv", rows)
    qc = participant_level(collate_ratings(config).ratings)
    comp = assignment_completion(qc, assigned_ids(config)).set_index("qc_task")
    assert comp.loc["FS_surface_workflow", "rated_assigned"] == 1 and comp.loc["FS_surface_workflow", "pct_complete"] == 20.0
    assert (comp.loc[ALL_TASKS, "assigned"], comp.loc[ALL_TASKS, "rated_assigned"]) == (10, 5)
    assert comp.loc[ALL_TASKS, "pct_complete"] == 50.0


def test_assignment_completion_empty(tmp_path):
    path = tmp_path / "users.json"
    path.write_text(json.dumps({"users": {}}))
    assert assignment_completion(participant_level(collate_ratings(path).ratings), {}).empty


EXPECTED = ["FS_preproc_workflow", "FS_volume_workflow"]


def test_task_status_reports_unstarted_and_unexpected(config, tmp_path):
    rows = _rows("alice", "sub-01", "All-Pass", ["PASS"], task="old_task")
    _save(tmp_path / "alice" / "qc-output" / "alice_fsqc_old_task_qc_status.tsv", rows)
    qc = participant_level(collate_ratings(config).ratings)
    status = task_status(qc, "fsqc", EXPECTED).set_index("qc_task")
    assert list(status.index) == ["FS_preproc_workflow", "FS_volume_workflow", "old_task"]
    assert status.loc["FS_preproc_workflow", "status"] == NOT_STARTED and status.loc["FS_preproc_workflow", "ratings"] == 0
    assert status.loc["FS_volume_workflow", "status"] == IN_PROGRESS and status.loc["FS_volume_workflow", "raters_started"] == 2
    assert status.loc["old_task", "status"] == NOT_EXPECTED and not status.loc["old_task", "in_qc_json"]

    expected, other = split_expected(qc, "FSQC", EXPECTED)  # pipeline match ignores case
    assert set(expected["qc_task"]) == {"FS_volume_workflow"} and set(other["qc_task"]) == {"old_task"}


def test_unstarted_expected_tasks_in_completion_and_coverage(config):
    qc = participant_level(collate_ratings(config).ratings)
    comp = assignment_completion(qc, assigned_ids(config), tasks=EXPECTED).set_index("qc_task")
    assert comp.loc["FS_preproc_workflow", "rated_assigned"] == 0 and comp.loc["FS_preproc_workflow", "pct_complete"] == 0.0
    assert comp.loc["FS_preproc_workflow", "raters_started"] == 0
    # the unstarted task counts in the overall denominator
    assert (comp.loc[ALL_TASKS, "assigned"], comp.loc[ALL_TASKS, "rated_assigned"], comp.loc[ALL_TASKS, "pct_complete"]) == (10, 4, 40.0)

    cov = dataset_coverage(qc, POOL, assigned_ids(config), tasks=EXPECTED, pipeline="fsqc").set_index("qc_task")
    assert cov.loc["FS_preproc_workflow", "rated_1+"] == 0 and cov.loc["FS_preproc_workflow", "not_rated"] == len(POOL)
    assert cov.loc["FS_volume_workflow", "rated_1+"] == 3


def test_dataset_sessions_column_wins_over_session_list():
    pool = pd.DataFrame({"participant_id": ["sub-1", "sub-1", "sub-2"], "session_id": ["ses-BL", "ses-V04", "ses-BL"]})
    assert dataset_sessions(pool, "ses-X") == (["ses-BL", "ses-V04"], "session_id column")
    assert dataset_sessions(pool[["participant_id"]], "ses-BL") == (["ses-BL"], "--session_list")
    assert dataset_sessions(pool[["participant_id"]], None) == ([], "not specified")


def test_expected_records_and_records_rated():
    pool = pd.DataFrame({"participant_id": ["sub-1", "sub-2", "sub-3"]})
    records = expected_records(pool, ["t1", "t2"], "ses-BL,ses-V04")
    assert len(records) == 3 * 2 * 2
    qc = pd.DataFrame(
        {
            "rater_id": ["a", "b", "a", "a", "a"],
            "participant_id": ["sub-1", "sub-1", "sub-2", "sub-9", "sub-3"],  # sub-9 is outside the dataset
            "session_id": ["ses-BL", "ses-BL", "ses-V04", "ses-BL", "ses-BL"],
            "qc_task": ["t1", "t1", "t2", "t1", "t3"],  # t3 is not prescribed
        }
    )
    assert records_rated(qc, records) == 2  # sub-1/BL/t1 counted once despite two raters
    assert records_rated(qc.iloc[:0], records) == 0


def test_expected_records_from_session_column_and_without_sessions():
    pool = pd.DataFrame({"participant_id": ["sub-1", "sub-1", "sub-2"], "session_id": ["ses-BL", "ses-V04", "ses-BL"]})
    assert len(expected_records(pool, ["t1"])) == 3
    flat = expected_records(pool[["participant_id"]], ["t1", "t2"], None)
    assert len(flat) == 4 and flat["session_id"].isna().all()
    qc = pd.DataFrame({"participant_id": ["sub-1"], "session_id": ["ses-BL"], "qc_task": ["t2"]})
    assert records_rated(qc, flat) == 1  # no sessions: matched on participant and task
    assert expected_records(pool, []).empty


def test_split_expected_normalises_pipeline():
    qc = pd.DataFrame({"pipeline": ["FSQC", "fsqc", "mriqc"], "qc_task": ["t1", "t2", "t1"], "rater_id": "a", "participant_id": "s1"})
    expected, other = split_expected(qc, "fsqc", ["t1"])
    assert expected["pipeline"].tolist() == ["fsqc"] and len(other) == 2


def test_coverage_buckets_per_task():
    qc = pd.DataFrame({"qc_task": ["t1", "t1", "t1", "t2"], "rater_id": ["a", "b", "a", "a"], "participant_id": ["s1", "s1", "s2", "s9"]})
    out = coverage_buckets(qc, ["s1", "s2", "s3"], ["t1", "t2"])
    assert out.loc["t1"].to_dict() == {"0": 1, "1": 1, "2": 1, "3+": 0}
    assert out.loc["t2"].to_dict() == {"0": 3, "1": 0, "2": 0, "3+": 0}  # s9 is outside the pool


def _qc(rows):
    """Participant-level ratings from (rater, task, participant, timestamp) tuples."""
    return pd.DataFrame(
        [
            {
                "rater_id": r,
                "pipeline": "fsqc",
                "qc_task": t,
                "participant_id": p,
                "session_id": "ses-BL",
                "task_id": "",
                "run_id": "",
                "timestamp": ts,
            }
            for r, t, p, ts in rows
        ]
    )


def test_rating_durations_splits_sittings_at_breaks():
    qc = _qc(
        [
            ("r1", "A", "sub-01", "2026-11-01 10:00:00"),
            ("r1", "A", "sub-02", "2026-11-01 10:00:30"),
            ("r1", "B", "sub-01", "2026-11-01 10:01:30"),  # task switch: still the same stream
            ("r1", "A", "sub-03", "2026-11-01 11:00:00"),  # 58.5 min later: new sitting
            ("r1", "A", "sub-04", "2026-11-01 11:00:20"),
            ("r2", "A", "sub-01", "2026-11-01 10:00:10"),  # other rater: own stream
            ("r2", "A", "sub-02", "not a time"),  # dropped
        ]
    )
    d = rating_durations(qc, break_minutes=15)
    assert len(d) == 6
    r1 = d[d["rater_id"] == "r1"]
    assert r1["seconds"].fillna(-1).tolist() == [-1, 30.0, 60.0, -1, 20.0]  # -1 = first of a sitting
    assert r1["sitting"].tolist() == [1, 1, 1, 2, 2]
    assert d[d["rater_id"] == "r2"]["sitting"].tolist() == [1]

    # A longer cutoff joins the two sittings.
    assert rating_durations(qc, break_minutes=60).query("rater_id == 'r1'")["sitting"].max() == 1


def test_pace_summary_per_rater_task_and_task():
    qc = _qc([("r1", "A", f"sub-0{i}", f"2026-11-01 10:00:{10 * i:02d}") for i in range(5)] + [("r2", "A", "sub-01", "2026-11-02 09:00:00")])
    d = rating_durations(qc)
    s = pace_summary(d).set_index(["rater_id", "qc_task"])
    row = s.loc[("r1", "A")]
    assert (row["n_ratings"], row["n_timed"], row["median_s"], row["sittings"], row["days"]) == (5, 4, 10, 1, 1)
    assert row["active_min"] == round(40 / 60, 1)
    assert row["per_hour"] == 360.0
    assert s.loc[("r2", "A"), "n_timed"] == 0 and pd.isna(s.loc[("r2", "A"), "median_s"])
    t = pace_summary(d, by=["qc_task"]).set_index("qc_task")
    assert (t.loc["A", "n_ratings"], t.loc["A", "sittings"], t.loc["A", "days"]) == (6, 2, 2)


def test_pace_empty():
    assert rating_durations(pd.DataFrame()).empty
    assert pace_summary(rating_durations(pd.DataFrame())).empty


def test_progress_grid_fills_unstarted_tasks():
    assigned = {"r1": {"sub-01", "sub-02", "sub-03", "sub-04"}, "r2": {"sub-01", "sub-02"}, "r3": set()}
    qc = _qc([("r1", "A", "sub-01", "2026-11-01 10:00:00")]).assign(final_qc="All-Pass")
    progress = rater_progress(qc, assigned, POOL)
    g = progress_grid(progress, assigned, ["A", "B"])
    assert g[["rater_id", "qc_task", "rated_assigned", "pct_complete"]].values.tolist() == [
        ["r1", "A", 1, 25.0],
        ["r1", "B", 0, 0.0],
        ["r2", "A", 0, 0.0],
        ["r2", "B", 0, 0.0],
    ]  # r3 has no list: left out
    assert progress_grid(progress.iloc[0:0], {}, ["A"]).empty
