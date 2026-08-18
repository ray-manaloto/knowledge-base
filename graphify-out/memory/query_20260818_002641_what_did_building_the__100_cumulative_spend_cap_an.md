---
type: "query"
date: "2026-08-18T00:26:41.536692+00:00"
question: "What did building the $100 cumulative spend cap and the plan-time output ceiling teach about caps, evidence authorities, and hook budgets?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did building the $100 cumulative spend cap and the plan-time output ceiling teach about caps, evidence authorities, and hook budgets?

## Answer

# Two spend caps, and four things that only running found

Ray ruled two caps on 2026-08-17: a $100 cumulative provider-spend cap for the
semantic corpus run, and an output ceiling resolved at plan time instead of the
literal 8192. Both landed. What is worth keeping is not the caps but the four
defects that reading could not have caught.

## 1. A test of mine could not fail, and only the mutation arm said so

`kb-arms` reported **C4 SURVIVED**: deleting the spend records from the evidence
rotation — so every earlier chunk is charged again at the next chunk's read —
left the suite green. The fix was correct; the TEST was incapable of failing.

Cause: the helper named each record
`provider-spend-{pid}-{index}-{amount}.json`, with `index` from
`enumerate(amounts)`. Two calls each writing ONE record of the same amount
produced the SAME filename, so the second overwrote the first. With only ever one
file on disk, the double-charge the mutation introduces had nothing to double.

Fixed with a process-wide counter, then armed explicitly in both directions:
green with the fix, `Obtained: 3.0 / Expected: 2.0` without it.

**The general shape**: a fix and a test written together, both looking right, the
test structurally incapable of failing. Re-reading finds nothing. Running the
mutation is the only signal.

## 2. Advancing an "accepted" identity INVALIDATES the evidence it authorises

Claude Code self-updated 2.1.233 -> 2.1.234 under the session. Advancing
`graphify_semantic_slice._ACCEPTED_CLAUDE_VERSION` to match looked like ordinary
currency work. It turned the COMMITTED slice candidate from `unapproved` to
`failed`.

`_ACCEPTED_CLAUDE_*` is the authority for evidence that ALREADY EXISTS — a
retained receipt produced at 2.1.233, which no edit can change. The corpus
planner needs the opposite: what a run WILL use. The same module already draws
exactly this distinction for graphify (`_ACCEPTED_GRAPHIFY_RUNTIME` vs
`_CURRENT_GRAPHIFY_RUNTIME`) and states the rule in a comment: *"it may only
advance when the receipt does — never as part of a pin bump on its own, which
would assert an identity the receipt on disk contradicts."* I did the banned
thing to the constant next door.

Fix: give Claude the same `_ACCEPTED_`/`_CURRENT_` pair; the plan reads
`current_claude()`. **Two constants because there are two questions.**

## 3. SessionEnd hooks share ONE budget, not one each

Wiring the telemetry reaper into `SessionEnd` was the obvious placement and was
wrong. Re-probed live at 2.1.234 (`hooks.md:2948`, control `SessionEnd` x15 on
the same page): *"the overall budget is automatically raised to the highest
per-hook timeout configured in settings files, up to 60 seconds."* That is 60 s
**across all SessionEnd hooks**, and `currency.toml` already calls the number
load-bearing for the transcript audit. A third consumer would have competed with
it, and **a killed SessionEnd hook is silent** — the failure mode is an audit
that quietly stops existing. Moved to SessionStart, which is also the better
moment: the sink writes DURING a session, so reaping first bounds it ahead of
the growth.

## 4. A currency review is a CODE CHANGE here

The corpus plan was re-planned FOUR times in one round. Each re-plan was
invalidated by an edit to a module whose digest is inside the execution config.
`RE-PLAN LAST` was already written down; what this round adds is that reviewing a
tool's release notes ends in editing pinned constants, so **a currency review
belongs before the re-plan, however unrelated it feels.**

## Measurements worth not re-deriving

- **`OTEL_LOG_RAW_API_BODIES=file:<dir>` needs no exporter and no collector**, and
  took effect **without a session restart**. It writes **~1.17 MB per request**
  and rewrites the whole conversation each time: **67 MB / 117 files in ~25
  minutes**, 95.7 MB by the end of the round. The O(n^2) warning is not
  theoretical.
- **mise's registry has NO `git` entry at all.** Control: `gh` resolves to
  `aqua:cli/cli`; `git` returns nothing, and `aqua:git-scm/git` fails with
  `no aqua-registry found`. A mise-pinned git floor is not a thing that can be
  done, so the absence is recorded in `mise.toml` rather than left silent.
- **`pgrep -f "<string>"` matches its own invocation** when the search string is
  in the command line running it. An `until ! pgrep -f ...` waiter can never
  exit. Use a substring the wrapper does not contain (`bin/kb-setup arms`) or
  wait on the PID.
- **`claude --help` is byte-identical across 2.1.232, 2.1.233 and 2.1.234**
  (`71ad650f...`). That identity is what makes each version advance a mechanical
  bump rather than a fresh review of the CLI contract.
- **`.agents/skills/` was matched by NO gate** — tracked, read by the non-Claude
  lanes, and outside both `skill_lint` and `md_budget`. It had already drifted:
  `clear-prep`'s copy told the reader to edit a root `AGENTS.md`, a file this
  repo deliberately does not have.


## Outcome

- Signal: useful