"""Constants used throughout the QC-Studio UI application."""

# Rater experience levels
EXPERIENCE_LEVELS = ["Beginner (< 1 year experience)", "Intermediate (1-5 year experience)", "Expert (>5 year experience)"]

# Rater fatigue levels
FATIGUE_LEVELS = ["Not at all", "A bit tired ☕", "Very tired ☕☕"]

# Default panel selections
DEFAULT_PANELS = {"niivue": True, "svg": True, "iqm": False}

# Panel configuration metadata
PANEL_CONFIG = {
    "niivue": {"label": "🧠 3D MRI Viewer (Niivue)", "description": "Display interactive 3D MRI viewer", "default": True},
    "svg": {"label": "📊 SVG Montage", "description": "Display SVG montage visualization", "default": True},
    "iqm": {"label": "📈 QC Metrics", "description": "Display QC metrics panel", "default": False},
}

# QC rating options
QC_RATINGS = ["PASS", "FAIL", "UNCERTAIN"]
DEFAULT_QC_RATING = "PASS"

# Columns used to identify duplicate QC rows when merging/saving results
QC_DEDUP_KEYS = ["participant_id", "session_id", "pipeline", "qc_task"]

# Viewer settings
NIIVUE_HEIGHT = 600
SVG_HEIGHT = 600
IQM_HEIGHT = 400
DEFAULT_VIEW_MODE = "multiplanar"
VIEW_MODES = ["multiplanar", "axial", "coronal", "sagittal", "3d"]
OVERLAY_COLORMAPS = ["cool", "warm"]
DEFAULT_OVERLAY_OPACITY = 0.5

# Column layout ratios
NIIVUE_SECONDARY_RATIO = [0.1, 0.3, 0.6]
# Split for viewer area when Niivue + SVG (+ optional third panel) layouts need two columns
NIIVUE_SVG_RATIO = [0.55, 0.45]
EQUAL_RATIO = [0.5, 0.5]
RATING_IQM_RATIO = [0.4, 0.6]
RATER_INFO_RATIO = [1, 1, 1]

# Pagination
DEFAULT_BATCH_SIZE = 1

# Montage grid settings
DEFAULT_MONTAGE_MAX_ROWS = None  # None means auto-calculate
DEFAULT_MONTAGE_MAX_COLS = None  # None means auto-calculate
MIN_MONTAGE_GRID_SIZE = 1
MAX_MONTAGE_GRID_SIZE = 10

# Session state keys
SESSION_KEYS = {
    "current_page": "current_page",
    "batch_size": "batch_size",
    "qc_records": "qc_records",
    "rater_id": "rater_id",
    "rater_experience": "rater_experience",
    "rater_fatigue": "rater_fatigue",
    "notes": "notes",
    "notes_version": "notes_version",
    "rating_version": "rating_version",
    "participant_order": "participant_order",
    "qc_cohort_order": "qc_cohort_order",
    "landing_page_complete": "landing_page_complete",
    "selected_panels": "selected_panels",
    "montage_max_rows": "montage_max_rows",
    "montage_max_cols": "montage_max_cols",
    # Set once per Streamlit session after reading qc.json (avoid re-applying on every rerun)
    "montage_defaults_applied_qc_task": "montage_defaults_applied_qc_task",
}

# File upload settings
UPLOAD_FILE_TYPES = ["csv", "tsv"]
UPLOAD_SEPARATOR_INFERENCE = None  # Let pandas infer

# Substitution formats for participant and session IDs in qc_config
SUBSTITUTIONS_DICT = {
    "participant_id": "[[NIPOPPY_BIDS_PARTICIPANT_ID]]",
    "session_id": "[[NIPOPPY_BIDS_SESSION_ID]]",
    # QSIPrep internal workflow slugs use underscores (ses_01) not BIDS hyphens (ses-01).
    "session_slug": "[[NIPOPPY_QSIPREP_SESSION_SLUG]]",
}

