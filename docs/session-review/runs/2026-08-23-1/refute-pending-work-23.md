# Refute lane — finding 23 (pending-work): "already flagged 2026-08-18, nothing cleaned up"

CLAIM: Same worktree/branch inventory was already flagged by a pending-work lane on
2026-08-18 (docs/session-review/runs/2026-08-18-1/pending-work.md, committed on
origin/main) and nothing has been cleaned up in the 5 days / one landed round since.

## Probe 1 — the cited artifact exists on origin/main
    git show origin/main:docs/session-review/runs/2026-08-18-1/pending-work.md
  -> full report, 4 worktrees, 24 local branches, 2 stashes, ahead/behind table.
CONTROL: same command, NO-SUCH-FILE.md -> "fatal: path ... does not exist in 'origin/main'".
Probe discriminates.

## Probe 2 — current inventory vs the 08-18 table
worktrees: IDENTICAL 4 (knowledge-base-299 3018dff3 / -300 4cd58d0a / -301 8ace6198 /
  -graphify-0942 5eda1525) — same SHAs.
stash: IDENTICAL 2 (stash@{0} codex/graphify-0942 WIP 2026-08-13; stash@{1} main WIP).
ahead-counts: IDENTICAL for every branch present in both lists (e.g. 08-08g2 0,
  09b 1, session-work-memory 1, skills-1.2.2-sync 2, gh-stack-skill 1,
  fix-328 2, doppler-critical-kb 3, stash-0/1 3 each).
behind-counts MOVED (33->47 etc.) because origin/main advanced 14 commits.
branch SET is not byte-identical: docs-directive-addendum (the 08-18 session branch)
  is gone — it landed as PR #347 — and claude-resync-2.1.241 + close-2026-08-20-round
  were added. 24 -> 25 branches.

## Probe 3 — the two QUANTIFIERS in the claim are both wrong
    git log -1 --format='%H %ad' -- docs/session-review/runs/2026-08-18-1/pending-work.md
    dcd0b07f 2026-08-18 17:13:34 -0500  (PR #347)
Today is 2026-08-22 -> FOUR days, not five.
    git log origin/main --since=2026-08-18 --oneline | wc -l  -> 13
Thirteen squash-merged PRs landed after it: #375 #385 #386 #392 #398 #402 #406 #410
 #422 #439 #453 #459 #463 — not "one landed round".

## VERDICT: NOT REFUTED on substance; the two figures are wrong and UNDERSTATE it.

## Probe 4 — the flag WAS actioned once (a ticket), never executed
    gh issue view 368 --json ... -> {"number":368,"state":"OPEN",
      "createdAt":"2026-08-18T21:03:40Z","updatedAt":"2026-08-18T21:03:40Z","ncomments":0}
#368 "Pending-work audit: gh-stack-skill and two memory docs are genuinely unmerged..."
filed 3h after the 08-18 report, zero comments, untouched for 4 days.
So "nothing has been cleaned up" is TRUE of the worktrees/branches/stashes; the
finding omits that a tracking ticket exists and is itself untouched.

## Probe 5 — contradiction with finding 28 in this same set
    git show origin/main:.../pending-work.md | grep -c 'close-2026-08-20-round' -> 0
    CONTROL: same pipe, grep -c 'salvage/stash-1' -> 4
    git log -1 --date=iso close-2026-08-20-round -> 44093387 2026-08-20 04:47:58
Finding 28 dispositions close-2026-08-20-round, a branch created 2026-08-20 and
therefore NOT in the 08-18 inventory. So "same inventory ... already flagged" is
overstated: at least one branch in this round's inventory was never flagged then.

## Probe 6 — graph query (mandated step 0), no bearing
    mise run kb-query -- "pending work worktrees branches cleanup audit" --prose --idf
  -> top 20 hits all third-party corpus (graph engineering posts, claude docs).
  The corpus does not hold this repo's own branch state; not evidence either way.

## FINAL
Core NOT REFUTED (4 worktrees, 2 stashes, 22 branches, ahead-counts all identical).
REFUTED as stated: "5 days" (4) and "one landed round" (13 PRs) and "identical
branch set" (24 -> 25, one removed by landing, two added).
