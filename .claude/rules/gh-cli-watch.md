# gh CLI: Always use `--watch`, Never Hand-Roll Poll Loops

When waiting on a GitHub PR's checks or a workflow run via the `gh`
CLI, use the built-in `--watch` flags. Never hand-roll a
`while ! gh ... | grep ...; do sleep; done` polling loop.

## Why this rule exists

The `gh` CLI has first-class support for live-monitoring with
appropriate refresh intervals, exit codes, and table updates:

- `gh pr checks <n> --watch [--fail-fast] [--interval N]` — refreshes
  every 10s by default until terminal state. Exit code reflects
  pass/fail/pending. Docs: <https://cli.github.com/manual/gh_pr_checks>.
- `gh run watch <run-id> --exit-status` — same shape for a specific
  run. Caveat: `--exit-status` has reported 0 prematurely on edge cases,
  so cross-verify with `gh run view <id> --json conclusion` after.

Hand-rolled poll loops:

- Bury exit codes (the `grep` becomes the shell's exit, masking API
  errors).
- Race on multi-run scenarios (`gh run list --limit 1` matches the
  wrong run when multiple are queued).
- Burn API quota on aggressive sleeps.
- Don't redraw / show progress; the operator stares at silence.

## This repo has no CI — so the usual answer is `kb-ship` / `kb-land`

**`.github/` does not exist here.** There is no `ci.yml`, so a PR's only
required checks are whatever branch protection adds. That makes the
canonical path shorter, not different:

- `mise run kb-ship` checks the `kb-review` receipt, then runs the local gates
  (`lint`, `test`, `brain-audit`, `eval`) BEFORE pushing and opening the PR — the
  gates CI would have run, plus the review CI never did.
- `mise run kb-land -- <PR#>` gives the checks a BOUNDED chance to reach a
  terminal state (it wraps `gh pr checks --watch`, since that flag has no timeout
  of its own), then reads their state, refuses a PR head with no review receipt,
  squash-merges pinned to that SHA, and syncs main. **CodeRabbit is advisory** —
  reported in every bucket, blocking in none, because waiting on its quota is
  waiting on a rate limit rather than on a review.

Both already do the waiting. Reach for a raw `gh` watch only when you are
inspecting a PR neither task owns.

## When to reach for Claude Code's `Monitor` tool instead

Only when one of these is true:

1. You need **per-transition notifications** (each new ✔/✗ should
   surface as a separate event in chat). `gh pr checks --watch` shows
   a redrawing live table — fine for humans, low signal for an
   automation that wants to react per-transition.
2. The command is on a **non-GitHub system** with no built-in watch flag.
3. You need to **filter** the events (e.g., only emit on failure).

For "wait until done, tell me when", prefer `gh pr checks --watch`
straight up.

## Canonical patterns

```bash
# Wait for all PR checks to finish, in a long-running terminal:
gh pr checks 123 --watch --interval 30

# Fail loud on any check failure:
gh pr checks 123 --watch --fail-fast
echo "exit=$?"

# Wait for a specific run, then cross-verify the conclusion:
gh run watch 1234567890 --exit-status
gh run view 1234567890 --json conclusion --jq '.conclusion'

# Watch the current branch's PR:
gh pr checks --watch
```

## Anti-patterns

```bash
# WRONG — hand-rolled poll, no exit-code awareness:
while ! gh pr checks 123 --json bucket | grep -q success; do
  sleep 30
done

# WRONG — racy on multi-run queues:
gh run list --limit 1 --json status

# WRONG — fixed-time wait, never reflects actual completion:
sleep 600 && gh pr checks 123
```

## Applies to

All skills, agents, and ad-hoc Bash invocations in this repo. When `gh`
documentation lists a `--watch` flag for any subcommand (`pr checks`,
`run`, `workflow`, `pr status`), use it.

## See also

- `mise-tasks-only.md` — `kb-ship`/`kb-land` are the canonical PR path;
  they already watch.
- `long-running-command-hangs.md` — sibling rule for bounding local
  long-running commands and reading a real `rc` instead of a piped tail.
- `verify-before-advancing.md` — cross-verify a watch's exit code against
  the API `conclusion` field before calling a merge done.