# Messages and UI strings
MESSAGES = {
    "welcome_title": "Welcome to Nipoppy QC-Studio! 🚀",
    "rater_info_header": "👤 Rater Information",
    "rater_id_prompt": "Enter your Rater Name or ID:",
    "experience_prompt": "What is your QC experience level?",
    "fatigue_prompt": "How tired are you feeling?",
    "panels_header": "🖼️ Display Panels",
    "panels_help": "Select which panels to display during QC (at least one required).",
    "panels_validation_warning": "⚠️ You must select at least one panel to proceed!",
    "panels_success": "✅ {count} panel(s) selected",
    "upload_header": "📤 Upload Existing QC File (Optional)",
    "upload_help": "Upload a previously saved QC_status.csv file to resume your QC session or review previous results.",
    "csv_uploader_label": "Choose a QC_status.csv file",
    "continue_button": "✅ Continue to QC",
    "rater_form_button": "✅ Continue to QC",
    "congratulations_title": "🎉 QC Complete! Congratulations! 🎉",
    "export_results_button": "💾 Export Final Results",
    "previous_button": "◀️ Previous",
    "nav_tooltip_previous": ("Previous: navigates to the previous subject or session without saving any rating changes."),
    "nav_tooltip_next": ("Next: navigates to the next subject or session without saving any rating changes."),
    "nav_tooltip_confirm_next": ("Confirm and Next: saves the current QC rating and advances to the next subject or session."),
    "start_over_button": "🔄 Start Over (go to home page)",
    "qc_title": "Nipoppy QC-Studio: Quality Control",
    "qc_rating_header": "QC Rating",
    "qc_rating_prompt": "Rate this qc-task:",
    "qc_notes_prompt": "Notes (optional):",
    "save_csv_button": "💾 Save QC results to CSV",
    "confirm_next_button": "Confirm ✅️ and Next ▶️",
    "next_button": "Next ▶️",
    "play_button": "▶️ Play",
    "pause_button": "⏸️ Pause",
    "back_landing_button": "🏠 Back to Landing Page",
    "sidebar_subjects_header": "Subjects",
    "niivue_header": "3D MRI\n(Niivue)",
    "niivue_controls_header": "Niivue Controls",
    "svg_header": "SVG Montage",
    "metrics_header": "QC Metrics",
    "view_mode_label": "View Mode",
    "overlay_colormap_label": "Overlay Colormap",
    "display_settings_header": "Display Settings",
    "crosshair_label": "Show Crosshair",
    "radiological_label": "Radiological Convention",
    "colorbar_label": "Show Colorbar",
    "interpolation_label": "Interpolation",
    "show_overlay_label": "Show overlay image",
    "panel_selection_header": "Select Panels to Display",
}

# Error messages
ERROR_MESSAGES = {
    "invalid_rater_id": "Please enter a valid Rater ID (no spaces).",
    "no_panel_selected": "⚠️ You must select at least one display panel to proceed!",
    "no_participants": "❌ Error: The uploaded CSV contains {count} participant(s) not in the participant list: {participants}",
    "too_many_participants": "❌ Error: The uploaded CSV has {csv_count} unique participants, but the participant list only has {list_count}.",
    "file_load_error": "❌ Error loading file: {error}",
    "csv_comparison_error": "Could not display comparison: {error}",
    "mri_load_error": "Failed to load base MRI in Niivue viewer: {error}",
    "base_mri_not_found": "Base MRI image not found or could not be loaded.",
    "svg_not_found": "SVG montage not found or could not be loaded.",
    "participant_list_load_error": "Error loading participant list: {error}",
}

# Success messages
SUCCESS_MESSAGES = {
    "csv_loaded": "✅ Loaded {count} QC records from {filename}",
    "records_exported": "✅ All QC results exported to: {path}",
    "records_loaded": "✅ Loaded {count} QC records into session!",
    "records_saved": "✅ QC results saved to: {path}",
}

# Info messages
INFO_MESSAGES = {
    "proceed_with_form": "You can now proceed with the rater form on the left to continue QC.",
    "no_export_records": "No QC records to export.",
    "rater_info_extracted": "📋 Rater information extracted:",
    "rater_id_prefix": "- **Rater ID:** {id}",
    "experience_prefix": "- **Experience:** {exp}",
    "fatigue_prefix": "- **Fatigue Level:** {fatigue}",
    "preview_header": "Preview of Loaded Records",
    "load_records_button": "📥 Load These Records",
}
