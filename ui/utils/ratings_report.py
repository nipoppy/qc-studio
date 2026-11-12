"""Collate every rater's current QC ratings into dataset-level tables.

For each rater in a users config and each QC task, the current rating file is picked with
:func:`utils.qc_files.select_rating_file` (``qc_status.tsv``, else the newest checkpoint).
The functions here return DataFrames only; plotting is left to the callers (admin
dashboard, notebooks).

Comparisons with participant lists are on ``participant_id`` because the lists may not
carry sessions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from utils.assignments import as_users_config, read_participant_ids
from utils.qc_files import find_rating_files, read_rating_file, select_rating_file

ID_COLS = ["participant_id", "session_id", "task_id", "run_id"]
RATING_KEY = ["rater_id", "pipeline", "qc_task"] + ID_COLS
QC_ORDER = ["All-Pass", "Mixed", "All-Uncertain", "All-Fail", "All-Missing"]
VALUE_ORDER = ["PASS", "UNCERTAIN", "FAIL", "MISSING"]
REQUIRED_COLUMNS = ["pipeline", "qc_task", "participant_id", "timestamp", "final_qc", "facet", "rating_value"]

SOURCE_COLUMNS = [
    "rater_id",
    "task_key",
    "source_kind",
    "source_file",
    "checkpoint_stamp",
    "last_rating",
    "n_checkpoints",
    "n_participants",
    "in_latest_ckpt_not_in_status",
]


@dataclass
class Collation:
    """Result of :func:`collate_ratings`."""

    ratings: pd.DataFrame  # facet-level rows from every chosen file
    sources: pd.DataFrame  # one row per rater and task: the file used (SOURCE_COLUMNS)
    raters_without_files: list[str] = field(default_factory=list)
    n_duplicates_dropped: int = 0
    warnings: list[str] = field(default_factory=list)


def collate_ratings(rater_config, prefer_transformed: bool = True) -> Collation:
    """Read every rater's current rating file per QC task into one facet-level table.

    ``rater_id`` is taken from the users config (a mismatching ``rater_id`` column is
    reported and overwritten). Repeated rows for the same rater, participant/session and
    facet keep the latest ``timestamp``. ``in_latest_ckpt_not_in_status`` counts
    participants in the newest checkpoint that a chosen status file lacks: the status
    file is rewritten on every save, so it normally contains everything.
    """
    cfg = as_users_config(rater_config)
    warnings: list[str] = []
    sources, frames, no_files = [], [], []
    for u in sorted(cfg.users.values(), key=lambda u: u["rater_id"]):
        files = find_rating_files(u, warn=warnings.append)
        if files.empty:
            no_files.append(u["rater_id"])
            continue
        for task_key, g in files.groupby("task_key"):
            chosen, latest_ckpt, n_ckpts = select_rating_file(g, prefer_transformed)
            try:
                df = read_rating_file(chosen["path"])
            except Exception as exc:  # pandas raises many types for malformed files
                warnings.append(f"{chosen['path'].name}: cannot read ({exc}); skipped")
                continue
            missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
            if missing:
                warnings.append(f"{chosen['path'].name}: missing column(s) {missing}; skipped")
                continue
            for col in ID_COLS:
                if col not in df.columns:
                    df[col] = ""
            ids = set(df["participant_id"])
            ckpt_only = 0
            if chosen["kind"] == "status" and latest_ckpt is not None:
                try:
                    ckpt_only = len(set(read_rating_file(latest_ckpt["path"])["participant_id"]) - ids)
                except Exception as exc:
                    warnings.append(f"{latest_ckpt['path'].name}: cannot read ({exc})")
            wrong = sorted(set(df["rater_id"]) - {u["rater_id"], ""}) if "rater_id" in df else []
            if wrong:
                warnings.append(f"{chosen['path'].name}: rater_id column has {wrong}; replaced with {u['rater_id']!r}")
            df["rater_id"] = u["rater_id"]
            df["task_key"] = task_key
            df["source_kind"] = chosen["kind"]
            df["source_file"] = chosen["path"].name
            frames.append(df)
            stamp = chosen["stamp"]
            sources.append(
                {
                    "rater_id": u["rater_id"],
                    "task_key": task_key,
                    "source_kind": chosen["kind"],
                    "source_file": chosen["path"].name,
                    "checkpoint_stamp": "" if pd.isna(stamp) else stamp.strftime("%Y-%m-%d %H:%M"),
                    "last_rating": df["timestamp"].max() if len(df) else "",
                    "n_checkpoints": n_ckpts,
                    "n_participants": len(ids),
                    "in_latest_ckpt_not_in_status": ckpt_only,
                }
            )
    if frames:
        ratings = pd.concat(frames, ignore_index=True)
        n_before = len(ratings)
        ratings = ratings.sort_values("timestamp", kind="stable").drop_duplicates(RATING_KEY + ["facet"], keep="last").reset_index(drop=True)
        n_dup = n_before - len(ratings)
    else:
        ratings = pd.DataFrame(columns=RATING_KEY + ["timestamp", "final_qc", "facet", "rating_value", "task_key", "source_kind", "source_file"])
        n_dup = 0
    return Collation(
        ratings=ratings,
        sources=pd.DataFrame(sources, columns=SOURCE_COLUMNS),
        raters_without_files=no_files,
        n_duplicates_dropped=n_dup,
        warnings=warnings,
    )


def _count(value):
    return lambda s: int((s == value).sum())


def participant_level(ratings: pd.DataFrame) -> pd.DataFrame:
    """One row per rater x task x participant/session with ``final_qc`` and failing/uncertain/missing facet counts."""
    cols = RATING_KEY + ["task_key", "source_kind"]
    if ratings.empty:
        return pd.DataFrame(columns=cols + ["final_qc", "timestamp", "n_facets", "n_fail", "n_uncertain", "n_missing"])
    return ratings.groupby(cols, as_index=False).agg(
        final_qc=("final_qc", "last"),
        timestamp=("timestamp", "max"),
        n_facets=("facet", "size"),
        n_fail=("rating_value", _count("FAIL")),
        n_uncertain=("rating_value", _count("UNCERTAIN")),
        n_missing=("rating_value", _count("MISSING")),
    )


def final_qc_counts(qc: pd.DataFrame, by=("pipeline", "qc_task")) -> pd.DataFrame:
    """Counts of each ``final_qc`` value (columns in ``QC_ORDER``, plus any others) per group."""
    if qc.empty:
        return pd.DataFrame(columns=QC_ORDER)
    tab = pd.crosstab([qc[c] for c in by], qc["final_qc"])
    extra = [c for c in tab.columns if c not in QC_ORDER]
    return tab.reindex(columns=QC_ORDER + extra, fill_value=0)


def assigned_ids(rater_config) -> dict[str, set[str]]:
    """Each rater's assigned participant IDs (empty set when the list is missing or unreadable)."""
    out = {}
    for u in as_users_config(rater_config).users.values():
        try:
            out[u["rater_id"]] = set(read_participant_ids(u["participant_list"]))
        except (OSError, ValueError):
            out[u["rater_id"]] = set()
    return out


