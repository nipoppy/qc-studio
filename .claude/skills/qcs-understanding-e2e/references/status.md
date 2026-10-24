# e2e suite: current status

**Last updated: 2026-09-12.** This file is perishable by design. If the date
above is old, verify before trusting it — and once the suite is running
routinely in CI, delete this file rather than letting it rot.

## Verified

- The fixture chain in `e2e/conftest.py`.
- `pytest e2e/ --collect-only` passes — imports and discovery are sound.
- The launch command was executed against the real app: it booted, reported
  healthy on `/_stcore/health`, and shut down cleanly.

## Not verified

**Anything requiring a browser.** The Playwright test ids in
`e2e/shared/app_utils.py` were taken from streamlit/streamlit's own
`e2e_playwright/shared/app_utils.py` and are stable across recent versions, but
have not been confirmed against this repo's Streamlit (1.63). The wait helpers
are likewise unexercised. `get_file_uploader` is weaker still — it is inferred,
not copied, because Streamlit's suite has no file-uploader helper.

## Next step

```bash
pip install -r e2e/requirements-e2e.txt
playwright install chromium
pytest e2e/ -m smoke -v
```

`test_app_boots` proves the harness. `test_rater_form_is_reachable` proves the
selectors. If the second fails, a test id in `shared/app_utils.py` is wrong for
this Streamlit version — fix it *there*, once, not by working around it in a
test.

## Roadmap

1. ~~Fixture chain and helpers~~ — built, browser-level unverified.
2. Smoke tests green; correct test ids as needed.
3. Landing-page scenarios: rater validation, panel validation, CSV upload and
   resume.
4. Rating flow: rate → navigate → complete; then export, asserting on the CSV
   via the `output_files` fixture — the strongest assertion available.
5. Parametrize smoke across pipelines by overriding `qc_config` (fMRIPrep,
   FreeSurfer, QSIPrep, XCP-D, NODDIreg, DWI-IQM).
6. CI job running `pytest e2e/ -m smoke` on PRs, traces uploaded on failure.

## Known weak points

- `output_dir` is shared across a file's tests (see SKILL.md); the
  `output_files` fixture is the mitigation, not a fix.
- No page objects yet. Extract them once three or four tests repeat the same
  "fill rater form, pick panels, submit" sequence — not before.
- Most QC-Studio widgets have no explicit `key=`, so `get_by_key` is currently
  of limited use. Adding keys is a small source change purely for testability
  and worth proposing to maintainers.
