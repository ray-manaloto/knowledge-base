---
name: adversarial-critic-graphify-ecosystem
description: Durable adversarial replay of the Graphify ecosystem implementation proposals.
---

# Adversarial critique — Graphify ecosystem (2026-08-12)

Proposals under critique:

1. Twenty reviewed projects are durably registered without unsafe graph ingestion.
2. Graphify CLI and SDK 0.9.41 strict contracts catch version and signature drift.
3. `kb-query` fails on rc0 truncation and stderr warnings while retaining output.
4. Generated JSON Schema/msgspec contracts and codegen checks are deterministic.
5. Metadata discovery is bounded and shell-safe.
6. Manifest scope and commit prevent unintended corpus growth.

Record replayed against: working-tree implementation at
`/private/tmp/kb-graphify-ecosystem.bmSQpv/repo` on base commit (recorded below),
including the source-group registry/schema/generated model, Graphify 0.9.41
CLI+SDK, mise task rendering, and the focused test corpus.

| # | Verdict | Proposal | Fires on its motivating cases? | Shape |
|---|---|---|---|---|
| 1 | KILL | Twenty projects registered, ingestion disabled | Data assertions fire; advertised default task rejects the valid registry and current-only check accepts 19 | 2; transition gate inert |
| 2 | KEEP | CLI+SDK 0.9.41 strict contract | Yes: version and signature mutations both fail | — |
| 3 | KEEP | rc0 truncation/stderr fails with output retained | Yes for the actual 0.9.41 banner and stderr | Narrow: pinned banner protocol |
| 4 | KEEP | Deterministic schema/msgspec codegen | Yes: exact-byte mutation returns 1; clean reruns are stable | — |
| 5 | KEEP | Bounded shell-safe discovery plan | Yes: 11th alternative and shell metacharacters fail before execution | — |
| 6 | KILL | Scope/commit prevent corpus growth | No for omitted scope: it still renders `scope=corpus` | 1, 5 |

## Verdict 1 — KILL: the default registry gate rejects the valid registry

Motivating defects: the twenty-project review must survive as tracked state, and
none of those metadata-only records may enter the graph. The data half is real:
`tests/test_source_groups.py:186` asserts 20 records and 20 disabled ingestion
policies; `python/src/kb_setup/source_groups.py:408` rejects graph ingestion for
every non-admitted source. The live registry parsed as 20 records (16 REVIEWING,
4 REJECTED), all 20 `graph_ingestion=DISABLED`.

The proposed default task does not reach that data. `mise.toml:525` renders its
missing optional path as an empty quoted argument, so `check_main` takes `Path("")`
instead of its default (`python/src/kb_setup/source_groups.py:103`). Replay:

```text
$ mise run kb-source-groups-check
[kb-source-groups-check] $ uv run kb-setup source-groups-check ''
source-groups-check: FAIL: [Errno 21] Is a directory: '/private/tmp/kb-graphify-ecosystem.bmSQpv/repo'
[kb-source-groups-check] ERROR task failed
rc=1
```

Control arm (the parser and registry are healthy when the path is explicit):

```text
$ mise run kb-source-groups-check -- sources/groups/graphify-ecosystem.toml
{"group_id": "graphify-ecosystem", "path": "/private/tmp/kb-graphify-ecosystem.bmSQpv/repo/sources/groups/graphify-ecosystem.toml", "source_count": 20, "statuses": {"REJECTED": 4, "REVIEWING": 16}}
rc=0
```

Shape: inverted selectivity. The advertised default denies the valid motivating
case. The transition validator at `source_groups.py:146` would reject record
removal, but no production call site invokes it; current-file validation alone
accepts any valid 19-record subset. The count assertion in pytest catches a
simple deletion, but the task does not.

```text
control-count 20
missing-record-current-check-count 19 accepted
missing-record-transition SourceGroupValidationError source records cannot be removed; retire or reject them instead: ['josu']
malformed-toml SourceGroupValidationError invalid source-group config: Expected ']' at the end of a table declaration (at line 1161, column 8)
unsafe-ingestion SourceGroupValidationError program-context-protocol: metadata-only source cannot enable graph ingestion
```

Placement cost is low (on-demand mise task/Python parser), but that does not
offset a default invocation that is broken or an unwired transition check.

## Verdict 2 — KEEP: CLI and SDK 0.9.41 strict contract

Motivating defect: a stale CLI or separately resolved SDK must not write/query a
graph under the reviewed 0.9.41 claim. `graphify_env.py:250` refuses an unknown or
mismatched CLI version, then calls the SDK contract; `graphify_sdk.py:85` compares
both distribution version and five exact public signatures.

