# Spec: An empty Rater ID blocks entry to QC

**Screen:** landing

**Category:** edge

**Priority:** high

**Why end-to-end:** The rule itself lives in `views/landing_page.py`, but what
this test protects is the *wiring* -- that the real submit button runs the
validation at all, and that a failed validation leaves the rater on the landing
page instead of letting them through. `ui/tests/` mocks Streamlit entirely, so
nothing there proves the button is connected to the check.

---

### Given

A rater on a freshly loaded landing page, with at least one display panel
selected (so that panel validation is not what blocks them).

### When

They submit the rater form with the Rater Name / ID field left empty.

### Then

`ERROR_MESSAGES["invalid_rater_id"]` is visible on the page.

### And

The rater form is still on screen -- the app did not advance to the QC viewer.

---

### Copy used

    MESSAGES["rater_id_prompt"]       "Enter your Rater Name or ID:"
    MESSAGES["rater_form_button"]     "✅ Continue to QC"
    ERROR_MESSAGES["invalid_rater_id"]

### Notes

- The form is an `st.form`, so filling the text input triggers no rerun; only
  pressing the submit button does. Use `click_form_submit`, not `click_button`
  -- `st.form_submit_button` renders with a different test id.
- Panel selection lives in the middle column and is validated separately
  (`ERROR_MESSAGES["no_panel_selected"]`); that is spec 002, not this one.
