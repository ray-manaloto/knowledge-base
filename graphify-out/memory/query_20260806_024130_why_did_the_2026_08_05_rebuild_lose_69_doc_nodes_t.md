---
type: "query"
date: "2026-08-06T02:41:30.490632+00:00"
question: "Why did the 2026-08-05 rebuild lose 69 doc nodes the incremental merge had, and what made chunk supersession deterministic?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did the 2026-08-05 rebuild lose 69 doc nodes the incremental merge had, and what made chunk supersession deterministic?

## Answer

build_merge gives a source_file to the LAST chunk that names it - it prunes every existing node carrying the same value before adding its own - so chunk REPLAY ORDER is the supersession rule, and build() replayed the glob alphabetically. Measured by arithmetic, not theory: the 2026-08-05 refresh chunk and goal-engineering-docs.json both said bare "hooks.md", so the rebuild replaced the fresh page's 69 nodes with the older chunk's 13 (the [merge] line printed +290 while the total rose 221; 290-221=69), while the incremental kb-merge - new chunk last - did the exact reverse. Same committed corpus, two different graphs, chosen by the alphabet, zero warnings either way: invariant 3's precise failure shape. Fixes: chunks.replay_order (capture-date order, newest last, undated first, name ties - mutation-armed with fixtures where alphabetical and capture order fully disagree); kb-extract.js sourceFileFor emits CLONE-RELATIVE source_file (a bare basename is a global namespace collision; the clone-relative path is collision-free AND is what makes intended supersession fire); captured_at is format-validated because "zzz" beats every real date lexically. Deferred with tracked homes: per-file-vs-per-chunk date inversion detector is #189 (measured zero live instances); legacy bare-basename identity migration is #187's second half. Bonus mechanism fact: graphify's doc merge CANONICALIZES node ids from source_file (docs_claude_code_hooks_*), rewriting hyperedge members consistently - probe by source_file, not by the chunk's raw ids.

## Outcome

- Signal: useful