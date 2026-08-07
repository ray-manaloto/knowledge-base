---
type: "query"
date: "2026-08-07T16:38:59.856845+00:00"
question: "When adding a count-continuity assertion to the doc-merge path, is patching graphify_ops.merge_chunk enough?"
contributor: "graphify"
outcome: "useful"
---

# Q: When adding a count-continuity assertion to the doc-merge path, is patching graphify_ops.merge_chunk enough?

## Answer

No — there are TWO argv builders and the ticket cited one. graph._replay_doc_chunks builds its own argv for the kb-build REBUILD path, and that is the path on which the #186 loss (11 hyperedges to 8, no nodes moved) was actually observed. Thread from ONE table (_THREADED_COUNTS) so they cannot diverge. Also: the handoff file is UNLINKED on read, so the reader MUST return the whole mapping — a second per-field reader could never see the file, and would report unknown forever, which looks exactly like a passing check. And do NOT reuse the node messages single-cause wording: a doc merge has one way to drop a node and FOUR ways to lose a hyperedge, only one of which graphify announces.

## Outcome

- Signal: useful