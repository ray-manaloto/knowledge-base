# Clarify Before Acting: Ask Until Sure on Ambiguous Work

When a task is ambiguous, admits multiple reasonable approaches, or is
hard to reverse, ask clarifying questions (via `AskUserQuestion`) and
keep asking across rounds until you are confident what to do. Do not
guess and proceed.

## Why this rule exists

Ray, 2026-06-29 (dotfiles, carried here verbatim): *"keep asking questions
until 100% sure on what to do"*, and record the preference so it need not be
repeated. In that same session the user's chosen approach turned out to be
**impossible** — the tool had no such feature. Surfacing that and
re-confirming the pivot before building avoided shipping the wrong thing.

This repo raises the stakes in one specific way: **ingestion is expensive and
semi-irreversible.** A host-agent extraction pass over a large source spends
real Claude tokens and lands a committed chunk in `sources/extractions/`. A
merged chunk becomes part of the graph other repos query. Guessing at what a
source is *for* before ingesting it is the costly mistake here.

## The channel: EVERY question is an `AskUserQuestion`

Ray, 2026-07-30, verbatim: *"enforce this and always do this going forward — use
the AskUserQuestion tool for questions you need from me"*.

This is broader than the rest of this file. The rules below govern **when** to
ask; this governs **how**, and it admits no exceptions:

- Any question whose answer you need before proceeding goes through
  `AskUserQuestion` — including a plain "confirm this?", a yes/no, and a
  "which of these two?". A question in prose at the end of a
  `SendUserMessage` does **not** count.
- `SendUserMessage` may carry the findings and context around a question. The
  question itself lives in the tool, never only in the prose.
- **In PLAN MODE, render the options** — pros and cons per option, multi-select
  where the choices are not mutually exclusive, and always leave the free-text
  escape. Ray has stated this **twice**, which is why it is recorded rather than
  remembered: a plan presented as prose asks the reader to reconstruct the
  alternatives before they can choose between them, and the answer that comes
  back is then about the summary rather than about the options.
- Bundle related questions into ONE call (it takes up to four) rather than
  several round trips.

**Why:** a prose question buried at the end of a long message is easy to miss
and gives the user nothing to act on. `AskUserQuestion` renders labelled
options, a recommendation, and an "Other" escape — so the question is
unmissable and answering it is one click. It also forces you to name the real
options and pick one, instead of offloading an open-ended prompt.

**The trigger, recorded so the narrow reading does not return:** a session
charting a wayfinder map asked its first four questions correctly, then ended a
message with two in prose — "confirm the map" and "want me to spawn the research
subagent". Both read as too small to warrant the tool, because rule 1 below
scopes asking to *ambiguous / multi-path / irreversible* work. Size is not the
test. **The test is only whether you need an answer.**

This does not license asking *more* — rule 3 still stands.

## Rules

1. **Ask before acting on ambiguous / multi-path / irreversible work.**
   If there is genuine uncertainty about scope, approach, or intent, or
   the action is hard to undo (deletes, pushes, merges, a large extraction
   run, external/outward-facing effects), resolve it with the user first.

2. **Recommend, don't just enumerate.** Lead with the option you'd pick,
   marked `(Recommended)`, and give the trade-offs. A question is a
   proposal to confirm, not a blank survey.

3. **Proceed directly on clear, low-risk, reversible tasks.** Do not
   manufacture questions for things with an obvious default or facts you
   can verify yourself — over-asking is its own failure mode. Pick the
   obvious option, state it, and move. `mise run kb-query`, a `graphify
   path`/`explain` read, and `mise run kb-build` (deterministic, no LLM)
   are all cheap and reversible; none of them needs a question.

4. **Surface infeasibility immediately.** If a chosen approach turns out
   impossible or much worse than expected mid-flight, stop and
   re-confirm the pivot with evidence — never silently substitute a
   different solution for the one that was agreed.

5. **Keep asking until sure.** A second clarifying round is cheaper than
   rework. Don't stop at one question if the answer revealed new
   ambiguity.

## Applies to

All non-trivial work: planning, multi-file changes, design choices,
source selection and ingestion strategy, destructive or outward-facing
actions, and any task where the request under-determines what to build.

## See also

- `do-not.md` — project invariants (some actions are never OK regardless
  of clarification).
- `probes-need-a-control-arm.md` — when the ambiguity is "is this fact
  true?", the answer is a second probe, not a question.
