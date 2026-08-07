# #160 — the mutation harness as a module: mutation arms

The eighth mutation harness in this repo is the first that is not a program
someone re-typed. `kb_setup.arms` owns the loop; a round contributes arms as
TOML data; `mise run kb-arms -- <spec.toml>` runs them.

This report is the evidence for the module, and it was produced **by the module
running against itself** — the behavioural proof #219's closing comment stakes
itself on, and the reason the arms table below is not embedded here as python.
The arms live in
[`2026-08-07-arms-module-arms.toml`](2026-08-07-arms-module-arms.toml),
committed beside this file and re-runnable:

```bash
mise run kb-arms -- docs/research/reports/2026-08-07-arms-module-arms.toml
mise run kb-arms -- docs/research/reports/2026-08-07-arms-module-arms.toml --dry-run
```

## Result

**Final sweep: 35 of 35 real arms DIED with the NAMED test failing, `A0` a
declared no-op CONTROL that held, baseline green, restored green.**

Five sweeps were needed, and the ones that were not clean are the report.

| sweep | arms | died | survived | what changed after |
|---|---|---|---|---|
| 1 | 28 | 25 | `A2`, `A12`, `A24` | one real gap, one inert mutation, one probe defect — below |
| 2 | 29 | 28 | `A30` | the harness was setting the condition it was measuring |
| 3 | 29 | **29** | none | cold review round 1 → 1 P1 + 2 P2 |
| 4 | 35 | **35** | none | six added arms REVERT the review's own fixes |
| 5 | 35 | **35** | none | after round 2's P3 fix — final |

Sweep 3 was clean and the cold lane then found a P1 in the same code. That is
the fourth clean sweep in this repo immediately preceding a real defect, and it
is worth stating plainly: **a full arm score is a statement about the tests, and
says nothing about whether the module is safe.** No arm asks "may this write
there at all?"

## Sweep 0: the harness refused to run at all, and was right to

The first invocation printed:

```text
baseline (unmutated) rc=1
  BASELINE RED - no arm below could have discriminated
ABORTED: baseline suite is RED - no arm could have discriminated
```

`tests/test_arms.py` was green under `mise run test` and red under the harness.
The cause is the subject of this whole module:
`test_a_stale_pyc_is_really_used_and_the_purge_prevents_it` needs bytecode to
**be written**, and the harness exports `PYTHONDONTWRITEBYTECODE=1`, which the
test's own child process inherited. No `.pyc` was ever written, so the test's
own guard — `assert (tmp_path / "__pycache__").is_dir()` — fired.

**A test whose result depends on which tool invoked it.** It was caught only
because the guard exists; without it the test would have failed one assertion
later, on the stale-value comparison, and named the wrong cause.

Note what the harness did **not** do: it did not run 28 arms against a red suite
and report 28 deaths. Against an already-red baseline every death is free.

## The three survivors of sweep 1

Each was settled by measurement rather than argument, and the three answers were
three different things — which is why "survivor" is not a verdict on its own.

### `A2` — a REAL gap that looked inert

Removing `PYTHONDONTWRITEBYTECODE=1` moved no verdict, because the purge runs
before every suite and anything written during arm N is gone before arm N+1.

It is still not redundant: `purge_bytecode` can fail, and this is the second
line. Arming it by asserting the variable is present in the env would have been
the code agreeing with itself, so the new test asserts the **observable
consequence** — the purge runs *before* the suite, so a `.pyc` written during it
would still be on disk when it returns.

### `A12` — genuinely INERT, and the guard was deleted

`Report.ok` carried both `bool(self.rows)` and
`any(row.arm.control for row in self.rows)`. `any()` over an empty tuple is
already `False`, so the first clause is strictly implied by the second: **two
guards for one property, each masking the other's mutation.**

Deleted rather than tested, on this repo's precedent. A guard whose removal no
test can notice is worse than no guard, because a sweep scores it as covered.
`test_a_report_with_no_rows_at_all_is_not_ok` still pins the behaviour and now
arms the clause that actually delivers it.

### `A24` — a PROBE defect, not a coverage gap

