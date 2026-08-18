---
name: kb-session-review
description: Review a whole ROUND from outside it — the circles, the forgotten requirements, the contradicted instructions, the unpinned tools, the context blowouts — then apply what it finds. Use when the user says work is going in circles, asks what this round got wrong, asks for a review of the last N sessions, or wants the project to self-correct. Distinct from kb-session-reflect, which counts what one transcript DID; this asks what the round should have done and did not.
argument-hint: "[since-date, e.g. 2026-08-15; defaults to the newest directive's date]"
---

# kb-session-review

A round is invisible from inside it. `kb-session-reflect` counts what a
transcript did — piped exit codes, hand-rolled harnesses, graph-query rate — and
it is a good instrument for its own question. It cannot see the questions this
skill asks: *what did we agree to and then drop, what does a file claim that the
repo does not do, what did we do four times.*

The 2026-08-17 run found, in one pass: **10 of 10 sessions over the 200K context
target with zero compactions**; **`gh` pinned nowhere** while `kb-ship` calls it,
so a fresh clone fails at the tool it needs most; a **`CLAUDE.md` line asserting
an `AGENTS.md` policy the repo does not follow**; and **`docs/direction/**` with
no reader at all** — a directive could be filed carefully and never consulted
again. None of those is reachable by a task.

That run was never saved, so it could not be re-run — the same disease it
diagnosed. `.claude/workflows/session-review.js` is the fix, and this skill is
what a workflow cannot be.

## Why the work splits in two

A workflow cannot call `AskUserQuestion`. That is not a detail: the last run's
single biggest waste was **two agents spending a full pass each hunting a
question one sentence from Ray settled**. So the interview happens HERE, first,
and its answers are threaded into every lane as `answered` so no lane re-hunts
settled ground.

Same split as `kb-extract`: the skill owns judgement and the conversation, the
workflow owns the fan-out.

## Process

### 1. Preflight — ASK BEFORE SPENDING ANYTHING

Read the newest `docs/direction/*.md` in full, and every
`.agent/plans/session-*.md` from the window. Then, in ONE `AskUserQuestion`
call (it takes up to four questions), settle whatever the round left ambiguous —
typically: which of two readings of a directive is meant, whether a half-finished
item is still wanted, and what the window is.

**Anything you could resolve by reading, read.** This is not a survey; over-asking
is its own failure (`clarify-before-acting.md` rule 3). Ask only what a probe
cannot settle.

### 2. Collect the arguments the workflow refuses to default

`transcriptDir`, `since` and `handoffs` are REQUIRED and have no defaults.

- `since` cannot be computed — `Date.now()` throws inside a workflow, so a
  default would be a hardcoded lie.
- `handoffs` is passed explicitly rather than globbed, because `.agent/` is
  gitignored and **a glob that matches nothing looks exactly like a round with no
  handoffs**.

`$ARGUMENTS` is the `since` date when the user gave one; with none, propose the
newest `docs/direction/*.md` date and confirm it in the preflight question rather
than assuming it.

Arm the window before you use it: `ls -lt` the transcript dir and confirm the
file just outside `since` really is older. The last run had four independent
agents agree on 14 files, which is what made the scope trustworthy.

### 3. Run the workflow

```text
Workflow({ name: 'session-review', args: { transcriptDir, since, directive, handoffs, answered } })
```

Six lanes sweep independently, every live finding is adversarially refuted, then
one ranked synthesis. It returns findings; it changes nothing.

### 4. Read the coverage before the findings

Every lane returns a COVERAGE object, and the workflow logs any lane that failed
to reach something. **Read that first.** A lane that was interrupted returns a
confident report about the part it reached and is indistinguishable from one that
finished — that happened twice in the round that wrote this file, once on a usage
limit and once on a content-policy refusal.

`partial_coverage` non-empty means the review is partial. Say so when you report,
and aim a follow-up at exactly what was missed. It does not buy an extra round;
it costs coverage.

### 5. Apply — and this is the half that gets skipped

A review nobody acts on is a document. Turn the confirmed findings into:

- **fixes**, where the finding is a live defect;
- **gates**, where the finding is a class rather than an instance — a finding is
  a SAMPLE of a class, so sweep for its siblings before patching the one;
- **issues** (`gh issue create`) for anything deferred, with the evidence;
- **work-memory**: `mise run kb-remember` then `mise run kb-reflect`, so the
  lesson compounds instead of living in a transcript nobody re-reads.

Then ship it the normal way: `kb-review` → receipt → `kb-ship` → `kb-land`.

### 6. Record what THIS review got wrong

Every run of this review has found defects in its own probes, and that section is
what made the next run better. The 2026-08-17 run's §7 is why this skill exists
in the shape it does. Write it, in the report, before you close.

## What this does not claim

Six lanes of an LLM reading a round. `NO FINDINGS` from a lane means that lane
found nothing — never that the area is sound. The cross-check refutes findings;
it cannot manufacture the ones nobody looked for. Its value is the *routes* it
takes, not a proof of completeness.

## See also

- `.claude/workflows/session-review.js` — the fan-out, and the ten lessons it enforces.
- `kb-session-reflect` — the per-transcript counter; run it too, with its arguments.
- `docs/research/reports/2026-08-17-session-review.md` — the first run, verbatim.
- `.claude/rules/probes-need-a-control-arm.md` — every lane's negative needs one.
