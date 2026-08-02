# Adversarial verification — "graphify cannot answer 'which tests cover this change'"

Date: 2026-08-01 · HEAD `99eb824` · graphify **0.9.31** (pinned; stamp
`graphify-out/.currency-stamp.json` reports `version: 0.9.31`, `built_at
2026-08-01T22:27:05+00:00`)

```
claim:     "graphify cannot answer 'which tests cover this change'"
refuted:   true
```

## Verdict

**REFUTED as a claim about graphify.** `graphify affected "<symbol>" --depth 1`
returns test functions with `file:line` under `tests/`, from the aggregate graph,
today. Worked example below.

**But it is currently TRUE as a statement about this repo's own code** — for a
wiring reason inside `kb_setup.graph`, not a graphify limitation. The distinction
is the whole finding: the gap analysis attributes to the tool a defect that lives
in one line of this repo's config.

## Probe

```
graphify affected "get_document_from_graph" --depth 1
```

## Control

Four arms, three of them positive (a probe that has only ever returned "absent"
is a coin with one face):

| arm | command | result |
|---|---|---|
| **negative** | `graphify affected "zzz_no_such_symbol_qqq" --depth 1` | `No unique node match for zzz_no_such_symbol_qqq` — the probe discriminates absence |
| **positive, test nodes returnable at all** | `graphify affected "_state" --depth 1` | 9 test functions, all `tests/test_currency_staleness.py:L…` |
| **positive, cross-FILE within one extraction** | `graphify affected "commit_file" --depth 1` | 17 test functions across `test_pr.py` + `test_review.py`, from a fixture defined in `tests/conftest.py` |
| **positive, test→SRC across a real package** | `graphify affected "get_document_from_graph" --depth 1` | test functions under `cognee-mcp/tests/` — see evidence |

Plus a same-syntax A/B that isolates the cause (below).

## Evidence (verbatim)

### The money probe — test nodes come back

```
$ graphify affected "get_document_from_graph" --depth 1
Affected nodes for get_document_from_graph()
Relations: calls, indirect_call, references, imports, imports_from, re_exports, inherits, extends, implements, uses, mixes_in, embeds, requires
Depth: 1
- cognee_client.py [imports] cognee-mcp/src/cognee_client.py:L24
- .get_document() [calls] cognee-mcp/src/cognee_client.py:L442
- get_chunk_neighbors_from_graph() [calls] cognee-mcp/src/retrieval_utils.py:L355
- test_get_document_from_graph_accepts_chunk_id_via_connections() [calls] cognee-mcp/tests/test_mcp_server_hardening.py:L426
- test_get_document_from_graph_uses_subgraph_sorts_and_truncates() [calls] cognee-mcp/tests/test_mcp_server_hardening.py:L395
rc=0
```

```
$ graphify affected "get_chunk_neighbors_from_graph" --depth 1
Affected nodes for get_chunk_neighbors_from_graph()
Relations: calls, indirect_call, references, imports, imports_from, re_exports, inherits, extends, implements, uses, mixes_in, embeds, requires
Depth: 1
- cognee_client.py [imports] cognee-mcp/src/cognee_client.py:L24
- .get_chunk_neighbors() [calls] cognee-mcp/src/cognee_client.py:L464
- test_get_chunk_neighbors_from_graph_filters_direction_and_target() [calls] cognee-mcp/tests/test_mcp_server_hardening.py:L452
- test_get_chunk_neighbors_from_graph_validates_inputs() [calls] cognee-mcp/tests/test_mcp_server_hardening.py:L471
rc=0
```

Those are literally "which tests exercise this symbol", answered by the command
the claim says cannot answer it.

### Control arm — bogus symbol

```
$ graphify affected "zzz_no_such_symbol_qqq" --depth 1
No unique node match for zzz_no_such_symbol_qqq
rc=0
```

### Control arm — test nodes ARE returnable (this repo's own tests)

