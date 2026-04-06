pipeline_script="ui.py"
qc_pipeline="fmriprep"
qc_task="anat_wf_qc func_wf_qc"
qc_json="sample_qc_multi.json"
participant_list="qc_participants.tsv"
output_dir="../output"
port_number="8503"

streamlit run $pipeline_script --server.port=$port_number -- \
  --qc_json $qc_json \
  --qc_task $qc_task \
  --qc_pipeline $qc_pipeline \
  --participant_list $participant_list \
  --output_dir $output_dir
