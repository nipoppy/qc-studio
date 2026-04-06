import os
from pathlib import Path
from datetime import datetime
import streamlit as st
from niivue_component import niivue_viewer
from utils import parse_all_qc_tasks, parse_qc_config, parse_bids_entities, group_svg_paths_by_run, load_mri_data, load_mesh_data, load_svg_data, save_qc_results_to_csv
from models import MetricQC, QCRecord

@st.dialog("SVG Viewer", width="large")
def show_svg_dialog(name: str, content: str) -> None:
    st.markdown(f"**{name}**")
    st.markdown(f'<div style="width:100%">{content}</div>', unsafe_allow_html=True)


def _render_svg_items(svg_items: list[tuple[str, str]], key_prefix: str) -> None:
	"""Render a list of (name, content) SVG tuples with expand buttons."""
	if not svg_items:
		st.info("SVG montage not found or could not be loaded.")
		return
	if len(svg_items) == 1:
		name, content = svg_items[0]
		if st.button("🔍 View full size", key=f"{key_prefix}_expand_0"):
			show_svg_dialog(name, content)
		st.markdown(
			f'<div class="{key_prefix}-wrap-0" style="width:100%;overflow-y:auto;overflow-x:hidden">'
			f'<style>.{key_prefix}-wrap-0 svg{{width:100%!important;height:auto!important;}}</style>'
			f'{content}</div>',
			unsafe_allow_html=True,
		)
	else:
		tabs = st.tabs([name for name, _ in svg_items])
		for i, (tab, (name, content)) in enumerate(zip(tabs, svg_items)):
			with tab:
				if st.button("🔍 View full size", key=f"{key_prefix}_expand_{i}"):
					show_svg_dialog(name, content)
				st.markdown(
					f'<div class="{key_prefix}-wrap-{i}" style="width:100%;overflow-y:auto;overflow-x:hidden">'
					f'<style>.{key_prefix}-wrap-{i} svg{{width:100%!important;height:auto!important;}}</style>'
					f'{content}</div>',
					unsafe_allow_html=True,
				)


