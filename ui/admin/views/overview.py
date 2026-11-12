"""Overview tab: setup status of every rater, config problems and headline numbers."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from admin.core import AdminContext, cached_collation
from utils.assignments import read_participant_ids
from utils.ratings_report import (
    ALL_TASKS,
    NOT_EXPECTED,
    assigned_ids,
    assignment_completion,
    participant_level,
    split_expected,
    task_status,
)
from utils.user_setup import ERROR, validate_users_setup


def render(ctx: AdminContext) -> None:
    report = validate_users_setup(ctx.users_config, session_list=ctx.session_list)
    cfg = ctx.cfg

    try:
        pool_size = len(read_participant_ids(ctx.participant_list))
    except (OSError, ValueError) as exc:
        pool_size = None
        st.error(f"Dataset participant list cannot be read: {exc}")

    c = st.columns(5)
    c[0].metric("Raters", len(cfg.users))
    c[1].metric("Ready", len(report.ready_users))
    c[2].metric("Invalid entries", len(cfg.rejected))
    c[3].metric("Admins", len(cfg.admins))
    c[4].metric("Dataset participants", "–" if pool_size is None else pool_size)

    _completion(ctx)

    for lvl, msg in report.global_issues:
        (st.error if lvl == ERROR else st.warning)(msg)

    st.subheader("Raters")
    rows = [
        {
            "status": u.status,
            "email": u.email,
            "rater_id": u.rater_id,
            "participants": u.n_participants if u.config_valid else None,
            "pages": u.n_pages if u.config_valid else None,
            "saved_files": u.n_saved_files if u.config_valid else None,
            "sessions": ", ".join(u.sessions),
            "issues": " | ".join(m for _, m in u.issues),
        }
        for u in report.users
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(
        "READY* = ready; the output folder is created at launch. INVALID entries and NOT READY raters are refused at sign-in. "
        "Edit raters in the **Raters** tab."
    )

    with st.expander("Configuration"):
        st.markdown(
            f"- Users config: `{ctx.users_config}`\n"
            f"- Rater root: `{cfg.rater_root}`\n"
            f"- Dataset participant list: `{ctx.participant_list}`\n"
            f"- Report folder: `{ctx.output_dir or '(not set: downloads only)'}`\n"
            f"- Identity: {report.identity_mode}\n"
            f"- Admins: {', '.join(sorted(cfg.admins))}"
        )
        if cfg.admin_rejected:
            st.warning("Ignored admin entries: " + "; ".join(cfg.admin_rejected.values()))


def _completion(ctx: AdminContext) -> None:
    st.subheader("Rating completion")
    st.caption(f"Expected tasks from `{ctx.qc_json}` (pipeline **{ctx.qc_pipeline}**).")
    qc = participant_level(cached_collation(ctx).ratings)
    expected, _ = split_expected(qc, ctx.qc_pipeline, ctx.expected_tasks)
    comp = assignment_completion(expected, assigned_ids(ctx.cfg), tasks=ctx.expected_tasks)
    per_task = comp[comp["qc_task"] != ALL_TASKS]
    total = comp[comp["qc_task"] == ALL_TASKS].iloc[0]
    cols = st.columns(len(per_task) + 1)
    for col, row in zip(cols, list(per_task.itertuples()) + [total]):
        pct = 0.0 if pd.isna(row.pct_complete) else float(row.pct_complete)
        not_started = row.qc_task != ALL_TASKS and row.raters_started == 0
        col.metric(
            row.qc_task,
            f"{pct:.1f}%",
            delta="not started" if not_started else None,
            delta_color="off",
            help=f"{row.rated_assigned} of {row.assigned} assigned participants rated; {row.raters_started} of {row.raters_with_list} raters started",
        )
        col.progress(min(pct / 100, 1.0))
    st.caption(
        "Rated ÷ assigned, summed over every rater with a participant list (a rater who hasn't started a task counts as 0). "
        "Details per rater are in the **Ratings** tab."
    )

    status = task_status(qc, ctx.qc_pipeline, ctx.expected_tasks)
    st.dataframe(status, hide_index=True, width="stretch")
    unexpected = status[status["status"] == NOT_EXPECTED]
    if not unexpected.empty:
        st.warning(
            "Ratings found for task(s) not in qc.json (left out of completion and reports): "
            + ", ".join(f"{p}/{t} ({n} ratings)" for p, t, n in unexpected[["pipeline", "qc_task", "ratings"]].values)
        )
