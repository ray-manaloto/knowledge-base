---
type: "query"
date: "2026-08-25T05:03:08.396945+00:00"
question: "Did this round follow the standing directives it had in context?"
contributor: "graphify"
outcome: "corrected"
correction: "Noticing a trap mid-session does not stop you walking into it again — only a DENY\ndoes. This round caught a piped exit code lying to it, said so out loud, and then\npiped a gate's exit code twice more.\n\nSo the actionable form is: when a round finds itself violating a warn-only\ndirective, the remedy is not to resolve harder, it is to ask whether that\ndirective should become a guard. The two guards that fired this round\n(bare-interpreter, graph-first) each changed behaviour on the spot and were never\nviolated twice; the two warn-only ones (piped-rc, hand-rolled arms) were each\nviolated 3x by a session that knew both rules and had them in context.\n\nConcretely for the next round: `mise run kb-arms -- <spec.toml>` is the harness,\nnever a scratchpad heredoc — and it is now 152 hand-written harnesses deep, which\nis a number that should be falling. And a `2>&1 | tail` on any gate is the shape\nto catch yourself on, because the pipe returns tail's status, not the gate's.\n"
---

# Q: Did this round follow the standing directives it had in context?

## Answer

Measured by `mise run kb-session-reflect` over this round's own transcript
(1 session, 100 bash commands scanned), not recalled:

* **Hand-rolled mutation harness x3**, where `mise run kb-arms -- <spec.toml>`
  exists and owns exactly that loop. These are the 150th-152nd hand-written
  harnesses across 21 sessions. A scratchpad harness drops the `__pycache__`
  mitigation, which can credit an arm with a death the mutation never caused —
  so the three arms this round leaned on hardest were run on the shape the task
  exists to replace.
* **`piped-rc` x3** — `mise run kb-gates 2>&1 | tail`, three times. This is the
  directive `kb-check`/`kb-gates` were BUILT for, after 35 such invocations in one
  session and 12 more in another. Worse: this round explicitly NOTICED the trap
  mid-session (a `kb-check` run printed `rc=0` from `tail` while the task itself
  reported ERROR) and still did it again afterwards.
* **`bare-interpreter` x1** — a `python3` invocation, caught by the hook DENY.
* **Counting greps: 0 of 6 carried a control arm in the same command.** Six
  stood alone, including sweeps whose NEGATIVE result was reported (the dangling-
  reference sweep, the stale-string sweep). Two of those were separately
  control-armed in a later command, which is not the same as the probe carrying
  its own arm.

The pattern across all four: the guards that DENY were obeyed 100% (the
bare-interpreter and graph-first denies both fired and both changed behaviour
immediately), while the directives that only WARN were violated at a rate. That is
the same finding this repo has now measured four separate times, and this round is
another data point for it rather than an exception.


## Outcome

- Signal: corrected
- Correction: Noticing a trap mid-session does not stop you walking into it again — only a DENY
does. This round caught a piped exit code lying to it, said so out loud, and then
piped a gate's exit code twice more.

So the actionable form is: when a round finds itself violating a warn-only
directive, the remedy is not to resolve harder, it is to ask whether that
directive should become a guard. The two guards that fired this round
(bare-interpreter, graph-first) each changed behaviour on the spot and were never
violated twice; the two warn-only ones (piped-rc, hand-rolled arms) were each
violated 3x by a session that knew both rules and had them in context.

Concretely for the next round: `mise run kb-arms -- <spec.toml>` is the harness,
never a scratchpad heredoc — and it is now 152 hand-written harnesses deep, which
is a number that should be falling. And a `2>&1 | tail` on any gate is the shape
to catch yourself on, because the pipe returns tail's status, not the gate's.
