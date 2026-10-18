# Spec: The panels chosen on the landing page are the ones the viewer renders

---

**Screen:** viewer

**Category:** functional

**Priority:** medium

**Why end-to-end:** Spec 002 proves the panel checkboxes are *validated*;
nothing proves they are *obeyed*. Displaying images is what a QC tool is for,
and the link between a checkbox on one screen and a rendered panel on the next
exists nowhere except in the running app. If it broke, a rater would rate
subjects while looking at the wrong panel -- or at nothing -- which is worse
than an obvious crash, because the ratings would still get recorded.

---

### Given

A rater on a freshly loaded landing page who has left the Montage panel
selected and unchecked the 🧠 3D MRI Viewer (Niivue) panel.

### When

The rater submits the rater form and arrives at the QC viewer.

### Then

The montage panel is on screen and the Niivue viewer is not.

### And (optional)

Selecting 📈 QC Metrics instead renders the IQM panel -- a second case worth
covering only if it does not slow the suite much.

---

### Copy used

PANEL_CONFIG["niivue"]["label"]     "🧠 3D MRI Viewer (Niivue)"
PANEL_CONFIG["montage"]["label"]    "📊 Montage"
PANEL_CONFIG["iqm"]["label"]        "📈 QC Metrics"

### Notes

- **Identifying a rendered panel is the hard part of this spec**, and it is
  not solved yet. The panels are images and components, not text, so there may
  be no stable handle to assert on. Before writing the test, look at the
  viewer's DOM and decide what identifies each panel -- a container key is the
  robust answer, the same fix that made the autoplay countdown assertable
  (`key="autoplay_countdown_banner"`). Expect to add `key=` to the panel
  containers in `qc_viewer.py` as part of this spec.
- Assert on the *container*, not on a loaded image. Niivue initialises WebGL
  and decodes a real NIfTI; a test that waits for pixels is a test that waits
  tens of seconds and then fails on a slow machine.
- The negative half ("Niivue is not there") is the valuable half and the easy
  half to get wrong -- it must come after the rerun has settled, or it passes
  against the landing page where Niivue was never present either.
- This is the one spec that deliberately *does* load a viewer panel, so it
  will be among the slower tests. Keep it to a single panel combination unless
  the second case proves cheap.
- Niivue has a size ceiling (`base_mri_too_large`) above which it refuses to
  render and tells the rater to use the montage instead. `sample_data` is
  small enough that this should not fire, but if the Niivue assertion behaves
  oddly, check for that message before assuming the wiring is broken.
