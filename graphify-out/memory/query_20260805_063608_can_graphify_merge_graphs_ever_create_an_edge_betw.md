---
type: "query"
date: "2026-08-05T06:36:08.511957+00:00"
question: "Can graphify merge-graphs ever create an edge between two pinned sources?"
contributor: "graphify"
outcome: "useful"
---

# Q: Can graphify merge-graphs ever create an edge between two pinned sources?

## Answer

No, by construction. merge-graphs relabels every input into a disjoint <tag>:: namespace before nx.compose, and compose unifies nodes by id equality only, so no node is identified across sources and no edge can span two. Measured 2026-08-05: 0 cross-source edges of 819,167 with 0 unclassified. Three independent discriminators agree; the sharpest partitions by the second :: segment of the node id and classifies 100 percent of edges while the same parser finds 108,647 edges crossing a community boundary. Upstream issue 1729 confirms the intent - colliding prefixes were treated as the defect because they invent cross-runtime edges. The only mechanism that produces a genuine cross-source edge is an LLM reading material from two sources inside ONE extraction chunk. Label-join was measured and withdrawn: 4,910 labels shared across sources, topped by main() in 36 sources, path in 28, run() in 23.

## Outcome

- Signal: useful