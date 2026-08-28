"""Congratulations page component for QC-Studio UI."""

from pathlib import Path
import streamlit as st
from constants import MESSAGES, SUCCESS_MESSAGES, INFO_MESSAGES, SESSION_KEYS, QC_RATINGS
from managers.session_manager import SessionManager
from utils.export import save_qc_results_to_csv


def show_congratulations_page(
    qc_task: str,
    out_dir: str,
    total_participants: int,
    drop_duplicates: bool,
    *,
    cohort_complete: bool = True,
    participant_ids: list | None = None,
    session_id: str | None = None,
    qc_cohort: list | None = None,
    qc_tasks: list | None = None,
    entrypoint_rel_path: str | None = None,
) -> None:
    """Display congratulations (full summary) or a minimal placeholder until all subjects are QC'd.

    Args:
            qc_task: QC task name
            out_dir: Output directory path
            total_participants: Total number of participants in the QC session
            drop_duplicates: Whether to drop duplicate records before saving
            cohort_complete: When False, show a minimal page (not all subjects have a decided rating).
            participant_ids: Cohort order (for Continue QC navigation when using legacy single-session mode).
            session_id: BIDS session id for legacy single-session completion checks.
            qc_tasks: Task keys for this run (defaults to ``[qc_task]``).
            entrypoint_rel_path: If set (e.g. ``"main.py"``), sidebar navigation uses ``st.switch_page``.
    """
    tasks_eff = list(qc_tasks) if qc_tasks else [qc_task]

    def _fully_reviewed_cohort_pages(records: list) -> int:
        required = {str(t) for t in tasks_eff}
        by_page: dict[tuple[str, str], set[str]] = {}
        for r in records:
            if not SessionManager._final_qc_is_decided(r):
                continue
            pid = r.participant_id if hasattr(r, "participant_id") else r.get("participant_id", "")
            sid = r.session_id if hasattr(r, "session_id") else r.get("session_id", "")
            tk = r.qc_task if hasattr(r, "qc_task") else r.get("qc_task", "")
            k = (str(pid), str(sid))
            by_page.setdefault(k, set()).add(str(tk))
        return sum(1 for ts in by_page.values() if required <= ts)

    if not cohort_complete:
        st.subheader("QC not finished yet")
        st.info("Not every review page has a PASS / FAIL / UNCERTAIN rating yet. " "When you are ready, use **Continue QC** to return to the review.")
        can_continue = bool(qc_cohort) or (bool(participant_ids) and bool(session_id))
        if can_continue and st.button("Continue QC", key="congrats_continue_qc_incomplete"):
            if qc_cohort:
                miss = SessionManager.first_qc_cohort_page_missing_for_tasks(tasks_eff, qc_cohort)
            else:
                temp_cohort = []
                for pid in participant_ids or []:
                    p = str(pid).strip()
                    if not p.startswith("sub-"):
                        p = f"sub-{p}"
                    temp_cohort.append({"participant_id": p, "session_id": session_id})
                miss = SessionManager.first_qc_cohort_page_missing_for_tasks(tasks_eff, temp_cohort)
            SessionManager.set_current_page(miss)
            if entrypoint_rel_path:
                st.switch_page(entrypoint_rel_path)
            st.rerun()
        return

    st.title(MESSAGES["congratulations_title"])

    record_list = SessionManager.get_latest_qc_records_for_task_set(tasks_eff)
    num_pages_done = _fully_reviewed_cohort_pages(record_list)
    num_decided_rows = len([r for r in record_list if SessionManager._final_qc_is_decided(r)])
    if len(tasks_eff) > 1:
        headline = f"## {num_pages_done} review page(s) fully completed (all {len(tasks_eff)} tasks rated)"
    else:
        headline = f"## {num_decided_rows} participant(s) have been reviewed!"

    st.markdown(
        f"""
	{headline}

	Thank you for completing the quality control process. Your thorough review ensures the integrity of our data!

	✅ All QC records have been automatically saved.

	"""
    )

    rater_id = SessionManager.get_rater_id()
    # Display session information and results summary
    task_label = ", ".join(tasks_eff) if len(tasks_eff) > 1 else tasks_eff[0]
    summary_count = num_pages_done if len(tasks_eff) > 1 else num_decided_rows
    _display_session_summary(rater_id, task_label, record_list, reviewed_count=summary_count, multi_task=len(tasks_eff) > 1)
    if pending := st.session_state.pop("_pending_export_msg", None):
        kind, msg = pending
        (st.success if kind == "success" else st.info)(msg)
    # Action buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button(MESSAGES["export_results_button"], width="stretch"):
            export_rows = SessionManager.get_latest_qc_records_per_dedup(None)
            _export_qc_results(rater_id, out_dir, export_rows, drop_duplicates)
            st.rerun()
    with col2:
        if st.button(MESSAGES["previous_button"], width="stretch"):
            SessionManager.previous_page()
            if entrypoint_rel_path:
                st.switch_page(entrypoint_rel_path)
            st.rerun()
    with col3:
        if st.button(MESSAGES["start_over_button"], width="stretch"):
            SessionManager.set_landing_page_complete(False)
            SessionManager.set_qc_cohort_order([])
            SessionManager.set_participant_ids([])
            SessionManager.set_qc_records([])
            SessionManager.set_current_page(1)
            if entrypoint_rel_path:
                st.switch_page(entrypoint_rel_path)
            st.rerun()


