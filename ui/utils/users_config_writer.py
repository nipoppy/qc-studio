"""Safe edits of rater entries in a users config (used by the admin dashboard).

An edit is prepared first (``prepare_add_rater`` / ``prepare_update_rater`` /
``prepare_remove_rater``), which validates it and returns a :class:`ConfigChange` holding
the new file content and a diff for review. :func:`apply_change` then writes it:

* only ``users`` entries are edited; ``admins``, ``rater_root`` and any other key are
  copied unchanged, so the dashboard can neither grant admin rights nor move every rater
* the edited config must parse, the edited rater must be valid, and every rater that was
  valid before must still be valid (e.g. a duplicate ``rater_id`` is refused)
* the file must not have changed since the change was prepared (another admin's save)
* the current file is copied to ``<config dir>/config_backups/`` and the new content is
  written to a temporary file that atomically replaces the config

The running rater app reloads the config when its modification time changes, so a saved
edit applies on the raters' next page load.
"""

from __future__ import annotations

import copy
import difflib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from utils.user_config import UserEntry, UsersConfigError, _build_config

BACKUP_DIRNAME = "config_backups"
ENTRY_KEYS = ["rater_id", "rater_dir", "participant_list", "session_list", "output_dir"]


class ConfigWriteError(ValueError):
    """The edit was refused; the config file is unchanged."""


@dataclass(frozen=True)
class ConfigChange:
    path: Path
    old_text: str  # file content when the change was prepared
    new_text: str  # content that apply_change writes
    mtime_ns: int  # file modification time when the change was prepared
    summary: str

    def diff(self) -> str:
        """Unified diff between the (re-formatted) current config and the new one."""
        old = _dump(json.loads(self.old_text))
        return "".join(difflib.unified_diff(old.splitlines(keepends=True), self.new_text.splitlines(keepends=True), fromfile="current", tofile="new"))


def _dump(raw: dict) -> str:
    return json.dumps(raw, indent=4, ensure_ascii=False) + "\n"


def _no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    dups = sorted({k for k in keys if keys.count(k) > 1})
    if dups:
        raise ConfigWriteError(f"duplicate key(s) {dups} in the users config; fix the file by hand first")
    return dict(pairs)


def _read(path: Path) -> tuple[str, dict, int]:
    try:
        stat = path.stat()
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigWriteError(f"cannot read {path}: {exc}") from exc
    try:
        raw = json.loads(text, object_pairs_hook=_no_duplicates)
    except json.JSONDecodeError as exc:
        raise ConfigWriteError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("users"), dict):
        raise ConfigWriteError(f'{path} must be a JSON object with a top-level "users" object')
    return text, raw, stat.st_mtime_ns


def clean_entry(entry: dict) -> dict:
    """A rater entry with blank values dropped, keys in the usual order; raises ConfigWriteError if invalid."""
    unknown = sorted(set(entry) - set(ENTRY_KEYS))
    if unknown:
        raise ConfigWriteError(f"unknown key(s) {unknown} (allowed: {', '.join(ENTRY_KEYS)})")
    cleaned = {k: str(entry[k]).strip() for k in ENTRY_KEYS if entry.get(k) is not None and str(entry[k]).strip()}
    try:
        model = UserEntry.model_validate(cleaned)
    except ValidationError as exc:
        msgs = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}".replace("Value error, ", "") for e in exc.errors())
        raise ConfigWriteError(msgs) from exc
    if model.rater_id:
        cleaned["rater_id"] = model.rater_id
    return cleaned


def _find_key(users: dict, email: str) -> str | None:
    """The key in ``users`` matching ``email`` case-insensitively."""
    email = email.strip().lower()
    return next((k for k in users if str(k).strip().lower() == email), None)


