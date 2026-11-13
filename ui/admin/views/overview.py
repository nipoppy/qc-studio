"""Overview tab: users, dataset, prescribed QC tasks, progress and rater setup at a glance."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from admin import icons
from admin.core import AdminContext, cached_ratings
from utils.ratings_report import (
    ALL_TASKS,
    NOT_EXPECTED,
    assigned_ids,
    assignment_completion,
    dataset_sessions,
    split_expected,
    task_status,
)
from utils.user_setup import ERROR, validate_users_setup


def render(ctx: AdminContext) -> None:
    alerts = st.container()  # every warning/error banner of this tab is collected here, above the sections
    report = validate_users_setup(ctx.users_config, session_list=ctx.session_list)
    users, dataset, tasks = st.columns(3)  # three summary panels side by side
    with users.container(border=True):
        _users(ctx, report, alerts)
    with dataset.container(border=True):
        _dataset(ctx)
    with tasks.container(border=True):
        _qc_tasks(ctx)
    _completion(ctx, alerts)
    _raters(report, alerts)
    _configuration(ctx, report, alerts)


def _users(ctx: AdminContext, report, alerts) -> None:
    cfg = ctx.cfg
    st.subheader(f"{icons.USERS} Users")
    c = st.columns(4)
    c[0].metric("Raters", len(cfg.users) + len(cfg.rejected), help="Rater entries in the users config")
    c[1].metric("Active", len(report.ready_users), help="Raters whose setup is complete, so they can sign in and rate")
    c[2].metric(f"{icons.ADMIN} Admins", len(cfg.admins))
    c[3].metric(f"{icons.VIEWER} Viewers", len(cfg.viewers), help="View-only access to this dashboard")
    for lvl, msg in report.global_issues:
        (alerts.error if lvl == ERROR else alerts.warning)(msg)


def _dataset(ctx: AdminContext) -> None:
    st.subheader(f"{icons.DATASET} Dataset")
    sessions, source = dataset_sessions(ctx.pool, ctx.session_list)
    c = st.columns(2)
    c[0].metric("Participants", len(ctx.pool_ids))
    c[1].metric("Sessions", len(sessions) if sessions else "–", help=f"From the {source}: {', '.join(sessions) or '–'}")


def _qc_tasks(ctx: AdminContext) -> None:
    st.subheader(f"{icons.QC_TASKS} QC tasks")
    c = st.columns(2)
    c[0].metric("Pipeline", ctx.qc_pipeline)
    c[1].metric("Prescribed tasks", len(ctx.expected_tasks), help=", ".join(ctx.expected_tasks))


def _raters(report, alerts) -> None:
    st.subheader(f"{icons.USERS} Raters")
    valid = [u for u in report.users if u.config_valid]
    rows = [
        {
            "rater_id": u.rater_id,
            "status": u.status,
            "participants": u.n_participants,
            "pages": u.n_pages,
            "saved_files": u.n_saved_files,
            "sessions": ", ".join(u.sessions),
            "issues": " | ".join(m for _, m in u.issues),
        }
        for u in valid
    ]
    table = pd.DataFrame(rows, columns=["rater_id", "status", "participants", "pages", "saved_files", "sessions", "issues"])
    st.dataframe(table.set_index("rater_id").sort_index(), width="stretch")
    st.caption(
        "READY* = ready; the output folder is created at launch. NOT READY raters are refused at sign-in. " "Edit raters in the **Raters** tab."
    )
    invalid = [u for u in report.users if not u.config_valid]
    if invalid:
        alerts.warning(
            f"{len(invalid)} invalid users-config entr{'y' if len(invalid) == 1 else 'ies'} (refused at sign-in):\n"
            + "\n".join(f"- `{u.email}`: {'; '.join(u.errors)}" for u in invalid)
        )


def _configuration(ctx: AdminContext, report, alerts) -> None:
    cfg = ctx.cfg
    with st.expander(f"{icons.CONFIG} Configuration"):
        st.markdown(
            f"- Users config: `{ctx.users_config}`\n"
            f"- Rater root: `{cfg.rater_root}`\n"
            f"- Dataset participant list: `{ctx.participant_list}`\n"
            f"- Report folder: `{ctx.output_dir or '(not set: downloads only)'}`\n"
            f"- Identity: {report.identity_mode}\n"
            f"- Admins: {', '.join(sorted(cfg.admins))}\n"
            f"- Viewers (view only): {', '.join(sorted(cfg.viewers)) or '–'}"
        )


def _completion(ctx: AdminContext, alerts) -> None:
    st.subheader(f"{icons.PROGRESS} QC progress")
    _, qc = cached_ratings(ctx)
    expected, _ = split_expected(qc, ctx.qc_pipeline, ctx.expected_tasks)
    comp = assignment_completion(expected, assigned_ids(ctx.cfg), tasks=ctx.expected_tasks)
    per_task = comp[comp["qc_task"] != ALL_TASKS]
    total = comp[comp["qc_task"] == ALL_TASKS].iloc[0]
    cols = st.columns(len(per_task) + 1)
    for col, row in zip(cols, list(per_task.itertuples()) + [total]):
        pct = 0.0 if pd.isna(row.pct_complete) else float(row.pct_complete)
        not_started = row.qc_task != ALL_TASKS and row.raters_started == 0
        col.metric(
            row.qc_task if row.qc_task == ALL_TASKS else f"{icons.QC_TASKS} {row.qc_task}",
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
        alerts.warning(
            "Ratings found for task(s) not in qc.json (left out of completion and reports): "
            + ", ".join(f"{p}/{t} ({n} ratings)" for p, t, n in unexpected[["pipeline", "qc_task", "ratings"]].values)
        )
