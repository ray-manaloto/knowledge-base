---
type: "query"
date: "2026-08-07T04:47:57.090513+00:00"
question: "What did promoting the mutation harness to kb_setup.arms (#160) change about how a survivor is read?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did promoting the mutation harness to kb_setup.arms (#160) change about how a survivor is read?

## Answer

A survivor stopped being one verdict. Sweep 1 produced three, and they were three different things: (1) a REAL gap that looked inert - PYTHONDONTWRITEBYTECODE moved no verdict because the purge subsumes it, but the purge can fail, so it needed a test of its OBSERVABLE consequence rather than of its spelling; (2) a genuinely INERT mutation - bool(self.rows) was strictly implied by any(row.arm.control ...) beside it, so the two guards masked each other and the clause was DELETED rather than tested; (3) a PROBE defect - the arm mutated a branch the named test never reached, so it was asking a question the test could not answer. The module now reports four PROBE BROKEN states apart from SURVIVED for exactly this reason, and requires a `test` on every non-control arm so a red suite that does not name it is never credited as a death.

## Outcome

- Signal: useful