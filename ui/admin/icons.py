"""Emojis for the admin dashboard: one per concept, used the same way everywhere.

Import these instead of typing emoji literals in the views, so a concept keeps one icon
(e.g. 👥 always means raters/users, 🧪 always means QC tasks).
"""

# Core concepts
USERS = "👥"
RATER = "👤"
ADMIN = "🛡️"
VIEWER = "👁️"
DATASET = "🗂️"
QC_TASKS = "🧪"

# Tabs
OVERVIEW = "🏠"
ASSIGNMENTS = "📋"
RATINGS = "✅"

# Sections
PROGRESS = "📈"
NEW_LIST = "📝"
PACE = "⏱️"
SITTINGS = "🪑"
FACETS = "🔍"
AGREEMENT = "🤝"
FINAL_QC = "⭐"
CONFIG = "🔧"

# Rater actions (Raters tab)
ADD = "➕"
EDIT = "✏️"
REMOVE = "🗑️"
