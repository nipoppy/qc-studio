"""Admin dashboard plumbing: CLI args, the access gate, shared context and cached loaders."""

from __future__ import annotations

import os
import sys
from argparse import ArgumentParser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from utils import identity
from utils.assignments import read_participant_list
from utils.cache import file_signature, files_signature
from utils.config import PIPELINE_KEY, list_qc_tasks_from_json, qc_pipeline_from_json
from utils.ratings_report import collate_ratings, participant_level
from utils.user_config import ADMIN, UsersConfig, UsersConfigError, dashboard_role, load_users_config

UI_DIR = Path(__file__).resolve().parent.parent


@dataclass
class AdminContext:
    users_config: Path  # resolved path of the users config
    participant_list: Path  # dataset-level participant pool
    pool: pd.DataFrame  # its participant_id (and session_id) rows, read once per run
    output_dir: Path | None  # where "Save reports" writes (None = downloads only)
    session_list: str | None  # the --session_list the rater app is launched with
    email: str  # the signed-in admin or viewer
    cfg: UsersConfig
    qc_pipeline: str = ""  # pipeline of the expected tasks (the rater app's --qc_pipeline)
    qc_json: Path | None = None  # the pipeline's qc.json: the prescription of tasks raters are expected to do
    expected_tasks: list[str] = field(default_factory=list)  # task keys from qc.json, file order
    role: str = ADMIN  # ADMIN (full access) or VIEWER (view only)

    @property
    def pool_ids(self) -> list[str]:
        """Unique dataset participant IDs, in file order."""
        return self.pool["participant_id"].unique().tolist()

    @property
    def can_edit(self) -> bool:
        """Only admins write: rater edits, participant lists, saved reports."""
        return self.role == ADMIN


def parse_admin_args(argv=None):
    parser = ArgumentParser("QC-Studio admin")
    parser.add_argument("--users_config", required=True, help="Users config (users.json) with top-level 'admins' (and optional 'viewers') lists")
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
    return parser.parse_args(argv)


def log_admin_action(email: str, message: str) -> None:
    """Audit line on stderr for every write the dashboard performs."""
    print(f"QC-Studio admin [{datetime.now().isoformat(timespec='seconds')}] {email}: {message}", file=sys.stderr, flush=True)


def require_dashboard_access(users_config: str | Path) -> tuple[str, UsersConfig, str]:
    """Return ``(email, config, role)`` for an admin or viewer; otherwise show an error and stop the script."""
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
    role = dashboard_role(user.email, cfg)
    if role is None:
        print(f"QC-Studio admin: access denied for {user.email}", file=sys.stderr)
        st.error(f"**{user.email}** is not a QC-Studio admin or viewer.")
        st.stop()
    return user.email, cfg, role


def require_editor(ctx: AdminContext) -> None:
    """Guard in front of every write: a viewer is refused (the UI also hides write controls from them)."""
    if not ctx.can_edit:
        print(f"QC-Studio admin: write refused for viewer {ctx.email}", file=sys.stderr)
        st.error("View-only access: only admins can make changes.")
        st.stop()


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


ENV_QC_PIPELINE = "QC_PIPELINE"  # same as admin_launch.sh's variable; may also come from .env


def resolve_qc_pipeline(cli_value: str | None, qc_json: Path, env: dict | None = None) -> str:
    """The pipeline of the expected tasks: ``qc.json``'s ``__pipeline__`` key, else ``--qc_pipeline``, else ``$QC_PIPELINE``.

    Raises ValueError when none names one, or when qc.json and the given value disagree (case-insensitive).
    """
    env = os.environ if env is None else env
    from_json = qc_pipeline_from_json(qc_json)
    given = str(cli_value or "").strip() or str(env.get(ENV_QC_PIPELINE) or "").strip() or None
    if from_json and given and from_json.lower() != given.lower():
        raise ValueError(f"`--qc_pipeline`/`{ENV_QC_PIPELINE}` {given!r} does not match `{PIPELINE_KEY}` {from_json!r} in `{qc_json}`")
    pipeline = from_json or given
    if not pipeline:
        raise ValueError(
            f'no pipeline: pass `--qc_pipeline`, set `{ENV_QC_PIPELINE}` (shell or .env), or add `"{PIPELINE_KEY}": "<pipeline>"` to `{qc_json}`'
        )
    return pipeline


def build_context(args, email: str, cfg: UsersConfig, role: str = ADMIN) -> AdminContext:
    """Shared context for every tab; shows an error and stops when qc.json or the dataset list is unusable."""
    qc_json = resolve_qc_json(args.qc_json)
    participant_list = Path(args.participant_list).expanduser().resolve()
    try:
        tasks = expected_tasks(qc_json, args.qc_task)
        pipeline = resolve_qc_pipeline(args.qc_pipeline, qc_json)
    except ValueError as exc:
        st.error(f"QC tasks could not be loaded: {exc}")
        st.stop()
    try:
        pool = read_participant_list(participant_list)
    except (OSError, ValueError) as exc:
        st.error(f"Dataset participant list cannot be read: {exc}")
        st.stop()
    return AdminContext(
        users_config=Path(cfg.path).resolve(),
        participant_list=participant_list,
        pool=pool,
        output_dir=Path(args.output_dir).expanduser().resolve() if args.output_dir else None,
        session_list=args.session_list,
        email=email,
        cfg=cfg,
        qc_pipeline=pipeline,
        qc_json=qc_json,
        expected_tasks=tasks,
        role=role,
    )


def to_tsv_bytes(df: pd.DataFrame, index: bool = False) -> bytes:
    return df.to_csv(sep="\t", index=index).encode("utf-8")


def ratings_signature(cfg: UsersConfig) -> tuple:
    """Signature of every rating file, so cached reports refresh when a rater saves."""
    dirs = [d for u in cfg.users.values() for d in (Path(u["out_dir"]), Path(u["out_dir"]) / "checkpoints")]
    return files_signature(sorted(p for d in dirs for p in d.glob("*.tsv")))


@st.cache_data(show_spinner="Collating ratings…", max_entries=8)
def _collate(config_sig: tuple, ratings_sig: tuple, prefer_transformed: bool):
    """Cached on the config and on every rating file's mtime, so a rater's save refreshes it."""
    col = collate_ratings(config_sig[0], prefer_transformed=prefer_transformed)
    return col, participant_level(col.ratings)


def cached_ratings(ctx: AdminContext, prefer_transformed: bool = True):
    """``(collation, participant_level_ratings)`` of every rater (see :mod:`utils.ratings_report`), shared by all tabs."""
    return _collate(file_signature(ctx.users_config), ratings_signature(ctx.cfg), prefer_transformed)
