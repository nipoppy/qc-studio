"""Multipage sidebar entry: onboarding / landing (same UI as the main app flow).

The full UI lives in ``views/landing_page.py``; this file only wires CLI context
so Streamlit can run the page when selected from the left navigation.
"""

import streamlit as st

from main import get_cli_run_context
from managers.session_manager import SessionManager
from views.landing_page import show_landing_page
from views.sidebar_cohort_nav import render_sidebar_cohort_subjects

st.set_page_config(layout="wide")
ctx = get_cli_run_context()
SessionManager.init_session_state()
SessionManager.compact_duplicate_qc_records_if_needed()
render_sidebar_cohort_subjects(
    qc_cohort=ctx.get("qc_cohort"),
    total_participants=ctx["total_participants"],
    qc_task=ctx["qc_task"],
    qc_tasks=ctx["qc_tasks"],
    entrypoint_rel_path="main.py",
)
show_landing_page(
    ctx["qc_pipeline"],
    ctx["qc_task"],
    ctx["out_dir"],
    ctx["participant_list"],
    ctx["qc_config_path"],
    qc_cohort=ctx.get("qc_cohort"),
    session_ids=ctx.get("session_ids"),
    entrypoint_rel_path="main.py",
)
