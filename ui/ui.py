# %%
import os
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from layout import app

def parse_args(args=None):
    parser = ArgumentParser("QC-Studio")

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


args = parse_args()

participant_list = args.participant_list
session_list = args.session_list
qc_pipeline = args.qc_pipeline
qc_task = args.qc_task
qc_json = args.qc_json
out_dir = args.out_dir


participants_df = pd.read_csv(participant_list, delimiter="\t")

def init_session_state():
    defaults = {
        "current_page": 1,
        "batch_size": 1,
        "current_batch_qc": {},
    }
    # Initialize defaults if not already set
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# Initialize session state
init_session_state()

current_dir = os.path.dirname(os.path.abspath(__file__))
# print(f"Current directory: {current_dir}")

qc_config_path = os.path.join(current_dir, qc_json)
# print(f"qc path: {qc_config_path}")

page_idx = min(st.session_state.get("current_page", 1) - 1, len(participants_df) - 1)
participant_id = participants_df["participant_id"].iloc[page_idx]
session_id = session_list

app(
    participant_id=participant_id,
    session_id=session_id,
    qc_pipeline=qc_pipeline,
    qc_task=qc_task,
    qc_config_path=qc_config_path,
    out_dir=out_dir
)

    




# %%
