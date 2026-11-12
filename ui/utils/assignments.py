"""Rater workloads: who is assigned which participants, and lists for new raters.

Assignments come from a users config (see :mod:`utils.user_config`): each rater's
assignments are the rows of the ``participant_list`` it points to. Every function that
takes ``rater_config`` accepts either a path or an already loaded :class:`UsersConfig`.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from utils.user_config import UsersConfig, load_users_config

ASSIGNMENT_COLUMNS = ["rater_id", "list_file", "participant_id", "session_id"]


def as_users_config(rater_config: str | Path | UsersConfig) -> UsersConfig:
    return rater_config if isinstance(rater_config, UsersConfig) else load_users_config(rater_config)


def read_participant_list(path: str | Path) -> pd.DataFrame:
    """``participant_id`` (and ``session_id`` when present) of a TSV, stripped, blank IDs dropped."""
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    if "participant_id" not in df.columns:
        raise ValueError(f"{path}: no participant_id column")
    keep = ["participant_id"] + (["session_id"] if "session_id" in df.columns else [])
    df = df[keep].apply(lambda s: s.str.strip())
    return df[df["participant_id"] != ""].reset_index(drop=True)


def read_participant_ids(path: str | Path) -> list[str]:
    """Unique, non-blank participant_id values from a TSV, in file order."""
    return read_participant_list(path)["participant_id"].unique().tolist()


def restrict_to_pool(custom_ids, pool_ids) -> tuple[list[str], list[str]]:
    """Split a custom participant list into ``(kept, not_in_pool)`` against the dataset pool.

    Both are stripped, de-duplicated, non-blank and in the custom list's order.
    """
    pool = {str(p).strip() for p in pool_ids}
    ids = [p for p in pd.unique(pd.Series(list(custom_ids), dtype=str).str.strip()) if p]
    return [p for p in ids if p in pool], [p for p in ids if p not in pool]


def load_assignments(rater_config, warn=print) -> pd.DataFrame:
    """Every rater's assigned rows as a long table with ``ASSIGNMENT_COLUMNS``.

    A rater's assignments are the rows of their configured ``participant_list``. ``session_id``
    is ``""`` for lists without a session column. Rows are kept as listed (duplicates included).
    Raters without an existing list, and unreadable lists, are reported through ``warn`` and
    contribute no rows.
    """
    cfg = as_users_config(rater_config)
    rows, no_list = [], []
    for u in cfg.users.values():
        f = Path(u["participant_list"])
        if not f.is_file():
            no_list.append(u["rater_id"])
            continue
        try:
            df = read_participant_list(f)
        except ValueError as exc:
            warn(f"{u['rater_id']}: {exc}; skipped")
            continue
        df = df.reindex(columns=["participant_id", "session_id"], fill_value="")
        df.insert(0, "list_file", f.name)
        df.insert(0, "rater_id", u["rater_id"])
        rows.append(df)
    if no_list:
        warn(f"Raters without an existing list (no assignments): {', '.join(sorted(no_list))}")
    if not rows:
        return pd.DataFrame(columns=ASSIGNMENT_COLUMNS)
    return pd.concat(rows, ignore_index=True)[ASSIGNMENT_COLUMNS]


def add_units(assign: pd.DataFrame, participant_level_only: bool = False) -> tuple[pd.DataFrame, list[str]]:
    """Add a ``unit`` column: participant, or participant+session when every row has a session.

    Returns ``(assign_with_unit, key_columns)``.
    """
    has_sessions = not assign.empty and (assign["session_id"] != "").all()
    key = ["participant_id"] if (participant_level_only or not has_sessions) else ["participant_id", "session_id"]
    out = assign.copy()
    out["unit"] = out[key].agg("|".join, axis=1) if not out.empty else pd.Series(dtype=str)
    return out, key


def raters_per_unit(assign: pd.DataFrame) -> pd.Series:
    """Number of distinct raters per unit (``assign`` must have a ``unit`` column)."""
    return assign.drop_duplicates(["rater_id", "unit"]).groupby("unit")["rater_id"].nunique()


def rater_summary(assign: pd.DataFrame) -> pd.DataFrame:
    """Per rater: rows, unique participants/units, duplicates, sessions, shared vs exclusive units."""
    if assign.empty:
        return pd.DataFrame()
    n_raters = assign["unit"].map(raters_per_unit(assign))
    a = assign.assign(n_raters_for_unit=n_raters)
    rows = []
    for rid, g in a.groupby("rater_id"):
        uniq = g.drop_duplicates("unit")
        rows.append(
            {
                "rater_id": rid,
                "rows": len(g),
                "unique_participants": g["participant_id"].nunique(),
                "unique_units": len(uniq),
                "duplicate_rows": len(g) - len(uniq),
                "n_sessions": g.loc[g["session_id"] != "", "session_id"].nunique(),
                "shared_with_others": int((uniq["n_raters_for_unit"] > 1).sum()),
                "exclusive": int((uniq["n_raters_for_unit"] == 1).sum()),
            }
        )
    out = pd.DataFrame(rows).set_index("rater_id")
    out["pct_shared"] = (100 * out["shared_with_others"] / out["unique_units"]).round(1)
    return out.sort_values("unique_units", ascending=False)


def rater_count_distribution(assign: pd.DataFrame) -> pd.DataFrame:
    """How many units have 1, 2, ... raters: ``n_units``, ``pct``, ``cum_pct_at_least`` indexed by ``n_raters``."""
    per_unit = raters_per_unit(assign)
    total = len(per_unit)
    cov = per_unit.value_counts().sort_index().rename_axis("n_raters").rename("n_units").to_frame()
    if total:
        cov["pct"] = (100 * cov["n_units"] / total).round(1)
        cov["cum_pct_at_least"] = (100 * cov["n_units"][::-1].cumsum()[::-1] / total).round(1)
    return cov


def overlap_matrices(assign: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """``(shared_counts, jaccard)`` between every pair of raters; the diagonal is each rater's unit count."""
    sets = assign.groupby("rater_id")["unit"].agg(set)
    raters = sorted(sets.index)
    overlap = pd.DataFrame(0, index=raters, columns=raters, dtype=int)
    jaccard = pd.DataFrame(0.0, index=raters, columns=raters)
    for a in raters:
        for b in raters:
            inter = len(sets[a] & sets[b])
            union = len(sets[a] | sets[b])
            overlap.loc[a, b] = inter
            jaccard.loc[a, b] = inter / union if union else 0.0
    return overlap, jaccard


