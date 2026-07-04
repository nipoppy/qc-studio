"""Data loading utilities for QC Studio.

This module provides functions for loading MRI data, SVG montages, and IQM metrics
from files and directories.
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Union

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
	if isinstance(svg_paths_value, (str, Path)):
		svg_paths_value = [svg_paths_value]
	elif not isinstance(svg_paths_value, list):
		return None
	
	if not svg_paths_value:
		return None
	
	return _load_svg_data_cached(
		str(dataset_dir) if dataset_dir else "",
		tuple(str(path) for path in svg_paths_value),
		max_montage_rows,
		max_montage_cols,
	)


@st.cache_data(show_spinner=False, max_entries=128)
def _load_svg_data_cached(dataset_dir: str, svg_paths: tuple, max_montage_rows=None, max_montage_cols=None) -> Optional[dict]:
	"""Load montage image files and build display data.

	This cached helper does the expensive work: resolving paths, reading SVG
	text, loading raster images, converting images for montage creation, and
	building an optional grid montage.

	Args:
		dataset_dir: Base directory path for resolving relative paths.
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
				with open(full_path, encoding="utf-8") as f:
					svg_content = f.read()
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
