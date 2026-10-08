# Autoplay

Autoplay automatically advances QC-Studio through the cohort on a timer.

## Turning it on and off

The controls are at the top of the sidebar on the QC viewer page.

| Control | Effect |
|---------|--------|
| **▶️ Play** | Starts (or resumes) playback and begins the countdown for the current page |
| **⏸️ Pause** | Stops playback and clears the countdown |

Autoplay is **off** at the start of every session.

## Setting the duration

Set the countdown length on the landing page, under **👤 Rater Information**.
The duration can be set between 5 and 15 seconds, and defaults to 10 seconds.

## Duration countdown

While playback is running, a countdown banner sits above the main QC viewer:

```text
⏱️  Next page in   3   s
```

## When autoplay pauses or stops

| Situation | What happens | Do you need to do anything |
|-----------|--------------|------------------|
| You start editing notes | Autoplay stops and the countdown is cleared | Press **▶️ Play** again to resume |
| You press **Next** manually | The page advances immediately and the countdown restarts from the full duration | Nothing |
| You press **Previous** manually | Same — the countdown restarts | Nothing |
| You use the sidebar subject filter | Autoplay continues, but only walks the **filtered** pages | Nothing |
| The timer expires on the last *filtered* page | Autoplay stops; the congratulations page is **not** opened while a filter is active | Clear the filter, then press **▶️ Play** |
| The timer expires on the last page of the unfiltered cohort | Autoplay stops; the congratulations page opens only if every page is rated | Nothing |
