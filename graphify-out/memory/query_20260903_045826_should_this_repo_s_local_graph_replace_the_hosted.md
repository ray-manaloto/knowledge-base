---
type: "query"
date: "2026-09-03T04:58:26.208695+00:00"
question: "Should this repo's local graph replace the hosted graphify MCP, or sit alongside it?"
contributor: "graphify"
outcome: "corrected"
correction: "I believed the local graph should REPLACE the hosted graphify, and shipped that\nswap (baf41a33). It was wrong in a way I could have checked and did not.\n\nThe hosted service is not a smaller copy of our graph — it is a DIFFERENT\ncapability set. Measured from the code we run (`sources/graphify/graphify/\nserve.py:1614-1744`): hosted 23 tools, local 10. Roughly thirteen capabilities\nexist only on hosted — seed search, file ranking, callers/callees/references,\ntraces, file-neighbours, imports/exports, tests-for, impact_and_risk,\nremember/recall, workspace and repository discovery, formal verification.\n\nAnd it is not a superset either: the LOCAL server carries `list_prs`,\n`get_pr_impact` and `triage_prs`, which the hosted inventory never listed. So\nneither side can be deleted without losing something.\n\nTHE ERROR IN MY REASONING was treating \"which corpus is bigger\" as the whole\nquestion. Node count (13,126 vs 359,146) is a statement about SCOPE. It says\nnothing about which TOOLS exist, and I let the first number settle the second.\n\nTHE COST WAS NOT HYPOTHETICAL. Sharing one server name broke codex outright —\n`Error: failed to load bootstrap configuration / url is not supported for stdio`\n— because a global entry and a project entry collided on the key `graphify`.\nOurs is now `kb`.\n\nThe general form: when two things answer the same question, ask what ELSE each\none answers before replacing either.\n"
---

# Q: Should this repo's local graph replace the hosted graphify MCP, or sit alongside it?

## Answer

Phase U's first slice. The round set out to make the claude/graphify/codex setup
observable, enforced and owned by tasks (#672), and the enforcement it built kept
finding defects in itself.

WHAT SHIPPED (11 commits on feat/phase-u-setup-inventory, 8/8 gates green):
- `docs/setup-inventory.md` — #672's DoD 1: configured vs OBSERVED RUNNING, every
  row naming the command that proved it, plus an explicit list of what it did NOT
  observe.
- `kb_setup.graphify_health` — `mise run kb-build` was FAILING and nobody knew.
  The OpenSymphony extract succeeded (11,004 nodes) and the health check failed
  the whole build on one benign line graphify narrates. Approved narrowly, read
  out of graphify's own if/else (`build.py:1969-1997`) rather than by wording.
  kb-build is now GREEN: 359,146 nodes / 807,085 edges.
- `kb_setup.codex_lane` + `mise run kb-codex` — one place owns the four codex
  flags a lane cannot be right without; a raw lane is denied.
- `kb_setup.destructive_git` — the first STATEFUL guard in the chain; denies
  reset --hard / clean / checkout / restore only when there is uncommitted work.
- codex 0.152.0 -> 0.152.1, manifest + lockfile with it.
- Both clients wired: `graphify` = hosted, `kb` = the local 359k graph.

THE MEASURED RESULT WORTH KEEPING: `codex review` works as a cold lane, and the
METHOD paragraph is what makes it work. Default instructions: 6 findings. With
`-c developer_instructions=<METHOD>`: 7 findings, 6 P1, every one EXECUTED — it
built scratch repositories and destroyed real files to prove them.

ELEVEN defects were found in this round's own code. ONE was found by a test.


## Outcome

- Signal: corrected
- Correction: I believed the local graph should REPLACE the hosted graphify, and shipped that
swap (baf41a33). It was wrong in a way I could have checked and did not.

The hosted service is not a smaller copy of our graph — it is a DIFFERENT
capability set. Measured from the code we run (`sources/graphify/graphify/
serve.py:1614-1744`): hosted 23 tools, local 10. Roughly thirteen capabilities
exist only on hosted — seed search, file ranking, callers/callees/references,
traces, file-neighbours, imports/exports, tests-for, impact_and_risk,
remember/recall, workspace and repository discovery, formal verification.

And it is not a superset either: the LOCAL server carries `list_prs`,
`get_pr_impact` and `triage_prs`, which the hosted inventory never listed. So
neither side can be deleted without losing something.

THE ERROR IN MY REASONING was treating "which corpus is bigger" as the whole
question. Node count (13,126 vs 359,146) is a statement about SCOPE. It says
nothing about which TOOLS exist, and I let the first number settle the second.

THE COST WAS NOT HYPOTHETICAL. Sharing one server name broke codex outright —
`Error: failed to load bootstrap configuration / url is not supported for stdio`
— because a global entry and a project entry collided on the key `graphify`.
Ours is now `kb`.

The general form: when two things answer the same question, ask what ELSE each
one answers before replacing either.
