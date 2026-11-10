"""Tests for utils.qc_files (finding and picking each rater's current rating file)."""

from datetime import datetime

import pytest

from utils.qc_files import checkpoint_stamp, find_rating_files, read_rating_file, select_rating_file


def _touch(path, text="pipeline\tparticipant_id\nfsqc\tsub-01\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def rater(tmp_path):
    out = tmp_path / "alice" / "qc-output"
    return {"rater_id": "alice", "out_dir": str(out)}


def test_checkpoint_stamp():
    assert checkpoint_stamp("a_fsqc_t_checkpoint_20261012T143005Z.tsv") == datetime(2026, 10, 12, 14, 30, 5)
    assert checkpoint_stamp("a_fsqc_t_checkpoint_20261012T143005Z_transformed.tsv") == datetime(2026, 10, 12, 14, 30, 5)
    assert checkpoint_stamp("a_fsqc_t_qc_status.tsv") is None
    assert checkpoint_stamp("a_checkpoint_20261399T999999Z.tsv") is None


def test_find_groups_by_task(rater):
    out = rater["out_dir"]
    from pathlib import Path

    out = Path(out)
    _touch(out / "alice_fsqc_fs_surface_workflow_qc_status.tsv")
    _touch(out / "checkpoints" / "alice_fsqc_fs_surface_workflow_checkpoint_20261106T160953Z.tsv")
    _touch(out / "checkpoints" / "alice_fsqc_fs_volume_workflow_checkpoint_20261106T173054Z.tsv")
    files = find_rating_files(rater)
    assert sorted(files["task_key"].unique()) == ["fsqc_fs_surface_workflow", "fsqc_fs_volume_workflow"]
    assert set(files["kind"]) == {"status", "checkpoint"}
    assert (files["rater_id"] == "alice").all()


def test_find_skips_foreign_and_unrecognized_files(rater):
    from pathlib import Path

    out = Path(rater["out_dir"])
    _touch(out / "bob_fsqc_t_qc_status.tsv")
    _touch(out / "checkpoints" / "notes.tsv")
    warnings = []
    files = find_rating_files(rater, warn=warnings.append)
    assert files.empty
    assert any("notes.tsv" in w for w in warnings)
    assert any("bob_fsqc_t_qc_status.tsv" in w for w in warnings)


def test_find_missing_out_dir(rater):
    assert find_rating_files(rater).empty


def _files(rater, names):
    from pathlib import Path

    out = Path(rater["out_dir"])
    for n in names:
        _touch(out / n if n.endswith("_qc_status.tsv") else out / "checkpoints" / n)
    return find_rating_files(rater)


def test_status_preferred_over_checkpoints(rater):
    files = _files(rater, ["alice_p_t_qc_status.tsv", "alice_p_t_checkpoint_20261107T100000Z.tsv"])
    chosen, latest, n = select_rating_file(files)
    assert chosen["kind"] == "status"
    assert latest["path"].name == "alice_p_t_checkpoint_20261107T100000Z.tsv"
    assert n == 1


def test_newest_checkpoint_by_filename_stamp(rater):
    files = _files(rater, ["alice_p_t_checkpoint_20261106T235959Z.tsv", "alice_p_t_checkpoint_20261107T000001Z.tsv"])
    chosen, _, n = select_rating_file(files)
    assert chosen["path"].name == "alice_p_t_checkpoint_20261107T000001Z.tsv"
    assert n == 2


@pytest.mark.parametrize("prefer, expected", [(True, "_transformed.tsv"), (False, "Z.tsv")])
def test_transformed_copy(rater, prefer, expected):
    files = _files(rater, ["alice_p_t_checkpoint_20261007T152450Z.tsv", "alice_p_t_checkpoint_20261007T152450Z_transformed.tsv"])
    chosen, _, n = select_rating_file(files, prefer_transformed=prefer)
    assert chosen["path"].name.endswith(expected)
    assert n == 1  # the copy has the same stamp


def test_read_rating_file_strips(tmp_path):
    p = _touch(tmp_path / "f.tsv", " participant_id \tfinal_qc\n sub-01 \tAll-Pass \n")
    df = read_rating_file(p)
    assert list(df.columns) == ["participant_id", "final_qc"]
    assert df.iloc[0].tolist() == ["sub-01", "All-Pass"]
