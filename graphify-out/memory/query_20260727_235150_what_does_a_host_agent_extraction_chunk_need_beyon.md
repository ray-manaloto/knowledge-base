---
type: "query"
date: "2026-07-27T23:51:50.488189+00:00"
question: "What does a host-agent extraction chunk need beyond passing kb-validate-chunks?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does a host-agent extraction chunk need beyond passing kb-validate-chunks?

## Answer

EDGES. Measured 2026-07-27 ingesting the goal-engineering corpus: claude-docs.json arrived with 73 good nodes and ZERO edges, and sabrina.json with 16 nodes and 1 edge (14 orphans). Both PASSED kb-validate-chunks and would have merged cleanly — the validator checks schema, dangling endpoints and id collisions, none of which a chunk with no edges violates. But this corpus is queried by graph traversal, so an orphaned node is nearly unreachable: the ingestion would have looked successful and contributed almost nothing. Check nodes AND edges AND orphan count before assembling, not just the validator. Both agents fixed it when pinged with the specific gap (73n/0e -> 73n/96e; 16n/1e -> 57n/90e), so the fix is a ping, not a re-dispatch. Corollary for monitoring: a watch whose success condition is FILE PRESENCE cannot distinguish a rich chunk from an empty one — watch quality metrics instead.

## Outcome

- Signal: useful