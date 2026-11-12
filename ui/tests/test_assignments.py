"""Tests for utils.assignments (rater workloads and new participant lists)."""

import json

import pandas as pd
import pytest

from utils.assignments import (
    clean_ids,
    count_buckets,
    create_rater_list,
    load_assignments,
    overlap_matrices,
    overlapping_pairs,
    rank_participants_by_rater_count,
    rater_count_distribution,
    rater_count_buckets,
    rater_summary,
    rater_workload,
    read_participant_ids,
    restrict_to_pool,
    write_participant_list,
)
from utils.user_config import load_users_config

POOL = [f"sub-{i:02d}" for i in range(1, 11)]


@pytest.fixture
def config(tmp_path):
    """alice: sub-01..04, bob: sub-03..06, carol: in config but no list yet."""
    lists = {"alice": POOL[0:4], "bob": POOL[2:6]}
    for rid, pids in lists.items():
        (tmp_path / rid).mkdir()
        pd.DataFrame({"participant_id": pids}).to_csv(tmp_path / rid / f"{rid}.tsv", sep="\t", index=False)
    users = {f"{rid}@x.org": {"participant_list": f"{rid}.tsv"} for rid in ["alice", "bob", "carol"]}
    path = tmp_path / "users.json"
    path.write_text(json.dumps({"users": users}))
    return path


def test_read_participant_ids_strips_and_dedups(tmp_path):
    p = tmp_path / "p.tsv"
    p.write_text("participant_id\tsession_id\n sub-01 \tses-BL\nsub-01\tses-FU\n\t\nsub-02\tses-BL\n")
    assert read_participant_ids(p) == ["sub-01", "sub-02"]


def test_read_participant_ids_requires_column(tmp_path):
    p = tmp_path / "p.tsv"
    p.write_text("subject\nsub-01\n")
    with pytest.raises(ValueError, match="participant_id"):
        read_participant_ids(p)


def test_load_assignments(config):
    notes = []
    a = load_assignments(config, warn=notes.append)
    assert sorted(a["rater_id"].unique()) == ["alice", "bob"]
    assert len(a) == 8
    assert any("carol" in n for n in notes)
    assert (a["session_id"] == "").all()


def test_load_assignments_accepts_loaded_config(config):
    assert len(load_assignments(load_users_config(config), warn=lambda _: None)) == 8


def test_only_configured_list_is_used(config):
    pd.DataFrame({"participant_id": ["sub-09"]}).to_csv(config.parent / "alice" / "alice_secondary.tsv", sep="\t", index=False)
    a = load_assignments(config, warn=lambda _: None)
    assert "sub-09" not in set(a["participant_id"])
    assert set(a["list_file"]) == {"alice.tsv", "bob.tsv"}


def test_overlap_statistics(config):
    a = load_assignments(config, warn=lambda _: None)
    summary = rater_summary(a)
    assert summary.loc["alice", "n_participants"] == 4
    assert summary.loc["alice", "shared_with_others"] == 2 and summary.loc["alice", "exclusive"] == 2
    dist = rater_count_distribution(a)
    assert dist.loc[1, "n_participants"] == 4 and dist.loc[2, "n_participants"] == 2
    overlap, jaccard = overlap_matrices(a)
    assert overlap.loc["alice", "bob"] == 2 and overlap.loc["alice", "alice"] == 4
    assert jaccard.loc["alice", "bob"] == pytest.approx(2 / 6)
    pairs = overlapping_pairs(a)
    assert pairs.iloc[0][["rater_a", "rater_b", "shared"]].tolist() == ["alice", "bob", 2]


def test_overlap_is_per_participant_even_with_sessions():
    a = pd.DataFrame({"rater_id": ["a", "a", "b"], "list_file": "f", "participant_id": ["s1", "s1", "s1"], "session_id": ["ses-1", "ses-2", "ses-1"]})
    summary = rater_summary(a)
    assert summary.loc["a", "n_participants"] == 1 and summary.loc["a", "n_sessions"] == 2
    assert summary.loc["a", "duplicate_rows"] == 0  # different sessions are not duplicates
    assert overlap_matrices(a)[0].loc["a", "b"] == 1


