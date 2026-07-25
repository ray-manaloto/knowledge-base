# Zero-Bash-Logic: No Bash Scripts, No Inline Shell Logic

Non-trivial logic (environment detection, tool config, validation,
orchestration) lives in `python/src/kb_setup/` and is invoked as
`uv run kb-setup <cmd>`. This repo goes one step further than the sibling
dotfiles repo, which still allows thin `scripts/*.sh` wrappers:

**This repo has ZERO `.sh` files, and that is the invariant.**

## The rule

1. **No `.sh` scripts anywhere.** Not in a `scripts/` directory, not beside a
   task. If you are about to create one, the logic belongs in a `kb_setup`
   module plus a mise task.
2. **No inline shell logic in `hk.pkl` or `mise.toml`.** A `run =` / `check =`
   line is a *seam*, not a program: it names one command. The moment it grows a
   loop, a conditional, a pipeline with a decision in it, or a multi-statement
   `&&` chain, it has become logic and must move into python.
3. **A recurring workflow ships as a `kb_setup` module + a mise task**
   (`mise-tasks-only.md`), never as a shell one-liner someone has to remember.

## Why the checks themselves are python

A big inline-bash grep in an hk step would itself violate the policy it
enforces. So `no_lint_skip` is `kb_setup.lint_checks.no_lint_skip`, the
PreToolUse guard is `kb_setup.hook_guard`, the budget gate is
`kb_setup.md_budget`, and each hk step is a thin `uv run kb-setup <cmd>`
wrapper over it. Same shape every time: **logic in python, a one-line seam in
config.**

This also makes every check testable. `tests/` covers `lint_checks`,
`hook_guard`, `md_budget`, `chunks`, `manifest`, `fetch`, `pr`, `brain`, and
the currency engine — none of which would be reachable from a shell script.

## Where the line actually falls

| Shape | Verdict |
|---|---|
| `run = "uv run kb-setup build"` | seam — fine |
| `run = "agnix . --strict"` | seam — fine, one command with flags |
| `check = "uv run ruff check {{files}}"` | seam — fine |
| `run = "for f in ...; do ...; done"` | **logic** — move to `kb_setup` |
| `run = "X && test -f Y && Z"` | **logic** — move to `kb_setup` |
| a new `scripts/foo.sh` | **forbidden** — there are none, keep it that way |

`.venv/`, `graphify-out/`, `sources/`, and `raw/` are derived or vendored and
out of scope; nothing there is ours to write.

## Applies to

Every check, gate, task, and hook in this repo. When a graphify operation needs
a wrapper, it becomes a `kb-*` mise task backed by `kb_setup.graphify_ops` —
which is also what makes the `kb_setup.hook_guard` redirect possible
(`mise-tasks-only.md`).

## See also

- `use-tool-builtins.md` — prefer a native/tool feature over ANY homegrown
  code, bash or python; the parent principle.
- `mise-tasks-only.md` — canonical mise tasks wrapping python modules.
- `python/src/kb_setup/lint_checks.py` — the pattern this rule describes.
