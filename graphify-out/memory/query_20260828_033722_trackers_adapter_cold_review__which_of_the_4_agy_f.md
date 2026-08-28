---
type: "query"
date: "2026-08-28T03:37:22.645438+00:00"
question: "trackers adapter cold review: which of the 4 agy findings survived refutation, and why"
contributor: "graphify"
outcome: "useful"
---

# Q: trackers adapter cold review: which of the 4 agy findings survived refutation, and why

## Answer

The codex lane's trackers adapter (spec v6, commit 03c2f224) went to antigravity:review (agy pro, Gemini) as the cross-family cold lens because codex wrote it. 4 findings, 0 blocking. Refutation pass: two P1s were the SPEC's own pins (`command` = "the search argv", singular, spec line 66; arm command = "argv joined by single spaces", line 64) — the lane implemented faithfully, so both are design residuals, not defects; the P3 (codegen test mutates the tree) is the checked-in fetch-receipt precedent, house pattern. The P2 (msgspec decode of a zero-status gh payload uncaught) was CONFIRMED and had been found independently by the architect's own read before the lane returned — two families, same line. Fixed inline as a spec-saturated diff (Err(rc=Rc.NOT_RUN), mirroring pr.checks_state), armed by stashing the fix and watching both parametrisations go red. Lesson: the spec's v5 "accepted rc-1 traceback" clause covered validate() (programmer error) and was read by the lane as covering external input too — a stated exception gets applied one class wider than written.


## Outcome

- Signal: useful