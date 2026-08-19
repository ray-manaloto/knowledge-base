---
name: kb-resume
description: "Pick up where the last session left off in the knowledge-base repo: find the newest handoff and directive, read the real git/gate/PR state, and report the branch, what shipped, what is owed, the standing traps, and the next task. Use this as the FIRST thing after a /clear or at the start of any fresh session here, and whenever the user says resume, catch me up, where were we, what was I doing, what is next, or pastes nothing at all after clearing. It replaces copy/pasting a handoff prompt between sessions."
argument-hint: "[optional: a specific handoff path, or a nudge like 'just the traps']"
---

# kb-resume — start where the last session stopped

`/clear-prep` writes a handoff. This reads it, and then checks it against the
repo rather than believing it.

`$ARGUMENTS`, when given, narrows the job: a path points at a specific handoff
instead of the newest, and a nudge like *"just the traps"* or *"only what's
owed"* selects which part of the report to expand. Empty is the normal case and
means the full reconciliation below.

That second half is the point. A handoff is written by a session at the end of
its context, and this repo has measured what that produces: a branch that had
moved on, a "pin 1.1.13" that was neither the right file nor the right number, a
gate claim describing a dirty tree. So this skill reports **two things side by
side** — what the handoff says, and what the repo says — and calls out any
disagreement rather than smoothing it over.

## Process

### 1. Find the handoff and the directive

```bash
ls -t .agent/plans/session-*.md | head -3
ls -t docs/direction/*.md | head -2
```

Read the **newest** of each, in full. Not a skim: the owed section and the
gotchas are the parts that cost a session when missed.

**`.agent/` is gitignored.** On a fresh clone there is no handoff at all, and
that is a different state from "no work pending" — say so plainly and fall back
to the newest `docs/direction/*.md` plus `git log`, which are tracked.

A directive file may carry several addenda, and the newest one is usually the
live agenda. Read to the bottom.

### 2. Get the real state, from the repo

```bash
mise run kb-session-state
```

One task, already handoff-shaped: branch, tree, recent commits, open PRs. A
failed `gh` lookup prints `COULD NOT ASK` rather than `none`, which is the
distinction that matters when deciding whether a PR is waiting.

**To COPY any figure out of it, use `uv run kb-setup session-state` instead** —
mise's output redaction mangles the branch name, every SHA and every PR number.
The task is right for reading; the direct call is right for quoting.

Then, only if the handoff makes claims about them:

```bash
mise run kb-handoff-check
mise run kb-currency-check
```

`kb-handoff-check` validates the handoff's own citations — a path that does not
exist, a gate claim with no artifact, a gate that ran against a dirty tree.
`kb-currency-check` is offline and silent when clean.

### 3. Reconcile, and report the disagreements first

Compare what you read against what you found. The useful output is not a summary
of the handoff — the user can read that. It is:

- **the branch you are actually on**, and whether it matches the handoff's;
- **anything the handoff asserts that the repo contradicts** — a merged PR it
  calls open, a gate it calls green with no artifact at that SHA, a commit that
  is not an ancestor of `main`;
- **the next task**, quoted from the handoff or the directive rather than
  paraphrased;
- **the standing traps**, because those are what re-cost time;
- **what is owed**, with issue numbers where the handoff gives them.

If everything agrees, say so in one line and move on. A clean reconciliation is
a short report.

### 4. Offer the next step, do not take it

End by naming the next task and asking whether to start it. Resuming is
orientation; the user may have arrived with something else in mind, and a skill
that reads a handoff and then starts executing it has decided something that was
not its to decide.

## Report shape

Keep it tight. Something like:

```
On `<branch>` at `<sha>` — <clean | N uncommitted>. <PR state.>

DISAGREEMENT: <only if there is one>

NEXT: <the next task, quoted>

OWED: <the short list, with issue numbers>

TRAPS: <the ones that would bite today>
```

Expand a section only when it earns it. The failure mode here is a wall of text
that restates a handoff the user could have opened themselves.

## What this does not do

It does not write, commit, or ship anything, and it does not update the handoff
— `/clear-prep` owns that end. It reads, checks, and reports.

It also cannot tell you the handoff is *complete*. `kb-handoff-check` verifies
citations, not coverage: a handoff can pass every check and still have dropped
an item nobody re-derived. If the previous round's owed list matters, read it
against the one before it.

## See also

- `.claude/skills/clear-prep/SKILL.md` — the other end of this loop.
- `.claude/skills/kb-session-review/SKILL.md` — what generates the handoff in
  `output: 'handoff'` mode.
- `.claude/rules/agent-artifact-conventions.md` — why `.agent/` is gitignored
  and what that means for a fresh clone.
