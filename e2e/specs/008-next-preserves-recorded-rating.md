# Spec: Next navigates on without discarding an already-recorded rating

---

**Screen:** viewer

**Category:** functional

**Priority:** medium

**Why end-to-end:** "Next" and "Confirm and Next" both advance, and their
tooltips say the difference is saving -- but the rating radio already saves on
change, so what Next actually does to a rating is unclear from reading the
code. This spec pins down the current behaviour in the browser, where the two
buttons genuinely differ. Its real value is as the safety net for a decision
that has not been made yet: if the two buttons are later collapsed into one,
this test is what says whether the collapse changed anything a rater would
notice.

---

### Given

A rater on the QC viewer with more than one subject in the cohort, who has
rated the first subject PASS.

### When

The rater clicks "Next ▶️" -- the plain navigation button, not "Confirm and
Next".

### Then

The app shows the next subject.

### And (optional)

Navigating back, the first subject is still rated PASS -- moving on with the
plain Next did not discard it.

---

### Copy used

MESSAGES["next_button"]              "Next ▶️"
MESSAGES["previous_button"]          "◀️ Previous"
MESSAGES["confirm_next_button"]      named only to say which button is *not* used
QC_RATINGS                           ["PASS", "FAIL", "UNCERTAIN"]

### Notes

- **Needs the same multi-subject config as spec 003** -- the default
  participant list has a single subject and the Next button is not rendered at
  all when there is no next page. Rebind the shared fixture:

      from conftest import two_subject_qc_config as qc_config
- Next and Confirm-and-Next are separate buttons rendered near each other in
  the sidebar. `get_button` filters by label text, and "Next ▶️" is a
  substring concern -- check the helper does not also match the confirm
  button before trusting the click landed on the right one. If it does, that
  is an `app_utils.py` fix, not a test workaround.
- This spec deliberately overlaps spec 003: 003 proves a rating survives a
  round trip at all, this one proves the *plain* Next specifically does not
  drop it. Write 003 first -- if it fails, this one cannot be interpreted.
- If this test ever disagrees with its "And" clause -- that is, if Next really
  does lose a rating -- that is a product finding, not a test bug. Say so
  rather than adjusting the spec to match the behaviour.
