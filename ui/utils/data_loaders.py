"""Data loading utilities for QC Studio.

This module provides functions for loading MRI data, SVG montages, and IQM metrics
from files and directories.
"""

import json
import os
import re
import pandas as pd

from pathlib import Path
from typing import Optional, Dict, List, Union

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Reference-data host is not committed to source; set REFERENCE_DATA_URL in
# the environment (or a .env file) before running the app.
URL_PARENT = os.environ.get("REFERENCE_DATA_URL")

REFERENCE_CACHE_DIR = Path(".streamlit/reference_cache")
REFERENCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

MAX_REFERENCE_ROWS = 50_000
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60

UNKNOWN_LABELS = {"", "unknown", "nan", "none", "na", "n/a", "null"}

MANUFACTURER_ALIASES = {
    "siemens": "siemens",
    "siemens healthineers": "siemens",
    "siemens healthcare": "siemens",

    "ge": "ge",
    "general electric": "ge",
    "ge healthcare": "ge",
    "ge medical systems": "ge",

    "philips": "philips",
    "philips healthcare": "philips",
    "philips medical systems": "philips",
}

FIELD_STRENGTH_ALIASES = {
	"1.0": "1",
	"1t": "1",
	"3.0": "3",
	"3T": "3",
	"3t": "3",
}


def load_mri_data(
	dataset_dir: Union[str, Path, dict],
	path_dict: Optional[dict] = None,
) -> dict:
	"""Load base and overlay MRI image files as bytes.

	Supports ``load_mri_data(dataset_dir, path_dict)`` (paths relative to
	``dataset_dir``) and ``load_mri_data(path_dict)`` (paths already absolute
	or cwd-relative).

	Args:
		dataset_dir: Root directory containing the dataset, or a path_dict if
			``path_dict`` is omitted.
		path_dict: Dictionary with keys 'base_mri_image_path' and 'overlay_mri_image_path'
	
	Returns:
		dict with keys: 'base_mri_image_bytes', 'base_mri_image_path', 
		'overlay_mri_image_bytes', 'overlay_mri_image_path'
		Returns empty dict if files don't exist
	"""
	if path_dict is None:
		if not isinstance(dataset_dir, dict):
			raise TypeError("load_mri_data: pass either path_dict only or (dataset_dir, path_dict)")
		path_dict = dataset_dir
		dataset_dir = ""
	elif not path_dict.get("base_mri_image_path") and not path_dict.get("overlay_mri_image_path"):
		raise TypeError("load_mri_data: at least one MRI path must be provided")

	base_root = Path(dataset_dir) if dataset_dir else Path()
	base_mri_path = base_root / path_dict.get("base_mri_image_path") if path_dict.get("base_mri_image_path") else None
	overlay_mri_path = base_root / path_dict.get("overlay_mri_image_path") if path_dict.get("overlay_mri_image_path") else None

	# print(f"Loading MRI data from dataset_dir: {dataset_dir} with paths: base_mri={base_mri_path}, overlay_mri={overlay_mri_path}")
	file_bytes_dict = {}

	if base_mri_path is not None and base_mri_path.is_file():
		file_bytes_dict["base_mri_image_bytes"] = base_mri_path.read_bytes()
		file_bytes_dict["base_mri_image_path"] = base_mri_path

	if overlay_mri_path is not None and overlay_mri_path.is_file():
		file_bytes_dict["overlay_mri_image_bytes"] = overlay_mri_path.read_bytes()
		file_bytes_dict["overlay_mri_image_path"] = overlay_mri_path

	return file_bytes_dict


