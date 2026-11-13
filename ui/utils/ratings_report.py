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

from utils.assignments import as_users_config, count_buckets, read_participant_ids
from utils.cohort import parse_session_list
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


def progress_grid(progress: pd.DataFrame, assigned: dict[str, set[str]], tasks) -> pd.DataFrame:
    """Every rater with a participant list × every task, with completion from :func:`rater_progress`.

    Tasks a rater hasn't started get ``rated_assigned = 0`` and ``pct_complete = 0``, so each
    rater has one row per task. Raters with an empty or unreadable list are left out.
    """
    raters = sorted(r for r, ids in assigned.items() if ids)
    grid = pd.MultiIndex.from_product([raters, list(tasks)], names=["rater_id", "qc_task"]).to_frame(index=False)
    grid["assigned"] = grid["rater_id"].map(lambda r: len(assigned[r]))
    done = progress[["rater_id", "qc_task", "rated_assigned", "pct_complete"]]
    grid = grid.merge(done, on=["rater_id", "qc_task"], how="left").fillna({"rated_assigned": 0, "pct_complete": 0.0})
    return grid.astype({"rated_assigned": int})


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


def coverage_buckets(qc: pd.DataFrame, pool_ids, tasks) -> pd.DataFrame:
    """Per task (rows): dataset participants by number of raters, columns ``"0"``, ``"1"``, ``"2"``, ``"3+"``."""
    per_task = {t: qc[qc["qc_task"] == t].groupby("participant_id")["rater_id"].nunique() for t in tasks}
    return pd.DataFrame({t: count_buckets(n, pool_ids) for t, n in per_task.items()}).T.rename_axis("qc_task")


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


def dataset_sessions(pool: pd.DataFrame, session_list: str | None = None) -> tuple[list[str], str]:
    """Sessions of the dataset participant list and where they come from.

    The list's ``session_id`` column wins; otherwise the ``--session_list`` value. An empty
    list means the dataset has no session level (each participant is one QC page).
    """
    if "session_id" in pool.columns:
        return sorted(s for s in pool["session_id"].dropna().astype(str).str.strip().unique() if s), "session_id column"
    sessions = parse_session_list(session_list) or []
    return sessions, ("--session_list" if sessions else "not specified")


def expected_records(pool: pd.DataFrame, tasks, session_list: str | None = None) -> pd.DataFrame:
    """Every QC record the dataset calls for: one row per participant × session × task.

    Participant–session pairs come from the list's ``session_id`` column when present, else every
    participant × each ``--session_list`` session. Without sessions, ``session_id`` is empty.
    """
    cols = ["participant_id", "session_id", "qc_task"]
    ids = pool["participant_id"].astype(str).str.strip()
    if "session_id" in pool.columns:
        pages = pd.DataFrame({"participant_id": ids, "session_id": pool["session_id"].astype(str).str.strip()})
    else:
        sessions = dataset_sessions(pool, session_list)[0] or [None]
        pages = pd.MultiIndex.from_product([ids.unique(), sessions], names=cols[:2]).to_frame(index=False)
    pages = pages[pages["participant_id"] != ""].drop_duplicates()
    tasks = pd.DataFrame({"qc_task": list(tasks)})
    if pages.empty or tasks.empty:
        return pd.DataFrame(columns=cols)
    return pages.merge(tasks, how="cross")[cols]


def records_rated(qc: pd.DataFrame, records: pd.DataFrame) -> int:
    """Number of ``records`` (participant × session × task) with at least one participant-level rating.

    Each record counts once however many raters rated it; ratings outside ``records`` are ignored.
    When ``records`` has no sessions, ratings match on participant and task only.
    """
    if qc.empty or records.empty:
        return 0
    keys = ["participant_id", "qc_task"] + (["session_id"] if records["session_id"].notna().any() else [])
    rated = qc[keys].astype(str).drop_duplicates()
    return len(records[keys].astype(str).drop_duplicates().merge(rated, on=keys))


