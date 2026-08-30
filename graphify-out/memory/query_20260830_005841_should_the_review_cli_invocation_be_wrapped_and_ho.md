---
type: "query"
date: "2026-08-30T00:58:41.915401+00:00"
question: "Should the review-CLI invocation be wrapped and hook-guarded, and where does #616 belong in the roadmap?"
contributor: "graphify"
outcome: "useful"
---

# Q: Should the review-CLI invocation be wrapped and hook-guarded, and where does #616 belong in the roadmap?

## Answer

Filed #616 to wrap the ad-hoc `agy-delegate`/`codex exec` cold-review CLI
invocation in a `kb_setup` module + mise task (no such wrapper exists today;
only `kb-review-receipt` is task-wrapped, not the review invocation itself).

Two findings worth remembering:

1. A subprocess call from inside a mise task never routes through a Bash
   PreToolUse hook — it isn't a Bash tool call. This means a wrapper task and
   a deny-hook on raw CLI invocations are COMPLEMENTARY, not alternatives
   (the same shape as the existing `check_first` guard: raw `ruff`/`ty` denied,
   `mise run kb-*` allowed). An initial analysis wrongly concluded "no hook is
   possible here" before this was caught.

2. `codex-implementer`/`codex-reviewer` (fable-orchestrator plugin) and
   `antigravity:review`/`antigravity:delegate` (antigravity plugin) are agent
   definitions living under `~/.claude/plugins/cache/...` — outside this
   project. This repo's own `do-not.md` rule 11 forbids editing anything
   there. So a blanket deny on `codex`/`agy` command words would ALSO break
   those plugins' own internal invocations, with no way for this repo to
   route around it on the plugins' side. The deny-hook SCOPE (review-only
   heuristic vs. full blanket vs. defer) is therefore a real architecture
   decision, not a mechanical build — left open in #616 for a human call.

fable-advisor placed #616 in `docs/roadmap/aggregated-research-chain.toml`
(unblocked, blocks nothing, not urgent) despite that file's header originally
scoping it to the aggregated-research plugin build — because
`mise run kb-next-ticket` is the only mechanism that reads that file, so a
ticket filed anywhere else is invisible to it. The header comment was amended
in the same commit to say the chain also tracks repo-internal enablers.


## Outcome

- Signal: useful