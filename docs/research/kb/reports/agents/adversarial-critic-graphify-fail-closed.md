---
name: adversarial-critic-graphify-fail-closed
description: Replay of Graphify stabilization proposals against their motivating defects.
---

# Adversarial critique — Graphify fail-closed core and source workflow (2026-08-12)

Proposals under critique:

1. Single-owner Graphify dependency across `pyproject.toml`, `uv.lock`, `mise.toml`, and `mise.lock`.
2. Lock-stable `mise` task dependencies through `uv`.
3. Public-SDK fingerprint drift detection.
4. Fail-closed handling of warnings, truncation, partial results, AST-only deep queries, and required unclassified zero-node sources.
5. Exact source-group completeness, scope, and immutable usage evidence.
6. Deterministic code generation.
7. `currency.toml` coverage through `python_package`.

Record replayed against: commit `72c464caeb464d3e4ae4d5465e4759b9bbbd6531`
over base `dffe600a3111e4bec7c93cc17ca4ae9165d7875f`; the checked-out public
`mise`/`uv` tasks, focused mutation tests, and the committed ecosystem registry.
The derived `graphify-out/graph.json` and `graph-prose.json` are absent, so no
successful corpus build/query is claimed.

| # | Verdict | Proposal | Fires on its motivating cases? | Shape |
|---|---|---|---|---|
| 1 | KEEP | Single Graphify dependency owner plus locked `uv` sync | Yes: the old mise/pipx owner is absent, the exact Python pin is locked, and `mise deps` leaves all four owner/lock files byte-clean | — |
| 2 | KEEP | Public SDK signature/version fingerprint | Yes: the public task passes the reviewed 0.9.41 surface and both signature and version mutations refuse | — |
| 3 | KEEP, NARROWED | Typed fail-closed Graphify health | Historical rc=0 query truncation/stderr: YES. Build/extract/deep/partial/required-zero-node cases: 0; those types are not connected to those operations | 1, 3, 5 |
| 4 | KILL | Exact source-group completeness, scope, and immutable usage evidence | NO: identity, evidence path, and reviewed SHA can be replaced consistently and the public gate still passes; every source has ingestion disabled | 1, 4, 5 |
| 4a | FILE | Strict metadata registry and policy invariants | The duplicate/unknown/policy controls fire, but this is metadata validation rather than external evidence or corpus enforcement | — |
| 5 | KEEP, NARROWED | Deterministic source-group code generation | YES when the explicit codegen-check task runs: clean bytes pass and a one-line generated-file mutation returns 1; it is not in the default four ship gates | — |
| 6 | KEEP | Currency `python_package` ownership | YES: exact Python owner + installed uv CLI are checked; a non-exact requirement is DRIFT; the absent graph stamp is reported as rebuild pending | — |

## 1. Single dependency owner and lock-stable sync — KEEP

Restated: move `graphifyy[all]` from mise/pipx into the exported project runtime
dependencies, lock it in `uv.lock`, make `[deps.uv]` run `uv sync --locked`, and
remove the mise/mise-lock owner. The motivating defect is the live stale PATH
installation recorded at `python/src/kb_setup/currency/sync.py:5` and
`python/src/kb_setup/currency/sync.py:9`: bare `graphify` reached stale
`pipx-graphifyy/0.9.23` while the old mise pin said `0.9.25`. The immediately
preceding state also owned Graphify in `dffe600:mise.toml` as
`"pipx:graphifyy" = { version = "0.9.36", extras = ["all"] }`.

Replay:

| Case | Result |
|---|---|
| Current exact owner | FIRES/PASS: `pyproject.toml` declares `graphifyy[all]==0.9.41`; `uv.lock` contains package `graphifyy` 0.9.41 and the exact root requirement |
| Old mise owner | FIRES/PASS: no `pipx:graphifyy` declaration or lock entry remains in `mise.toml` / `mise.lock` |
| Lock stability | FIRES/PASS: `uv lock --check`, `mise deps`, a second `uv lock --check`, and `git diff --exit-code -- pyproject.toml uv.lock mise.toml mise.lock currency.toml` all returned 0 |
| Non-exact Python owner mutation | FIRES/REFUSES: `test_python_package_owner_requires_an_exact_project_pin` classifies `graphifyy[all]>=0.9.41` as DRIFT |

Verbatim public-path replay:

```text
Resolved 157 packages in 4ms
mise All dependencies are up to date
Resolved 157 packages in 4ms
```

