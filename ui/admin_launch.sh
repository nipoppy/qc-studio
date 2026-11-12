#!/usr/bin/env bash
# Launch the QC-Studio admin dashboard (workloads + collated ratings).
#
# Usage: ./admin_launch.sh <users.json> <dataset participant list> <qc.json> [port] [report dir]
#   e.g. QC_PIPELINE=fsqc ./admin_launch.sh /data/qc-raters/users.json /data/qc_participants.tsv ../pipelines/fsqc/qc.json
#
# <qc.json> is the rater app's --qc_json: its tasks are the ones raters are expected to complete
# (set QC_TASK=a,b for a subset). The pipeline comes from its "__pipeline__" key; until qc.json
# has one, set QC_PIPELINE (the rater app's --qc_pipeline) here or in the repo's .env.
#
# Only emails in the users config's top-level "admins" list get in. In production, expose
# this port through its own Cloudflare Access application limited to the admins; Streamlit
# binds to 127.0.0.1 so the tunnel is the only way in.
set -euo pipefail

usage="usage: [QC_PIPELINE=<pipeline>] $0 <users.json> <participant_list.tsv> <qc.json> [port] [report dir]"
# Paths given relative to the caller's folder must survive the cd below.
abspath() { if [[ -e "$1" ]]; then realpath "$1"; else echo "$1"; fi; }

users_config="$(abspath "${1:?$usage}")"
participant_list="$(abspath "${2:?$usage}")"
qc_json="$(abspath "${3:?$usage}")"  # a path that doesn't exist here is tried relative to ui/
port_number="${4:-${ADMIN_PORT:-8502}}"
report_dir="${5:-${ADMIN_REPORT_DIR:-}}"
session_list="${SESSION_LIST:-ses-BL}"  # the --session_list the rater app is launched with
qc_task="${QC_TASK:-all}"

extra=()
if [[ -n "${QC_PIPELINE:-}" ]]; then
  extra+=(--qc_pipeline "$QC_PIPELINE")
fi
if [[ -n "$report_dir" ]]; then
  extra+=(--output_dir "$(abspath "$report_dir")")
fi

cd "$(dirname "$0")"
streamlit run admin/admin_app.py --server.port="$port_number" --server.address=127.0.0.1 -- \
  --users_config "$users_config" \
  --participant_list "$participant_list" \
  --qc_json "$qc_json" \
  --qc_task "$qc_task" \
  --session_list "$session_list" \
  ${extra[@]+"${extra[@]}"}
