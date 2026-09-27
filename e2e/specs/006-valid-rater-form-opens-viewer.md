# Spec: A valid rater form advances the rater to the QC viewer

---

**Screen:** landing

**Category:** functional

**Priority:** high

**Why end-to-end:** Specs 001 and 002 prove the gate *blocks*; nothing proves
it ever *opens*. That asymmetry is dangerous -- if the success branch broke
(`set_landing_page_complete`, the `st.switch_page` that follows), both existing
specs would still pass happily while no rater could get into the app at all.
This is also the path every viewer test depends on, so when it fails, it
should fail here with a clear cause rather than as a confusing timeout
somewhere in spec 003.

---

### Given

A rater on a freshly loaded landing page, with the default panels still
selected.

### When

The rater enters a valid Rater ID and submits the rater form.

### Then

The QC viewer is on screen: the rating prompt for the subject is visible.

### And (optional)

The rater form is gone -- the app moved on rather than re-rendering the
landing page underneath.

---

### Copy used

MESSAGES["rater_id_prompt"]      "Enter your Rater Name or ID:"
MESSAGES["rater_form_button"]    "✅ Continue to QC"
MESSAGES["qc_rating_prompt"]     "Rate this qc-task:"

### Notes

- The Rater ID is stripped of all whitespace before validation
  (`"".join(rater_id.split())`), so any ID without spaces is valid. A plain
  string is enough; nothing here needs to be realistic.
- Leave the panel checkboxes alone. They default to niivue and montage
  selected, which is what makes the panel check pass -- spec 002 is the one
  that touches them.
- `get_current_subject_label` in `app_utils.py` finds the participant/session
  heading and is an alternative assertion to the rating prompt. Prefer
  whichever is genuinely specific to the viewer: the point is to prove the
  app *moved*, so pick something that cannot appear on the landing page.
- Asserting the form is gone is a negative assertion, so it must come after
  the interaction helper's `wait_for_app_run` -- `not_to_be_visible()` passes
  instantly against a stale page and would give a green test over a real bug.
- The viewer loads real imaging panels (niivue, montage) for `sub-ED01`, so
  this test is slower than the landing-page specs. Assert on the rating
  controls rather than on an image, which would make the test hostage to how
  fast a NIfTI renders.