The final `git diff --exit-code` emitted no output and returned 0. The focused
positive and negative currency-owner arms were included in this passing run:

```text
...................................................................      [100%]
```

What fires first: `mise deps` invokes the locked uv provider before a project
task needs the CLI/SDK; the later Graphify contract checks the resulting binary
and imports. They are complementary rather than mutually dominating.

Placement cost: project-local `pyproject.toml`, `uv.lock`, and `mise.toml`; no
eager agent prose is needed for enforcement. This catches the actual ownership
and stale-project-install class that motivated it.

## 2. Public SDK fingerprint — KEEP

Restated: before query or graph-writing work, require the uv environment's
Graphify distribution version and the signatures of every reviewed public SDK
symbol to match the 0.9.41 fingerprint in
`python/src/kb_setup/graphify_sdk.py:37`. The motivating defect is the prior
plan's CLI-only posture: a matching `graphify --version` did not prove the
library functions imported by this repository still had the reviewed call
contracts (`graphify_sdk.py:2-10`).

Replay:

| Case | Result |
|---|---|
| Installed 0.9.41 CLI + SDK | FIRES/PASS through `mise run kb-graphify-contract`; all 11 reviewed symbols and signatures print |
| Signature mutation | FIRES/REFUSES through `test_signature_drift_fails_closed` |
| Installed SDK version mutation | FIRES/REFUSES through `test_sdk_version_drift_fails_closed` |
| Real query/writer entry | FIRES FIRST via `assert_pinned_graphify`, which calls `assert_public_sdk`, before `query`, `build`, `watch`, merge/label/artifact writers, or skill refresh use Graphify |

Verbatim positive replay begins:

```text
[kb-graphify-contract] $ uv run kb-setup graphify-contract
Graphify CLI/SDK contract PASS: 0.9.41
  graphify.build.build(extractions: 'list[dict]', *, directed: 'bool' = False, dedup: 'bool' = True, dedup_llm_backend: 'str | None' = None, root: 'str | Path | None' = None) -> 'nx.Graph'
  graphify.build.build_from_json(extraction: 'dict', *, directed: 'bool' = False, root: 'str | Path | None' = None) -> 'nx.Graph'
  graphify.build.build_merge(new_chunks: 'list[dict]', graph_path: 'str | Path | None' = None, prune_sources: 'list[str] | None' = None, *, directed: 'bool | None' = None, dedup: 'bool' = True, dedup_llm_backend: 'str | None' = None, root: 'str | Path | None' = None) -> 'nx.Graph'
```

The task continued with the eight remaining reviewed signatures and returned 0.
The mutation control was:

```text
tests/test_graphify_sdk.py::test_signature_drift_fails_closed PASSED     [ 50%]
tests/test_graphify_sdk.py::test_sdk_version_drift_fails_closed PASSED   [100%]

============================== 2 passed in 0.10s ===============================
```

What fires first: import/version/signature validation precedes the actual
Graphify subprocess or writer. Placement is project code and a public mise task;
the repeated cost is local introspection of 11 functions, not eager prose or a
corpus build. The check fires on the motivating CLI-versus-SDK gap and the
negative arms establish that its pass is discriminating.

## 3. Fail-closed Graphify health — KEEP, NARROWED to the query wrapper

Restated: classify Graphify operations as complete/incomplete/failed and refuse
warnings, truncation, partial extraction, AST-only execution where deep output
was required, missing reflection/artifacts, scope mismatch, unclassified files,
and required sources producing zero nodes. The motivating record is:

- the real `278/562` query with an explicit truncation warning, preserved in
  `/Users/rmanaloto/.codex/memories/extensions/chronicle/resources/2026-08-12T22-25-00-nuKB-10min-memory-summary.md`;
- `docs/currency/graphify-watch-state.json:44-47`, where `sources/ruff`
  produced **0** nodes and `ty` only **36** while `mise`/`uv`/`codex` produced
  19,653/20,524/90,797; and
- the stated requirement for deep, reflection, artifact, and scope evidence in
  `python/src/kb_setup/graphify_health.py:123-133`.

Replay:

