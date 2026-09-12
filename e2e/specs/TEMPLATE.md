# Spec: <one line naming the rule being tested>

Copy this file, rename it `NNN-short-name.md`, and fill it in *before* writing
any test code. Two minutes of writing here saves an hour of rewriting a test
that checked the wrong thing.

---

**Screen:** landing | viewer | complete

**Category:** functional | edge | visual | interaction

**Priority:** high | medium | low

**Why end-to-end:** <What wiring would break and go unnoticed if this test
didn't exist? If a unit test in `ui/tests/` covers it just as well, write that
instead -- it is faster and more precise. Pure logic (string cleaning, config
parsing, dataframe filtering) belongs there, not here.>

---

### Given

<The state of the app before the action. Be specific about what has already
been done -- a fresh landing page, a rater who has already submitted, a cohort
part-way through rating.>

### When

<One action, described the way a rater would describe it. Not "call
SessionManager.set_rater_id" -- "submits the rater form with an empty ID".>

### Then

<What is *visible on screen* afterwards. This is the part people get wrong:

  BAD   the rating is saved to session state      <- invisible, untestable
  GOOD  the PASS button renders as selected
  GOOD  the progress counter reads "2 of 3"
  GOOD  ERROR_MESSAGES["invalid_rater_id"] appears

The one exception is the export: the tests own the output directory, so
"a CSV exists with one row per rated participant" is fully observable.>

### And (optional)

<A second observable consequence -- often "and the app did NOT move on".
Negative assertions like this are the most valuable ones and the easiest to
get wrong, so always pair them with `wait_for_app_run` via the interaction
helpers.>

---

### Copy used

<List the `ui/constants.py` keys this test asserts on, so whoever writes the
test imports them instead of hardcoding strings:

  MESSAGES["rater_form_button"]
  ERROR_MESSAGES["invalid_rater_id"] >

### Notes

<Anything the test author needs to know: widgets without a `key=`, a slow
rerun, data setup required.>
