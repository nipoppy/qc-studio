"""
Run a minimal experiment with Claude on generated MRI QC evidence packages. 

expected package layout:
packages_dir/
    package_1/
        PACKAGE.md
        expected.json  (optional, not sent to Claude)

shared_data_dir/
    package_1/
        iqms.json
        metadata.json

The runner sends PACKAGE.md to Claude, validates the response, and writes a results JSON file.

"""

from __future__ import annotations

import os
import argparse
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_PACKAGES_DIR = Path(__file__).resolve().parent / "package"
DEFAULT_SHARED_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "qc_inputs"

class QCDecision(BaseModel):
    decision: Literal["pass", "fail", "uncertain"]
    confidence:  Literal["high", "medium", "low"]
    summary: str
    flagged_metrics: list[str]
    reasons: list[str]
    recommended_followup: list[str]


def discover_package_dirs(package_dir:Path) -> list[Path]:
    package_dirs = [
        path for path in package_dir.iterdir()
        if path.is_dir() and (path / "PACKAGE.md").exists()    
    ]
    return sorted(package_dirs)


def build_prompt(package_dir: Path, shared_data_dir: Path) -> str:
    package_md = (package_dir / "PACKAGE.md").read_text(encoding="utf-8")
    iqms_path = shared_data_dir / package_dir.name / "iqms.json"
    if not iqms_path.exists():
        raise FileNotFoundError(f"Shared IQM data not found for {package_dir.name}: {iqms_path}")

    total = len(json.loads(iqms_path.read_text(encoding="utf-8"))["iqms"])
    return f"{package_md}\n\n*{total} IQMs were computed in total; only flagged ones appear in the table above.*\n"
   

def call_claude(client: Anthropic, prompt: str, model: str = DEFAULT_MODEL, max_tokens: int = 800) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=1.0,
        system=(
            "You are an expert MRI quality control (QC) assistant. "
            "Given a package of QC evidence for a single MRI scan, "
            "your task is to make a final QC decision (pass/fail/uncertain) based on the evidence, "
            "and provide a summary explanation along with any relevant details."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def normalize_response_json(raw_response: str) -> str:
    stripped = raw_response.strip()

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    return stripped


def validate_response(response: str) -> tuple[bool, dict[str, Any]]:
    normalized_response = normalize_response_json(response)

    try:
        decision = QCDecision.model_validate_json(normalized_response)

    except ValidationError as e:
        print(f"Response validation failed: {e}")
        return False, {
            "error": "Response validation failed",
            "details": e.errors(),
            "raw_response": response,
        }

    return True, decision.model_dump()


def write_results(package_dir: Path, response: str) -> None:
    success, data = validate_response(response)

    if not success:
        result_path = package_dir / "result_error.json"
        result_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Wrote validation error details to {result_path}")
    else:
        result_path = package_dir / "result.json"
        result_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Wrote QC decision to {result_path}")


def parser_args() ->argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run QC decision experiment with Claude.")
    parser.add_argument(
        "--packages_dir",
        type=Path,
        default=DEFAULT_PACKAGES_DIR,
        help="Directory containing subdirectories of evidence packages.",
    )
    parser.add_argument(
        "--shared-data-dir",
        type=Path,
        default=DEFAULT_SHARED_DATA_DIR,
        help="Directory containing shared per-scan metadata.json and iqms.json files.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=800,
        help="Maximum output tokens per Claude response.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL),
        help=f"Claude model name. Defaults to CLAUDE_MODEL or {DEFAULT_MODEL}.",
    )
    return parser.parse_args()

if __name__ == "__main__":

    args =  parser_args()
    package_dirs = discover_package_dirs(args.packages_dir)
    shared_data_dir = args.shared_data_dir
    max_tokens = args.max_tokens
    model = args.model
    print(f"Found {len(package_dirs)} packages. Running experiment with model={model} and max_tokens={max_tokens}.")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set; export it before running this experiment.")

    try:
        from anthropic import Anthropic
    except ModuleNotFoundError as error:
        raise SystemExit(
            "Missing dependency 'anthropic'. Install it before running this experiment."
        ) from error

    client = Anthropic(api_key=api_key)

    for package_dir in package_dirs:
        print(f"Processing package: {package_dir.name}")
        prompt = build_prompt(package_dir, shared_data_dir)
        response = call_claude(
            client=client,
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
        )
        write_results(package_dir, response)