def test_rater_workload_qc_records(config):
    a = load_assignments(config, warn=lambda _: None)
    wl = rater_workload(a, n_tasks=3, sessions_by_rater={"alice": ["ses-BL", "ses-FU"], "bob": None})
    # QC records = participants x sessions x tasks
    assert (wl.loc["alice", "n_sessions"], wl.loc["alice", "qc_records"]) == (2, 4 * 2 * 3)
    assert (wl.loc["bob", "n_sessions"], wl.loc["bob", "qc_records"]) == (1, 4 * 1 * 3)  # no session level: one
    assert (wl["n_tasks"] == 3).all()


def test_rater_workload_counts_listed_sessions():
    a = pd.DataFrame(
        {"rater_id": "a", "list_file": "f", "participant_id": ["s1", "s1", "s2", "s2"], "session_id": ["ses-1", "ses-2", "ses-1", "ses-1"]}
    )
    wl = rater_workload(a, n_tasks=2, sessions_by_rater={"a": ["ses-X"]})  # the list's own sessions win
    assert (wl.loc["a", "n_sessions"], wl.loc["a", "qc_records"], wl.loc["a", "duplicate_rows"]) == (2, 3 * 2, 1)


def test_rank_fewest_raters_first(config):
    ranked = rank_participants_by_rater_count(config, POOL, seed=1, warn=lambda _: None)
    assert ranked["n_raters"].tolist() == sorted(ranked["n_raters"].tolist())
    assert set(ranked.head(4)["participant_id"]) == {"sub-07", "sub-08", "sub-09", "sub-10"}
    assert ranked.set_index("participant_id").loc["sub-03", "raters"] == "alice, bob"


def test_create_rater_list_is_repeatable_and_ignores_own_list(config):
    a = load_assignments(config, warn=lambda _: None)
    first = create_rater_list("alice", 6, POOL, a, seed=7)
    again = create_rater_list("alice", 6, POOL, a, seed=7)
    assert first.equals(again)
    # alice's own list is ignored: sub-01/02 count as unassigned, sub-03..06 have bob only.
    assert (first["n_raters"] == 0).sum() == 6
    assert first["participant_id"].tolist() == sorted(first["participant_id"], key=lambda s: (len(s), s))


def test_create_rater_list_too_many(config):
    with pytest.raises(ValueError, match="only 10"):
        create_rater_list("carol", 11, POOL, load_assignments(config, warn=lambda _: None))


def test_write_participant_list_never_overwrites_by_default(config):
    out, status = write_participant_list(["sub-07", "sub-08"], config, "carol")
    assert status == "written" and out == (config.parent / "carol" / "carol.tsv").resolve()
    assert read_participant_ids(out) == ["sub-07", "sub-08"]
    _, status = write_participant_list(["sub-09"], config, "carol")
    assert status.startswith("exists")
    assert read_participant_ids(out) == ["sub-07", "sub-08"]
    write_participant_list(["sub-09"], config, "carol", overwrite=True)
    assert read_participant_ids(out) == ["sub-09"]


def test_write_participant_list_unknown_rater(config):
    with pytest.raises(KeyError):
        write_participant_list(["sub-01"], config, "dave")


def test_least_rated_is_the_default_policy(config):
    a = load_assignments(config, warn=lambda _: None)
    assert create_rater_list("carol", 5, POOL, a, seed=3).equals(create_rater_list("carol", 5, POOL, a, seed=3, policy="least_rated"))


def test_random_policy(config):
    a = load_assignments(config, warn=lambda _: None)
    first = create_rater_list("carol", 5, POOL, a, seed=1, policy="random")
    assert first.equals(create_rater_list("carol", 5, POOL, a, seed=1, policy="random"))
    others = {tuple(create_rater_list("carol", 5, POOL, a, seed=s, policy="random")["participant_id"]) for s in range(2, 8)}
    assert others - {tuple(first["participant_id"])}  # another seed gives another sample
    assert set(first.columns) == {"participant_id", "n_raters", "raters"}
    counts = {p: n for p, n in zip(first["participant_id"], first["n_raters"])}
    assert all(counts[p] == (2 if p in ("sub-03", "sub-04") else 1 if p in ("sub-01", "sub-02", "sub-05", "sub-06") else 0) for p in counts)


