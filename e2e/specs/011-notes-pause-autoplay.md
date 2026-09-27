# Spec: Starting to add notes pauses autoplay

---

**Screen:** viewer

**Category:** interaction

**Priority:** high

**Why end-to-end:** The pause lives in `_toggle_notes_editing_for_task`, but a
mocked unit test can only prove that function clears the autoplay flags. It
cannot prove the real "Add notes" button is wired to it. If that wiring broke,
a rater who stopped to write a note would be carried on to the next subject
mid-sentence, and their half-typed note would go with the page -- a failure no
unit test can reproduce, because it only exists in real elapsed time.

---

### Given

A rater part-way through QC on the viewer, with autoplay running: they have
pressed "▶️ Play" and the countdown is ticking toward the next subject.

### When

The rater clicks "Add notes" on the task they are rating, so they can write
something before moving on.

### Then

Autoplay stops: the countdown banner above the viewer is gone.

### And (optional)

The notes box for that task is no longer disabled -- the rater can type in it
-- and after the full autoplay duration has elapsed, the app is still showing
the same subject.

---

### Copy used

MESSAGES["play_button"]           "▶️ Play"
MESSAGES["qc_notes_prompt"]       "Notes (optional):"

The "Add notes" button label is hardcoded in `qc_viewer.py` -- there is no
`constants.py` key for it yet. Add one before writing this test rather than
hardcoding the string in the test.

### Notes

- The countdown is drawn with `st.components.v1.html`, which Streamlit renders
  **inside an iframe** -- ordinary page locators cannot see its text. Do not
  try to assert on the words in the countdown. Assert that the banner element
  is absent instead: it is only rendered while `is_autoplay_enabled()` and
  `autoplay_start_time > 0`, so its absence *is* the paused state.
- Set a short autoplay duration in the landing form (the slider allows 2-10s)
  so the "still on the same subject" assertion does not make the test crawl.
- `wait_for_app_run` waits for a rerun to finish, not for a countdown. The
  final assertion has to wait out the duration deliberately and then check the
  page did not move -- it is the only test in the suite that depends on real
  elapsed time, so expect it to be the slowest and the most fragile.
- Autoplay can also be paused by *typing* in the notes box (`_on_notes_change`).
  That is a second route to the same state; this spec covers the button only.
- Getting to the viewer at all (submit the rater form, land on a subject,
  press Play) is several steps that every viewer spec will repeat. Consider a
  fixture for it before writing the second viewer test.
