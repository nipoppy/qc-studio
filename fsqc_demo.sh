qc_launch_script="ui/main.py"
qc_pipeline="fsqc"
qc_task="FS_left_hippocampus_wf_qc"
qc_json="../pipelines/fsqc/qc.json"
dataset_dir="sample_data"
participant_list="sample_data/qc_participants.tsv"
output_dir="./output"
port_number="8501"

streamlit run $qc_launch_script --server.port=$port_number -- \
  --qc_json $qc_json \
  --qc_task $qc_task \
  --qc_pipeline $qc_pipeline \
  --dataset_dir $dataset_dir \
  --participant_list $participant_list \
  --output_dir $output_dir
