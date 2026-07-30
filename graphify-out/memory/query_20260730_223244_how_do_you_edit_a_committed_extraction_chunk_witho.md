---
type: "query"
date: "2026-07-30T22:32:44.404585+00:00"
question: "How do you edit a committed extraction chunk without producing an unreviewable diff?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["cc_goal_small_fast_model", "ccgoal_evaluator_is_small_fast_model"]
---

# Q: How do you edit a committed extraction chunk without producing an unreviewable diff?

## Answer

CONTROL-ARM THE WRITER FORMAT FIRST: read the file, json round-trip it, and assert the bytes are identical BEFORE modifying anything. The chunks under sources/extractions/ are NOT written the same way — claude-docs-docs.json round-trips with a bare json.dumps(d), while goal-engineering-docs.json needs indent=1, ensure_ascii=False and a trailing newline. A naive json.dump(d, indent=2) over both produced a 23,657-line diff for a TWO-NODE change and had to be reverted. Correcting a node that the source no longer supports is legitimate re-ingestion rather than falsified provenance, PROVIDED captured_at moves with the label — the node then honestly records what the page said on that date instead of asserting a stale claim as current.

## Outcome

- Signal: useful

## Source Nodes

- cc_goal_small_fast_model
- ccgoal_evaluator_is_small_fast_model