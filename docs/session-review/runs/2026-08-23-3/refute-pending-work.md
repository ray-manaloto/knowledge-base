# Refutation lane: pending-work finding #24 (4 worktrees safe to remove)

CLAIM: 4 git worktrees (knowledge-base-299/300/301/graphify-0942) hold branches whose
commits are ALL already merged into origin/main via squash-merged PRs #307/#308/#312/#291
— safe to remove.

## Probe 1 — control-arm the OFFERED evidence (`merge-base --is-ancestor <mergeCommit>`)
Positive: 67f7ef0b, cc6e226b, 0c15267e, c70f0f81 -> rc=0 (all)
Negative control: branch HEADs 3018dff3, 4cd58d0a, 8ace6198, 5eda1525 -> rc=1 (all)
=> the probe discriminates, BUT it tests the MERGE COMMIT, which is on main by
construction. It never asked whether the BRANCH's content landed.

## Probe 2 — the question the offered evidence did not ask (content equivalence)
git rev-parse: branch head == PR headRefOid for all four (307/308/312/291).
git diff --name-only <branchHead> <mergeCommit> -> 0 files for ALL FOUR.
Control: git diff --name-only 3018dff3 origin/main -> 389 files (probe discriminates).
=> "commits are ALL already merged" HOLDS, and now on stronger evidence than offered.

## Probe 3 — the "safe to remove" half (IN PROGRESS)
git status --porcelain per worktree:
  knowledge-base-299 -> 0 lines (clean)
  knowledge-base-300 -> 0 lines (clean)
  knowledge-base-301 -> 0 lines (clean)
  knowledge-base-graphify-0942 -> 9 lines, ALL untracked:
    .agents/skills/{clear-prep,goal-engineering,kb-curator,kb-reclaim,kb-review,
                    kb-session-reflect,orchestrator-routing,tool-currency}/
    .codex/
  27 files, 188K + 48K.

## Probe 4 — DECISIVE: `git worktree remove` semantics vs what these worktrees hold
`git version 2.50.1 (Apple Git-155)`; `git worktree remove --dry-run` -> `error: unknown
option 'dry-run'` (rc=129). Only `-f/--force` exists. Plain `remove` refuses a worktree
with modified/untracked files; `--force` deletes the directory WHOLESALE, including every
GITIGNORED file (git's clean-check does not count `!!` entries).

All four worktrees carry a gitignored `.agent/` tree:
  knowledge-base-299            644 files / 171M
  knowledge-base-300             13 files /  40K
  knowledge-base-301            219 files / 3.6M
  knowledge-base-graphify-0942    7 files /  28K

Of the 14 `kb-review` cold-lane reports held there, **11 exist in no other copy**:
  not in the main worktree's .agent/kb/review/reports/ (116 entries), and
  `git log --all --diff-filter=A -- '**/<name>'` -> 0 adding commits for each
  (CONTROL: `docs/research/README.md` -> 1 adding commit, so the probe discriminates).
  15,158 bytes total, e.g. review-4af54b5e…-cold.md (2,244B/24L),
  review-f1a2155c…-cold.md (2,811B/36L).

Plus 9 unique PR/issue research artifacts absent from main, e.g.
  299 :: kb/pr-307-body.md (2,592B), kb/issue-292-handshake-v15.md (782B)
  301 :: kb/pr-309-body.md (2,085B), kb/pr-309-final-bot-disposition.md (1,788B)

knowledge-base-301 also holds gitignored `graphify-out/graphify-semantic-corpus*`
(8 entries, 304K + prototypes + 4 preflight JSONs) — the retained provider evidence class
that `.claude/rules/clean-git-state.md` says is deliberately untracked-and-visible (#317).

knowledge-base-graphify-0942 additionally holds 27 UNTRACKED, non-ignored files
(.agents/skills/** 188K + .codex/** 48K), so plain `git worktree remove` REFUSES it —
it is not removable without `--force` at all.

## VERDICT: REFUTED (the "safe to remove" half)
- "commits ALL already merged" -> TRUE, and I strengthened the evidence for it.
- "safe to remove" -> FALSE. Removal destroys 883 gitignored files, incl. 11 sole-copy
  kb-review cold reports and 9 sole-copy research artifacts, and one worktree cannot be
  removed without --force at all.
