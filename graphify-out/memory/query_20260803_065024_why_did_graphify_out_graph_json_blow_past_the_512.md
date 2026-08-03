---
type: "query"
date: "2026-08-03T06:50:24.782866+00:00"
question: "Why did graphify-out/graph.json blow past the 512 MiB read cap, and is merging inherently expensive?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did graphify-out/graph.json blow past the 512 MiB read cap, and is merging inherently expensive?

## Answer

No — the cost was a pairwise merge LOOP in kb_setup.graph.build(), which re-fed graph.json in as an input once per source while graphify's prefix_graph_for_global prefixes every input unconditionally. Measured: 184 MB / 33% of the file was duplicated 'repo::' prefix, node-id depth 1-22 (mode 10). One N-ary merge-graphs call fixes it: depth 1-2, waste 0.00%. Merging N sources costs ONE prefix per node. Growth is now linear in ingested bytes, so what we ingest is the only lever left — the 13 toolchain pins are 266 MB, 49% of all sub-graph bytes, against graphify's 11 MB.

## Outcome

- Signal: useful