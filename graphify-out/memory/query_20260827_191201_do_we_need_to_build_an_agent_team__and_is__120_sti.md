---
type: "query"
date: "2026-08-27T19:12:01.723561+00:00"
question: "Do we need to build an agent team, and is #120 still open?"
contributor: "graphify"
outcome: "corrected"
correction: "THREE beliefs were overturned this round, and all three were held confidently\nenough to be reported before being checked.\n\n1. \"We need to build an agent team.\" FALSE — one was researched on 2026-08-06\n   (docs/research/reports/2026-08-06-roster-synthesis.md, 353 lines, COMPLETE)\n   and SHIPPED. Six agents sit in .claude/agents/; five match the proposal\n   exactly on model+effort. It did not help because it was built on a substrate\n   that cannot answer: all six are told to query the graph FIRST, and .mcp.json\n   registers the HOSTED api.graphify.com 2-repo workspace rather than our corpus.\n   LESSON: before building the thing that was asked for, check whether a prior\n   round already built it. \"We researched this before\" is a citation to find,\n   not a memory to trust.\n\n2. \"#120 and #130 are both open, so federation is the durable fix.\" HALF FALSE —\n   #120 SHIPPED 2026-08-05 (graph.py:2552, \"THE FIX FOR #120\"), recovered 184 MB\n   / 33% of graph.json, and is gated on every build at graph_checks.py:52. I read\n   \"Both open\" off mise.toml:911 and repeated it to Ray as fact. The comment was\n   correct when written and went stale in three weeks.\n   LESSON: a correctly-cited fact is not a current fact. A code comment naming\n   an issue's state is a claim with an expiry date, and the issue tracker or the\n   code that fixed it is the primary source.\n\n3. \"The problem is which agent roles exist.\" FALSE, per Ray's own restatement:\n   the struggle is \"the communication between claude and codex models which\n   seems to be fragile and slow\". A roster is downstream of a transport nobody\n   has characterised — which is exactly why the 2026-08-06 roster did not help.\n   LESSON: when a user asks for X and a prior X already exists unused, the\n   question to ask is not \"build a better X\" but \"what is X sitting on\".\n\nMeta-lesson tying all three together, and it is the same one twice more this\nround (200-vs-294 open issues; \"~260\" lane reports that was a directory hardlink\ncount): EVERY number I reported without measuring it in-session was wrong. Five\nfor five. The measurements were each under a minute.\n"
---

# Q: Do we need to build an agent team, and is #120 still open?

## Answer

Seven blockers were named; six were real and ALL SIX were already filed as issues.
The seventh, unnamed, is that nothing orders the backlog.

MEASURED THIS ROUND (2026-08-27, session 14c497b3):

- 294 open issues, not 200. The 200 came from `gh issue list --limit 200`
  returning exactly its limit — a display bound read as a total. Two independent
  routes agree at 294.
- The backlog has NEVER shrunk: 0 of 6 weeks net-negative, 3 of 34 days. Close
  ratio fell 0.39 (weeks 1-4) -> 0.095 (weeks 5-6) while filing tripled (38 -> 125
  per week). The two biggest filing days are both round-review days: filing is a
  byproduct of the review rounds and nothing consumes it.
- Duplication is 4.8% confirmed / 6.8% incl. probable. Collapsing every cluster
  removes 11 issues. Triage is not the lever.
- 89 issues are ON-PATH to the stated finish line; 56 are ON-PATH *and* LIVE.
  Of the 89: 62 ingestion, 19 retrieval, 7 reach, 1 autonomy. The measured
  failure is in retrieval and reach, so the backlog is optimising the half that
  already works.
- ACID TEST: an agent could NOT get a sourced answer from this corpus. Seven
  control-armed probes; the graph contributed exactly one substantive fact.
  Cause: the corpus indexes its DEPENDENCIES, not its DECISIONS. mise.toml,
  .claude/rules/**, kb_setup/**, docs/direction/** and the issues are not
  ingested; `#130`, `#120`, `federate`, `shard` appear in neither graph layer.
  An English question loses to code symbols 101:1 (492,654 AST vs 4,868 prose)
  and the miss exits rc=0.
- Four graphify-out trees outside sources/, not two: graphify-out/ (live, 736
  MiB), .agent/kb/native-extract/graphify-out/ (138 MB orphan), brain/graphify-out/
  (empty), plus 73 inside pinned clones (by design).
- 10 stranded worktrees, ~30 local branches. None checked for uncommitted work.
- Lane evidence on disk: 235 reports in .agent/kb/reports/agents/, 478 .md under
  reports/ recursively, 159 cross-family reviews in .agent/kb/review/reports/.

OUTCOME: a five-round sequence, settled with Ray across five grilling rounds, and
the first goal+rider pair since 2026-08-01 (docs/goals/2026-08-27-1342-kb-
aggregated-research-*, kb-goal-check 15 OK / 0 WARN / 0 FAIL).


## Outcome

- Signal: corrected
- Correction: THREE beliefs were overturned this round, and all three were held confidently
enough to be reported before being checked.

1. "We need to build an agent team." FALSE — one was researched on 2026-08-06
   (docs/research/reports/2026-08-06-roster-synthesis.md, 353 lines, COMPLETE)
   and SHIPPED. Six agents sit in .claude/agents/; five match the proposal
   exactly on model+effort. It did not help because it was built on a substrate
   that cannot answer: all six are told to query the graph FIRST, and .mcp.json
   registers the HOSTED api.graphify.com 2-repo workspace rather than our corpus.
   LESSON: before building the thing that was asked for, check whether a prior
   round already built it. "We researched this before" is a citation to find,
   not a memory to trust.

2. "#120 and #130 are both open, so federation is the durable fix." HALF FALSE —
   #120 SHIPPED 2026-08-05 (graph.py:2552, "THE FIX FOR #120"), recovered 184 MB
   / 33% of graph.json, and is gated on every build at graph_checks.py:52. I read
   "Both open" off mise.toml:911 and repeated it to Ray as fact. The comment was
   correct when written and went stale in three weeks.
   LESSON: a correctly-cited fact is not a current fact. A code comment naming
   an issue's state is a claim with an expiry date, and the issue tracker or the
   code that fixed it is the primary source.

3. "The problem is which agent roles exist." FALSE, per Ray's own restatement:
   the struggle is "the communication between claude and codex models which
   seems to be fragile and slow". A roster is downstream of a transport nobody
   has characterised — which is exactly why the 2026-08-06 roster did not help.
   LESSON: when a user asks for X and a prior X already exists unused, the
   question to ask is not "build a better X" but "what is X sitting on".

Meta-lesson tying all three together, and it is the same one twice more this
round (200-vs-294 open issues; "~260" lane reports that was a directory hardlink
count): EVERY number I reported without measuring it in-session was wrong. Five
for five. The measurements were each under a minute.
