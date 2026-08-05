# Cross-source connectivity: why the merged graph has zero inter-source edges

Agent: cross-source-connectivity. Started 2026-08-04. Written incrementally.

Installed graphify under analysis (0.9.32):
`/Users/rmanaloto/.local/share/mise/installs/pipx-graphifyy/0.9.32/graphifyy/lib/python3.14/site-packages/graphify/`
(abbreviated below as `graphify/…`)

## Method

The 552 MB `graph.json` was **streamed line-by-line**, never `json.load`-ed.
It is written by `write_json_atomic(indent=2)`, so `nodes[]`/`links[]` objects
sit at indent 4 and their top-level fields at indent 6; `graph.hyperedges`
objects sit at indent 6 with fields at indent 8, so an indent-6 field filter
cannot see them. Array boundaries located by `grep -n`: `"nodes": [` at line
82, `"links": [` at line 4,043,171. Scripts:
`…/scratchpad/scan_graph.py`, `scan2.py`, `scan3.py`. Full pass ≈ 8 s.

## Headline answers

1. **`repo` is collapsed because the LAST merge re-tags everything.** Not a
   graphify bug and not `_merge_sources_into`'s doing — the self-code merge 20
   lines later re-prefixes the entire aggregate. `graph.py`'s comment "Every
   source now carries its own tag, exactly once" is true for ~30 lines of
   `build()` and false in the artifact.
2. **0 cross-source edges is EXPECTED, not a defect.** Extraction is per-source
   and `merge-graphs` is `nx.compose` over disjointly-prefixed node sets; no
   graphify code path adds an edge at merge/build/cluster time. Cross-source
   dedup is explicitly refused.
3. **Per-source provenance is NOT lost** — it survives as the *second* `::`
   segment of every node id (`knowledge-base::mise::…`), which is how all the
   numbers below were partitioned. Only the `repo` **attribute** was clobbered.
4. **The one thing that appears to span sources — communities — is an integer
   collision, not a bridge.** 171 communities "span" two tags; every one of
   them is `.self-graph` + one corpus source, because `.self-graph` is merged
   *after* the only global `cluster()` call and carries its own local ids 0-170.
5. **The tools Ray named are in the corpus as SOURCE CODE only.** 44 of 46
   manifests are `kind = code` → AST-only, every `.md` skipped. `ruff` is
   pinned and contributed **0 nodes**. `ty` contributed **36**.

---

## Probe log (append-only)

### P1 — where the `repo` tag comes from (source read)

- `graphify/build.py:1590-1608` `prefix_graph_for_global(G, repo_tag)`: relabels
  every node id to `f"{repo_tag}::{n}"` (`build.py:1598`), then sets
  `data["repo"] = repo_tag` **unconditionally** (`build.py:1601`) and
  `data.setdefault("local_id", …)` (`build.py:1602`).
  The asymmetry is load-bearing: on a second pass `repo` is **overwritten**
  while `local_id` is **preserved**.
- `graphify/build.py:1611-1636` `distinct_repo_tags(graph_paths)`: tag =
  `p.parent.parent.name` (`build.py:1623-1624`) — for
  `sources/<name>/graphify-out/graph.json` that is `<name>`.
- `graphify/cli.py:2095-2191` `merge-graphs`: N-ary (`cli.py:2098-2107`),
  `repo_tags = _repo_tags(graph_paths)` (`cli.py:2168`), then per input
  `_prefix(G, repo_tag)` + `nx.compose` (`cli.py:2172-2175`).

**The tag is derived from each INPUT path, not the output path.** A single
N-ary merge over `sources/*/graphify-out/graph.json` therefore *does* produce
one distinct tag per source. Something later overwrote them.

### P2 — the later writer (source read, `kb_setup/graph.py`)

`build()` writes `graph.json` **four** times, in this order:

| step | `graph.py` | effect on tags |
|---|---|---|
| corpus compose, ONE N-ary merge | `graph.py:653-655` | each source gets its own tag, ids `<name>::<local>` ✅ |
| doc chunks replayed, one call per chunk | `graph.py:664-667` → `_merge_docs.py:31-39` | adds unprefixed semantic nodes; **`cluster(G)` at `_merge_docs.py:34` — the only global clustering** |
| `.base-graph.json` snapshot | `graph.py:672-673` | — |
| **self-code merge** | `graph.py:676-681` | ⚠️ re-prefixes EVERYTHING |

The self merge is:

```python
_run([graphify_exe(repo_root), "merge-graphs", str(out), str(sub), "--out", str(out)])
```

`out` is `graphify-out/graph.json`, so `distinct_repo_tags` reads
`parent.parent` = the **repo root** → tag `knowledge-base`; `sub` is
`.self-graph/graphify-out/graph.json` → tag `.self-graph`. `prefix_graph_for_global`
then rewrites `repo` on all 331,251 already-merged nodes to `knowledge-base`
and re-prefixes their ids. `refresh_self` (`graph.py:326-338`) does the
identical thing to the staged base, so `kb-watch` reproduces the same state.

