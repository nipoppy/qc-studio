# %%
import os
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from app import app
from managers.session_manager import SessionManager
from constants import SESSION_KEYS

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
        help=("List of sessions to QC"),
        default="Baseline",
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
        help=("Specific workflow output to QC"),
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


def main():
    """Main entry point for the Streamlit app."""
    args = parse_args()
    
    dataset_dir = args.dataset_dir
    participant_list = args.participant_list
    session_list = args.session_list
    qc_pipeline = args.qc_pipeline
    qc_task = args.qc_task
    qc_json = args.qc_json
    out_dir = args.out_dir

    current_dir = os.path.dirname(os.path.abspath(__file__))
    qc_config_path = os.path.join(current_dir, qc_json)

    participants_df = pd.read_csv(participant_list, delimiter="\t")

    # Use session-stored order (set after CSV upload) if available, else use file order
    stored_ids = SessionManager.get_participant_ids()
    participant_ids = stored_ids if stored_ids else participants_df['participant_id'].tolist()
    total_participants = len(participant_ids)

    # Initialize session state
    SessionManager.init_session_state()

    current_page = st.session_state.get(SESSION_KEYS['current_page'], 1)
    if current_page < 1:
        st.session_state[SESSION_KEYS['current_page']] = 1
        current_page = 1

    if current_page > total_participants:
        participant_id = None
    else:
        participant_id = participant_ids[current_page - 1]
        # Ensure participant_id has "sub-" prefix
        if participant_id and not participant_id.startswith("sub-"):
            participant_id = f"sub-{participant_id}"

    session_id = "ses-01"

    drop_duplicates = True
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
        participant_list=participant_list
    )


if __name__ == "__main__":
    main()




# %%
