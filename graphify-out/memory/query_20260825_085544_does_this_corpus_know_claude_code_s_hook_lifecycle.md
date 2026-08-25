---
type: "query"
date: "2026-08-25T08:55:44.824973+00:00"
question: "Does this corpus know Claude Code's hook lifecycle events, and why did the first query say no?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does this corpus know Claude Code's hook lifecycle events, and why did the first query say no?

## Answer

The corpus already held the answer and the DEFAULT QUERY VERB could not surface it.

Measured 2026-08-25, same graph, same question ("what hook lifecycle events does
Claude Code support"):

- default BFS `--prose`: 313 nodes, TRUNCATED to 18, ZERO relevant — it returned
  goal-engineering docs, the dotfiles secrets spec, and graphify's SECURITY.md.
- `--idf --top 12`: all 12 were hook material, correctly ranked, with the exact
  node `ConfigChange event` at rank 6.

Every event asked about was already ingested via
`agent-harness-docs/docs/claude-code/hooks.md` and `code.claude.com_docs_en_hooks.md`
— ConfigChange, CwdChanged, FileChanged, WorktreeCreate, WorktreeRemove, TaskCreated,
plus the caveat node "FileChanged and StopFailure use a NARROWER exact-match set".

Two consequences beyond the retrieval bug itself:

1. The `graph_first` hook is satisfied by a query that CANNOT answer. It requires
   that *a* graph query ran, not that it returned anything useful — so an 18-of-313
   BFS clears the guard and licenses the repo-wide grep it exists to prevent.
2. A session that trusts the empty-ish result reaches for the web docs, which is what
   happened here before the second arm was tried.

Filed as #489. The rule "control-arm an empty graph result" already exists
(probes-need-a-control-arm.md); what it lacked was the observation that a NON-empty
but irrelevant result is the same failure wearing better clothes.


## Outcome

- Signal: useful