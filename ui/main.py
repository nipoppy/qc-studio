# %%
import os
import sys
from argparse import ArgumentParser

import pandas as pd
import streamlit as st
from app import app, resolve_qc_tasks
from components.qc_viewer import AUTOPLAY_RUN_CTX_KEY
from managers.session_manager import SessionManager
from constants import SESSION_KEYS
from views.sidebar_cohort_nav import render_sidebar_cohort_subjects
from utils.cohort import (
    build_qc_cohort,
    normalize_participant_id_bids as _normalize_participant_id,
    normalize_session_id_bids as _normalize_session_id,
    parse_session_list as _parse_session_list,
    participant_ids_in_cohort_order,
)


def parse_args(args=None):
    parser = ArgumentParser("QC-Studio")

    parser.add_argument(
        "--dataset_dir",
        dest="dataset_dir",
        help=("Path to dataset dir"),
        required=True,
    )
    parser.add_argument(
        "--participant_list",
        dest="participant_list",
        help=("List of participants to QC"),
        required=True,
    )
    parser.add_argument(
        "--session_list",
        dest="session_list",
        help=(
            "Comma-separated BIDS session labels to QC (e.g. ses-01,ses-02). "
            "Each participant is combined with each session into one review page. "
            "If the participant TSV has a session_id column, that table defines "
            "(participant, session) rows instead. Legacy default Baseline maps to ses-01."
        ),
        default=None,
        required=False,
    )
    parser.add_argument(
        "--qc_pipeline",
        help=("Pipeline output to QC"),
        dest="qc_pipeline",
        required=True,
    )
    parser.add_argument(
        "--qc_task",
        help=(
            "QC task key from qc.json (e.g. anat_wf_qc), or **all** to show every task "
            "on one scrollable page with a rating per task."
        ),
        dest="qc_task",
        required=True,
    )
    parser.add_argument(
        "--output_dir",
        dest="out_dir",
        help="Directory to save session state and QC results",
        required=True,
    )
    parser.add_argument(
        "--qc_json",
        dest="qc_json",
        help=("Path to a JSON containing a list of image file paths to be displayed."),
        required=True,
    )

    return parser.parse_args(args)


def get_cli_run_context():
    """Paths and counts from CLI args.

    Used by ``main()`` and by multipage ``pages/*.py`` entrypoints so sidebar
    navigation matches the same run configuration.
    """
    args = parse_args()
    ui_dir = os.path.dirname(os.path.abspath(__file__))
    qc_config_path = os.path.join(ui_dir, args.qc_json)
    session_ids = _parse_session_list(args.session_list)
    if session_ids is None:
        from bids import BIDSLayout
        layout = BIDSLayout(args.dataset_dir, validate=False)
        bids_sessions = layout.get_sessions()
        if bids_sessions:
            session_ids = [_normalize_session_id(s) for s in bids_sessions]
            print(
                f"No --session_list given, using sessions found in dataset: {session_ids}",
                file=sys.stderr,
            )
    participants_df = pd.read_csv(args.participant_list, delimiter="\t")
    stored_cohort = SessionManager.get_qc_cohort_order()
    if stored_cohort:
        qc_cohort = stored_cohort
    else:
        qc_cohort = build_qc_cohort(participants_df, session_ids)
    total_participants = len(qc_cohort)
    participant_ids = participant_ids_in_cohort_order(qc_cohort)
    qc_tasks = resolve_qc_tasks(args.qc_task, qc_config_path)
    if str(args.qc_task).strip().lower() == "all" and not qc_tasks:
        print(
            "QC-Studio: --qc_task all requires a readable qc.json (JSON object with task keys). "
            f"No tasks found at {qc_config_path!r}.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return {
        "dataset_dir": args.dataset_dir,
        "participant_list": args.participant_list,
        "session_list": args.session_list,
        "session_ids": session_ids,
        "qc_pipeline": args.qc_pipeline,
        "qc_task": args.qc_task,
        "qc_tasks": qc_tasks,
        "qc_config_path": qc_config_path,
        "out_dir": args.out_dir,
        "total_participants": total_participants,
        "drop_duplicates": True,
        "participant_ids": participant_ids,
        "qc_cohort": qc_cohort,
    }


def main():
    """Main entry point for the Streamlit app."""
    ctx = get_cli_run_context()
    dataset_dir = ctx["dataset_dir"]
    participant_list = ctx["participant_list"]
    qc_pipeline = ctx["qc_pipeline"]
    qc_task = ctx["qc_task"]
    qc_config_path = ctx["qc_config_path"]
    out_dir = ctx["out_dir"]
    total_participants = ctx["total_participants"]
    drop_duplicates = ctx["drop_duplicates"]
    qc_cohort = ctx["qc_cohort"]
    participant_ids = ctx["participant_ids"]

    # Initialize session state
    SessionManager.init_session_state()
    SessionManager.compact_duplicate_qc_records_if_needed()

    session_id_for_sidebar = qc_cohort[0]["session_id"] if qc_cohort else None
    qc_tasks = ctx["qc_tasks"]

    current_page = st.session_state.get(SESSION_KEYS['current_page'], 1)
    if current_page < 1:
        st.session_state[SESSION_KEYS['current_page']] = 1
        current_page = 1

    if current_page > total_participants or not qc_cohort:
        participant_id = None
        session_id = session_id_for_sidebar
    else:
        entry = qc_cohort[current_page - 1]
        participant_id = entry["participant_id"]
        session_id = entry["session_id"]

    if (
        participant_id is not None
        and qc_cohort
        and current_page <= total_participants
    ):
        st.session_state[AUTOPLAY_RUN_CTX_KEY] = {
            "participant_id": participant_id,
            "session_id": session_id,
            "qc_pipeline": qc_pipeline,
            "qc_task": qc_task,
            "qc_tasks": qc_tasks,
            "total_participants": total_participants,
            "qc_cohort": qc_cohort,
            "participant_ids": participant_ids,
        }
    else:
        st.session_state.pop(AUTOPLAY_RUN_CTX_KEY, None)

    # Sidebar must be drawn before main content so Navigation + Subjects both appear.
    on_qc_viewer_page = bool(
        participant_id is not None
        and qc_cohort
        and current_page <= total_participants
    )
    render_sidebar_cohort_subjects(
        qc_cohort=qc_cohort,
        total_participants=total_participants,
        qc_task=qc_task,
        qc_tasks=qc_tasks,
        entrypoint_rel_path=None,
        prepend_navigation=on_qc_viewer_page,
        navigation_kwargs={
            "current_page": SessionManager.get_current_page(),
            "total_participants": total_participants,
            "participant_id": participant_id,
            "session_id": session_id,
            "qc_pipeline": qc_pipeline,
            "qc_tasks": qc_tasks,
            "participant_ids": participant_ids,
            "qc_cohort": qc_cohort,
        }
        if on_qc_viewer_page
        else None,
    )

    app(
        dataset_dir=dataset_dir,
        participant_id=participant_id,
        session_id=session_id,
        qc_pipeline=qc_pipeline,
        qc_task=qc_task,
        qc_config_path=qc_config_path,
        out_dir=out_dir,
        total_participants=total_participants,
        drop_duplicates=drop_duplicates,
        participant_list=participant_list,
        participant_ids=participant_ids,
        qc_cohort=qc_cohort,
        qc_tasks=qc_tasks,
    )


if __name__ == "__main__":
    main()



# %%
