"""Example renderer for an experiment with IQM and image evidence.

Copy this folder for a new experiment, edit PACKAGE_TEMPLATE.md, and add any
experiment-specific artifact generation before building the template context.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sandbox.qc_package import (  # noqa: E402
    build_template_context,
    prepare_qc_data,
    render_markdown_template,
    write_shared_qc_data,
)


EXPERIMENT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_ROOT = REPO_ROOT / "sandbox" / "data" / "qc_inputs"
DEFAULT_SCAN_DIR = DEFAULT_DATA_ROOT / "sub-000103_acq-standard_T1w"
DEFAULT_TEMPLATE = EXPERIMENT_DIR / "PACKAGE_TEMPLATE.md"
DEFAULT_OUTPUT_DIR = EXPERIMENT_DIR / "package" / "sub-000103_acq-standard_T1w"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an MRI QC package with optional image evidence.")
    parser.add_argument("--scan-id", default="n/a")
    parser.add_argument("--participant-id", default="sub-000103")
    parser.add_argument("--session-id")
    parser.add_argument("--modality", default="T1w")
    parser.add_argument("--acquisition", default="standard")
    parser.add_argument(
        "--bids-json",
        default=DEFAULT_SCAN_DIR / "sub-000103_acq-standard_T1w.json",
        type=Path,
    )
    parser.add_argument(
        "--iqm-file",
        default=DEFAULT_SCAN_DIR / "sub-000103_acq-standard_T1w_mriqc.json",
        type=Path,
    )
    parser.add_argument(
        "--reference-tsv",
        default=REPO_ROOT / "reference_data" / "group_T1w.tsv",
        type=Path,
    )
    parser.add_argument(
        "--semantics-json",
        default=REPO_ROOT / "sandbox" / "iqms_context" / "tw1.json",
        type=Path,
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="Optional image artifact to reference from the rendered Markdown.",
    )
    parser.add_argument(
        "--shared-data-dir",
        type=Path,
        help="Directory for shared processed metadata.json and iqms.json. Defaults to the BIDS JSON parent.",
    )
    parser.add_argument("--template", default=DEFAULT_TEMPLATE, type=Path)
    parser.add_argument("--out-dir", default=DEFAULT_OUTPUT_DIR, type=Path)
    return parser.parse_args()


def render_image_section(image_path: Path | None) -> str:
    if image_path is None:
        return "No image artifact was provided for this package."

    return (
        f"Image artifact: `{image_path}`\n\n"
        "Use this image only as supporting evidence. Do not invent visual findings."
    )


def main() -> int:
    args = parse_args()

    qc_data = prepare_qc_data(
        bids_json=args.bids_json,
        iqm_file=args.iqm_file,
        reference_tsv=args.reference_tsv,
        semantics_json=args.semantics_json,
    )

    shared_data_dir = args.shared_data_dir or args.bids_json.parent
    write_shared_qc_data(shared_data_dir, qc_data)

    context = build_template_context(
        scan_id=args.scan_id,
        participant_id=args.participant_id,
        session_id=args.session_id,
        modality=args.modality,
        acquisition=args.acquisition,
        qc_data=qc_data,
        extra_context={
            "image_section": render_image_section(args.image),
        },
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.out_dir / "PACKAGE.md"
    output_path.write_text(
        render_markdown_template(args.template, context),
        encoding="utf-8",
    )

    print(f"Wrote shared metadata/IQMs to {shared_data_dir}")
    print(f"Wrote image evidence bundle to {output_path}")
    print(f"Loaded {len(qc_data['raw_iqms'])} numeric IQMs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