```
$ graphify affected "_state" --depth 1
Affected nodes for _state()
Relations: calls, indirect_call, references, imports, imports_from, re_exports, inherits, extends, implements, uses, mixes_in, embeds, requires
Depth: 1
- test_a_new_and_unreadable_input_is_not_verifiable_not_ok() [calls] test_currency_staleness.py:L155
- test_absent_graph_is_never_built_even_with_a_stamp() [calls] test_currency_staleness.py:L305
- test_detector_fires_on_a_real_content_change() [calls] test_currency_staleness.py:L178
- test_restamp_artifacts_carries_inputs_forward_unchanged() [calls] test_currency_staleness.py:L379
- test_restamp_does_not_invent_an_empty_input_map() [calls] test_currency_staleness.py:L390
- test_silent_after_branch_round_trip_touching_sources() [calls] test_currency_staleness.py:L269
- test_silent_after_checkout_of_a_reverted_edit() [calls] test_currency_staleness.py:L253
- test_silent_after_stash_and_pop_of_a_sources_edit() [calls] test_currency_staleness.py:L280
- test_stamp_without_input_fingerprints_is_not_verifiable() [calls] test_currency_staleness.py:L344
```

So `affected` does not filter tests, and `tests/` is genuinely indexed.

### Control arm — fixture-mediated, cross-file, one extraction run

`commit_file` is a `@pytest.fixture` defined in `tests/conftest.py:83` and reached
by parameter injection. It still resolves, because the test bodies call it:

```
$ graphify affected "commit_file" --depth 1
Affected nodes for commit_file()
...
- test_land_accepts_an_ancestor_receipt_for_a_closing_commit() [calls] test_pr.py:L903
- test_ship_accepts_an_ancestor_receipt_for_a_closing_commit() [calls] test_pr.py:L868
- test_a_control_character_in_a_path_is_escaped() [calls] test_review.py:L1129
  … 17 total, across two files, from a definition in a third
```

### The same-syntax A/B that isolates the real cause

Two call sites, byte-for-byte the same call shape, same target symbol:

```
$ sed -n '375,380p' tests/test_currency_staleness.py
    _stamp(root)
    (root / "sources" / "alpha.manifest").write_text("edited after the build\n", encoding="utf-8")

    sync.restamp_artifacts(root, spec)
    assert _state(root) == staleness.CHANGED

--- and the src twin, same call syntax ---
$ sed -n '250,253p' python/src/kb_setup/graph.py
        if spec is None:
            return
        path = sync.restamp_artifacts(repo_root, spec)
        if path is None:
```

Only one of them produces an edge:

```
$ graphify affected "restamp_artifacts" --depth 1
Affected nodes for restamp_artifacts()
Relations: calls, indirect_call, references, imports, imports_from, re_exports, inherits, extends, implements, uses, mixes_in, embeds, requires
Depth: 1
- _restamp() [calls] src/kb_setup/artifacts.py:L109
- _restamp_self() [calls] src/kb_setup/graph.py:L252     <-- the src call site, PRESENT
rc=0
```

```
$ graphify path "test_restamp_artifacts_carries_inputs_forward_unchanged" "restamp_artifacts"
No path found between 'test_restamp_artifacts_carries_inputs_forward_unchanged' and 'restamp_artifacts'.

$ graphify path "_restamp_self" "restamp_artifacts"          # CONTROL, known-connected
Shortest path (1 hops):
  _restamp_self() --calls [EXTRACTED]--> restamp_artifacts()
```

So it is **not** an attribute-call resolution failure — `sync.restamp_artifacts(…)`
resolves fine at `graph.py:252`. Attribute calls work.

### Root cause: two disjoint node-id namespaces

```
$ graphify explain "_stamp_build"
  ID:        knowledge-base::python::src_kb_setup_graph_stamp_build

$ graphify explain "test_restamp_artifacts_carries_inputs_forward_unchanged"
  ID:        tests::test_currency_staleness_test_restamp_artifacts_carries_inputs_forward_unchanged
  Connections (6):
    <-- test_currency_staleness.py [contains]
    --> _repo() [calls]      test_currency_staleness.py:L373
    --> _spec() [calls]      test_currency_staleness.py:L374
    --> _stamp() [calls]     test_currency_staleness.py:L375
    --> _state() [calls]     test_currency_staleness.py:L379
    <-- <rationale_for>
```

Note what is missing from those 6 connections: the `sync.restamp_artifacts(root,
spec)` at `:378`, which sits *between* `:375` and `:379`.

Structural count over `graphify-out/graph.json` (streaming scan; the `src<->src`
row is the control that proves the scan sees real edges):

