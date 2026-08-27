---
type: "query"
date: "2026-08-27T04:36:40.243777+00:00"
question: "Does kb-remember make the corpus smarter, as the ingestion doctrine claims?"
contributor: "graphify"
outcome: "corrected"
correction: "# The belief that was wrong: `kb-remember` makes the corpus smarter\n\nEvery version of this repo's ingestion doctrine says the loop closes with\n`kb-remember` + `kb-reflect`, \"so the corpus gets smarter every ingestion\". The\n`kb-curator` MANDATE says it, `clear-prep` step 2 says it, and `CLAUDE.md` says\nit.\n\n**Measured 2026-08-26, and it is not true today:**\n\n    graphify-out/memory/                             271 committed files\n    graph-prose.json nodes                           4,868\n    prose nodes sourced from graphify-out/memory/        0\n\nThe 34 nodes whose `source_file` matches \"memory\" all come from\n`claude-code-memory-plan.md`, an ingested DOC. **None come from the work-memory\nstore.** So `kb-remember` writes durably and nothing reads back: it is an\narchive, not a retrieval surface.\n\n`#212` is the same defect one layer up and has been open since before this round\n— *\"LESSONS.md is gitignored: the self-improving loop's only durable output\nnever reaches a consumer or a fresh clone.\"* Both halves of the circuit are open.\nFiled the raw-memory half as `#540`.\n\n## Why this was believed for so long\n\nBecause the WRITE half works perfectly. `kb-remember` succeeds, the file lands,\nthe commit includes it, and the next `kb-reflect` aggregates it. Every\nobservable in the loop is green. Nothing in the loop ever asks the question the\nloop exists to answer — *can anyone get this fact back out?* — so the absence is\ninvisible from inside it.\n\nThat is this repo's own recurring finding wearing new clothes: a validator\nnothing calls is not a gate, and a write path with no read path is not a memory.\n\n## What to do with it\n\n1. **Do not point `MEMORY.md` at `graphify-out/memory/`** until `#540` closes.\n   The auto-memory index genuinely cannot hold 339 topic files inside its ~17 KB\n   target, and moving the tail into the graph is the right architecture — but\n   pointing at an unqueryable store trades a VISIBLE leak (64 orphaned files,\n   findable by grep) for an invisible one.\n2. **The acceptance test is a control-armed query**, not a successful write: a\n   `kb-query` for a fact recorded via `kb-remember` returns it, AND the same\n   query shape returns nothing for a fact never recorded.\n3. **Suspect the same shape elsewhere.** Any loop in this repo whose success\n   criterion is \"the artifact was written\" should be asked whether anything\n   reads it. `#212` and `#540` were found this way, one after the other.\n"
---

# Q: Does kb-remember make the corpus smarter, as the ingestion doctrine claims?

## Answer

# The 2026-08-26 funnel round — what it asked and what it found

## The question

This repo exists so that research it does becomes corpus other sessions can
query. Five clauses describe that purpose and none had a mechanism. The round
before this one convened to fix the funnel and did not funnel its own research:
33 files added under `docs/research/**` and `docs/artifacts/**`, and **zero
lines** under `sources/`.

The round asked: can that clause be given teeth, and can this branch's own debt
be paid?

## What was built

**A ship gate, `kb-funnel`.** A branch that adds or edits anything under
`docs/research/**` or `docs/artifacts/**` with no added or edited file under
`sources/**` and no `Funnel-exempt: <reason>` commit trailer now FAILS the ship.
Five distinct states, not two — `clean`, `funnelled`, `exempt`, `drift`, and
`no_base` (rc 127) so that "we could not check" can never render as green.

It was landed BEFORE the data it demands, deliberately, so its FAIL direction
was proven on real data rather than on a fixture: `DRIFT`, 33 docs files, 0
sources files, rc 1. The funnel data then flipped it to `FUNNELLED`, rc 0.

**The funnel itself.** 38 registry rows (114-151) recording every tool the
2026-08-26 survey judged, verdicts quoted verbatim rather than paraphrased, plus
eight pinned manifests for the live repos among them. Status `manifest`, never
`code`: `kb-build` is failing, so pinning is not extracting, and a registry that
claimed otherwise would be worse than a shorter one.

## What it cost, honestly

Two cold review rounds found 30 findings. **Three of the defects in round 2 were
introduced by round 1's own fixes**, including one BLOCKING: a test repaired so
that it computed its expectation from the same function it was testing, making
it unable to fail. Unwiring the guard from the hook entirely left it green.

## Numbers, all measured this session

| | |
|---|---|
| gate states, distinct | 5 |
| registry rows appended | 38 (114-151) |
| manifests pinned | 8 |
| tools in the survey | 45 distinct, across 38 report rows |
| already funnelled before this round | 2 manifests, 1 registry row |
| review findings | 19 (round 1) + 11 (round 2) |
| defects introduced BY round 1's fixes | 3, one of them BLOCKING |
| ship gates green at `125af27c` | 7 of 7 |


## Outcome

- Signal: corrected
- Correction: # The belief that was wrong: `kb-remember` makes the corpus smarter

Every version of this repo's ingestion doctrine says the loop closes with
`kb-remember` + `kb-reflect`, "so the corpus gets smarter every ingestion". The
`kb-curator` MANDATE says it, `clear-prep` step 2 says it, and `CLAUDE.md` says
it.

**Measured 2026-08-26, and it is not true today:**

    graphify-out/memory/                             271 committed files
    graph-prose.json nodes                           4,868
    prose nodes sourced from graphify-out/memory/        0

The 34 nodes whose `source_file` matches "memory" all come from
`claude-code-memory-plan.md`, an ingested DOC. **None come from the work-memory
store.** So `kb-remember` writes durably and nothing reads back: it is an
archive, not a retrieval surface.

`#212` is the same defect one layer up and has been open since before this round
— *"LESSONS.md is gitignored: the self-improving loop's only durable output
never reaches a consumer or a fresh clone."* Both halves of the circuit are open.
Filed the raw-memory half as `#540`.

## Why this was believed for so long

Because the WRITE half works perfectly. `kb-remember` succeeds, the file lands,
the commit includes it, and the next `kb-reflect` aggregates it. Every
observable in the loop is green. Nothing in the loop ever asks the question the
loop exists to answer — *can anyone get this fact back out?* — so the absence is
invisible from inside it.

That is this repo's own recurring finding wearing new clothes: a validator
nothing calls is not a gate, and a write path with no read path is not a memory.

## What to do with it

1. **Do not point `MEMORY.md` at `graphify-out/memory/`** until `#540` closes.
   The auto-memory index genuinely cannot hold 339 topic files inside its ~17 KB
   target, and moving the tail into the graph is the right architecture — but
   pointing at an unqueryable store trades a VISIBLE leak (64 orphaned files,
   findable by grep) for an invisible one.
2. **The acceptance test is a control-armed query**, not a successful write: a
   `kb-query` for a fact recorded via `kb-remember` returns it, AND the same
   query shape returns nothing for a fact never recorded.
3. **Suspect the same shape elsewhere.** Any loop in this repo whose success
   criterion is "the artifact was written" should be asked whether anything
   reads it. `#212` and `#540` were found this way, one after the other.