def load_svg_data(dataset_dir, path_dict: dict, max_montage_rows=None, max_montage_cols=None) -> Optional[dict]:
	"""Load SVG/image montage files and return for display with optional grid montage.
	
	Creates a display dict with individual image files (SVG as strings, PNG/JPEG as PIL Images),
	plus an optional grid montage if multiple images are provided and montage parameters are set.
	
	Args:
		dataset_dir: Base directory path for resolving relative paths
		path_dict: Dictionary containing 'svg_montage_path' key with:
			- None (no montage)
			- Single Path/str object
			- List of Path/str objects
		max_montage_rows: Maximum rows for grid montage (optional, requires multiple images)
		max_montage_cols: Maximum columns for grid montage (optional, requires multiple images)
	
	Returns:
		Dict with format:
			For single/list of files: {
				"filename1": {"type": "svg"|"png"|"jpeg", "content": string|PIL.Image},
				"filename2": {"type": "svg"|"png"|"jpeg", "content": string|PIL.Image},
				...
			}
		
		If montage parameters are provided and multiple images exist:
			{
				"montage": {"type": "png", "content": PIL.Image (grid montage)},
				"filename1": {...},
				"filename2": {...},
				...
			}
		
		Returns None if no valid image files found, path is None, or directory is invalid.
	
	Notes:
		- SVG files: returned as HTML string (can be rendered with st.components.v1.html)
		- PNG/JPEG files: returned as PIL Image objects (can be rendered with st.image)
		- Unsupported formats are silently skipped
		- Individual SVG files are included in montage only after conversion to images
	"""
	svg_paths_value = path_dict.get("svg_montage_path")
	if not svg_paths_value:
		return None
	
	# Normalize to list of paths
	if isinstance(svg_paths_value, (str, Path)):
		svg_paths_value = [svg_paths_value]
	elif not isinstance(svg_paths_value, list):
		return None
	
	if not svg_paths_value:
		return None
	
	image_data_dict = {}
	images_for_montage = []  # Collect PIL Images for montage creation
	
	for i, svg_path in enumerate(svg_paths_value):
		full_path = Path(dataset_dir).joinpath(str(svg_path)) if dataset_dir else Path(svg_path)
		
		if not full_path.is_file():
			# Some pipelines omit session entity in generated figure names.
			no_ses_name = re.sub(r'_ses-[^_]+', '', full_path.name)
			fallback_path = full_path.parent / no_ses_name
			if fallback_path.is_file():
				full_path = fallback_path
			else:
				continue
		
		file_ext = full_path.suffix.lower()
		
		# Create unique identifier using last 3 path components to avoid collisions
		# E.g., "screenshots/sub-CMH0001/sub-CMH0001.png" -> "screenshots_sub-CMH0001_sub"
		path_parts = full_path.parts
		if len(path_parts) >= 3:
			# Use last 3 path components (grandparent dir + parent dir + stem)
			grandparent = path_parts[-3]
			parent = path_parts[-2]
			stem = full_path.stem
			unique_id = f"{grandparent}_{parent}_{stem}"
		elif len(path_parts) >= 2:
			# Fallback: use parent dir + stem
			parent = path_parts[-2]
			stem = full_path.stem
			unique_id = f"{parent}_{stem}"
		else:
			unique_id = full_path.stem
		
		if file_ext == '.svg':
			# Return SVG as string content (use open() so tests can mock builtins.open)
			try:
				svg_content = full_path.read_text(encoding="utf-8")
				filename = f"{unique_id}_svg"
				image_data_dict[filename] = {
					"type": "svg",
					"content": svg_content
				}
				# Convert SVG to image for montage (optional - if conversion fails, SVG is still available as string)
				try:
					pil_img = _load_image_from_file(full_path)
					images_for_montage.append(pil_img)
				except Exception:
					# SVG conversion not critical; skip but keep the SVG string version for rendering
					pass
			except Exception as e:
				print(f"Failed to load SVG file {full_path}: {e}")
				continue
		
		elif file_ext in ['.png', '.jpg', '.jpeg']:
			# Return PNG/JPEG as PIL Image
			try:
				pil_img = _load_image_from_file(full_path)
				raster_type = "jpeg" if file_ext in (".jpg", ".jpeg") else file_ext.lstrip(".")
				filename = f"{unique_id}_{raster_type}"
				image_data_dict[filename] = {
					"type": raster_type,
					"content": pil_img
				}
				images_for_montage.append(pil_img)
			except ValueError as e:
				print(f"Failed to load image file {full_path}: {e}")
				continue
	
	if not image_data_dict:
		return None
	
	# Auto-generate a grid montage whenever multiple images are available.
	# `create_grid_montage` computes rows/cols when max_rows/max_cols are None.
	if len(images_for_montage) > 1:
		try:
			from .image_processing import create_grid_montage
			montage_img = create_grid_montage(
				images_for_montage,
				max_rows=max_montage_rows,
				max_cols=max_montage_cols
			)
			# Insert montage at the beginning of result dict
			result_dict = {"montage": {"type": "png", "content": montage_img}}
			result_dict.update(image_data_dict)
			return result_dict
		except Exception as e:
			print(f"Failed to create montage: {e}")
			# Return individual images if montage creation fails
			return image_data_dict
	
	# Return individual images (no montage for single image)
	return image_data_dict


