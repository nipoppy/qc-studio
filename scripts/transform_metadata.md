# transform_metadata.py

Remaps the values of the rater metadata columns in a `*_qc_status.tsv`:
- `rater_experience`,
- `rater_fatigue`,
- `rater_screen_size`.

Use it when the UI's options for these fields change (see `EXPERIENCE_LEVELS`, `FATIGUE_LEVELS` and `SCREEN_SIZES` in `ui/constants.py`), so that older files match the new options. All other columns are left as they are. Row order, row count and column order are kept.

The script is standalone: it needs only Python and pandas, and you can copy it out of the repo and run it on its own.

```bash
# Write to a new file
python scripts/transform_metadata.py \
  --input rater1_fmriprep_anat_wf_qc_qc_status.tsv \
  --mapping scripts/sample_metadata_transform.json \
  --output rater1_fmriprep_anat_wf_qc_qc_status_v2.tsv

# Rewrite the input file, keeping a copy of the original as <input>.bak
python scripts/transform_metadata.py \
  --input rater1_fmriprep_anat_wf_qc_qc_status.tsv \
  --mapping scripts/sample_metadata_transform.json \
  --in-place --backup
```

| Option | Effect |
|---|---|
| `--output PATH` | Writes the result to `PATH`. Give either this or `--in-place`. |
| `--in-place` | Rewrites `--input`. The script writes a temporary file first and then swaps it in, so a failed run never leaves a half-written file. |
| `--backup` | Only with `--in-place`. Copies the original to `<input>.bak` first. |
| `--skip-allowed-check` | Doesn't check mapped target values against the allowed lists. |
| `--passthrough-unmapped-values` | Keeps values that have no mapping entry. Without it, such values are an error. |
| `--strict` | Treats warnings as errors: values passed through unmapped, and output values not in the allowed lists. |
| `--overwrite` | Replaces an existing `--output` file or `.bak` file. |
| `--dry-run` | Prints the summary without writing anything, including with `--in-place`. |

## Mapping file

```json
{
  "filter": {"pipeline": "fmriprep", "qc_task": "anat_wf_qc", "rater_id": "rater1"},
  "columns": {
    "rater_experience":  {"Expert": "Expert (>5 years)"},
    "rater_fatigue":     {"Not tired": "Not at all", "": "Not at all"},
    "rater_screen_size": {"27": "26-30"}
  },
  "allowed": {"rater_screen_size": ["small", "medium", "large"]}
}
```

| Field | Meaning |
|---|---|
| `filter` | Optional. Only rows that match every key given (`pipeline`, `qc_task`, `rater_id`) are rewritten. Other rows are copied unchanged, so you can chain several mapping files. |
| `columns` | Required. For each metadata column, maps source values to target values. Columns you leave out are not changed. Each value maps to a single string; a list is rejected. |
| `columns.<col>[""]` | Optional. Fills blank cells (empty, `nan` or `none`). Without it, blank cells stay blank. |
| `allowed` | Optional. Replaces a column's list of allowed values. The defaults mirror `ui/constants.py`. |

## Checks

- **Mapped targets.** Every target value in `columns` must be in that column's allowed list, unless you pass `--skip-allowed-check`.
- **Re-runs.** A value that is already one of the column's target values is left as it is, so running the same mapping twice is safe.
- **Unmapped values.** Any other non-blank value with no entry in the map is an error. With `--passthrough-unmapped-values` it is kept as it is, and a warning is printed.
- **Leftover values.** If any matched row still has a non-blank value outside the allowed lists after the transform, a warning is printed. This includes columns you didn't map.
- **No matching rows.** If no rows match `filter`, the script fails.
