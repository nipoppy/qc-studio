"""Data loading utilities for QC Studio.

This module provides functions for loading MRI data, SVG montages, and IQM metrics
from files and directories.
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Union, Tuple

from constants import NIIVUE_MAX_FILE_BYTES


def _resolve_all_under_dataset(base_root: Path, rel_path: Union[str, Path, None]) -> list[Path]:
	"""Resolve a dataset-relative path to zero or more files (globs return all sorted matches)."""
	if rel_path is None:
		return []
	rel = Path(rel_path)
	direct = base_root / rel
	if "*" in str(rel):
		matches = sorted(p for p in base_root.glob(str(rel)) if p.is_file())
		if matches:
			return matches
	if direct.is_file():
		return [direct]
	no_ses_name = re.sub(r"_ses-[^_]+", "", direct.name)
	fallback = direct.parent / no_ses_name
	if fallback.is_file():
		return [fallback]
	return []


def _expand_dataset_paths(base_root: Path, paths_value: Union[str, Path, list, None]) -> list[Path]:
	"""Expand path specs to concrete files; globs include every match."""
	if paths_value is None:
		return []
	specs = paths_value if isinstance(paths_value, list) else [paths_value]
	expanded: list[Path] = []
	seen: set[Path] = set()
	for spec in specs:
		for path in _resolve_all_under_dataset(base_root, spec):
			if path not in seen:
				seen.add(path)
				expanded.append(path)
	return expanded


def _resolve_under_dataset(base_root: Path, rel_path: Union[str, Path, None]) -> Optional[Path]:
	"""Resolve a single dataset-relative file (first glob match when multiple exist)."""
	matches = _resolve_all_under_dataset(base_root, rel_path)
	return matches[0] if matches else None


def _nifti_volume_to_bytes(img, vol_index: int = 0) -> bytes:
	"""Serialize one 3D volume from a NIfTI image (handles 4D via mmap slice)."""
	import numpy as np
	import nibabel as nib

	shape = img.shape
	if len(shape) == 4:
		vol = np.asanyarray(img.dataobj[..., vol_index])
	elif len(shape) == 3:
		vol = np.asanyarray(img.dataobj)
	else:
		raise ValueError(f"Unsupported NIfTI rank for Niivue preview: {len(shape)}")
	hdr = img.header.copy()
	hdr.set_data_shape(vol.shape)
	out = nib.Nifti1Image(vol, img.affine, hdr)
	return out.to_bytes()


def _read_nifti_bytes_for_niivue(path: Path) -> Tuple[Optional[bytes], bool, Optional[str]]:
	"""Load NIfTI bytes for Niivue; reduce 4D / oversize files to the first volume."""
	size = path.stat().st_size
	try:
		import nibabel as nib
	except ImportError:
		if size > NIIVUE_MAX_FILE_BYTES:
			return None, False, "oversize"
		return path.read_bytes(), False, None

	try:
		img = nib.load(str(path))
		reduce = size > NIIVUE_MAX_FILE_BYTES or len(img.shape) == 4
		if reduce:
			vol_bytes = _nifti_volume_to_bytes(img, vol_index=0)
			if len(vol_bytes) > NIIVUE_MAX_FILE_BYTES:
				return None, True, "oversize"
			return vol_bytes, True, None
		if size > NIIVUE_MAX_FILE_BYTES:
			return None, False, "oversize"
		return path.read_bytes(), False, None
	except Exception:
		if size <= NIIVUE_MAX_FILE_BYTES:
			return path.read_bytes(), False, None
		return None, False, "oversize"


def _attach_nifti_bytes(file_bytes_dict: dict, path: Path, prefix: str) -> None:
	"""Read NIfTI bytes for Niivue (first BOLD volume when 4D or file is large)."""
	nbytes, reduced, err = _read_nifti_bytes_for_niivue(path)
	file_bytes_dict[f"{prefix}_mri_image_path"] = path
	if nbytes is not None:
		file_bytes_dict[f"{prefix}_mri_image_bytes"] = nbytes
		if reduced:
			file_bytes_dict[f"{prefix}_mri_preview_reduced"] = True
		return
	if err == "oversize":
		file_bytes_dict[f"{prefix}_mri_oversize"] = True
		file_bytes_dict[f"{prefix}_mri_size_bytes"] = path.stat().st_size

import streamlit as st


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

	base_root = Path(dataset_dir) if dataset_dir else Path()
	base_mri_path = _resolve_under_dataset(base_root, path_dict.get("base_mri_image_path"))
	overlay_mri_path = _resolve_under_dataset(base_root, path_dict.get("overlay_mri_image_path"))

	# print(f"Loading MRI data from dataset_dir: {dataset_dir} with paths: base_mri={base_mri_path}, overlay_mri={overlay_mri_path}")
	file_bytes_dict = {}

	if base_mri_path is not None and base_mri_path.is_file():
		_attach_nifti_bytes(file_bytes_dict, base_mri_path, "base")

	if overlay_mri_path is not None and overlay_mri_path.is_file():
		_attach_nifti_bytes(file_bytes_dict, overlay_mri_path, "overlay")

	return file_bytes_dict


def load_iqm_data(path_dict: dict) -> Optional[dict]:
	"""Load IQM metrics from a JSON file referenced by ``path_dict['iqm_path']``.

	Returns ``None`` if the path is missing, the file does not exist, or JSON is invalid.
	"""
	iqm_ref = path_dict.get("iqm_path")
	if not iqm_ref:
		return None
	iqm_path = Path(iqm_ref)
	if not iqm_path.is_file():
		return None
	try:
		return json.loads(iqm_path.read_text(encoding="utf-8"))
	except (json.JSONDecodeError, OSError):
		return None


def _normalize_svg_paths(svg_paths_value):
	"""Normalize montage paths to a list of Path objects."""

	if isinstance(svg_paths_value, (str, Path)):
		return [Path(svg_paths_value)]
	
	if isinstance(svg_paths_value, list):
		normalized_paths = []
		for p in svg_paths_value:
			if p is None:
				continue
			try:
				normalized_paths.append(Path(p))
			except TypeError:
				# Ignore malformed path entries and keep loading valid montage files.
				continue
		return normalized_paths
	
	return None


def load_svg_data(dataset_dir, path_dict: dict, max_montage_rows=None, max_montage_cols=None) -> Optional[dict]:
	"""Normalize montage paths from a QC config and return cached image data.

	This public wrapper keeps the config-dictionary API used by callers while
	delegating expensive file reads, image conversion, and montage creation to
	``_load_svg_data_cached``.
	
	Args:
		dataset_dir: Base directory path for resolving relative paths.
		path_dict: Dictionary containing 'svg_montage_path' key with:
			- None (no montage)
			- Single Path/str object
			- List of Path/str objects
		max_montage_rows: Maximum rows for grid montage.
		max_montage_cols: Maximum columns for grid montage.
	
	Returns:
		Cached display data from ``_load_svg_data_cached``, or None if no
		montage paths are configured.
	"""
	svg_paths_value = path_dict.get("svg_montage_path")
	if not svg_paths_value:
		return None
	
	# Normalize to list of paths
	svg_paths_value = _normalize_svg_paths(svg_paths_value)
	
	if not svg_paths_value:
		return None

	base_root = Path(dataset_dir) if dataset_dir else Path()
	resolved_paths = _expand_dataset_paths(base_root, svg_paths_value)
	if not resolved_paths:
		return None

	return _load_svg_data_cached(
		tuple(str(path) for path in resolved_paths),
		max_montage_rows,
		max_montage_cols,
	)


def _create_unique_id_from_path(file_path: Path) -> str:
	"""Create a unique identifier from the last 2-3 components of a file path.

	Args:
		file_path: Path object for the file.

	Returns:
		Unique identifier string based on the last 2-3 path components.
	"""
	path_parts = file_path.parts

	if len(path_parts) >= 3:
		# Use last 3 path components (grandparent dir + parent dir + stem)
		grandparent = path_parts[-3]
		parent = path_parts[-2]
		stem = file_path.stem
		return f"{grandparent}_{parent}_{stem}"
	elif len(path_parts) >= 2:
		# Fallback: use parent dir + stem
		parent = path_parts[-2]
		stem = file_path.stem
		return f"{parent}_{stem}"
	else:
		return file_path.stem


def _load_svg_entry(full_path: Path, unique_id: str):
	try:
		with open(full_path, encoding="utf-8") as f:
			svg_content = f.read()

		filename = f"{unique_id}_svg"
		data_content = {
			"type": "svg",
			"content": svg_content,
		}

		# Convert SVG to image for montage (optional - if conversion fails, SVG is still available as string)
		try:
			pil_img = _load_image_from_file(full_path)
		except Exception:
			# SVG conversion not critical; skip but keep the SVG string version for rendering
			pil_img = None

		return filename, data_content, pil_img

	except Exception as e:
		print(f"Failed to load SVG file {full_path}: {e}")
		return None
	
			
def _load_raster_entry(full_path: Path, unique_id: str, raster_type: str):
	try:
		pil_img = _load_image_from_file(full_path)
		
		filename = f"{unique_id}_{raster_type}"
		data_content = {
			"type": raster_type,
			"content": pil_img
		}
		return filename, data_content, pil_img
	
	except ValueError as e:
		print(f"Failed to load image file {full_path}: {e}")
		return None


def _add_montage_if_available(
	image_data_dict: dict,
	images_for_montage: list,
	max_montage_rows=None,
	max_montage_cols=None,
) -> dict:
	if len(images_for_montage) <= 1:
		# Return individual images (no montage for single image)
		return image_data_dict

	try:
		from .image_processing import create_grid_montage
		montage_img = create_grid_montage(
			images_for_montage,
			max_rows=max_montage_rows,
			max_cols=max_montage_cols,
		)
		# Insert montage at the beginning of result dict
		result_dict = {"montage": {"type": "png", "content": montage_img}}
		result_dict.update(image_data_dict)
		return result_dict
	except Exception as e:
		print(f"Failed to create montage: {e}")
		# Return individual images if montage creation fails
		return image_data_dict


@st.cache_data(show_spinner=False, max_entries=128)
def _load_svg_data_cached(svg_paths: tuple, max_montage_rows=None, max_montage_cols=None) -> Optional[dict]:
	"""Load montage image files and build display data.

	This cached helper does the expensive work: resolving paths, reading SVG
	text, loading raster images, converting images for montage creation, and
	building an optional grid montage.

	Args:
		svg_paths: Tuple of SVG/PNG/JPEG paths to load.
		max_montage_rows: Maximum rows for grid montage.
		max_montage_cols: Maximum columns for grid montage.

	Returns:
		Dict with image keys mapped to ``{"type": ..., "content": ...}``.
		SVG content is returned as a string; PNG/JPEG content is returned as a
		PIL Image. If multiple images can be converted for montage display, a
		``"montage"`` entry is inserted first. Returns None if no valid image
		files are found.

	Notes:
		- Unsupported formats are silently skipped.
		- SVG-to-image conversion is optional; if conversion fails, the SVG text
		  is still returned for direct rendering.
	"""
	image_data_dict = {}
	images_for_montage = []  # Collect PIL Images for montage creation
	
	for svg_path in svg_paths:
		full_path = Path(svg_path)
		if not full_path.is_file():
			continue
		file_ext = full_path.suffix.lower()
		
		# Create unique identifier using last 3 path components to avoid collisions
		# E.g., "screenshots/sub-CMH0001/sub-CMH0001.png" -> "screenshots_sub-CMH0001_sub"
		unique_id = _create_unique_id_from_path(full_path)

		if file_ext == '.svg':
			# Return SVG as string content (use open() so tests can mock builtins.open)
			loaded_entry = _load_svg_entry(full_path, unique_id)
			if loaded_entry is None:
				continue
			filename, data_content, pil_img = loaded_entry
			image_data_dict[filename] = data_content
			if pil_img is not None:
				images_for_montage.append(pil_img)

		elif file_ext in ['.png', '.jpg', '.jpeg']:
			# Return PNG/JPEG as PIL Image
			raster_type = "jpeg" if file_ext in (".jpg", ".jpeg") else file_ext.lstrip(".")
			loaded_entry = _load_raster_entry(full_path, unique_id, raster_type)
			if loaded_entry is None:
				continue
			filename, data_content, pil_img = loaded_entry
			image_data_dict[filename] = data_content
			images_for_montage.append(pil_img)
	
	if not image_data_dict:
		return None
	
	return _add_montage_if_available(
		image_data_dict,
		images_for_montage,
		max_montage_rows=max_montage_rows,
		max_montage_cols=max_montage_cols,
	)


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
