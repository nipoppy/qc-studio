"""Transform one qc_task in a qc_status.tsv using a JSON mapping.

Usage:
    python scripts/transform_ratings.py --input in_qc_status.tsv \\
        --mapping map.json --output out_qc_status.tsv \\
        [--target-qc-json pipelines/fsqc_enigma/qc.json]

The mapping renames the task (and optionally the pipeline), remaps facet
names via explicit one_to_one / one_to_many / many_to_one blocks, and remaps
rating scale values. Rows belonging to other tasks are passed through
unchanged, so several mapping files can be chained. See
scripts/transform_ratings.md for the mapping schema.
"""

import argparse
import json
import logging
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger("transform_ratings")

OUTPUT_COLUMNS = [
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
# Mirrors ui/constants.py::QC_DEDUP_KEYS (+ facet), as used by save_qc_results_to_csv
DEDUP_KEYS = ["participant_id", "session_id", "pipeline", "qc_task", "facet"]
RECORD_KEYS = ["pipeline", "participant_id", "session_id", "task_id", "run_id", "rater_id"]
METADATA_COLUMNS = ["timestamp", "rater_experience", "rater_fatigue", "rater_screen_size", "notes"]
SORT_COLUMNS = ["pipeline", "participant_id", "session_id", "qc_task", "facet"]

FINAL_QC = "final_qc"
ALL_FACETS = "*"
FACET_BLOCKS = ("one_to_one", "one_to_many", "many_to_one")
TARGET_TYPES = ("multi", "single")
BLANK_VALUES = {"", "none", "nan"}


class MappingError(ValueError):
    """Raised when the mapping file is invalid."""


def _is_blank(value) -> bool:
    return value is None or str(value).strip().lower() in BLANK_VALUES


@dataclass
class FacetRule:
    """One target facet (or final_qc) and how to compute it from source facets."""

    target: str
    sources: list[str]
    aggregate: str = "first"
    block: str = "one_to_one"


@dataclass
class Mapping:
    source_task: str
    source_pipeline: str | None
    target_task: str
    target_pipeline: str | None
    target_type: str
    scale: dict[str, str] | None
    rules: list[FacetRule] | None  # None means identity facet mapping
    unmapped_facets: str = "drop"

    def referenced_sources(self) -> set[str]:
        if self.rules is None:
            return set()
        return {s for r in self.rules for s in r.sources}


@dataclass
class Report:
    records: int = 0
    rows_in: int = 0
    rows_out: int = 0
    passthrough_rows: int = 0
    blank_cells: int = 0
    scale_remapped: Counter = field(default_factory=Counter)
    dropped_facets: Counter = field(default_factory=Counter)
    missing_facets: Counter = field(default_factory=Counter)
    ties: list[str] = field(default_factory=list)
    unmapped_values: Counter = field(default_factory=Counter)

    def warnings(self) -> list[str]:
        out = []
        if self.dropped_facets:
            out.append(f"Dropped unmapped source facets: {dict(self.dropped_facets)}")
        if self.missing_facets:
            out.append(f"Referenced source facets missing from records: {dict(self.missing_facets)}")
        if self.ties:
            out.append(f"Majority ties produced blank ratings ({len(self.ties)}): {self.ties[:10]}")
        if self.unmapped_values:
            out.append(f"Scale values passed through unmapped: {dict(self.unmapped_values)}")
        return out


# ---------------------------------------------------------------------------
# Mapping loading and validation
# ---------------------------------------------------------------------------


def _validate_aggregate(how: str, where: str) -> str:
    if how in ("majority", "first"):
        return how
    if how.startswith("any:") and how[4:].strip():
        return how
    raise MappingError(f"{where}: unknown aggregate '{how}' (expected 'majority', 'first' or 'any:<VALUE>')")


def _parse_facet_rules(facets: dict, target_type: str) -> list[FacetRule]:
    unknown = set(facets) - set(FACET_BLOCKS)
    if unknown:
        raise MappingError(f"Unknown facet block(s): {sorted(unknown)}; expected {list(FACET_BLOCKS)}")

    rules: list[FacetRule] = []
    for src, tgt in facets.get("one_to_one", {}).items():
        if not isinstance(tgt, str):
            raise MappingError(f"one_to_one['{src}'] must be a single facet name, got {tgt!r}")
        rules.append(FacetRule(target=tgt, sources=[src], block="one_to_one"))

    for src, tgts in facets.get("one_to_many", {}).items():
        if not isinstance(tgts, list) or not tgts or not all(isinstance(t, str) for t in tgts):
            raise MappingError(f"one_to_many['{src}'] must be a non-empty list of facet names")
        rules.extend(FacetRule(target=t, sources=[src], block="one_to_many") for t in tgts)

    for tgt, spec in facets.get("many_to_one", {}).items():
        if not isinstance(spec, dict) or not isinstance(spec.get("from"), list) or not spec["from"]:
            raise MappingError(f"many_to_one['{tgt}'] must be an object with a non-empty 'from' list")
        how = _validate_aggregate(spec.get("aggregate", "majority"), f"many_to_one['{tgt}']")
        rules.append(FacetRule(target=tgt, sources=list(spec["from"]), aggregate=how, block="many_to_one"))

    targets = Counter(r.target for r in rules)
    dupes = sorted(t for t, n in targets.items() if n > 1)
    if dupes:
        raise MappingError(f"Target facet(s) produced more than once: {dupes}")

    for r in rules:
        if ALL_FACETS in r.sources and (r.block != "many_to_one" or r.sources != [ALL_FACETS]):
            raise MappingError(f"'{ALL_FACETS}' may only appear alone in a many_to_one 'from' list ({r.target})")
        if FINAL_QC in r.sources and len(r.sources) > 1:
            raise MappingError(f"'{FINAL_QC}' cannot be combined with other source facets ({r.target})")

    if target_type == "single":
        if [r.target for r in rules] != [FINAL_QC]:
            raise MappingError(f"target.type 'single' requires exactly one rule whose target is '{FINAL_QC}'")
    elif FINAL_QC in targets:
        raise MappingError(f"'{FINAL_QC}' cannot be a target facet when target.type is 'multi'")
    return rules


def load_mapping(path) -> Mapping:
    with open(path) as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise MappingError("Mapping file must contain a JSON object")

    source = raw.get("source") or {}
    target = raw.get("target") or {}
    if not source.get("qc_task"):
        raise MappingError("'source.qc_task' is required")
    if not target.get("qc_task"):
        raise MappingError("'target.qc_task' is required")
    target_type = target.get("type", "multi")
    if target_type not in TARGET_TYPES:
        raise MappingError(f"'target.type' must be one of {TARGET_TYPES}, got '{target_type}'")

    scale = raw.get("scale")
    if scale is not None:
        if not isinstance(scale, dict):
            raise MappingError("'scale' must be an object mapping source values to target values")
        for k, v in scale.items():
            if not isinstance(v, str):
                raise MappingError(f"scale['{k}'] must map to a single value (one-to-many is ambiguous), got {v!r}")

    facets = raw.get("facets")
    rules = _parse_facet_rules(facets, target_type) if facets else None
    if rules is None and target_type == "single":
        raise MappingError("target.type 'single' requires a 'facets' section with a 'final_qc' rule")

    unmapped = raw.get("unmapped_facets", "drop")
    if unmapped not in ("drop", "keep"):
        raise MappingError("'unmapped_facets' must be 'drop' or 'keep'")
    if unmapped == "keep" and target_type == "single":
        raise MappingError("'unmapped_facets: keep' is not allowed with target.type 'single'")

    return Mapping(
        source_task=source["qc_task"],
        source_pipeline=source.get("pipeline"),
        target_task=target["qc_task"],
        target_pipeline=target.get("pipeline"),
        target_type=target_type,
        scale=scale,
        rules=rules,
        unmapped_facets=unmapped,
    )


def validate_against_qc_json(mapping: Mapping, qc_json_path) -> list[str]:
    """Validate the mapping against a target qc.json. Returns warnings; raises on errors."""
    with open(qc_json_path) as f:
        qc = json.load(f)
    if mapping.target_task not in qc:
        raise MappingError(f"target.qc_task '{mapping.target_task}' not found in {qc_json_path}")
    rating = qc[mapping.target_task].get("rating") or {}
    warnings = []

    qc_scale = rating.get("scale")
    if mapping.scale and qc_scale:
        bad = sorted(set(mapping.scale.values()) - set(qc_scale))
        if bad:
            raise MappingError(f"Mapped scale value(s) {bad} not in target scale {qc_scale}")

    qc_type = rating.get("type", "single")
    if qc_type != mapping.target_type:
        raise MappingError(f"target.type '{mapping.target_type}' does not match qc.json rating.type '{qc_type}'")

    for r in mapping.rules or []:
        if r.aggregate.startswith("any:") and qc_scale and r.aggregate[4:] not in qc_scale:
            raise MappingError(f"Aggregate '{r.aggregate}' for '{r.target}' uses a value not in target scale {qc_scale}")

    if qc_type == "multi" and mapping.rules is not None:
        qc_facets = rating.get("facets") or []
        produced = {r.target for r in mapping.rules}
        bad = sorted(produced - set(qc_facets))
        if bad:
            raise MappingError(f"Target facet(s) {bad} not defined in qc.json facets for '{mapping.target_task}'")
        if mapping.unmapped_facets == "drop":
            never = [f for f in qc_facets if f not in produced]
            if never:
                warnings.append(f"qc.json facets never produced by the mapping: {never}")
    return warnings


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------


def load_qc_status(path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[OUTPUT_COLUMNS]


def map_scale(value: str, scale: dict | None, passthrough: bool, report: Report) -> str:
    if _is_blank(value) or scale is None:
        return "" if _is_blank(value) else value
    if value in scale:
        if scale[value] != value:
            report.scale_remapped[f"{value}->{scale[value]}"] += 1
        return scale[value]
    if passthrough:
        report.unmapped_values[value] += 1
        return value
    raise MappingError(f"Rating value '{value}' has no entry in 'scale' (use --passthrough-unmapped-values to keep it)")


def aggregate(values: list[str], how: str) -> tuple[str, bool]:
    """Combine source values into one. Returns (value, is_tie)."""
    if how == "first":
        return next((v for v in values if not _is_blank(v)), ""), False
    if not values or any(_is_blank(v) for v in values):
        return "", False
    if how.startswith("any:") and how[4:] in values:
        return how[4:], False
    counts = Counter(values).most_common()
    if len(counts) > 1 and counts[0][1] == counts[1][1]:
        return "", True
    return counts[0][0], False


def derive_final_qc(ratings: dict[str, str]) -> str:
    """Generalized copy of SessionManager.derive_multifacet_final_qc (ui/managers/session_manager.py)."""
    values = [str(v).strip() for v in ratings.values()]
    if not values or any(_is_blank(v) for v in values):
        return ""
    if len(set(v.upper() for v in values)) == 1:
        return f"All-{values[0].title()}"
    return "Mixed"


def group_records(df_source: pd.DataFrame) -> list[dict]:
    """Group source rows into records: {key, facets: {name: value}, final_qc, meta}."""
    records = []
    for key, grp in df_source.groupby(RECORD_KEYS, sort=False):
        first = grp.iloc[0]
        facet_rows = grp[grp["facet"].str.strip() != ""]
        records.append(
            {
                "key": dict(zip(RECORD_KEYS, key)),
                "facets": dict(zip(facet_rows["facet"], facet_rows["rating_value"])),
                "final_qc": first["final_qc"] if facet_rows.empty else "",
                "meta": {c: first[c] for c in METADATA_COLUMNS},
            }
        )
    return records


def transform_record(record: dict, mapping: Mapping, passthrough: bool, report: Report) -> dict[str, str]:
    """Return {target_facet: value} (or {'final_qc': value} for single targets)."""
    source = {f: map_scale(v, mapping.scale, passthrough, report) for f, v in record["facets"].items()}
    final_qc = map_scale(record["final_qc"], mapping.scale, passthrough, report)

    if mapping.rules is None:
        return source if source else {FINAL_QC: final_qc}

    def lookup(name):
        if name == FINAL_QC:
            if record["facets"]:
                report.missing_facets[FINAL_QC] += 1
                return [""]
            return [final_qc]
        if name == ALL_FACETS:
            return list(source.values())
        if name not in source:
            report.missing_facets[name] += 1
            return [""]
        return [source[name]]

    out = {}
    for rule in mapping.rules:
        values = [v for s in rule.sources for v in lookup(s)]
        value, tie = aggregate(values, rule.aggregate)
        if tie:
            k = record["key"]
            report.ties.append(f"{k['participant_id']}/{k['session_id']}:{rule.target}")
        out[rule.target] = value

    referenced = mapping.referenced_sources()
    if ALL_FACETS not in referenced:
        for name, value in source.items():
            if name in referenced:
                continue
            if mapping.unmapped_facets == "keep":
                out.setdefault(name, value)
            else:
                report.dropped_facets[name] += 1
    return out


def _matches_source(df: pd.DataFrame, mapping: Mapping) -> pd.Series:
    mask = df["qc_task"] == mapping.source_task
    if mapping.source_pipeline:
        mask &= df["pipeline"] == mapping.source_pipeline
    return mask


def transform(df: pd.DataFrame, mapping: Mapping, passthrough_unmapped_values: bool = False) -> tuple[pd.DataFrame, Report]:
    report = Report(rows_in=len(df))
    df = df.drop_duplicates(subset=DEDUP_KEYS, keep="last")

    mask = _matches_source(df, mapping)
    df_source, df_other = df[mask], df[~mask]
    report.passthrough_rows = len(df_other)

    rows = []
    for record in group_records(df_source):
        report.records += 1
        ratings = transform_record(record, mapping, passthrough_unmapped_values, report)
        base = {
            **record["key"],
            **record["meta"],
            "qc_task": mapping.target_task,
            "pipeline": mapping.target_pipeline or record["key"]["pipeline"],
        }
        if mapping.target_type == "single" or set(ratings) == {FINAL_QC}:
            rows.append({**base, "final_qc": ratings[FINAL_QC], "facet": "", "rating_value": ""})
            report.blank_cells += int(_is_blank(ratings[FINAL_QC]))
            continue
        final_qc = derive_final_qc(ratings)
        for facet, value in ratings.items():
            rows.append({**base, "final_qc": final_qc, "facet": facet, "rating_value": value})
            report.blank_cells += int(_is_blank(value))

    df_out = pd.concat([df_other, pd.DataFrame(rows, columns=OUTPUT_COLUMNS)], ignore_index=True)
    df_out = df_out[OUTPUT_COLUMNS].fillna("")
    if not df_out.empty:
        df_out = df_out.sort_values(by=SORT_COLUMNS, kind="mergesort").reset_index(drop=True)
    report.rows_out = len(df_out)
    return df_out, report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Transform one qc_task in a qc_status.tsv using a JSON mapping.")
    parser.add_argument("--input", required=True, type=Path, help="Input qc_status.tsv")
    parser.add_argument("--mapping", required=True, type=Path, help="JSON mapping file")
    parser.add_argument("--output", required=True, type=Path, help="Output qc_status.tsv")
    parser.add_argument("--target-qc-json", type=Path, help="Target qc.json to validate the mapping against")
    parser.add_argument("--passthrough-unmapped-values", action="store_true", help="Keep rating values missing from 'scale' instead of failing")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the output file if it exists")
    parser.add_argument("--dry-run", action="store_true", help="Print the summary without writing output")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    if args.output.exists() and not args.overwrite and not args.dry_run:
        logger.error(f"Output file {args.output} exists; pass --overwrite to replace it")
        return 1

    try:
        mapping = load_mapping(args.mapping)
        warnings = validate_against_qc_json(mapping, args.target_qc_json) if args.target_qc_json else []
        df = load_qc_status(args.input)
        if not _matches_source(df, mapping).any():
            logger.error(f"No rows found for source qc_task '{mapping.source_task}' in {args.input}")
            return 1
        df_out, report = transform(df, mapping, args.passthrough_unmapped_values)
    except (MappingError, json.JSONDecodeError) as e:
        logger.error(str(e))
        return 1

    warnings += report.warnings()
    logger.info(f"{mapping.source_task} -> {mapping.target_task} ({mapping.target_type})")
    logger.info(f"Records transformed: {report.records}")
    logger.info(f"Rows in: {report.rows_in}, rows out: {report.rows_out} (passed through: {report.passthrough_rows})")
    logger.info(f"Blank ratings produced: {report.blank_cells}")
    if report.scale_remapped:
        logger.info(f"Scale remapped: {dict(report.scale_remapped)}")
    for w in warnings:
        logger.warning(w)

    if args.strict and warnings:
        logger.error("Warnings present and --strict set; no output written")
        return 1
    if args.dry_run:
        logger.info("Dry run; no output written")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(args.output, sep="\t", index=False)
    logger.info(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