```
edges touching a tests:: node: 3368
  within tests:: only          : 3368
  CROSSING tests:: <-> other   : 0
edges within ::python:: only   : 2194   <-- CONTROL: nonzero proves the scan sees real edges
```

**Zero of 3,368.** The `tests::` sub-graph is a fully disconnected island.

The mechanism is `kb_setup.graph`:

```python
_SELF_TREES = ("python", "tests")            # graph.py:110

for tree in _SELF_TREES:                     # graph.py:153 (_extract_self), :203 (refresh_self)
    _run([graphify_exe(repo_root), "extract", tree, "--code-only", "--force"], repo_root)
    _run([graphify_exe(repo_root), "merge-graphs", str(out), str(sub), "--out", str(out)], repo_root)
```

Two *separate* `graphify extract` runs, union-merged. `refresh_self`'s own
docstring already records that `merge-graphs` **"re-namespaces node ids per
merge"** — which is exactly why no edge can span the two sub-graphs. A call from
`tests/` to `python/src/` is unresolvable at extraction time (the extractor only
sees the one tree) and unrepairable at merge time (union, not re-resolution).

### The natural experiment that proves it is the split, not the tool

`cognee` is pinned as a single source and extracted in **one** run, so its `src/`
and `tests/` share a namespace. Same scan, same script, same graph file:

```
cognee nodes classified: test= 7827  src= 14516
cognee edges  test<->src CROSSING: 10099
cognee edges  test<->test        : 10711
cognee edges  src<->src          : 33848   <-- CONTROL
```

**10,099 test→src edges** where this repo has 0. Sample:

```
TEST test_get_document_from_graph_accepts_chunk_id_via_connections()  (cognee-mcp/tests/test_mcp_server_hardening.py)
   -->  SRC get_document_from_graph()  (cognee-mcp/src/retrieval_utils.py)

TEST test_get_chunk_neighbors_from_graph_filters_direction_and_target()  (cognee-mcp/tests/test_mcp_server_hardening.py)
   -->  SRC get_chunk_neighbors_from_graph()  (cognee-mcp/src/retrieval_utils.py)

TEST test_cognee_client_api_add_uses_content_addressed_filename()  (cognee-mcp/tests/test_mcp_server_hardening.py)
   -->  SRC CogneeClient  (cognee-mcp/src/cognee_client.py)
```

One variable differs between cognee and us: one extraction run vs two.

## What the gap analysis should say instead

- ❌ "graphify cannot answer 'which tests cover this change'" — false, and
  falsified by a single `affected` call against the graph the report was written
  from.
- ✅ "graphify links a test to the symbol it exercises whenever both are in the
  **same extraction run**; it cannot link across sub-graphs joined by
  `merge-graphs`, which re-namespaces ids and adds no cross-graph edges."
- ✅ "This repo's own self-index currently splits `python/` and `tests/` into two
  runs (`_SELF_TREES`), so the capability is unavailable **for our own code**
  specifically — 0 of 3,368 tests-touching edges cross into `python/`."

### Bounds I did not exceed

- `affected` answers **symbol → dependents**, not **diff → tests**. Mapping a
  changed hunk to the symbols it touches is the caller's job; graphify ships no
  `affected --since <ref>`. That is a real ergonomic gap and is worth stating —
  but it does not rescue the claim, which was unqualified and is about capability.
- Everything above is measured on the **pinned 0.9.31** (`graphify_exe`), not a
  bare-PATH `graphify`. A 0.9.32 also exists on this host; `graphify --version`
  in this shell reported `0.9.31`, matching the pin and the build stamp.
- I did not probe whether a *combined* single-run extraction of `python/`+`tests/`
  would work **in this repo** — that would require `graphify extract` by hand,
  which `kb_setup.hook_guard` denies. The cognee natural experiment is the
  indirect arm; a direct arm would be a `kb_setup.graph` change plus `kb-build`.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the tool under test; pinned 0.9.31, `affected`/`path`/`explain` behaviour and `merge-graphs` id re-namespacing.
- [topoteretes/cognee](https://github.com/topoteretes/cognee) — the natural experiment: a pinned source whose `src/` and `tests/` are extracted in one run, giving 10,099 test→src edges.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo; `kb_setup.graph._SELF_TREES` / `_extract_self` / `refresh_self` are the cause of the local failure.
