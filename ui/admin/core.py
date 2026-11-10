"""Admin dashboard plumbing: CLI args, the admin gate, shared context and cached loaders."""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from utils import identity
from utils.user_config import UsersConfig, UsersConfigError, is_admin, load_users_config

ADMIN_URL_ENV = "QC_STUDIO_ADMIN_URL"


@dataclass
class AdminContext:
    users_config: Path  # resolved path of the users config
    participant_list: Path  # dataset-level participant pool
    output_dir: Path | None  # where "Save reports" writes (None = downloads only)
    session_list: str | None  # the --session_list the rater app is launched with
    admin_email: str
    cfg: UsersConfig


def parse_admin_args(argv=None):
    parser = ArgumentParser("QC-Studio admin")
    parser.add_argument("--users_config", required=True, help="Users config (users.json) with a top-level 'admins' list")
    parser.add_argument("--participant_list", required=True, help="Dataset-level participant pool (TSV with participant_id)")
    parser.add_argument("--output_dir", default=None, help="Folder for report TSVs written by 'Save reports' (optional)")
    parser.add_argument("--session_list", default=None, help="The --session_list the rater app is launched with (for setup checks)")
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


def build_context(args, admin_email: str, cfg: UsersConfig) -> AdminContext:
    return AdminContext(
        users_config=Path(cfg.path).resolve(),
        participant_list=Path(args.participant_list).expanduser().resolve(),
        output_dir=Path(args.output_dir).expanduser().resolve() if args.output_dir else None,
        session_list=args.session_list,
        admin_email=admin_email,
        cfg=cfg,
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
