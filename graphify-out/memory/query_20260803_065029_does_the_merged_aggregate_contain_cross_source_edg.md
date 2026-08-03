---
type: "query"
date: "2026-08-03T06:50:29.176493+00:00"
question: "Does the merged aggregate contain cross-source edges that federating across per-source graphs would lose?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does the merged aggregate contain cross-source edges that federating across per-source graphs would lose?

## Answer

No. Measured on the rebuilt aggregate: 0 cross-namespace edges of 815,481 across 40 namespaces, 0 unresolved endpoints. Control-armed — injecting one synthetic crossing moves the count 0 to 1, so the detector discriminates. merge-graphs namespaces every input before nx.compose, so an edge can only exist between ids that shared a graph when it was written. This generalises #101 (python/ and tests/ needed ONE extraction root) from our own trees to every source, and settles the risk that blocked #130: federation costs nothing in recall. The measurement was IMPOSSIBLE before #120 — prefix_graph_for_global overwrote node['repo'] on every re-prefix, so early-merged sources all carried the accumulator's tag.

## Outcome

- Signal: useful