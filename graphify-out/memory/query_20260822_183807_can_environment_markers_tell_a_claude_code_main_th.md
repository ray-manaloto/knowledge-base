---
type: "query"
date: "2026-08-22T18:38:07.671264+00:00"
question: "Can environment markers tell a Claude Code main thread from a subagent, and did kb-context work?"
contributor: "graphify"
outcome: "corrected"
correction: "# A one-armed probe cannot discriminate, however carefully it is run\n\n## The belief that was wrong\n\n`kb_setup.context_usage` decided \"am I the main thread or a subagent?\" from two environment\nvariables, and its docstring defended the choice carefully: the positive case was\n*\"observed — both markers were read from a live fork\"*, and it explicitly, honestly flagged\nthat the negative case (a main session carrying neither) was *\"asserted, not measured\"*. It\neven reasoned about which failure direction was safe.\n\nEvery sentence of that was written in good faith, and the conclusion was still false.\n\n## What was actually true\n\nBoth markers are present in **both** arms:\n\n- `CLAUDE_CODE_CHILD_SESSION` is *\"Set to 1 in subprocesses Claude Code spawns via the Bash,\n  PowerShell, and Monitor tools, hook commands, and status line commands\"*\n  (`sources/agent-harness-docs/docs/claude-code/env-vars.md:208`). It marks a SUBPROCESS,\n  not an agent — every Bash tool call carries it, and `kb-setup context` runs in one.\n- `CLAUDE_CODE_FORK_SUBAGENT` is an operator-set flag that ENABLES forking\n  (`changelog.md:2211`), not a marker announcing you are one.\n\nSo observing them on a fork proved nothing: they would have been observed on the main\nthread too. The detector refused **100% of the time**, from the day it was written — a\ncheck that could only refuse, which made `/clear-prep`'s context trigger inert on every\nsession that ever ran it.\n\n## Why\n\nCare about the arm you DID run is not a substitute for running the other one. The\ndocstring's honesty about the missing arm made the module read as *rigorous*, which is\nexactly what stopped anyone going and running it — the flagged gap was treated as\ndisclosed-and-therefore-handled rather than as work outstanding.\n\nThe tests made it permanent. `test_main_thread_has_no_marker` asserted\n`child_marker({...}) is None` on an env **constructed without** the markers the real\nenvironment always has, and its sibling asserted a declared marker IS detected — which\nstays true of a marker that means nothing. Fixture-shaped from both sides, green forever.\n\n## How to apply\n\n1. **Both citations were already in this repo's own corpus** before the module was written.\n   `research-doc-sources.md` step 0 — query the graph first — would have settled it for\n   free. The cost here was not a wasted search; it was a feature that never worked.\n2. When a docstring says a case is *\"asserted, not measured\"*, that is a TODO with a\n   deadline, not a caveat. Treat an unmeasured arm as an open defect.\n3. Before trusting a discriminator, ask what it reads in the arm you did NOT run. If the\n   answer is \"the same thing\", it is not a discriminator at any level of care.\n4. A test whose fixture is constructed rather than observed cannot see this class. Arm the\n   end-to-end path against the REAL environment at least once.\n"
---

# Q: Can environment markers tell a Claude Code main thread from a subagent, and did kb-context work?

## Answer

# The 2026-08-22 resync + review round

Five commits on `repowise-mcp-0821`: Repowise MCP registered and its "no PR-scoped tool"
premise refuted (`25cb30f7`); the hosted graphify MCP's exit condition re-tested and its
destructive "delete .mcp.json" advice corrected (`8ce5214d`, `fda5bf28`, #450);
claude-code resynced 2.1.238 -> 2.1.240 with the plan authority re-recorded (`4f2193e9`);
and `kb-context` fixed (`e82708d9`, #451).

Then an 8-lane session-review workflow (23 agents, 3.15M tokens, 720 tool calls, ~29 min)
produced `.agent/plans/session-2026-08-22-c.md` — 102 OK / 0 broken on `kb-handoff-check`.
Its verification counts are the honest headline: **5 confirmed, 8 refuted, 25 NOT TRIAGED**
(the refuter budget ran out, so those are neither clean nor false), and all 8 lanes PARTIAL.

Three defects were found by measurement rather than reasoning, and all three had been
invisible to every gate:

1. `kb-context` could ONLY refuse (#451) — so `/clear-prep`'s context trigger was inert on
   every session that ever ran it.
2. The deep extraction Ray scheduled for next session is BLOCKED (#452):
   `_ACCEPTED_GRAPHIFY_RUNTIME` is still 0.9.47 while six other sites say 0.9.48.
3. The authority gate binding the committed digests to the real plan **skips** wherever the
   plan directory is absent, which is everywhere except a machine that has run `plan` (#317).

Scoped for next session, measured from the committed ledger rather than estimated: 58 chunks,
475 admitted units, `claude-opus-5` over `claude-cli` on the Max subscription, **concurrency
1**, $25/chunk and $100 total ceilings, 900 s per-chunk timeout, checkpoint-per-chunk so it
is resumable. Two blockers: #452 and `kb-build` red (#397/#417).


## Outcome

- Signal: corrected
- Correction: # A one-armed probe cannot discriminate, however carefully it is run

## The belief that was wrong

`kb_setup.context_usage` decided "am I the main thread or a subagent?" from two environment
variables, and its docstring defended the choice carefully: the positive case was
*"observed — both markers were read from a live fork"*, and it explicitly, honestly flagged
that the negative case (a main session carrying neither) was *"asserted, not measured"*. It
even reasoned about which failure direction was safe.

Every sentence of that was written in good faith, and the conclusion was still false.

## What was actually true

Both markers are present in **both** arms:

- `CLAUDE_CODE_CHILD_SESSION` is *"Set to 1 in subprocesses Claude Code spawns via the Bash,
  PowerShell, and Monitor tools, hook commands, and status line commands"*
  (`sources/agent-harness-docs/docs/claude-code/env-vars.md:208`). It marks a SUBPROCESS,
  not an agent — every Bash tool call carries it, and `kb-setup context` runs in one.
- `CLAUDE_CODE_FORK_SUBAGENT` is an operator-set flag that ENABLES forking
  (`changelog.md:2211`), not a marker announcing you are one.

So observing them on a fork proved nothing: they would have been observed on the main
thread too. The detector refused **100% of the time**, from the day it was written — a
check that could only refuse, which made `/clear-prep`'s context trigger inert on every
session that ever ran it.

## Why

Care about the arm you DID run is not a substitute for running the other one. The
docstring's honesty about the missing arm made the module read as *rigorous*, which is
exactly what stopped anyone going and running it — the flagged gap was treated as
disclosed-and-therefore-handled rather than as work outstanding.

The tests made it permanent. `test_main_thread_has_no_marker` asserted
`child_marker({...}) is None` on an env **constructed without** the markers the real
environment always has, and its sibling asserted a declared marker IS detected — which
stays true of a marker that means nothing. Fixture-shaped from both sides, green forever.

## How to apply

1. **Both citations were already in this repo's own corpus** before the module was written.
   `research-doc-sources.md` step 0 — query the graph first — would have settled it for
   free. The cost here was not a wasted search; it was a feature that never worked.
2. When a docstring says a case is *"asserted, not measured"*, that is a TODO with a
   deadline, not a caveat. Treat an unmeasured arm as an open defect.
3. Before trusting a discriminator, ask what it reads in the arm you did NOT run. If the
   answer is "the same thing", it is not a discriminator at any level of care.
4. A test whose fixture is constructed rather than observed cannot see this class. Arm the
   end-to-end path against the REAL environment at least once.
