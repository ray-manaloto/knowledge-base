# `docs/goals/` — goal + rider pairs

One **pair** of markdown files per round of agent work:

- a **goal** — the ≤4,000-character text pasted after `/goal` (with a space before
  the condition), and nothing else;
- a **rider** — unbounded prescriptive detail the goal points at.

The convention is Greg Ceccarelli's
([*Goal Engineering: how I brief coding agents using paired goal+rider documents*](https://www.gregceccarelli.com/goal-engineering),
2026-05-18), adopted here after a research pass whose reports live in
`.agent/kb/reports/agents/res-*.md`. His TL;DR:

> Two markdown files per round of agent work: a goal (under 4,000 characters) and a
> rider (unbounded, with phases and named tests). The agent reads both, executes
> against them, and commits its work alongside them. The pair lives in `docs/goals/`
> forever.

## Naming

```text
docs/goals/<YYYY-MM-DD>-<HHMM>-<project>-<topic>-{goal,rider}.md
```

`<HHMM>` is local 24-hour authoring time, so `ls` sorts in true authoring order rather
than alphabetically by topic. **The pair shares one timestamp** — never split it across
minutes, or the sort breaks.

## The index

| Pair | Headline word | Round | Status |
|---|---|---|---|
| `2026-07-27-1702-kb-redaction-legibility` | **Legible** | Why `mise run` masks its own output as `[redacted]` | achieved |
| `2026-07-31-1348-kb-fluent-stale-graph` | **Fluent** | SessionStart stale-graph detection + the graphify/mise/hk/fnox release-notes review | achieved |
| `2026-07-31-2056-kb-navigable-graph` | **Navigable** | Index our own library for blast radius, ingest three peer tools, stand up a reusable cross-family review team, fold in the graphify version-sync tail | stalled |
| `2026-08-01-2116-kb-settled-claims` | **Settled** | Re-derive every deferred or inherited claim: #101's cross-namespace edges, the currency tail, two cross-report disagreements, and `kb-tool-review.js` exercised end-to-end on a fourth peer tool | achieved |

## Why the goal file is capped at 4,000 characters

That is the limit `/goal` enforces on the objective text. Both Claude Code and Codex
refuse longer input and tell you to *"put longer instructions in a file and refer to
that file in the goal"* — **the rider is that file**. Ceccarelli's corpus runs
3,929–4,112 characters; past ~4,100 means the goal is doing work that belongs in the
rider.

Check it with `mise run kb-goal-check`, **not `wc -c`**. The cap is stated in
*characters* and `wc -c` counts *bytes* — they disagree by the number of multi-byte
characters, and this convention's prose is full of em dashes. The first goal written
here measures 3,729 bytes but 3,703 characters, so `wc -c` would have you trimming a
goal that already fits. (`wc -m` counts characters and agrees with the checker.)

## The one constraint that shapes every goal written here

`/goal` is a session-scoped prompt-based Stop hook. After each turn the condition and
the conversation so far go to a small fast model (Haiku by default), which returns
`{ok, reason}`. From the official docs:

> It does not call tools, so it can only judge what Claude has already surfaced in the
> conversation.

So **every completion clause must be satisfiable by text visible in the main
transcript.** "The tests pass" is unjudgeable; "the transcript contains `PASS  gate
test rc=0`" is judgeable. Three consequences worth not rediscovering:

1. **Sentinels need a run-specific value.** Setting a goal starts a turn *with the
   condition itself as the directive*, so any literal string spelled out in the
   condition is already in the transcript at turn 0. Every sentinel here therefore ends
   with `@ <sha>` (the current short HEAD), which cannot be pre-satisfied.
2. **Subagent output is invisible** unless the main session restates it — the evaluator
   sees only the main conversation.
3. **On `ok: false` the evaluator's `reason` becomes Claude's next instruction.** So
   enumerate the clauses; a failing evaluation then names *which* one failed and
   becomes useful steering instead of "not yet".

## Writing a new pair

Structure the goal as: `GOAL:` line (opening **verb**, the current pain named with real
file paths, a single **headline word**) · **Read first** · **Preserve** · **Posture** ·
domain body · **Phases** · **Verification** · **Stop when**.

Two of those carry most of the weight:

- **Posture** — what this round will *not* do, mostly negations. *"An autonomous agent
  under pressure will invent solutions. Posture is the fence."*
- **Preserve** — the explicit change-everything-except list. Without it, an agent
  optimising the stated metric deletes the thing the round exists to protect: in
  Ceccarelli's worked example, a consistency pass eventually removes the banner,
  *because removing it improves the audit metric*.

**Pick one headline word.** If you cannot, the scope is too wide — split the round in
two.

Audit the result with `mise run kb-goal-check` (the mechanical half) and then against
the thirteen ambiguity tests in
`.claude/skills/goal-engineering/references/rubric.md` — tracked, unlike the
`.agent/kb/reports/**` research it was distilled from, which is gitignored and would
be a citation only this machine could open (T1 transcript-visibility · T2 literal-token ·
T3 stated-check · T4 Goodhart · T5 partial-completion · T6 floor-and-ceiling ·
T7 one-interpretation · T8 scope-fence · T9 one-round · T10 proxy-signal ·
T11 off-transcript · T12 stale-evidence · T13 stated-connective).

## See also

- `.claude/rules/probes-need-a-control-arm.md` — why every negative needs its arm.
- `.claude/rules/verify-before-advancing.md` — the gate matrix a Verification section
  should draw from.
- `.agent/plans/` — the session handoff a goal's round is drawn from (gitignored).
