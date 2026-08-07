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

**Final sweep: 29 of 29 real arms DIED with the NAMED test failing, `A0` a
declared no-op CONTROL that held, baseline green, restored green.**

Three sweeps were needed, and the two that were not clean are the report.

| sweep | arms | died | survived | what changed after |
|---|---|---|---|---|
| 1 | 28 | 25 | `A2`, `A12`, `A24` | one real gap, one inert mutation, one probe defect — below |
| 2 | 29 | 28 | `A30` | the harness was setting the condition it was measuring |
| 3 | 29 | **29** | none | — |

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
