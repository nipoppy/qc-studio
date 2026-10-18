# Spec: Next saves the current page's rating before advancing

---

**Screen:** viewer

**Category:** functional

**Priority:** medium

**Why end-to-end:** "Next" used to be a pure navigation button sitting beside
a separate "Confirm and Next"; those have since been collapsed into one
button that records the page and then advances. That makes saving a
*side-effect of navigating*, which is only observable in a browser: the click
has to reach `_record_all_qc_tasks` before the page is torn down. If that
ordering broke, a rater's last rating on each subject would vanish as they
moved on -- the most expensive possible failure, since it would hit every
subject but the last.

---

### Given

A rater on the QC viewer with more than one subject in the cohort, who has
rated the first subject PASS.

### When

The rater clicks "Next ▶️".

### Then

The app shows the next subject.

### And (optional)

Navigating back, the first subject is still rated PASS.

---

### Copy used

MESSAGES["next_button"]          "Next ▶️"
MESSAGES["previous_button"]      "◀️ Previous"
QC_RATINGS                       ["PASS", "FAIL", "UNCERTAIN"]

### Notes

- **This spec was rewritten.** It originally contrasted "Next" with "Confirm
  and Next", which no longer exists -- the buttons were merged into the single
  `pag_next`, which saves and then advances. Nothing in the suite covers the
  old two-button behaviour because that behaviour is gone.
- Needs the multi-subject config; the Next button is not rendered at all when
  there is no next page:

      from conftest import two_subject_qc_config as qc_config

- Overlaps spec 003 deliberately. 003 proves a rating survives a round trip at
  all; this one proves the *save-then-advance ordering* inside the Next
  handler specifically. Write 003 first -- if it fails, this one cannot be
  interpreted.
- Uncheck the Niivue panel in setup. It renders a real 3D volume client-side
  and keeps `wait_for_app_run`'s skeleton check blocked for tens of seconds
  per rerun, and this spec navigates twice. See
  `notes-autoplay-test-debugging.md`.
- Both nav buttons have explicit keys (`pag_next`, `pag_prev`), so `get_by_key`
  avoids any risk of a label-substring collision.
