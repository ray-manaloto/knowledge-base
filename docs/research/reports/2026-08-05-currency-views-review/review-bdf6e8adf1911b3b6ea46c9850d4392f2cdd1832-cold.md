# Fix-round record — bdf6e8adf1911b3b6ea46c9850d4392f2cdd1832

**No lane re-ran against `bdf6e8adf1911b3b6ea46c9850d4392f2cdd1832`.** This file
exists because a receipt is always keyed to HEAD, and committing round 2's fixes
moved HEAD past the SHA its report is named for. It is deliberately NOT a copy of
that report — asserting a lane read bytes it never saw is the gap-wearing-a-
reason's-clothes shape the receipt gate exists to refuse.

## What was reviewed, by whom, and where

| round | SHA | lane | outcome |
|---|---|---|---|
| 1 | `8c574c57f954419c55ea1852cbafc78df14a4510` | `cold:codex` (GPT-5.6 Sol, read-only, 3 batches) | 2 findings, both P2 |
| 2 | `532d25606934728a4c96a4b47dd6319b684992f2` | `cold:codex` (GPT-5.6 Sol, read-only, 2 batches) | 3 findings — 1 P1, 2 P2 |

Full reports: `review-8c574c57f954419c55ea1852cbafc78df14a4510-cold.md`,
`review-532d25606934728a4c96a4b47dd6319b684992f2-cold.md`. Both name their own
commit in the body. The two-round bound is spent (`kb-review` SKILL.md step 4).

## What changed after round 2, and how it was verified

`bdf6e8a` fixes round 2's P1 and first P2, and documents the third. Verification
is the local gates plus a mutation arm, which is what the skill's fix-round path
prescribes when the round bound is spent:

    mise run kb-gates @ bdf6e8adf191
      lint         PASS
      test         PASS
      brain-audit  PASS
      eval         PASS
      4 passed, 0 failed, clean tree
      -> .agent/kb/gates/gates-bdf6e8adf1911b3b6ea46c9850d4392f2cdd1832.json

Mutation arm on the P1 fix — replacing the new `NOT_VERIFIABLE` branch in
`decide._gate_sync` with `if False:` kills exactly
`test_gate_six_blocks_an_auto_apply_on_views_it_could_not_verify` and nothing
else; restoring it returns the file green. Run with `__pycache__` cleared and
`PYTHONDONTWRITEBYTECODE=1`.

## Disposition of every finding across both rounds

| round | sev | finding | disposition |
|---|---|---|---|
| 1 | P2 | view provenance misattributed after a silently-failed restamp | **FIXED** in `203ed91` — reproduced first, then closed by bracketing each operation with `stamps.snapshot_views`. Three arms: the defect, the bootstrap, and the label case. |
| 1 | P2 | views verdict reached neither `run --json` nor `apply()`'s gate 6 | **FIXED** in `203ed91`; round 2 then found both halves incomplete (below). |
| 2 | **P1** | gate 6 blind to `NOT_VERIFIABLE` — only `STALE` was wired | **FIXED** in `bdf6e8a`. `_gate_sync` takes the whole `ViewStatus`. |
| 2 | P2 | `_run_one` dropped the computed status; `--json` always said `skip` | **FIXED** in `bdf6e8a`. |
| 2 | P2 | inter-process race — no locking anywhere in `kb_setup` | **ACCEPTED, DOCUMENTED, TRACKED.** Recorded in `sync.view_records`' docstring with the reviewer's own `grep` as evidence. Not fixed here: a lock is a separate change with its own failure modes. |
| 2 | — | `.claude/settings.json` codex plugin not in `extraKnownMarketplaces` | **DOWNGRADED BY THE LANE ITSELF** — four already-committed plugins share the property and `.claude/CLAUDE.md` documents the convention. Not introduced by this diff. |
| 2 | — | stale stub kwarg `regenerated_views` in `test_artifacts.py` | **FIXED** in `bdf6e8a` — renamed to `views_before`, now asserting it is `None`. |

## Round 1's unverified sub-claim, carried forward rather than dropped

The round-1 lane reported, and its transporting agent could **not** independently
confirm, that "a byte-identical regeneration retains stale provenance".
`deep_artifact_fingerprint` is mtime-based rather than content-based, so a real
regeneration moves the identity regardless of content. Labelled unverified in that
report and neither acted on nor discarded here.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the tool
  whose stamp, artifacts and label behaviour this whole change is about.
