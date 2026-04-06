import json
from pathlib import Path
import pandas as pd
from models import QCConfig, QCRecord
from bids.layout import parse_file_entities

def group_svg_paths_by_run(qc_config: dict) -> dict[tuple[str | None, str | None, str | None], list[Path]]:
	"""Group svg_montage_path entries by their BIDS (session, task, run) entities.

	Returns an ordered dict ``{(ses_id, task_id, run_id): [Path, ...]}``.
	Each value is ``None`` when that entity is absent from the filename.
	"""
	svg_paths = qc_config.get("svg_montage_path") or []
	if not isinstance(svg_paths, list):
		svg_paths = [svg_paths]

	groups: dict[tuple[str | None, str | None, str | None], list[Path]] = {}
	for p in svg_paths:
		if p and p.is_file():
			entities = parse_file_entities(str(p))
			raw_ses  = entities.get("session")
			raw_task = entities.get("task")
			raw_run  = entities.get("run")
			ses_key  = str(raw_ses)  if raw_ses  is not None else None
			task_key_bids = str(raw_task) if raw_task is not None else None
			run_key  = str(raw_run)  if raw_run  is not None else None
			groups.setdefault((ses_key, task_key_bids, run_key), []).append(p)
	return groups


def parse_bids_entities(qc_config: dict) -> dict:
	"""Extract BIDS task and run labels from all paths in qc_config.

	Scans every available path (svg_montage_path, base_mri_image_path, iqm_path)
	and returns the first non-None value found for each entity.
	Returns a dict with keys ``task_id`` and ``run_id`` (either str or None).
	"""
	svg_paths = qc_config.get("svg_montage_path") or []
	if not isinstance(svg_paths, list):
		svg_paths = [svg_paths]

	candidates = [
		*svg_paths,
		qc_config.get("base_mri_image_path"),
		qc_config.get("iqm_path"),
	]

	task_id = run_id = None
	for path in candidates:
		if path is None:
			continue
		entities = parse_file_entities(str(path))
		if task_id is None:
			task_id = entities.get("task")
		if run_id is None:
			raw_run = entities.get("run")
			run_id = str(raw_run) if raw_run is not None else None
		if task_id and run_id:
			break

	return {"task_id": task_id, "run_id": run_id}


def parse_all_qc_tasks(qc_json) -> dict[str, dict]:
	"""Parse every QC task from a QC JSON file.

	Returns a dict mapping task name -> config dict (same shape as
	``parse_qc_config``).  Returns an empty dict on any error.
	"""
	qc_json_path = Path(qc_json) if qc_json else None
	try:
		raw_text = qc_json_path.read_text()
		qcconf = QCConfig.model_validate_json(raw_text)
	except Exception:
		return {}
	return {
		task_name: {
			"base_mri_image_path": qctask.base_mri_image_path,
			"overlay_mri_image_path": qctask.overlay_mri_image_path,
			"svg_montage_path": qctask.svg_montage_path,
			"iqm_path": qctask.iqm_path,
			"mesh_paths": qctask.mesh_paths,
		}
		for task_name, qctask in qcconf.root.items()
	}

def parse_qc_config(qc_json, qc_task) -> dict:
	"""
	Parse a QC JSON file using the QCConfig Pydantic model.

	Returns a dict with keys:
	  - 'base_mri_image_path': Path | None
	  - 'overlay_mri_image_path': Path | None
	  - 'svg_montage_path': list[Path] | None
	  - 'iqm_path': list[Path] | None

	If the file is missing, invalid, or the requested qc_task is not present,
	all values will be None.
	"""
	qc_json_path = Path(qc_json) if qc_json else None

	try:
		# Pydantic v2 deprecates `parse_file`; read file and validate JSON string.
		raw_text = qc_json_path.read_text()
		qcconf = QCConfig.model_validate_json(raw_text)
	except Exception:
		return {
			"base_mri_image_path": None,
			"overlay_mri_image_path": None,
			"svg_montage_path": None,
			"iqm_path": None,
			"mesh_paths": None,
			"mesh_paths": None,
		}

	qctask = qcconf.root.get(qc_task)
	if not qctask:
		return {
			"base_mri_image_path": None,
			"overlay_mri_image_path": None,
			"svg_montage_path": None,
			"iqm_path": None,
			"mesh_paths": None,
		}

	# qctask is a QCTask model; its fields are Path or None already
	return {
		"base_mri_image_path": qctask.base_mri_image_path,
		"overlay_mri_image_path": qctask.overlay_mri_image_path,
		"svg_montage_path": qctask.svg_montage_path,
		"iqm_path": qctask.iqm_path,
		"mesh_paths": qctask.mesh_paths,
	}


def load_mri_data(path_dict: dict) -> dict:
	"""Load base and overlay MRI image files as bytes."""
	base_mri_path = path_dict.get("base_mri_image_path")
	overlay_mri_path = path_dict.get("overlay_mri_image_path")

	file_bytes_dict = {}

	if base_mri_path and Path(base_mri_path).is_file():
		file_bytes_dict["base_mri_image_bytes"] = Path(base_mri_path).read_bytes()

	if overlay_mri_path and Path(overlay_mri_path).is_file():
		file_bytes_dict["overlay_mri_image_bytes"] = Path(overlay_mri_path).read_bytes()

	return file_bytes_dict


def load_svg_data(path_dict: dict) -> str | None:
	"""Load SVG montage file content as string."""
	svg_montage_path = path_dict.get("svg_montage_path")
	if svg_montage_path and svg_montage_path.is_file():
		try:
			with open(svg_montage_path, "r") as f:
				return f.read()
		except Exception:
			return None
	return None


def load_iqm_data(path_dict: dict):
	"""
	Load IQM files.
	- TSV files are returned as pandas DataFrames
	- JSON files are returned as dicts

	Returns a list of loaded objects (possibly empty).
	"""
	iqm_paths = path_dict.get("iqm_path") or []
	out = []

	for p in iqm_paths:
		p = Path(p)
		if not p.is_file():
			continue

		suffix = p.suffix.lower()

		if suffix == ".tsv":
			try:
				out.append(pd.read_csv(p, sep="\t"))
			except Exception:
				pass
		elif suffix == ".json":
			try:
				out.append(json.loads(p.read_text()))
			except Exception:
				pass
		else:
			try:
				out.append(p.read_text())
			except Exception:
				pass

	return out


def save_qc_results_to_csv(out_file, qc_records):
	"""
	Save QC results to a CSV/TSV file. Accepts QCRecord objects or dicts.
	Overwrites rows by identity keys.

	Output columns:
	  qc_task, participant_id, session_id, task_id, run_id, pipeline,
	  timestamp, rater_id, rater_experience, rater_fatigue, final_qc, notes
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

		row = {
			"qc_task": rec_dict.get("qc_task"),
			"participant_id": rec_dict.get("participant_id"),
			"session_id": rec_dict.get("session_id"),
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

	df = pd.DataFrame(rows)
	if out_file.exists():
		df_existing = pd.read_csv(out_file, sep="\t")
		df = pd.concat([df_existing, df], ignore_index=True)
		# Drop duplicates based on core identity columns
		subset_keys = ["participant_id", "session_id", "pipeline", "qc_task"]
		existing_keys = [k for k in subset_keys if k in df.columns]
		if existing_keys:
			df = df.drop_duplicates(subset=existing_keys, keep="last")

	if "participant_id" in df.columns:
		df = df.sort_values(by=["participant_id"]).reset_index(drop=True)
	df = df.reindex(columns=QCRecord.csv_columns())

	df.to_csv(out_file, index=False, sep="\t")
	return out_file
