# #181 + #182 — the cold review, both rounds, verbatim

Promoted from `.agent/kb/review/reports/` because PR
[#185](https://github.com/ray-manaloto/knowledge-base/pull/185)'s body cites
these filenames, and `.agent/` is gitignored — a citation only one machine can
open is not a citation.

Lane: `cold:codex` (GPT-5.6 Sol, read-only sandbox), cross-family against a
Claude-written diff. Two rounds, the `kb-review` bound. **5 findings, 0
blocking.** Both rounds exceeded codex's ~1,500-line single-shot guard and ran in
batches; every file in scope was covered.

| file | SHA | outcome |
|---|---|---|
| `review-8c574c57f954419c55ea1852cbafc78df14a4510-cold.md` | round 1 | 2 findings, both P2 |
| `review-532d25606934728a4c96a4b47dd6319b684992f2-cold.md` | round 2 | 3 findings — 1 **P1**, 2 P2 |
| `review-bdf6e8adf1911b3b6ea46c9850d4392f2cdd1832-cold.md` | fix round | no lane re-ran; records what verified the fixes |

## Why these are worth keeping past the round

**Two of the five findings were defects in the fixes for earlier findings.**

- Round 1 found a genuine **false pass**: after a silently-failed best-effort
  restamp, a following `kb-merge` certified all three derived views against a
  graph they predate, and `check_views` returned OK. Reproduced end to end before
  it was accepted.
- Round 2's **P1** was an inversion of a docstring added by round 1's own fix.
  `_gate_sync` says *"silence on this path is consent"* and was wired for `STALE`
  only — via a tuple that is empty for every `NOT_VERIFIABLE` verdict, so a views
  check that verified nothing reached gate 6 looking clean.

Both hid for one reason the lane named explicitly: `tests/test_currency_run.py`
stubs `_run_one`, so nothing exercised the wiring end to end. That is the durable
finding — a module unit-tested in isolation with its integration point stubbed
has a blind spot exactly where the two layers meet.

## The one finding NOT fixed

Round 2's third P2: an **inter-process race**. The `snapshot_views` bracket bounds
one process, not the file, and nothing in `kb_setup` locks (the lane's own
`grep -rnE "FileLock|flock|fcntl"` returns nothing). Accepted, documented in
`sync.view_records`' docstring, and left tracked rather than fixed — a lock is a
separate change with its own failure modes.

## Also recorded here

Round 1 carried a sub-claim its transporting agent could **not** confirm (that a
byte-identical regeneration retains stale provenance). It is labelled unverified
in that report rather than dropped, per the receipt rules.

Round 2 **downgraded** one of its own lane's findings on spot-check: the
`codex@openai-codex` plugin's marketplace is absent from `extraKnownMarketplaces`,
which is true, pre-existing, shared by four already-committed plugins, and
documented in `.claude/CLAUDE.md`.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the tool
  whose stamp, `label` and artifact behaviour the reviewed change is about.