def _load_image_from_file(file_path, dpi=96):
	"""Load image from file path, supporting both raster and SVG formats.
	
	Args:
		file_path: Path to image file (SVG, PNG, JPG, JPEG)
		dpi: DPI for SVG rendering (default: 96)
	
	Returns:
		PIL.Image: Image object in RGB mode
		
	Raises:
		ValueError: If file format is not supported or conversion fails
	"""
	from io import BytesIO
	from PIL import Image
	
	file_path = Path(file_path)
	file_ext = file_path.suffix.lower()
	
	if not file_path.exists():
		raise ValueError(f"File not found: {file_path}")
	
	if file_ext == '.svg':
		try:			
			import cairosvg
			# Convert SVG to PNG in memory
			png_data = cairosvg.svg2png(bytestring=file_path.read_bytes(), dpi=dpi)
			img = Image.open(BytesIO(png_data))
		except ImportError:
			raise ValueError(
				"cairosvg library required for SVG support. "
				"Install it with: pip install cairosvg"
			)
		except Exception as e:
			raise ValueError(f"Failed to convert SVG file {file_path}: {e}")
	elif file_ext in ['.png', '.jpg', '.jpeg']:
		try:
			img = Image.open(file_path)
		except Exception as e:
			raise ValueError(f"Failed to load image file {file_path}: {e}")
	else:
		raise ValueError(
			f"Unsupported image format: {file_ext}. "
			f"Supported formats: SVG, PNG, JPG, JPEG"
		)
	
	# Ensure image is in RGB mode
	if img.mode != 'RGB':
		img = img.convert('RGB')
	
	return img


def _resolve_metadata_path(image_path: Union[Path, str]) -> Path:
	"""Returning the JSON sidecar path for a BIDS image file."""
	if not image_path:
		return None
	image_path = Path(image_path)
	image_name = image_path.name
	if image_name.endswith('.nii.gz'):
		json_name = image_name.replace('.nii.gz', '.json')
	elif image_name.endswith('.nii'):
		json_name = image_name.replace('.nii', '.json')
	else:
		return None
	
	return image_path.parent / json_name


def _infer_bids_ids_from_path(image_path: Union[Path, str]) -> tuple:
	"""Infer BIDS participant/session IDs from a file path string."""
	if not image_path:
		return None, None

	path_str = str(image_path)
	participant_match = re.search(r"(sub-[A-Za-z0-9]+)", path_str)
	session_match = re.search(r"(ses-[A-Za-z0-9]+)", path_str)

	participant_id = participant_match.group(1) if participant_match else None
	session_id = session_match.group(1) if session_match else None
	return participant_id, session_id


def _infer_dataset_root_from_path(image_path: Union[Path, str]) -> Optional[Path]:
	"""Infer dataset root from a path containing BIDS-like folders."""
	if not image_path:
		return None

	path_obj = Path(image_path)
	parts = path_obj.parts

	if "derivatives" in parts:
		idx = parts.index("derivatives")
		return Path(*parts[:idx]) if idx > 0 else Path(".")

	if "bids" in parts:
		idx = parts.index("bids")
		return Path(*parts[:idx]) if idx > 0 else Path(".")

	return None


