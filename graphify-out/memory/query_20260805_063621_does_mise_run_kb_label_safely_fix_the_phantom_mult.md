---
type: "query"
date: "2026-08-05T06:36:21.438347+00:00"
question: "Does mise run kb-label safely fix the phantom multi-tag communities?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does mise run kb-label safely fix the phantom multi-tag communities?

## Answer

It fixes them and destroys hyperedges. Measured: phantom communities 326 to 0, where 326 equalled K exactly - the number of communities .self-graph occupies, contiguous 0..325 - and afterwards .self-graph is scattered across ids 67..9421, so it was folded into the global partition. But the same command deleted all 5 hyperedges: base-graph 5, post-build 5, post-label 0. Mechanism: to_json writes hyperedges from G.graph, and attach_hyperedges has exactly one caller inside build_merge, so the build_from_json path used by label and cluster-only never attaches them and to_json writes an empty list over the real one. Hyperedges are now known broken on three independent paths - kb-assemble drops them on the way in, the merge orphans their members, and kb-label deletes the survivors.

## Outcome

- Signal: useful