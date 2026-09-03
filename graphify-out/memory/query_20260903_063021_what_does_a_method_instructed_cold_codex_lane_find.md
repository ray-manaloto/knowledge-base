---
type: "query"
date: "2026-09-03T06:30:21.985200+00:00"
question: "What does a METHOD-instructed cold codex lane find on a DOCS-ONLY diff, and can its stated scope be trusted?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does a METHOD-instructed cold codex lane find on a DOCS-ONLY diff, and can its stated scope be trusted?

## Answer

The cold `codex review` lane, given a METHOD paragraph, found 3 P2 findings on a
DOCS-ONLY diff — and all three were the same species: a figure or a citation that
was believed because it sat beside something authoritative-looking.

1. `list_repositories` returns **15 repository entries**, of which only **14** are
   `status: ready` / `queryable: true`. One
   (`ray-manaloto/pydantic-deepagent-auto-claude`) is `not_started`,
   `queryable: false`, `nodeCount: null`. The branch had written "15 indexed
   repositories". Confirmed by a second, independent call by the caller.
2. An ELI5 page turned a tool-NAME count into a CAPABILITY claim — "21 of its 24
   tools have no answer on our side". The TOML comment beside it was careful to
   say "a tool count, not a capability count"; the page dropped the qualifier.
   Several hosted names have a local answer under a different name
   (`graphify_node` vs `get_node`).
3. Two files attributed the HOSTED 24-tool count to
   `sources/graphify/graphify/serve.py:1614-1744` — the file that defines the
   LOCAL ten-tool server. The lane AST-walked its `list_tools` and got the local
   ten back, which is the probe that settles it. The 24 was correct; its
   provenance was not.

WHAT THE METHOD PARAGRAPH BOUGHT. It said, in substance: do not review by reading;
for every numeric or factual claim, construct the derivation and RUN it, and check
CLI/config claims against pinned argument definitions rather than help text or
error strings. On a diff with no executable code this is the ONLY thing that could
have produced findings 1 and 3 — both are invisible to a reading pass, because
prose that cites a real file at real line numbers reads as sourced.

WHAT THE LANE GOT WRONG, and why checking it mattered. It reported that the
15-repo error also appeared in the two `graphify-out/memory/` files. It does not:
those say "returned 15 repositories, among them <name> at status: ready,
queryable: true", which is an accurate statement about what the call returned.
Accepting a correct finding's STATED SCOPE without checking it would have produced
an incorrect edit to committed work-memory.

VERIFIED: 24 / 10 / 3 and the 13,152 nodes all hold, by two independent routes
(the lane's `comm` over sorted registries, and the caller counting this session's
own `mcp__graphify__*` / `mcp__kb__*` tool roster).


## Outcome

- Signal: useful