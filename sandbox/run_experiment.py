"""
Run a minimal experiment with Claude on generated MRI QC evidence packages. 

expected package layout:
packages_dir/
    package_1/
        PACKAGE.md
        iqms.json
        metadata.json
        expected.json  (optional, not sent to Claude)

The runner sends PACKAGE.md to Claude, validates the response, and writes a results JSON file.

"""

from __future__ import annotations

import os
import argparse
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from anthropic import Anthropic

import build_package as bp
DEFAULT_MODEL = "claude-sonnet-4-6"

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


def build_prompt(package_dir: Path) -> str:
    package_md = (package_dir / "PACKAGE.md").read_text(encoding="utf-8")
    total = len(json.loads((package_dir / "iqms.json").read_text(encoding="utf-8"))["iqms"])
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
        help="Directory containing subdirectories of evidence packages.",
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
        help="Claude model name. Defaults to CLAUDE_MODEL or claude-sonnet-4-5.",
    )
    return parser.parse_args()

if __name__ == "__main__":

    args =  parser_args()
    package_dirs = discover_package_dirs(args.packages_dir)
    max_tokens = args.max_tokens
    model = args.model
    print(f"Found {len(package_dirs)} packages. Running experiment with model={model} and max_tokens={max_tokens}.")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = Anthropic(api_key=api_key)

    for package_dir in package_dirs:
        print(f"Processing package: {package_dir.name}")
        prompt = build_prompt(package_dir)
        response = call_claude(
            client=client,
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
        )
        write_results(package_dir, response)

