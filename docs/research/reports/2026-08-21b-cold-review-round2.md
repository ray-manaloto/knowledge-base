# Cold review — `ebcf9fcb` (base `d8114ab1`) and `c720f1c9` (base `3d9bb3ff`)

Reviewed by ref only (`git show` / `git diff`); the working tree was never read
and nothing was modified, run, or staged. Installed-library facts come from
`.venv/lib/python3.14/site-packages/**` and from `git show <sha>:<path>` blobs.
Line numbers are as they appear **in the commit named for each finding**.

Ancestry confirmed linear: `d8114ab1 → ebcf9fcb → 3d9bb3ff → c720f1c9`, so
`git diff d8114ab1 ebcf9fcb` and `git diff 3d9bb3ff c720f1c9` are each the whole
commit.

---

## Commit `ebcf9fcb` — routing-scrub evidence, proxy exemption, re-derived arms

### P1

**P1-1 · The `execute()` half of the emission fix is asserted only in a test that
cannot execute its own assertions at this commit.**
`tests/test_graphify_semantic_corpus_run.py:767` (`assert "AWS_REGION" in
captured.err`) sits after `pytest.raises(RuntimeError, match="preflight
tripwire")` at `:763`. `_execute` drives `execute()` against `_PLAN`
(`tests/test_graphify_semantic_corpus_run.py:32`, the gitignored on-disk plan),
and `execute()` reaches `_load_plan(candidate)` at
`python/src/kb_setup/graphify_semantic_corpus_run.py:1073` — **before** the
stubbed `preflight` at `:1075-1077`. `_load_plan` strict-decodes
`execution-config.json` into `CorpusExecutionConfig`
(`graphify_semantic_corpus_run.py:1017-1021`), which the commit's own message
records as raising `msgspec.ValidationError` for the whole 20-test class here.
`msgspec.ValidationError` is not `RuntimeError`, so the test errors at `:763`
and every line this commit added below it is unreached.

Consequence: of the three call sites P1-1 claims to have wired
(`build_candidate` `graphify_semantic_slice.py:1988`, `semantic_main` `:2126`,
`execute` `graphify_semantic_corpus_run.py:1070`), two have green arms and the
third — the one that spends the most money — has none. Deleting
`report_routing_scrub` from `execute()` would be invisible to the suite for the
same reason the P1-1 defect was invisible before.

### P2

**P2-1 · The proxy exemption makes `preflight`'s refusal reachable from a
production CLI entry point with no handler, changing behaviour for proxied
hosts.**
`graphify_semantic_slice.py:858-860` filters `_ROUTE_OVERRIDE_PROXY_NAMES`
(`:176-183`) out of the scrub while `preflight` keeps refusing all 37
(`:1026-1028`, reading `_ROUTE_OVERRIDE_NAMES` at `:113-152` — counted, 37 names,
33 non-proxy, matching the docstring). `semantic_main` scrubs at `:2126` and then
calls `preflight` directly at `:2135`; `cli._run` dispatches this command at
`python/src/kb_setup/cli.py:243-246` inside no `try`/`except`, and `cli.main`
(`:34-51`) adds none. On a host carrying `HTTP_PROXY`, `mise run
kb-graphify-semantic-slice preflight` now exits on an uncaught
`ValueError: forbidden routing environment names: HTTP_PROXY` traceback; at
`d8114ab1` the scrub deleted that name and the command ran. The commit message's
"uncaught, as before" is accurate about the raise statement and not about its
reachability — the scrub is what made it unreachable. Same for
`graphify_semantic_corpus_run.execute` at `:1070-1076`.

This may be the intended trade (the comment at `:155-175` argues a loud refusal
beats a silent direct connection), but nothing converts it into an exit code or
a message, and no test covers the proxied-host path.

**P2-2 · The exemption — and the refusal it defers to — is uppercase-only, so
the stated justification covers only half of real proxy configuration.**
`_ROUTE_OVERRIDE_PROXY_NAMES` (`:176-183`) lists only
`HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY`/`NO_PROXY`. The comment justifies keeping
them for "the in-process graphify SDK, whose httpx client defaults to
`trust_env=True`" (`:169-171`), but httpx resolves environment proxies through
`urllib.request.getproxies()` (`.venv/lib/python3.14/site-packages/httpx/_utils.py:7`
and `:37`), which reads the **lowercase** `http_proxy`/`https_proxy`/`all_proxy`/
`no_proxy` first; `git` reads the lowercase forms too. So the lowercase spelling
was never scrubbed (nothing changed for it) and is also never refused — the
"loud refusal" P2-1 above trades for does not exist on a host that uses the more
common spelling. `probes-need-a-control-arm.md` rule 3 (a token spelling is a
bound) applies to the name set itself.