def overlapping_pairs(assign: pd.DataFrame) -> pd.DataFrame:
    """Rater pairs that share at least one unit, most shared first."""
    sets = assign.groupby("rater_id")["unit"].agg(set)
    rows = []
    for a, b in combinations(sorted(sets.index), 2):
        shared = len(sets[a] & sets[b])
        if shared:
            union = len(sets[a] | sets[b])
            rows.append(
                {
                    "rater_a": a,
                    "rater_b": b,
                    "shared": shared,
                    "n_a": len(sets[a]),
                    "n_b": len(sets[b]),
                    "jaccard": round(shared / union, 3),
                    "identical": sets[a] == sets[b],
                }
            )
    cols = ["rater_a", "rater_b", "shared", "n_a", "n_b", "jaccard", "identical"]
    return pd.DataFrame(rows, columns=cols).sort_values(["shared", "jaccard"], ascending=False).reset_index(drop=True)


def _rank(pool_ids, assignments: pd.DataFrame, seed=None, warn=print, warn_outside_pool=True) -> pd.DataFrame:
    """Rank the pool by number of raters in ``assignments`` (fewest first, ties shuffled with ``seed``)."""
    pool = pd.Index(pd.unique(pd.Series(list(pool_ids), dtype=str).str.strip()))
    a = assignments.drop_duplicates(["participant_id", "rater_id"])
    outside = set(a["participant_id"]) - set(pool)
    if outside and warn_outside_pool:
        warn(f"{len(outside)} assigned participants are not in the pool and are ignored, e.g. {sorted(outside)[:5]}")
    per_pid = a.groupby("participant_id")["rater_id"]
    ranked = pd.DataFrame(
        {
            "participant_id": pool,
            "n_raters": per_pid.nunique().reindex(pool, fill_value=0).astype(int).values,
            "raters": per_pid.agg(lambda s: ", ".join(sorted(s))).reindex(pool, fill_value="").values,
        }
    )
    ranked["_tiebreak"] = np.random.default_rng(seed).random(len(ranked))
    return ranked.sort_values(["n_raters", "_tiebreak"]).drop(columns="_tiebreak").reset_index(drop=True)


