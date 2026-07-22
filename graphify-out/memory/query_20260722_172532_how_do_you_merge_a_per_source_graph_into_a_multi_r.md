---
type: "query"
date: "2026-07-22T17:25:32.158194+00:00"
question: "How do you merge a per-source graph into a multi-repo aggregate graph.json without graphify's cross-project dedup error?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["build_merge", "deduplicate_entities", "merge-graphs"]
---

# Q: How do you merge a per-source graph into a multi-repo aggregate graph.json without graphify's cross-project dedup error?

## Answer

Pass dedup=False to build_merge/build (or use the merge-graphs CLI). Cross-project dedup is disabled by design: deduplicate_entities RAISES when nodes span >1 repo (a 'main' in repo A != repo B). Each source is already single-repo-deduped at extraction, so at merge-into-aggregate time dedup MUST be off. This was a real 60k-node kb-build failure; fixed in _merge_docs.py.

## Outcome

- Signal: useful

## Source Nodes

- build_merge
- deduplicate_entities
- merge-graphs