```text
$ mise run kb-graphify-contract
Graphify CLI/SDK contract PASS: 0.9.41
  graphify.build.build(extractions: 'list[dict]', *, directed: 'bool' = False, dedup: 'bool' = True, dedup_llm_backend: 'str | None' = None, root: 'str | Path | None' = None) -> 'nx.Graph'
  graphify.build.build_from_json(extraction: 'dict', *, directed: 'bool' = False, root: 'str | Path | None' = None) -> 'nx.Graph'
  graphify.build.build_merge(new_chunks: 'list[dict]', graph_path: 'str | Path | None' = None, prune_sources: 'list[str] | None' = None, *, directed: 'bool | None' = None, dedup: 'bool' = True, dedup_llm_backend: 'str | None' = None, root: 'str | Path | None' = None) -> 'nx.Graph'
  graphify.extract.collect_files(target: 'Path', *, follow_symlinks: 'bool' = False, root: 'Path | None' = None) -> 'list[Path]'
  graphify.extract.extract(paths: 'list[Path]', cache_root: 'Path | None' = None, *, root: 'Path | None' = None, parallel: 'bool' = True, max_workers: 'int | None' = None, resolution_context_nodes: 'list[dict] | None' = None, resolution_context_edges: 'list[dict] | None' = None) -> 'dict'
rc=0
```

Hostile replay and control:

```text
control ()
unknown-version ('graphify SDK version 0.9.41 != accepted version 9.9.9',)
signature-drift ("graphify.build.build signature changed: expected (mutated: int) -> None; got (extractions: 'list[dict]', *, directed: 'bool' = False, dedup: 'bool' = True, dedup_llm_backend: 'str | None' = None, root: 'str | Path | None' = None) -> 'nx.Graph'",)
```

Malformed/missing `mise.toml` is converted to UNKNOWN and the outer gate refuses
it (`graphify_env.py:187`, `:254`), rather than authorizing an unverifiable run.
Nothing accepted fires earlier on the same CLI/SDK divergence.

Placement is on-demand Python plus a mise task; it adds no eager-session prose.

## Verdict 3 — KEEP: rc0 truncation/stderr refusal retains output

Motivating defect: Graphify 0.9.41 returned a visible prefix plus a truncation
warning with rc=0, which was consumed as complete evidence. The wrapper prints
both captured streams before classification, then returns 3 for the reviewed
uppercase banner or any nonblank child stderr (`graphify_ops.py:632`). Replay:

```text
historical-banner rc=3 stdout='[!] TRUNCATED: showing 20 of 200 nodes\npartial\n' stderr='ERROR: [kb-query] Graphify returned an incomplete TRUNCATED result with rc=0. Narrow the query or raise --budget; this prefix is not evidence of absence.\n'
stderr-warning rc=3 stdout='answer\n' stderr='coverage reduced\nERROR: [kb-query] Graphify emitted stderr while returning rc=0. The warning/error must be investigated before this result can be used.\n'
clean rc=0 stdout='answer\n'
```

Hostile mutations establish the exact boundary:

```text
case-mutated-banner rc=0 stdout='[!] Truncated: showing 20 of 200 nodes\npartial\n' stderr=''
answer-mentions-word rc=3 stdout='The constant is named TRUNCATED.\n' stderr='ERROR: [kb-query] Graphify returned an incomplete TRUNCATED result with rc=0. Narrow the query or raise --budget; this prefix is not evidence of absence.\n'
```

The case-changed banner is a real blind spot in `_run_graphify_query` considered
alone, and the substring match can false-positive on answer content. It does not
overturn the motivating replay because 0.9.41's actual banner is uppercase and
the accepted version contract fires first on a release/output-format change.
KEEP is therefore limited to the pinned 0.9.41 safety claim, not a general
warning-protocol detector.

Placement is on the query execution path, where the warning exists; no cheaper
sibling detects rc0 partial output after the CLI/SDK gate has passed.

## Verdict 4 — KEEP: deterministic schema-to-msgspec codegen check

Motivating defect: generated persistence models must not drift silently from
the reviewed JSON Schema or from the generator/formatter toolchain. The
generator refuses any datamodel-code-generator version other than 0.72.4
(`schemas/generate_source_groups.py:18`), disables timestamps, uses committed
templates, and the checker compares exact bytes from a repository-local temp
directory (`schemas/check_source_groups_codegen.py:12`). Ruff 0.16.2 and isort
8.0.1 are present in `uv.lock`.

```text
$ mise run kb-source-groups-codegen-check   # first run
source-groups codegen PASS
rc=0
$ mise run kb-source-groups-codegen-check   # second run
source-groups codegen PASS
rc=0
84f1e24c171d099a16054d25924eff3c1d3e987f7b8d2179fa7427220c00d66a  python/src/kb_setup/generated/source_groups.py
4edbac38189f0154fae6dfed70e0036edb70f02ee3d11b0579593ad1d8eb2529  schemas/source-groups.schema.json
```

Mutation/control replay, without changing repository bytes:

