# refute-circles — the kb-review receipt "copied forward / blocking never fired" finding

Judging: "The kb-review receipt ... is copied forward across fix-rounds and its numbers
describe a different review. Three receipts written this session are byte-identical except
sha/written_at, and two of them assert lanes_ran ["cold:antigravity"] for commits where no
lane ran. Separately, blocking is 0 in 66 of 66 receipts on disk, so the only check that can
fail a receipt has never once fired."

## Probe 1 — reproduce the receipt comparison (CONFIRMS the literal byte fact)
`cat .agent/kb/review/receipt-{85201adb...,d85f2835...,f0659e51...}.json`
All three: lanes_ran ["cold:antigravity"], lanes_skipped same 3, findings 7, blocking 0,
fixed_point origin/main, fixed_point_sha 5dabbc59da9e. Differ only in sha/written_at. TRUE.

## Probe 2 — do the lane REPORTS exist and differ? (REFUTES "no evidence")
`ls -la .agent/kb/review/reports/review-{85201adb,d85f2835,f0659e51}*-cold.md; md5; wc -l`
  1226 B / 21:31 / md5 8121e2cc... / 14 lines
  2608 B / 22:10 / md5 595161b4... / 31 lines
  3746 B / 22:22 / md5 234df5d2... / 48 lines
THREE DISTINCT reports, three distinct mtimes. Not copied forward.
Each one states, verbatim in its own body: "No lane re-ran against <sha>." and then names the
exact delta and the verification run at that SHA. The thing the finding presents as a hidden
overclaim is SELF-DISCLOSED in the artifact the gate requires beside the receipt.
Each also states: "Review totals across the two rounds: 7 findings (2 + 5) ... 0 blocking" —
so `findings: 7` is documented as the ROUND's cumulative total, not a per-SHA fresh count.

## Probe 3 — is `blocking` "the only check that can fail a receipt"? (REFUTES)
`grep -n "_CHECKS" python/src/kb_setup/review.py` -> line 829:
  _CHECKS = (_check_identity, _check_range, _check_lanes, _check_blocking)
FOUR checks, not one. Plus `_base_coverage_gap` in receipt_state outside _all_reasons.

## Probe 4 — THE KILLER: the "66 of 66" survey is a one-face coin
A receipt with `blocking > 0` is NEVER WRITTEN. `cli.py:696-703`:
    # Validated BEFORE the write. Writing first and reporting REJECTED after
    # would leave an invalid receipt on disk for this SHA ...
    reason = review.rejection(repo_root, receipt)
    if reason is not None:
        print(f"review-receipt: REFUSED — {reason}", file=sys.stderr)
        return 2
And `.claude/skills/kb-review/SKILL.md:345` states it verbatim:
  "**A `--blocking` greater than 0 is refused before anything is written**, so the
   command exits 2 and `kb-ship` then refuses for *no receipt*."
So `grep '"blocking": *[0-9-]*' receipt-*.json` can ONLY ever return 0. It is a
survivorship bound, not a measurement of the check.

## Probe 5 — CONTROL ARM: does _check_blocking discriminate? YES
  uv run python -c "... review._check_blocking(payload, sha) ..."
  blocking=0    -> None
  blocking=1    -> '1 blocking review finding(s) — resolve them or re-review'
  blocking=7    -> '7 blocking review finding(s) — resolve them or re-review'
  blocking=-1   -> 'has a negative blocking count (-1) — that is malformed, not zero'
  blocking=None -> 'has no readable blocking count'
  blocking=True -> 'has no readable blocking count'
  blocking='0'  -> 'has no readable blocking count'

## Probe 6 — has the receipt gate EVER fired in real runs? YES, repeatedly
  grep -ho 'review-receipt: REFUSED[^"\\]*' ~/.claude/projects/<this repo>/*.jsonl | sort | uniq -c
  4x "records an EMPTY comparison range (fixed_point_sha == sha)"   (_check_range)
  2x "names unknown lane(s): placeholder"                            (_check_lanes)
  8x "lane(s) unaccounted for: ..."                                  (_check_lanes)
 12x "claims lane(s) cold ran, but no non-empty report is at ..."    (_check_lanes)
  4x "left a report that never names c33990f8880d / 4c0ed9603f16"    (#56 SHA binding)
Control: 346 `review-receipt: OK` lines, so the transcript grep discriminates.
=> "the ONLY check that can fail a receipt" is false: _CHECKS has FOUR members
(review.py:829) and three of the other kind have demonstrably refused real writes.
Every "blocking review finding" hit in the transcripts is SOURCE/TEST text, never
gate output — consistent with the write-refusal design, not with a dead check.

## Probe 7 — is "copied forward" true? NO, the skill MANDATES this shape
SKILL.md:197-211 prescribes the fix-round report at the new SHA with the literal
line "No lane re-ran against <fixed-sha>", and SKILL.md:209 says "**Do not copy
the round-2 report to the new name.**" All three reports follow the template and
are distinct files. `findings` is documented in each report as the ROUND total
("7 findings (2 + 5)") and is NOT GATED — cli.py:637-638: "`--findings` does
default: it is reported, not gated". The "2 items" the f0659e51 round found were
CODERABBIT bot findings, not kb-review lane findings; the receipt's `findings`
counts lane findings.

## VERDICT: REFUTED
