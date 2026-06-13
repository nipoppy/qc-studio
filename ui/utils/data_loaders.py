"""Data loading utilities for QC Studio.

This module provides functions for loading MRI data, SVG montages, and IQM metrics
from files and directories.
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, List


def _sanitize_svg(svg_content: str) -> str:
    """Remove JavaScript and event handlers from SVG content to prevent XSS.
    
    Strips <script> tags and all on* event handler attributes (e.g., onload, onerror).
    """
    # Remove <script> tags and their content
    svg_content = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', svg_content, flags=re.IGNORECASE)
    # Remove on* event handlers (e.g., onload, onerror) with quoted values
    svg_content = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', svg_content, flags=re.IGNORECASE)
    # Remove on* event handlers with unquoted values
    svg_content = re.sub(r'\s+on\w+\s*=\s*[^\s>]+', '', svg_content, flags=re.IGNORECASE)
    return svg_content


def load_mri_data(dataset_dir, path_dict: dict) -> dict:
	"""Load base and overlay MRI image files as bytes.
	
	Args:
		dataset_dir: Root directory containing the dataset
		path_dict: Dictionary with keys 'base_mri_image_path' and 'overlay_mri_image_path'
	
	Returns:
		dict with keys: 'base_mri_image_bytes', 'base_mri_image_path', 
		'overlay_mri_image_bytes', 'overlay_mri_image_path'
		Returns empty dict if files don't exist
	"""
	base_mri_path = Path(dataset_dir).joinpath(path_dict.get("base_mri_image_path"))
	overlay_mri_path = Path(dataset_dir).joinpath(path_dict.get("overlay_mri_image_path"))

	# print(f"Loading MRI data from dataset_dir: {dataset_dir} with paths: base_mri={base_mri_path}, overlay_mri={overlay_mri_path}")
	file_bytes_dict = {}

	if base_mri_path and Path(base_mri_path).is_file():
		file_bytes_dict["base_mri_image_bytes"] = Path(base_mri_path).read_bytes()
		file_bytes_dict["base_mri_image_path"] = base_mri_path

	if overlay_mri_path and Path(overlay_mri_path).is_file():
		file_bytes_dict["overlay_mri_image_bytes"] = Path(overlay_mri_path).read_bytes()
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
		# E.g., "screenshots/sub-ED01/sub-ED01.png" -> "screenshots_sub-ED01_sub"
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
			# Return SVG as string content
			try:
				svg_content = full_path.read_text(encoding='utf-8')
				# SECURITY: Sanitize SVG to remove scripts and event handlers to prevent XSS
				svg_content = _sanitize_svg(svg_content)
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
				filename = f"{unique_id}_{file_ext.lstrip('.')}"
				image_data_dict[filename] = {
					"type": file_ext.lstrip('.'),
					"content": pil_img
				}
				images_for_montage.append(pil_img)
			except ValueError as e:
				print(f"Failed to load image file {full_path}: {e}")
				continue
	
	if not image_data_dict:
		return None
	
	# Create montage if multiple images exist (will auto-calculate layout if no constraints provided)
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
