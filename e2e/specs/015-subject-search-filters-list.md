# Spec: Searching the subject list filters it to matching subjects

---

**Screen:** viewer

**Category:** interaction

**Priority:** medium

**Why end-to-end:** This widget is fragile by its author's own admission --
`sidebar_cohort_nav.py` carries a comment explaining that the search box must
be *created before* the Play/Previous/Next buttons or Streamlit blanks it, and
there is a whole "hold" mechanism (`SIDEBAR_SEARCH_HOLD_KEY`) to keep the
query alive across forced navigations. Ordering constraints like that break
silently under refactoring and cannot be seen from unit tests. Code with a
written-down "don't touch this or it breaks" note and no test is exactly where
a regression lands.

---

### Given

A rater on the QC viewer with more than one subject in the cohort, so the
subject list has something to filter.

### When

The rater types part of one subject's ID into the subject search box.

### Then

The subject list shows only the matching subject.

### And (optional)

A query matching nothing shows MESSAGES["sidebar_subjects_search_empty"] and
no subject rows at all.

---

### Copy used

MESSAGES["sidebar_subjects_search"]              "Search subjects"
MESSAGES["sidebar_subjects_search_placeholder"]  "Filter by subject or session"
MESSAGES["sidebar_subjects_search_empty"]        "No subjects match this search."

### Notes

- Needs the multi-subject config -- filtering a one-row list proves nothing:

      from conftest import two_subject_qc_config as qc_config

  `sub-CMH0001` and `sub-ED01` share no common prefix, so either ID filters
  cleanly to exactly one row.
- Subject rows are **buttons**, labelled `"<mark> <pid> · <sid>"` where the
  mark is ✅ or ⬜, with keys `sidebar_cohort_nav_<i>`. Counting visible rows
  means counting those buttons; `get_current_subject_label` will not help
  here, since it matches the viewer heading rather than the sidebar list.
- The search box uses `label_visibility="collapsed"`, so its label is not
  rendered as visible text -- a label-based getter may miss it. It has an
  explicit widget key; prefer `get_by_key`.
- It is a `st.text_input` **outside** a form, so typing triggers a rerun on
  blur/Enter rather than instantly. `fill_text_input` does not wait (by
  design, for in-form fields), so this spec needs the blur-then-wait treatment
  that `fill_text_area_and_blur` gave spec 010 -- check whether an equivalent
  exists for text inputs before hand-rolling one in the test.
- Filtering can renumber pages and force a navigation
  (`_page_after_filter_change` → `st.rerun()`), which flushes QC state. Do not
  assume the subject on screen stays the same after filtering; this spec is
  about the list, so assert on the list.
