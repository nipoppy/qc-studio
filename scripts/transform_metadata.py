"""Remap rater metadata values in a qc_status.tsv using a JSON mapping.

Usage:
    python scripts/transform_metadata.py --input in_qc_status.tsv \\
        --mapping map.json (--output out_qc_status.tsv | --in-place [--backup])

The mapping remaps the values of the rater metadata columns
(rater_experience, rater_fatigue, rater_screen_size), optionally restricted
to rows matching a pipeline / qc_task / rater_id filter. All other columns and
rows are left untouched. This script is standalone (stdlib + pandas only). See
scripts/transform_metadata.md for the mapping schema.
"""

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger("transform_metadata")

METADATA_COLUMNS = ("rater_experience", "rater_fatigue", "rater_screen_size")
FILTER_KEYS = ("pipeline", "qc_task", "rater_id")
MAPPING_KEYS = {"filter", "columns", "allowed"}
BLANK_VALUES = {"", "none", "nan"}

# Mirrors ui/constants.py (EXPERIENCE_LEVELS, FATIGUE_LEVELS, SCREEN_SIZES)
ALLOWED_VALUES = {
    "rater_experience": ["Beginner (< 1 year)", "Intermediate (1-5 years)", "Expert (>5 years)"],
    "rater_fatigue": ["Not at all", "A bit tired ☕", "Very tired ☕☕"],
    "rater_screen_size": ["14 or less", "15-20", "21-25", "26-30", "31 or above", "Unknown"],
}


class MappingError(ValueError):
    """Raised when the mapping file is invalid."""


def _is_blank(value) -> bool:
    return value is None or str(value).strip().lower() in BLANK_VALUES


@dataclass
class Mapping:
    filter: dict[str, str]
    columns: dict[str, dict[str, str]]
    allowed: dict[str, list[str]]


@dataclass
class Report:
    rows_in: int = 0
    rows_matched: int = 0
    passthrough_rows: int = 0
    remapped: Counter = field(default_factory=Counter)
    filled_blanks: Counter = field(default_factory=Counter)
    unmapped_values: Counter = field(default_factory=Counter)
    disallowed_values: Counter = field(default_factory=Counter)

    def warnings(self) -> list[str]:
        out = []
        if self.unmapped_values:
            out.append(f"Values passed through unmapped: {dict(self.unmapped_values)}")
        if self.disallowed_values:
            out.append(f"Output values not in the allowed lists: {dict(self.disallowed_values)}")
        return out


# ---------------------------------------------------------------------------
# Mapping loading and validation
# ---------------------------------------------------------------------------


def load_mapping(path) -> Mapping:
    with open(path) as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise MappingError("Mapping file must contain a JSON object")
    unknown = set(raw) - MAPPING_KEYS
    if unknown:
        raise MappingError(f"Unknown top-level key(s): {sorted(unknown)}; expected {sorted(MAPPING_KEYS)}")

    filt = raw.get("filter") or {}
    if not isinstance(filt, dict):
        raise MappingError("'filter' must be an object")
    bad = sorted(set(filt) - set(FILTER_KEYS))
    if bad:
        raise MappingError(f"Unknown filter key(s): {bad}; expected {list(FILTER_KEYS)}")
    for k, v in filt.items():
        if not isinstance(v, str) or not v:
            raise MappingError(f"filter['{k}'] must be a non-empty string")

    columns = raw.get("columns")
    if not isinstance(columns, dict) or not columns:
        raise MappingError(f"'columns' is required and must map at least one of {list(METADATA_COLUMNS)}")
    bad = sorted(set(columns) - set(METADATA_COLUMNS))
    if bad:
        raise MappingError(f"Unknown column(s) in 'columns': {bad}; expected {list(METADATA_COLUMNS)}")
    for col, values in columns.items():
        if not isinstance(values, dict) or not values:
            raise MappingError(f"columns['{col}'] must be a non-empty object mapping source to target values")
        for k, v in values.items():
            if not isinstance(v, str):
                raise MappingError(f"columns['{col}']['{k}'] must map to a single string value, got {v!r}")

    allowed = {c: list(v) for c, v in ALLOWED_VALUES.items()}
    overrides = raw.get("allowed") or {}
    if not isinstance(overrides, dict):
        raise MappingError("'allowed' must be an object")
    for col, values in overrides.items():
        if col not in METADATA_COLUMNS:
            raise MappingError(f"Unknown column in 'allowed': '{col}'; expected {list(METADATA_COLUMNS)}")
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise MappingError(f"allowed['{col}'] must be a list of strings")
        allowed[col] = values

    return Mapping(filter=filt, columns=columns, allowed=allowed)


def validate_targets(mapping: Mapping) -> None:
    """Raise if a mapped target value is not in its column's allowed list."""
    for col, values in mapping.columns.items():
        bad = sorted(set(values.values()) - set(mapping.allowed[col]))
        if bad:
            raise MappingError(f"Target value(s) {bad} for '{col}' not in allowed values {mapping.allowed[col]}")


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------


