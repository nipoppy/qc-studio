# Spec: A note typed against a subject is still there when the rater returns

---

**Screen:** viewer

**Category:** functional

**Priority:** high

**Why end-to-end:** The notes box is disabled until "Add notes" is clicked,
saves through `_on_notes_change`, and is read back on re-render from the
stored record via `value=initial_notes`. Three separate pieces of wiring, none
of which a mocked test exercises together. If any one of them broke, a rater
would type a note, see it on screen, and lose it the moment they moved on --
with nothing on screen to warn them.

---

### Given

A rater part-way through QC on the viewer, on a subject whose notes box they
have made editable by clicking "Add notes".

### When

The rater types a note for that task and commits it by moving focus out of
the box.

### Then

Navigating away to the next subject and back again, the note is still shown in
the notes box for that subject.

### And (optional)

The note also reaches disk: after clicking "💾 Save progress", the written
file contains the note text against that participant.

---

### Copy used

MESSAGES["add_notes_button"]        "Add notes"
MESSAGES["qc_notes_prompt"]         "Notes (optional):"
MESSAGES["next_button"]             "Next ▶️"
MESSAGES["previous_button"]         "◀️ Previous"

### Notes

- The notes box starts **disabled** (`disabled=not notes_editable`). Clicking
  "Add notes" is a required first step, not optional setup -- without it the
  box cannot be typed into at all.
- Streamlit's `st.text_area` fires `on_change` on **blur or Ctrl+Enter**, not
  on every keystroke. Playwright's `fill()` alone does not blur the field, so
  the note may never be committed. The test has to move focus away (click
  another element, or press Tab) and then `wait_for_app_run` -- this is the
  most likely reason a first attempt at this test fails while looking correct.
- The navigation in "Then" is the *observation mechanism*, not a second action
  under test: an in-memory save has no visible form until you leave and come
  back. Keep the round trip as short as possible (next, then previous).
- **The default config has a single subject**, so there is nowhere to navigate
  to and no Next button is rendered. Either rebind the shared two-subject
  fixture (`from conftest import two_subject_qc_config as qc_config`), or drop
  the navigation entirely and observe the note through the saved file instead
  (the "And" clause above) -- which keeps this spec runnable on the default
  config. Decide before writing, because it changes the Given.
- The notes widget key is `qc_notes_<task>_<nver>`, where `nver` comes from
  `SessionManager.get_notes_version()` and is not stable across a version
  bump. Prefer the label-based `get_text_area` over `get_by_key` here.
- `_notes_edit_mode_<task>` is keyed by **task, not by subject**, so edit mode
  carries over between subjects. The note text itself renders from the stored
  record either way, so this does not change the assertion -- but do not be
  surprised to find the box already editable after navigating.
- If the "And" clause is included, use the `output_files` fixture for the
  save-progress file rather than listing the output directory directly.
