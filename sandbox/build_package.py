"""Build a minimal MRI QC evidence package from real BIDS/MRIQC files.

Outputs:
- metadata.json: selected + full BIDS sidecar metadata
- iqms.json: all numeric MRIQC IQMs with percentile/z-score and optional semantics
- PACKAGE.md: compact model-readable package summary
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from requests import session


BIDS_METADATA_FIELDS = [
    "Manufacturer",
    "ManufacturersModelName",
    "MagneticFieldStrength",
    "ScanningSequence",
    "SequenceVariant",
    "MRAcquisitionType",
    "RepetitionTime",
    "EchoTime",
    "InversionTime",
    "FlipAngle",
    "ReceiveCoilName",
    "PhaseEncodingDirection",
    "SliceEncodingDirection",
]


ALWAYS_HIGHLIGHT_T1W = {
    "snr_total",
    "snr_gm",
    "snr_wm",
    "cjv",
    "cnr",
    "efc",
    "fber",
    "fwhm_avg",
    "qi_1",
    "qi_2",
    "wm2max",
    "inu_range",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at {path}, got {type(data)}")

    return data


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def numeric_values(data: dict[str, Any]) -> dict[str, float]:
    values = {}

    for key, value in data.items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue

        if np.isfinite(number):
            values[key] = number

    return values


def read_table(path: Path) -> pd.DataFrame:
    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    return pd.read_csv(path, sep=sep)


def select_metadata(sidecar: dict[str, Any]) -> dict[str, Any]:
    return {
        key: sidecar[key]
        for key in BIDS_METADATA_FIELDS
        if key in sidecar and sidecar[key] not in (None, "")
    }


def load_subject_iqms(iqm_path: Path) -> dict[str, float]:
    """Load subject-level MRIQC IQMs from JSON or one-row TSV/CSV."""
    if iqm_path.suffix.lower() == ".json":
        return numeric_values(load_json(iqm_path))

    df = read_table(iqm_path)

    if df.empty:
        return {}

    return numeric_values(df.iloc[0].to_dict())


def load_reference_iqms(reference_path: Path) -> pd.DataFrame:
    return read_table(reference_path)


_UNKNOWN_VALUES = {"", "unknown", "n/a", "none"}
_STRATIFY_FIELDS = ["Manufacturer", "MagneticFieldStrength", "ManufacturersModelName"]


def _is_known(value: Any) -> bool:
    return value is not None and str(value).strip().lower() not in _UNKNOWN_VALUES


def filter_reference_by_metadata(
    reference_df: pd.DataFrame,
    subject_metadata: dict[str, Any],
) -> pd.DataFrame:
    """Narrow the reference population to match (or complement) subject scanner metadata.

    For each stratification field:
    - Subject value known  → keep reference rows where the field matches.
    - Subject value unknown → keep reference rows where the field is flagged unknown.
    Falls back to the unfiltered slice if the match would produce an empty result.
    """
    df = reference_df

    for field in _STRATIFY_FIELDS:
        if field not in df.columns:
            continue

        subject_value = subject_metadata.get(field)

        if _is_known(subject_value):
            mask = df[field].astype(str).str.strip() == str(subject_value).strip()
        else:
            mask = df[field].astype(str).str.strip().str.lower().isin(_UNKNOWN_VALUES)

        filtered = df[mask]
        if not filtered.empty:
            df = filtered

    return df


def compute_reference_stats(
    metric_name: str,
    value: float,
    reference_df: pd.DataFrame,
) -> dict[str, float | None]:
    """Compute percentile and z-score for one IQM."""
    if metric_name not in reference_df.columns:
        return {"percentile": None, "z_score": None}

    ref = pd.to_numeric(reference_df[metric_name], errors="coerce").dropna().to_numpy()

    if ref.size == 0:
        return {"percentile": None, "z_score": None}

    ref_mean = float(np.mean(ref))
    ref_std = float(np.std(ref, ddof=0))

    percentile = float(100 * np.mean(ref <= value))
    z_score = None if ref_std == 0 else float((value - ref_mean) / ref_std)

    return {
        "percentile": round(percentile, 3),
        "z_score": None if z_score is None else round(z_score, 3),
    }


def load_semantics(semantics_path: Path | None) -> dict[str, Any]:
    if semantics_path is None:
        return {"metrics": {}, "metric_patterns": {}}

    data = load_json(semantics_path)

    return {
        "metrics": data.get("metrics", {}),
        "metric_patterns": data.get("metric_patterns", {}),
    }


def lookup_semantics(metric_name: str, catalog: dict[str, Any]) -> dict[str, Any] | None:
    """Find exact or pattern-based semantic context for one metric."""
    if metric_name in catalog["metrics"]:
        return catalog["metrics"][metric_name]

    for pattern, entry in catalog["metric_patterns"].items():
        if pattern.endswith("*") and metric_name.startswith(pattern[:-1]):
            return entry

    return None


def enrich_iqms(
    subject_iqms: dict[str, float],
    reference_df: pd.DataFrame,
    semantics_catalog: dict[str, Any],
    subject_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Attach reference stats and optional semantic context to every IQM."""
    filtered_ref = filter_reference_by_metadata(reference_df, subject_metadata or {})
    enriched = []

    for metric_name, value in sorted(subject_iqms.items()):
        item: dict[str, Any] = {
            "name": metric_name,
            "value": value,
            "reference_stats": compute_reference_stats(
                metric_name=metric_name,
                value=value,
                reference_df=filtered_ref,
            ),
        }

        semantics = lookup_semantics(metric_name, semantics_catalog)
        if semantics is not None:
            item["semantic_context"] = {k: v for k, v in semantics.items() if k != "matches"}

        enriched.append(item)

    return enriched


