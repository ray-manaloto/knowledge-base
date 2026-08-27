---
type: "query"
date: "2026-08-27T04:36:39.785656+00:00"
question: "Can this repo's research-funnel clause be given a mechanism, and can the branch that convened to fix the funnel pay its own debt?"
contributor: "graphify"
outcome: "useful"
---

# Q: Can this repo's research-funnel clause be given a mechanism, and can the branch that convened to fix the funnel pay its own debt?

## Answer

# The 2026-08-26 funnel round — what it asked and what it found

## The question

This repo exists so that research it does becomes corpus other sessions can
query. Five clauses describe that purpose and none had a mechanism. The round
before this one convened to fix the funnel and did not funnel its own research:
33 files added under `docs/research/**` and `docs/artifacts/**`, and **zero
lines** under `sources/`.

The round asked: can that clause be given teeth, and can this branch's own debt
be paid?

## What was built

**A ship gate, `kb-funnel`.** A branch that adds or edits anything under
`docs/research/**` or `docs/artifacts/**` with no added or edited file under
`sources/**` and no `Funnel-exempt: <reason>` commit trailer now FAILS the ship.
Five distinct states, not two — `clean`, `funnelled`, `exempt`, `drift`, and
`no_base` (rc 127) so that "we could not check" can never render as green.

It was landed BEFORE the data it demands, deliberately, so its FAIL direction
was proven on real data rather than on a fixture: `DRIFT`, 33 docs files, 0
sources files, rc 1. The funnel data then flipped it to `FUNNELLED`, rc 0.

**The funnel itself.** 38 registry rows (114-151) recording every tool the
2026-08-26 survey judged, verdicts quoted verbatim rather than paraphrased, plus
eight pinned manifests for the live repos among them. Status `manifest`, never
`code`: `kb-build` is failing, so pinning is not extracting, and a registry that
claimed otherwise would be worse than a shorter one.

## What it cost, honestly

Two cold review rounds found 30 findings. **Three of the defects in round 2 were
introduced by round 1's own fixes**, including one BLOCKING: a test repaired so
that it computed its expectation from the same function it was testing, making
it unable to fail. Unwiring the guard from the hook entirely left it green.

## Numbers, all measured this session

| | |
|---|---|
| gate states, distinct | 5 |
| registry rows appended | 38 (114-151) |
| manifests pinned | 8 |
| tools in the survey | 45 distinct, across 38 report rows |
| already funnelled before this round | 2 manifests, 1 registry row |
| review findings | 19 (round 1) + 11 (round 2) |
| defects introduced BY round 1's fixes | 3, one of them BLOCKING |
| ship gates green at `125af27c` | 7 of 7 |


## Outcome

- Signal: useful