# The goal+rider convention

## Naming

```text
docs/goals/<YYYY-MM-DD>-<HHMM>-<project>-<topic>-{goal,rider}.md
```

`<HHMM>` is local 24-hour authoring time, so `ls docs/goals/` sorts in true
authoring order rather than alphabetically by topic. **The pair shares one
timestamp** — split it across minutes and the sort breaks.

## The goal file is a payload, not a document

Its bytes are the exact text pasted after `/goal `. It carries no H1 and no
front matter, and `docs/goals/*-goal.md` is excluded from hk's markdown builtins
for that reason: a formatter that strips a trailing period off a heading would be
silently rewriting a live instruction to an agent.

Measure it with `mise run kb-goal-check`, **not `wc -c`**. The cap is stated in
characters; `wc -c` counts bytes, and this convention's prose is full of em
dashes. The first goal written here is 3,729 bytes but 3,703 characters.

## Goal skeleton

Fill each section; cut to fit 4,000 characters. Ceccarelli's corpus runs
3,929–4,112.

```markdown
GOAL: <opening VERB>. <current pain, named with real file paths and function
names — the agent grounds itself in HEAD, not in an abstraction>. Headline word:
<One>.

EVIDENCE RULE. The text of this condition is NOT evidence. Every line named
below counts only if it appears in a message Claude wrote AFTER this goal was
set, and only if the sentinel carries `@ <sha>`. Work done in a subagent,
workflow, or background task counts only when its output is pasted into THIS
conversation.

Read first. <the rider>, <the plan>, <the rules that bind this round>.

Preserve. Change anything except: <the explicit list>.

Posture. <mostly negations>. Stop after <N> turns.

<domain body — the decisions this round makes>

Phases. P1–P<n>, in the rider.

Verification. This conversation must contain, in Claude's own later messages:
1. `<SENTINEL> @ <sha>` — <what produced it>, output pasted.
2. ...

Stop when 1–<n> are present, OR Claude's most recent message is
`GOAL-BLOCKED: <blocker> — tried: <probe1>; <probe2> @ <sha>`.
```

**Trim priority when over budget**, in order: parenthetical detail already in the
rider → Read-first descriptions down to bare paths → Posture to one or two lines
→ verification bullets to the essential ones. Never trim the preserve list or the
turn bound; those are the two whose absence causes the expensive failures.

## Rider skeleton

No cap. Typically 2–35 KB. Roughly a dozen named sections:

- **Scope decision** — is this one round? What was split out, and why.
- **The evaluator constraint** — restate it; every later choice follows from it.
- **Preserve list** — the full version, with a table of what/where/why.
- **Posture** — the negations, expanded.
- **The question this round answers** — and the banned answers, if a theory has
  already been retracted.
- **Phases** — `### P1`…, each: depth test first → implement → gates green →
  one conventional commit. A phase that only produces a *finding* has no failing
  test to write first, and that is fine; say so rather than faking one.
- **Sentinel formats** — the exact strings, with the `@ <sha>` rule and why.
- **Verification** — the literal lines, with `file:line` for the code that prints
  each one. Source these from the code that PRINTS them, never from prose
  describing them; prose goes stale and the mismatch is silent.
- **Out of scope** — the overflow valve. Anything the round proves it should not
  do goes here rather than quietly expanding scope.
- **Hand-back** — decisions that are the user's, which the agent must never
  report as done.

The rider must name the goal it serves by path, so the pair is navigable from
either half.

## Where the strings come from

A condition naming a command that does not exist is worse than no condition. In
this repo, verified from the code that prints them:

| Signal | Literal | Source |
|---|---|---|
| review receipt, before any gate runs | `==> review: <n> lane(s): …` | `pr.py` `ship_main` |
| any gate under `kb-ship` | `PASS  gate <name> rc=0` — **two spaces** | `pr.py:82` |
| gates `kb-ship` runs | lint, test, brain-audit, eval | `pr.py:74` |
| new PR | `ship: OK — PR open, gates green` (em dash) | `pr.py:166` |
| merged | `land: OK — PR #N merged, main synced` | `pr.py:226` |
| eval | `OK eval: N passed, N skipped, 0 failed, 0 unarmed` | `evals.py:1163` |
| memory | `Saved to graphify-out/memory/<file>.md` | graphify `cli.py` |
| reflect | `Reflected N memories (...) -> ...LESSONS.md` | graphify `cli.py` |

**Three traps measured here.** `mise run test` runs pytest under `-qq`, so
`"N passed"` **never appears** — a condition requiring it is unsatisfiable
(control arm: bare `uv run pytest tests/` prints `578 passed`). And
`kb-currency-check` prints **nothing** on success, so silence is
indistinguishable from never-ran; require an echoed, file-recorded `rc`.

**And the newest one, which is the sharpest: `kb-ship` now REFUSES before it
runs a single gate** unless a `kb-review` receipt exists for the current HEAD.
So a condition asking for `PASS  gate lint rc=0` from `mise run kb-ship`, with
no instruction to review first, is **unsatisfiable** — ship stops at the receipt
check and those strings never appear. Any round that ships must say: run the
`kb-review` skill, write the receipt, then `kb-ship`.

Note what this class has in common. All three are unsatisfiable conditions whose
text looks completely reasonable, and none is detectable by reading the goal —
only by knowing what the command actually prints. That is why this table is
sourced from the code that PRINTS each string, and why it has to be re-checked
whenever the shipping path changes. It went stale the same evening the review
gate landed.

## Sources

- Greg Ceccarelli, *Goal Engineering: how I brief coding agents using paired
  goal+rider documents* (2026-05-18) — the goal+rider split, the headline word,
  posture, the preserve list, and the `dr-gate` critique of LLM-as-judge.
- Sabrina Ramonov, *6 INSANE Projects to Learn Claude Fable and /goal*
  (2026-07-11) — the 5-part TASK/WHY/OUTCOME/CONSTRAINTS/VERIFICATION template
  and the "something it can literally check" test.
- `code.claude.com/docs/en/goal.md` and `/hooks.md` — the evaluator's
  transcript-only limit, the 4,000-character cap, the turn clause, `{ok, reason}`
  and the fact that `reason` becomes Claude's next instruction.

Query them rather than trusting this summary:
`mise run kb-query -- "<question>" --prose --idf`.
