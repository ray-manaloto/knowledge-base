---
type: "query"
date: "2026-08-07T21:07:45.522941+00:00"
question: "How do you apply 60+ cold-review findings to extraction chunks without the fix pass degrading, and how do you tell a real defect from a faithful extraction?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you apply 60+ cold-review findings to extraction chunks without the fix pass degrading, and how do you tell a real defect from a faithful extraction?

## Answer

Three moves. FIRST, dump every edge with its node LABELS inlined so direction is checkable by reading aloud; that gives judgment-free fixes a test, and the ones with no such test go last. SECOND, prove the applier round-trips the JSON byte-identically BEFORE it writes, then address fixes by content (source/target/relation triple) and assert each matches exactly one edge; a fix matching 0 or 2 is a bug in the fix table, not in the data. 107 insertions / 107 deletions across four files confirmed zero reformatting. THIRD and most important, control-arm every reviewer finding against the UPSTREAM bytes before touching a node. Of 63 findings, four were faithful reproductions of contradictions in the source docs themselves - including both P1s - and editing them would have corrupted an accurate extraction while every gate stayed green. hooks.md line 13 and line 265 read as one finding in the report and were two different things: one verbatim upstream, one a genuinely dropped clause. The rule that fell out: change what is FALSE, not what is coarse; when a source contradicts itself, record the tension and alter no claim.

## Outcome

- Signal: useful