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
