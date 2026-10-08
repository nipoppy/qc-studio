# Configuration

QC-Studio is configured at four levels, from least to most specific:

1. Command-line flags
2. `qc.json`
3. Environment variables
4. In-app settings on the landing page

## Command-line reference

QC-Studio is launched by running the script under `streamlit run`

```bash
streamlit run ui/main.py --server.port=8501 -- [flags]
```

You can also read the built-in help with `python ui/main.py --help`.

### Flags

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--dataset_dir` | yes | — | Path to the dataset root. **Every relative path inside `qc.json` resolves against this directory.** |
| `--participant_list` | yes | — | Path to a TSV listing the participants to QC. See [Participant list](#participant-list-tsv). |
| `--qc_pipeline` | yes | — | Pipeline name being reviewed. Recorded in the exported `pipeline` column; also used in checkpoint/session file names. |
| `--qc_task` | yes | — | One QC task key from `qc.json`, **or the literal value `all`** to show every task on one scrollable page. See [One task or all of them](#one-task-or-all-of-them). |
| `--output_dir` | yes | — | Directory for session state, results, and checkpoints. Created on demand. |
| `--qc_json` | yes | — | Path to the QC configuration JSON describing what to display. |
| `--session_list` | no | `null` | Comma-separated BIDS session labels, for example `ses-01,ses-02`. |
| `--rater_id` | no | `null` | Rater name or ID used to pre-fill the landing page. |
| `--default_qc_rating` | no | `PASS` | Rating preselected on unrated pages: `PASS`, `FAIL`, `UNCERTAIN` or `None`. See [Default rating](ratings.md#default-rating). |

Everything else is configured through `qc.json`, the environment, or the landing page.

## Participant list (TSV)

A tab-separated file whose first column is `participant_id`.

```text
participant_id
sub-CMH0001
sub-CMH0002
sub-CMH0003
```

Notes:

- The `participant_id` column is **required**.
- IDs may be written with or without the `sub-` prefix; QC-Studio normalizes them to include it.

### Session labels

The participant list file can include a `session_id` column:

```text
participant_id	session_id
sub-CMH0001	ses-01
sub-CMH0001	ses-02
```

Alternatively, session labels can be specified via the `--session_list` flag.

If session labels are not specified in either of these ways,
QC-Studio discovers sessions by asking PyBIDS for every session under `--dataset_dir`.

- If sessions are found, it uses them and prints the list to stderr.
- If the dataset has no session level, the cohort is one page per participant with no session.

## `qc.json`

### Structure

`qc.json` is a JSON **object** with QC tasks as top-level keys and task display configuration as values.

```json
{
  "sdc_wf_qc": {
    "display_name": "Susceptibility distortion correction (SDC)",
    "base_mri_image_path": "bids/[[NIPOPPY_BIDS_PARTICIPANT_ID]]/[[NIPOPPY_BIDS_SESSION_ID]]/func/[[NIPOPPY_BIDS_PARTICIPANT_ID]]_[[NIPOPPY_BIDS_SESSION_ID]]_task-*_run-*_bold.nii.gz",
    "montage_path": "derivatives/fmriprep/[[NIPOPPY_BIDS_PARTICIPANT_ID]]/figures/[[NIPOPPY_BIDS_PARTICIPANT_ID]]_[[NIPOPPY_BIDS_SESSION_ID]]_task-*_run-*_desc-sdc_bold.svg",
    "iqm_path": [
      "derivatives/mriqc/group_T1w.tsv",
      "derivatives/mriqc/group_bold.tsv"
    ]
  }
}
```

The schema is defined by the `QCTask` model in [`ui/models/qc_models.py`](https://github.com/nipoppy/qc-studio/blob/main/ui/models/qc_models.py).

### Task fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `display_name` | string | no | Human-readable label shown in the UI. Falls back to the key when absent. |
| `base_mri_image_path` | path | no | Base MRI for the Niivue 3D viewer. Glob patterns allowed. |
| `overlay_mri_image_path` | path | no | Overlay drawn on top of the base MRI. One overlay maximum. |
| `montage_path` | path or list of paths | no | 2D montage images for the Montage panel: **SVG, PNG, JPG/JPEG only**. |
| `iqm_path` | path or list of paths | no | IQM sources: TSV/CSV distribution tables or JSON metric files, one entry per pipeline source. |
| `montage_max_rows` | integer, 1–10 | no | Default maximum grid rows. Omit for automatic layout. |
| `montage_max_cols` | integer, 1–10 | no | Default maximum grid columns. Omit for automatic layout. |
| `rating` | object | no | Rating scheme for the task. See [Rating fields](#rating-fields). |

### Rating fields

The optional `rating` object sets how a task is rated (see [Rating schemes](ratings.md)).

| Field | Description | Default |
|-------|-------------|---------|
| `type` | `"single"` or `"multi"` | `"single"` |
| `scale` | The rating options offered (shared by all facets) | `["PASS", "FAIL", "UNCERTAIN"]` |
| `facets` | The facet names to rate (used when `type` is `"multi"`) | none |

If `type` is `"multi"` but no facets are listed, the task falls back to a single rating.

Example of a multi-facet task:

```json
"FS_preproc_workflow": {
    "base_mri_image_path": "derivatives/fmriprep/[[NIPOPPY_BIDS_PARTICIPANT_ID]]/...",
    "montage_path": ["derivatives/fmriprep/[[NIPOPPY_BIDS_PARTICIPANT_ID]]/figures/..."],
    "rating": {
        "type": "multi",
        "scale": ["PASS", "FAIL", "UNCERTAIN"],
        "facets": ["Cropped", "Aliasing", "Motion", "Susceptibility", "Ringing", "Inhomogeneity"]
    }
}
```

### Path substitutions

Placeholders in `qc.json` are textually replaced with values known for the current cohort page
**before** Pydantic validation runs.

| Placeholder | Replaced with | Example |
|-------------|---------------|---------|
| `[[NIPOPPY_BIDS_PARTICIPANT_ID]]` | The normalized participant ID, including `sub-` | `sub-CMH0001` |
| `[[NIPOPPY_BIDS_SESSION_ID]]` | The BIDS session label | `ses-02` |

### One task or all of them

`qc.json` can define several tasks. Use `--qc_task` to select the one to start with;
you can switch to another task from the landing page sidebar.

Setting `--qc_task all` puts every task on one page.

## Environment variables

| Variable | Read from | Required when | Effect |
|----------|-----------|---------------|--------|
| `REFERENCE_DATA_URL` | Process environment or a `.env` file in the working directory | Only the **Dataset + Reference** IQM mode needs to download data | Base URL of the host serving reference IQM Parquet files |

Cached downloads are written to `.streamlit/reference_cache/` and reused for **seven days**.
Once a modality is cached, the app runs without `REFERENCE_DATA_URL`.

## In-app settings

These are set on the landing page and stored in the Streamlit session, not on disk. They do not
persist across browser sessions.

### Rater information

| Field | Values | Written to |
|-------|--------|------------|
| Rater name or ID | Free text | `rater_id` |
| QC experience level | `Beginner (< 1 year)`, `Intermediate (1-5 years)`, `Expert (>5 years)` | `rater_experience` |
| Fatigue level | `Not at all`, `A bit tired`, `Very tired` | `rater_fatigue` |
| Screen size (diagonal, inches) | `14 or less`, `15-20`, `21-25`, `26-30`, `31 or above`, `Unknown` | `rater_screen_size` |
| [Autoplay](autoplay.md) duration | 5–15 seconds, default 10 | Nowhere |

### QC task and default rating

The landing page sidebar also lets you:

- choose which QC task to rate
- choose the [default rating](ratings.md#default-rating) preselected on unrated pages

### Display panels

Select which panel(s) are active.

| Panel | Default |
|-------|---------|
| 3D MRI (Niivue) | on |
| Montage | on |
| QC Metrics | off |

### Montage grid

**Montage Grid Settings** lets you set maximum rows and columns (1–10).
Choosing **Auto-calculate** will derive a near-square layout from the number of images.

### Saving your work

| Action | Where it lands |
|--------|----------------|
| **🏁 Create checkpoint** | `<output_dir>/checkpoints/<rater>_<pipeline>_<task>_checkpoint_<timestamp>.tsv` |
| **💾 Export Final Results** | Anywhere you choose; defaults to `<output_dir>/<rater>_<pipeline>_<task>_qc_status.tsv` |

## Exported results (TSV)

Results are tab-separated with a header row. Columns always appear in this order:

| # | Column | Meaning |
|---|--------|---------|
| 1 | `pipeline` | Value of `--qc_pipeline` |
| 2 | `qc_task` | QC task key |
| 3 | `participant_id` | BIDS subject ID, with `sub-` prefix |
| 4 | `session_id` | Session label, or empty for session-less cohorts |
| 5 | `task_id` | Reserved; usually empty |
| 6 | `run_id` | Reserved; usually empty |
| 7 | `timestamp` | `YYYY-MM-DD HH:MM:SS` when the rating was recorded |
| 8 | `rater_id` | Normalized rater ID |
| 9 | `rater_experience` | Rater experience level |
| 10 | `rater_fatigue` | Rater fatigue level |
| 11 | `rater_screen_size` | Rater monitor size band |
| 12 | `final_qc` | QC rating (for multi-facet tasks, the [overall rating](ratings.md#multi-facet-rating-interface)) |
| 13 | `facet` | Facet name; empty for single-rating tasks |
| 14 | `rating_value` | Rating for that facet; empty for single-rating tasks |
| 15 | `notes` | Free text |

For [multi-facet tasks](ratings.md), each facet is written as its own row.

### Resuming a session

Upload a previous `<rater>_status.tsv` (CSV and TSV are both accepted) from the landing page.

## Bundled pipeline configurations

Example configuration files are available in the [`pipelines/` directory](https://github.com/nipoppy/qc-studio/blob/main/pipelines).

## See also

- [Quickstart](../overview/quickstart.md) — the flags in context, running a demo.
- [Rating schemes](ratings.md) — single and multi-facet ratings.
- [Autoplay](autoplay.md) — the timed auto-advance settings.
- [Architecture](../development/architecture.md) — where each configuration value is read in the code.
