---
type: "query"
date: "2026-07-31T02:22:11.672951+00:00"
question: "Does mise run kb-merge leave graph-prose.json stale, and does that matter?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does mise run kb-merge leave graph-prose.json stale, and does that matter?

## Answer

YES to both, measured 2026-07-30. After merging a fresh 132-node chunk, kb-query --prose still reported 2,421 indexed nodes — the pre-merge figure — and returned ZERO hits from the just-merged file. mise run kb-prose took it to 2,553 and the same query then returned the new material at rank 1-6 (top score 21.10 vs a pre-merge top of 9.53). This matters because --prose is the RECOMMENDED arm for questions about the documents (CLAUDE.md), and the kb-curator ingestion workflow is add -> merge -> label with NO prose step. So every merge-only ingestion has silently left the best query path answering from an older corpus until some later kb-build happened to re-derive it. kb-build DOES re-derive prose (confirmed in its log). Fix: run mise run kb-prose after kb-merge, or make kb-merge call prose.derive_for like build() does.

## Outcome

- Signal: useful