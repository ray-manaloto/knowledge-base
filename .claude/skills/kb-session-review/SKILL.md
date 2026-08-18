---
name: kb-session-review
description: Review a whole ROUND from outside it — the circles, the forgotten requirements, the contradicted instructions, the unpinned tools, the context blowouts, the ignored bot reviews, the pending work stranded on worktrees and branches — then apply what it finds. Use when the user says work is going in circles, asks what this round got wrong, asks for a review of the last N sessions, or wants the project to self-correct. Distinct from kb-session-reflect, which counts what one transcript DID; this asks what the round should have done and did not.
argument-hint: "[a kb-session-select selector, e.g. --last 3 | --current | --since 2026-08-15]"
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

### 2. Resolve the sessions with a task, not by hand

`sessions` and `handoffs` are REQUIRED and have no defaults.

**`sessions` comes from `mise run kb-session-select`** — never typed:

```bash
mise run kb-session-select -- --current            # this session (for a handoff)
mise run kb-session-select -- --last 3             # the last three
mise run kb-session-select -- --since 2026-08-15   # a datetime range
mise run kb-session-select -- --sessions <id> <id> # named explicitly
```

Pass its `sessions` array straight through. It resolves `started_at` from
**birthtime cross-checked against each transcript's own first timestamp**, and
says which clock it used — because mtime is not when a session ran. Measured: 20
of 238 transcripts carry a birth-to-mtime gap over 24h (worst 119.6h), and a run
of THIS review dropped a session holding **675 of the round's 1,693 tool calls**
because its UTC records and local mtime straddled midnight.

It **refuses rather than returning nothing**: an empty window exits 127 and says
how many transcripts it examined; an unknown id exits 2 naming it, never a
partial list.

- `handoffs` is still passed explicitly rather than globbed, because `.agent/` is
  gitignored and **a glob that matches nothing looks exactly like a round with no
  handoffs**. In handoff mode it is also the BACKLOG the composer reconciles
  against, so a short list is a short memory.

`$ARGUMENTS` is the selector when the user gave one; with none, propose
`--since <newest docs/direction date>` and confirm it in the preflight rather
than assuming it.

**Do not hand-arm the window any more.** The old instruction here was to `ls -lt`
the transcript dir and eyeball whether the file just outside `since` was really
older — a check performed by the same context that chose the bound. The selector
does it instead, and reports `started_at` with the clock that produced it, so the
scope is a resolved artifact you can paste rather than a judgement you made.

### 3. Run the workflow

```text
Workflow({ name: 'session-review', args: { sessions, handoffs, directive, answered } })
```

`output` (`'report'` | `'handoff'`, default `report`) decides the ARTIFACT;
`lanes` decides the WORK and merely defaults from it. They were one flag until
2026-08-18, which meant there was no way to ask for a full eight-lane sweep
ending in a handoff. An unknown value for either now THROWS rather than silently
falling back — a run that swept four lanes because one was misspelled reports as
confidently as one that swept five.

Eight lanes sweep independently, the highest-cost findings are adversarially
refuted, then one ranked synthesis. It returns findings; it changes nothing. The
two lanes the 2026-08-18 directive added carry their own preflight needs:
`bot-reviews` discovers the window's PRs itself with `gh`, and `pending-work`
checks a backup directory only if the preflight named one — so settle that
path (or its absence) in the interview rather than letting the lane guess.

**What each phase runs on**, because a run that inherits the session model puts
every agent on the most expensive tier available — which is exactly how one run
spent 78 agents and died before writing its report:

