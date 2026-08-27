---
type: "query"
date: "2026-08-27T22:32:37.393712+00:00"
question: "What did the Aggregated round settle about building aggregated-research as a plugin, and what was measured rather than assumed?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the Aggregated round settle about building aggregated-research as a plugin, and what was measured rather than assumed?

## Answer

The round built `aggregated-research` (#509), evaluated it against a baseline, and
then Ray rescoped it: the skill becomes a PLUGIN in his own marketplace, wrapping
skills/CLIs/MCP servers/agents rather than living in this repo.

Seven decisions were settled by /grilling and are binding:
1. VALIDATED = a real question end-to-end with output pasted, PLUS a failing case,
   PLUS a test in tests/ that can go red. No tool enters the skill on a paragraph.
2. One package, four modules (now THREE — Chroma dropped, see below).
3. Modules staged: built in kb_setup/research/ first, split out to a standalone
   uv-installable package once the shape is proven.
4. Marketplace: reuse ray-manaloto/claude-code-marketplace, wiped, tagged
   `pre-reset-2026-08-27` first. Schema json.schemastore.org/claude-code-marketplace.json.
5. This repo DELETES its local copy and installs its own plugin — dogfood the
   distribution.
6. The plugin IS aggregated-research, declaring last30days / firecrawl / exa /
   context7 as dependencies via plugin.dependencies +
   allowCrossMarketplaceDependenciesOn.
7. plugin-dev installed at project scope to help build it.

The measured facts that decided the design:
- The marketplace schema supports plugin-to-plugin dependencies, so we COMPOSE
  rather than vendor.
- Three of four candidate tools have NO python library to wrap; only lychee ships
  anything and what it ships is the binary (lychee-bin 0.24.2 on PyPI).
- Chroma has $5 of credits, not a free tier -> dropped on Ray's rule.
- /deep-research is Scope -> pipeline(Search -> dedup -> Fetch+Extract) -> 3-vote
  adversarial Verify -> Synthesize, with VOTES_PER_CLAIM=3, REFUTATIONS_REQUIRED=2,
  MAX_FETCH=15, MAX_VERIFY_CLAIMS=25, and a THREE-outcome tally where an errored
  verifier is `unverified`, never `refuted`. It is user-invoke-only: the refusal
  says "by the coordinator or by workers".
- agy-delegate WORKS and is subagent-reachable; three of its four load-bearing
  claims confirmed against primary sources, one left unverified.
- The firecrawl CLI works (`firecrawl developer`); the MCP firecrawl_search hung up.

Ray's closing instruction: PROTOTYPE all the tools first, before building, so we
understand what we are actually building.


## Outcome

- Signal: useful