def _render_task_panels(
	task_key: str,
	qc_config: dict,
	participant_id: str,
	session_id: str,
	qc_pipeline: str,
	out_dir: str,
	rater_id: str,
	rater_experience: str,
	rater_fatigue: str,
) -> None:
	"""Render the middle (NiiVue + SVG) and bottom (IQM + QC rating) panels
	for a single QC task.  All Streamlit widget keys are scoped with
	``task_key`` so multiple tasks can coexist on the same page.
	"""
	PANEL_HEIGHT = 600

	# Middle: side-by-side viewers
	has_niivue   = bool(qc_config.get("base_mri_image_path"))
	has_svg      = bool(qc_config.get("svg_montage_path"))
	has_iqm_plot = bool(qc_config.get("iqm_path"))
	has_mesh     = bool(qc_config.get("mesh_paths"))

	if has_niivue and has_svg:
		middle_left, middle_right = st.columns([0.4, 0.6], gap="small")
	elif has_niivue:
		middle_left = st.container()
		middle_right = None
	elif has_svg:
		middle_left = None
		middle_right = st.container()
	else:
		middle_left = middle_right = None

	if has_niivue and middle_left:
		with middle_left:
			st.subheader("MRI (3D) viewer: NiiVue")
			cfg_col, view_col = st.columns([0.32, 0.68], gap="small")

			with cfg_col:
				st.header("Niivue Controls")
				view_mode = st.selectbox(
					"View Mode",
					["multiplanar", "axial", "coronal", "sagittal", "3d"],
					key=f"{task_key}_view_mode",
					help="Select the viewing perspective",
				)
				height = 600
				overlay_colormap = st.selectbox(
					"Overlay Colormap",
					["grey", "cool", "warm", "red", "yellow"],
					key=f"{task_key}_overlay_colormap",
					help="Select the colormap for the overlay",
				)
				st.divider()
				st.subheader("Display Settings")
				show_crosshair = st.checkbox("Show Crosshair",          value=False,    key=f"{task_key}_crosshair")
				radiological   = st.checkbox("Radiological Convention", value=False,    key=f"{task_key}_radiological")
				show_colorbar  = st.checkbox("Show Colorbar",           value=True,     key=f"{task_key}_colorbar")
				interpolation  = st.checkbox("Interpolation",           value=True,     key=f"{task_key}_interpolation")
				show_overlay   = st.checkbox("Show overlay image",      value=False,    key=f"{task_key}_show_overlay")
				show_mesh      = st.checkbox("Show FreeSurfer surfaces", value=has_mesh, disabled=not has_mesh, key=f"{task_key}_show_mesh")

			with view_col:
				st.header("3D MRI (Niivue)")
				mri_data = load_mri_data(qc_config)
				if "base_mri_image_bytes" in mri_data:
					base_mri_image_bytes = mri_data["base_mri_image_bytes"]
					base_mri_name = str(qc_config.get("base_mri_image_path").name) if qc_config.get("base_mri_image_path") else "base_mri.nii"
					try:
						settings = {
							"crosshair":     show_crosshair,
							"radiological":  radiological,
							"colorbar":      show_colorbar,
							"interpolation": interpolation,
						}
						overlays = []
						if show_overlay and "overlay_mri_image_bytes" in mri_data:
							overlays.append({
								"data":     mri_data["overlay_mri_image_bytes"],
								"name":     "overlay",
								"colormap": overlay_colormap,
								"opacity":  0.5,
							})
						meshes = []
						if show_mesh and has_mesh:
							meshes = load_mesh_data(qc_config)

						overlay_state = f"{overlay_colormap}_{show_overlay}"
						mesh_state    = f"mesh_{show_mesh}"
						viewer_key    = f"niivue_{task_key}_{view_mode}_{overlay_state}_{mesh_state}"

						viewer_kwargs = {
							"nifti_data": base_mri_image_bytes,
							"filename":   base_mri_name,
							"height":     height,
							"key":        viewer_key,
							"view_mode":  view_mode,
							"settings":   settings,
							"styled":     True,
						}
						if overlays:
							viewer_kwargs["overlays"] = overlays
						if meshes:
							viewer_kwargs["meshes"] = meshes

						niivue_viewer(**viewer_kwargs)
					except Exception as e:
						st.error(f"Failed to load base MRI in Niivue viewer: {e}")
				else:
					st.info("Base MRI image not found or could not be loaded.")

	# Group SVG paths by (session, run) — used by both the SVG panel and QC rating
	svg_groups  = group_svg_paths_by_run(qc_config)   # {(ses, run): [Path,...]}
	multi_group = len(svg_groups) > 1

	def _group_label(ses: str | None, task: str | None, run: str | None) -> str:
		parts = []
		if ses:  parts.append(f"ses-{ses}")
		if task: parts.append(f"task-{task}")
		if run:  parts.append(f"run-{run}")
		return " ".join(parts) if parts else "N/A"

	if has_svg and middle_right:
		with middle_right:
			st.subheader("Report (SVG) Montage")
			if not svg_groups:
				st.info("SVG montage not found or could not be loaded.")
			elif not multi_group:
				paths = next(iter(svg_groups.values()))
				_render_svg_items([(p.name, p.read_text()) for p in paths], task_key)
			else:
				group_tabs = st.tabs([_group_label(s, t, r) for s, t, r in svg_groups])
				for tab, ((ses_val, task_val, run_val), paths) in zip(group_tabs, svg_groups.items()):
					with tab:
						key_prefix = f"{task_key}_ses{ses_val}_task{task_val}_run{run_val}"
						_render_svg_items([(p.name, p.read_text()) for p in paths], key_prefix)

	# Bottom: IQM plot + QC rating
	st.divider()
	if has_iqm_plot:
		bot_left, bot_right = st.columns([0.4, 0.6], gap="small")
	else:
		bot_left = st.container()
		bot_right = None

	if has_iqm_plot and bot_right:
		with bot_right:
			st.subheader("IQM distributions")
			iqm_paths = qc_config.get("iqm_path") or []
			svg_iqms = [
				(p.name, p.read_text())
				for p in iqm_paths
				if p and p.is_file() and p.suffix == ".svg"
			]
			if svg_iqms:
				_render_svg_items(svg_iqms, f"{task_key}_iqm")
			else:
				st.info("IQM file not found or unsupported format.")

	with bot_left:
		st.subheader("QC Rating")
		bids    = parse_bids_entities(qc_config)
		task_id = bids["task_id"]

		# One rating + save per (session, run) group
		_ses_fallback = session_id.removeprefix("ses-") if session_id else None
		group_keys  = list(svg_groups.keys()) if multi_group else [(_ses_fallback, task_id, bids["run_id"])]
		rating_tabs = st.tabs([_group_label(s, t, r) for s, t, r in group_keys]) if multi_group else [None]

		for rating_tab, (ses_val, task_val, run_val) in zip(rating_tabs, group_keys):
			ctx   = rating_tab if multi_group else st.container()
			scope = f"{task_key}_ses{ses_val}_task{task_val}_run{run_val}" if multi_group else task_key
			with ctx:
				rating = st.radio("Rate this qc-task:", options=("PASS", "FAIL", "UNCERTAIN"), index=None, key=f"{scope}_rating")
				notes  = st.text_area("Notes (optional):", key=f"{scope}_notes")
				if st.button("💾 Save QC results to CSV", key=f"{scope}_save", width=600):
					now       = datetime.now()
					timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
					out_file  = Path(out_dir) / f"{rater_id}_QC_status.tsv"
					record = QCRecord(
						participant_id=participant_id,
						session_id=(f"ses-{ses_val}" if ses_val else session_id),
						task_id=task_val,
						run_id=run_val,
						qc_task=task_key,
						pipeline=qc_pipeline,
						timestamp=timestamp,
						rater_id=rater_id,
						rater_experience=rater_experience,
						rater_fatigue=rater_fatigue,
						final_qc=rating,
						notes=notes,
					)
					out_path = save_qc_results_to_csv(out_file, [record])
					st.success(f"QC results saved to: {out_path}")


