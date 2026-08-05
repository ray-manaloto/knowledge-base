---
type: "query"
date: "2026-08-05T02:27:12.536746+00:00"
question: "How should a handoff checker extract the agent/report names it audits, and what does a full mutation score actually prove?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should a handoff checker extract the agent/report names it audits, and what does a full mutation score actually prove?

## Answer

Three readings were measured over all 37 handoffs before building anything. A prose anchor for agent names scored 1 correct capture in 42 (the word "agent" saturates this repo: .agent/, docs/agents/, ready-for-agent, agent-report-persistence.md). Binding a lane mention to the commits in its own block left 27 of 31 unbindable. The reading that works is the elided report citation, which path_citations excludes BY CONSTRUCTION because the elision character is in _NON_PATH_CHARS.

The durable lesson is not the feature. The first version passed 12 of 12 mutation arms and was still wrong in three ways a two-axis review found: a docstring claiming a directory scope the code never applied (the false-green direction, defended by a sentence asserting the opposite), an elided LEADING directory silently dropped, and two false numeric claims. A full mutation score is a statement about the tests, never about the design. Three of the now-15 arms exist only because the review found what no arm was asking about.

Two smaller lessons worth carrying. First, one review suggestion was DECLINED after running it: composing the writer's sanitiser on the reader side destroys the elision, turning a pattern into a literal that matches nothing; the two sides are asymmetric because their inputs are. Second, after fixing the dropped-directory case the re-derived count came back as the same number that had just been declared wrong. Two different quantities coinciding. That was recorded in all three artifacts rather than quietly corrected back, because a reader seeing only the final number would conclude the original claim had been right when it counted a different set.

Also: a subagent brief that omits the incremental-persistence instruction produces nothing durable. The first pair of review lanes wrote zero files; a disk probe with a control arm (0 touched against 374 for a loose filter) is what proved it rather than assuming the agents had died.

## Outcome

- Signal: useful