```text
source-groups codegen drift: run `mise run kb-source-groups-codegen`
mutated_rc 1
source-groups codegen PASS
control_rc 0
```

The schema's strict model base uses `forbid_unknown_fields=True`
(`generated/source_groups.py:11`), and malformed TOML/unknown fields are refused
at the parser boundary (`source_groups.py:85`).

Placement is an on-demand codegen check; it is the first proposal that can
observe schema/generated byte divergence.

## Verdict 5 — KEEP: bounded, shell-safe metadata discovery plan

Motivating defects: discovery must neither turn an incomplete GitHub prefix into
a consumer verdict nor let caller-supplied technology names alter the shell or
GitHub query. This proposal only emits a plan; it performs no HTTP, graph, or
registry mutation (`ecosystem_discovery.py:578`, `:634`). Every request caps
pages/results, and at most ten caller alternatives are accepted.

```text
max-alt requests 35 max_total_results 7000
eleven ValueError at most 10 alternatives may be searched per plan
reject 'x; touch /tmp/p' alternative names must be non-empty literal search terms
reject 'x$(touch /tmp/p)' alternative names must be non-empty literal search terms
reject 'x`id`' alternative names must be non-empty literal search terms
reject 'x&y' alternative names must be non-empty literal search terms
reject 'x|y' alternative names must be non-empty literal search terms
reject 'x\ny' alternative names must be non-empty literal search terms
reject 'x" repo:private' alternative names must be non-empty literal search terms
```

Real task hostile/control replay:

```text
$ mise run kb-ecosystem-discovery-plan -- 'cognee; touch /private/tmp/kb-ecosystem-injection-control-zqxjvbwkmpf'
ecosystem-discovery-plan: FAIL: alternative names must be non-empty literal search terms
rc=2
control: /private/tmp/kb-ecosystem-injection-control-zqxjvbwkmpf absent before and after

$ mise run kb-ecosystem-discovery-plan -- 'cognee # fork'
rc=0
hash-query ['"cognee # fork"', '"cognee # fork"']
```

The accepted `#` arm demonstrates that mise's `quote` in `mise.toml:537` keeps a
shell-sensitive but policy-valid literal intact; rejection is not merely a ban
on every punctuation character. Incomplete/rate-limited/partial adapter results
remain typed INCOMPLETE at `ecosystem_discovery.py:396`.

Placement is an on-demand pure planner. It incurs no eager cost and validation
fires before any future adapter could perform network work.

## Verdict 6 — KILL: optional scope is a saving throw, not a growth gate

Motivating defect: three peer-study repositories entered the corpus aggregate
and pushed `graph.json` 7.6 MiB over its 512 MiB cap
(`tests/test_graph_study_scope.py:4`). The partition itself works for an exact
`scope = study`: `graph.py:1307` excludes only that literal from corpus and the
study-scope tests pass. But the new manifest task defaults every omitted scope
to corpus (`mise.toml` task `kb-manifest-add`; `NewSource.scope` at
`manifest.py:238`). That is the historical invocation shape, so the proposal
does not fire unless the operator supplies the new convention.

```text
$ MISE_TASK_SHOW_FULL_CMD=1 mise run --dry-run kb-manifest-add -- https://github.com/example/peer
[kb-manifest-add] $ uv run kb-setup manifest-add 'https://github.com/example/peer' --ref 'main' --kind 'code' --scope 'corpus'
rc=0

$ MISE_TASK_SHOW_FULL_CMD=1 mise run --dry-run kb-manifest-add -- https://github.com/example/peer --scope study --commit AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
[kb-manifest-add] $ uv run kb-setup manifest-add 'https://github.com/example/peer' --ref 'main' --kind 'code' --scope 'study' --commit 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
rc=0
```

The malformed-scope control reveals a second fail-open boundary. The add path
rejects unknown scope, but the common manifest loader does not validate it
(`manifest.py:60`), and graph partitioning treats everything other than literal
`study` as corpus:

```text
$ mise run kb-manifest-add -- https://example.invalid/peer --scope quarantine
mise ERROR Invalid choice for option scope: quarantine, expected one of corpus, study
rc=1

loaded-scope quarantine
partition corpus
```

Exact-commit verification is sound when requested: the selected 40-hex commit
must be reachable from the declared ref (`manifest.py:96`, `:247`), and the
reachable-ancestor/unreachable/other-ref controls pass. It does not rescue the
growth claim: `--commit` is optional and scope still defaults to corpus.

Shape 1 plus shape 5: the gate fires only on the convention introduced by the
proposal, and the actual protection is the operator's judgement to type
`--scope study`. The explicit study partition insight survives; the claim that
the manifest task prevents unintended growth does not.

Placement is on the manifest-add path, but it is dominated by its own corpus
default: the unsafe branch proceeds before any scope-specific protection fires.
