"""Find and pick the QC rating files a rater has saved.

A rater's output folder (``out_dir``, see :mod:`utils.user_config`) holds, per QC task:

* ``<rater_id>_<pipeline>_<task>_qc_status.tsv`` – rewritten on every save
* ``checkpoints/<rater_id>_<pipeline>_<task>_checkpoint_<YYYYmmddTHHMMSS>Z.tsv`` – timestamped
  snapshots, possibly with a derived copy such as ``..._checkpoint_<stamp>Z_transformed.tsv``
  (old checkpoints migrated to the current facet names)

The *current* rating file for a rater and task is the ``qc_status.tsv`` when it exists,
otherwise the newest checkpoint by the stamp in its filename.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

STATUS_SUFFIX = "_qc_status.tsv"
TRANSFORMED_SUFFIX = "_transformed"

# Matches the stamp written by qc_viewer._default_qc_checkpoint_path, e.g. "..._checkpoint_20261012T143005Z.tsv",
# including derived files with a trailing suffix such as "..._checkpoint_20261012T143005Z_transformed.tsv".
CHECKPOINT_STAMP_RE = re.compile(r"_checkpoint_(\d{8}T\d{6})Z?(?:_[^/]*)?\.tsv$")
# Full checkpoint filename: "<stem>_checkpoint_<stamp>[Z][<suffix>].tsv"
_CHECKPOINT_NAME_RE = re.compile(r"^(?P<stem>.+)_checkpoint_(?P<stamp>\d{8}T\d{6})Z?(?P<suffix>_[^/]*)?\.tsv$")

RATING_FILE_COLUMNS = ["rater_id", "task_key", "kind", "stamp", "transformed", "path"]


def checkpoint_stamp(path: Path | str) -> datetime | None:
    """Timestamp embedded in a checkpoint filename, or None when absent or unparsable."""
    match = CHECKPOINT_STAMP_RE.search(Path(path).name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%dT%H%M%S")
    except ValueError:
        return None


def find_rating_files(rater: dict, warn=print) -> pd.DataFrame:
    """All status/checkpoint TSVs in a rater's ``out_dir``.

    ``rater`` is a resolved users-config entry (needs ``rater_id`` and ``out_dir``).
    Returns one row per file with columns ``RATING_FILE_COLUMNS``; ``task_key`` is the
    ``<pipeline>_<task>`` slug between the ``<rater_id>_`` prefix and the status/checkpoint
    suffix, ``stamp`` is the checkpoint time (``NaT`` for status files). Files that don't
    follow the naming scheme are reported through ``warn`` and skipped.
    """
    rid, out = rater["rater_id"], Path(rater["out_dir"])
    rows = []
    if out.is_dir():
        for p in sorted(out.glob(f"*{STATUS_SUFFIX}")):
            rows.append((p.name[: -len(STATUS_SUFFIX)], "status", pd.NaT, False, p))
        for p in sorted((out / "checkpoints").glob("*.tsv")):
            m = _CHECKPOINT_NAME_RE.match(p.name)
            stamp = checkpoint_stamp(p)
            if not m or stamp is None:
                warn(f"{rid}: unrecognized checkpoint name {p.name}; skipped")
                continue
            rows.append((m["stem"], "checkpoint", stamp, m["suffix"] == TRANSFORMED_SUFFIX, p))
    files = pd.DataFrame(rows, columns=["stem", "kind", "stamp", "transformed", "path"])
    prefix = f"{rid}_"
    other = ~files["stem"].str.startswith(prefix)
    if other.any():
        warn(f"{rid}: files not prefixed with {prefix!r} skipped: {[p.name for p in files.loc[other, 'path']]}")
    files = files[~other].copy()
    files.insert(0, "task_key", files.pop("stem").str[len(prefix) :])
    files.insert(0, "rater_id", rid)
    return files[RATING_FILE_COLUMNS].reset_index(drop=True)


def select_rating_file(files: pd.DataFrame, prefer_transformed: bool = True) -> tuple[pd.Series | None, pd.Series | None, int]:
    """Pick the current rating file for one rater and task.

    ``files`` holds the rows of :func:`find_rating_files` for a single ``task_key``.
    Returns ``(chosen, latest_checkpoint, n_checkpoints)``: ``chosen`` is the status file
    when present, else the newest checkpoint; for the newest stamp, its ``*_transformed``
    copy is used when ``prefer_transformed`` is True and the copy exists.
    """
    status = files[files["kind"] == "status"]
    ckpts = files[files["kind"] == "checkpoint"]
    latest_ckpt = None
    if not ckpts.empty:
        newest = ckpts[ckpts["stamp"] == ckpts["stamp"].max()]
        pick = newest[newest["transformed"] == prefer_transformed]
        latest_ckpt = (pick if not pick.empty else newest).iloc[0]
    chosen = status.iloc[0] if not status.empty else latest_ckpt
    return chosen, latest_ckpt, int(ckpts["stamp"].nunique())


def read_rating_file(path: Path | str) -> pd.DataFrame:
    """A rating TSV as strings, with column names and values stripped."""
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df.apply(lambda s: s.str.strip())
