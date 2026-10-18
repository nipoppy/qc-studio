# Spec: With several QC tasks on a page, every task must be rated before moving on

---

**Screen:** viewer

**Category:** edge

**Priority:** high

**Why end-to-end:** The Next button's tooltip makes this promise in writing:
*"When more than one QC task is shown, set PASS, FAIL, or UNCERTAIN for every
task before continuing."* Multi-task mode (`--qc_task all`) is the only
configuration where that sentence means anything, and no test covers it. The
failure it guards against is quiet and permanent: a rater advances believing
all three tasks were recorded, and the two they skipped are simply absent from
the export -- indistinguishable later from tasks nobody looked at.

---

### Given

A rater on the QC viewer running with `qc_task="all"`, so the page shows more
than one QC task, with only the first task rated.

### When

The rater clicks "Next ▶️".

### Then

<Decide after checking the behaviour by hand: either the app refuses to
advance and says which tasks still need a rating, or it advances. Write down
what actually happens, then see the warning in Notes before treating it as
correct.>

### And (optional)

<>

---

### Copy used

MESSAGES["next_button"]          "Next ▶️"
MESSAGES["nav_tooltip_next"]     the sentence this spec is testing
QC_RATINGS                       ["PASS", "FAIL", "UNCERTAIN"]

### Notes

- **The promised gate may not exist.** Reading `_render_next_page_button`,
  the handler calls `_record_all_qc_tasks` and then advances; no branch was
  found that blocks navigation on unrated tasks, and
  `_record_qc_for_current_participant` silently returns early when a rating is
  `None`. So the likely current behaviour is: the page advances and the
  unrated tasks are never written. **Check this by hand before writing the
  test.** If it is confirmed, this is a product bug -- the tooltip promises
  something the app does not do -- and the right move is to raise it, not to
  write a test that enshrines the current behaviour as correct.
- Multi-task needs its own config. `pipelines/fmriprep/qc_demo.json` defines
  `anat_wf_qc`, `sdc_wf_qc` and `coreg_wf_qc`, so:

      QCAppConfig(qc_task="all")

  Add it to `conftest.py` beside `two_subject_qc_config` rather than inline.
- With three tasks, every per-task widget key (`qc_rating_<task>_<rver>`,
  `qc_notes_<task>_<nver>`) is distinct, but the **labels repeat** -- each task
  renders its own PASS/FAIL/UNCERTAIN group. `get_radio_option` by label alone
  will match three elements. Select within the task's section, or use the key;
  this is the main selector problem in this spec and may need an
  `app_utils.py` helper.
- One subject is enough here, so the default `qc_config` participant list is
  fine -- but with one subject there is no next page, and the Next handler
  takes a different branch. Use the two-subject fixture so "did it advance"
  is a real question.