def rater_progress(qc: pd.DataFrame, assigned: dict[str, set[str]], pool_ids) -> pd.DataFrame:
    """Per rater and task: participants rated out of the rater's own list, and anyone rated outside it or the pool."""
    pool = set(pool_ids)
    rows = []
    for (rid, pipe, task), g in qc.groupby(["rater_id", "pipeline", "qc_task"]):
        rated, mine = set(g["participant_id"]), assigned.get(rid, set())
        rows.append(
            {
                "rater_id": rid,
                "pipeline": pipe,
                "qc_task": task,
                "assigned": len(mine),
                "rated": len(rated),
                "rated_assigned": len(rated & mine),
                "pct_complete": round(100 * len(rated & mine) / len(mine), 1) if mine else np.nan,
                "rated_not_assigned": len(rated - mine),
                "rated_not_in_pool": len(rated - pool),
                **{q: int((g["final_qc"] == q).sum()) for q in QC_ORDER},
            }
        )
    cols = ["rater_id", "pipeline", "qc_task", "assigned", "rated", "rated_assigned", "pct_complete", "rated_not_assigned", "rated_not_in_pool"]
    return pd.DataFrame(rows, columns=cols + QC_ORDER)


COMPLETION_COLUMNS = ["qc_task", "assigned", "rated_assigned", "pct_complete", "raters_started", "raters_with_list"]
ALL_TASKS = "All tasks"