# Folder + filename-suffix to search for, per BIDS modality.
MODALITY_SIDECAR_HINTS = {
	"anat": ("anat", "T1w"),
	"t1w": ("anat", "T1w"),
	"func": ("func", "bold"),
	"bold": ("func", "bold"),
	"dwi": ("dwi", "dwi"),
	"diffusion": ("dwi", "dwi"),
}


def _infer_modality_from_path(image_path: Union[Path, str]) -> str:
	"""Infer a BIDS modality hint ('anat', 'func', 'dwi') from an image path/filename."""
	if not image_path:
		return "anat"

	path_str = str(image_path).lower()
	if re.search(r"_(bold|sbref)\.", path_str) or "/func/" in path_str:
		return "func"
	if re.search(r"_dwi\.", path_str) or "/dwi/" in path_str:
		return "dwi"
	return "anat"


def _find_bids_metadata_sidecar(
	dataset_root: Union[Path, str],
	participant_id: str = None,
	session_id: str = None,
	modality: str = "anat",
) -> Optional[Path]:
	"""Find a likely metadata sidecar for a participant, checking raw BIDS first, then derivatives.

	``modality`` selects which BIDS folder/suffix to search (anat/T1w,
	func/bold, dwi/dwi); unrecognized values fall back to anat/T1w. Every
	search pattern is scoped to ``participant_id`` (required) so this never
	returns a *different* participant's sidecar as a guess - if nothing
	matches, it returns ``None`` so callers fall back to "Unknown" instead
	of silently mislabeling the subject's scanner metadata.
	"""
	if not dataset_root or not participant_id:
		return None

	dataset_root = Path(dataset_root)
	folder, suffix = MODALITY_SIDECAR_HINTS.get(str(modality).lower(), ("anat", "T1w"))

	if not participant_id.startswith("sub-"):
		participant_id = f"sub-{participant_id}"
	if session_id and not session_id.startswith("ses-"):
		session_id = f"ses-{session_id}"

	def _patterns_for(prefix: str) -> list:
		patterns = []
		if session_id:
			patterns.extend([
				f"{prefix}{participant_id}/{session_id}/{folder}/*{suffix}*.json",
				f"{prefix}{participant_id}/{session_id}/{folder}/*.json",
				f"{prefix}{participant_id}/{session_id}/**/*{suffix}*.json",
			])
		patterns.extend([
			f"{prefix}{participant_id}/**/*{suffix}*.json",
			f"{prefix}{participant_id}/**/{folder}/*.json",
		])
		return patterns

	# Raw BIDS sidecars are the authoritative source when present.
	bids_root = dataset_root / "bids"
	if not bids_root.is_dir():
		bids_root = dataset_root
	search_roots = [(bids_root, "")]

	# Datasets that only ship pipeline outputs (no raw bids/ folder) still
	# carry scanner metadata in derivative JSON sidecars (e.g. MRIQC), under
	# an unknown pipeline subdirectory - "**/" skips over that layer while
	# still anchoring on participant_id so it can't match another subject.
	derivatives_root = dataset_root / "derivatives"
	if derivatives_root.is_dir():
		search_roots.append((derivatives_root, "**/"))

	for root, prefix in search_roots:
		for pattern in _patterns_for(prefix):
			matches = sorted(root.glob(pattern))
			for match in matches:
				if match.is_file():
					return match

	return None


