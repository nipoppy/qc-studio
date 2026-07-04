"""Build and inspect participant×session QC cohort rows."""
from __future__ import annotations

import pandas as pd

from constants import QC_RATINGS


from utils.bids import (
    bare_bids_id,
    normalize_participant_id_bids,
    normalize_session_id_bids,
    parse_session_list,
)


def build_qc_cohort(participants_df: pd.DataFrame, session_ids: list[str] | None) -> list[dict]:
	"""Each dict is one pagination page: participant_id + session_id (None for datasets with no session level)."""
	rows: list[dict] = []
	if "session_id" in participants_df.columns:
		for _, r in participants_df.iterrows():
			pid = normalize_participant_id_bids(r["participant_id"])
			sid_raw = r.get("session_id")
			sid = normalize_session_id_bids(str(sid_raw)) if sid_raw else None
			rows.append({"participant_id": pid, "session_id": sid})
		return rows
	for pid_raw in participants_df["participant_id"].tolist():
		pid = normalize_participant_id_bids(pid_raw)
		if session_ids is None:
			rows.append({"participant_id": pid, "session_id": None})
		else:
			for sid in session_ids:
				rows.append({"participant_id": pid, "session_id": sid})
	return rows


def cohort_page_key(entry: dict) -> tuple[str, str | None]:
	sid = entry["session_id"]
	return (
		bare_bids_id(entry["participant_id"], "sub-"),
		bare_bids_id(sid, "ses-") if sid is not None else None,
	)


def cohort_page_keys(qc_cohort: list[dict]) -> set[tuple[str, str | None]]:
	return {cohort_page_key(entry) for entry in qc_cohort}


def participant_ids_in_cohort_order(qc_cohort: list[dict]) -> list[str]:
	"""Unique participant IDs in first-seen cohort order."""
	out: list[str] = []
	seen: set[str] = set()
	for entry in qc_cohort:
		pid = entry["participant_id"]
		if pid not in seen:
			seen.add(pid)
			out.append(pid)
	return out


def decided_rating_keys_from_df(df: pd.DataFrame, qc_tasks: list[str]) -> set[tuple[str, str | None, str]]:
	"""(bare_pid, bare_sid, task) tuples with PASS/FAIL/UNCERTAIN in ``df``."""
	if df is None or df.empty or not qc_tasks:
		return set()
	allowed = {str(t) for t in qc_tasks}
	out: set[tuple[str, str | None, str]] = set()
	for _, row in df.iterrows():
		task = str(row.get("qc_task", ""))
		if task not in allowed:
			continue
		final_qc = str(row.get("final_qc", ""))
		if final_qc not in QC_RATINGS:
			continue
		pid = bare_bids_id(str(row.get("participant_id", "")), "sub-")
		sid_raw = row.get("session_id")
		sid = bare_bids_id(normalize_session_id_bids(str(sid_raw)), "ses-") if sid_raw else None
		out.add((pid, sid, task))
	return out


def is_cohort_page_complete(
	entry: dict,
	qc_tasks: list[str],
	decided: set[tuple[str, str | None, str]],
) -> bool:
	page_pid, page_sid = cohort_page_key(entry)
	for task in qc_tasks:
		if (page_pid, page_sid, str(task)) not in decided:
			return False
	return True


def count_complete_cohort_pages(
	qc_cohort: list[dict],
	qc_tasks: list[str],
	decided: set[tuple[str, str | None, str]],
) -> int:
	return sum(1 for entry in qc_cohort if is_cohort_page_complete(entry, qc_tasks, decided))


def first_incomplete_cohort_page(
	qc_cohort: list[dict],
	qc_tasks: list[str],
	decided: set[tuple[str, str | None, str]],
) -> int:
	"""1-based page index of the first cohort row missing a decided rating."""
	for i, entry in enumerate(qc_cohort or []):
		if not is_cohort_page_complete(entry, qc_tasks, decided):
			return i + 1
	return max(len(qc_cohort), 1)


def invalid_upload_cohort_pairs(
	df_task: pd.DataFrame,
	qc_cohort: list[dict],
	allowed_participant_bare_ids: set[str],
) -> list[tuple[str, str | None]]:
	"""(participant_id, session_id) pairs in upload that are not in the cohort or participant list."""
	valid_pages = cohort_page_keys(qc_cohort)
	invalid: list[tuple[str, str | None]] = []
	seen_invalid: set[tuple[str, str | None]] = set()
	if df_task.empty:
		return invalid
	for _, row in df_task.iterrows():
		pid_bare = bare_bids_id(str(row.get("participant_id", "")), "sub-")
		sid_raw = row.get("session_id")
		if sid_raw:
			sid = normalize_session_id_bids(str(sid_raw))
			sid_bare = bare_bids_id(sid, "ses-")
		else:
			sid = None
			sid_bare = None
		if pid_bare not in allowed_participant_bare_ids:
			continue
		key = (pid_bare, sid_bare)
		if key not in valid_pages and key not in seen_invalid:
			seen_invalid.add(key)
			invalid.append((str(row.get("participant_id", "")), sid))
	return invalid
