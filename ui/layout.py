import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from niivue_component import niivue_viewer
from utils import parse_qc_config, load_mri_data, load_svg_data, save_qc_results_to_csv
from models import MetricQC, QCRecord
from iqm_distribution_config import IQM_DISTRIBUTION_GROUPS, REFRENCE_DATA_PATHS


def niivue_viewer_from_path(filepath: str, height: int = 600, key: str | None = None) -> None:
	"""Helper to read a local NIfTI file and call the niivue component (if available).

	This mirrors the project's existing helper behavior: read the file bytes and
	hand them to the component. If the niivue component is not installed/available,
	a friendly warning is shown instead.
	"""
	if niivue_viewer is None:
		st.warning(
			"NiiVue component not available. Install the project's `niivue_component` or run the example in `ui/niivue_test.py` to preview behavior."
		)
		return

	if not os.path.isfile(filepath):
		st.error(f"NIfTI file not found: {filepath}")
		return

	with open(filepath, "rb") as f:
		file_bytes = f.read()

	if key is None:
		key = f"niivue_viewer_{os.path.basename(filepath)}"

	# call the underlying component
	try:
		niivue_viewer(nifti_data=file_bytes, filename=os.path.basename(filepath), height=height, key=key)
	except Exception as e:
		st.error(f"Failed to render niivue viewer: {e}")