def _load_scanner_metadata(image_path:Union[Path, str], participant_id: str = None,
							 session_id: str = None, modality: str = None,
							 dataset_dir: Union[Path, str] = None) -> dict:
	"""Load scanner metadata from the JSON sidecar of a BIDS image file.

	``modality`` ("anat"/"func"/"dwi", or their common aliases) selects which
	sidecar to look for when the direct sidecar next to ``image_path`` isn't
	found; when omitted, it's inferred from ``image_path`` itself.

	``image_path`` is commonly a dataset-relative path (e.g. from qc.json,
	like ``"bids/sub-01/..."``); join it onto ``dataset_dir`` first so
	dataset-root/participant/session inference below sees the real root
	instead of resolving to the current working directory.
	"""
	if dataset_dir and image_path:
		image_path = Path(dataset_dir) / image_path

	json_path = _resolve_metadata_path(image_path)
	dataset_root = _infer_dataset_root_from_path(image_path)

	# Prefer IDs inferred from image path when explicit IDs are not provided.
	inferred_participant, inferred_session = _infer_bids_ids_from_path(image_path)
	participant_id = participant_id or inferred_participant
	session_id = session_id or inferred_session
	modality = modality or _infer_modality_from_path(image_path)

	if not json_path or not Path(json_path).is_file():
		json_path = _find_bids_metadata_sidecar(dataset_root, participant_id, session_id, modality=modality)

	# Metadata sidecar may be absent for derivative images. Fall back to
	# unknown values instead of failing the whole IQM panel.
	if not json_path or not Path(json_path).is_file():
		return {
			"Manufacturer": "Unknown",
			"MagneticFieldStrength": "Unknown",
			"ProtocolName": "Unknown",
		}

	with open(json_path, 'r') as f:
		metadata = json.load(f)

	# MRIQC sidecars nest the original BIDS  metadata under "bids_meta" instead of at the top level for individual subjects.
	bids_meta = metadata.get("bids_meta") or {}

	return {
		"Manufacturer": metadata.get("Manufacturer") or bids_meta.get("Manufacturer", "Unknown"),
		"MagneticFieldStrength": metadata.get("MagneticFieldStrength") or bids_meta.get("MagneticFieldStrength", "Unknown"),
		"ProtocolName": metadata.get("ProtocolName") or bids_meta.get("ProtocolName", "Unknown"),
	}

def resolve_iqm_data_path(
	modality_path: str,
	qc_config_path: str = None,
	dataset_dir: str = None,
) -> Path:
	"""Resolve an IQM dataset TSV path across common runtime contexts."""
	path = Path(modality_path)

	if path.is_absolute() and path.is_file():
		return path

	candidates = [Path.cwd() / path]

	if dataset_dir:
		candidates.append(Path(dataset_dir) / path)

	if qc_config_path:
		candidates.append(Path(qc_config_path).parent / path)

	for candidate in candidates:
		if candidate.is_file():
			return candidate

	# Return original path so callers can surface it in error messages.
	return path


def resolve_reference_data_path(ref_path: str, base_dir: Optional[Path] = None) -> Path:
	"""Resolve a reference population TSV path across runtime contexts.

	Args:
		ref_path: Relative or absolute path to the reference TSV.
		base_dir: Optional caller-supplied directory (e.g. the importing
		          module's own directory) added as an additional candidate.
	"""
	path = Path(ref_path)

	if path.is_absolute() and path.is_file():
		return path

	candidates = [Path.cwd() / path]

	if base_dir:
		candidates.append(Path(base_dir) / path)

	for candidate in candidates:
		if candidate.is_file():
			return candidate

	return path


@st.cache_data(show_spinner="Downloading reference data...", ttl=CACHE_TTL_SECONDS)
def _download_reference_parquet_bytes(url: str) -> bytes:
	"""Download reference Parquet content and cache bytes in memory."""
	response = requests.get(url, timeout=120)
	response.raise_for_status()
	return response.content


def download_reference_parquet(modality: str, url_parent: str = URL_PARENT) -> str:
	"""Ensure a reference Parquet file exists locally and return its path."""
	cache_file_path = REFERENCE_CACHE_DIR / f"{modality}.parquet"

	if cache_file_path.exists():
		return str(cache_file_path)

	if not url_parent:
		raise RuntimeError(
			"REFERENCE_DATA_URL is not set. Set it in the environment to enable "
			"downloading reference IQM data."
		)

	url = url_parent.rstrip("/") + f"/{modality}.parquet"
	cache_file_path.write_bytes(_download_reference_parquet_bytes(url))

	return str(cache_file_path)


