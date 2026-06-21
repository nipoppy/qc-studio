# NODDIreg QC configuration

QC-Studio loads **only** `qc.json` from this folder. Run `streamlit run ui/main.py …` from the repository root, or use **`ui/noddireg_test.sh`** (from `ui/`) for the same defaults.

Example (after `cd` to the qc-studio root):

```bash
streamlit run ui/main.py --server.port=8501 -- \
  --qc_json ../pipelines/noddireg/qc.json \
  --qc_task noddireg_density \
  --qc_pipeline noddireg \
  --dataset_dir sample_data \
  --participant_list sample_data/qc_participants.tsv \
  --session_list ses-01,ses-02 \
  --output_dir ./output
```

Use **`--session_list`** with comma-separated BIDS session labels (e.g. `ses-01,ses-02`). The app builds one review **page** per **(participant × session)** from your participant list. If `qc_participants.tsv` includes a **`session_id`** column, that file defines the exact rows instead (one row per participant–session pair).

### Multiple tasks in `qc.json` (`noddireg_density`, `noddireg_od_icvf_isovf`)

`qc.json` can define **several** tasks. You choose how to run QC-Studio:

- **One task per run** (default): pass the task key with **`--qc_task`** (e.g. `noddireg_density`). The UI does not switch tasks mid-session.
- **All tasks on one scrollable page**: use **`--qc_task all`**. Each cohort page gets a PASS / FAIL / UNCERTAIN (and notes) **per task**, and the sidebar marks a page complete only when **every** task in `qc.json` has a decided rating.

Examples:

- From `ui/` with **`noddireg_test.sh`**: `./noddireg_test.sh ../pipelines/noddireg/qc.json noddireg_od_icvf_isovf`, or `./noddireg_test.sh ../pipelines/noddireg/qc.json all`, or set **`QC_TASK=all ./noddireg_test.sh`**.

Paths inside `qc.json` are relative to **`--dataset_dir`**. Use **`[[NIPOPPY_BIDS_PARTICIPANT_ID]]`** and **`[[NIPOPPY_BIDS_SESSION_ID]]`** where filenames include those entities.

Expected layout: **`sample_data/derivatives/noddireg/<subject>/`** with PNGs named like `<subject>_<session>_desc-dsegtissue_model-noddi_density.png` and the OD / ICVF / ISOVF QC images referenced in `noddireg_od_icvf_isovf`. There are no NIfTI panels in the shipped `qc.json`; QC is figure-based only.
