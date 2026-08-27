---
type: "query"
date: "2026-08-27T17:06:58.159565+00:00"
question: "Why does /clear-prep keep leaving files uncommitted, and what actually causes the next session to get stuck?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why does /clear-prep keep leaving files uncommitted, and what actually causes the next session to get stuck?

## Answer

RETRIEVAL: `grep -rl "clear-prep" graphify-out/memory/` — the memory store is
write-only (#540), so read the FILES, never `kb-query`.

## The complaint, in Ray's words (2026-08-27)

"we've been having issues w /clear-prep leaving files uncommitted and the next
session flagging it and/or not being able to continue to the next claude session
without having to fix the session after running /kb-resume"

## The live instance, caught this round rather than recalled

At the moment `/clear-prep` was invoked, `git status --short` showed exactly one
entry:

    ?? docs/artifacts/three-sources-of-truth.html

An artifact authored and PUBLISHED mid-conversation, never committed. Nothing
was wrong with the round; the file simply had no commit that wanted it, because
it was produced while answering a question rather than while doing a task.

## The mechanism, not the symptom

Three things compose, and no single one is a defect:

1. Work that is not a "task" still writes files. Published artifacts are the
   clearest case — the output style makes an artifact the DEFAULT form of an
   explanation, so an exploratory conversation reliably produces tracked-worthy
   files that no commit message anticipated.
2. `/clear-prep` step 5 says "stage specific paths rather than `git add .`" —
   correct, and it means a file nobody names is a file nobody stages. The step
   commits what the round CHANGED, and these are files the round PRODUCED as a
   side effect.
3. `mise run kb-ship` REFUSES on untracked files under `docs/artifacts/` — that
   is #541, already filed. So the residue is not merely untidy: it BLOCKS the
   next session's ship until someone cleans it up, which is the "having to fix
   the session after running /kb-resume" half of the complaint.

## Why the obvious fixes are wrong

- `git add -A` in clear-prep: DENIED by `kb_setup.stage_explicitly`, and for a
  measured reason — a blanket add swept derived corpus evidence into a commit
  three times in one session.
- Gitignoring `docs/artifacts/`: the output style REQUIRES artifact source to be
  tracked in the repo ("artifact source lives in the repo, not the scratchpad")
  precisely so a diagram can be regenerated and kept in sync. Ignoring it trades
  one failure for a worse one.

## The shape a real fix probably has

A check that runs at handoff time and FAILS when the tree carries untracked
paths outside a known-ignorable set — naming them, so clear-prep cannot write a
handoff over a dirty tree. That is a gate, not a reminder, which is the only
thing this repo has ever measured as working (warning-only graph-first: 0/19
compliance; the DENY that replaced it: 62 -> 0).

RULED THIS ROUND (Ray, 2026-08-27): diagnose and file, do NOT build it this
round — the round was already over its context threshold and a new gate needs
its own cold review and gate run. The next session starts from a diagnosed
ticket rather than a symptom.

## What to do about it next session

Add the above to #541 as the root-cause analysis, then decide whether the fix
belongs in `clear-prep` (a step), `kb_setup` (a check with a mise task), or
`kb-ship` (relaxing the refusal for artifact sources specifically). The three
are not equivalent and the choice is Ray's.


## Outcome

- Signal: useful