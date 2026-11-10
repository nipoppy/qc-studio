"""Overview tab: setup status of every rater, config problems and headline numbers."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from admin.core import AdminContext
from utils.assignments import read_participant_ids
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
