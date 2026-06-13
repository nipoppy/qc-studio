"""Congratulations page component for QC-Studio UI."""
from pathlib import Path
import streamlit as st
from constants import MESSAGES, SUCCESS_MESSAGES, INFO_MESSAGES
from managers.session_manager import SessionManager
from utils.export import save_qc_results_to_csv
from constants import QC_RATINGS
import pandas as pd
import altair as alt

def show_congratulations_page(qc_task: str, out_dir: str, total_participants: int, drop_duplicates: bool) -> None:
	"""Display the final congratulations page after QC is complete.
	
	Args:
		qc_task: QC task name
		out_dir: Output directory path
		total_participants: Total number of participants in the QC session
		drop_duplicates: Whether to drop duplicate records before saving
	"""
	st.title(MESSAGES['congratulations_title'])
	
	# Display rater info and summary statistics
	rater_id = SessionManager.get_rater_id()
	record_list = SessionManager.get_qc_records()
	num_reviewed = len(record_list)
	
	st.markdown(f"""
	## {num_reviewed} participant(s) have been reviewed!
	
	Thank you for completing the quality control process. Your thorough review ensures the integrity of our data!
	
	✅ All QC records have been automatically saved.
	
	""")
	
	# Display session information and results summary
	_display_session_summary(rater_id, qc_task, record_list)
	
	# Action buttons
	col1, col2, col3 = st.columns([1, 1, 1])
	with col1:
		if st.button(MESSAGES['export_results_button'], width='stretch'):
			_export_qc_results(rater_id, out_dir, record_list, drop_duplicates)
	with col2:
		if st.button(MESSAGES['previous_button'], width='stretch'):
			SessionManager.previous_page()
			st.rerun()
	with col3:
		if st.button(MESSAGES['start_over_button'], width='stretch'):
			SessionManager.set_landing_page_complete(False)
			st.rerun()


def _display_session_summary(rater_id: str, qc_task: str, record_list: list) -> None:
	"""Display summary of the QC session.
	
	Args:
		rater_id: Rater ID
		qc_task: QC task name
		record_list: List of QC records
	"""
	col1, col2 = st.columns([1, 1])
	with col1:
		st.subheader("Session Information")
		st.write(f"**Rater ID:** {rater_id}")
		st.write(f"**QC Task:** {qc_task}")
		st.write(f"**Total Participants Reviewed:** {len(record_list)}")
	
	with col2:
		st.subheader("QC Results Summary")
		# Count final_qc values
		if record_list:
			num_reviewed = len(record_list)
			final_qc_counts = {}
			durations = []
			labels = []
			for record in record_list:
				qc_value = record.final_qc				
				if qc_value not in QC_RATINGS:
					final_qc_counts["Unrated"] = final_qc_counts.get(qc_value, 0) + 1
					labels.append("Unrated")
				else:
					final_qc_counts[qc_value] = final_qc_counts.get(qc_value, 0) + 1
					labels.append(qc_value)
				durations.append(int(record.duration))
			duration_dict = {"duration":durations, "qc_value":labels}
			duration_df = pd.DataFrame(duration_dict, columns=['duration','qc_value'])

			final_qc_df = pd.DataFrame.from_dict(final_qc_counts, orient='index', columns=['Count'])
			final_qc_df['Percentage'] = final_qc_df['Count'].apply(lambda x : x/num_reviewed)
			#table with count and percentage per qc_value
			st.table(data=final_qc_df, border=True, width="stretch", height="content", hide_index=None, hide_header=None)
			#stacked histogram of duration count
			selection = alt.selection_point(fields=['qc_value'], bind='legend')
			line_chart = alt.Chart(duration_df).encode(
				alt.X('duration:Q', title='Duration (s)',axis=alt.Axis(tickMinStep=1), bin=alt.Bin(step=1)),
				alt.Y('count()',).stack(True), # change True to None to get non-stacked histogram
				alt.Color('qc_value:N').scale(scheme="observable10"),
				opacity=alt.condition(selection, alt.value(1), alt.value(0.2)) #link opacity to the selection state
			).add_params(
    			selection,
			).mark_bar(
				opacity=1 # to adapt if layering histograms
			)

			st.altair_chart(line_chart)


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
		out_path = save_qc_results_to_csv(out_file, record_list, drop_duplicates)
		st.success(SUCCESS_MESSAGES['records_exported'].format(path=out_path))
	else:
		st.info(INFO_MESSAGES['no_export_records'])
