---
type: "query"
date: "2026-08-25T00:49:10.978245+00:00"
question: "What goes wrong when I dispatch a codex lane with isolation: worktree, and how do I verify the base?"
contributor: "graphify"
outcome: "corrected"
correction: "I verified .venv provisioning but never checked WHICH COMMIT the worktree was cut from; the harness used main, 16 commits behind, and two lanes worked on a deleted code layer."
---

# Q: What goes wrong when I dispatch a codex lane with isolation: worktree, and how do I verify the base?

## Answer

THE HARNESS CUTS AN ISOLATION WORKTREE FROM `main`, NOT FROM YOUR BRANCH.

Measured 2026-08-24. Two `codex-implementer` lanes dispatched with
`isolation: "worktree"` both landed on `40859351` — the tip of `main` — while the
working branch was at `2b1cdc3a`, **16 commits ahead**. The diff between them was
**174 files, +18,687 / -4,472**, and the worktrees still contained the entire
semantic-corpus layer that commit `1e6eadd9` had deleted (15 such files in the
worktree vs 3 on the branch tip).

Both lanes were editing code that no longer exists on the branch. Their diffs could
not have merged. Killed by process group; both had written nothing, so nothing was
lost but ~250k subagent tokens.

**THE ARM THAT CATCHES IT, which I did not run the first time:**

    git -C <worktree> rev-parse HEAD   ==   git rev-parse HEAD

Run it BEFORE dispatching. I verified `.venv` provisioning — which the doctrine warns
about — and never asked the more basic question of WHICH COMMIT. A worktree lane that
starts from the wrong base fails silently: everything compiles, tests pass, and the
diff is simply about a different codebase.

**THE FIX: cut it yourself.**

    git worktree add --detach <path> <your-branch-sha>

Then arm it. A branch already checked out in the main checkout cannot be checked out
in a second worktree, so `--detach` is the form that works.

**TWO STANDING COSTS OF ANY WORKTREE LANE IN THIS REPO**, both measured the same night:

1. `uv sync --locked` fails with `Operation not permitted` writing the GLOBAL uv
   cache — the macOS sandbox blocks it from a worktree. Pass a task-scoped
   `UV_CACHE_DIR`.
2. `mise run kb-query` exits 2 because `graphify-out/graph.json` is gitignored and
   absent from every worktree. **No worktree lane can EVER satisfy the graph-first
   mandate.** Expected, not a defect — tell the lane so it does not investigate.

**AND: NEVER EDIT A SPEC FILE WHILE ITS LANE IS LIVE.** I rewrote
`spec-B-build-health.md` in place to re-point a relaunch, and the ORIGINAL lane —
still running — saw its own instructions mutate mid-run and had to reason about a
contradiction I introduced. Its report is the evidence. Write a NEW spec file for a
relaunch; leave the one a live lane references frozen. This is the same class as
switching branches under a lane, which the doctrine bans outright.

**What both lanes did right, and what to expect:** each stopped, reported
`STATUS: partial`, and refused to retry into a vanished directory. A lane whose
worktree disappears cannot run ANY further Bash — the harness refuses every call with
"Report this instead of retrying." So a killed worktree lane will still notify later
with an honest report; do not read that as the lane still being alive.


## Outcome

- Signal: corrected
- Correction: I verified .venv provisioning but never checked WHICH COMMIT the worktree was cut from; the harness used main, 16 commits behind, and two lanes worked on a deleted code layer.