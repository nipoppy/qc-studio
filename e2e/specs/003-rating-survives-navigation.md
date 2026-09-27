# Spec: A recorded rating is still selected when the rater navigates back to it

---

**Screen:** viewer

**Category:** functional

**Priority:** high

**Why end-to-end:** This is the promise the whole app rests on -- that a
rating, once given, is not lost. It spans three pieces of wiring that only
meet in the browser: the radio's `on_change` writes the record, navigation
tears the page down and rebuilds it, and the rebuilt radio reads the stored
rating back through `index=`. A mocked test can check each in isolation and
still miss that the round trip is broken. If it were, a rater would rate a
subject, come back, find it blank, and have no way to know whether their
earlier rating was recorded or silently dropped.

---

### Given

A rater on the QC viewer with more than one subject in the cohort, who has
rated the first subject PASS.

### When

The rater moves to the next subject and then navigates back to the first one.

### Then

The PASS option is still selected for that subject.

### And (optional)

The rating for the *second* subject is still unset -- returning to a rated
subject does not carry its rating onto its neighbour.

---

### Copy used

MESSAGES["qc_rating_prompt"]     "Rate this qc-task:"
MESSAGES["next_button"]          "Next ▶️"
MESSAGES["previous_button"]      "◀️ Previous"
QC_RATINGS                       ["PASS", "FAIL", "UNCERTAIN"]

### Notes

- **This spec cannot run on the default test config.** `QCAppConfig` points at
  `sample_data/qc_participants_demo.tsv`, which lists exactly one subject
  (`sub-ED01`), and with one subject the viewer never renders a Next button at
  all (`next_page is None`). Use the existing fixture instead:

      from conftest import two_subject_qc_config as qc_config

  It writes a two-row participant list (`sub-CMH0001`, `sub-ED01`, both of
  which have fmriprep derivatives under `sample_data/`) to a temp path.
- The rating radio has an explicit key, `qc_rating_<task>_<rver>`, where
  `rver` is `SessionManager.get_rating_version()` and is not stable across a
  version bump. `get_radio_option` by its PASS/FAIL/UNCERTAIN label is the
  safer selector.
- The radio starts with **no option selected** (`index=None` when there is no
  stored rating), so "is PASS selected" is a real assertion, not a default.
  Check the input's checked state -- do not just assert the PASS text is
  visible, since all three labels are always on screen.
- Navigation is a rerun like any other; use the `click_button` helper so the
  wait is handled, and never assert straight after the click.
