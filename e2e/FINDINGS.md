# What the e2e suite turned up

Things found while writing the tests in `e2e/tests/`, recorded here because
they are product questions rather than test problems. Nothing in this list is
fixed; each needs a decision from someone who owns the behaviour.

Two are pinned down by `xfail(strict=True)` tests, so CI stays green and the
test fails loudly the moment the behaviour changes -- at which point the
marker should be removed.

## Behaviour that contradicts what the UI promises

### Next does not require every task to be rated

`MESSAGES["nav_tooltip_next"]` tells the rater:

> When more than one QC task is shown, set PASS, FAIL, or UNCERTAIN for every
> task before continuing.

Nothing enforces this. With `--qc_task all` (three tasks on the page), rating
one task and pressing Next advances to the next subject, and the untouched
tasks are never written to the export -- indistinguishable later from tasks
nobody looked at.

Verified with the default QC rating set to **None**; at the shipped default of
PASS every task already counts as rated, so the gate is never reached.

Covered by `test_next_requires_every_task_to_be_rated` (xfail).

### The default QC rating is applied inconsistently

An unrated subject takes the configured default rating (shipped as **PASS**),
but *only* when reached by navigating -- the first subject the rater lands on
shows nothing selected. The relevant branch also skips the default when
`task_has_data_sources` is false, which is why subjects without derivatives at
the configured paths behave differently again.

Worth deciding whether the default should apply everywhere or nowhere.
Covered by `test_unrated_subjects_take_the_configured_default_rating` and
`test_default_rating_of_none_leaves_subjects_unrated`, both passing -- they
describe current behaviour rather than asserting it is right.

A related product question, raised in review and still open: with the shipped
default of PASS, pressing Next past a subject exports PASS for it without the
rater having judged it.

## Dead code and stale constants

### The viewer's overwrite guard is never called

`_require_overwrite_confirmation` is defined in `ui/components/qc_viewer.py`
and never called. `_save_qc_record` also takes an `allow_overwrite` parameter
that is never read in its body. The congratulations page has its own working
copy of the same function, which is the one spec 004 covers.

There is no sidebar save button any more, so nothing is being silently
overwritten today -- but the dead guard suggests an intent that was lost.

### Constants that no longer render anywhere

- `MESSAGES["qc_rating_prompt"]` -- the viewer writes its own
  `"#### 📊 Rate **<task>**"` heading instead.
- `INFO_MESSAGES["load_records_button"]` -- the button is hardcoded in
  `ui/views/landing_page.py` as `"📥 Confirm Import"`.

Both are safe to delete. They are worth noticing because a test written
against either one looks correct and can never pass.

### Copy still hardcoded in views

The ✅ / ⬜ completion marks in `ui/views/sidebar_cohort_nav.py` and the
`"📥 Confirm Import"` / `"Cancel"` buttons in `ui/views/landing_page.py` have
no `constants.py` keys, so the tests that touch them hold literal strings. The
overwrite warnings and confirm button were extracted for spec 004; these are
the remainder.

## Environment

### Streamlit is unpinned, and the DOM changed between versions

`requirements.txt` asks for `streamlit>=1.56`. A local environment on 1.58 and
a CI runner on 1.65 produced different markup for radio widgets, which failed
sixteen tests in CI while everything passed locally.

The suite side is fixed -- widgets are now located by ARIA role and accessible
name rather than by the component library's internal attributes, which is
stable across both versions. The unpinned dependency is still there, and will
cause the same class of surprise again.

### sub-CMH0001 has no derivatives at the configured paths

`pipelines/fmriprep/qc_demo.json` expects montages under
`derivatives/fmriprep/23.1.3/output/<id>/figures/`. `sub-ED01` has them;
`sub-CMH0001`'s files sit at `derivatives/fmriprep/<id>/figures/` instead, so
the viewer reports "Montage not found or could not be loaded" for it.

Harmless for the tests, which do not assert on the montage, but it means the
two-subject fixture exercises two different data situations.

## Known flake

`test_add_notes_pauses_autoplay` failed once in roughly a dozen full-suite
runs, while passing consistently on its own. It is the only test whose timing
depends on wall-clock rather than on the app: it waits out the autoplay
duration to prove the page did *not* advance. Under full-suite load on a
slower machine that margin may not be enough.

If it becomes noisy, widen the wait rather than removing the assertion -- the
"did not advance" check is the point of the test.