The arm mutated the missing-required-key `errors.append` into an immediate
`raise` and named `test_every_problem_is_reported_in_one_pass`. That test's spec
has a missing `test` and a missing control, and **never a missing required key**,
so the mutated line was never reached. The arm had been asking a question the
test could not answer.

Re-pointed at `"; ".join(errors)` → `errors[0]`, which is the line that test does
exercise, and the previously unreached line got a test of its own (`A24b`).

## Sweep 2: the harness was setting the condition it was measuring

`A30` — the re-pointed `PYTHONDONTWRITEBYTECODE` arm — survived again, and the
diagnosis is the sharpest finding here.

`run_suite` builds `{**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}`. When the
suite is run **by the harness**, the parent process already exports that
variable, so deleting the explicit key changes nothing. Control-armed, with the
mutation applied both ways:

| context | rc |
|---|---|
| parent exports `PYTHONDONTWRITEBYTECODE=1` (a `kb-arms` run) | **0 — survives** |
| parent does not (an ordinary `mise run test`) | **1 — dies** |

The test discriminated perfectly, and the instrument suppressed it. The fix is
`monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)`, so the test gives
the same answer whoever invoked it. Armed four ways afterwards — mutation dies in
both contexts, control green in both.

**This is the same defect as sweep 0, one layer up**, and that is the durable
lesson: two of the three problems found in this module were a test inheriting
the harness's environment. When the thing under test configures the environment,
the test must own its own.

## The defect found by inspecting a survivor rather than by an arm

`purge_bytecode` paired `shutil.rmtree(cache, ignore_errors=True)` with an
unconditional `removed += 1`. A purge that silently failed therefore returned the
count of a purge that worked — **the mitigation lying about itself**, which is
the one failure this module cannot absorb, since every later verdict rests on it.

It now checks the directory is gone and raises if it is not (`A29`, dies).

## Sweep 3 was clean; the cold lane then found a P1 in the same code

Round 1 of the `kb-review` cold lane (`fable-orchestrator:codex-reviewer`,
OpenAI, MUTATING brief) over `f9cb5d1571978d` returned **3 findings — 1 P1, 2 P2
— every one verified by execution rather than by reading**. Full report:
`.agent/kb/review/reports/review-f9cb5d1571978de7eb3f33dc7112e443135e9550-cold.md`.

### P1 — an arm could mutate any file on disk

`path = repo_root / arm.file` is not containment. `Path.__truediv__` discards
the left operand when the right is absolute, so `Path("/repo") / "/etc/hosts"`
is `/etc/hosts` — **and this module writes to that path.** The lane built three
constructions and ran them for real: an absolute path, a `../` traversal, and a
symlink checked in under the repo. It caught the harness mid-run with a file
*outside this repo* holding `MUTATED BY ARMS`, restored afterwards, with
`git status` clean throughout — because nothing outside the tree is tracked.

That is `do-not.md` #11 ("Do NOT edit anything outside this project") with a
keyboard, and the module's own framing made it worse: "arms are data, never
code" invites reviewing a spec more loosely than code, while a `file` value in
that data reached anywhere on disk.

Fixed with `contained_path()`, which resolves **both** sides before comparing.
Lexical containment would have passed the symlink straight through — the exact
substitution that was defended in a docstring in this repo once and walked
through by a symlink the next round. A new `BROKEN_ESCAPES_REPO` verdict covers
the runner, and `load_spec` now refuses an escaping spec before the baseline
runs. Those are two entry points rather than two guards on one path: `run()`
accepts hand-built `Spec` objects that never pass through the loader, so each is
separately reachable and separately armed (`A31`, `A36`).

### P2 — `UnicodeDecodeError` is a `ValueError`, not an `OSError`

Three `except OSError` handlers therefore missed it, and a non-UTF-8 target or
spec crashed the whole run with a traceback instead of taking the PROBE BROKEN
verdict the docstring promises. Verified at all three sites by pointing an arm at
a PNG-header blob and by feeding the loader raw `0xff 0xfe`. Now caught as
`(OSError, UnicodeDecodeError)`.

### P2 — `_restore`'s self-check was a verified surviving mutant

