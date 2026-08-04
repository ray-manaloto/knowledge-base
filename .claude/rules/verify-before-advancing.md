# Verify Before Advancing: All Applicable Checks Green First

Before moving to the next task, committing, opening or merging a PR, or
claiming a task is "done", you MUST run **every check applicable to what
changed** and confirm each is **green with evidence**. Not a subset. Not
"should pass". Not an assumed outcome. Not a piped/notified exit code.

"Done" means *verified* done — the checks actually ran and actually
passed, and you read the real result.

## Why this rule exists

Repeatedly, the expensive failure mode is declaring a step complete on an
*assumption*: "that's a trivial edit", "lint should be fine", "the extraction
obviously worked". The assumption is sometimes wrong, and the gap is
discovered a task later when it is costly to unwind. This rule makes
verification a hard gate between every unit of work, not an optional courtesy.
It is the operational teeth behind `zero-skip-policy.md`.

## The check matrix — run what applies to the change

**Always (any code/config/docs change):** `mise run kb-gates` runs all four and
records each result to `.agent/kb/gates/gates-<sha>.json`, which is what a later
claim about them gets checked against. It does not stop at the first failure.

- `mise run lint` — hk `check --all`, exit 0. Never raw `hk` (see
  `long-running-command-hangs.md`).
- `mise run test` — `uv run pytest tests/ -x -q`, all pass.
- `mise run brain-audit`, `mise run eval` — the other two `kb-ship` enforces.

**Conditional (only when that surface changed):**

| Changed | Also required |
|---|---|
| `CLAUDE.md`, `.claude/**` (rules, skills, settings.json) | `mise run lint-docs` (agnix `--strict`) **and** the per-load-class budget holds (`md_size_budget`; see `md-size-budgets.md`) |
| `sources/*.manifest`, `sources/extractions/**`, `sources/media/**` | `mise run kb-build` reproduces from committed inputs alone, then `mise run kb-query` returns the new material |
| a new extraction chunk | `mise run kb-validate-chunks -- <chunk.json>` BEFORE `kb-merge` |
| `python/src/kb_setup/**` | the module's own tests, not just the suite total — a new module with no test file is not covered by a green suite |
| `mise.toml` tool pins | `mise run kb-currency-check` (offline drift check) |
| `hk.pkl` | `hk validate`, then the FAIL direction of the new step (below) |
| anything the `brain` surface reads | `mise run brain-audit` — `kb-ship` runs it, so a failure blocks the PR anyway; find it locally first |
| Opened a PR | `gh pr checks <n>` until terminal — every **binding** check `pass` or `skipping`, **0 fail**. CodeRabbit is *advisory here* and blocking in no bucket (`kb_setup.pr._ADVISORY_CHECKS`); it is still read and reported, never silently dropped |

Scale the matrix to the blast radius — a one-line doc typo needs the docs
row, not a full `kb-build`.

**`mise run kb-ship` checks the `kb-review` receipt, then runs `lint` + `test` +
`brain-audit` + `eval`, and refuses to push if any fails.** That is the floor, not the ceiling: it does not know whether
your change needed a `kb-build` or a chunk validation.

## A green gate is not a green artifact

This repo can pass every gate while producing a corpus nobody else can
reproduce, because `graphify-out/` and the `sources/<name>/` clones are
gitignored. Two things must therefore be verified *against committed inputs*,
not against your working tree:

1. **Reproducibility** — `mise run kb-build` from committed inputs alone must
   produce the graph you are claiming exists. A graph built from an
   uncommitted chunk exists only for you.
2. **Provenance of the version that built it** — `mise run kb-currency-check`
   reads `graphify-out/.currency-stamp.json`, which records the version that
   ACTUALLY RAN. A rebuild that bypassed `kb-build` reports *version unknown*,
   never a false green — treat that as a red, not a shrug.

## Prove the FAIL direction of anything you add

A gate verified only on clean input is decoration. When you add an hk step, a
contract, or a check: break the thing it checks, confirm rc=1, restore, confirm
rc=0 — and make the break **realistic** (delete the wiring line that calls a
function, not rename its definition; a renamed symbol still contains the
original as a substring). See `probes-need-a-control-arm.md`.

## Evidence discipline (trust the artifact, not the notification)

- Read a **file-based `rc`** or the **API `conclusion` field**, never a
  piped `… | tail` (bash returns tail's exit 0, masking upstream failure) and
  never a background-task "completed" notification's exit code.
- `gh run watch --exit-status` has reported 0 prematurely — cross-verify
  with `gh run view <id> --json conclusion --jq .conclusion`. See
  `gh-cli-watch.md`.
- A "skipped" job is a *valid terminal state*, but confirm it skipped for the
  expected reason. **A SKIPPED job never asked the question** — "never ran" is
  not "ran and found nothing".

## The gate

Only after every applicable check above is green do you: commit, push,
merge, start the next task, or report completion. If any check is red,
that is the current task — investigate and resolve it (`zero-skip-policy.md`),
do not defer past it.

## Carry a fact's CONDITION, not just its source

A figure that travels without its "true when" survives review — the citation
checks out — and is still wrong where it is used. Each of these was genuine,
correctly sourced, and misapplied:

| fact | true when | was applied to | what it cost |
|---|---|---|---|
| a 12,000-char limit | Windsurf / agnix AGM-003 | all Claude markdown | a gate enforcing a limit its real owner never set |
| "extracts NOTHING under an unsupported node" | some older tool version | a version that extracts fine | a hunt for a data-loss bug that does not exist |
| a 2–2.5h cold build | a specific cache **miss** | any config touch | a ~4x over-warning; measured ~37 min |

A stated condition is also what makes a fact **falsifiable later**. So when you
carry a number, carry its condition — and when you meet one, ask "what has to
be true for this to hold, and is it true HERE?"

## Applies to

Every task in this repo — local edits, ingestion runs, PRs, merges, and
agent-delegated work (the delegating context is responsible for confirming the
delegate's checks actually passed).

## See also

- `zero-skip-policy.md` — no red check is ever dismissed.
- `probes-need-a-control-arm.md` — arm both directions.
- `long-running-command-hangs.md` — bound `mise run lint`; never wait blind.
- `md-size-budgets.md` — the per-load-class budgets.
- `do-not.md` — project invariants that never bend regardless of green checks.
