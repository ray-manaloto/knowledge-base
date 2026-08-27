---
type: "query"
date: "2026-08-27T19:11:55.832827+00:00"
question: "Are we using graphify wrong, and what agent team gets us to the knowledge-base goal?"
contributor: "graphify"
outcome: "useful"
---

# Q: Are we using graphify wrong, and what agent team gets us to the knowledge-base goal?

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

- Signal: useful