# Clean Git State Before Validation

Divergence between what hk checked and what a reviewer (or a fresh clone) sees
is the #1 cause of "passes locally, fails for someone else." Ensure git state
is clean before running validation or committing.

## Before Running hk Checks

1. Run `git status --short` to identify unstaged changes
2. Stage ALL file deletions: `git add <deleted-file>`
   - A deleted-but-unstaged file still exists in a fresh checkout
3. Stage ALL file modifications you intend to commit
4. Then run `mise run lint`

## Before Every Commit

Verify what hk checked locally matches what lands in the commit:

1. `git diff --name-only` — should show no unstaged changes for hk-checked files
2. `git diff --cached --name-only` — should show all intended changes
3. New files must be `git add`-ed before hk runs, or hk won't check them

## Common Divergence Patterns

| Local State | What others get | Fix |
|-------------|-----------------|-----|
| File deleted on disk, not staged | File still exists | `git add <deleted-file>` |
| File modified, not staged | Old content | `git add <file>` or stash |
| Globally-installed tool | Tool missing | Pin it in `mise.toml` |
| `npx` resolves a cached package | `npx` re-downloads a different version | Use the mise binary name |

## The corpus adds one more pattern, and it is the expensive one

`graphify-out/` is DERIVED and gitignored except for `memory/`. `sources/<name>/`
clones are gitignored too — a source is reproduced from its `.manifest` pin.
So a green local state can rest on bytes nobody else will ever have:

| Local state | What a fresh clone gets | Fix |
|---|---|---|
| A graph built from an un-committed extraction chunk | A graph missing those nodes | commit the chunk under `sources/extractions/` |
| A source clone advanced past its manifest SHA | The pinned SHA | `mise run kb-update -- <name>` so the manifest moves too |
| Hand-edited `graphify-out/` artifacts | Regenerated output | re-derive via `kb-build` / `kb-artifacts`; never hand-edit |

**`mise run kb-build` from a clean tree is the control arm.** If the graph you
are reasoning about cannot be reproduced from committed inputs, it does not
exist for anyone else.

## A blanket `git add` is DENIED (2026-08-18)

`kb_setup.stage_explicitly` refuses `git add -A` / `--all` / `.` / `:/` at the
PreToolUse hook, and prints the remedy: name the paths, or `git add -u` for
tracked modifications only.

**The measurement, because a guard without one is a preference.** In a single
session `git add -A` swept derived corpus evidence under
`graphify-out/graphify-semantic-corpus-chunks/` into a commit **three times** —
the first caught, amended out, and written up before the second and third
happened. Knowing the rule prevented nothing, which is this repo's recurring
finding about warnings: the warning-only graph-first rule was complied with **0
times out of 19**, while the DENY that replaced it took its violations **62 → 0**.

**Why that path and not an ignore rule, at the time.** `graphify-out/graphify-semantic-corpus-chunks/`
was deliberately absent from `.gitignore`, and the comment there said why: it was
retained provider evidence for a run that cost real tokens, and whether to track
it was the open question in #317 (settled 2026-08-23 in favour of tracking).
Ignoring it would have settled that question silently; committing it settled it
just as silently the other way. That whole tree — and the layer it evidenced —
was removed 2026-08-24 (`docs/archive/README.md`), so the path no longer exists;
the guard and its "name the paths explicitly" remedy are unchanged and still
apply to whatever untracked evidence a future run produces.

**`git add -u` is deliberately allowed.** It stages modifications to
already-tracked files and cannot introduce an untracked path, which is the entire
failure mode — a guard that refused the safe alternative its own message
recommends would be worse than none.

## Why this rule is eager (never `paths:`-scoped)

Same class as `zero-skip-policy.md`: it fires when validation is about to run,
not when a given file is read, so no glob predicts it. In dotfiles it was
scoped until 2026-07-15, which meant validating after a python-only edit never
loaded it. See `md-size-budgets.md` § "Scoping: the trigger test".
