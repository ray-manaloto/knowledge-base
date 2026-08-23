# Refute lane: circles — "16 hand-rolled poll loops, 117.5 min, against gh-cli-watch.md"

Re-derived independently from the PRIMARY artifact
`/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/773421d1-632d-44fb-a680-8117295016ad.jsonl`
with my own parser (`$S/refute/mypairs.py`), not from the lane's `pairs.json`.
My parser also captures the tool_result timestamp, which the lane's did not.

## CONFIRMED exactly

- 499 Bash tool_use blocks now (the lane measured 492; indices 492-498 are the
  review round itself). Index numbering matches the lane's 1:1.
- `for i in $(seq` AND `sleep` -> 18 hits; minus indices 497,498 (post-report)
  = the lane's **16**, same index list.
- Sum of delta-to-next-call over those 16 = **117.51 min**. Lane said 117.5.
- Control arm re-run: `--watch` 0/499, `gh pr checks` 15/499, `gh run watch`
  0/499. The probe discriminates; the zero is real.
- `gh pr checks 386 --watch` in a NON-TTY: works, prints, terminates rc=0
  (control: same command without `--watch`, rc=0). So the native mechanism the
  lane says was available IS available here.
- CodeRabbit appears as a `pending` row inside `gh pr checks` output
  (idx 112/334 outputs), so `--watch` could genuinely have waited on it.

## REFUTED components

1. **"Eight waited on the agy cold lane's report file" is FIVE.**
   Only idx 69, 94, 273, 274, 408 poll `.agent/kb/review/reports/review-$SHA-cold.md`.
   Idx **19, 20, 21** poll a Workflow FAN-OUT JOURNAL, not any agy report:
   `D=.../subagents/workflows/wf_2249d7a7-223; for i in $(seq 1 11); do t=$(wc -l < $D/journal.jsonl); r=$(grep -c '"type":"result"' $D/journal.jsonl); ... sleep 45; done`
   Different waited-on object, different native answer.

2. **"Eleven of the sixteen took 495-614 s each" mixes two metrics.**
   By delta-to-next-call (the metric that produced the 117.5) it is **twelve**
   in [495,614]. By actual command duration (tool_result ts - tool_use ts) it is
   eleven, but the range is then **488.4-600.2 s**, not 495-614. `614` is a dt
   value (613.8, idx 459) and `495` is a dur value (495.7, idx 19).

3. **The cited rule does not govern half the loops.** `.claude/rules/gh-cli-watch.md`
   scopes itself to gh: *"When waiting on a GitHub PR's checks or a workflow run
   via the `gh` CLI, use the built-in `--watch` flags"*, Applies-to: *"When `gh`
   documentation lists a `--watch` flag for any subcommand ... use it."*
   Only 8 of the 16 are gh waits. For the other 8 (file/journal waits) the same
   rule sends you to `Monitor` (case 2: "non-GitHub system with no built-in watch
   flag"), and `.claude/rules/long-running-command-hangs.md` rule 2 explicitly
   PRESCRIBES the shape used: *"run it in the background and monitor its log with
   a count-diff loop rather than a fixed sleep"* + *"Poll in successive calls
   instead of one long one."* Idx 17/19/20/21 are literally count-diff loops
   (`wc -l` / `grep -c`) in successive sub-600 s calls.
   So "sized to just under the ~600 s Bash cap" is compliance with rule 2, not
   evidence of the violation.

## UNDERCOUNT (cuts the lane's way, not mine)

- **idx 17** is a 17th hand-rolled poll loop the AND-filter missed by spelling:
  `for i in 1 2 3 4 5 6 7 8 9 10; do ... sleep 45; done` (dt 458.4 s).
- **idx 363** is `sleep 120; gh pr checks 375 ...` - a blind fixed wait, the
  exact anti-pattern gh-cli-watch.md lists ("fixed-time wait, never reflects
  actual completion").
- Cross-check for other spellings: `while`+`sleep` = 0, `until`+`sleep` = 0,
  `for x in {a..b}` = 0. `sleep ` = 20 total, 18 in the AND set, the 2 extras
  are idx 17 and 363.

## Contradiction with another live finding

None of findings 1-16 contradicts this one. Finding 3 (the PR-bot sweep) is
about the same PR-wait region of the transcript and is consistent: idx 422
polls `gh pr checks` AND `gh api .../reviews` in the same loop, which is a shape
`--watch` alone cannot express.

## Internal inconsistency in the lane's own report

`circles.md` line 28 cost table says the poll-loop family is **18 calls /
127.4 min**; CIRCLE 3 says **16 / 117.5 min**. The table's `cost.py` predicate is
an **OR** (`"for i in $(seq" in c or "sleep " in c`) while CIRCLE 3 is an AND -
not an error, but the two numbers are printed 100 lines apart with no note.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) - the repo under review; `gh pr checks` probes against PR #386.

## Live confirmation of bot-review finding #13, from this very prompt

My "EVERY OTHER LIVE FINDING" list contains the finding I am judging, verbatim,
as item **4**. That is exactly the graphify-labs defect recorded as live finding
#13 ("`otherClaims` ... reused verbatim for every refuter without excluding the
finding under judgment"). Fresh evidence, this run.

## VERDICT: refuted = true (partially — the cost figure survives, three stated facts do not)

- 16 loops / 117.51 min: REPRODUCED EXACTLY. Not refuted.
- "Eight waited on the agy cold lane's report file": REFUTED -> five.
- "Eleven of the sixteen took 495-614 s each": REFUTED as stated -> twelve by
  the report's own dt metric; eleven only by a different metric whose range is
  488.4-600.2 s.
- "against a repo rule that says never hand-roll one": REFUTED for 8 of 16 -
  gh-cli-watch.md scopes itself to gh waits, and long-running-command-hangs.md
  rule 2 prescribes "a count-diff loop" + "poll in successive calls" for the
  local ones, which is the shape actually used.
