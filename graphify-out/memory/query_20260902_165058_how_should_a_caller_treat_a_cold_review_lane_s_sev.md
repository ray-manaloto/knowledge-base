---
type: "query"
date: "2026-09-02T16:50:58.710706+00:00"
question: "How should a caller treat a cold review lane's severity grades?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should a caller treat a cold review lane's severity grades?

## Answer

The cold kb-review lane on 69c126cbaef8 rated six findings P2. Three were
actually P1, all one shape: the new kb-extract-census reported a clean result
for a question nobody asked. It swept `kind = docs` sources kb-build never
AST-scans (79 built, 8 docs, build scans 71), dropped a missing clone silently
while still printing "0 BLOCKED" with rc 0, and exited 0 on an `--only` name
matching nothing.

This repo had already ruled on that exact shape four times -- kb-session-select,
kb-attribute-write, kb-skill-score and skill_lint all REFUSE rather than return
an empty result. The census was the one new tool that did not, and a lane graded
it P2 because P2 is what "cosmetic-looking predicate" looks like from outside.

The durable lesson is about the CALLER, not the lane: a lane's severity grade is
an input, not a verdict. verify-before-advancing already says an UNVERIFIED item
in a lane report is not done; the same applies to a graded one. Re-read each
finding against the house rules before accepting its severity.


## Outcome

- Signal: useful