def normalize_manufacturer(value: object) -> str:
    normalized = str(value or "").strip().lower()

    if normalized in UNKNOWN_LABELS:
        return "unknown"

    return MANUFACTURER_ALIASES.get(normalized, normalized)

#fix this
def normalize_field_strength(value: object) -> Optional[str]:
	normalized = str(value or "").strip().lower()

	if normalized in UNKNOWN_LABELS:
		return None

	if normalized in FIELD_STRENGTH_ALIASES:
		return FIELD_STRENGTH_ALIASES[normalized]

	# try:
	# 	numeric_value = float(normalized)
	# except (TypeError, ValueError):
	# 	return normalized or None

	# # if numeric_value.is_integer():
	# # 	return f"{int(numeric_value)}T"

	# # return f"{numeric_value:g}T"


@st.cache_data(show_spinner="Loading reference data...", ttl=CACHE_TTL_SECONDS)
def _load_reference_parquet(modality: str) -> pd.DataFrame:
    """Load and cache the full, unfiltered reference Parquet table for a modality."""
    local_parquet_path = REFERENCE_CACHE_DIR / f"{modality}.parquet"
    if not local_parquet_path.exists():
        download_reference_parquet(url_parent=URL_PARENT, modality=modality)

    return pd.read_parquet(local_parquet_path, engine="pyarrow")


def load_reference_iqm_for_subject(
    modality: str,
    manufacturer: str,
	field_strength: Optional[object] = None,
    max_rows: int = MAX_REFERENCE_ROWS,
) -> pd.DataFrame:
    """Load and filter reference data for a given subject's scanner."""
    manufacturer_subject_norm = normalize_manufacturer(manufacturer)
    field_strength_subject_norm = normalize_field_strength(field_strength)

    return _load_reference_iqm_filtered(
        modality, manufacturer_subject_norm, field_strength_subject_norm, max_rows
    )


@st.cache_data(show_spinner="Loading reference data...", ttl=CACHE_TTL_SECONDS)
def _load_reference_iqm_filtered(
    modality: str,
    manufacturer_subject_norm: str,
    field_strength_subject_norm: Optional[str],
    max_rows: int,
) -> pd.DataFrame:
    """Filter the cached reference table by already-normalized scanner values.

    Cached on the normalized values (not the raw subject metadata) so that
    different raw spellings that mean the same thing (e.g. "", "N/A", and
    "Unknown", or "GE" and "General Electric") share one cache entry.
    """
    print(f"Loading reference IQM data for modality={modality}, manufacturer={manufacturer_subject_norm}, field_strength={field_strength_subject_norm}")

    data = _load_reference_parquet(modality)

    if manufacturer_subject_norm != "unknown" and "Manufacturer" in data.columns:
        manufacturer_norm = data["Manufacturer"].map(normalize_manufacturer)
        data = data[manufacturer_norm == manufacturer_subject_norm]

    if field_strength_subject_norm is not None and "MagneticFieldStrength" in data.columns:
        field_strength_norm = data["MagneticFieldStrength"].map(normalize_field_strength)
        data = data[field_strength_norm == field_strength_subject_norm]

    if len(data) > max_rows:
        data = data.sample(n=max_rows, random_state=42)

    return data

@st.cache_data(ttl=3600, show_spinner=False)
def _load_iqm_distribution_table(resolved_path) -> pd.DataFrame:
	"""Load a TSV/CSV distribution table and return a DataFrame. Raises on failure -
	the caller decides how to surface that (st.cache_data doesn't cache a raised
	exception, so a transient/fixable failure gets retried on the next rerun
	instead of silently returning a cached None for up to `ttl` seconds)."""

	suffix = resolved_path.suffix.lower()
	return pd.read_csv(resolved_path, sep="," if suffix == ".csv" else "\t")


def _load_iqm_metrics_subject_level(resolved_path) -> dict:
	"""Read a single per-subject IQM metrics file. Raises on failure."""
	return json.loads(Path(resolved_path).read_text(encoding="utf-8"))
	