# Cold review — commit `d8114ab1` (base `a67cbac4`)

Reviewed SHA: **`d8114ab1`** (`d8114ab1adf25969dadd69ae435dda2d6defd060`), read entirely by
ref (`git show d8114ab1:<path>`, `git diff a67cbac4 d8114ab1`). No working-tree file under
review was read; no file was modified; no test, gate or mise task was run. Line numbers are
as in the commit.

No P0. Three P1s, seven P2s, five nits.

---

## P1

### P1-1 — `verify_plan` can still raise: `TypeError` escapes the new catch, on the exact input class the branch exists for

`graphify_semantic_corpus.py:1846-1848` catches `ValueError, SystemExit` around
`_measured_runtime`. `graphify_baseline.runtime_identity` raises a **third** type:

- `graphify_baseline.py:360-361` — `sdist = package.get("sdist")` / `if not isinstance(sdist, dict): raise TypeError("Graphify uv.lock entry has no source distribution")`.

A `uv.lock` whose `graphifyy` entry has no `sdist` key (a wheel-only publication — ordinary
on PyPI) produces `TypeError`, which is not caught. It escapes `verify_plan`, and nothing
above catches it either: `corpus_main` has no handler around the call
(`graphify_semantic_corpus.py:3279`), and `cli.py`'s `except BaseException` (`cli.py:560`) is
scoped to the `graph.build` route, not the corpus dispatch at `cli.py:247-250`.

That defeats the contract the commit states in its own test docstring
(`tests/test_graphify_semantic_corpus.py:2669-2675`: *"`corpus_main`'s `verify` route must
always print a verdict and its `run` route must always reach `_abort`"*): `verify` tracebacks
instead of printing a verdict, and `run` never reaches `_abort`, so no abort artifact is
written.

Secondary route, same hole: `runtime_identity` calls `graphify_sdk.running_sdk_version()`
(`graphify_baseline.py:377` → `graphify_sdk.py:182-184` → `metadata.version("graphifyy")`),
which raises `PackageNotFoundError` (an `ImportError` subclass) — also uncaught. Contrived,
but it is the same defect.

The comment at `graphify_semantic_corpus.py:1836-1839` enumerates exactly two raise
types and reads as if that enumeration is complete; it was derived from the two *named*
`raise` sites rather than from the function's whole exception surface. Fail-closed either
way — it does not authorize spend — but a verifier whose stated property is totality is not
total.

Fix is one token: `except (ValueError, TypeError, SystemExit)`, or better `except Exception,
SystemExit` — the semantic being asserted is "the live runtime cannot be vouched for",
which does not depend on *how* the measurement failed.

### P1-2 — the new docs section and the new mise comment contradict the code on restart cost, re-introducing a falsehood the code was explicitly corrected to remove

`docs/agents/graphify-semantic-corpus.md:435-438`:

> **A restart resumes; it does not restart from zero at the mise layer.** `_verified_stages`
> re-publishes every chunk whose stage directory already holds verified evidence before
> staging the rest, so an interrupted run picks up where it left off rather than
> re-publishing completed chunks.

`mise.toml:678-680` repeats it: *"the run is resumable (`_verified_stages` re-publishes
already-staged chunks, so a restart does not redo completed work at the mise layer)"*.

The code says the opposite, in three places:

- `graphify_semantic_corpus_run.py:1139-1141` — *"a chunk that was already staged is paid
  for again (graphify serves nothing from cache on this entry point)"*. The charge is taken
  in `on_chunk_done` **before** the disposition and outside every branch, so already-staged
  chunks are charged.
- `graphify_semantic_corpus_run.py:1188-1195` — `_dispose` routes an already-staged chunk to
  `_resolve_existing_stage` and appends its ordinal to a list literally named **`repaid`**.
- `graphify_semantic_corpus.py:838-851` — the `graphify_no_incremental_cache` comment records
  that the "a resumed run pays only for the chunks it has not already extracted" framing
  *"was never true on this path"*, with an AST walk as the arm, and ends *"Budget an
  interrupted run at full price."*

So `_verified_stages` avoids re-**publishing** evidence; it does not avoid the provider
**spend**, which is the only cost anyone reads this section to understand. The docs sentence
is also self-contradictory on its face — it says the mechanism re-publishes, then says it
happens "rather than re-publishing" — and "before staging the rest" is mechanically wrong:
`_verified_stages` runs once before the loop (`graphify_semantic_corpus_run.py:1119`), while
the re-publish happens per chunk inside `_dispose`, *after* graphify has already re-extracted
and re-charged that chunk.

