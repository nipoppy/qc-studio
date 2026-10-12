"""Tests for scripts/transform_metadata.py."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import transform_metadata as tm  # noqa: E402

COLUMNS = [
    "pipeline",
    "qc_task",
    "participant_id",
    "session_id",
    "task_id",
    "run_id",
    "timestamp",
    "rater_id",
    "rater_experience",
    "rater_fatigue",
    "rater_screen_size",
    "final_qc",
    "facet",
    "rating_value",
    "notes",
]


def _row(task="t1", rater="r1", pid="sub-01", exp="Expert", fatigue="Not tired", size="27", pipeline="fsqc"):
    row = {c: "" for c in COLUMNS}
    row.update(
        pipeline=pipeline,
        qc_task=task,
        participant_id=pid,
        session_id="ses-01",
        rater_id=rater,
        timestamp="2026-10-01 10:00:00",
        rater_experience=exp,
        rater_fatigue=fatigue,
        rater_screen_size=size,
        final_qc="PASS",
    )
    return row


FULL_COLUMNS = {
    "rater_experience": {"Expert": "Expert (>5 years)"},
    "rater_fatigue": {"Not tired": "Not at all"},
    "rater_screen_size": {"27": "26-30"},
}


def _write_mapping(tmp_path, data):
    path = tmp_path / "map.json"
    path.write_text(json.dumps(data))
    return path


def _mapping(tmp_path, data):
    return tm.load_mapping(_write_mapping(tmp_path, data))


def _df(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


def _read(path):
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)


class TestLoadMapping:
    @pytest.mark.parametrize(
        "data, match",
        [
            ({"columns": {"rater_mood": {"a": "b"}}}, "Unknown column"),
            ({"columns": {}}, "'columns' is required"),
            ({}, "'columns' is required"),
            ({"columns": {"rater_fatigue": {"a": ["b", "c"]}}}, "single string"),
            ({"filter": {"session_id": "ses-01"}, "columns": FULL_COLUMNS}, "Unknown filter key"),
            ({"columns": FULL_COLUMNS, "extra": 1}, "Unknown top-level"),
            ({"columns": FULL_COLUMNS, "allowed": {"rater_mood": []}}, "Unknown column in 'allowed'"),
        ],
    )
    def test_invalid_mappings_rejected(self, tmp_path, data, match):
        with pytest.raises(tm.MappingError, match=match):
            _mapping(tmp_path, data)


class TestValidateTargets:
    def test_target_not_allowed_raises(self, tmp_path):
        m = _mapping(tmp_path, {"columns": {"rater_experience": {"Expert": "Guru"}}})
        with pytest.raises(tm.MappingError, match="Guru"):
            tm.validate_targets(m)

    def test_valid_mapping_passes(self, tmp_path):
        tm.validate_targets(_mapping(tmp_path, {"columns": FULL_COLUMNS}))

    def test_allowed_override_honoured(self, tmp_path):
        m = _mapping(tmp_path, {"columns": {"rater_screen_size": {"27": "large"}}, "allowed": {"rater_screen_size": ["large"]}})
        tm.validate_targets(m)

    def test_allowed_values_mirror_ui_constants(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import constants

        assert tm.ALLOWED_VALUES == {
            "rater_experience": constants.EXPERIENCE_LEVELS,
            "rater_fatigue": constants.FATIGUE_LEVELS,
            "rater_screen_size": constants.SCREEN_SIZES,
        }


class TestTransform:
    def test_remaps_values_and_keeps_layout(self, tmp_path):
        df = _df([_row(pid="sub-01"), _row(pid="sub-02")])
        out, report = tm.transform(df, _mapping(tmp_path, {"columns": FULL_COLUMNS}))
        assert list(out.columns) == COLUMNS
        assert list(out["participant_id"]) == ["sub-01", "sub-02"]
        assert set(out["rater_experience"]) == {"Expert (>5 years)"}
        assert set(out["rater_fatigue"]) == {"Not at all"}
        assert set(out["rater_screen_size"]) == {"26-30"}
        assert report.remapped["rater_experience:Expert->Expert (>5 years)"] == 2
        assert not report.warnings()

    def test_filter_limits_rows(self, tmp_path):
        df = _df([_row(task="t1", rater="r1"), _row(task="t2", rater="r1"), _row(task="t1", rater="r2")])
        m = _mapping(tmp_path, {"filter": {"qc_task": "t1", "rater_id": "r1"}, "columns": FULL_COLUMNS})
        out, report = tm.transform(df, m)
        assert list(out["rater_experience"]) == ["Expert (>5 years)", "Expert", "Expert"]
        assert report.rows_matched == 1 and report.passthrough_rows == 2

    def test_blank_key_fills_blanks(self, tmp_path):
        df = _df([_row(fatigue=""), _row(fatigue="nan")])
        m = _mapping(tmp_path, {"columns": {"rater_fatigue": {"": "Not at all"}}})
        out, report = tm.transform(df, m)
        assert list(out["rater_fatigue"]) == ["Not at all", "Not at all"]
        assert sum(report.filled_blanks.values()) == 2

    def test_blanks_untouched_without_blank_key(self, tmp_path):
        df = _df([_row(fatigue="")])
        out, _ = tm.transform(df, _mapping(tmp_path, {"columns": FULL_COLUMNS}))
        assert out.loc[0, "rater_fatigue"] == ""

    def test_unmapped_value_raises(self, tmp_path):
        df = _df([_row(exp="Novice")])
        with pytest.raises(tm.MappingError, match="Novice"):
            tm.transform(df, _mapping(tmp_path, {"columns": FULL_COLUMNS}))

    def test_passthrough_keeps_and_reports(self, tmp_path):
        df = _df([_row(exp="Novice")])
        out, report = tm.transform(df, _mapping(tmp_path, {"columns": FULL_COLUMNS}), passthrough_unmapped_values=True)
        assert out.loc[0, "rater_experience"] == "Novice"
        assert report.unmapped_values["rater_experience:Novice"] == 1
        assert report.disallowed_values["rater_experience:Novice"] == 1

    def test_unmapped_column_unchanged_but_flagged(self, tmp_path):
        df = _df([_row()])
        out, report = tm.transform(df, _mapping(tmp_path, {"columns": {"rater_experience": {"Expert": "Expert (>5 years)"}}}))
        assert out.loc[0, "rater_fatigue"] == "Not tired"
        assert out.loc[0, "rater_screen_size"] == "27"
        assert set(report.disallowed_values) == {"rater_fatigue:Not tired", "rater_screen_size:27"}

    def test_rerun_is_idempotent(self, tmp_path):
        m = _mapping(tmp_path, {"columns": FULL_COLUMNS})
        once, _ = tm.transform(_df([_row()]), m)
        twice, report = tm.transform(once, m)
        assert twice.equals(once)
        assert not report.remapped and not report.warnings()

    def test_input_not_mutated(self, tmp_path):
        df = _df([_row()])
        tm.transform(df, _mapping(tmp_path, {"columns": FULL_COLUMNS}))
        assert df.loc[0, "rater_experience"] == "Expert"


class TestMain:
    @pytest.fixture
    def files(self, tmp_path):
        inp = tmp_path / "in.tsv"
        _df([_row(pid="sub-01"), _row(pid="sub-02", task="other")]).to_csv(inp, sep="\t", index=False)
        mp = _write_mapping(tmp_path, {"filter": {"qc_task": "t1"}, "columns": FULL_COLUMNS})
        return inp, mp

    def test_end_to_end_and_overwrite_guard(self, tmp_path, files):
        inp, mp = files
        out = tmp_path / "out.tsv"
        args = ["--input", str(inp), "--mapping", str(mp), "--output", str(out)]
        assert tm.main(args) == 0
        df = _read(out)
        assert list(df.columns) == COLUMNS
        assert list(df["rater_experience"]) == ["Expert (>5 years)", "Expert"]
        assert tm.main(args) == 1
        assert tm.main(args + ["--overwrite"]) == 0

    def test_dry_run_writes_nothing(self, tmp_path, files):
        inp, mp = files
        out = tmp_path / "out.tsv"
        assert tm.main(["--input", str(inp), "--mapping", str(mp), "--output", str(out), "--dry-run"]) == 0
        assert not out.exists()

    def test_no_matching_rows(self, tmp_path, files):
        inp, _ = files
        mp = _write_mapping(tmp_path, {"filter": {"qc_task": "missing"}, "columns": FULL_COLUMNS})
        assert tm.main(["--input", str(inp), "--mapping", str(mp), "--output", str(tmp_path / "o.tsv")]) == 1

    def test_disallowed_target_fails_unless_skipped(self, tmp_path, files):
        inp, _ = files
        mp = _write_mapping(tmp_path, {"columns": {"rater_experience": {"Expert": "Guru"}}})
        base = ["--input", str(inp), "--mapping", str(mp), "--output", str(tmp_path / "o.tsv")]
        assert tm.main(base) == 1
        assert tm.main(base + ["--skip-allowed-check"]) == 0

    def test_strict_fails_on_warnings(self, tmp_path, files):
        inp, _ = files
        mp = _write_mapping(tmp_path, {"columns": {"rater_experience": {"Expert": "Expert (>5 years)"}}})
        assert tm.main(["--input", str(inp), "--mapping", str(mp), "--output", str(tmp_path / "o.tsv"), "--strict"]) == 1


class TestInPlace:
    @pytest.fixture
    def files(self, tmp_path):
        inp = tmp_path / "in.tsv"
        # Non-standard column order to check it is preserved
        cols = list(reversed(COLUMNS))
        _df([_row(pid="sub-01"), _row(pid="sub-02", task="other")])[cols].to_csv(inp, sep="\t", index=False)
        mp = _write_mapping(tmp_path, {"filter": {"qc_task": "t1"}, "columns": FULL_COLUMNS})
        return inp, mp

    def test_rewrites_only_metadata_cells(self, files):
        inp, mp = files
        before = _read(inp)
        assert tm.main(["--input", str(inp), "--mapping", str(mp), "--in-place"]) == 0
        after = _read(inp)
        assert list(after.columns) == list(before.columns)
        changed = [c for c in after.columns if not after[c].equals(before[c])]
        assert sorted(changed) == sorted(tm.METADATA_COLUMNS)
        assert after.loc[1].equals(before.loc[1])
        assert not list(inp.parent.glob(".in.tsv.*.tmp"))

    def test_backup(self, files):
        inp, mp = files
        original = inp.read_text()
        args = ["--input", str(inp), "--mapping", str(mp), "--in-place", "--backup"]
        assert tm.main(args) == 0
        bak = inp.with_name("in.tsv.bak")
        assert bak.read_text() == original
        assert tm.main(args) == 1
        assert tm.main(args + ["--overwrite"]) == 0

    def test_dry_run_leaves_file(self, files):
        inp, mp = files
        original = inp.read_text()
        assert tm.main(["--input", str(inp), "--mapping", str(mp), "--in-place", "--backup", "--dry-run"]) == 0
        assert inp.read_text() == original
        assert not inp.with_name("in.tsv.bak").exists()

    def test_output_and_in_place_exclusive(self, tmp_path, files):
        inp, mp = files
        with pytest.raises(SystemExit):
            tm.parse_args(["--input", str(inp), "--mapping", str(mp), "--in-place", "--output", str(tmp_path / "o.tsv")])

    def test_backup_requires_in_place(self, tmp_path, files):
        inp, mp = files
        with pytest.raises(SystemExit):
            tm.parse_args(["--input", str(inp), "--mapping", str(mp), "--output", str(tmp_path / "o.tsv"), "--backup"])
