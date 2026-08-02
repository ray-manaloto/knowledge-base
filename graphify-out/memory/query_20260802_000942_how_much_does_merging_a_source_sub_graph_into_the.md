---
type: "query"
date: "2026-08-02T00:09:42.895386+00:00"
question: "How much does merging a source sub-graph into the aggregate actually cost, and is kb-watch idempotent?"
contributor: "graphify"
outcome: "useful"
---

# Q: How much does merging a source sub-graph into the aggregate actually cost, and is kb-watch idempotent?

## Answer

Two lessons. (1) SIZE: source->sub-graph expansion is ~1.3x, but sub-graph->AGGREGATE growth is far larger — 71.0 MB of sub-graphs added >=155 MiB to a 364 MiB aggregate and took graph.json 7.6 MiB past the 512 MiB cap, failing the build. Check headroom against the second number. Fix was scope=study (a second axis from kind), partitioned BEFORE seeding so a study repo sorting first cannot become the corpus. (2) IDEMPOTENCE: merge-graphs re-namespaces node ids per merge, so re-merging a sub-graph does not dedupe — 0 duplicate IDs is the mechanism, not a reassurance. kb-watch doubled kb_setup nodes 1040->2080 and broke affected. Fix: .base-graph.json snapshot taken after external merges and before the self-merge; refresh_self restarts from it. Proven over 3 runs flat at 133873/1042 with node id sets IDENTICAL (0 added, 0 removed); sha256 churns from ordering only.

## Outcome

- Signal: useful