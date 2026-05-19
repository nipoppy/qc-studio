"""Export utilities for QC Studio.

This module provides functions for saving QC results to various formats.
"""

import pandas as pd
from pathlib import Path
from constants import QC_DEDUP_KEYS


def save_qc_results_to_csv(out_file, qc_records, drop_duplicates=True):
	"""Save QC results from Streamlit session state to a CSV file.

	This function is resilient to both `QCRecord` model instances and plain
	dicts. It will extract the canonical fields from the updated `QCRecord`:
	- qc_task, participant_id, session_id, task_id, run_id, pipeline,
	  timestamp, rater_id, rater_experience, rater_fatigue, final_qc

	If a record also contains a `metrics` list (items compatible with
	`MetricQC`), those metrics will be flattened into columns as
	`<metric_name>_value` and `<metric_name>` (for qc string), and
	`QC_notes` (if present) will be placed in a `notes` column.

	Parameters
	----------
	out_file : str or Path
		Path where the CSV will be saved.
	qc_records : list
		List of `QCRecord` objects (or dicts) stored.
	"""
	out_file = Path(out_file)
	out_file.parent.mkdir(parents=True, exist_ok=True)

	rows = []

	for rec in qc_records:
		# support both model instances and plain dicts
		if hasattr(rec, "model_dump"):
			# pydantic v2 model -> convert to dict for uniform access
			rec_dict = rec.model_dump()
		elif hasattr(rec, "dict"):
			# pydantic v1 fallback
			rec_dict = rec.dict()
		elif isinstance(rec, dict):
			rec_dict = rec
		else:
			# Handle this better with exceptions
			print("Unknown record format")

		participant_id = rec_dict.get("participant_id") or ""
		if participant_id.startswith("sub-"):
			participant_id = participant_id[4:]

		session_id = rec_dict.get("session_id") or ""
		if session_id.startswith("ses-"):
			session_id = str(session_id[4:])

		row = {
			"qc_task": rec_dict.get("qc_task"),
			"participant_id": participant_id,
			"session_id": session_id,
			"task_id": rec_dict.get("task_id"),
			"run_id": rec_dict.get("run_id"),	
			"pipeline": rec_dict.get("pipeline"),
			"timestamp": rec_dict.get("timestamp"),
			"rater_id": rec_dict.get("rater_id"),
			"rater_experience": rec_dict.get("rater_experience"),
			"rater_fatigue": rec_dict.get("rater_fatigue"),
			"final_qc": rec_dict.get("final_qc"),
			"notes": rec_dict.get("notes"),
		}
		rows.append(row)

	# Define expected columns
	expected_columns = [
		"qc_task", "participant_id", "session_id", "task_id", "run_id",
		"pipeline", "timestamp", "rater_id", "rater_experience",
		"rater_fatigue", "final_qc", "notes"
	]

	# Create dataframe with proper columns even if empty
	if rows:
		df = pd.DataFrame(rows)
	else:
		df = pd.DataFrame(columns=expected_columns)

	if out_file.exists():
		df_existing = pd.read_csv(out_file, sep="\t")
		df = pd.concat([df_existing, df], ignore_index=True)

	# Drop duplicates based on core identity columns
	if drop_duplicates:
		existing_keys = [k for k in QC_DEDUP_KEYS if k in df.columns]
		if existing_keys:
			# Normalise to string so int/str type mismatches (e.g. session_id 1 vs "1") don't prevent dedup
			for col in existing_keys:
				df[col] = df[col].astype(str)
			df = df.drop_duplicates(subset=existing_keys, keep="last")

	# Only sort if dataframe is not empty
	# if not df.empty:
	# 	sort_key = "participant_id" if "participant_id" in df.columns else df.columns[0]
	# 	df = df.sort_values(by=[sort_key]).reset_index(drop=True)
	
	df.to_csv(out_file, index=False, sep='\t')

	return out_file
