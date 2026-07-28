---
paths:
  - ".github/workflows/*.yml"
  - "hk.pkl"
  - "mise.toml"
  - "pyproject.toml"
---

# CI/Local Parity: Keep Local Checks in Sync (and With CI, If It Ever Exists)

**This repo has no `.github/` today.** The gates are entirely local:
`mise run lint` (hk), `mise run test` (pytest), `mise run lint-docs` (agnix),
plus `kb-scan-range`, `brain-audit` and `eval` — all run by `mise run kb-ship` before a PR is
opened, behind a `kb-review` receipt check that runs first.
That makes the rule below *cheaper*, not optional: with no CI to catch drift,
a check that exists in one place and not the other is simply not run.

This rule is `paths:`-scoped, and legitimately so: its trigger genuinely *is*
a file — you only need it when editing `hk.pkl`, `mise.toml`, `pyproject.toml`,
or a workflow. That is the test in `md-size-budgets.md`, applied to itself.

## Rule 1: Every gate has ONE definition, reachable from `mise run`

A check that a reviewer or a future CI job would run must be an hk step or a
mise task — never a command that lives only in someone's shell history. If you
add a workflow step later, add its hk equivalent in the same change.

`kb_setup.pr.run_gates` is the list `mise run kb-ship` actually enforces
(`kb-scan-range`, `lint`, `test`, `brain-audit`, `eval` — the `GATES` tuple in
`pr.py`). `kb-scan-range` is the only one that asks about a COMMIT RANGE rather
than the working tree: hk's `gitleaks` step is handed `{{ files }}`, so it never
opens a blob that exists only in an intermediate commit — and `ship` pushes
every commit on the branch (#67). It is a ship gate rather than an hk step
because of **timing**, not capability — `no_lint_skip` and `md_size_budget`
prove hk can host a whole-repo step — and the range question is only meaningful
against what a push would publish. The
review receipt is checked BEFORE that list and again before the push. A gate
that is not in that list, and not an hk step reached by `lint`, does not gate
anything.

## Rule 2: Every tool an hk step invokes must be pinned in `mise.toml`

When adding an hk step with a `check` command, verify the binary is in
`mise.toml` `[tools]`. A tool present only in global `~/.config/mise/` is
invisible to a fresh clone and to any future runner.

Verification: `mise which <tool>` should resolve under
`~/.local/share/mise/installs/`.

**`mise tasks` merges the user's GLOBAL config**, so it will list tasks that
exist in no file in this repo. To audit what this repo really defines, read
`mise.toml` — including `alias` keys, or an alias reads as a missing task.

## Rule 3: Use mise binary names, never `npx`

For tools in `mise.toml`, use the binary name directly:

- YES: `agnix . --strict`, `graphify query`
- NO: `npx agnix .`

`npx` bypasses mise, re-downloads, and may resolve a different version.

## Rule 4: `uv run` from the repo root — no `--directory`

This repo has ONE `pyproject.toml`, at the root, aggregating `[project]` +
ruff + ty + pytest so `python/src` and `tests/` resolve the same config.
So plain `uv run …` from the root is correct.

Never `uv run --directory python …`: `--directory` changes cwd and breaks
relative paths. (The sibling dotfiles repo needs `--project python` because
its package config lives in `python/`; ours does not. Copying its incantation
here is a common and silent mistake.)

## Rule 5: Both hk hooks must stay in sync

`hk.pkl` defines `lintSteps` once and spreads it into `check`, `fix`, and
`pre-commit`. Adding a step to one and not the others would let a commit pass a
hook that `mise run lint` fails. Add to `lintSteps`, never to a single hook.

## Rule 6: Test a new hk step locally before committing

1. `hk validate` — config syntax
2. `mise run lint` — the step actually passes
3. Prove the FAIL direction (`probes-need-a-control-arm.md`) — break the thing
   it checks and confirm rc=1, then restore
4. Only then commit