The hedge two lines later (`:438-441`, "Graphify itself re-buys any chunk it re-attempts at
full price") understates it: it re-attempts **all** of them, every restart. That is the whole
premise of the F3 sizing at `graphify_semantic_corpus.py:82-91`, which is correct — the docs
and the mise comment are the artifacts that disagree with it.

### P1-3 — the commit ships with a red `mise run test`, by its own account, and the fix for it was written in this same commit but applied to one test only

The commit message states 20 of 57 tests in `tests/test_graphify_semantic_corpus_run.py`
fail, plus `test_recorded_authority_authorizes_this_plan_and_only_this_plan` "deliberately NOT
fixed". `zero-skip-policy.md` § Local Validation Gate ("Do NOT push until `mise run lint` and
`mise run test` pass") and `verify-before-advancing.md` ("`mise run test` … all pass") both
forbid this, and `kb-ship` runs `test` as a gate, so this HEAD cannot ship as-is.

Cause and blast radius (derived, not run — I did not execute the suite):

- `CorpusExecutionConfig.effort` is required with no default
  (`graphify_semantic_corpus.py:462`), so `msgspec` strict-decode of any pre-existing plan
  raises. `_config()` / `_run_context()` in the run tests decode
  `_PLAN / "execution-config.json"` at setup (`tests/test_graphify_semantic_corpus_run.py:32,
  55-61`).
- `_PLAN` is `graphify-out/graphify-semantic-corpus`, which `.gitignore:57` ignores and
  `git ls-tree -r d8114ab1 -- graphify-out` confirms is **untracked**. So those tests SKIP on a
  fresh clone (`skipif(not _PLAN.is_dir())`) and FAIL only where the plan exists — i.e. on the
  authoring machine, which is exactly where `kb-ship` runs the gate.

The remedy already exists inside this commit: `_fresh_plan`
(`tests/test_graphify_semantic_corpus_run.py:1370-1396`) builds a plan carrying the current
schema, and its docstring says precisely why (*"any test that needs `_load_plan` to actually
strict-decode must build its own plan"*). It was written for the one new test and not applied
to the 20 it also fixes. Leaving them red defers a known-broken gate to "after the
architect's re-plan" — a state nothing in the repo enforces or tracks.

---

## P2

### P2-1 — the new pre-spend guard's **call site** is unarmed, and the arms spec declines it by name

`graphify_semantic_corpus_run.py:1074` is the one line that wires the guard into `execute()`.
No test executes it: `test_the_pre_spend_runtime_guard_refuses_a_runtime_that_moved_since_the_plan`
(`tests/test_graphify_semantic_corpus_run.py:1399-1458`) calls
`_assert_graphify_runtime_unchanged_since_plan` directly, and
`docs/research/reports/2026-08-21-426-runtime-derive-arms.toml:24-31` states R2 targets the
helper "never `execute()` itself".

`probes-need-a-control-arm.md` rule 2 names this case exactly: *"Deleting the line that CALLS
a function is usually the realistic break; renaming its definition is not."* Deleting
`:1074` leaves every test green and the sweep clean, and the thing lost is a **pre-spend**
refusal on a ~$65 run.

The author's caution is defensible on its own terms (a full `execute()` arm reaches a real
Claude subprocess if the guard is neutered — which is the point of the guard). But that is an
argument against one particular arm, not against any coverage. Two bounded options the commit
did not take: monkeypatch `_extract_corpus` (or `graphify_semantic_slice.preflight`) so a
neutered guard reaches a stub rather than a provider; or, at minimum, a source-level wiring
assertion (`inspect.getsource(execute)` / `ast`) that fails when the call disappears. The
repo already treats "a validator nothing calls is not a gate" as a known class.

### P2-2 — `_stage_plan_context` now compares the plan's runtime against itself, so the staging path lost its runtime cross-check entirely

`graphify_semantic_corpus.py:2414-2417` passes `config.graphify_runtime` into `_cross_reasons`.
Downstream, `_config_reasons` (`:1684-1685`) evaluates `if runtime != config.graphify_runtime`
— structurally always `False` here, so `plan-graphify-runtime-mismatch` is **unreachable** on
this path; and `_effective_config` (`:1691-1693`) then derives `expected.graphify_runtime`
and `expected.graphify_version` from that same value, so `config-contract-mismatch` cannot fire
on the runtime fields either.

Before this commit, `_effective_config` read the frozen `_ACCEPTED_GRAPHIFY_RUNTIME`, so a plan
recorded under a *different module version's* constant was caught at staging. That check is now
gone from `stage_chunk` (`:2311-2317`) and from `verify_staged_chunk`'s plan reload. The comment
at `:2409-2413` argues `verify_plan` and `execute()`'s guard both cover it — true for the
`corpus_main run` path, and `stage_chunk` has no other production caller
(`graphify_semantic_corpus_run.py:784` only). So the exposure is narrow. But the reasoning
given is about **cost** ("re-measuring per chunk would spend a subprocess call 58 times"),
which argues for hoisting the measurement into `_RunContext` and threading it down — not for
substituting a value that makes the comparison a tautology. As written, a reader who greps
`plan-graphify-runtime-mismatch` will believe the staging path checks something it cannot.

### P2-3 — `verify_plan`'s docstring still promises it does not invoke Graphify; it now does

`graphify_semantic_corpus.py:1813`: `"""Rehash and cross-check a plan without mutating it or
invoking Graphify."""` — unchanged by this commit. As of `:1846` it calls `_measured_runtime`
→ `runtime_identity` → `graphify_env.assert_pinned_graphify` → `running_graphify_version`,
which `subprocess.run`s `.venv/bin/graphify --version` (`graphify_env.py:129-149`), and
`graphify_sdk.public_api_fingerprint()`, which imports the Graphify SDK
(`graphify_sdk.py:31-37`). `_effective_config`'s own new comment (`:753-758`) acknowledges the
subprocess. `tool-currency-and-native-first.md` rule 5 ("sync the describing docs in the SAME
change") is the applicable house rule; the docstring is the describing doc closest to the code.

### P2-4 — the pre-spend refusal message prints only the two fields most likely to be identical

`graphify_semantic_corpus_run.py:1042-1046` raises
`f"Graphify runtime changed after plan: plan={config.graphify_version} live={preflight_receipt.graphify_version}"`.

The condition (`:1039-1041`) fires on **whole-struct** inequality of `RuntimeIdentity`, whose
other fields are `executable`, `sdk_fingerprint_sha256`, `wheel_sha256`, `sdist_sha256`,
`schema_version` (`graphify_baseline.py:121-131`). A same-version change — a re-locked wheel
digest, a moved executable path, an SDK signature change at one version — produces
`plan=0.9.48 live=0.9.48`: a refusal asserting that two identical values differ. Print the
differing field(s), or the structs.

Related and benign: the second clause (`preflight_receipt.graphify_version !=
config.graphify_version`) is implied by the first. `runtime_identity` asserts
`{version, cli_version, sdk_version} == {pinned}` (`graphify_baseline.py:379-385`), and
`preflight` sets `graphify_version=running_sdk_version()` alongside
`graphify_runtime=runtime_identity(...)` (`graphify_semantic_slice.py:988-989`), so the two
can never disagree once the struct matches. Redundancy is fine here; it is worth knowing it
buys nothing.

### P2-5 — the cap fixes exactly one restart and leaves the second with the identical failure, unannounced

The F3 arithmetic checks out (58 × 1.12 = 64.96; 2 × 64.96 = 129.92; 140.0 ≈ +7.8%), and the
"~31" threshold is right (1.12N + 64.96 > 100 ⟹ N > 31.3). But at 140.0 a **second**
interruption reproduces the original defect verbatim: 3 × 64.96 = 194.88 > 140, so the plan
becomes uncompletable again, and nothing surfaces that before the money is spent.

`seeded_spend` (`graphify_semantic_corpus_run.py:247-274`) is the natural place, and its own
docstring already makes the argument for going one step further: *"a run that hit the cap at
chunk 40 and was restarted must refuse BEFORE the first provider call, not discover it after
paying for chunk 41."* The same reasoning applies to `carried + (len(ledger.chunks) ×
measured_per_chunk) > limit` — a projection, refused or at minimum warned, up front. Today
`seeded_spend` only refuses when `carried` **alone** already exceeds the cap.

### P2-6 — the slice task's 30m timeout is justified by a measurement taken under a different profile

`mise.toml:668-672` justifies `timeout = "30m"` on `kb-graphify-semantic-slice` with *"the
measured chunk-1 lower bound is 659.5s (see `_INFERENCE_TIMEOUT_SECONDS`'s comment)"*. That
comment (`graphify_semantic_corpus.py:54-59`) measures **corpus** chunk 1, and the corpus runs
`CORPUS_PROFILE` — `claude-opus-5`, `max_output_tokens=8192`, `effort="high"`
(`graphify_semantic_slice.py:562-572`). The slice runs `SLICE_PROFILE` — a different model,
`max_output_tokens=4096`, `effort=""` (`:538-548`). The number is real and correctly cited; it
just does not describe the task it is being used to size. This is
`verify-before-advancing.md` § *Carry a fact's CONDITION*.

### P2-7 — the `pyproject.toml` suppression is file-wide and permanent for a reason that names three functions, and the alternative refactor is smaller than described

`pyproject.toml:179-187` adds `"python/src/kb_setup/graphify_semantic_corpus.py" = ["PLR0913",
"PLR0917"]`.

In fairness, I measured the scope and it is currently exact — an AST walk of the committed
file finds exactly three functions over the limit, and they are the three the comment names:
`plan_source` (:1345, 2 positional / 6 total), `_config_reasons` (:1668, 6/6), `_cross_reasons`
(:1722, 6/6). Both codes are needed (`plan_source` trips only PLR0913) and both are **stable**,
not preview, in the pinned ruff 0.16.3. The reason is documented, which is what
`zero-skip-policy.md` rule 1 asks for.

Two things it does not say. The ignore is file-wide over a 3,300-line module, so every future
6-argument function there is silently exempt with no second review. And the stated alternative
— *"wrapping the existing five in a new struct … would be a second, separately-reviewable
refactor"* — is smaller than that framing implies: `inventory, advisories, exclusions, ledger,
config` are already produced as one tuple by `_typed_members(candidate)` and forwarded
unchanged from `_cross_reasons` to `_config_reasons`; passing that tuple would put both
functions at 3 arguments and need no new call-site logic. Worth stating whether that was
weighed and declined, since the ignore outlives the change that motivated it.

---

## Nits

- **N1** — `graphify_semantic_corpus.py:198-200`: *"this file is
  `python/src/kb_setup/graphify_semantic_corpus.py`, three parents up from the repository
  root."* Backwards — the repo root is three parents up from the file. The index is correct
  (`parents[3]`), and I confirmed the install is editable (`_editable_impl_kb_setup.pth` →
  `python/src`), so `__file__` really is the source tree.
- **N2** — `tests/test_graphify_semantic_corpus.py:2669-2686`: the docstring foregrounds
  `SystemExit` ("exactly what `graphify_env.assert_pinned_graphify` raises … a scenario this
  repo has hit for real"), but `_unmeasurable` raises only `ValueError`. The `SystemExit`
  direction is unarmed. Given P1-1, this is where the missing type would have shown up.
- **N3** — `tests/test_graphify_semantic_corpus.py:2601-2607` compares five `RuntimeIdentity`
  fields and omits `executable`, `sdk_fingerprint_sha256` and `schema_version`. The production
  comparison is whole-struct (msgspec generates `__eq__` over all fields), so the code is
  fine; the test just checks less than the thing it guards.
- **N4** — `mise.toml:683`: `timeout = "16h"` is a task-level property, and
  `kb-graphify-semantic-corpus` dispatches `plan | run | verify` from the same task
  (`graphify_semantic_corpus.py:3264`). So the two provider-free, seconds-to-minutes actions —
  including the `verify` the docs tell you to run first (`docs/…:421-423`) — inherit a 16-hour
  leash. mise cannot express a per-argument timeout; if the guard matters for the cheap
  actions, that wants separate tasks, and if it does not, saying so costs one line.
- **N5** — `provider-effort-mismatch` (`graphify_semantic_corpus.py:2273-2274, 2294`) can only
  fire alone when `config.effort != _PROFILE.effort`, and in that state `config-contract-mismatch`
  already refuses at verify, which gates `run`. So on every non-adversarial path it is
  implied by checks that ran earlier; its live value is against hand-substituted evidence,
  which is what its test constructs. Defence in depth is a fair call — but the commit message's
  claim that the run-time check is what "binds" effort overstates it; the plan-level
  recomputation does the work.

---

## What I checked and found clean

- **`except A, B:` without parentheses** — 12 occurrences in `graphify_semantic_corpus.py`
  (`:951, 1754, 1778, 1797, 1847, 2149, 2220, 2329, 2492, 2497, 2590, 2809, 3098`), including
  the new one at `:1847`. This is **PEP 758**, valid from Python 3.14. Control-armed:
  `ast.parse` on the committed bytes of both changed modules under the venv's Python 3.14.7
  returns `PARSE OK`.
- **The CLAUDE.md count.** `grep -c '^timeout = ' mise.toml` is **8** at `a67cbac4` and **10**
  at `d8114ab1`; `CLAUDE.md:176` now says 10. Both measured, both correct — including the
  commit's claim that the previous "7" was already stale.
- **`16h` / `30m` are valid mise durations.** `mise.toml`'s timeouts go through
  `duration::parse_duration` (`sources/mise/src/duration.rs:37`), which parses via
  `jiff::Span`; mise's own docs name `30s`, `5m`, `1h` as accepted
  (`sources/mise/docs/tasks/task-configuration.md:1063-1070`). This mattered because an
  unparsable value is only `warn!`ed and silently replaced by a default
  (`sources/mise/src/task/task_executor.rs:1348-1358`) — it would not fail loudly. Existing
  values in the file are all minute-spelled, so `16h` is the first hour-spelled one; it parses.
- **Arm-spec anchors.** All five `old` strings in
  `docs/research/reports/2026-08-21-426-runtime-derive-arms.toml` match the committed bytes,
  each exactly once (`grep -cF` per anchor: C0=1, R1=1, R2=1, R3=1, R4=1). R2's replacement
  (`if False:` for a 4-line condition) leaves the body correctly indented and parses. Each
  named test does assert the thing its arm removes, so R1/R3/R4 would go red. R2 would go red
  too — for the helper, not the wiring (P2-1).
- **Runtime-identity comparisons compare every field.** `RuntimeIdentity` is a `msgspec.Struct`
  (`graphify_baseline.py:121`), so `!=` at `graphify_semantic_corpus.py:1684` and
  `graphify_semantic_corpus_run.py:1039-1041` is whole-struct, not a field subset, and
  type-checked. No "passes when it should fail" there.
- **No stale cross-module runtime literal.** `graphify_semantic_slice._ACCEPTED_GRAPHIFY_RUNTIME`
  (`:310-327`) is already at 0.9.48 with `wheel_sha256=4f745d72…`, matching what
  `_measured_runtime` will record — so `_runtime_reasons`' receipt gate (`:1427-1461`) does not
  contradict the newly-derived plan.
- **All call sites of the changed helpers were updated.** `_effective_config` (2 sites),
  `_cross_reasons` (2), `_config_reasons` (2, one of them the adjusted test at
  `tests/test_graphify_semantic_corpus.py:2517`). No unpatched caller anywhere in `python/` or
  `tests/`.
- **New-test scaffolding is well-formed.** `Never` is imported
  (`tests/test_graphify_semantic_corpus.py:24`); `ClaudePreflight` (10 fields) and
  `AuthIdentity` (4 fields) match the construction at
  `tests/test_graphify_semantic_corpus_run.py:1414-1431`; `plan_source`'s new `repo_root` is
  keyword-only (AST: 2 positional / 6 total), so no positional caller breaks.
- **`provider-effort-mismatch` cannot fire spuriously on a real run.** `expected_adapter_argv`
  emits `--effort` only `if profile.effort` (`graphify_semantic_slice.py:758`) and
  `CORPUS_PROFILE.effort == "high"`; argv equality is separately required, so `_argv_value`
  returns `"high"` and the check passes. The empty-`config.effort` branch requires the flag
  absent, which is the correct pairing.
- **F3 arithmetic.** 58 × 1.12 = 64.96; 2 × 64.96 = 129.92; 140.0/129.92 = 1.078 ("+~8%"). The
  "past chunk ~31" threshold reproduces. The per-chunk ceiling product (1,450) is indeed
  unchanged.
- **`_MAX_ARGS` / `corpus_main` routing** and the `plan` route's new `repo_root=repo_root`
  (`:3296`) — correct, and `plan` is the one entry point that measures with a real root rather
  than the module default.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repository under review; commit `d8114ab1` read by ref.
- [jdx/mise](https://github.com/jdx/mise) — vendored pinned clone at `sources/mise` (`d9a27434`); read `src/duration.rs`, `src/task/task_executor.rs`, `docs/tasks/task-configuration.md` to settle whether `16h` parses and what happens when a timeout value does not.
- [astral-sh/ruff](https://github.com/astral-sh/ruff) — not read as source; the pinned binary's `ruff rule --output-format json PLR0917` was used to confirm the rule is stable rather than preview.
