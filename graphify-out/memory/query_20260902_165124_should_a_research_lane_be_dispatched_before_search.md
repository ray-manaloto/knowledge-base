---
type: "query"
date: "2026-09-02T16:51:24.439963+00:00"
question: "Should a research lane be dispatched before searching the issue tracker?"
contributor: "graphify"
outcome: "corrected"
correction: "I dispatched a codex lane to measure whether graphify's semantic cache is\nbackend-blind. It came back with a decisive, control-armed NO on every\npersistence surface -- and the whole finding was already filed as issue #518 on\n2026-08-26, a week earlier, measured against v0.9.50, with three fix options\nwritten out and none chosen.\n\nCost: ~59k subagent tokens to re-derive a tracked issue.\n\nWHAT I SKIPPED: research-doc-sources step 0 says query the graph / the existing\nrecord FIRST. I went straight to a lane because the question felt novel TO ME.\nNovelty to the current context is not evidence of novelty to the project -- and\nthis project's whole premise is that the record outlives the context.\n\nTHE CHEAP CHECK, before any research lane on a question about our own tooling:\n`gh issue list --repo <repo> --state all --search \"<term>\"` plus a\n`mise run kb-query`. Seconds, against tens of thousands of tokens.\n\nNot zero value: the re-run confirmed it still holds at 0.9.53 (the issue was\nwritten against 0.9.50) and added that `--fallback-backend` already MERGES two\nbackends into one graph unmarked, which #518 does not state. But that is the\ndelta a five-minute read of #518 would have scoped correctly in the first place.\n"
---

# Q: Should a research lane be dispatched before searching the issue tracker?

## Answer

I dispatched a codex lane to measure whether graphify's semantic cache is
backend-blind. It came back with a decisive, control-armed NO on every
persistence surface -- and the whole finding was already filed as issue #518 on
2026-08-26, a week earlier, measured against v0.9.50, with three fix options
written out and none chosen.

Cost: ~59k subagent tokens to re-derive a tracked issue.

WHAT I SKIPPED: research-doc-sources step 0 says query the graph / the existing
record FIRST. I went straight to a lane because the question felt novel TO ME.
Novelty to the current context is not evidence of novelty to the project -- and
this project's whole premise is that the record outlives the context.

THE CHEAP CHECK, before any research lane on a question about our own tooling:
`gh issue list --repo <repo> --state all --search "<term>"` plus a
`mise run kb-query`. Seconds, against tens of thousands of tokens.

Not zero value: the re-run confirmed it still holds at 0.9.53 (the issue was
written against 0.9.50) and added that `--fallback-backend` already MERGES two
backends into one graph unmarked, which #518 does not state. But that is the
delta a five-minute read of #518 would have scoped correctly in the first place.


## Outcome

- Signal: corrected
- Correction: I dispatched a codex lane to measure whether graphify's semantic cache is
backend-blind. It came back with a decisive, control-armed NO on every
persistence surface -- and the whole finding was already filed as issue #518 on
2026-08-26, a week earlier, measured against v0.9.50, with three fix options
written out and none chosen.

Cost: ~59k subagent tokens to re-derive a tracked issue.

WHAT I SKIPPED: research-doc-sources step 0 says query the graph / the existing
record FIRST. I went straight to a lane because the question felt novel TO ME.
Novelty to the current context is not evidence of novelty to the project -- and
this project's whole premise is that the record outlives the context.

THE CHEAP CHECK, before any research lane on a question about our own tooling:
`gh issue list --repo <repo> --state all --search "<term>"` plus a
`mise run kb-query`. Seconds, against tens of thousands of tokens.

Not zero value: the re-run confirmed it still holds at 0.9.53 (the issue was
written against 0.9.50) and added that `--fallback-backend` already MERGES two
backends into one graph unmarked, which #518 does not state. But that is the
delta a five-minute read of #518 would have scoped correctly in the first place.