def test_random_ignores_existing_assignments(config):
    # with the whole pool drawn, random must include already-assigned participants
    a = load_assignments(config, warn=lambda _: None)
    assert set(create_rater_list("carol", 10, POOL, a, seed=0, policy="random")["participant_id"]) == set(POOL)


def test_unknown_policy(config):
    with pytest.raises(ValueError, match="unknown policy"):
        create_rater_list("carol", 2, POOL, load_assignments(config, warn=lambda _: None), policy="fair")


def test_restrict_to_pool():
    kept, dropped = restrict_to_pool([" sub-05", "sub-99", "sub-05", "", "sub-01", "sub-98"], POOL)
    assert kept == ["sub-05", "sub-01"]
    assert dropped == ["sub-99", "sub-98"]


@pytest.mark.parametrize("policy", ["least_rated", "random"])
def test_custom_source_only(config, policy):
    kept, _ = restrict_to_pool(["sub-02", "sub-07", "sub-09", "sub-99"], POOL)
    notes = []
    a = load_assignments(config, warn=lambda _: None)
    chosen = create_rater_list("carol", 3, kept, a, seed=4, policy=policy, warn=notes.append, warn_outside_pool=False)
    assert set(chosen["participant_id"]) == {"sub-02", "sub-07", "sub-09"}
    assert notes == []
    with pytest.raises(ValueError, match="only 3"):
        create_rater_list("carol", 4, kept, a, policy=policy, warn_outside_pool=False)


def test_all_policy_takes_the_whole_source(config):
    a = load_assignments(config, warn=lambda _: None)
    kept, _ = restrict_to_pool(["sub-09", "sub-02", "sub-07"], POOL)
    chosen = create_rater_list("carol", None, kept, a, policy="all", warn_outside_pool=False)
    assert chosen["participant_id"].tolist() == ["sub-02", "sub-07", "sub-09"]
    assert chosen.set_index("participant_id").loc["sub-02", "n_raters"] == 1
    # the count is ignored
    assert len(create_rater_list("carol", 1, POOL, a, policy="all")) == len(POOL)


def test_rater_count_buckets(config):
    a = load_assignments(config, warn=lambda _: None)
    extra = pd.DataFrame({"rater_id": ["carol"] * 2, "list_file": "c.tsv", "participant_id": ["sub-03", "sub-99"], "session_id": ""})
    b = rater_count_buckets(pd.concat([a, extra], ignore_index=True), POOL).set_index("bucket")
    # pool of 10: sub-07..10 none; sub-01,02,05,06 one; sub-04 two; sub-03 three (alice, bob, carol); sub-99 not in pool
    assert list(b.index) == ["0", "1", "2", "3+"]
    assert b["n_participants"].tolist() == [4, 4, 1, 1]
    assert b.loc["0", "pct"] == 40.0 and b.loc["2", "pct_at_least"] == 20.0 and b.loc["0", "pct_at_least"] == 100.0


def test_rater_count_buckets_empty_pool(config):
    b = rater_count_buckets(load_assignments(config, warn=lambda _: None), [])
    assert b["n_participants"].tolist() == [0, 0, 0, 0]


def test_clean_ids_and_count_buckets():
    assert clean_ids([" s1", "s2", "s1", "", "s3 "]) == ["s1", "s2", "s3"]
    counts = pd.Series({"s1": 1, "s2": 5, "out": 2})  # "out" is not in the pool
    buckets = count_buckets(counts, ["s1", "s2", "s3"])
    assert buckets.to_dict() == {"0": 1, "1": 1, "2": 0, "3+": 1}


def test_overlap_jaccard_zero_for_disjoint_and_identical_is_one():
    a = pd.DataFrame({"rater_id": ["a", "a", "b", "c", "c"], "list_file": "f", "participant_id": ["s1", "s2", "s3", "s1", "s2"], "session_id": ""})
    overlap, jaccard = overlap_matrices(a)
    assert overlap.loc["a", "b"] == 0 and jaccard.loc["a", "b"] == 0
    assert jaccard.loc["a", "c"] == 1 and overlap.loc["c", "c"] == 2
