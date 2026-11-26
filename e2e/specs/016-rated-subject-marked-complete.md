# Spec: A rated subject is marked complete in the subject list

---

**Screen:** viewer

**Category:** functional

**Priority:** medium

**Why end-to-end:** The ✅/⬜ mark beside each subject is the rater's only
answer to "where am I up to", and for a long session it is the thing they
steer by. It is computed per row from
`SessionManager.participant_has_decided_qc` at render time, so it spans the
rating widget, the stored record and a completely different part of the UI --
a seam no unit test crosses. A stuck ⬜ would send a rater back over work they
had already finished; a premature ✅ would let them skip a subject entirely.

---

### Given

A rater on the QC viewer with more than one subject in the cohort, where no
subject has been rated yet, so every row in the subject list shows ⬜.

### When

The rater rates the subject currently on screen.

### Then

That subject's row in the list changes to ✅.

### And (optional)

The other subject's row still shows ⬜ -- rating one subject does not mark the
cohort done.

---

### Copy used

QC_RATINGS      ["PASS", "FAIL", "UNCERTAIN"]

The ✅ and ⬜ marks are **hardcoded** in `views/sidebar_cohort_nav.py` with no
`constants.py` keys. Extract them before writing this test rather than typing
the emoji into it -- the same fix "Add notes" needed before spec 011.

### Notes

- Needs the multi-subject config, or the "And" clause has nothing to compare
  against:

      from conftest import two_subject_qc_config as qc_config

- Row labels are `"<mark> <pid> · <sid>"`, plus `" — current"` on the row the
  rater is on, so the row under test carries that suffix too. Match on the
  participant ID and the mark rather than on an exact full label.
- Rows have keys `sidebar_cohort_nav_<i>`, which is the stable way to find a
  specific row; the index is the subject's position in the cohort, not its ID.
- The mark flips on `participant_has_decided_qc`, which asks whether the
  record's rating is one of QC_RATINGS -- so it should flip on the rating
  click alone, with no save or navigation needed. If it does not, check
  whether the sidebar re-rendered before asserting rather than assuming the
  feature is broken.
- With several tasks configured the row only turns ✅ once **every** task is
  decided (`all(... for t in tasks_eff)`). Keep this spec on the default
  single-task config; multi-task completion belongs with spec 013.