*Control arm run for the comment's own claim, and it holds:*
`grep -rl 'HTTP_PROXY\|HTTPS_PROXY\|ALL_PROXY\|NO_PROXY'
.venv/lib/python3.14/site-packages/graphify/` → **no files**; control
`grep -rl 'GEMINI_API_KEY' …` → 3+ files. The probe discriminates, so
"no proxy name appears anywhere in graphify's installed source" is CONFIRMED.

### nits

**nit-1 · A test docstring describes a guard that does not exist.**
`tests/test_graphify_semantic_slice.py:437` — "The `if removed:` guard at every
one of the three call sites is identical in shape". There is no such guard at any
call site; all three are bare one-line calls (`graphify_semantic_slice.py:1988`,
`:2126`, `graphify_semantic_corpus_run.py:1070-1072`). The guard lives once
inside `report_routing_scrub` (`graphify_semantic_slice.py:880-881`), which the
function's own docstring states correctly at `:875-878`. The test docstring
contradicts the function it exercises.

**nit-2 · `scrub_route_overrides`'s summary line is now over-broad.**
`graphify_semantic_slice.py:820` still reads "Delete every forbidden ROUTING name
so the refusal never has to fire (#334)", while `:837-849` documents four names
it deliberately leaves in place *so that* the refusal fires. The first line is
what a reader sees in `help()` and in an IDE tooltip.

**nit-3 · `test_execute_scrubs_routing_overrides_before_preflight` has no skip
guard for its on-disk dependency.**
`tests/test_graphify_semantic_corpus_run.py:723`; the docstring at `:747-749`
justifies omitting `@_needs_driver` on the grounds that the test never reaches
`_extract_corpus` or the provider binaries — true, but it does reach
`_load_plan(_PLAN)`, so on a host without the gitignored plan it errors rather
than skipping. `_needs_driver` (`:707-710`) already tests `_PLAN.is_dir()`.

---

## Commit `c720f1c9` — widened catch, `live_runtime`, arg-count suppression removal

### P1

**P1-1 · `stage_chunk(..., live_runtime=)` replaces one tautology with another
that is equally unreachable from the only production caller.**
The stated defect (`_stage_plan_context` comparing the plan's runtime against
itself) is real. But `_stage_completed_chunk` passes
`context.preflight_receipt.graphify_runtime`
(`python/src/kb_setup/graphify_semantic_corpus_run.py:801`), and `execute()`
has already refused at `:1094`
(`_assert_graphify_runtime_unchanged_since_plan`) unless
`preflight_receipt.graphify_runtime == config.graphify_runtime`. Every path to
`stage_chunk` runs after that guard, with the same two objects and no
re-measurement in between (`:1095-1220`). So at
`python/src/kb_setup/graphify_semantic_corpus.py:1897`
(`if runtime != config.graphify_runtime:`) the condition is still structurally
false on the staging path, and the runtime half of the `_effective_config`
recomputation at `:1904-1921` is still not exercised there.
`plan-graphify-runtime-mismatch` and the runtime half of
`config-contract-mismatch` remain exactly as unreachable from production as
before the change.

The comment at `graphify_semantic_corpus.py:2645-2653` states the mechanism
("this function and `execute`'s pre-spend guard both read the SAME preflight
measurement") without drawing the consequence that follows from it. The only
thing exercising the restored reasons is
`tests/test_graphify_semantic_corpus.py:2919`, which injects a disagreement
`execute()` cannot produce. The change is a real improvement for a *direct*
`stage_chunk` caller and is not a regression — but "made
`plan-graphify-runtime-mismatch` unreachable on the staging path … (P2-2)" is not
resolved for the caller that wires it.

**P1-2 · Both files edited to fix the restart wording now assert the opposite of
the code.**
`docs/agents/graphify-semantic-corpus.md:435-437` — "A restart **re-publishes**
already-staged evidence … `_verified_stages` **re-publishes** every chunk whose
stage directory already holds verified evidence" — and `mise.toml:684` —
"`_verified_stages` **re-publishes** already-staged chunks so their evidence is
not duplicated" (self-contradictory in one clause, the same shape the commit set
out to remove).

The code does the opposite:
- `_verified_stages` (`graphify_semantic_corpus_run.py:962-1000`) only calls
  `verify_staged_chunk`; it writes nothing.
- `_resolve_existing_stage` returns `None` meaning REPAID, and its docstring says
  "so this pass **must not re-publish it**" (`:884`).
- the module docstring says a verified chunk "is **skipped rather than
  re-published**" (`:23-24`).
- `_dispose` appends the ordinal to `repaid` and returns without staging
  (`:1208-1218`).

The money half of both edits ("Graphify re-buys EVERY chunk at full price on
every restart") is correct and matches `_resolve_existing_stage`'s measured
argument at `:889-899`. It is the *mechanism* sentence that is backwards, in the
commit whose P1-2 exists to correct that sentence.

### P2

**P2-1 · Four of the seven newly named exception types are untested, including
the two the comment says are reachable.**
`graphify_semantic_corpus.py:2080` names `ValueError, TypeError, LookupError,
OSError, ImportError, RuntimeError, SystemExit`; the parametrization at
`tests/test_graphify_semantic_corpus.py:2953-2967` covers only ValueError /
TypeError / SystemExit. The comment at `:2054-2079` cites reachable raise sites
for `RuntimeError` (`graphify_sdk.py:250`, reached via `graphify_env.py:195`) and
`ImportError` (`graphify_sdk.py:184`, reached at `graphify_baseline.py:375`) —
both **CONFIRMED** by reading those files — yet neither is armed, so narrowing
the union back to `(ValueError, TypeError, SystemExit)` passes the entire suite.
That is precisely the regression P1-1 of this commit was raised about.

Secondary concern on the same line: `LookupError` subsumes `KeyError`/
`IndexError` and `RuntimeError` subsumes `NotImplementedError`/`RecursionError`,
so a programming error inside the measurement chain is now reported to the
operator as `plan-graphify-runtime-unmeasurable` — a refusal whose message names
a cause it did not establish.

**P2-2 · The new `verify_plan` docstring gets the mechanism of its own
correction wrong, twice.**
`graphify_semantic_corpus.py:2027-2029`: "twice each, once directly and once
again inside the version-agreement check `runtime_identity` performs on itself."
That check is `graphify_baseline.py:381-386`
(`{identity.version, identity.cli_version, identity.sdk_version} !=
{pinned_graphify_version(repo_root)}`), which reads `pyproject.toml` and spawns
nothing and imports nothing. The actual second `graphify --version` is the
`cli_version=` field at `graphify_baseline.py:374`; the actual second signature
sweep is `contract_errors` (`graphify_sdk.py:229-243`) reached from
`assert_pinned_graphify` — i.e. inside the call the sentence already credits as
"directly".
Also "imports the Graphify SDK … twice": graphify is imported once, at
`kb_setup.graphify_sdk` module import (`graphify_sdk.py:31-37`);
`public_api_fingerprint()` (`:187-192`) only runs `inspect.signature` over
symbols already bound at import.
The docstring's headline claim — that `verify_plan` is not free of Graphify — is
correct and worth keeping; the parenthetical explanation is not.

**P2-3 · The identical stale-count defect was fixed in one comment and left in
its neighbour.**
`graphify_semantic_corpus.py:2017-2018` still says `verify_plan` has "17 existing
callers (13 tests, 2 positional in `graphify_semantic_corpus_prototype.py`,
`verify_execution_modes`, `corpus_main`)". Measured at this commit
(`git grep -n "verify_plan(" c720f1c9 -- '*.py'`, minus the definition): **23** —
19 in `tests/test_graphify_semantic_corpus.py`, 2 in
`python/src/kb_setup/graphify_semantic_corpus_prototype.py`,
`verify_execution_modes` (`:3326`), `corpus_main` (`:3539`). The commit
explicitly re-counted the `plan_source` comment one function above (14 → 19,
which I independently confirm is 19) and treats a stale count as a defect; this
one shares the same "13 tests" figure and was not re-derived.

**P2-4 · A live caller of the changed `stage_chunk` signature is left broken and
outside every gate.**
`docs/agents/evidence/issue-301/prototype-corrected-launcher.py:269` calls
`stage_chunk(candidate, cache_root, request)` with no `live_runtime`, which is
now a required keyword-only parameter (`graphify_semantic_corpus.py:2548-2549`).
The commit's justification is accurate — `hk.pkl:252` sets
`pyGlob = List("python/src/**/*.py", "tests/**/*.py")` and the ty step checks
`python/src tests` only, so nothing will report it. Recording it because the file
is executable Python that no longer runs, not an inert transcript. (Whether it
"already fails ruff/ty today for an unrelated pre-existing reason" is
**UNVERIFIED** — running those tools is a denied/mutating action here.)

**P2-5 · Four "the pinned 0.9.45" citations survive under a 0.9.48 pin, and one
of them is newly promoted to load-bearing.**
`graphify_semantic_corpus.py:877`, `graphify_semantic_corpus_run.py:31`, `:104`,
`:890` all label their AST-walk evidence "the pinned 0.9.45", while
`pyproject.toml:32` pins `graphifyy[all]==0.9.48` and the installed distribution
is `graphifyy-0.9.48.dist-info`. `mise.toml:688` now points the reader at one of
those comments as the authority for the restart claim. The *substance* still
holds at 0.9.48 — `load_cached` is imported only by `graphify/cache.py` and
`graphify/extract.py` in the installed tree, never by `graphify/llm.py`, so
`extract_corpus_parallel`'s chain still has no cache read — but the condition
attached to the measurement is stale, which is the failure
`verify-before-advancing.md` § "Carry a fact's CONDITION" names.

### nits

**nit-1 · The N1 fix reverses the direction and keeps the wrong count.**
`graphify_semantic_corpus.py:201`: "the repository root is three parents up from
the file (`parents[3]`)". For
`<root>/python/src/kb_setup/graphify_semantic_corpus.py`, `parents[0]` is
`kb_setup`, `parents[1]` is `src`, `parents[2]` is `python`, `parents[3]` is the
root — the **fourth** parent. "Three parents up from the file" is `parents[2]`.
The original said "three parents up from the repository root"; the correction
fixed the direction and carried the off-by-one through.

**nit-2 · `mise.toml:673-674` contradicts the figure it cites in the same
sentence.** "took 54.6s elapsed … (`adapter-metadata.json`: duration_ms 54203…)".
54203 ms is 54.2 s. (Verified from the comment's own citation only; the cited
file is under gitignored `graphify-out/` and was not read.)

**nit-3 · The arms spec's reason for leaving `plan-graphify-runtime-unmeasurable`
unarmed is contradicted by the module it arms.**
`docs/research/reports/2026-08-21-426-runtime-derive-arms.toml:16-18` — "reaching
it requires patching `graphify_baseline.runtime_identity` or `graphify_env` to
raise, which is a heavier fixture than this spec's other rows". But
`_measured_runtime` exists precisely so a test can patch **one name in this
module** — its docstring says so at `graphify_semantic_corpus.py:219-224` — and
the positive test does exactly that (`tests/test_graphify_semantic_corpus.py:2989`,
`monkeypatch.setattr(graphify_semantic_corpus, "_measured_runtime", …)`). The
`except` line at `graphify_semantic_corpus.py:2080` is a unique anchor, so an arm
costs no more than R1/R3/R4 and would close P2-1 above.

**nit-4 · A safety argument lists the wrong statements.**
`tests/test_graphify_semantic_corpus_run.py:1496` — "`execute()`'s own ordering
puts nothing that spends between `preflight` and the guard (routing scrub,
`_load_plan`, `_run_namespace` are all providers-free)". All three named
statements run *before* `preflight`
(`graphify_semantic_corpus_run.py:1085-1090`); between `preflight` (`:1091-1093`)
and the guard (`:1094`) there is nothing at all. The conclusion is right; the
evidence cited for it is not.

**nit-5 · The test-helper default restores the plan-vs-plan comparison
everywhere except one test.**
`tests/test_graphify_semantic_corpus.py:2038` and `:2470` default
`live_runtime` to `_plan_runtime(candidate)` (`:1999-2007`), so every
pre-existing staging test still compares the plan's runtime with itself. That is
the right call for preserving those tests' meaning, but it means exactly one test
(`:2919`) stands between the codebase and a re-introduction of P2-2 — and per
P1-1 above, that test exercises a state production cannot reach.

---

## Do the two commits contradict each other?

**Yes, on one point, and it is the currency one.** `ebcf9fcb` re-states
throughout `graphify_semantic_slice.py:339-455` that the attested and installed
Graphify runtime is **0.9.48** (`_ACCEPTED_GRAPHIFY_RUNTIME.version` `:349`,
`_CURRENT_GRAPHIFY_RUNTIME.version` `:446`), consistent with
`pyproject.toml:32`. `c720f1c9` edits `graphify_semantic_corpus_run.py` and
`graphify_semantic_corpus.py` while leaving four "the pinned **0.9.45**"
evidence labels standing (`corpus.py:877`, `run.py:31`, `:104`, `:890`) and adds
a new `mise.toml:688` pointer to one of them. See P2-5.

**Everywhere else they compose cleanly.** `c720f1c9` preserves `ebcf9fcb`'s
`report_routing_scrub("execute", …)` verbatim
(`graphify_semantic_corpus_run.py:1085-1087`); no `c720f1c9` edit touches the
scrub, the proxy set, `preflight`, or `graphify_env.py`, and `ebcf9fcb`'s new
`graphify_env.py:25-31` note remains true at `c720f1c9`. The
`_PlanMembers`/`PlanSourceOptions`/`live_runtime` refactors do not intersect the
slice module at all.

---

## What I checked and found clean

**Arms spec (`c720f1c9`).** All six `old` anchors match the committed source
**exactly once**, with correct surrounding context: C0
(`graphify_semantic_corpus.py:226`), R1 (`:1897-1898`), R2
(`graphify_semantic_corpus_run.py:1051`), R2b (`:1094`), R3
(`graphify_semantic_corpus.py:2526-2527`), R4 (`:93`). R2b's `new` (`pass  #
…`) is syntactically valid at that indent and leaves no unused-name break.

**R2b's safety claim.** With the guard call deleted, `execute()` proceeds through
`semantic_cache.mkdir`, `trusted_evidence_dir`, `_RunContext`, `_adapter_overlay`
(`graphify_semantic_corpus_run.py:436-468` — `shutil.which` + `sha256_file` +
`symlink_to`, no subprocess), `clear_stale_evidence`, `_verified_stages`
(filesystem only), and then hits the stubbed `seeded_spend` (`:1152`) which raises
`AssertionError`. Under `pytest.raises(ValueError, match="Graphify runtime
changed after plan")` that fails the test. Checked the whole-suite case too:
every other `execute()`-driving test stubs `_extract_corpus`
(`tests/test_graphify_semantic_corpus_run.py:693`), so a sweep cannot reach a
real provider either.

**The arg-count suppression is genuinely gone.**
`git grep -n "PLR0913\|PLR0917" c720f1c9` returns only a prose mention in a
docstring; `pyproject.toml` has no per-file entry. Statically re-derived the
reason it passes: the widest signature in `graphify_semantic_corpus.py` is now
5 parameters (`_effective_config`, `_run_artifact`, `_run_reconciliation_reasons`,
`_source_reasons`, `plan_source`, `_intentional_exclusion`), none over the
default `max-args`/`max-positional-args` of 5, and no single-line `def` hides a
wider one at `line-length = 100`.

**Call-site counts re-derived rather than trusted.** `plan_source` has exactly
**19** call sites at `c720f1c9` (18 across the two test modules + `corpus_main`),
matching the re-counted comment; exactly 3 of them pass a non-default value, and
exactly those 3 changed in the diff.

**No caller left mismatched by the refactors** (inside the linted tree):
`_config_reasons` and `_cross_reasons` have one caller each
(`graphify_semantic_corpus.py:1944`, `:2084`, `:2655` plus the test at `:2787`),
all passing `_PlanMembers`; `_stage_plan_context` has exactly one caller
(`:2552`); `stage_chunk` has three in-tree callers
(`graphify_semantic_corpus_run.py:784`, `tests/…corpus.py:2022`, `:2455`), all
passing `live_runtime`. `verify_staged_chunk` genuinely never reaches
`_cross_reasons` (`:2704-2760`), so no fallback was needed there.

**`live_runtime` has no default in production** — required keyword-only at
`graphify_semantic_corpus.py:2548-2549`; the defaulting is confined to the two
test helpers (see nit-5).

**Emission cannot pollute JSON stdout, and the tests capture the right stream.**
`events.warn` emits at WARNING (`events.py:240-245`); `sinks._human_handlers`
puts a `_MaxLevel(logging.WARNING)` filter on the stdout handler and
`setLevel(WARNING)` on the stderr handler (`sinks.py:333-337`), and `cli.main`
attaches `stdout_sink(...)` with `stream=None` (`cli.py:49`), so the split
applies in production. `semantic_main` prints its verdict with `print`
(`graphify_semantic_slice.py:2142`), so stdout stays JSON-only. The three
`capsys.readouterr().err` assertions are therefore the correct capture, and the
docstrings' reason for not using `caplog` (`events._ensure_sink` sets
`logger.propagate = False`, `events.py:216`) is accurate.
`_StdStreamHandler` resolving the stream per record (`sinks.py:197-227`) is what
makes this work under `capsys`.

**No env leak across the session.** In all four affected tests the ordering is
`monkeypatch.setenv(...)` (recorded against the real `os._Environ` object) and
only then `monkeypatch.setattr(os, "environ", dict(os.environ))`, so
`MonkeyPatch.undo` restores the real mapping through the reference it captured;
the scrub only ever mutates the copy, and `real_environ[...]` is read back
afterwards to prove it
(`tests/test_graphify_semantic_slice.py:290-296`, `:369-390`, `:412-425`;
`tests/test_graphify_semantic_corpus_run.py:753-766`).

**Stubs cannot reach a subprocess.** `build_candidate` calls the stubbed
`preflight` as its third statement, before any `tempfile`/`_admit_source`/
provider work (`graphify_semantic_slice.py:1988-1994`), and `semantic_main`'s
`preflight` route dispatches straight to it (`:2131-2135`).

**Every cited raise site in the widened-catch comment checks out**:
`graphify_baseline.py:361` is the `raise TypeError`, `:375` is the
`running_sdk_version()` call, `graphify_sdk.py:184` is
`metadata.version("graphifyy")`, `graphify_sdk.py:250` is `assert_public_sdk`'s
`raise RuntimeError`, `graphify_env.py:179`/`:186` are the two `raise SystemExit`
statements and `:195` is the `assert_public_sdk(pinned)` call.
Also checked and **refuted** as a gap: `subprocess.CalledProcessError` /
`TimeoutExpired` cannot escape, because `running_graphify_version` catches
`OSError, subprocess.SubprocessError` itself and returns `""`
(`graphify_env.py:145-153`).

**`except A, B, …:` is not a syntax bug** — PEP 758 on the 3.14 pin, and the form
already appears pre-existing at `graphify_env.py:126`, `:152`,
`graphify_semantic_corpus.py:1989`, `:2008`, `:2730`.

**`verify_plan` stays total against a missing member**: `_manifest_reasons`
returns `member-unavailable:<name>` / `candidate-unavailable` for any absent or
irregular file (`graphify_semantic_corpus.py:1566-1583`) and `verify_plan`
short-circuits on it before `_typed_members` can raise `FileNotFoundError`.

**Arithmetic and figures that do hold**: `_INFERENCE_TIMEOUT_SECONDS`'s 659.5 s
citation is real (`graphify_semantic_corpus.py:55-73`); 58 × ~11 min = ~10.6 h and
16 h ≈ 1.5×; `_MAX_TOTAL_COST_USD = 140.0` matches its own 58 × 1.12 → 64.96 → 2×
→ 129.92 → +8% derivation (`:82-93`); `SLICE_PROFILE` really is Haiku / 4096 /
`effort=""` and `CORPUS_PROFILE` really is Opus / 8192 / `effort="high"`
(`graphify_semantic_slice.py:577-611`), so `mise.toml:668-671`'s profile
distinction is correct; `_ROUTE_OVERRIDE_NAMES` really holds 37 names, 33 after
the proxy exclusion.

**The re-derived vacuity fix works.** `_runtime_reasons` reads
`_ACCEPTED_GRAPHIFY_RUNTIME` through a module-global lookup at call time
(`graphify_semantic_slice.py:1506-1510`), so the synthetic monkeypatch in
`test_non_authority_path_accepts_the_current_graphify_runtime` really does force
the two constants apart, and the added authority-path assertion really does
discriminate the one-entry tuple from the two-entry one. The two constants are
otherwise field-identical at this commit (`:339-356` vs `:446-454`), which is
what made the old form vacuous.

## GitHub repos touched

_None._ All evidence came from this repository's own history and from
already-installed distributions under `.venv/`
(`graphifyy-0.9.48`, `httpx`).