The lane deleted the verify-and-raise, leaving only the `write_text`, and **all
38 tests still passed**. Nothing exercised a write that raises no exception and
still leaves the wrong bytes. Now tested (`A35`) by stubbing `write_text` to a
no-op — the stub *is* the failure being modelled (a write that silently does not
take, or a second writer between the write and the read), not a stand-in for the
code under test.

### The condition on round 1: I edited the tree while the lane was still alive

Round 1's report carries an addendum saying so. Partway through finalising, it
observed `python/src/kb_setup/arms.py` **modified and uncommitted** — my fix for
the very P1 it had just reported — and correctly declined to evaluate it,
recording that its findings "were verified against that commit's committed code,
before this uncommitted change appeared".

**A lane with a MUTATING brief executes code, so it is measuring the WORKING
TREE, not the commit.** Editing production source while one is running can
therefore corrupt its measurements, and nothing in the review flow prevents it:
the brief pins a SHA, and `git diff` respects that, but `uv run pytest` does not.

Nothing here was corrupted, and the reason is stated rather than assumed:

1. the lane's own addendum places its verification before the edit;
2. round 2 independently **re-armed all three fixes** by reverting each and
   watching the named test go red (its items 3, 4, 5), which does not depend on
   round 1's execution environment at all.

So the findings stand. What does not stand is the impression that round 1 ran
against a static tree. **The fix is to wait for the lane's report before
touching a file it may execute** — and this is the third instance in one round
of the same shape: an instrument and its subject sharing state, after the two
`PYTHONDONTWRITEBYTECODE` findings above.

### And the harness caught its own arms going stale

Those fixes moved the lines `A22` and `A23` were pointed at, and the next
`--dry-run` reported both as **`PROBE BROKEN - pattern not found`** rather than
scoring them. Protection 2, firing on live input rather than on a fixture, in
the first hour of the module's life. Both were re-pointed; `A22` and `A34` now
mutate the same `except` clause for two different reasons.

## Round 2 — 0 blocking, and the P3 is the same lesson twice

Round 2 over `4f6e8a8d2a12` found **no P1 or P2**, and the reason it is worth
reading is what it *cleared*: it constructed every legitimate case the new
containment guard could have wrongly refused — a repo root reached through a
symlink (the real macOS `/tmp` → `/private/tmp` case), redundant `./` segments,
a nonexistent parent, an in-repo symlinked subdirectory — and confirmed the
guard allows all of them while refusing every escape. It also ran the escaping
spec end to end through `mise run kb-arms` and checked the task propagates rc=2.
The mirror of a P1 is a guard that over-corrects, and this one does not.

**P3 (fixed): a dead branch no arm could ever kill.** `_read_target` returned
`tuple[Path | None, str | None, Row | None]`, so both callers carried a
`source is None and refusal is None` fallback that no input could reach. This is
the `bool(self.rows)` finding again, from the opposite direction: there the
guard was implied by its neighbour, here the **annotation admitted a state the
function cannot produce**, and the caller wrote a branch for it. A sweep scores
such a branch as covered forever. Fixed by narrowing the return to
`tuple[Path, str] | Row`; both fallbacks are gone.

**P3 (accepted unfixed): case-insensitive filesystems.** `contained_path(repo,
"SUB/FILE.TXT")` is accepted when the tracked file is `sub/file.txt`, because
`Path.resolve()` does not canonicalise case. It is not an escape — the resolved
path is still inside the repo — and the only consequence is that a row can
display different casing than the tracked path.

That fix moved a line a third arm pointed at, and the stale detector fired for
the third time in this round. **All three stale reports were true and none was
scored**, which is the property the module exists for.

## What this sweep does NOT say

- It says these lines are covered. It says nothing about whether the module
  implements the right rule — arms mutate an implementation and cannot ask that.
  A clean sweep is a statement about the TESTS.
- `--dry-run` is not a run. It is reported as `DRY RUN` and a dry `Report` can
  never be `ok`; the first version printed a green baseline row and a green
  restored row for a dry run, neither of which had executed.
- Three arms were **removed or re-pointed** between sweeps and that is recorded
  in the spec's comments rather than silently dropped. A shrinking spec with no
  explanation reads as arms that were quietly abandoned.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under test.