def split_expected(qc: pd.DataFrame, pipeline: str, tasks) -> tuple[pd.DataFrame, pd.DataFrame]:
    """``(expected, other)``: rows of the expected pipeline tasks (``pipeline`` spelled as given), and everything else.

    Works on facet- and participant-level tables; the pipeline is matched case-insensitively.
    """
    mask = (qc["pipeline"].str.lower() == str(pipeline).lower()) & qc["qc_task"].isin(list(tasks))
    return qc[mask].assign(pipeline=pipeline), qc[~mask]


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


DEFAULT_BREAK_MINUTES = 15
DURATION_COLUMNS = ["rater_id", "pipeline", "qc_task"] + ID_COLS + ["timestamp", "seconds", "sitting"]
PACE_STATS = ["n_ratings", "n_timed", "median_s", "p25_s", "p75_s", "active_min", "per_hour", "sittings", "days", "first_rating", "last_rating"]


def rating_durations(qc: pd.DataFrame, break_minutes: float = DEFAULT_BREAK_MINUTES) -> pd.DataFrame:
    """Seconds spent on each participant-level rating, from the gap to the rater's previous save.

    ``qc`` is participant-level (one ``timestamp`` per rater and QC record, the last save). Each
    rater's saves are taken as one stream across tasks, sorted by time; a rating's ``seconds``
    is the gap since the rater's previous save, so time is attributed to the task being rated.
    A gap longer than ``break_minutes`` starts a new ``sitting`` (numbered per rater from 1)
    and, like the rater's first save, gets ``seconds = NaN``. Rows with unparsable timestamps
    are dropped. Re-rating a record moves its timestamp, so prefer medians over means.
    """
    if qc.empty:
        return pd.DataFrame(columns=DURATION_COLUMNS)
    df = qc[DURATION_COLUMNS[:-2]].copy()  # all but the computed seconds and sitting
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values(["rater_id", "timestamp"], kind="stable").reset_index(drop=True)
    if df.empty:
        return pd.DataFrame(columns=DURATION_COLUMNS)
    gap = df.groupby("rater_id")["timestamp"].diff().dt.total_seconds()
    new_sitting = gap.isna() | (gap > break_minutes * 60)
    df["seconds"] = gap.where(~new_sitting)
    df["sitting"] = new_sitting.astype(int).groupby(df["rater_id"]).cumsum()
    return df[DURATION_COLUMNS]


def pace_summary(durations: pd.DataFrame, by=("rater_id", "qc_task")) -> pd.DataFrame:
    """Rating pace per group of :func:`rating_durations` rows.

    ``n_timed`` ratings have a duration (not the first of a sitting); ``median_s``/``p25_s``/``p75_s``
    are seconds per rating over those; ``active_min`` sums them and ``per_hour`` is
    ``n_timed`` per active hour. ``sittings`` counts distinct (rater, sitting) pairs and ``days``
    distinct calendar days with a rating.
    """
    by = list(by)
    if durations.empty:
        return pd.DataFrame(columns=by + PACE_STATS)
    d = durations.assign(_sitting=durations.groupby(["rater_id", "sitting"]).ngroup(), _day=durations["timestamp"].dt.normalize())
    out = d.groupby(by).agg(
        n_ratings=("seconds", "size"),
        n_timed=("seconds", "count"),
        median_s=("seconds", "median"),
        p25_s=("seconds", lambda x: x.quantile(0.25)),
        p75_s=("seconds", lambda x: x.quantile(0.75)),
        active_min=("seconds", "sum"),
        sittings=("_sitting", "nunique"),
        days=("_day", "nunique"),
        first_rating=("timestamp", "min"),
        last_rating=("timestamp", "max"),
    )
    out["active_min"] = out["active_min"] / 60
    out["per_hour"] = (out["n_timed"] / (out["active_min"] / 60)).where(out["active_min"] > 0)
    out[["median_s", "p25_s", "p75_s"]] = out[["median_s", "p25_s", "p75_s"]].round(0)
    out[["active_min", "per_hour"]] = out[["active_min", "per_hour"]].round(1)
    return out.reset_index()[by + PACE_STATS]


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
