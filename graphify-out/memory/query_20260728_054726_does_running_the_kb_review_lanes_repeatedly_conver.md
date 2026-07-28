---
type: "query"
date: "2026-07-28T05:47:26.026637+00:00"
question: "Does running the kb-review lanes repeatedly converge to zero findings?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does running the kb-review lanes repeatedly converge to zero findings?

## Answer

No. Five rounds against one branch found 4, 11, ~6, ~13 and ~28 findings, with a blocking-class gate hole in four of the five. Twice a fix introduced the next round's blocker: the TOCTOU push pinning removed git's accidental detached-HEAD guard, and the base-coverage check shipped with a test that could not fail. Budget for it and agree a stop rule BEFORE starting, because the receipt is SHA-keyed so every fix forces another full round.

## Outcome

- Signal: useful