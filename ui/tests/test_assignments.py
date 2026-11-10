"""Tests for utils.assignments (rater workloads and new participant lists)."""

import json

import pandas as pd
import pytest

from utils.assignments import (
    add_units,
    create_rater_list,
    load_assignments,
    overlap_matrices,
    overlapping_pairs,
    rank_participants_by_rater_count,
    rater_count_distribution,
    rater_summary,
    read_participant_ids,
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


def test_list_glob_adds_secondary_lists(config):
    pd.DataFrame({"participant_id": ["sub-09"]}).to_csv(config.parent / "alice" / "alice_secondary.tsv", sep="\t", index=False)
    a = load_assignments(config, list_glob="*.tsv", warn=lambda _: None)
    assert "sub-09" in set(a.loc[a["rater_id"] == "alice", "participant_id"])


def test_overlap_statistics(config):
    a, key = add_units(load_assignments(config, warn=lambda _: None))
    assert key == ["participant_id"]
    summary = rater_summary(a)
    assert summary.loc["alice", "shared_with_others"] == 2 and summary.loc["alice", "exclusive"] == 2
    dist = rater_count_distribution(a)
    assert dist.loc[1, "n_units"] == 4 and dist.loc[2, "n_units"] == 2
    overlap, jaccard = overlap_matrices(a)
    assert overlap.loc["alice", "bob"] == 2 and overlap.loc["alice", "alice"] == 4
    assert jaccard.loc["alice", "bob"] == pytest.approx(2 / 6)
    pairs = overlapping_pairs(a)
    assert pairs.iloc[0][["rater_a", "rater_b", "shared"]].tolist() == ["alice", "bob", 2]


def test_units_use_sessions_when_every_row_has_one():
    a = pd.DataFrame({"rater_id": ["a", "a"], "list_file": "f", "participant_id": ["s1", "s1"], "session_id": ["ses-1", "ses-2"]})
    out, key = add_units(a)
    assert key == ["participant_id", "session_id"]
    assert out["unit"].nunique() == 2
    assert add_units(a, participant_level_only=True)[0]["unit"].nunique() == 1


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
