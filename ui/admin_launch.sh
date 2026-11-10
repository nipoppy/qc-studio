#!/usr/bin/env bash
# Launch the QC-Studio admin dashboard (workloads + collated ratings).
#
# Usage: ./admin_launch.sh <users.json> <dataset participant list> [port] [report dir]
#
# Only emails in the users config's top-level "admins" list get in. In production, expose
# this port through its own Cloudflare Access application limited to the admins; Streamlit
# binds to 127.0.0.1 so the tunnel is the only way in.
set -euo pipefail

users_config="${1:?usage: $0 <users.json> <participant_list.tsv> [port] [report dir]}"
participant_list="${2:?usage: $0 <users.json> <participant_list.tsv> [port] [report dir]}"
port_number="${3:-${ADMIN_PORT:-8502}}"
report_dir="${4:-${ADMIN_REPORT_DIR:-}}"
session_list="${SESSION_LIST:-ses-BL}"  # the --session_list the rater app is launched with

cd "$(dirname "$0")"
extra=()
if [[ -n "$report_dir" ]]; then
  extra+=(--output_dir "$report_dir")
fi

streamlit run admin/admin_app.py --server.port="$port_number" --server.address=127.0.0.1 -- \
  --users_config "$users_config" \
  --participant_list "$participant_list" \
  --session_list "$session_list" \
  ${extra[@]+"${extra[@]}"}