def _prepare(path: str | Path, mutate, summary: str, must_be_valid: str | None) -> ConfigChange:
    path = Path(path).expanduser().resolve()
    old_text, raw, mtime_ns = _read(path)
    try:
        before = _build_config(path, old_text)
    except UsersConfigError as exc:
        raise ConfigWriteError(str(exc)) from exc
    new_raw = copy.deepcopy(raw)
    mutate(new_raw)
    for key in raw:
        if key != "users" and new_raw.get(key) != raw[key]:  # defensive: only users may change
            raise ConfigWriteError(f"refusing to change top-level {key!r}")
    new_text = _dump(new_raw)
    try:
        after = _build_config(path, new_text)
    except UsersConfigError as exc:
        raise ConfigWriteError(str(exc)) from exc
    if must_be_valid and must_be_valid not in after.users:
        raise ConfigWriteError(f"{must_be_valid}: " + "; ".join(after.rejected.get(must_be_valid, ["entry is invalid"])))
    broken = sorted(e for e in before.users if e != must_be_valid and e not in after.users and _find_key(new_raw["users"], e))
    if broken:
        reasons = "; ".join(f"{e}: {', '.join(after.rejected.get(e, ['invalid']))}" for e in broken)
        raise ConfigWriteError(f"this change would lock out other raters ({reasons})")
    return ConfigChange(path=path, old_text=old_text, new_text=new_text, mtime_ns=mtime_ns, summary=summary)


def prepare_add_rater(path: str | Path, email: str, entry: dict) -> ConfigChange:
    """Add a new rater entry under ``email`` (refused if the email is already listed)."""
    email = str(email or "").strip().lower()
    cleaned = clean_entry(entry)

    def mutate(raw):
        if _find_key(raw["users"], email):
            raise ConfigWriteError(f"{email} is already in the users config; edit that entry instead")
        raw["users"][email] = cleaned

    return _prepare(path, mutate, f"add rater {email}", must_be_valid=email)


def prepare_update_rater(path: str | Path, email: str, entry: dict) -> ConfigChange:
    """Replace the entry of an existing rater (the email itself is not changed)."""
    email = str(email or "").strip().lower()
    cleaned = clean_entry(entry)

    def mutate(raw):
        key = _find_key(raw["users"], email)
        if key is None:
            raise ConfigWriteError(f"{email} is not in the users config")
        raw["users"][key] = cleaned

    return _prepare(path, mutate, f"update rater {email}", must_be_valid=email)


def prepare_remove_rater(path: str | Path, email: str) -> ConfigChange:
    """Remove a rater entry. Their participant list and rating files are left on disk."""
    email = str(email or "").strip().lower()

    def mutate(raw):
        key = _find_key(raw["users"], email)
        if key is None:
            raise ConfigWriteError(f"{email} is not in the users config")
        del raw["users"][key]

    return _prepare(path, mutate, f"remove rater {email}", must_be_valid=None)


def apply_change(change: ConfigChange) -> Path:
    """Write a prepared change; returns the backup of the previous file. Raises ConfigWriteError if refused."""
    path = change.path
    try:
        stat = path.stat()
    except OSError as exc:
        raise ConfigWriteError(f"cannot read {path}: {exc}") from exc
    if stat.st_mtime_ns != change.mtime_ns or path.read_text(encoding="utf-8") != change.old_text:
        raise ConfigWriteError("the users config changed since this edit was prepared; reload and try again")

    backup_dir = path.parent / BACKUP_DIRNAME
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = backup_dir / f"{path.stem}.{stamp}{path.suffix}"
    shutil.copy2(path, backup)

    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(change.new_text)
        os.chmod(tmp, stat.st_mode & 0o7777)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return backup


def add_rater(path, email, entry) -> Path:
    return apply_change(prepare_add_rater(path, email, entry))


def update_rater(path, email, entry) -> Path:
    return apply_change(prepare_update_rater(path, email, entry))


def remove_rater(path, email) -> Path:
    return apply_change(prepare_remove_rater(path, email))
