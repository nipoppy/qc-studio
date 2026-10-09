# transform_ratings.py

Rewrites **one qc_task** in a `*_qc_status.tsv` so it matches a new QC protocol. It can change:
- the task name (and optionally the pipeline name),
- facet names, through explicit 1-1, 1-many and many-1 blocks,
- the rating scale.

Rows from all other tasks are copied through unchanged. To transform several tasks, chain mapping files: feed the output of one run into the next.

```bash
python scripts/transform_ratings.py \
  --input rater1_fmriprep_anat_wf_qc_qc_status.tsv \
  --mapping map.json \
  --output rater1_fsqc_qc_status.tsv \
  --target-qc-json pipelines/fsqc_enigma/qc.json
```

| Option | Effect |
|---|---|
| `--target-qc-json` | Checks the mapping against the target `qc.json`. The target task must exist, `rating.type` must match, target facets must be listed in `rating.facets`, and mapped scale values must be in `rating.scale`. Warns about facets the mapping never produces. |
| `--passthrough-unmapped-values` | Keeps rating values that have no `scale` entry. Without it, such values are an error. |
| `--strict` | Treats warnings as errors: dropped facets, missing source facets, majority ties. |
| `--overwrite` | Replaces an existing output file. |
| `--dry-run` | Prints the summary without writing anything. |

## Mapping file

```json
{
  "source": {"pipeline": "fsqc", "qc_task": "FS_volume_workflow_v1"},
  "target": {"pipeline": "fsqc_enigma", "qc_task": "FS_volume_workflow", "type": "multi"},

  "scale": {"PASS": "PASS", "FAIL": "FAIL", "UNCERTAIN": "UNCERTAIN", "QUESTIONABLE": "UNCERTAIN"},

  "facets": {
    "one_to_one":  {"L thalamus": "L whol thal"},
    "one_to_many": {"Brainstem": ["M brainstem", "L ventrl DC", "R ventrl DC"]},
    "many_to_one": {
      "L hippocamp": {"from": ["L hippo head", "L hippo tail"], "aggregate": "any:FAIL"}
    }
  },
  "unmapped_facets": "drop"
}
```

| Field | Meaning |
|---|---|
| `source.qc_task` | Required. The task to transform. |
| `source.pipeline` | Optional. Only rows with this pipeline are transformed. |
| `target.qc_task` | Required. The new task name. |
| `target.pipeline` | Optional. The new pipeline name. If omitted, the pipeline stays the same. |
| `target.type` | `multi` (default; one row per facet) or `single` (one row, `final_qc` only). |
| `scale` | Optional. Maps each source value to a target value. Many-to-one is allowed. One-to-many (a list as the value) is rejected. It is applied before facets are aggregated. |
| `facets` | Optional. If omitted, facet names are kept as they are, which is useful for renaming a task or changing only the scale. |
| `unmapped_facets` | `drop` (default) or `keep`: what happens to source facets that no block references. |

### Facet blocks

| Block | Shape | Notes |
|---|---|---|
| `one_to_one` | `{source: target}` | Renames a facet. |
| `one_to_many` | `{source: [target, ...]}` | Copies the rating to each target. |
| `many_to_one` | `{target: {"from": [source, ...], "aggregate": rule}}` | Combines several ratings into one. |

Each target facet may appear only once across the three blocks. Special tokens:
- **`final_qc` as a source** reads the `final_qc` of a single-scale task. This converts single to multi, e.g. `"one_to_many": {"final_qc": ["Motion", "Cropped"]}`.
- **`final_qc` as a target**, used with `"target": {..., "type": "single"}`, converts multi to single, e.g. `"many_to_one": {"final_qc": {"from": ["*"], "aggregate": "any:FAIL"}}`.
- **`*`** means all source facets. It is only allowed alone, in a `many_to_one` `from` list.

### Aggregation rules (`many_to_one`)

| Rule | Result |
|---|---|
| `majority` (default) | The most common value. A tie gives a blank, and a warning is printed. |
| `any:<VALUE>` | `<VALUE>` if any source has it; otherwise the majority value. |
| `first` | The first non-blank value, in `from` order. |

Under `majority` and `any:`, if any source rating is blank, the result is blank. The record therefore stays "undecided" in the UI.

### Output

The output has the same 15 columns as the UI export. For `multi` targets, `final_qc` is recomputed from the new facet ratings, using the same logic as the UI:
- `All-Pass`, `All-Fail` or `All-Uncertain` (generally `All-<Value>`) when every facet has the same rating,
- `Mixed` otherwise,
- blank if any facet is blank.

### Timestamps, notes and rater metadata

`timestamp`, `notes`, `rater_experience`, `rater_fatigue` and `rater_screen_size` are copied as they are. They are never rewritten, merged or set to the time of the transform.

- **One value per record.** Rows are grouped into records by `pipeline`, `participant_id`, `session_id`, `task_id`, `run_id` and `rater_id`. The metadata comes from the record's first row, in file order. Every output row for that record gets this value, whatever the facet mapping does.
- **Per-facet differences are lost.** If rows within one record have different notes or timestamps, only the first row's value survives. Notes are not concatenated, even when facets are combined with `many_to_one`.
- **The timestamp records when the rating was made.** The output keeps the original rating time, so it doesn't show that the data was transformed. Keep the input file and mapping if you need that history.
- **Duplicates are removed first.** Before grouping, rows with the same `participant_id`, `session_id`, `pipeline`, `qc_task` and `facet` are deduplicated, keeping the last one, as the UI does when saving. So the record's metadata comes from the most recent save of its first facet.
- **Passthrough rows are untouched.** Rows from other tasks keep all their columns, including timestamps and notes.
