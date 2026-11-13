"""QC-Studio admin dashboard.

Assign rater workloads and collate everyone's ratings. Only emails listed in the users
config's top-level ``admins`` (full access) or ``viewers`` (view only) get in. Run it separately from the rater app, on its own port
and (in production) behind its own Cloudflare Access application:

    streamlit run ui/admin/admin_app.py --server.port=8502 --server.address=127.0.0.1 -- \\
        --users_config /data/qc-raters/users.json \\
        --participant_list /data/qc_participants.tsv \\
        --qc_json ../pipelines/fsqc/qc.json [--qc_pipeline fsqc] [--qc_task all] \\
        [--output_dir /data/qc-raters/reports] [--session_list ses-BL]

The tasks in qc.json are the ones raters are expected to complete. The pipeline comes from
qc.json's "__pipeline__" key, else --qc_pipeline (they must agree if both are given).

This script lives in its own folder so Streamlit does not add the rater app's ``ui/pages``
to this app's sidebar.
"""

import sys
from pathlib import Path

ADMIN_DIR = Path(__file__).resolve().parent
UI_DIR = ADMIN_DIR.parent
# `streamlit run` puts this folder first on sys.path; drop it so `views`/`core` can't shadow
# the rater app's packages, and import everything from ui/ (admin code as `admin.*`).
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != ADMIN_DIR]
if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))

import streamlit as st  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

# Same identity settings (CF_ACCESS_*) as the rater app: repo .env, then the working directory's.
load_dotenv(UI_DIR.parent / ".env")
load_dotenv()

from admin import icons  # noqa: E402
from admin.core import build_context, parse_admin_args, require_dashboard_access  # noqa: E402
from admin.views import assignments, overview, ratings, raters  # noqa: E402


def main() -> None:
    st.set_page_config(page_title="QC-Studio admin", page_icon="🛠️", layout="wide")
    args = parse_admin_args()
    email, cfg, role = require_dashboard_access(args.users_config)
    ctx = build_context(args, email, cfg, role)

    title, who, refresh = st.columns([6, 3, 1], vertical_alignment="bottom")
    title.title("QC-Studio admin")
    who.caption(f"👤 Signed in as {email}" + ("" if ctx.can_edit else " · view only"))
    if refresh.button("🔄", help="Reload the users config, participant lists and ratings from disk"):
        st.cache_data.clear()
        st.rerun()

    tab_overview, tab_raters, tab_assign, tab_ratings = st.tabs(
        [f"{icons.OVERVIEW} Overview", f"{icons.USERS} Raters", f"{icons.ASSIGNMENTS} Assignments", f"{icons.RATINGS} Ratings"]
    )
    with tab_overview:
        overview.render(ctx)
    with tab_raters:
        raters.render(ctx)
    with tab_assign:
        assignments.render(ctx)
    with tab_ratings:
        ratings.render(ctx)


if __name__ == "__main__":
    main()