def app(participant_id, session_id, qc_pipeline, qc_task, qc_config_path, out_dir) -> None:
	"""Main Streamlit layout: top inputs, middle two viewers, bottom QC controls."""
	st.set_page_config(layout="wide")

	# Top container: inputs
	top = st.container()
	with top:
		st.title("Welcome to Nipoppy QC-Studio! 🚀")
		# qc_pipeline = "fMRIPrep"
		# qc_task = "sdc-wf"
		st.subheader(f"QC Pipeline: {qc_pipeline}, QC task: {qc_task}")

		# show participant and session
		st.write(f"Participant ID: {participant_id} | Session ID: {session_id}")        

		# Rater info 
		rater_id = st.text_input("Rater name or ID: 🧑" )
		st.write("You entered:", rater_id)
		
        # Remove spaces
		rater_id = "".join(rater_id.split())

		# Split into two columns for collecting rater specific info
		exp_col, fatigue_col = st.columns([0.5, 0.5], gap="small")
		
		with exp_col:
			# Input rater experience as radio buttons
			options = ["Beginner (< 1 year experience)", "Intermediate (1-5 year experience)", "Expert (>5 year experience)"]
			# add radio buttons
			# experience_level = st.radio()
			rater_experience = st.radio("What is your QC experience level:", options)
			st.write("Experience level:", rater_experience)
			
		with fatigue_col:
			# Input rater experience as radio buttons
			options = ["Not at all", "A bit tired ☕", "Very tired ☕☕"]
			# add radio buttons
			# experience_level = st.radio()
			rater_fatigue = st.radio("How tired are you feeling:", options)
			st.write("Fatigue level:", rater_fatigue)
		

	# parse qc config
	qc_config = parse_qc_config(qc_config_path, qc_task) 
	# print(f"qc config: {qc_config_path}, {qc_config}")

	# Middle: two side-by-side viewers
	middle = st.container()
	with middle:
		niivue_col, svg_col = st.columns([0.4, 0.6], gap="small")

		with niivue_col:
			st.header("3D MRI (Niivue)")
			# Show mri
			mri_data = load_mri_data(qc_config)
			if "base_mri_image_bytes" in mri_data:
				try:
					niivue_viewer(
						nifti_data=mri_data["base_mri_image_bytes"],
						filename=str(qc_config.get("base_mri_image_path").name) if qc_config.get("base_mri_image_path") else "base_mri.nii",
						height=600,
						key="niivue_base_mri",
					)
				except Exception as e:
					st.error(f"Failed to load base MRI in Niivue viewer: {e}")
			else:
				st.info("Base MRI image not found or could not be loaded.")

			# TODO : Optionally overlay another image

		with svg_col:
			st.header("SVG Montage")
			# Show SVG montage
			svg_data = load_svg_data(qc_config)
			if svg_data:
				st.components.v1.html(svg_data, height=600, scrolling=True)
			else:
				st.info("SVG montage not found or could not be loaded.")

	# Bottom: QC metrics and radio buttons
	bottom = st.container()
	with bottom:
		# st.header("QC: Rating & Metrics")
		rating_col, iqm_col = st.columns([0.4, 0.6], gap="small")
		with iqm_col:
			st.subheader("QC Metrics")

			import json
			# Read and parse JSON file
			with open(qc_config_path, 'r') as f:
				data = json.load(f)

			group_cfg = data.get("iqm_distribution", None)

			if not group_cfg:
				st.info("No IQM distribution configuration found in qc_config. Please check your qc_config file.")
			else:

				modality = st.selectbox(
					"Select modality for IQM distributions", 
					options=list(IQM_DISTRIBUTION_GROUPS.keys()),
					key="iqm_modality_select",
				)
				modality_path = group_cfg.get(modality, "")
				print(f"Selected modality: {modality}, path: {modality_path}")

				try:
					df = pd.read_csv(modality_path, sep="\t")
					distribution_groups = IQM_DISTRIBUTION_GROUPS[modality]

					group_name = st.selectbox("Select group", options=list(distribution_groups.keys()), key="iqm_group_name_select")

					mode = st.radio(
						"Display mode",
						["Dataset only", "Dataset + reference"],
						horizontal=True
					)

					cols = distribution_groups[group_name]

					fig = go.Figure()

					if mode == "Dataset only":
						for i, col in enumerate(cols):
							if col not in df.columns:
								continue

							values = df[col].dropna()

							fig.add_trace(go.Box(
								x=[col] * len(values),
								y=values,
								name="Dataset",
								legendgroup="dataset",
								showlegend=(i == 0),
								boxpoints="all",
								jitter=0.45,
								pointpos=0,
								marker=dict(
									size=4,
									symbol="circle",
									color="rgba(31, 119, 180, 0.55)",
								),
								line=dict(
									color="rgba(31, 119, 180, 1.0)"
								),
								fillcolor="rgba(31, 119, 180, 0.25)",
								hovertemplate=f"Source: Dataset<br>Metric: {col}<br>Value: %{{y}}<extra></extra>",
							))
					elif mode == "Dataset + reference":
						ref_path = REFRENCE_DATA_PATHS.get(modality, "")
						if not ref_path:
							st.warning(f"No reference data path configured for modality {modality}. Cannot display reference distributions.")
						else:
							try:
								ref_df = pd.read_csv(ref_path, sep="\t")
								
								for i, col in enumerate(cols):
									if col in df.columns:
										values = df[col].dropna()
										fig.add_trace(go.Box(
											x=[col] * len(values),
											y=values,
											name="Dataset",
											legendgroup="dataset",
											showlegend=(i == 0),
											offsetgroup="dataset",
											boxpoints="all",
											jitter=0.45,
											pointpos=-0.3,
											marker=dict(
												size=4,
												symbol="circle",
												color="rgba(31, 119, 180, 0.55)",
											),
											line=dict(
												color="rgba(31, 119, 180, 1.0)"
											),
											fillcolor="rgba(31, 119, 180, 0.25)",
											hovertemplate=f"Source: Dataset<br>Metric: {col}<br>Value: %{{y}}<extra></extra>",
										))

									if col in ref_df.columns:
										values = ref_df[col].dropna()
										fig.add_trace(go.Box(
											x=[col] * len(values),
											y=values,
											name="Reference",
											legendgroup="reference",
											showlegend=(i == 0),
											offsetgroup="reference",
											boxpoints="all",
											jitter=0.45,
											pointpos=0.3,
											marker=dict(
												size=4,
												symbol="diamond",
												color="rgba(214, 39, 40, 0.55)",
											),
											line=dict(
												color="rgba(214, 39, 40, 1.0)"
											),
											fillcolor="rgba(214, 39, 40, 0.25)",
											hovertemplate=f"Source: Reference<br>Metric: {col}<br>Value: %{{y}}<extra></extra>",
										))
							except Exception as e:
								st.warning(f"Failed to read reference data from {ref_path}: {e}")
								# If reference data can't be loaded, fall back to dataset only
		
					fig.update_layout(
					title=f"{group_name} distributions",
					xaxis_title="Metric",
					yaxis_title="Value",
					template="plotly_white",
					height=650,
					boxmode="group",
					legend_title="Source"
					)

					st.plotly_chart(fig, use_container_width=True)
				except Exception as e:
					st.error(f"Failed to read IQM distribution data from {modality_path}: {e}")				

		with rating_col:
			st.subheader("QC Rating")
			rating = st.radio("Rate this qc-task:", options=("PASS", "FAIL", "UNCERTAIN"), index=0)
			notes = st.text_area("Notes (optional):")
			if st.button("💾 Save QC results to CSV", width=600):
				now = datetime.now()
				timestamp = now.strftime("%Y-%m-%d %H:%M:%S")				
				out_file = Path(out_dir) / f"{rater_id}_QC_status.tsv"

				record = QCRecord(
					participant_id=participant_id,
					session_id=session_id,
					qc_task=qc_task,
					pipeline=qc_pipeline,
					timestamp=timestamp,
					rater_id=rater_id,
					rater_experience=rater_experience,
					rater_fatigue=rater_fatigue,
					final_qc=rating,
					notes=notes,
				)

                # TODO: handle list of records (i.e. multiple subjects and/or qc-tasks)
				# For now just save a single record
                
				record_list = [record]
				out_path = save_qc_results_to_csv(out_file, record_list)
				st.success(f"QC results saved to: {out_path}")
				
                