def load_qc_status(path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    for col in (*FILTER_KEYS, *METADATA_COLUMNS):
        if col not in df.columns:
            df[col] = ""
    return df


def _matches_filter(df: pd.DataFrame, mapping: Mapping) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for key, value in mapping.filter.items():
        mask &= df[key] == value
    return mask


def map_value(value: str, column: str, values: dict[str, str], passthrough: bool, report: Report) -> str:
    if _is_blank(value):
        if "" in values:
            report.filled_blanks[f"{column}:->{values['']}"] += 1
            return values[""]
        return value
    if value in values:
        if values[value] != value:
            report.remapped[f"{column}:{value}->{values[value]}"] += 1
        return values[value]
    if value in values.values():  # already a target value, so re-runs are idempotent
        return value
    if passthrough:
        report.unmapped_values[f"{column}:{value}"] += 1
        return value
    raise MappingError(f"Value '{value}' in '{column}' has no mapping entry (use --passthrough-unmapped-values to keep it)")


def transform(df: pd.DataFrame, mapping: Mapping, passthrough_unmapped_values: bool = False) -> tuple[pd.DataFrame, Report]:
    df = df.copy()
    mask = _matches_filter(df, mapping)
    report = Report(rows_in=len(df), rows_matched=int(mask.sum()), passthrough_rows=int((~mask).sum()))

    for col, values in mapping.columns.items():
        df.loc[mask, col] = df.loc[mask, col].map(
            lambda v, col=col, values=values: map_value(v, col, values, passthrough_unmapped_values, report)
        )

    for col in METADATA_COLUMNS:
        out = df.loc[mask, col]
        for value in out[~out.map(_is_blank) & ~out.isin(mapping.allowed[col])]:
            report.disallowed_values[f"{col}:{value}"] += 1
    return df, report


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_tsv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, sep="\t", index=False)


def write_in_place(df: pd.DataFrame, path: Path) -> None:
    """Write atomically: temp file in the same directory, then os.replace."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    try:
        write_tsv(df, Path(tmp))
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Remap rater metadata values in a qc_status.tsv using a JSON mapping.")
    parser.add_argument("--input", required=True, type=Path, help="Input qc_status.tsv")
    parser.add_argument("--mapping", required=True, type=Path, help="JSON mapping file")
    dest = parser.add_mutually_exclusive_group(required=True)
    dest.add_argument("--output", type=Path, help="Output qc_status.tsv")
    dest.add_argument("--in-place", action="store_true", help="Rewrite the input file in place")
    parser.add_argument("--backup", action="store_true", help="With --in-place, copy the original to <input>.bak first")
    parser.add_argument("--skip-allowed-check", action="store_true", help="Do not check mapped values against the allowed lists")
    parser.add_argument("--passthrough-unmapped-values", action="store_true", help="Keep values missing from the mapping instead of failing")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite an existing output (or .bak) file")
    parser.add_argument("--dry-run", action="store_true", help="Print the summary without writing output")
    args = parser.parse_args(argv)
    if args.backup and not args.in_place:
        parser.error("--backup requires --in-place")
    return args


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)
    backup = args.input.with_name(args.input.name + ".bak")

    if not args.dry_run:
        if args.output and args.output.exists() and not args.overwrite:
            logger.error(f"Output file {args.output} exists; pass --overwrite to replace it")
            return 1
        if args.backup and backup.exists() and not args.overwrite:
            logger.error(f"Backup file {backup} exists; pass --overwrite to replace it")
            return 1

    try:
        mapping = load_mapping(args.mapping)
        if not args.skip_allowed_check:
            validate_targets(mapping)
        df = load_qc_status(args.input)
        if not _matches_filter(df, mapping).any():
            logger.error(f"No rows match filter {mapping.filter} in {args.input}")
            return 1
        df_out, report = transform(df, mapping, args.passthrough_unmapped_values)
    except (MappingError, json.JSONDecodeError) as e:
        logger.error(str(e))
        return 1

    warnings = report.warnings()
    logger.info(f"Rows in: {report.rows_in}, matched: {report.rows_matched} (passed through: {report.passthrough_rows})")
    if report.remapped:
        logger.info(f"Remapped: {dict(report.remapped)}")
    if report.filled_blanks:
        logger.info(f"Filled blanks: {dict(report.filled_blanks)}")
    for w in warnings:
        logger.warning(w)

    if args.strict and warnings:
        logger.error("Warnings present and --strict set; no output written")
        return 1
    if args.dry_run:
        logger.info("Dry run; no output written")
        return 0

    if args.in_place:
        if args.backup:
            shutil.copy2(args.input, backup)
            logger.info(f"Backed up original to {backup}")
        write_in_place(df_out, args.input)
        logger.info(f"Rewrote {args.input} in place")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_tsv(df_out, args.output)
        logger.info(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