def should_highlight_iqm(iqm: dict[str, Any], modality: str) -> bool:
    name = iqm["name"]
    percentile = iqm["reference_stats"].get("percentile")
    z_score = iqm["reference_stats"].get("z_score")

    if modality.lower() == "t1w" and name in ALWAYS_HIGHLIGHT_T1W:
        return True

    if percentile is not None and (percentile <= 10 or percentile >= 90):
        return True

    if z_score is not None and abs(z_score) >= 1.5:
        return True

    return False


def format_optional(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def render_metadata_table(selected_metadata: dict[str, Any]) -> str:
    if not selected_metadata:
        return "| n/a | n/a |"

    return "\n".join(
        f"| `{key}` | `{value}` |"
        for key, value in selected_metadata.items()
    )


def render_iqm_table(iqms: list[dict[str, Any]], modality: str) -> str:
    highlighted = [
        iqm for iqm in iqms
        if should_highlight_iqm(iqm, modality)
    ]

    if not highlighted:
        return "| n/a | n/a | n/a | n/a | n/a | No highlighted IQMs. |"

    rows = []

    for iqm in highlighted:
        stats = iqm["reference_stats"]
        semantics = iqm.get("semantic_context", {})
        if semantics.get("evidence_strength") == "none":
            continue

        rows.append(
            "| `{name}` | {value} | {percentile} | {z_score} | {direction} | {interpretation} | {caveats} | {evidence_strength} |".format(
                name=iqm["name"],
                value=round(iqm["value"], 6),
                percentile=format_optional(stats.get("percentile")),
                z_score=format_optional(stats.get("z_score")),
                direction=semantics.get("direction_of_concern", ""),
                interpretation=semantics.get("qc_interpretation", ""),
                caveats="; ".join(semantics.get("caveats", [])) or "None",
                evidence_strength=semantics.get("evidence_strength", "unknown"),
            )
        )

    return "\n".join(rows)

def extract_provenance_warnings(raw_iqm_data: dict[str, Any]) -> dict[str, bool]:
    provenance = raw_iqm_data.get("provenance", {})
    if not isinstance(provenance, dict):
        return {}
    warnings = provenance.get("warnings", {})
    return {k: v for k, v in warnings.items() if isinstance(v, bool)}


def render_warnings_section(warnings: dict[str, bool]) -> str:
    if not warnings:
        return "No provenance warnings."
    return "\n".join(
        f"- `{key}`: {'**true**' if value else 'false'}"
        for key, value in sorted(warnings.items())
    )


def render_package_md(
    *,
    template_path: Path,
    scan_id: str,
    participant_id: str,
    session_id: str | None,
    modality: str,
    acquisition: str | None,
    selected_metadata: dict[str, Any],
    iqms: list[dict[str, Any]],
    provenance_warnings: dict[str, bool],
) -> str:
    if not scan_id:
        scan_id = "n/a"
    context = {
        "scan_id": scan_id,
        "participant_id": participant_id,
        "session_id": session_id or "n/a",
        "modality": modality,
        "acquisition": acquisition or "n/a",
        "metadata_table": render_metadata_table(selected_metadata),
        "iqm_table": render_iqm_table(iqms, modality),
        "warnings_section": render_warnings_section(provenance_warnings),
    }

    template = template_path.read_text(encoding="utf-8")
    return template.format(**context)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a minimal MRI QC evidence package.")
    # parser.add_argument("--scan-id", required=True)
    parser.add_argument("--scan-id", default="n/a")
    parser.add_argument("--participant-id", required=True)
    parser.add_argument("--session-id")
    parser.add_argument("--modality", required=True)
    parser.add_argument("--acquisition")
    parser.add_argument("--bids-json", required=True, type=Path)
    parser.add_argument("--iqm-file", required=True, type=Path)
    parser.add_argument("--reference-tsv", required=True, type=Path)
    parser.add_argument("--semantics-json", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    sidecar = load_json(args.bids_json)
    selected_metadata = select_metadata(sidecar)
    raw_iqm_data = load_json(args.iqm_file)
    provenance_warnings = extract_provenance_warnings(raw_iqm_data)
    raw_iqms = numeric_values(raw_iqm_data)
    reference_columns = load_reference_iqms(args.reference_tsv)
    semantics_catalog = load_semantics(args.semantics_json)
    enriched_iqms = enrich_iqms(raw_iqms, reference_columns, semantics_catalog)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        args.out_dir / "metadata.json",
        {
            "selected": selected_metadata,
            "full_sidecar": sidecar,
        },
    )
    write_json(args.out_dir / "iqms.json", {"iqms": enriched_iqms})
    (args.out_dir / "PACKAGE.md").write_text(
        render_package_md(
            scan_id=args.scan_id,
            participant_id=args.participant_id,
            session_id=args.session_id,
            modality=args.modality,
            acquisition=args.acquisition,
            selected_metadata=selected_metadata,
            iqms=enriched_iqms,
            provenance_warnings=provenance_warnings,
            template_path=Path(__file__).parent / "PACKAGE_TEMPLATE.md",
        ),
        encoding="utf-8",
    )

    print(f"Wrote evidence package to {args.out_dir}")
    print(f"Loaded {len(raw_iqms)} numeric IQMs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
