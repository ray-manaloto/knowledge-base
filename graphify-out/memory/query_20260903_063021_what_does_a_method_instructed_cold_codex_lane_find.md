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

WHAT THE METHOD PARAGRAPH PLAUSIBLY BOUGHT — a HYPOTHESIS, not a result. It said,
in substance: do not review by reading; for every numeric or factual claim,
construct the derivation and RUN it, and check CLI/config claims against pinned
argument definitions rather than help text or error strings. Findings 1 and 3 are
both invisible to a reading pass, because prose that cites a real file at real
line numbers reads as sourced — so METHOD is a plausible mechanism for them.

IT IS NOT EVIDENCE THAT METHOD CAUSED THEM, and an earlier version of this record
said it was ("the ONLY thing that could have produced findings 1 and 3"). Two
things refute that, both found by the next cold round reading this very file:

- **n=1 with no control.** One METHOD lane ran; zero no-METHOD lanes ran on this
  diff. A mechanism with no counterfactual arm is a story, not a measurement
  (`probes-need-a-control-arm.md` rule 5).
- **The diff was NOT docs-only**, which the premise required. It was five files
  and one of them, `.codex/config.toml`, is operational — and findings 2 and 3
  both land on config/prose pairs, not on prose alone.

`kb-review/SKILL.md:412-426` already names this exact shape and says it is "not
worth calling settled". This record was written by someone who had read that
paragraph and still wrote the causal claim, which is the more useful lesson:
knowing the rule did not prevent the violation. Third occurrence of METHOD
appearing to help; still third of three, still uncontrolled.

WHAT THE LANE GOT WRONG, and why checking it mattered. It reported that the
15-repo error also appeared in the two `graphify-out/memory/` files. It does not:
those say "returned 15 repositories, among them <name> at status: ready,
queryable: true", which is an accurate statement about what the call returned.
Accepting a correct finding's STATED SCOPE without checking it would have produced
an incorrect edit to committed work-memory.

VERIFIED — and the ROSTER and NODE figures have different provenance, which an
earlier version of this record collapsed into one sentence:

- **24 / 10 / 3 (tool counts)** hold by two independent routes: the lane's Python
  set comparison over the two hard-coded registries, and the caller counting this
  session's own `mcp__graphify__*` (24) and `mcp__kb__*` (10) tool rosters, whose
  shared names are `graph_stats`, `query_graph`, `shortest_path` (3). Re-derived
  by a later cold lane: 24→24, 10→10, 3→3.
- **13,152 (hosted nodes)** came from neither of those — it is `list_repositories`,
  a LIVE hosted API call, and neither roster comparison measures nodes at all.
  Being live, it is dated: the same call on 2026-09-03 returned **13,433**. Cite
  it with its date or re-run it; do not carry it forward as a constant.

The earlier version also said the route was `comm` over sorted registries. It was
not — the transcript uses a Python set comparison. `comm` is what such a
comparison usually looks like, which is why the wrong tool name survived writing
and one reading pass.


## Outcome

- Signal: useful