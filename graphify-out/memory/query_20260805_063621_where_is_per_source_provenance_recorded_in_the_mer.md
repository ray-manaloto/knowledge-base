---
type: "query"
date: "2026-08-05T06:36:21.102096+00:00"
question: "Where is per-source provenance recorded in the merged graph?"
contributor: "graphify"
outcome: "useful"
---

# Q: Where is per-source provenance recorded in the merged graph?

## Answer

In the node ID, not the repo attribute. The repo field has exactly two values across 46 pinned sources - knowledge-base 331,318 and .self-graph 4,494 - because prefix_graph_for_global assigns repo unconditionally while local_id uses setdefault, so the final self-merge at graph.py:676-681 overwrites every already-merged tag. Read id.split("::")[1] instead: 39-40 distinct tags, correct for all 328,387 depth-2 nodes. Proof of exactly two prefix passes: a sampled node local_id lacks the OpenSymphony:: segment its id carries. The study graph is the control arm - it runs the same merge-graphs code with no second merge over its own output and keeps all 5 tags at depth 1.

## Outcome

- Signal: useful