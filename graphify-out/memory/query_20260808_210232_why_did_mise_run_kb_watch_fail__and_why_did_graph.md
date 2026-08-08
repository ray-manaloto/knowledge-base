---
type: "query"
date: "2026-08-08T21:02:32.657083+00:00"
question: "Why did mise run kb-watch fail, and why did graph-first orientation keep failing on the newest modules?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did mise run kb-watch fail, and why did graph-first orientation keep failing on the newest modules?

## Answer

kb-watch was broken on main and the graph could not be recomposed. Root cause: build() and refresh_self() each had their OWN replay loop over the same committed chunks. build()'s applied chunks.replay_order (capture date) and threaded --prior-<field>; the recomposition loop did NEITHER, replaying manifest.chunks in stored alphabetical order with no arithmetic checked. Same committed corpus, two different graphs, chosen by the alphabet -- the exact defect replay_order was written to remove, fixed on one path and left live on its sibling. Cost: claude-code-docs-mirror (captured 07-30, 26 nodes) replayed AFTER claude-code-docs-2026-08-05-refresh (08-05, 116 nodes) and superseded it, hooks.md 69 nodes to 5 and skills.md 47 to 15, net -90; only graphify's 479 shrink guard refusing the write kept the regression off disk. Fixed with ONE shared _replay_pairs both callers route through, taking (chunk, root) PAIRS because the root is the only thing the two callers disagree about, plus a named chunks.replay_key so the sort key cannot be re-derived in two places. Verified end to end: rc=0, 359069 nodes, 881532 edges, 122 hyperedges 0 lost, 0 dangling. 9 of 9 mutation arms died. The lesson that outlives it: two fixes landing on one path and not its sibling is not two bugs, it is one missing seam -- and the symptom was that the self-graph was stale by exactly the newest modules, so graph-first orientation on session_reflect.py and graph_first.py could not work while the guard still scored the single query as compliance.

## Outcome

- Signal: useful