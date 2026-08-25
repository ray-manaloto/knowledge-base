---
type: "query"
date: "2026-08-25T15:21:24.222428+00:00"
question: "Was the guardrail survey's claim that settings.json uses the ./.venv/bin/graphify spelling false?"
contributor: "graphify"
outcome: "corrected"
correction: "I reported a guardrail survey's supporting evidence as FALSE, and my probe was the\nbroken one.\n\nThe survey said `.claude/settings.json` uses the `./.venv/bin/graphify` spelling\nthree times. I ran `grep -c './\\.venv/bin/'`, got 0, and published \"that part is\nfalse\" — in an artifact, as a worked example of a true finding arriving with false\nsupport.\n\nThe real spelling is `${CLAUDE_PROJECT_DIR:-.}/.venv/bin/graphify`, at\n`.claude/settings.json:19` and `:39`. A token-spelling bound produced a false\nnegative, exactly the class `probes-need-a-control-arm.md` rule 3 names — and I\nran no control arm before publishing, on a claim whose whole subject was that\nunverified claims mislead.\n\nIt mattered beyond the embarrassment: the finding I dismissed the evidence for was\na BLOCKER. Widening `hook_guard` without adding `hook-guard` to the read-only\nallowlist would deny the repo's own PreToolUse hook command (#497).\n\nThe habit that would have caught it in one command: before reporting a 0-result\ngrep as a refutation, grep a term you KNOW is present in the same file with the\nsame command shape. `grep -c '.venv/bin/graphify'` returns 2.\n"
---

# Q: Was the guardrail survey's claim that settings.json uses the ./.venv/bin/graphify spelling false?

## Answer

`kb-land` merged PR #482 pinned to the REMOTE branch head while the local branch
stood TEN commits ahead, then `--delete-branch` removed the branch holding them.
50 files / +4,705 lines of reviewed work were dropped and briefly orphaned, and
every surviving artifact read green: `land` printed `OK — PR #482 merged, main
synced`, the receipt it cited was genuine, the gates were genuine.

The mechanism: `pr.py:627` validates the PR head oid, not local HEAD — on purpose,
so a commit pushed by another route cannot merge unreviewed. Nothing anywhere
compares the two. The author reasoned about local being BEHIND the PR head; local
being AHEAD was never a case anyone wrote down.

Recovered by recreating the branch at `c41720d7`, then cherry-picking the ten onto
the post-#494 `main` (zero conflicts; `git diff c41720d7 HEAD` excluding the guard
files is EMPTY). Shipped as #496. Fixed by the `_local_ahead_gap` guard in #494.

The same round produced the inverse defect from the same function: landing #494
FROM A WORKTREE, `kb-land` printed `merge failed (head may have moved)` and exited
1 while the PR had actually MERGED — `gh pr merge --delete-branch` cannot switch
off the branch when `main` is checked out in another worktree, and `pr.py` maps
that non-zero to "merge failed". Filed as #495.

Both are one defect wearing two faces: **`land`'s report of what happened is not
derived from what happened.** The repo already has the rule (`gh-cli-watch.md`:
cross-verify an exit code against the API `conclusion` field); this call site does
not follow it.

Five things do NOT cross a git-worktree boundary, each discovered by a loud
failure that first read like a broken branch: the `.venv`, the gitignored
`sources/skillopt` clone, `kb-arms`' interpreter (it runs the suite with
`sys.executable`, so invoking it via another checkout's `kb-setup` yields
BASELINE RED and it correctly refuses to score), review reports, and receipts —
`git worktree remove` DESTROYS `.agent/`, taking the receipt and gate artifacts
with it.


## Outcome

- Signal: corrected
- Correction: I reported a guardrail survey's supporting evidence as FALSE, and my probe was the
broken one.

The survey said `.claude/settings.json` uses the `./.venv/bin/graphify` spelling
three times. I ran `grep -c './\.venv/bin/'`, got 0, and published "that part is
false" — in an artifact, as a worked example of a true finding arriving with false
support.

The real spelling is `${CLAUDE_PROJECT_DIR:-.}/.venv/bin/graphify`, at
`.claude/settings.json:19` and `:39`. A token-spelling bound produced a false
negative, exactly the class `probes-need-a-control-arm.md` rule 3 names — and I
ran no control arm before publishing, on a claim whose whole subject was that
unverified claims mislead.

It mattered beyond the embarrassment: the finding I dismissed the evidence for was
a BLOCKER. Widening `hook_guard` without adding `hook-guard` to the read-only
allowlist would deny the repo's own PreToolUse hook command (#497).

The habit that would have caught it in one command: before reporting a 0-result
grep as a refutation, grep a term you KNOW is present in the same file with the
same command shape. `grep -c '.venv/bin/graphify'` returns 2.