| Phase / lane | Runs on |
|---|---|
| `context`, `unpinned` | `haiku` / `medium` — registry lookups and counting jq |
| `forgotten`, `bot-reviews`, `pending-work`, `tooling-gap`, `contradicted` | `sonnet` / `high` |
| `circles` | `opus` / `high` — the round's highest-value lane, and judgment-heavy |
| Cross-check | `kb-adversarial-verifier` (the roster's own refuter, opus/high) |
| Synthesise | `kb-synthesist` on **`fable`**, falling back to `opus`/`xhigh` |

The fallback is reported as `synthesis_ran_on` in the return value. **It heals
model exhaustion only** — a session or weekly limit is shared across models, so
switching cannot escape it.

**The cross-check is capped** at `MAX_REFUTERS` (14) findings, ranked by
`cost_rank`, which keeps the whole run under the 25-agent advisory ceiling.
Anything past the cap is returned as **`not_triaged`** — a fourth state beside
`confirmed`, `refuted` and `unverified`, and logged per finding. Read it: it
means the review did not look, not that it looked and found nothing.

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

Eight lanes of an LLM reading a round. `NO FINDINGS` from a lane means that lane
found nothing — never that the area is sound. The cross-check refutes findings;
it cannot manufacture the ones nobody looked for. Its value is the *routes* it
takes, not a proof of completeness.

## See also

- `.claude/workflows/session-review.js` — the fan-out, and the ten lessons it enforces.
- `kb-session-reflect` — the per-transcript counter; run it too, with its arguments.
- `docs/research/reports/2026-08-17-session-review.md` — the first run, verbatim.
- `.claude/rules/probes-need-a-control-arm.md` — every lane's negative needs one.

## `mode: 'handoff'` — this workflow prepares `/clear-prep`'s handoff

Ray, 2026-08-18: *"it should be the session review workflow that is performing the
handoff preparation for /clear-prep since that is what we are building."*

`clear-prep/SKILL.md` states the problem outright — **"The handoff is written from
memory."** A session at the end of its context recollecting its own round is where
wrong, missing and vague come from, and that is directive item 1. Fresh subagents
reading git, the gates JSON, the issue tracker and the transcripts do not
recollect; they read.

```text
mise run kb-session-select -- --current
Workflow({ name: 'session-review', args: {
  output: 'handoff',          // the ARTIFACT; `lanes` defaults to the five below
  handoffOut: '.agent/plans/session-<date>-<letter>.md',
  sessions, handoffs, answered,
}})
```

Lanes in handoff mode: `forgotten` (what was asked and dropped), `pending-work`
(unlanded branches/worktrees), `circles` (the gotchas the next session would
repeat), `contradicted` (docs that drifted), `bot-reviews` (findings nobody
actioned). `unpinned`, `context` and `tooling-gap` are round-level and stand down.

The composer is told the shape `kb-handoff-check` parses — branch in the lead,
every gate claim carrying its commit with the sha backticked, `(absent)` on any
path cited because it does not exist — so the existing check becomes an **arm on a
derived artifact** rather than a spellcheck on a remembered one. It also proposes
MEMORY.md index lines; it never writes MEMORY.md.

### The composer RECONCILES the previous handoff — and did not, on run 1

The first real run (2026-08-18) beat the hand-written handoff at everything it was
given and was blind to everything it was not. It dropped **seven of the nine items**
under the previous handoff's own *"Owed, unchanged from the previous handoff"*
heading, the graphify-circle diagnosis and its plan path, and every standing
environment trap — codex out of credits, `find -newermt` on BSD,
`docs/session-review/runs/**` being formatter-exempt.

No lane failed. `handoffs` reached the **sweep** lanes and stopped there, and a lane
returns FINDINGS — so an item that is merely *still owed* was nobody's finding and
had no route to the composer. A backlog carrying only what a lane re-derived is a
backlog truncated to one round, which is the exact failure this mode exists to fix.

The composer now reads the handoffs itself and must state, for every item in their
owed/next/gotcha sections, one of **CARRIED / DONE (with the commit or issue) /
DROPPED (with the reason)**. Omission is none of those and is not allowed —
the same reason lane coverage is a required field: an omission and a decision are
indistinguishable unless the format forbids omission.

**So pass `handoffs` deliberately.** In handoff mode it is not window metadata, it
is the backlog. A short list means a short memory.

### Two rules the caller MUST keep

1. **Never make this the only path.** `/clear-prep` fires when the session budget
   is most depleted, and a session limit is **not model-scoped** — `judge()`'s
   fable→opus fallback cannot save it. A workflow handoff that dies leaves
   NOTHING, which is worse than an imperfect remembered one. Keep the manual
   handoff as the fallback and treat this as the preferred input.
2. **Always run `mise run kb-handoff-check` on the result.** That is what turns a
   nicer draft into a checked one. It has already caught, on a hand-written
   handoff: a cited path that did not exist, gate claims with no artifact, and
   gates that had run against a dirty tree.
