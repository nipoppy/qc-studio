"""Tests for scripts/transform_ratings.py."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import transform_ratings as tr  # noqa: E402


def _row(task, facet="", value="", final_qc="", pid="sub-01", sid="ses-01", pipeline="fsqc", notes=""):
    row = {c: "" for c in tr.OUTPUT_COLUMNS}
    row.update(
        pipeline=pipeline,
        qc_task=task,
        participant_id=pid,
        session_id=sid,
        rater_id="r1",
        timestamp="2026-10-01 10:00:00",
        final_qc=final_qc,
        facet=facet,
        rating_value=value,
        notes=notes,
    )
    return row


def _multi(task, ratings, **kw):
    return [_row(task, facet=f, value=v, final_qc="Mixed", **kw) for f, v in ratings.items()]


def _mapping(tmp_path, data):
    data = {"source": {"qc_task": "old"}, "target": {"qc_task": "new", "type": "multi"}, **data}
    path = tmp_path / "map.json"
    path.write_text(json.dumps(data))
    return tr.load_mapping(path)


def _ratings(df, task="new"):
    sub = df[df["qc_task"] == task]
    return dict(zip(sub["facet"], sub["rating_value"]))


class TestLoadMapping:
    def test_duplicate_target_rejected(self, tmp_path):
        with pytest.raises(tr.MappingError, match="more than once"):
            _mapping(tmp_path, {"facets": {"one_to_one": {"a": "X"}, "one_to_many": {"b": ["X", "Y"]}}})

    def test_scale_one_to_many_rejected(self, tmp_path):
        with pytest.raises(tr.MappingError, match="one-to-many"):
            _mapping(tmp_path, {"scale": {"PASS": ["1", "2"]}})

    def test_unknown_block_rejected(self, tmp_path):
        with pytest.raises(tr.MappingError, match="Unknown facet block"):
            _mapping(tmp_path, {"facets": {"many_to_many": {}}})

    def test_bad_aggregate_rejected(self, tmp_path):
        with pytest.raises(tr.MappingError, match="unknown aggregate"):
            _mapping(tmp_path, {"facets": {"many_to_one": {"X": {"from": ["a", "b"], "aggregate": "worst"}}}})

    def test_single_requires_final_qc_rule(self, tmp_path):
        with pytest.raises(tr.MappingError, match="single"):
            _mapping(tmp_path, {"target": {"qc_task": "new", "type": "single"}, "facets": {"one_to_one": {"a": "X"}}})


class TestAggregate:
    @pytest.mark.parametrize(
        "values,how,expected",
        [
            (["PASS", "PASS", "FAIL"], "majority", ("PASS", False)),
            (["PASS", "FAIL"], "majority", ("", True)),
            (["PASS", "FAIL", "PASS"], "any:FAIL", ("FAIL", False)),
            (["PASS", "PASS"], "any:FAIL", ("PASS", False)),
            (["", "FAIL"], "first", ("FAIL", False)),
            (["", "FAIL"], "majority", ("", False)),
            (["", "FAIL"], "any:FAIL", ("", False)),
        ],
    )
    def test_aggregate(self, values, how, expected):
        assert tr.aggregate(values, how) == expected


class TestDeriveFinalQc:
    @pytest.mark.parametrize(
        "ratings,expected",
        [
            ({"a": "PASS", "b": "PASS"}, "All-Pass"),
            ({"a": "FAIL", "b": "FAIL"}, "All-Fail"),
            ({"a": "UNCERTAIN"}, "All-Uncertain"),
            ({"a": "PASS", "b": "FAIL"}, "Mixed"),
            ({"a": "PASS", "b": ""}, ""),
        ],
    )
    def test_matches_ui_labels(self, ratings, expected):
        assert tr.derive_final_qc(ratings) == expected


class TestTransform:
    def test_rename_only_keeps_facets_and_other_tasks(self, tmp_path):
        df = pd.DataFrame(_multi("old", {"a": "PASS", "b": "FAIL"}) + [_row("other", final_qc="PASS")])
        m = _mapping(tmp_path, {"target": {"qc_task": "new", "type": "multi", "pipeline": "fsqc_enigma"}})
        out, report = tr.transform(df, m)
        assert _ratings(out) == {"a": "PASS", "b": "FAIL"}
        assert set(out.loc[out["qc_task"] == "new", "pipeline"]) == {"fsqc_enigma"}
        other = out[out["qc_task"] == "other"].iloc[0]
        assert other["final_qc"] == "PASS" and other["pipeline"] == "fsqc"
        assert report.records == 1 and report.passthrough_rows == 1

    def test_facet_blocks(self, tmp_path):
        df = pd.DataFrame(_multi("old", {"a": "PASS", "b": "FAIL", "c": "PASS", "d": "PASS", "e": "UNCERTAIN"}))
        m = _mapping(
            tmp_path,
            {
                "facets": {
                    "one_to_one": {"a": "A"},
                    "one_to_many": {"b": ["B1", "B2"]},
                    "many_to_one": {"CD": {"from": ["c", "d", "b"], "aggregate": "any:FAIL"}},
                }
            },
        )
        out, report = tr.transform(df, m)
        assert _ratings(out) == {"A": "PASS", "B1": "FAIL", "B2": "FAIL", "CD": "FAIL"}
        assert set(out["final_qc"]) == {"Mixed"}
        assert report.dropped_facets == {"e": 1}

    def test_unmapped_facets_keep(self, tmp_path):
        df = pd.DataFrame(_multi("old", {"a": "PASS", "e": "FAIL"}))
        m = _mapping(tmp_path, {"facets": {"one_to_one": {"a": "A"}}, "unmapped_facets": "keep"})
        out, _ = tr.transform(df, m)
        assert _ratings(out) == {"A": "PASS", "e": "FAIL"}

    def test_missing_source_facet_is_blank(self, tmp_path):
        df = pd.DataFrame(_multi("old", {"a": "PASS"}))
        m = _mapping(tmp_path, {"facets": {"one_to_one": {"a": "A", "zzz": "Z"}}})
        out, report = tr.transform(df, m)
        assert _ratings(out) == {"A": "PASS", "Z": ""}
        assert set(out["final_qc"]) == {""}
        assert report.missing_facets == {"zzz": 1} and report.blank_cells == 1

    def test_single_to_multi(self, tmp_path):
        df = pd.DataFrame([_row("old", final_qc="PASS"), _row("old", final_qc="FAIL", pid="sub-02")])
        m = _mapping(tmp_path, {"facets": {"one_to_many": {"final_qc": ["Motion", "Cropped"]}}})
        out, _ = tr.transform(df, m)
        assert _ratings(out[out["participant_id"] == "sub-01"]) == {"Motion": "PASS", "Cropped": "PASS"}
        assert set(out.loc[out["participant_id"] == "sub-02", "final_qc"]) == {"All-Fail"}

    def test_multi_to_single(self, tmp_path):
        df = pd.DataFrame(_multi("old", {"a": "PASS", "b": "FAIL"}))
        m = _mapping(
            tmp_path,
            {
                "target": {"qc_task": "new", "type": "single"},
                "facets": {"many_to_one": {"final_qc": {"from": ["*"], "aggregate": "any:FAIL"}}},
            },
        )
        out, _ = tr.transform(df, m)
        assert len(out) == 1
        assert out.iloc[0]["final_qc"] == "FAIL" and out.iloc[0]["facet"] == ""

    def test_scale_many_to_one(self, tmp_path):
        df = pd.DataFrame(_multi("old", {"a": "QUESTIONABLE", "b": "PASS"}))
        m = _mapping(tmp_path, {"scale": {"PASS": "1", "QUESTIONABLE": "0.5", "UNCERTAIN": "0.5"}})
        out, report = tr.transform(df, m)
        assert _ratings(out) == {"a": "0.5", "b": "1"}
        assert report.scale_remapped["PASS->1"] == 1

    def test_unmapped_scale_value(self, tmp_path):
        df = pd.DataFrame(_multi("old", {"a": "WEIRD"}))
        m = _mapping(tmp_path, {"scale": {"PASS": "1"}})
        with pytest.raises(tr.MappingError, match="WEIRD"):
            tr.transform(df, m)
        out, report = tr.transform(df, m, passthrough_unmapped_values=True)
        assert _ratings(out) == {"a": "WEIRD"} and report.unmapped_values == {"WEIRD": 1}

    def test_majority_tie_reported(self, tmp_path):
        df = pd.DataFrame(_multi("old", {"a": "PASS", "b": "FAIL"}))
        m = _mapping(tmp_path, {"facets": {"many_to_one": {"X": {"from": ["a", "b"]}}}})
        out, report = tr.transform(df, m)
        assert _ratings(out) == {"X": ""}
        assert report.ties == ["sub-01/ses-01:X"]

    def test_source_pipeline_filter(self, tmp_path):
        df = pd.DataFrame(_multi("old", {"a": "PASS"}) + _multi("old", {"a": "FAIL"}, pipeline="other"))
        m = _mapping(tmp_path, {"source": {"qc_task": "old", "pipeline": "fsqc"}})
        out, _ = tr.transform(df, m)
        assert set(out["qc_task"]) == {"new", "old"}
        assert out.loc[out["qc_task"] == "old", "pipeline"].iloc[0] == "other"


class TestValidateAgainstQcJson:
    @pytest.fixture
    def qc_json(self, tmp_path):
        path = tmp_path / "qc.json"
        path.write_text(json.dumps({"new": {"rating": {"type": "multi", "scale": ["PASS", "FAIL"], "facets": ["A", "B"]}}}))
        return path

    def test_unknown_target_facet(self, tmp_path, qc_json):
        m = _mapping(tmp_path, {"facets": {"one_to_one": {"a": "Z"}}})
        with pytest.raises(tr.MappingError, match="not defined"):
            tr.validate_against_qc_json(m, qc_json)

    def test_bad_scale_value(self, tmp_path, qc_json):
        m = _mapping(tmp_path, {"scale": {"PASS": "1"}})
        with pytest.raises(tr.MappingError, match="not in target scale"):
            tr.validate_against_qc_json(m, qc_json)

    def test_missing_target_task(self, tmp_path, qc_json):
        m = _mapping(tmp_path, {"target": {"qc_task": "nope", "type": "multi"}})
        with pytest.raises(tr.MappingError, match="not found"):
            tr.validate_against_qc_json(m, qc_json)

    def test_unproduced_facets_warn(self, tmp_path, qc_json):
        m = _mapping(tmp_path, {"facets": {"one_to_one": {"a": "A"}}})
        assert tr.validate_against_qc_json(m, qc_json) == ["qc.json facets never produced by the mapping: ['B']"]


class TestMain:
    def test_end_to_end_and_overwrite_guard(self, tmp_path):
        inp, out = tmp_path / "in.tsv", tmp_path / "out.tsv"
        pd.DataFrame([_row("old", final_qc="PASS")]).to_csv(inp, sep="\t", index=False)
        mp = tmp_path / "map.json"
        mp.write_text(json.dumps({"source": {"qc_task": "old"}, "target": {"qc_task": "new"}, "facets": {"one_to_many": {"final_qc": ["A", "B"]}}}))
        args = ["--input", str(inp), "--mapping", str(mp), "--output", str(out)]
        assert tr.main(args) == 0
        df = pd.read_csv(out, sep="\t", dtype=str, keep_default_na=False)
        assert list(df.columns) == tr.OUTPUT_COLUMNS
        assert _ratings(df) == {"A": "PASS", "B": "PASS"}
        assert tr.main(args) == 1
        assert tr.main(args + ["--overwrite"]) == 0

    def test_strict_fails_on_warnings(self, tmp_path):
        inp = tmp_path / "in.tsv"
        pd.DataFrame(_multi("old", {"a": "PASS", "b": "PASS"})).to_csv(inp, sep="\t", index=False)
        mp = tmp_path / "map.json"
        mp.write_text(json.dumps({"source": {"qc_task": "old"}, "target": {"qc_task": "new"}, "facets": {"one_to_one": {"a": "A"}}}))
        assert tr.main(["--input", str(inp), "--mapping", str(mp), "--output", str(tmp_path / "o.tsv"), "--strict"]) == 1
