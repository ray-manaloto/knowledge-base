---
type: "query"
date: "2026-08-18T02:00:05.369527+00:00"
question: "What did the cold review of PR #336 find, and what could it not reach?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the cold review of PR #336 find, and what could it not reach?

## Answer

# The cold review round: what it found, and what it could not reach

`kb-review` round 1 on PR #336, cold cross-family (codex), against 4,712 lines.

## Its most severe finding was in the round's own new code

**A run stopped by the $100 cumulative spend cap could exit 0.**
`RunSummary.halted` was populated and never read — the completeness gate checked
`completed`, `repaid`, `chunk_total` and `failed`, so a cap trip right after the
LAST chunk satisfied every count. Verified before fixing: `.halted` had **zero
references** in `graphify_semantic_corpus.py`.

The comment I had written called `halted` *"the only thing that tells a reader
the counts are a partial accounting"* — and then let the reader be a human while
the machine gate ignored it. **A disclosure no gate consults is a comment.**

The fix that mattered was structural, not the three-line check:
`_execute_authorized` spends real money to obtain a summary, so **no test could
ever reach the decision**. Extracting `completeness_rc` is what made it armable.
A judgement wrapped inside an expensive side effect is unreviewable by
construction.

## Three tests that could not fail, in ONE round

Every one was invisible to reading and caught only by `mise run kb-arms`:

1. **C4** — the spend-rotation helper named records
   `provider-spend-{pid}-{index}-{amount}.json` with a per-call `enumerate`
   index, so two calls writing the same amount produced the SAME filename and the
   second overwrote the first. The double-charge the mutation introduces had
   nothing to double.
2. **D2** — the credential test called `_sdk_caller(...)` and then asserted on a
   client it constructed itself, so it verified the Anthropic SDK (never in
   doubt) and said nothing about the module. Fixed by extracting `sdk_client`,
   which was also the fix for a type error the reflection workaround caused —
   the cleaner design and the typeable one were the same design.
3. A corrupt-snapshot control arm **could not reach its own control**, because
   `write_snapshot` called `read_snapshot`. That surfaced a sixth defect the
   REVIEWER never found: **a corrupt snapshot made `--write` fail, so the one
   command that repairs it was the one command it prevented.**

In all three the FIX was correct and the TEST was decoration.

## Two findings answered rather than obeyed

- **`graph-size` passing on an absent graph.** True, and only harmless when the
  absence means the work never happened. Split: `unbuilt` (nothing ever built
  here) stays rc 0 because failing would make a fresh clone unshippable;
  `missing` (the build stamp says this machine HAS built) is `Rc.NOT_RUN`.
- **Telemetry pruning at SessionStart does not bound a long session.** Correct,
  and SessionEnd is unavailable (shared 60 s budget). Stated as a measured limit
  — ~1.17 MB/request, ~95.7 MB per round, so 2 GiB is ~20 rounds — rather than
  implied away. **The ceiling bounds the DIRECTORY, not any one session.**

## What the review could NOT reach, and why that is the durable lesson

Codex hit its **account usage limit** mid-run after a 600 s watchdog kill, so
**9 modules got no pass at all**. The lane reported this itself and named them —
which is the only reason it is recorded rather than invisible.

A lane killed or exhausted mid-review looks exactly like one that finished:
same report shape, same finding count. `kb-review`'s own guidance warns that
*read-but-unanalysed* is harder to detect than *never-opened*, because the
transcript shows the file. **Ask a lane to declare its coverage, and treat a
finding count as meaningless without it.**

## Consequences nobody predicted

- **`gitleaks dir` reads the telemetry sink.** Enabling raw-body capture put
  **86 findings and ~500 MB (17.7 s)** into every lint run, because gitleaks
  walks directories rather than tracked files. Allowlisting `.agent/telemetry/**`
  took it to 34 MB / 1.07 s. Capturing whole conversations to disk means a secret
  scanner pointed at the repo starts reading the conversation.
- **The plan was re-planned FIVE times.** A currency review and a review round
  are both code changes here. The order that works:
  **review → fix → re-plan → re-record.**
- **`kb-ship` refused once**, correctly: the previous handoff marked
  `.agent/telemetry/` `(absent)` and this round created it. The absence marker is
  checked BOTH ways, so a path claimed missing that now resolves is a broken
  citation.


## Outcome

- Signal: useful