| Historical/mutation case | FIRES? | Evidence |
|---|---|---|
| rc=0 query output with `[!] TRUNCATED: showing 20 of 200 nodes` | FIRES | `test_rc_zero_truncation_banner_fails_closed` returns 3 |
| rc=0 query with nonempty stderr | FIRES | `test_rc_zero_stderr_fails_closed` returns 3 |
| rc=0 query saying only `PARTIAL: 278/562 nodes` | **NO** | public `graphify_ops.query` returns 0; the implementation recognizes only the substring `truncated` or stderr |
| Real required source `sources/ruff` produces zero nodes during `kb-build` | **NO** | no build/extract path constructs a `GraphifyEvidence` receipt |
| Required source is unclassified | **NO** | same: the library model refuses only if some caller supplies the path/policy, and no real caller does |
| AST mode when deep is required | **NO** | same: test-only evidence fields; no build/extract integration |
| Missing reflection, artifact, or expected corpus scope | **NO** | same: test-only evidence fields; no lifecycle integration |
| Missing/unknown build evidence | **BACKWARDS** | `assess(GraphifyOperation.BUILD)` with no evidence returns `COMPLETE` |

The 0-fire result for non-query operations is control-armed by the identical
source-call search. The query call is found; all five other operation call sites
are absent; a freshly invented absent enum term is also absent:

```text
nonquery_rc=1
python/src/kb_setup/graphify_ops.py:646:        graphify_health.GraphifyOperation.QUERY,
query_control_rc=0
fresh_absent_control_rc=1
```

The behavioral replay is verbatim:

```text
empty_build_evidence= GraphifyReceipt(operation=<GraphifyOperation.BUILD: 'build'>, state=<GraphifyState.COMPLETE: 'complete'>, returncode=0, reasons=(), stdout='', stderr='', detected_sources=None, extracted_sources=None, unclassified_files=0, zero_node_sources=0, mode=None, expected_artifacts=(), produced_artifacts=(), expected_scope=None, observed_scope=None)
explicit_required_zero= GraphifyReceipt(operation=<GraphifyOperation.EXTRACT: 'extract'>, state=<GraphifyState.INCOMPLETE: 'incomplete'>, returncode=0, reasons=('required-source-zero-nodes', 'zero-node-sources'), stdout='', stderr='', detected_sources=None, extracted_sources=None, unclassified_files=0, zero_node_sources=0, mode=None, expected_artifacts=(), produced_artifacts=(), expected_scope=None, observed_scope=None)
PARTIAL: 278/562 nodes
partial_without_marker_rc= 0
```

This settles three named kill shapes for the broad claim. Shape 1: build,
extract, deep, reflection, artifact, scope, and source-coverage receipts fire on
zero motivating lifecycle cases because no workflow populates them. Shape 3:
the docstring says unknowns are not converted to success, while an evidence-free
build is `COMPLETE`. Shape 5: the saving throw for query completeness is the
word `truncated` appearing in Graphify's prose, not a structured partial-count
contract; the same 278/562 arithmetic without that label passes.

What fires first: the existing graph-build validation and Graphify version
contract run; this health model never enters the non-query branch. Placement is
cheap project code, but unused code is inert regardless of placement.

Exact restriction that survives: **keep only the `kb-query` rule that an rc=0
result is refused when output contains `truncated` (case-insensitive) or stderr
is nonempty. Do not describe `graphify_health` as shared build/extract/source
health until real lifecycle adapters populate and require those receipts.** The
query restriction catches its own 278/562 motivating defect. Everything else is
file-worthy design reasoning, not implemented enforcement.

## 4. Exact source-group completeness/scope/immutable evidence — KILL

Restated: the committed `graphify-ecosystem` source group is claimed to be an
exact, complete census whose selected scope and revision-bound usage evidence
cannot drift silently. The motivating defects are the missed Graphify consumer
workflow, the need to distinguish real usage from declarations/removals, and the
requirement that reviewed paths/commits remain immutable. The proposal's own
anchors are `tests/test_source_groups.py:184-194` ("tracks every reviewed
project") and `python/src/kb_setup/source_groups.py:146-191` (transition
immutability).

Replay through the public `mise run kb-source-groups-check -- <path>` boundary:

| Mutation | FIRES? | Result |
|---|---|---|
| Current 20-record registry | PASS | 20 records: 16 REVIEWING, 4 REJECTED |
| Replace the reviewed `program-context-protocol` identity consistently with invented `ghost-context-protocol` | **NO** | same 20/16/4 PASS |
| Replace the exact usage path with `src/pcp/does-not-exist.py` and replace its reviewed/evidence SHA consistently | **NO** | same 20/16/4 PASS |
| Duplicate a source id | FIRES | FAIL, proving the gate can reject a structural mutation |
| Real ingestion/scope outcome | **NO** | all 20 records set `graph_ingestion`, `deep_extraction`, `reflection`, and `artifacts` to `DISABLED` |