def _display_session_summary(
    rater_id: str,
    qc_task: str,
    record_list: list,
    *,
    reviewed_count: int | None = None,
    multi_task: bool = False,
) -> None:
    """Display summary of the QC session.

    Args:
            rater_id: Rater ID
            qc_task: QC task name
            record_list: QC records for this task (deduplicated)
            reviewed_count: Participants with a decided rating; defaults to len(record_list)
            multi_task: When True, ``reviewed_count`` counts cohort pages with every task rated.
    """
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Session Information")
        st.write(f"**Rater ID:** {rater_id}")
        st.write(f"**QC Task:** {qc_task}")
        n_rev = reviewed_count if reviewed_count is not None else len(record_list)
        if multi_task:
            st.write(f"**Fully completed review pages:** {n_rev}")
        else:
            st.write(f"**Total Participants Reviewed:** {n_rev}")

    with col2:
        st.subheader("QC Results Summary")
        # Count final_qc values
        if record_list:
            final_qc_counts = {}
            for record in record_list:
                qc_value = record.final_qc
                if qc_value not in QC_RATINGS:
                    final_qc_counts["Unrated"] = final_qc_counts.get("Unrated", 0) + 1
                else:
                    final_qc_counts[qc_value] = final_qc_counts.get(qc_value, 0) + 1

            for qc_status, count in sorted(final_qc_counts.items()):
                st.write(f"**{qc_status}:** {count}")


def _export_qc_results(rater_id: str, out_dir: str, record_list: list, drop_duplicates: bool) -> None:
    """Export QC results to file.

    Args:
            rater_id: Rater ID
            out_dir: Output directory path
            record_list: List of QC records to export
            drop_duplicates: Whether to drop duplicate records
    """
    out_file = Path(out_dir) / f"{rater_id}_QC_status.tsv"
    if record_list:
        out_path, dropped, dropped_details = save_qc_results_to_csv(out_file, record_list, drop_duplicates)
        msg = SUCCESS_MESSAGES["records_exported"].format(path=out_path)
        if dropped:
            lines = "\n".join(f"- {pid} × {sid}: {', '.join(tasks)}" for (pid, sid), tasks in dropped_details.items())
            msg += f"\n\n⚠️ {dropped} duplicate record(s) removed (kept latest):\n{lines}"
        st.session_state["_pending_export_msg"] = ("success", msg)
    else:
        st.session_state["_pending_export_msg"] = ("info", INFO_MESSAGES["no_export_records"])