def assignment_completion(qc: pd.DataFrame, assigned: dict[str, set[str]], tasks=None) -> pd.DataFrame:
    """Share of assigned participants rated, per QC task and over all tasks.

    For each task, ``assigned`` sums the list size of every rater with a non-empty list (raters
    who haven't started the task count as 0 rated) and ``rated_assigned`` sums each rater's rated
    participants that are on their own list (as in :func:`rater_progress`). ``tasks`` defaults to
    the tasks present in ``qc``, so a task nobody has started is not listed. The last row,
    ``ALL_TASKS``, pools every task.
    """
    tasks = sorted(qc["qc_task"].unique()) if tasks is None else list(tasks)
    lists = {r: ids for r, ids in assigned.items() if ids}
    n_assigned = sum(len(ids) for ids in lists.values())
    rows = []
    for task in tasks:
        g = qc[qc["qc_task"] == task]
        rated = g.groupby("rater_id")["participant_id"].agg(set)
        done = sum(len(rated.get(r, set()) & ids) for r, ids in lists.items())
        rows.append(
            {
                "qc_task": task,
                "assigned": n_assigned,
                "rated_assigned": done,
                "raters_started": int(sum(1 for r in lists if r in rated.index)),
                "raters_with_list": len(lists),
            }
        )
    if not rows:
        return pd.DataFrame(columns=COMPLETION_COLUMNS)
    out = pd.DataFrame(rows)
    started_any = set(qc.loc[qc["qc_task"].isin(tasks), "rater_id"]) & set(lists)
    total = {
        "qc_task": ALL_TASKS,
        "assigned": int(out["assigned"].sum()),
        "rated_assigned": int(out["rated_assigned"].sum()),
        "raters_started": len(started_any),
        "raters_with_list": len(lists),
    }
    out = pd.concat([out, pd.DataFrame([total])], ignore_index=True)
    out["pct_complete"] = (100 * out["rated_assigned"] / out["assigned"]).where(out["assigned"] > 0).round(1)
    return out[COMPLETION_COLUMNS]


def off_list_ratings(qc: pd.DataFrame, assigned: dict[str, set[str]], pool_ids) -> pd.DataFrame:
    """Ratings of participants outside the rater's own list or outside the dataset pool."""
    pool = set(pool_ids)
    flags = qc.assign(
        assigned=[p in assigned.get(r, set()) for r, p in zip(qc["rater_id"], qc["participant_id"])],
        in_pool=qc["participant_id"].isin(pool),
    )
    out = flags[~flags["assigned"] | ~flags["in_pool"]]
    return out[["rater_id", "pipeline", "qc_task", "participant_id", "session_id", "assigned", "in_pool"]].reset_index(drop=True)


def raters_per_participant(qc: pd.DataFrame, pool_ids, task: str) -> pd.Series:
    """For one task: number of raters for every participant in the pool (0 = not rated)."""
    g = qc[qc["qc_task"] == task].drop_duplicates(["participant_id", "rater_id"])
    return g.groupby("participant_id")["rater_id"].nunique().reindex(sorted(set(pool_ids)), fill_value=0)


def dataset_coverage(qc: pd.DataFrame, pool_ids, assigned: dict[str, set[str]] | None = None, tasks=None, pipeline=None) -> pd.DataFrame:
    """Per task: how many pool participants were rated by at least 1, 2 and 3 raters.

    ``tasks`` (with ``pipeline``) lists the expected tasks, so tasks nobody has started get a
    row of zeros; by default only tasks present in ``qc`` are listed.
    """
    pool = set(pool_ids)
    any_assigned = set().union(*assigned.values()) if assigned else set()
    if tasks is None:
        keys = list(qc.groupby(["pipeline", "qc_task"]).groups) if not qc.empty else []
    else:
        keys = [(pipeline, t) for t in tasks]
    rows = []
    for pipe, task in keys:
        g = qc[(qc["pipeline"] == pipe) & (qc["qc_task"] == task)]
        n_r = raters_per_participant(g, pool, task)
        rated_ids = set(g["participant_id"])
        rows.append(
            {
                "pipeline": pipe,
                "qc_task": task,
                "pool": len(pool),
                "assigned_to_any_rater": len(pool & any_assigned),
                "rated_1+": int((n_r >= 1).sum()),
                "rated_2+": int((n_r >= 2).sum()),
                "rated_3+": int((n_r >= 3).sum()),
                "not_rated": int((n_r == 0).sum()),
                "pct_rated": round(100 * (n_r >= 1).mean(), 1) if len(n_r) else np.nan,
                "rated_not_in_pool": len(rated_ids - pool),
                "n_sessions": g["session_id"].nunique(),
            }
        )
    cols = ["pipeline", "qc_task", "pool", "assigned_to_any_rater", "rated_1+", "rated_2+", "rated_3+"]
    return pd.DataFrame(rows, columns=cols + ["not_rated", "pct_rated", "rated_not_in_pool", "n_sessions"])