Verbatim replay:

```text
{"group_id": "graphify-ecosystem", "path": "/var/folders/z4/0p475gq56vvczc3y4qlt60f80000gn/T/tmp.Z37PPSkYgp/identity.toml", "source_count": 20, "statuses": {"REJECTED": 4, "REVIEWING": 16}}
identity_swap_rc=0
{"group_id": "graphify-ecosystem", "path": "/var/folders/z4/0p475gq56vvczc3y4qlt60f80000gn/T/tmp.Z37PPSkYgp/evidence.toml", "source_count": 20, "statuses": {"REJECTED": 4, "REVIEWING": 16}}
evidence_swap_rc=0
source-groups-check: FAIL: duplicate source_id: ['program-context-protocol']
[kb-source-groups-check] ERROR task failed
duplicate_control_rc=1
```

The replay distinguishes structural validation from truth. The test named
`test_committed_ecosystem_registry_tracks_every_reviewed_project` asserts only
`len(config.sources) == 20`, status counts, and disabled ingestion. A same-count
identity substitution therefore passes. The immutable transition function is
not invoked by `source-groups-check`; a snapshot has no previous snapshot to
compare against. A path is checked only for repository-relative syntax, not for
existence at the retained commit or for the retained summary's content.

What fires first: the parser catches malformed TOML, unknown fields, duplicate
identities, and inconsistent policy states. Nothing later checks the census
against discovery output or the evidence against the remote commit, and the
disabled ingestion policies ensure these records cannot change a graph outcome.

This is shape 1 for completeness/immutability (zero motivating external-truth
cases), shape 4 for corpus impact (metadata-only by construction), and shape 5:
the human research that chose the 20 repositories and read their paths is the
saving throw, not the count/schema gate.

Do not build or describe the exactness claim. File the useful structure instead:
strict typed records, license/admission separation, selected-path syntax, and
policy-state validation are sound metadata controls. What would change the
verdict is a public gate that compares the committed identity set to a retained,
complete discovery receipt; resolves every evidence path at the reviewed SHA;
checks retained exact usage bytes or hashes; and compares transitions to a
prior committed registry. Until then, the exact replacement is: **"typed
metadata registry with within-snapshot invariants; census completeness, remote
evidence truth, and transition immutability are not verified by this task."**

## 5. Deterministic code generation — KEEP, NARROWED

Restated: generate the strict msgspec models from the JSON Schema with an exact
generator version, no timestamp, project-root formatter configuration, and an
exact-byte comparison task. The motivating defect is ordinary schema/generated
model drift: a structurally valid registry could otherwise be interpreted by a
stale checked-in model.

Replay:

| Case | Result |
|---|---|
| Checked-in schema/model | FIRES/PASS through `mise run kb-source-groups-codegen-check` |
| Generated model plus one control line | FIRES/REFUSES; exact-byte comparator returns 1 |
| Wrong generator version | FIRES before generation at `schemas/generate_source_groups.py:20-27` |
| Default `kb-gates` run | **NO invocation**: `GATE_TASKS` is only `lint`, `test`, `brain-audit`, `eval` |

Verbatim replay:

```text
[kb-source-groups-codegen-check] $ uv run --group codegen python -m schemas.che…
source-groups codegen PASS
```

Negative arm:

```text
source-groups codegen drift: run `mise run kb-source-groups-codegen`
mutated_codegen_rc=1
```

What fires first: when explicitly invoked, the exact generator-version check
precedes generation, then the byte comparator rejects drift. No accepted
default ship gate invokes it, so the surviving restriction is exact: **keep the
deterministic generator and explicit check task; do not claim the default full
gate suite certifies generated/schema parity.** Placement is an on-demand task
and isolated uv codegen group, so it has no eager-session cost.

## 6. Currency `python_package` — KEEP

Restated: teach the currency engine that Graphify is owned by an exact exported
Python requirement rather than a mise tool, reject dual owners, compare the uv
environment's CLI version to that requirement, probe the installed extras, and
retain the existing source/stamp checks. The motivating defect is the stale
mise/pipx PATH recorded at `python/src/kb_setup/currency/sync.py:5-11`, together
with the ownership move assessed in proposal 1.

Replay:

