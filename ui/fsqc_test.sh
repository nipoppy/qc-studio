dataset_dir="/data/qc-datasets/ppmi-sandbox/"
participant_list="/data/qc-datasets/ppmi-sandbox/qc_participant_test.tsv"
qc_pipeline="fsqc"
qc_json="../pipelines/fsqc/qc.json"
qc_task="FS_preproc_workflow"
output_dir="/data/qc-datasets/ppmi-sandbox/qc-output/test-user-0"
pipeline_script="main.py"
port_number="8501"
session_list="ses-BL"
rater_id="odysseus"

streamlit run $pipeline_script --server.port=$port_number -- \
  --qc_json $qc_json \
  --qc_task $qc_task \
  --qc_pipeline $qc_pipeline \
  --dataset_dir $dataset_dir \
  --participant_list $participant_list \
  --session_list $session_list \
  --output_dir $output_dir \
  --rater_id $rater_id 