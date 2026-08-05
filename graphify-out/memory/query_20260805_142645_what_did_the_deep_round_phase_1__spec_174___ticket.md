---
type: "query"
date: "2026-08-05T14:26:45.270644+00:00"
question: "What did the deep round Phase 1 (spec 174 / ticket 175) change, measure, and teach?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the deep round Phase 1 (spec 174 / ticket 175) change, measure, and teach?

## Answer

Phase 1 of the deep round (spec issue 174, ticket 175) restructured the build to ONE N-ary composition: the self sub-graph joins the same merge-graphs call as every corpus source (no second pass over the aggregate, ever - the standing invariant), the doc-chunk replay is merge-only, and one deterministic label pass with the hyperedge carry runs inside the build before the stamp; the study graph gets an isolated cluster pass (cluster-only writes literal graph.json wherever it runs, so the pass runs in a temp graphify-out). kb-watch recomposes from recorded inputs (.compose-manifest.json) plus a sha-verified last-wins-by-path ledger of between-build merges (.merged-chunks.json), refusing by name anything it cannot vouch for, and carries the currency stamp across its own clear. Measured on the first real build: prefix depth at most 1 on all 336,032 nodes (333,168 depth-1, 2,864 depth-0 semantic), 40 distinct repo tags (was 2), 5/5 hyperedges kept through build AND through a kb-artifacts re-cluster (was 0/5), 326 phantom community spans went to 0 with no manual label step, size 498,804,246 bytes = 0.93x graphify's default cap (via the carry writing indent=1 after a 1.00x near miss), and kb-currency-check is green after a plain build for the first time. Review: two cold rounds (Claude Opus fallback, cross-family for this codex-authored branch, after the Gemini lane hit quota), 12 findings total, 0 blocking after fixes. Both P1s were fix-introduced: round 1 caught my own spec stamping LIVE input fingerprints the recomposition never reads (drift laundering), round 2 caught the restamp fix being destroyed by the refresh's own stamp-clear - hidden because both restamp tests stubbed _clear_stamp. Sharpest lesson: the round's hyperedge carry created the exact artifact shape (a member list keyed "nodes" inside graph.hyperedges, before the top-level nodes array) that broke the round's own new insights scanner, which had been validated only against the pre-round corpus where label had emptied hyperedges. When a change reshapes an artifact, every reader of that artifact needs re-arming against the post-change shape. Follow-ups filed: 179 (manual kb-label does not restamp). Phases 2-4 are tickets 176-178, chained.

## Outcome

- Signal: useful