**Artifact agrees exactly.** Sampled node (`graph.json` node #1):

```json
"repo": "knowledge-base",
"local_id": "agents_skills_convert_tasks_to_linear_scripts_convert_tasks_to_linear",
"id": "knowledge-base::OpenSymphony::agents_skills_convert_tasks_to_linear_scripts_convert_tasks_to_linear"
```

`local_id` still lacks the `OpenSymphony::` segment — that is the `setdefault`
of pass 1 surviving pass 2, i.e. positive proof of exactly **two** prefix
passes. Measured over all 334,486 nodes: `::` depth is **2 for 328,387 nodes
and 1 for 6,099** — never 0, never ≥3. (The 6,099 are the two sets merged in
the final call itself: 3,235 `.self-graph` + 2,864 semantic doc-chunk nodes.)

So `graph.py:649-652`'s claim "Every source now carries its own tag, exactly
once" is **correct about `_merge_sources_into` and wrong about the artifact**.
It was written for #120 (the pairwise-merge fix) and never re-checked against
the self merge that follows it.

**The provenance is not lost, only mislabelled**: `id.split("::")[1]` recovers
the source for every node. 40 distinct values (38 real sources + the two
single-prefix buckets).

### P3 — cross-source edge count, with a control arm

`scan2.py`, one streaming pass, node-id → tag map built first:

| measurement | value |
|---|---|
| nodes | 334,486 |
| links | 816,538 |
| links with both endpoints parsed | 816,538 (100%) |
| links with an endpoint absent from the node set (dangling) | **0** |
| **edges crossing a source tag** | **0** |
| **CONTROL: edges crossing a community boundary** | **108,647** |

The control arm is the same parser, the same 816,538 links, the same
`source`/`target` strings — and it returns a large non-zero. So "0 cross-source
edges" is an answer, not a broken probe. Re-derived independently in `scan1`
(pair counter) and `scan2` (tag-map join); both returned 0.

`node_repo` re-derived: `knowledge-base` 331,251 / `.self-graph` 3,235 —
matches the handed-down figures exactly.

### P3b — CONTROL ARM: the same probe on `.base-graph.json` (before the self merge)

`.base-graph.json` is the snapshot `build()` takes at `graph.py:672-673`,
immediately **before** the self merge. Same script (`scan_base.py`, generic
array detection, no hardcoded line numbers), same parser:

| | `.base-graph.json` (pre-self-merge) | `graph.json` (post) |
|---|---|---|
| nodes | 331,251 | 334,486 |
| **distinct `repo` values** | **39** (38 source tags + `<none>`) | **2** |
| `::` prefix depth | 0 → 2,864 · 1 → 328,387 | 1 → 6,099 · 2 → 328,387 |
| links | 810,382 | 816,538 |
| cross-tag edges | **0** | **0** |

This is the decisive evidence for P2: one probe, two files, **39 vs 2**. The
probe can obviously produce "many distinct repos" — it just did — so the
collapse in `graph.json` is caused by what happens between the two files, which
is exactly the one `merge-graphs` call at `graph.py:676-681`.

Arithmetic closes exactly: 810,382 (base links) + 6,156 (`.self-graph` intra
edges, `scan2`) = **816,538**. No edge is lost or duplicated by the self merge.
(Duplicate-undirected-pair count is 0 in both files; 12 self-loops in both.)

The 2,864 `<none>` repo values in base are the semantic doc-chunk nodes: they
are added by `build_merge` (`_merge_docs.py:31`), never by
`prefix_graph_for_global`, so they carry no `repo` and no prefix — until the
self merge gives them one of each.

### P4 — is 0 expected? (source read)

Yes, by construction, at three levels:

1. **Extraction is per-source and per-root.** `graph.py:_extract_code` runs
   `graphify extract sources/<name> --code-only` into that source's own
   `graphify-out/`. graphify's symbol resolution never leaves the scanned root,
   so no edge can be created between two sources at extract time.
2. **`merge-graphs` is pure composition.** `cli.py:2172-2175` is
   `nx.compose(merged, prefixed)` and nothing else. Because every input is
   relabelled into a disjoint `<tag>::` namespace *before* compose, the result
   is by definition a disjoint union — compose can only unify node ids that are
   already string-equal, and the prefixing guarantees none are. No label
   matching, no similarity pass, no alias resolution runs there.
3. **Dedup — the one mechanism that could bridge — is explicitly OFF, and
   graphify refuses it anyway.** `_merge_docs.py:31-33` passes `dedup=False`.
   Verified in the installed source, not just from the comment:
   `graphify/dedup.py:338-346` computes `repos_seen = {n["repo"] …}` and
   **raises `ValueError`** when `len(repos_seen) > 1` — "Cross-project dedup is
   disabled — run dedup per-repo before merging."

The only stage that touches the whole graph is `cluster(G)`
(`_merge_docs.py:34`), which *partitions* nodes and adds no edges.

**graphify DOES ship the machinery for cross-source linking — it is just
gated.** `graphify/dedup.py:1-4` documents the pipeline as "exact
normalization → entropy gate → MinHash/LSH blocking → Jaro-Winkler
verification → same-community boost → union-find merge"
(`_minhash.py:36,84`, `rapidfuzz` Jaro-Winkler, `dedup.py:141` `_UF`). So
Option C below is *not* a homegrown reinvention — the native path exists and
its author deliberately turned it off across repos.

**Latent hazard worth recording.** That guard keys on the `repo` attribute
that P2 shows is falsified by the second prefix pass. Today it still fires
(`graph.json` has 2 distinct values, `.base-graph.json` has 39 — both > 1), so
nothing is broken now. But a change that left every node with **one** `repo`
value would make the guard pass silently and let MinHash merge a `main` in
`codex` with a `main` in `uv`. The guard's correctness depends on an attribute
this repo's build path does not maintain.

### P5 — what actually spans sources today

**Communities: 171 of 9,330 span more than one tag — and all 171 are an id
collision, not a bridge.**

`scan3.py`, per-tag community id ranges:

| tag | # communities | min id | max id |
|---|---|---|---|
| `.self-graph` | 171 | **0** | **170** |
| `knowledge-base` (semantic doc nodes) | 162 | 1106 | 9329 |
| `codex` | 1566 | 11 | 8625 |
| `mise` | 1370 | 77 | 8897 |
| `uv` | 334 | 0 | 9327 |
| `graphify` | 352 | 40 | 8796 |
| `pkl` | 536 | 2 | 9169 |
| `hk` | 178 | 545 | 8809 |
| `ty` | 6 | 4007 | 9228 |

`.self-graph` occupies a **contiguous 0-170** — the signature of a sub-graph
clustered on its own, never re-clustered globally. Every multi-tag community is
`{.self-graph, <one corpus source>}`, e.g. community `0` = `uv` 2,671 nodes +
`.self-graph` 80; community `1` = `cognee` 2,549 + `.self-graph` 70. Two nodes
share a community id while having **no path between them** — the graph has 0
edges across that boundary.

Cause is the ordering in P2: the only `cluster()` call is inside the doc-chunk
merge (`_merge_docs.py:34`), which runs at `graph.py:667` — **before** the self
merge at `graph.py:676-681`. So our own code's community numbers were assigned
by its standalone `graphify extract` run and were never reconciled.

Consequence: **`community` is unusable as a cross-source signal for
`.self-graph` nodes**, and any tool reading it (wiki grouping, `kb-label` hub
labels, GRAPH_REPORT community sections) silently mixes our code into 171
unrelated corpus communities.

### P6 — what is actually in the corpus (46 manifests)

44 of 46 are `kind = code`; only two are `kind = docs`
(`agent-harness-docs`, `mattpocock-skills`). Four are `scope = study`
(`code-review-graph`, `codebase-memory-mcp`, `GitNexus`, `mindwalk`) and go to
`study-graph.json`, not the aggregate (`graph.py:_build_study_graph`).

Node counts for the tools Ray named, from the id-segment partition:

| tool | manifest `kind` | nodes in aggregate | intra-source edges |
|---|---|---|---|
| `uv` | code | 20,524 | 53,689 |
| `mise` | code | 19,651 | 46,868 |
| `rumdl` | code | 18,804 | 38,474 |
| `pkl` | code | 16,910 | 46,695 |
| `graphify` | code | 9,812 | 20,192 |
| `agnix` | code | 9,714 | 18,184 |
| `taplo` | code | 8,013 | 23,891 |
| `typos` | code | 3,422 | 4,673 |
| `hk` | code | 2,131 | 3,994 |
| `gitleaks` | code | 850 | 2,577 |
| **`ty`** | code | **36** | **46** |
| **`ruff`** | code | **0 — tag absent entirely** | **0** |
| Claude Code itself | *no manifest* | **0** | **0** |
| our own code (`.self-graph`) | — | 3,235 | 6,156 |
| doc chunks (`_origin: semantic`) | — | 2,864 | 3,747 |

Every one of those "intra" figures is also the source's **total** edge count —
because the cross-source count is 0, no source has a single edge leaving it.

`ruff`'s absence is issue #131 and is re-confirmed here from the artifact, not
from the issue: the tag never appears among the 40. `ty` at 36 nodes is a
second, quieter instance of the same class — present but effectively empty.
**Claude Code has no manifest at all**; what the corpus knows about it comes
from third-party repos (`awesome-claude-code` 363, `learn-claude-code` 1,688,
`last30days-skill` 9,102, `system-prompts-leaks` 362) and the doc chunks.

`kind = code` runs `extract --code-only`, and `graphify/cli.py:2897-2910` is
explicit about what that drops: on `--code-only` it prints "skipping N non-code
file(s) (D docs, P papers, I images) — no LLM extraction" and sets
`doc_files = paper_files = image_files = []`. So every `.md` in those 44 repos
— `mise`'s docs, `uv`'s guide, `hk`'s and `ruff`'s rule documentation — is
**never read**. That is the substance behind issue #81.

### P7 — the doc/semantic layer is an island too

2,864 nodes have `_origin: semantic` (the committed
`sources/extractions/*.json` chunks); 331,622 have `_origin: ast`. All 2,864
sit in the single-prefix `knowledge-base::` bucket, and the cross-tag count of
0 includes every semantic↔ast pair. So **no doc-extraction node is connected
to any AST node**, in either direction. The prose layer and the code layer are
two disconnected halves of the same file.

(That is also why `kb-query --prose` reads a separate 2,553-node graph: it is
not a view of the code graph, it is the other component.)

### P8 — the 5 hyperedges reference ids that do not exist in the graph

`graph.json` lines 5-81 carry `graph.hyperedges` (5 entries), whose `nodes`
arrays hold **unprefixed** ids while every node in `nodes[]` is prefixed 1-2
deep. `prefix_graph_for_global` rewrites node ids and edge `_src`/`_tgt`
(`build.py:1598-1607`) and **never touches `G.graph`**, so graph-level
structures survive each merge unrelabelled.

Control-armed membership probe over all 334,486 node ids (`hyper.py`), two
positives and two negatives from one run:

| id | present in `nodes[]` |
|---|---|
| `yt_9ciowbmokdu_memory_storage` (as the hyperedge writes it) | **false** |
| `knowledge-base::yt_9ciowbmokdu_memory_storage` | true |
| `security_safe_fetch` (as the hyperedge writes it) | **false** |
| `knowledge-base::security_safe_fetch` | true |

So all 5 hyperedges are dangling. Same root cause as P2, different victim.

Side observation on schema: `.base-graph.json` (written by `export.to_json`)
carries `hyperedges` and `built_at_commit` as **top-level** keys *in addition*
to `graph.hyperedges`; `graph.json` (last written by `merge-graphs` via
`node_link_data`) has only the `graph.hyperedges` copy. The two files are the
same corpus in two schemas, which is a trap for any consumer that reads one and
assumes the other.

---

## Q4 — the real options, with cost and risk

### Option A — stop the double prefix (repair `repo`, ~free)

Merge the self sub-graph as one more input to the **same** N-ary
`_merge_sources_into` call rather than as a second merge over the output
(`graph.py:676-681`). Then `distinct_repo_tags` sees
`.self-graph/graphify-out/graph.json` alongside the sources and every node
keeps its own tag, exactly once — which is what `graph.py:649-652` already
claims.

- **Buys:** a usable `repo` attribute (so a query can partition by source),
  ids one segment shorter, and it makes the doc chunks and hyperedges stop
  being silently re-namespaced.
- **Costs:** the `.base-graph.json` design depends on our code being merged
  *last* (`graph.py:669-673` — the snapshot is "the corpus without our own
  code") and `refresh_self` restores from it. Reordering means re-deriving the
  base differently, e.g. snapshot the corpus inputs list rather than the
  composed file.
- **Risk:** touches the one path #120 already broke once. Every node id in the
  graph changes, so `.graphify_labels.json`, memory, and any recorded id break.
- **Adds zero cross-source edges.** This is a provenance fix, not a
  connectivity fix.

### Option B — re-cluster after the last merge (fix the fake spans, cheap)

Run one `cluster()` over the final graph instead of leaving the doc-merge's
partition as the last word. Removes the 171 phantom multi-tag communities.

- **Buys:** `community` becomes meaningful again; hub labels stop mixing our
  code into `uv`'s communities.
- **Costs:** one Louvain pass over 334k nodes at build time. No LLM.
- **Risk:** low. **Caveat:** on a graph with 0 cross-source edges, Louvain can
  never place two sources in one community anyway — so this makes the graph
  *honest*, it does not create spans. Expect the multi-tag count to go to 0,
  not up.

### Option C — cross-source edges by shared normalised label (the real ask)

Every node already carries `norm_label` (seen in P2's sample). A post-merge
pass could add `same_name_as` / `semantically_similar_to` edges between nodes in
different tags with equal `norm_label`.

- **Buys:** the first actual cross-tool connectivity.
- **Costs:** deterministic, no LLM, one pass.
- **The native machinery exists** — `graphify/dedup.py` is a full
  MinHash/LSH + Jaro-Winkler + union-find pipeline (`dedup.py:1-4`,
  `deduplicate_entities` at `dedup.py:320`). Nothing needs to be hand-written;
  `use-tool-builtins.md` is satisfied by *using* it.
- **Risk — high, and graphify refuses it by design.** `dedup.py:338-346` raises
  `ValueError` the moment nodes span >1 `repo`, with the stated reason that a
  `main` in repo A is not a `main` in repo B. On this corpus a bare
  `norm_label` join would connect every `main`, `run`, `new`, `test`, `config`
  across 38 repos — and `codex` alone (90,797 nodes) would dominate the result.
  Taking this option means deliberately defeating an upstream guard, so it must
  be narrowed hard (rare-corpus-wide labels only, or an explicitly declared
  tool pair) and every edge produced must be tagged `INFERRED`.
- **Note the difference between dedup and linking.** `deduplicate_entities`
  *merges* nodes; what Ray asked for is a *relationship* between two tools that
  both still exist. Even if the guard were lifted, merging `uv`'s `main` into
  `mise`'s `main` is the wrong shape. The reusable part is the blocking +
  scoring (`_minhash.py`, Jaro-Winkler), applied to emit an edge rather than a
  union-find merge — which is a real change, not a flag.

### Option D — a deliberate bridge chunk (the cheapest honest win)

A committed `sources/extractions/toolchain-bridge.json` whose nodes ARE the
relationships Ray asked to see — "this repo pins `mise`", "`hk` invokes
`ruff`", "`graphify` is driven by `kb_setup.graph`" — with edges to node ids in
each source.

- **Buys:** exactly the picture asked for, and it is queryable today.
- **Costs:** host-agent extraction (real Claude tokens), and it must be
  re-pointed whenever ids change (which Option A would do).
- **Risk:** the ids are the hard part. Edges must name
  `knowledge-base::mise::<local>` today; that string is an artifact of the
  double prefix. **Do A before D**, or the bridge chunk encodes the bug.

### Option E — ingest the tools' DOCS (P6 says this is the actual gap)

For the question "how do claude-code / graphify / uv / ruff / ty / mise / hk
relate", the corpus currently holds their *Rust and Python internals* and none
of their *documentation*. Add `kind = docs` mirrors (issue #84's path) for the
tools this repo actually runs, plus a manifest for Claude Code, which has none.

- **Buys:** the material that would actually answer a tooling question, and
  prose nodes land in the `_origin: semantic` layer where cross-references are
  natural.
- **Costs:** host-agent extraction per source (the expensive path).
- **Risk:** low, and it fixes `ruff` (0 nodes) and `ty` (36) by a different
  route than debugging their AST extraction.
- **Note:** on its own this still yields 0 cross-source edges (P7 — the
  semantic layer is its own island). E supplies the *content*; C or D supplies
  the *edges*.

### Option F — federation (issue #130)

Query each source's sub-graph separately and merge results at query time.
P3 measures the recall cost of doing so: **0 edges of 816,538 would be lost**,
because none crosses a source. Federation is free today in recall terms and
would sidestep the 552 MB single-file problem — but it also forecloses C, since
there would be no single graph for a cross-source edge to live in.

## Recommendation (ordered)

1. **B** (re-cluster last) — cheap, removes a live falsehood in the artifact.
2. **A** (single N-ary merge incl. self) — restores `repo`, shortens every id,
   un-breaks the hyperedges; do it before anything encodes current ids.
3. **E** (docs for the tools we run + a Claude Code manifest) — the content gap
   is the real reason the question cannot be answered today.
4. **D** (bridge chunk) — after A, to state the relationships explicitly.
5. **C** (label-join edges) — only after reading `dedup.py` / `semantic_cleanup.py`
   for a native mechanism, and only rarity-restricted.

> **REVISED IN ROUND 2 — read `## Revised recommendation` at the end instead.**
> C is withdrawn on measurement (R5); a new option **G** (a joint cross-source
> semantic chunk) takes its place as the only thing that can produce a
> cross-source edge (R4-Q1, R6).

Do **not** treat 0 cross-source edges as a defect to be patched: it is the
correct output of a per-source extraction plus a disjoint-namespace compose.
The defects found here are the clobbered `repo` tag (P2), the phantom
communities (P5), the orphaned hyperedges (P8), `ruff`'s 0 nodes and `ty`'s 36
(P6).

---

# Round 2 — closing the UNVERIFIED, and the 182,041 skipped edges

## R1 — the 0 restated with its TRUE denominator (independently re-derived)

I did not use the `repo` attribute to partition edges — it has 2 values and
could only ever return 0, exactly as the lead diagnosed. My discriminator was
the **second `::` segment of the node id**, which has **40 values**.

| route | classified | skipped | cross-source |
|---|---|---|---|
| `repo` attribute (lead, retracted) | 816,538 | 0 | 0 — *cannot discriminate* |
| `source_file` → clone on disk (lead) | 634,497 | 182,041 | 0 |
| **id segment (mine, `scan1`+`scan2`)** | **816,538** | **0** | **0** |

**Denominator is 816,538, not 634,497.** Arms I ran, both directions:

1. *Can classify* — 816,538 of 816,538 links parsed; **0 dangling** endpoints
   (every `source`/`target` resolves to a node in `nodes[]`).
2. *Can find crossings* — same parser, same links, partitioned by `community`
   instead: **108,647 crossings**. Not blind.
3. *Can distinguish sources* — 40 distinct tag values, largest `codex` 90,797,
   smallest `awesome-harness-engineering` 15.
4. *Can produce "many" for the collapsed field* — `scan_base.py` on
   `.base-graph.json` returns **39 distinct `repo` values** where `graph.json`
   returns 2. Same script, two files.

Two independent implementations (`scan1` counts crossing pairs directly,
`scan2` builds a node→tag map then joins) both return 0.

## R2 — what the 182,041 skipped edges are (they are NOT a gap)

Reproduced the disk-attribution route (`scan4.py`) and cross-tabulated it
against the id segment. I get 176,942 skipped where the lead got 182,041 —
same phenomenon, slightly different attribution rules. Node attribution:

| bucket | nodes |
|---|---|
| `in_clone` (disk route can attribute) | 282,329 |
| **`empty_source_file`** | **46,180** |
| `in_repo_root` (our own `python/`+`tests/`) | 3,103 |
| `NOT_ON_DISK` | 2,020 |
| `in_sources_media` | 854 |

And the skipped edges by cause:

| endpoint pair | edges | share |
|---|---|---|
| **`empty_source_file` ↔ `in_clone`** | **167,025** | **94.4%** |
| `in_repo_root` ↔ `in_repo_root` | 5,404 | 3.1% |
| `NOT_ON_DISK` ↔ `NOT_ON_DISK` | 2,611 | 1.5% |
| `in_sources_media` ↔ `in_sources_media` | 1,102 | 0.6% |
| `empty_source_file` ↔ `in_repo_root` | 752 | 0.4% |
| everything else | 48 | 0.03% |

**94% of the skip is one cause: 46,180 nodes have no `source_file` at all.**
They are `_origin: ast`, `file_type: code`, and they are **undefined/imported
symbol references** — `Exception`, `ArgumentParser`, `Path`, `Any`, `Option`,
`String`, `Vec`, `AppHandle`. Symbols the scanned repo *uses* but does not
*define*, so there is no file to name. `codex` 19,574 · `uv` 5,618 ·
`mise` 4,014 · `pkl` 2,402.

Every one of those nodes **is** attributable — by id segment, which is why my
route skips nothing. So the 0 does not need restating: the skipped set is fully
covered by the stronger discriminator and contains no crossings either.

(All 50 `sources/*/` clones are present on disk including `ruff`, so missing
clones are not a factor — checked before assuming.)

## R3 — the clobber mechanism: CONFIRMED, and the depth-3 growth bug is REAL

The lead's reconstruction is correct in every particular. `graph.py:676-681`
runs `merge-graphs <aggregate> <self-sub> --out <aggregate>`;
`distinct_repo_tags` reads `parent.parent.name` of the aggregate path, which is
the repo root → `knowledge-base`; `prefix_graph_for_global` re-tags and
re-prefixes. Evidence in P2/P3b: `local_id` survives from pass 1 (`setdefault`)
while `repo` does not (assignment), and base has 39 tags vs graph.json's 2.

**Yes, it double-prefixes, and a third merge WOULD produce depth-3.**
`build.py:1598` is `relabel = {n: f"{repo_tag}::{n}" for n in G.nodes}` with no
already-prefixed guard — it is unconditional by construction. Measured depths:
`.base-graph.json` 0/1 → `graph.json` 1/2. Each `merge-graphs` call over the
aggregate adds exactly one segment to every id, forever.

This is the same defect family as #120 (the pairwise loop that reached depth
22). #120 fixed the *loop*; the one remaining second merge was left in place, so
the growth is now +1 per build instead of +N — bounded, but not zero. `kb-watch`
(`refresh_self`, `graph.py:326-338`) is safe from compounding only because it
restarts from `.base-graph.json` each time rather than appending.

## R4 — the four native-mechanism questions, answered from source

### Q1. Does anything build `semantically_similar_to` edges over a merged graph?

**No — nothing in graphify builds them at all.** Control-armed grep over the
whole installed package: `semantically_similar_to` appears **only** in

- **LLM prompt schemas** — `llm.py:478`, and the per-platform extraction specs
  (`skills/claude/references/extraction-spec.md:32`, and 13 sibling copies);
- **consumers** — `analyze.py:229` ("Excludes `semantically_similar_to` (genuine
  cross-boundary insight)"), `analyze.py:261`, `report.py:179`.

There is **no producer function anywhere in the package**. The edges the lead
saw in GRAPH_REPORT.md came from *our own host-agent extraction chunks*, where
the LLM was instructed to emit them. That is a much more useful fact than a
missing algorithm: **the only mechanism that creates a semantic cross-boundary
edge in this corpus is an LLM reading two things in one chunk.**

### Q2. What is MinHash for, and is it reachable?

`_minhash.py` implements MinHash + banded LSH (`_minhash.py:36,84`) and has
**exactly one consumer**: `dedup.py:13,46,471,483`, inside
`deduplicate_entities`. It is entity **deduplication** — pass 1 exact-norm
union-find, pass 2 LSH blocking + Jaro/Jaro-Winkler verification
(`dedup.py:453-530`).

Reachability: `deduplicate_entities` is called only from `build.py:1146`, whose
`dedup` flag is set `True` at **`cli.py:3547` and `cli.py:3556` — both inside
`extract`**, before any merge, on one scanned root. Audited the other entry
points the lead named:

- **`merge-chunks`** (`cli.py:3755-3835`) — dedups **by id only**, first-writer
  wins. No similarity.
- **`merge-semantic`** (`cli.py:3836+`) — same, cached entries win.
- **`cache-check`** (`cli.py:3695+`) — semantic cache lookup; no graph work.
- **`merge-graphs`** (`cli.py:2095-2191`) — `nx.compose` only, no dedup call.

**And even if the repo guard were lifted, it would not touch code.**
`dedup.py:451-456`: `if _is_code(node): continue` — code symbols are excluded
from fuzzy matching outright, with the comment "two functions with similar long
names in different files … must not be fuzzy-merged". That excludes 331,622 of
the 334,486 nodes in this corpus.

### Q3. `symbol_resolution.py` — cross-root? P4.1 CORRECTED

My P4.1 said resolution "never leaves the scanned root". That was uncited and,
as phrased, **wrong**. The precise statement:

- `resolve_cross_file_raw_calls` (`symbol_resolution.py:307`) and
  `resolve_python_import_guided_calls` (`:218`) take `(per_file, all_nodes,
  all_edges)` — **no `root` parameter**. Structurally they would happily resolve
  across roots if handed nodes from two.
- They are **never called.** Grep across the whole package finds only
  definitions plus one doc mention (`paths.py:231`). Control arm: the same grep
  shape finds a live caller for `resolve_bash_source_edges` at
  `extract.py:5282`, so it discriminates. These two are **dormant**, like
  `deduplicate_by_label` which `build.py:1167` labels "Dormant: this is NOT
  wired into build()".
- The wired resolver, `resolve_bash_source_edges` (`:404`), **does** take
  `root`, and `_file_node_id_for_path` (`:392-401`) falls back to hashing the
  absolute path when a path lies outside it.
- `extract.py` runs its own inline cross-file pass ("Cross-file call resolution
  for all languages … now that we have all nodes from all files",
  `extract.py:5288-5290`) over the node list of **one `extract` invocation**,
  which scans one target.

**Corrected claim:** resolution is bounded to one root not because the
resolvers refuse to cross one, but because nothing ever hands them two. The
capability exists and is unwired.

### Q4. Does `dedup=True` exist, and what is the guard?

Reachable only at `cli.py:3547` / `cli.py:3556`, both in `extract`. The guard,
quoted verbatim (`dedup.py:338-346`):

```python
# Guard: cross-project dedup is not supported — nodes from different repos
# share label names by coincidence and must never be merged by string similarity.
# If you need to dedup a global graph, run deduplicate_entities per-repo first.
repos_seen = {n.get("repo") for n in nodes if n.get("repo")}
if len(repos_seen) > 1:
    raise ValueError(
        f"deduplicate_entities: nodes span multiple repos {sorted(repos_seen)!r}. "
        f"Cross-project dedup is disabled — run dedup per-repo before merging."
    )
```

## R5 — Option C is now measurably dead, not merely risky

I sized the label-join surface rather than arguing about it (`bridge.py`):

- 217,386 distinct `norm_label` values; **4,910 appear in more than one source.**
- Ranked by how many sources share them: `main()` **36**, `path` 28, `run()` 23,
  `name` 23, `version` 22, `any` 22, `type` 21, `config` 21, `.__init__()` 21,
  `datetime` 20, `.get()` 20, `url` 19, `result` 19.
- Restricting to the undefined-symbol nodes (the most defensible subset) gives
  **558 shared labels**, and they are no better: `path` 25, `any` 21, `t` 20,
  `datetime` 20, `self` 16, `vec` 14, `string` 14, `option` 14, `hashmap` 14.

**Not one of the top labels in either list carries information about how two
tools relate.** The join surface is entirely stdlib types and universal verbs —
precisely the coincidence `dedup.py:338-346` and the `_is_code` exclusion were
written to prevent. **Option C is withdrawn**, on measurement rather than on
graphify's say-so.

## R6 — the cheapest mechanism for "how does mise's approach to X relate to hk's"

Given Q1 (only an LLM produces `semantically_similar_to`) and R5 (label joins
are noise), the candidates rank as follows.

| # | mechanism | LLM? | cost | produces a cross-source EDGE? |
|---|---|---|---|---|
| **1** | **Two sources' doc files batched into ONE semantic chunk** | yes, one pass | ~1 chunk of tokens per pair | **YES** — this is the only thing that does |
| 2 | Query per-source, join outside the graph | no | ~0 | no — answers the question without an edge |
| 3 | Re-cluster the final graph (Option B) | no | one Louvain pass | no |
| 4 | Fix the double prefix (Option A) | no | build change | no |
| 5 | Label-normalisation dedup across sources | no | one pass | **withdrawn — R5** |

**#1 is the answer, and the corpus already proves the mechanism works.** The
`semantically_similar_to` edges the lead found
(`claude-code-memory-plan.md` ↔ `yt-9CiOwbmOKdU-memory.md`) were produced by
exactly this: two files in one chunk, an LLM instructed to link concepts that
"solve the same problem without a structural link" at INFERRED confidence 0.6-0.95
(`skills/claude/references/extraction-spec.md:32`). Both files happen to sit
under `sources/media/`, i.e. one source — which is *why* the edge exists, and
is the whole lesson: **chunk membership, not source membership, decides what
can be linked.** graphify's own guidance to chunk 20-25 files "grouped by
directory" is what keeps chunks single-source today; deliberately grouping by
*topic across two sources* is a change of grouping policy, not of tooling.

Practical shape: for a tool pair, put `mise`'s and `hk`'s docs for one topic in
the same chunk. This requires **Option E first** (their docs are not in the
corpus — 44 of 46 manifests are `kind = code`, so every `.md` is skipped per
`cli.py:2897-2910`). E supplies the content; the joint chunk supplies the edge.

**#2 deserves more credit than its rank suggests.** Ray's question is
answerable *today* without any new edge: the id segment partitions the corpus
by tool with 100% coverage, so a query can retrieve `mise`'s and `hk`'s
subgraphs separately and a reader (or an agent) compares them. That is issue
#130's federation, and R1 prices its recall cost at **0 of 816,538 edges**.

## R7 — a PREDICTION, explicitly unrun

Earlier I wrote that re-clustering would take the phantom multi-tag community
count "to 0, not up". **That is a prediction. I have not run it, and this repo
has recently been bitten by treating a predicted outcome as a confirmed one.**

Reasoning: Louvain optimises modularity over edges; with 0 edges between any
two source tags, every source is a separate connected component, and no
community can contain nodes from two components. So the count should go 171 → 0.

What would falsify it: a clustering implementation that assigns by something
other than connectivity (a resolution-parameter fallback, a hub-exclusion path,
or a non-Louvain fallback on Python 3.14 where `graspologic`/`leidenalg`/
`igraph` auto-skip). `cluster()` was **not read** in this pass. Before believing
this, run it and count — and if it returns 171 again, that is a finding, not a
confirmation.

## R8 — the community integer space: CONFIRMED shared

`.self-graph` occupies ids 0-170 and `uv`'s minimum is 0. These are the **same
field and the same key space**, not two lookalikes:

- One attribute, `community`, one JSON key, integer-valued, read by a single
  `Counter` keyed on that value (`scan3.py`).
- The multi-tag count is *derived from that single key*: `scan2` built
  `community → set(tags)` from one field and found 171 communities holding both
  `.self-graph` and a corpus source — e.g. community `0` = `uv` 2,671 nodes +
  `.self-graph` 80; community `1` = `cognee` 2,549 + `.self-graph` 70.

So a reader joining on `community` **would** conflate them. That is not a
hypothetical: `GRAPH_REPORT.md`'s community sections and the wiki grouping both
join on this field.

---

# Round 3 — `cluster.py` read. R7 is REVISED, and the headline changes.

**The short version, and it inverts the framing: Option B is not something to
implement. `graphify label` already re-clusters the whole aggregate — so
`mise run kb-label` IS the fix, and it has not been run since the last build.**

I also had one thing wrong in round 2 and it mattered: I placed
`cli.py:1685`/`1697` inside the `watch` branch. They are inside
**`elif cmd in ("cluster-only", "label"):` (`cli.py:1578`)**, which spans
1578-1901. Stating it plainly because the conclusion I drew from the wrong
placement — that `remap_communities_to_previous` never runs in this repo — was
also wrong. It runs on **every** `kb-label`.

## R9.1 — which algorithm actually runs here

`_partition` (`cluster.py:22-78`) tries `from graspologic.partition import
leiden` and falls back to `nx.community.louvain_communities` on `ImportError`
(`cluster.py:66-77`).

Probed the graphify venv's `site-packages` with a control arm — the same loop
reports PRESENT and ABSENT, so it discriminates:

| package | in graphify's site-packages |
|---|---|
| `graspologic` | **ABSENT** |
| `leidenalg` | **ABSENT** |
| `igraph` | **ABSENT** |
| `networkx` | PRESENT — **3.6.1** |
| `rapidfuzz`, `numpy` | PRESENT |
| `scipy` | ABSENT |

**So networkx 3.6.1 Louvain is what runs**, exactly as `CLAUDE.md` says for
Python 3.14. graphify passes `seed=42, threshold=1e-4, resolution=1.0` and adds
`max_level=10` after an `inspect.signature` check (`cluster.py:73-76`);
networkx 3.6.1 does have `max_level` (`louvain.py:17`), and it is applied as
`itertools.islice(partitions, max_level)` (`louvain.py:125-128`) — it can only
**stop early**, never merge.

## R9.2 — can it co-assign two nodes with no path between them? NO — from the code

Read the installed `networkx/algorithms/community/louvain.py:227+` rather than
relying on what Louvain does in general:

- `nbrs = {u: {v: data["weight"] for v, data in G[u].items() if v != u} for u in G}`
  — the candidate set is **u's adjacency only**.
- `weights2com = _neighbor_weights(nbrs[u], node2com)` — the communities
  considered for `u` are exactly the communities of `u`'s **neighbours**.
- `for nbr_com, wt in weights2com.items():` — the move loop iterates only over
  those.

A node can therefore only ever move into a community containing one of its
neighbours, and the aggregation phase builds the next level's graph from the
previous level's edges, inventing no adjacency. Then in `cluster()` itself:

| step | `cluster.py` | can it co-assign disconnected nodes? |
|---|---|---|
| isolates get their own cid | `183-190` | no — one node each |
| hub reattachment (only if `exclude_hubs_percentile`) | `191-207` | no — votes over `G.neighbors(hub)`; a hub with no votes gets a **fresh** cid |
| oversized split | `209-216` | no — `_split_community` only makes them smaller |
| low-cohesion split | `218-227` | no — same |
| `_split_community` on a 0-edge subgraph | `243-246` | no — returns singletons |
| final re-index | `230-237` | no — `enumerate` over a total order → contiguous unique ids |

**No path in `cluster()` can place two nodes with no path between them into one
community.** That is R7's premise, now cited rather than assumed.

## R9.3 — `remap_communities_to_previous`: runs on every `kb-label`, and CANNOT reintroduce the collision

Callers (control-armed: the same grep shape finds three live callers for
`label_communities_by_hub`, so it discriminates):

- `cli.py:1697` — inside the **`label` / `cluster-only`** branch.
- `watch.py:1342` — inside `watch`, which this repo never runs.

It does **not** run inside `cluster()`. The `label` branch is:

```
cli.py:1684  print("Re-clustering...")
cli.py:1685  communities = cluster(G, resolution=co_resolution, exclude_hubs_percentile=co_exclude_hubs)
cli.py:1691  previous_node_community = {n["id"]: n["community"] for n in _raw["nodes"] ...}
cli.py:1697  communities = remap_communities_to_previous(communities, previous_node_community)
...          to_json(G, communities, str(out / "graph.json"), community_labels=labels)
```

**Can it reintroduce a span after a clean partition? No, and the reason is
structural.** `remap_communities_to_previous` (`cluster.py:272-320`) is
**injective by construction**: `used_old_ids` and `matched_new_ids` guard the
greedy match loop (`:298-305`), and the unmatched branch skips any id already in
`used_old_ids` (`:307-315`). Two new communities can never receive the same
final id, so the function **renumbers and never merges**.

Worked through on the actual data: `previous_node_community` is read from the
*current* graph.json, so old community `0` is the union of `uv`'s 2,671 nodes
and `.self-graph`'s 80. A clean re-cluster splits those into two new
communities, both of which overlap old-`0`. Sorted by `-overlap`, the `uv` one
takes final id `0`; the `.self-graph` one is blocked by `used_old_ids` and gets
a different id. **The span is broken, not preserved.**

One failure mode worth naming so it is not misdiagnosed: `remapped[new_to_final[
new_cid]] = sorted(nodes)` (`:317-318`) is a dict assignment. If the injectivity
guards were ever broken, the symptom would be a **silently dropped community**
(last writer wins), i.e. missing nodes — *not* a phantom multi-tag span.

## R9.4 — the id-reuse path, independent of remapping

`cluster()` returns `{i: sorted(nodes) for i, nodes in enumerate(...)}`
(`cluster.py:237`) — contiguous `0..N-1`, unique within one call. The reuse is
therefore **not** an id-allocation bug at all; it is **two independent
`cluster()` calls on two different graphs, each enumerating from 0**:

- the corpus is clustered by `_merge_docs.py:34` → `0..9329`;
- `.self-graph` is clustered by its own `graphify extract` run (`cli.py:3567`)
  → `0..170`;
- `merge-graphs` composes them and `nx.compose` **copies node attributes
  verbatim** — `prefix_graph_for_global` writes only `repo` and `local_id`
  (`build.py:1600-1602`), never `community`.

Two enumerations, one attribute, no renumbering step between them. That is the
whole mechanism, and it is exactly what P5 measured.

## R9.5 — REVISED PREDICTION (this supersedes R7)

R7 predicted "re-clustering drives the count to 0". The mechanism confirms it —
but R7 was silent on the thing that actually decides your measurement:

> **`build()` does not re-cluster after the self merge.** `graph.py:676-681` is
> the last write, followed only by `prose.derive_for`, `_write_base_guard` and
> `_stamp_build`. There is no `cluster()` call after the merge.

So, two different predictions depending on what your rebuild ran:

**P-A — if the rebuild is `mise run kb-build` alone: the phantom count comes
back at ≈171, NOT 0.** Precisely, it will equal *K*, the number of communities
`.self-graph`'s own `extract` produces (171 last time; it may shift if
`python/`+`tests/` changed). All *K* collide, because the corpus occupies
`0..M-1` with M = 9,330 ≫ K.
**A count near 171 here refutes nothing** — no re-cluster ran. Reading it as
"the fix doesn't work" would be the inverse of the trap you flagged: not a
predicted survival confirming itself, but an untested fix being blamed for a
number produced without it.

**P-B — if you then run `mise run kb-label`: the count goes to exactly 0.**
`graphify label` prints "Re-clustering...", runs `cluster()` over the whole
aggregate (`cli.py:1685`), remaps injectively, and rewrites graph.json via
`to_json(...)`. Combined with R9.2 (no co-assignment without a path) and 0
cross-source edges, every community must be single-tag.

### Falsifiers, stated in advance

| observation | what it would mean |
|---|---|
| **0 after `kb-build` alone** | something re-clusters that I did not find — check `prose.derive_for` and `_stamp_build` |
| **non-zero after `kb-label`** | one of R9.2's six rows is wrong, **or** `kb-label` did not actually rewrite graph.json |
| **nodes go missing after `kb-label`** | the injectivity guards in `remap_communities_to_previous` (R9.3) |
| count changes but stays ≈171 | *K* moved because our own code changed — the mechanism is unaffected |

### One live risk on P-B, flagged before you run it

`graph.json` is **552,462,397 bytes** against graphify's cap of
`_MAX_GRAPH_FILE_BYTES = 512 * 1024 * 1024 = 536,870,912` (`security.py:32`) —
**over by ~15.6 MB**. The `label` branch handles this deliberately: `_check_cap`
raises, `_over_cap = True`, it prints a warning and degrades only the HTML
render to `node_limit=5000` (`cli.py:1661-1676`), and the comment states "Core
outputs (graph.json + GRAPH_REPORT.md) still get written" — confirmed, the
`to_json(...)` call is unconditional. So `kb-label` should still work, but
expect the warning and do not read it as failure. (This is also independent
motivation for **Option A**: dropping the redundant `knowledge-base::` prefix
from 328,387 ids is the cheapest way back under the cap.)

## R9.6 — what this changes in the recommendation

**Option B was mis-specified as "a change to make". It is a command to run.**
`mise run kb-label` after every build — and note the ordering evidence: the
artifact dates show `.graphify_labels.json` at **2026-08-02 15:03** and
`graph.json` at **2026-08-03 11:15**, i.e. the graph was rebuilt *after* the
last label run, which is exactly why the 171 collisions are sitting in it now.
The durable fix is to make `kb-build` end with a re-cluster (or to document
`kb-build` → `kb-label` as one sequence), not to write any new clustering code.

---

# Round 4 — `study-graph.json`, and a live mid-build read of `graph.json`

**All four predictions made from the code before looking held.** The study graph
is the *clean* case for `repo` and the *worst* case for `community` — and it
independently re-derives R9.4's mechanism in a graph where `cluster()` was never
run on the merged result at all.

## R10.0 — a probe defect of my own, first

`grep -l "scope = study" sources/*.manifest` returns **6** files. The scope set
is **5**. `sources/codegraph.manifest` matches on a **comment at line 8** while
its actual field at line 12 is `scope = corpus`. My round-1 P6 (first
`^\s*scope` line per file) was right; the `-l` grep was the broken probe.
`grep -l` is not a scope parser — `kb_setup/manifest.py:67` reads
`f.get("scope", "corpus")` from parsed fields, and that is the authority.
Recorded because it is the same shape as the `repo`-tag error: a probe that
matches prose and gets read as matching a field.

## R10.1 — prediction from the code, made BEFORE reading the artifact

`_build_study_graph` (`graph.py`) is **one N-ary `_merge_sources_into` call**
over `sources/<n>/graphify-out/graph.json` for each study name, writing
`graphify-out/study-graph.json`. That output is **never fed back as an input**,
nothing merges into it afterwards, and no doc chunk or self sub-graph reaches
it. Predicted:

1. **No `repo` collapse** — 5 distinct tags, one per study source.
2. **`::` depth 1 for every node** — one prefix, never two.
3. **`community` collides ACROSS ALL FIVE**, worse than the corpus, because each
   study source was clustered by its own `graphify extract` (`cli.py:3567`) and
   **nothing ever clusters the merged study graph**.
4. 0 cross-tag edges.

## R10.2 — measured (file stable: mtime `00:23:42`, inode `221003538`, unchanged across the read)

| | value | prediction |
|---|---|---|
| nodes | **69,846** | — (matches your log) |
| links | **211,133** | re-derived; your redacted `2?1?33` fits |
| dangling endpoints | 0 | — |
| **distinct `repo` values** | **5** | ✅ **no collapse** |
| **`::` prefix depth** | **1 for all 69,846** | ✅ one prefix |
| `_origin` | `ast` 69,846 (no semantic layer) | — |
| cross-tag edges | **0** | ✅ |
| CONTROL: cross-community edges | **49,772** | probe discriminates |

`repo` and the id segment agree **exactly**, node for node:

| study source | nodes |
|---|---|
| `codebase-memory-mcp` | 33,396 |
| `GitNexus` | 24,674 |
| `code-review-graph` | 7,758 |
| `mindwalk` | 2,845 |
| **`rootly-graphify-importer`** | **1,173** |

**So Q1's answer is no — and the reason is exactly the one predicted: the study
compose has no second merge over its own output.** The corpus graph's collapse
is not a property of `merge-graphs`; it is a property of that one extra call at
`graph.py:676-681`. The study graph is the control arm for that claim, and it
sits in the same repo.

`rootly-graphify-importer` at 1,173 nodes / 55 communities is plausible for a
small importer repo — and, given it vendors graphify's modules, notably *small*
relative to `graphify`'s own 9,878, i.e. it is the importer plus a partial
vendored copy, not a full mirror.

## R10.3 — the study graph's community collision is FAR worse, and it is arithmetic

Every source starts at 0 and runs contiguously:

| tag | # communities | min | max |
|---|---|---|---|
| `GitNexus` | 1,915 | 0 | 1,914 |
| `codebase-memory-mcp` | 805 | 0 | 804 |
| `code-review-graph` | 339 | 0 | 338 |
| `mindwalk` | 168 | 0 | 167 |
| `rootly-graphify-importer` | 55 | 0 | 54 |

**805 of 1,915 communities span more than one tag — 42%**, against the corpus
graph's 171 of 9,330 (1.8%).

And the number is *derivable*, which is the strongest confirmation of R9.4
available: community `c` is multi-tag iff at least two sources have ≥ `c+1`
communities. With K = {1915, 805, 339, 168, 55}, ids 0-54 are 5-way, 55-167
4-way, 168-338 3-way, 339-804 2-way, 805-1914 single. **Multi-tag count =
805 = the SECOND-LARGEST per-source community count**, exactly as measured.

This is the pure case: N independent `cluster()` enumerations composed verbatim
by `nx.compose`, with **no global re-cluster anywhere**. It confirms R9.4's
mechanism in a graph the corpus's confounders (doc-chunk clustering, the self
merge) never touch.

**Consequence for anything that joins the two graphs:** `study-graph.json`
community `0` means five different things, and `graph.json` community `0` means
another. Any comparison across them is meaningless until one of them is
re-clustered — and **nothing re-clusters `study-graph.json` at all**, so
`mise run kb-label` (which reads `graphify-out/graph.json`) does *not* fix it.
That is a gap the corpus fix does not close.

## R10.4 — Q4: study sources are absent from the corpus graph, control-armed

**I read a `graph.json` that was still being written — stating that plainly.**
Snapshot: mtime `2026-08-05 00:29:20`, size 513,845,361, **inode `221005273`,
unchanged before and after the read** (and an `os.replace` cannot affect an
already-open fd, so the read is internally consistent regardless). The inode had
already moved from `221003538` at `00:27:16`, so the build is actively
replacing this file.

**Build stage of what I read:** 328,659 nodes, 807,033 links, `_origin` = `ast`
328,454 + `semantic` **205** → the corpus compose plus the first doc chunk(s),
**before** the self merge.

| probe | result |
|---|---|
| `rootly-graphify-importer` | **ABSENT** |
| `GitNexus` | **ABSENT** |
| `mindwalk` | **ABSENT** |
| `code-review-graph` | **ABSENT** |
| `codebase-memory-mcp` | **ABSENT** |
| **CONTROL — `graphify`** | PRESENT, 9,878 |
| **CONTROL — `uv`** | PRESENT, 20,524 |
| **CONTROL — `mise`** | PRESENT, 19,651 |
| **CONTROL — `hk`** | PRESENT, 2,131 |
| **CONTROL — `codegraph`** (the `scope = corpus` one R10.0 nearly mislabelled) | PRESENT, 6,390 |

The substring probe `"rootly" in node_id` is two-sided by construction: **0 hits
in `graph.json`, 1,173 hits in `study-graph.json`**, same script, same run
shape. So the absence discriminates.

**`scope = study` worked.** Code-level guarantee behind it: `build()` partitions
`with_code` into disjoint `corpus` / `study` lists by `study_names`, and only
`corpus` reaches `_merge_sources_into(out=graph.json)`. I also checked the one
back door — a doc chunk could inject a study source's nodes into `graph.json` —
and **none of the 18 files in `sources/extractions/` names any study source**.

### Two bonus live confirmations from that same read

- **39 distinct `repo` values, depth 0/1** at this stage. The collapse to 2 has
  **not happened yet**. That is P2/P3b confirmed *in flight*, on a graph neither
  of us had seen: the tags are correct right up until `graph.py:676-681`.
- **`communities_spanning_multiple_tags = 0`** right now, over 9,203
  communities. The doc-chunk merge's `cluster()` has just produced a clean
  global partition and `.self-graph` is not in yet.

**So the phantom spans are created, live, by the self merge.** Concrete
prediction for when your build exits, on top of R9.5's P-A/P-B:

> the count goes **0 → K** at the self merge (K = `.self-graph`'s own community
> count, 171 last build), then **K → 0** on `mise run kb-label`.

If it is anything other than 0 immediately before the self merge, or non-zero
after `kb-label`, R9.5's falsifier table applies unchanged.

### Two incidental deltas in this build

- `graphify` 9,812 → **9,878** nodes — consistent with the pin advancing to
  0.9.33 (the rootly manifest already cites "our 0.9.33"). Flagged, not chased:
  every `file:line` in this report was read against the **0.9.32** install.
- **`ruff` is STILL absent** — 0 nodes in a fresh build. #131 reproduces.

## Revised recommendation (supersedes the round-1 list)

Ordered by cost. Everything above the line is free of LLM spend.

1. **B — re-cluster after the last merge. THIS IS A COMMAND, NOT A CHANGE:
   `mise run kb-label`.** `graphify label` already re-clusters the whole
   aggregate (`cli.py:1684-1697`) and rewrites graph.json. No LLM (deterministic
   hub labels). Expect an over-cap warning — graph.json is 15.6 MB past
   graphify's 512 MiB cap; the core outputs still write (R9.5). The durable part
   is making `kb-build` end with it, so a build never again leaves the graph in
   the state measured here.
2. **A — fold the self sub-graph into the single N-ary merge.** Restores 38
   `repo` tags, stops the +1-segment-per-build id growth (R3), un-breaks the 5
   hyperedges. Do it before anything encodes current ids.
3. **F — federation / query-per-source-then-join.** Answers Ray's question
   *today* at zero cost: the id segment partitions the corpus by tool with 100%
   coverage, and R1 prices the recall given up at **0 of 816,538 edges**.
   Nothing else on this list is needed to start.

---

4. **E — ingest the tools' DOCS + a Claude Code manifest.** LLM cost, per
   source. This is the real content gap: `cli.py:2897-2910` skips every `.md`
   under `kind = code`, which is 44 of 46 manifests.
5. **G (NEW) — a joint cross-source semantic chunk.** The *only* mechanism that
   produces a cross-source edge (R4-Q1: no algorithm in graphify builds
   `semantically_similar_to`; an LLM does, from chunk membership). Requires E
   first. Start with one tool pair, one topic.
6. **D — a hand-authored bridge chunk.** Strictly worse than G for the same
   token budget unless the relationships are ones no document states.
7. ~~**C — label-normalisation dedup across sources.**~~ **WITHDRAWN (R5).**
   Measured join surface: 4,910 shared labels topped by `main()` (36 sources),
   `path`, `run()`, `name`, `version`, `config`. Noise, not signal.

## Loose ends / UNVERIFIED

**Closed in round 2:** `dedup.py` / `_minhash.py` / `symbol_resolution.py` /
`semantic_cleanup.py` (R4); the 182,041 skipped edges (R2); the depth-3 growth
question (R3); the community key space (R8).

**Closed in round 3:** `cluster.py` + the installed `networkx/…/louvain.py`
(R9.1-R9.2); `remap_communities_to_previous`'s call sites and its injectivity
(R9.3); the id-reuse mechanism (R9.4). R7 is **superseded by R9.5** — the
mechanism is confirmed, but the prediction now forks on whether `kb-label` ran.

Still open — genuinely unrun, and only measurement can close them:

- ~~**`cluster()` was not read**, so R7's prediction that re-clustering drives the
  phantom count to 0 is **unrun**~~ — the CODE is now read; the OUTCOME is still
  unmeasured. See R9.5's two predictions and their falsifier table. A stated
  falsifier, not a result.
- `god_nodes` / `surprising_connections` are computed in `_merge_docs.py:36-37`
  but only reach `GRAPH_REPORT.md`; I did not partition them by source tag.
  **UNVERIFIED** whether any god node spans sources — though with 0 cross edges
  it cannot.
- Why `ruff` produced no sub-graph and `ty` only 36 nodes. Not probed;
  `sources/ruff/` is a gitignored clone so this needs a build, which was out of
  scope here.
- ~~Whether `study-graph.json` shows the same tag collapse. Not probed.~~ **CLOSED in round 4 (R10): it does NOT collapse — 5 distinct `repo` tags, depth 1. Its `community` collision is far worse (805 of 1,915, 42%) and nothing re-clusters it, so `kb-label` does not reach it.**

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — read the installed 0.9.32 source: `build.py`, `cli.py` (`merge-graphs`, `prefix_graph_for_global`, `distinct_repo_tags`, `extract`, `merge-chunks`, `merge-semantic`, `cache-check`), `dedup.py`, `_minhash.py`, `symbol_resolution.py`, `semantic_cleanup.py`, `analyze.py`, `report.py`, `llm.py`, `extract.py`, `skills/*/references/extraction-spec.md`.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo: `python/src/kb_setup/graph.py`, `_merge_docs.py`, `sources/*.manifest`, `graphify-out/graph.json`.
- [astral-sh/ruff](https://github.com/astral-sh/ruff) — pinned manifest, contributes 0 nodes.
- [astral-sh/ty](https://github.com/astral-sh/ty) — pinned manifest, contributes 36 nodes.
- [astral-sh/uv](https://github.com/astral-sh/uv) — pinned manifest, 20,524 nodes.
- [jdx/mise](https://github.com/jdx/mise) — pinned manifest, 19,651 nodes.
- [jdx/hk](https://github.com/jdx/hk) — pinned manifest, 2,131 nodes.
- [apple/pkl](https://github.com/apple/pkl) — pinned manifest, 16,910 nodes.