def rank_participants_by_rater_count(rater_config, pool_ids, seed=None, exclude_raters=(), warn=print) -> pd.DataFrame:
    """Every participant in the pool with its number of assigned raters, fewest first.

    ``exclude_raters``: rater_ids left out of the counts (e.g. the rater you are about to (re)create).
    Returns ``participant_id``, ``n_raters``, ``raters``.
    """
    assignments = load_assignments(rater_config, warn=warn)
    assignments = assignments[~assignments["rater_id"].isin(exclude_raters)]
    return _rank(pool_ids, assignments, seed, warn=warn)


# How create_rater_list picks participants from the pool.
POLICIES = {
    "least_rated": "Least rated first: participants assigned to the fewest raters (ties broken at random with the seed)",
    "random": "Random: a seeded random sample of the pool, regardless of existing assignments",
    "all": "All: every participant of the pool (e.g. a custom list meant for one rater); the count is ignored",
}


def create_rater_list(
    rater_id: str, n: int | None, pool_ids, assignments: pd.DataFrame, seed=None, policy: str = "least_rated", warn=print, warn_outside_pool=True
) -> pd.DataFrame:
    """Participant list for one rater: ``n`` participants of ``pool_ids`` chosen by ``policy`` (see ``POLICIES``).

    ``pool_ids`` may be the whole dataset list or a subset of it (see :func:`restrict_to_pool`).
    With ``policy="all"`` every participant of the pool is taken and ``n`` is ignored.
    Existing rows for ``rater_id`` are ignored, so re-running with the same seed gives the same list.
    Returns the chosen rows (``participant_id``, ``n_raters`` before this rater, ``raters``),
    sorted by participant ID. Set ``warn_outside_pool=False`` when the pool is deliberately a subset.
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r} (choose from {', '.join(POLICIES)})")
    ranked = _rank(pool_ids, assignments[assignments["rater_id"] != rater_id], seed, warn=warn, warn_outside_pool=warn_outside_pool)
    if policy == "all":
        n = len(ranked)
    if n is None or n > len(ranked):
        raise ValueError(f"{rater_id}: asked for {n} participants but the pool has only {len(ranked)}")
    if policy in ("least_rated", "all"):
        chosen = ranked.head(n)
    else:  # random: sample in pool order so the result depends only on the pool and the seed
        pool = pd.unique(pd.Series(list(pool_ids), dtype=str).str.strip())
        picked = pool[np.random.default_rng(seed).choice(len(pool), size=n, replace=False)]
        chosen = ranked.set_index("participant_id").loc[picked].reset_index()
    ids = chosen["participant_id"]
    order = sorted(range(len(chosen)), key=lambda i: (len(ids.iat[i]), ids.iat[i]))
    return chosen.iloc[order].reset_index(drop=True)


def participant_list_path(rater_config, rater_id: str) -> Path:
    """The ``participant_list`` path the users config gives ``rater_id``."""
    raters = {u["rater_id"]: u for u in as_users_config(rater_config).users.values()}
    if rater_id not in raters:
        raise KeyError(f"{rater_id!r} is not a valid rater in the users config")
    return Path(raters[rater_id]["participant_list"])


def write_participant_list(participant_ids, rater_config, rater_id: str, overwrite: bool = False) -> tuple[Path, str]:
    """Write the list to the rater's ``participant_list`` path; returns ``(path, status)``.

    An existing file is only replaced with ``overwrite=True``.
    """
    out = participant_list_path(rater_config, rater_id)
    if out.exists() and not overwrite:
        return out, "exists, not written (set overwrite to replace it)"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"participant_id": list(participant_ids)}).to_csv(out, sep="\t", index=False)
    return out, "written"
