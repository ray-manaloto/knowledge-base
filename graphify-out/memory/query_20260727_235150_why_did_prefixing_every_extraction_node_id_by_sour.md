---
type: "query"
date: "2026-07-27T23:51:50.883264+00:00"
question: "Why did prefixing every extraction node id by source matter?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did prefixing every extraction node id by source matter?

## Answer

Because kb-assemble UNION-merges chunks, so two agents independently choosing the same id would silently collapse into one node and drop the other's content — no error, no warning. Briefing each of the three goal-engineering extractors with a mandatory distinct prefix (ceccarelli_ / sabrina_ / ccgoal_) made collisions structurally impossible rather than merely unlikely. Verified before assembling: 0 collisions across 262 nodes at the time of check, 293 in the final chunk. Cheap to check with a dict of id -> [chunk]; do it BEFORE assemble, since afterwards the loss is invisible.

## Outcome

- Signal: useful