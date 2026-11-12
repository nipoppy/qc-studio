"""Admin dashboard plumbing: CLI args, the admin gate, shared context and cached loaders."""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from utils import identity
from utils.config import PIPELINE_KEY, list_qc_tasks_from_json, qc_pipeline_from_json
from utils.ratings_report import collate_ratings
from utils.user_config import UsersConfig, UsersConfigError, is_admin, load_users_config

ADMIN_URL_ENV = "QC_STUDIO_ADMIN_URL"
UI_DIR = Path(__file__).resolve().parent.parent


@dataclass
class AdminContext:
    users_config: Path  # resolved path of the users config
    participant_list: Path  # dataset-level participant pool
    output_dir: Path | None  # where "Save reports" writes (None = downloads only)
    session_list: str | None  # the --session_list the rater app is launched with
    admin_email: str
    cfg: UsersConfig
    qc_pipeline: str = ""  # pipeline of the expected tasks (the rater app's --qc_pipeline)
    qc_json: Path | None = None  # the pipeline's qc.json: the prescription of tasks raters are expected to do
    expected_tasks: list[str] = field(default_factory=list)  # task keys from qc.json, file order


def parse_admin_args(argv=None):
    parser = ArgumentParser("QC-Studio admin")
    parser.add_argument("--users_config", required=True, help="Users config (users.json) with a top-level 'admins' list")
    parser.add_argument("--participant_list", required=True, help="Dataset-level participant pool (TSV with participant_id)")
    parser.add_argument("--output_dir", default=None, help="Folder for report TSVs written by 'Save reports' (optional)")
    parser.add_argument("--session_list", default=None, help="The --session_list the rater app is launched with (for setup checks)")
    parser.add_argument(
        "--qc_pipeline",
        default=None,
        help=f"Pipeline the raters QC, e.g. fsqc. Optional when qc.json names it in {PIPELINE_KEY!r}; must match it if both are given",
    )
    parser.add_argument(
        "--qc_json",
        required=True,
        help="The pipeline's qc.json (as the rater app's --qc_json); its tasks are the ones raters are expected to complete",
    )
    parser.add_argument("--qc_task", default="all", help="Expected task(s): 'all' tasks in qc.json (default) or a comma-separated subset")
    return parser.parse_args(argv if argv is not None else sys.argv[1:])


def log_admin_action(email: str, message: str) -> None:
    """Audit line on stderr for every write the dashboard performs."""
    print(f"QC-Studio admin [{datetime.now().isoformat(timespec='seconds')}] {email}: {message}", file=sys.stderr, flush=True)


def require_admin(users_config: str | Path) -> tuple[str, UsersConfig]:
    """Return ``(email, config)`` for an admin; otherwise show an error and stop the script."""
    try:
        user = identity.get_current_user()
    except identity.IdentityError as exc:
        st.error(f"QC-Studio identity configuration error: {exc}")
        st.stop()
    if user is None:
        st.error("Could not determine who you are. The admin dashboard must be accessed through its Cloudflare Access protected URL.")
        st.stop()
    try:
        cfg = load_users_config(users_config)
    except UsersConfigError as exc:
        print(f"QC-Studio admin: {exc}", file=sys.stderr)
        st.error(f"The users config could not be loaded: {exc}")
        st.stop()
    if not is_admin(user.email, cfg):
        print(f"QC-Studio admin: access denied for {user.email}", file=sys.stderr)
        st.error(f"**{user.email}** is not a QC-Studio admin.")
        st.stop()
    return user.email, cfg


def resolve_qc_json(path: str) -> Path:
    """``--qc_json`` as given, else relative to ``ui/`` like the rater app (e.g. ``../pipelines/fsqc/qc.json``)."""
    p = Path(path).expanduser()
    if not p.is_absolute() and not p.is_file():
        p = UI_DIR / p
    return p.resolve()


def expected_tasks(qc_json: Path, qc_task: str = "all") -> list[str]:
    """Task keys raters are expected to complete; raises ValueError for an unusable qc.json or unknown tasks."""
    tasks = list_qc_tasks_from_json(qc_json)
    if not tasks:
        raise ValueError(f"no QC tasks found in {qc_json} (missing file, invalid JSON, or not a JSON object)")
    if str(qc_task or "all").strip().lower() == "all":
        return tasks
    wanted = [t.strip() for t in str(qc_task).split(",") if t.strip()]
    unknown = [t for t in wanted if t not in tasks]
    if unknown:
        raise ValueError(f"--qc_task {', '.join(unknown)} not in {qc_json} (tasks: {', '.join(tasks)})")
    return wanted


def resolve_qc_pipeline(cli_value: str | None, qc_json: Path) -> str:
    """The pipeline of the expected tasks: ``qc.json``'s ``__pipeline__`` key, else ``--qc_pipeline``.

    Raises ValueError when neither names one, or when they disagree (case-insensitive).
    """
    from_json = qc_pipeline_from_json(qc_json)
    from_cli = str(cli_value or "").strip() or None
    if from_json and from_cli and from_json.lower() != from_cli.lower():
        raise ValueError(f"--qc_pipeline {from_cli!r} does not match {PIPELINE_KEY} {from_json!r} in {qc_json}")
    pipeline = from_json or from_cli
    if not pipeline:
        raise ValueError(f'no pipeline: pass --qc_pipeline or add "{PIPELINE_KEY}": "<pipeline>" to {qc_json}')
    return pipeline


def build_context(args, admin_email: str, cfg: UsersConfig) -> AdminContext:
    """Shared context for every tab; shows an error and stops when the qc.json prescription is unusable."""
    qc_json = resolve_qc_json(args.qc_json)
    try:
        tasks = expected_tasks(qc_json, args.qc_task)
        pipeline = resolve_qc_pipeline(args.qc_pipeline, qc_json)
    except ValueError as exc:
        st.error(f"QC tasks could not be loaded: {exc}")
        st.stop()
    return AdminContext(
        users_config=Path(cfg.path).resolve(),
        participant_list=Path(args.participant_list).expanduser().resolve(),
        output_dir=Path(args.output_dir).expanduser().resolve() if args.output_dir else None,
        session_list=args.session_list,
        admin_email=admin_email,
        cfg=cfg,
        qc_pipeline=pipeline,
        qc_json=qc_json,
        expected_tasks=tasks,
    )


def to_tsv_bytes(df: pd.DataFrame, index: bool = False) -> bytes:
    return df.to_csv(sep="\t", index=index).encode("utf-8")


def ratings_signature(cfg: UsersConfig) -> tuple:
    """(path, mtime) of every rating file, so cached reports refresh when a rater saves."""
    sig = []
    for u in cfg.users.values():
        out = Path(u["out_dir"])
        for p in list(out.glob("*.tsv")) + list((out / "checkpoints").glob("*.tsv")):
            try:
                sig.append((str(p), p.stat().st_mtime_ns))
            except OSError:
                continue
    return tuple(sorted(sig))


def file_signature(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


@st.cache_data(show_spinner="Collating ratings…", max_entries=8)
def _collate(config_path: str, config_mtime: int, signature: tuple, prefer_transformed: bool):
    """Cached on the config and on every rating file's mtime, so a rater's save refreshes it."""
    return collate_ratings(config_path, prefer_transformed=prefer_transformed)


def cached_collation(ctx: AdminContext, prefer_transformed: bool = True):
    """Every rater's current ratings (:func:`utils.ratings_report.collate_ratings`), shared by all tabs."""
    return _collate(str(ctx.users_config), file_signature(ctx.users_config), ratings_signature(ctx.cfg), prefer_transformed)


def clear_collation_cache() -> None:
    _collate.clear()
