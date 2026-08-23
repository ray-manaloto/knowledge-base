# Refutation — finding 13 (lane: forgotten)

CLAIM: "10 of 12 'LOST' requirements the round's own cold-lane review found are
not named in any handoff OWED section, so /kb-resume's chain never surfaces them
again."

VERDICT: **REFUTED.**

## 1. The probe could only have returned "absent" for half the denominator

The offered probe grepped nine tokens:
`disable-model-invocation / skill-creator / writing-for-agents / ls-remote /
excalidraw / kb-extract.js / kb-tool-review.js / 'python code' / 20%`.

Mapped against the L1-L12 table (`docs/plans/2026-08-23-directive-execution-plan.md:1148-1197`):

| L | token in the probe's list? |
|---|---|
| L2 | yes (skill-creator, writing-for-agents) |
| L3 | yes (disable-model-invocation, 20%) |
| L5 | yes ('python code') |
| L6 | yes (kb-extract.js, kb-tool-review.js) |
| L7 | yes (ls-remote) |
| L12 | yes (excalidraw) |
| **L1** | **no token** (`codex/config.toml`) |
| **L4** | **no token** (`intermediate steps` / `agent memory`) |
| **L8** | **no token** (`all modes`) |
| **L9** | **no token** (`yuting0624`) |
| **L10** | **no token** (`orchestration`) |
| **L11** | **no token** (`telemetry`) |

Six of the twelve had no token at all, so the count "10 of 12" is arithmetically
unreachable from that probe: it can only ever have reported those six absent.

## 2. Four of the six untested items ARE present in the very files searched

Same command shape, zsh array, on the same three handoffs:

```
$ H=(.agent/plans/session-2026-08-23-{a,b,c}.md); grep -n -i -- "<t>" $H
all modes     -> session-2026-08-23-a.md:32   (Ray verbatim, L8)
yuting        -> a.md:46, a.md:48             (Ray verbatim, L9)
orchestration -> a.md:20, a.md:23, a.md:48    (Ray verbatim, L10)
telemetry     -> a.md:3, a.md:37, a.md:74     (Ray verbatim, L11)
```

CONTROL: with the finder's OWN nine tokens the same shape returns, in handoff a,
exactly one hit -- `ls-remote` at `a.md:72`, which is `git ls-remote --heads
origin` and a FALSE POSITIVE for L7 -- and 0 for the other eight; handoff b 0;
handoff c 2. So the probe discriminates, and the zeros above were spelling, not
absence.

REPORTING BOUND: the offered evidence names a result for handoff b and handoff c
only. Handoff a is in the stated command and has no reported result.

## 3. The causal conclusion is refuted by kb-resume's own source

`.claude/skills/kb-resume/SKILL.md:40-44`:

```
ls -t .agent/plans/session-*.md | head -3
ls -t docs/direction/*.md | head -2
```
"Read the **newest** of each ... **in full**. Not a skim."

The newest tracked directive is `docs/direction/2026-08-22-ray-directives.md`
(`ls -t` head; committed b47a5a81). It carries Ray's verbatim asks:

- `:184` L8 "refactor it take in arguments/parameters/hints so it can work properly in all modes"
- `:198` L9 "yuting0624/antigravity-for-claude-code should be ... in sync w the latest version"
- `:172`, `:175` L10 "/fable-orchestrator:orchestration"
- `:148`, `:189` L11 telemetry (6 hits total)

L1 is verbatim at `docs/direction/2026-08-21-ray-directives.md:133`
("finding the cause of what is writing to .codex/config.toml and adding claude
telemetry lines") -- tracked, and its writer-hunt report was promoted this round
(`docs/research/reports/2026-08-21-codex-config-writer.md`, handoff c:49).

So the handoff OWED section is not the only leg of "/kb-resume's chain"; the
tracked directive is a co-equal leg and it surfaces L8/L9/L10/L11.

## 4. At least three L items ARE named in a handoff OWED section

`.agent/plans/session-2026-08-23-c.md:51` = "## 5. OWED".

- `:53` -- "**#468** -- clear-prep: rewrite via `/skill-creator` +
  `/mattpocock-skills:writing-for-agents`, fix the thread-scope clause ..."
  = **L2** verbatim, and the "thread-scope clause" half is **L3**.
  `gh issue view 468` -> OPEN.
- `:58` -- "The remaining plan units: U1, U2, U3, U4, **U5**, U6 ... U11."
  U5 is the yuting0624 registration = **L9**; `gh issue view 446` -> OPEN.

Handoff b's OWED (`:49-54`) likewise points at the tracked plan by name (`:53`
"the other eleven units in the tracked plan"), with the path given at `:33`
(`docs/plans/2026-08-23-directive-execution-plan.md`). That file is TRACKED at
HEAD and the L1-L12 table is in it (`git show HEAD:... | grep -n "LOST -- said"`
-> `1148`).

## 5. L11 is not lost at all -- the plan discharges it

The LOST table's own L11 row ends "**Discharged below.**", and the section
"### L11 discharged -- the first actual telemetry measurements" follows with the
`.agent/telemetry/` aggregate (11,370 files / 3.2 GB; cache_read 1,203,758,976).
Counting a discharged item inside a "never surfaced again" denominator is a
category error.

Similarly L3's premise is refuted in handoff c GOTCHA 4 (`:66`): "`clear-prep`
was model-invocable all along. `disable-model-invocation: false` was already
set." The flag Ray asked to toggle was already in the requested state.

## 6. Contradiction with other live findings

- **Finding 17** ("U5 (#446): register yuting0624 ... is undone") reached L9 by
  reading the tracked plan -- demonstrating a live surfacing route for the item
  finding 13 says is unreachable.
- **Finding 16** (L1 "asked 2026-08-21 and restated as still-lost 2026-08-23")
  is only derivable because L1 is recorded verbatim in a tracked directive
  (`docs/direction/2026-08-21-ray-directives.md:133`) -- again a live route.
- **Finding 14** (L4 and L7 unanswered) is consistent and survives; those two are
  the residue that the corrected count leaves standing.

## Corrected figure

At most **5 of 12** (L4, L5, L6, L7, L12) lack a named surfacing route.
Seven (L1, L2, L3, L8, L9, L10, L11) have one: a handoff OWED bullet, an open
GitHub issue, or the tracked directive kb-resume reads in full.

## GitHub repos touched

_None._
