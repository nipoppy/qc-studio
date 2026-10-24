# Spec: An empty QC panel blocks entry to QC
---

**Screen:** landing

**Category:** functional

**Priority:** medium

**Why end-to-end:** The rule lives in `landing_page.py`'s validation branch, but a mocked unit test can't prove the real checkbox widgets and the real submit button are wired to `SessionManager.get_panel_count()`. If someone breaks that wiring, the app would let a rater through with zero panels displayed and nobody would notice until a real click failed.
---

### Given

A rater on a freshly loaded landing page (where the niivue and montage panels are checked by default) who has entered a valid Rater ID and unchecked both default panels.

### When

The rater submits the rater form with no selected display panel.

### Then

`ERROR_MESSAGES["no_panel_selected"]` is visible on the page. 

### And (optional)

The rater form is still on screen -- the app did not advance to the QC viewer.

---

### Copy used

MESSAGES["rater_id_prompt"]       "Enter your Rater Name or ID:"
MESSAGES["rater_form_button"]     "✅ Continue to QC"
ERROR_MESSAGES["no_panel_selected"]

### Notes

- Niivue and montage panels are checked by default
  (`DEFAULT_PANELS = {"niivue": True, "montage": True, "iqm": False}` in
  `ui/constants.py`), so this test must actively uncheck both -- it is not the
  landing page's starting state.
- Neither panel checkbox has a `key=` yet, so use the label-based
  `uncheck_checkbox` helper with the exact labels from `PANEL_CONFIG`:
  `"🧠 3D MRI Viewer (Niivue)"` and `"📊 Montage"`.
- The rater ID check runs before the panel check in `landing_page.py`
  (`if not rater_id_clean: ... elif panel_count == 0: ...`), so the Rater ID
  field must be filled in first -- otherwise `invalid_rater_id` fires instead
  of `no_panel_selected`.
- Use `fill_text_input` for the Rater ID (no rerun inside a form) and
  `click_form_submit` for the submit button, not `click_button`.
