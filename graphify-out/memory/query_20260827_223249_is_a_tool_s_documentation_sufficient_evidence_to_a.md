---
type: "query"
date: "2026-08-27T22:32:49.904177+00:00"
question: "Is a tool's documentation sufficient evidence to adopt it?"
contributor: "graphify"
outcome: "corrected"
correction: "I adopted THREE tools from their documentation without running them, and each was\nrefuted by the first execution:\n\n1. /deep-research — P3 adopted it as step 4 from its shipped doc. A lane could not\n   invoke it. The binary's own refusal reads \"by the coordinator or by workers\".\n2. antigravity:research — recommended as adopt #3 from its description, IN THE SAME\n   COMMIT that wrote up lesson 1. It is a COMMAND, not a skill; what is actually\n   reachable is the agy-delegate wrapper it shells out to.\n3. The mermaid fix — published as fixed THREE times without one observation:\n   <div> renders nothing, then .mermaid svg rules that never matched, then the\n   id-targeted set that finally worked.\n\nThe common shape: I treated a description as evidence, and a publish/commit result\nas verification. The correction that generalises is not \"read more carefully\" — it\nis that a tool is not adopted until it has RUN, and Ray's VALIDATED rule now\nencodes exactly that (real question end-to-end + a failing case + a test that can\ngo red).\n\nThe second-order lesson is worse: I claimed \"13 tracked artifacts use <pre>\ncorrectly, so the recipe is sound\" as evidence. That was an inference from source,\nnot an observation of a render — and two of those pages had been silently broken\nsince publication, which is proof nobody ever looked. An inference from source\ndressed as a measurement is the most dangerous thing I produce, because it wears\nthe measured voice.\n"
---

# Q: Is a tool's documentation sufficient evidence to adopt it?

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

- Signal: corrected
- Correction: I adopted THREE tools from their documentation without running them, and each was
refuted by the first execution:

1. /deep-research — P3 adopted it as step 4 from its shipped doc. A lane could not
   invoke it. The binary's own refusal reads "by the coordinator or by workers".
2. antigravity:research — recommended as adopt #3 from its description, IN THE SAME
   COMMIT that wrote up lesson 1. It is a COMMAND, not a skill; what is actually
   reachable is the agy-delegate wrapper it shells out to.
3. The mermaid fix — published as fixed THREE times without one observation:
   <div> renders nothing, then .mermaid svg rules that never matched, then the
   id-targeted set that finally worked.

The common shape: I treated a description as evidence, and a publish/commit result
as verification. The correction that generalises is not "read more carefully" — it
is that a tool is not adopted until it has RUN, and Ray's VALIDATED rule now
encodes exactly that (real question end-to-end + a failing case + a test that can
go red).

The second-order lesson is worse: I claimed "13 tracked artifacts use <pre>
correctly, so the recipe is sound" as evidence. That was an inference from source,
not an observation of a render — and two of those pages had been silently broken
since publication, which is proof nobody ever looked. An inference from source
dressed as a measurement is the most dangerous thing I produce, because it wears
the measured voice.
