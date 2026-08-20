---
type: "query"
date: "2026-08-20T15:22:50.691448+00:00"
question: "What did fixing #397 (kb-build FAILS) establish, and what did the two cold review rounds cost?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did fixing #397 (kb-build FAILS) establish, and what did the two cold review rounds cost?

## Answer

# #397 — what the round established

## The stated blocker was real and small; the surrounding drift was not

`mise run kb-build` failed detect preflight on three `anthropic-sdk-python`
files. Two `.keep` placeholders joined `_NON_SOURCE_NAMES`; `Brewfile` joined the
COUNTED `_UNSUPPORTED_LANGUAGE_NAMES` (Ruby that `brew bundle` executes).

Both `.keep` files carry 239 and 224 bytes of Stainless prose, so the obvious
fix — an emptiness or size check — would have walked straight past them. The
class is about what a file is FOR, not how many bytes it holds.

Full census over 73 sources afterwards: `unclassified-files` gone from
`category_counts` entirely; absorbed loss now visible as a tally of 6,564 files.

## A version bump left drift in the code that reads the tool's output

graphify 0.9.47 reworded its partial-extraction warning: the trailing `(#2551)`
removed (their #2788 — the reference sent readers of every other language to a
closed Kotlin issue), a recovered-symbol count added, and `first error at line N`
degrading to a bare `syntax error`. Our matcher still expected the 0.9.45 text,
so the reviewed approval expired CLOSED and blocked the build.

Two lessons. Read the emitter, not one observed line: two of the three changes
are invisible in a single sample. And the test fixture pinned the old wording, so
the suite agreed with itself while the real build failed — a fixture is a claim
about what a tool emits, and it ages with the tool.

## Both P1s in the review were defects IN A FIX, in opposite directions

Round 1 P1: the new failure record was consulted only when the stamp was ABSENT.
But `graph.build` runs detect preflight BEFORE `_clear_stamp`, so a preflight
refusal — the exact failure #397 was filed from — aborts with the old stamp on
disk. Any machine that had ever built successfully reported OK for a broken
build. That is #397 itself, reintroduced inside the fix for it.

Round 2 P1: the round-1 fix made the record outrank the stamp, so a `clear()`
that failed left a SUCCESSFUL build reporting a DEFECT forever. Round 1 fixed
"OK for a broken build" and shipped "broken for a working build".

The durable fix was to SELF-HEAL rather than clear harder: supersede the record
when the stamp's own `built_at` is newer. Strictly, so ambiguity keeps REPORTING
the failure — the two errors are not symmetric.

## My own probe said the fix was broken, and the probe was wrong

The first end-to-end probe of the supersession fix compressed the failure and the
successful build into one second. `built_at` is written with `timespec="seconds"`
and truncates DOWN, so supersession needs ~1s of real separation. Re-probed with
realistic separation it self-heals. The condition is now pinned by a test rather
than left as folklore.

## Three probes were caught rather than believed

- `kb-arms --dry-run` found FIVE anchors moved by a restructure, twice.
- R4 came back PROBE BROKEN: the mutation unbalanced a `print(` call, so the
  module stopped importing and the red suite did not name R4's own test.
- S7 SURVIVED and was an INERT MUTANT — `>` vs `>=` cannot differ when one side
  truncates to seconds and the other keeps microseconds.

## `--ephemeral` invalidates this repo's tell for a substituted review lane

The recorded tell is "batch 3 left no codex JSONL". `codex exec --ephemeral`
means "run without persisting session files to disk", so an HONEST ephemeral run
leaves no rollout and trips that tell. The lane first explained the absence by
claiming codex 0.148.0 uses sqlite instead of JSONL — false: 27 rollouts existed
from that day, 3,187 in total. True conclusion, wrong mechanism. The durable
evidence for an ephemeral run is the live process plus its `-o` file.

## Criterion 2 remains open, deliberately

`kb-build` now clears the preflight and fails later on GitNexus: 79 zero-node and
15 partially-extracted files against a committed inventory of 12 and 1, and it is
the 3rd of 70 code sources. GitNexus is `scope = study`. Ray re-scoped the corpus
run to the graphify clone, so this was filed (#409) rather than pursued. #408
covers `kb-detect-census`'s false `pin-unreachable`.


## Outcome

- Signal: useful