def app(participant_id, session_id, qc_pipeline, qc_task, qc_config_path, out_dir) -> None:
	"""Main Streamlit layout: top inputs, middle two viewers, bottom QC controls.

	``qc_task`` may be a single task name string, a list of task name strings,
	or ``None`` / ``"all"`` to render every task found in the config file.
	"""
	st.set_page_config(layout="wide")

	# Top: participant info + rater inputs (shared across all tasks)
	top = st.container()
	with top:
		st.title("Welcome to Nipoppy QC-Studio! 🚀")
		st.subheader(f"QC Pipeline: {qc_pipeline}")
		st.write(f"Participant ID: {participant_id} | Session ID: {session_id}")

		rater_id = st.text_input("Rater name or ID: 🧑")
		st.write("You entered:", rater_id)
		rater_id = "".join(rater_id.split())

		exp_col, fatigue_col = st.columns([0.5, 0.5], gap="small")
		with exp_col:
			options = ["Beginner (< 1 year experience)", "Intermediate (1-5 year experience)", "Expert (>5 year experience)"]
			rater_experience = st.radio("What is your QC experience level:", options)
			st.write("Experience level:", rater_experience)
		with fatigue_col:
			options = ["Not at all", "A bit tired ☕", "Very tired ☕☕"]
			rater_fatigue = st.radio("How tired are you feeling:", options)
			st.write("Fatigue level:", rater_fatigue)

	# Resolve which tasks to render
	all_tasks = parse_all_qc_tasks(qc_config_path)

	if qc_task is None or qc_task == "all":
		tasks_to_render = all_tasks
	elif isinstance(qc_task, list):
		tasks_to_render = {k: all_tasks[k] for k in qc_task if k in all_tasks}
	else:
		tasks_to_render = {qc_task: all_tasks[qc_task]} if qc_task in all_tasks else {}

	if not tasks_to_render:
		st.error(f"No matching QC tasks found in {qc_config_path}.")
		return
	
	# Render panels — one tab per task when there are multiple
	rater_kwargs = dict(
		participant_id=participant_id,
		session_id=session_id,
		qc_pipeline=qc_pipeline,
		out_dir=out_dir,
		rater_id=rater_id,
		rater_experience=rater_experience,
		rater_fatigue=rater_fatigue,
	)

	if len(tasks_to_render) == 1:
		task_key, qc_config = next(iter(tasks_to_render.items()))
		st.subheader(f"QC task: {task_key}")
		_render_task_panels(task_key, qc_config, **rater_kwargs)
	else:
		tabs = st.tabs(list(tasks_to_render.keys()))
		for tab, (task_key, qc_config) in zip(tabs, tasks_to_render.items()):
			with tab:
				_render_task_panels(task_key, qc_config, **rater_kwargs)