TASK_STATUS_COLUMNS = ["pipeline", "qc_task", "in_qc_json", "status", "raters_started", "participants_rated", "ratings"]
NOT_STARTED, IN_PROGRESS, NOT_EXPECTED = "Not started", "In progress", "Not in qc.json"


def split_expected(qc: pd.DataFrame, pipeline: str, tasks) -> tuple[pd.DataFrame, pd.DataFrame]:
    """``(expected, other)``: ratings of the expected pipeline tasks, and everything else."""
    mask = (qc["pipeline"].str.lower() == str(pipeline).lower()) & qc["qc_task"].isin(list(tasks))
    return qc[mask], qc[~mask]


def task_status(qc: pd.DataFrame, pipeline: str, tasks) -> pd.DataFrame:
    """Every expected task (``qc.json`` order) with its progress, then any rated task not in ``qc.json``.

    ``status`` is ``Not started`` (no ratings), ``In progress``, or ``Not in qc.json`` for
    ratings of tasks the prescription doesn't list (e.g. a different pipeline or a renamed task).
    """
    expected, other = split_expected(qc, pipeline, tasks)
    rows = []

    def _row(pipe, task, g, in_json):
        status = (IN_PROGRESS if len(g) else NOT_STARTED) if in_json else NOT_EXPECTED
        rows.append(
            {
                "pipeline": pipe,
                "qc_task": task,
                "in_qc_json": in_json,
                "status": status,
                "raters_started": g["rater_id"].nunique(),
                "participants_rated": g["participant_id"].nunique(),
                "ratings": len(g),
            }
        )

    for task in tasks:
        _row(pipeline, task, expected[expected["qc_task"] == task], True)
    for (pipe, task), g in other.groupby(["pipeline", "qc_task"]) if not other.empty else []:
        _row(pipe, task, g, False)
    return pd.DataFrame(rows, columns=TASK_STATUS_COLUMNS)


def consensus(qc: pd.DataFrame) -> pd.DataFrame:
    """Per task and participant/session: raters, their ``final_qc`` values, unanimity and majority.

    ``majority_qc`` is the ``final_qc`` given by more than half of the raters, else ``"No majority"``.
    """
    cols = ["pipeline", "qc_task"] + ID_COLS
    out_cols = cols + ["n_raters", "raters", "ratings", "unanimous", "majority_qc"]
    if qc.empty:
        return pd.DataFrame(columns=out_cols)
    rows = []
    for key, g in qc.groupby(cols):
        vc = g["final_qc"].value_counts()
        n = int(vc.sum())
        rows.append(
            dict(
                zip(cols, key),
                n_raters=n,
                raters=", ".join(sorted(g["rater_id"])),
                ratings=", ".join(f"{k}:{v}" for k, v in vc.items()),
                unanimous=len(vc) == 1,
                majority_qc=vc.index[0] if vc.iloc[0] > n / 2 else "No majority",
            )
        )
    return pd.DataFrame(rows, columns=out_cols)


def agreement_summary(cons: pd.DataFrame) -> pd.DataFrame:
    """Per task, among participants rated by more than one rater: how many ratings were unanimous."""
    multi = cons[cons["n_raters"] > 1]
    if multi.empty:
        return pd.DataFrame(columns=["n", "unanimous", "pct_unanimous"])
    out = multi.groupby("qc_task").agg(n=("unanimous", "size"), unanimous=("unanimous", "sum"))
    out["pct_unanimous"] = (100 * out["unanimous"] / out["n"]).round(1)
    return out


def facet_rating_counts(ratings: pd.DataFrame, task: str) -> pd.DataFrame:
    """For one task: counts of each ``rating_value`` per facet, least-passing facets first."""
    g = ratings[ratings["qc_task"] == task]
    if g.empty:
        return pd.DataFrame(columns=VALUE_ORDER)
    tab = pd.crosstab(g["facet"], g["rating_value"])
    extra = [c for c in tab.columns if c not in VALUE_ORDER]
    tab = tab.reindex(columns=VALUE_ORDER + extra, fill_value=0)
    pass_rate = tab["PASS"] / tab.sum(axis=1)
    return tab.loc[pass_rate.sort_values(kind="stable").index]