| Case | Result |
|---|---|
| Exact `graphifyy[all]==0.9.41` + `.venv/bin/graphify` 0.9.41 | FIRES/PASS for pin, resolution, and extras paths |
| Non-exact `graphifyy[all]>=0.9.41` mutation | FIRES/DRIFT in `test_python_package_owner_requires_an_exact_project_pin` |
| Both `mise_key` and `python_package` | FIRES at config load (`currency.toml` permits one owner) |
| No corpus build/stamp in this clean checkout | FIRES/DRIFT with `artifacts have never been stamped — rebuild pending` |

Verbatim public replay:

```text
[kb-currency-check] $ uv run kb-setup currency check --tool graphify
[currency] tool drift detected — run the tool-currency skill:
[currency]   graphify: build-stamp — artifacts have never been stamped — rebuild pending
[graph] no graph has been built here yet (no build stamp) — run `mise run kb-build`
```

This proposal does not launder the missing corpus build into green, which is the
important discrimination in this checkout. The command's rc remains 0 by the
currency workflow's pre-existing advisory design; the emitted DRIFT is the
result. `mise deps` fires first and uses `uv sync --locked`; currency then checks
the exact pyproject owner, the actual `.venv` executable, extras, manifest, and
stamp. Placement is the existing on-demand/session currency workflow rather
than new eager prose.

## What survives, and what the survivors do NOT cover

Survivors:

- KEEP the single pyproject/uv Graphify owner and locked `mise deps` provider.
- KEEP the public SDK version/signature contract.
- KEEP only the query wrapper's explicit rc=0 truncation/stderr refusal.
- FILE the strict source metadata schema/policy model, without its external
  exactness claims.
- KEEP the deterministic code generator and explicit byte-drift task, with the
  caveat that default ship gates do not invoke it.
- KEEP currency's `python_package` owner and uv-environment resolution check.

The survivors do **not** catch these motivating defects:

- a build/extract with partial source coverage;
- required `sources/ruff`-class zero-node output or a required unclassified
  path;
- AST-only output where deep extraction was promised;
- missing reflection, artifact, or expected corpus scope;
- an evidence-free build being classified `COMPLETE` by the health model;
- source-census substitution at constant count;
- fabricated/nonexistent evidence paths or a consistently rewritten reviewed
  SHA through the public source-group check; or
- schema/generated drift during the ordinary default gate suite unless the
  explicit codegen task is separately invoked.

The caller's record says the full default gates were green. That is compatible
with every residual above: the new source code compiles/tests, while no corpus
build/query completed and the codegen check is outside `GATE_TASKS`.

## Corpus build/query status

No corpus success is claimed. The recorded build attempt was stopped after
4m30. At re-verification time `graphify-out/` contained only `memory/`; there
was no `graph.json`, `graph-prose.json`, or build stamp. The current currency
task reported `artifacts have never been stamped — rebuild pending`.

Both query routes failed closed rather than producing an answer:

```text
ERROR: [kb-query] no graph at /private/tmp/kb-graphify-clean.55nHWG/repo/graphify-out/graph-prose.json — run `mise run kb-prose` first
[kb-query] ERROR task failed
```

```text
error: graph file not found: /private/tmp/kb-graphify-clean.55nHWG/repo/graphify-out/graph.json
```

Therefore the focused unit/task arms settle the contracts above, but they are
not a substitute for a completed 0.9.41 corpus build followed by real clean,
truncated, warning, partial, zero-node, and deep-required query/build replays.

## Re-verified before reporting

Immediately before this write-up I re-read:

- `python/src/kb_setup/graphify_health.py:136-179` and
  `python/src/kb_setup/graphify_ops.py:627-669` for the top health verdict;
- `python/src/kb_setup/source_groups.py:85-191` and
  `tests/test_source_groups.py:184-214` for the exactness verdict;
- `currency.toml:12-55` and
  `python/src/kb_setup/currency/sync.py:142-178` for Python ownership;
- `schemas/check_source_groups_codegen.py:12-24` for deterministic comparison;
  and
- `python/src/kb_setup/graphify_sdk.py:145-164` for the SDK contract.

HEAD remained `72c464caeb464d3e4ae4d5465e4759b9bbbd6531`, and `git diff
--exit-code HEAD --` over every critiqued implementation/config file returned
0. Only this report was untracked. None of the proposal surfaces had moved.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base)
  — read-only replay of commit `72c464c`; only this repository-path critique report
  was created locally.
