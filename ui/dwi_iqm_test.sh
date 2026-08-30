#!/usr/bin/env bash
# Run QC-Studio against bundled MRIQC DWI sample data (invoke from anywhere, e.g. ./ui/dwi_iqm_test.sh)
#
# Exercises the DWI IQM distribution viewer end to end: group_dwi.tsv
# (shell-dependent groups) plus a per-subject dwi.json (metrics-table path)
# for sub-CMH0001/2/3, using ../pipelines/mriqc/dwi_iqm_test_qc.json
# (uncommitted, not a real pipeline config - group_dwi.tsv/dwi.json aren't
# wired into pipelines/qsiprep/qc.json yet).
#
# Optional arguments:
#   $1 — path to qc.json (default: ../pipelines/mriqc/dwi_iqm_test_qc.json)
#   $2 — qc_task name (default: dwi_iqm_qc). Same as env QC_TASK.
# Examples:
#   ./dwi_iqm_test.sh
#   PORT=8502 ./dwi_iqm_test.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

qc_launch_script="main.py"
qc_pipeline="mriqc"
qc_json="${1:-${QC_JSON:-${SCRIPT_DIR}/../pipelines/mriqc/dwi_iqm_test_qc.json}}"
qc_task="${2:-${QC_TASK:-dwi_iqm_qc}}"
dataset_dir="${SCRIPT_DIR}/../sample_data"
participant_list="${SCRIPT_DIR}/../sandbox/dwi_iqm_test_participants.tsv"
output_dir="${SCRIPT_DIR}/output"
port_number="${PORT:-8501}"
# sub-CMH0003 only has ses-02 DWI data - both sessions requested on purpose
# to exercise that missing-session case.
session_list="${SESSION_LIST:-ses-01,ses-02}"

echo "Using qc_json=${qc_json}  qc_task=${qc_task}  port=${port_number}  session_list=${session_list}"

VENV_STREAMLIT="${SCRIPT_DIR}/../.venv/bin/streamlit"
if [[ -x "${VENV_STREAMLIT}" ]]; then
	STREAMLIT_CMD="${VENV_STREAMLIT}"
elif command -v streamlit >/dev/null 2>&1; then
	STREAMLIT_CMD="streamlit"
else
	echo "❌ streamlit not found. Activate the project venv first:"
	echo "   cd ${SCRIPT_DIR}/.. && source .venv/bin/activate && pip install -r requirements.txt"
	exit 1
fi

cd "${SCRIPT_DIR}"
"${STREAMLIT_CMD}" run "$qc_launch_script" --server.port="$port_number" -- \
  --qc_json "$qc_json" \
  --qc_task "$qc_task" \
  --qc_pipeline "$qc_pipeline" \
  --dataset_dir "$dataset_dir" \
  --participant_list "$participant_list" \
  --session_list "$session_list" \
  --output_dir "$output_dir"
