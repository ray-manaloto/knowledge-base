# Research: Should graphify remain a dependency, or does the tool need its own layer?

**Agent:** research-graphify-dependency
**Date:** 2026-08-02
**Evidence base:** the INSTALLED graphify **0.9.31** and **0.9.32** sources under
`/Users/rmanaloto/.local/share/mise/installs/pipx-graphifyy/`, this repo's
`python/src/kb_setup/`, `.self-graph/graphify-out/graph.json`, PyPI metadata for
`graphifyy`, and `mise run kb-query --prose --idf`.

---

## RECOMMENDATION (up front)

**Keep graphify as an EXTRACTION dependency. Own RETRIEVAL outright, and say so
explicitly in the architecture.** Do not fork, do not absorb.

The seam is already cut and this repo is already standing on the far side of it: the
best-measured retrieval arm (`kb-query --idf`) never invokes graphify. What is missing is
not capability — it is a **declared boundary**. Today the split is an accident of three
incremental PRs; it should become the stated architecture, because a distributable tool
needs to tell its consumers which half is ours.

Concretely:

1. **Declare `graph.json` the contract.** graphify produces it; `kb_setup` consumes it.
   Nothing in the retrieval path may call a graphify private function.
2. **Move `--idf` from "third arm" to the default**, once P4 lands. It already wins.
3. **Build P3/P4/P6 in `kb_setup`** against `graph.json` + networkx. No fork needed.
4. **Push #106-class defects upstream** — extraction is the half we should not own.
5. **Set `GRAPHIFY_MAX_GRAPH_BYTES` deliberately** in `graphify_env.clean_env()` rather
   than inheriting the 512 MiB default at 75% occupancy. Cheap, and it removes a failure
   mode that presents as a build crash rather than a capacity signal.

Rationale in one line: **the retrieval code we would gain by forking is ~2,157 lines we
already bypass; the extraction code we would inherit is ~5,700 lines plus 61 tree-sitter
grammars we could never maintain.**

---

## (a) Can #12 be fixed on top of graphify? — YES. Partly already is.

### What graphify's query actually does (installed 0.9.31)

`graphify query` → `cli.py:852-975` → `serve.py:_query_graph_text` (line 1033):

1. `_query_terms()` (`serve.py:247`) — tokenize, drop multilingual stopwords.
2. `_score_query()` (`serve.py:433`) — **IDF-weighted** lexical scoring. Tiers
   `_EXACT_MATCH_BONUS=1000` / `_PREFIX=100` / `_SUBSTRING=1` / `_SOURCE=0.5`, each
   multiplied by `_compute_idf()` (`serve.py:274`), plus term-coverage squaring (#1602)
   and a trigram candidate prefilter (`serve.py:337`).
3. `_pick_seeds()` (`serve.py:627`) — **top-k = 3 seeds**, 20% score-gap cutoff,
   per-label dedup, per-term seed guarantee (#1445).
4. `_filter_graph_by_context()` (`serve.py:805`) — filters EDGES by `context`.
5. `_bfs`/`_dfs` at **hardcoded depth=2** (`cli.py:955`), with a p99-degree hub block.
6. `_subgraph_to_text()` — truncate to a token budget.

### ⚠️ Issue #12's premise is STALE on one point

#12 states `kb-query` has "no scoping, no lexical/vector hybrid, **no IDF**, no recency
weighting, no fusion, no reranking."

**graphify 0.9.31 HAS IDF.** `_compute_idf` at `serve.py:274`, applied at `serve.py:470`
(`idf = _compute_idf(G, norm_terms)`) and per-term at `serve.py:545` (`w = idf.get(t, 1.0)`).

This is the repo's own `probes-need-a-control-arm.md` trap — except the stale secondary
artifact is **our own issue**, not graphify's tracker.

**But #12's substantive complaint survives, sharper:**

> graphify's IDF ranks **SEEDS ONLY**. It then returns an unranked 2-hop BFS
> neighbourhood of ≤3 seeds, in traversal order, cut by a token budget. **Nothing scores
> the returned set.** On a 140k-node graph where 138k are code AST, one lexically-similar
> code seed floods the whole budget.

That reframing matters for the dependency question: the defect is not that graphify's
scorer is weak, it is that **graphify's query has no concept of ranking a result set at
all** — it is a subgraph *extractor*, not a retriever. That is a design boundary, not a bug.

### Capability matrix — installed 0.9.31

| Capability | Present? | Evidence |
|---|---|---|
| IDF term weighting | **YES** | `serve.py:274`, used at `:470`, `:545` |
| Trigram candidate index | **YES** | `serve.py:337 _get_trigram_index` |
| Edge-`context` scoping (`--context call/import/field/…`) | **YES** | `cli.py:883/886`; 8 contexts + alias map `serve.py:690` |
| Scoping by SOURCE or node KIND | **NO** | `cli.py:865-889` parses only `--budget`/`--context`/`--graph`/`--dfs` |
| Ranking of the RETURNED set | **NO** | `_query_graph_text` returns `header + _subgraph_to_text(...)` |
| BM25 (TF saturation + length norm) | **NO** | graphify's IDF is `log(1+N/(1+df))`, substring `df`, no TF, no length norm |
| RRF / fusion | **NO** | one scorer |
| Reranker | **NO** | — |
| Embeddings / vector search | **NO** (by design) | see control-armed table below |
| Recency / age decay | **NO** | — |
| `query --json` machine-readable output | **NO** | `cli.py:975` `print(_result)` — text blob only |
| Configurable traversal depth | **NO** | `depth=2` hardcoded `cli.py:955` |

### Verdict

**#12's remaining items (P3 rerank, P4 neighbour expansion, P5 embeddings, P6 age decay)
are all buildable in `kb_setup` with no fork.** The seam is the **artifact**, not an API:
`graph.json` is plain node-link JSON that `networkx.json_graph.node_link_graph` reads —
graphify itself does exactly this at `cli.py:915`.

Notably **P4 is the item that re-imports traversal into our own retriever**, and it is
~20 lines of networkx over the same JSON. That is the moment `kb_setup` stops being "a
thin orchestration layer" and becomes a retrieval engine consuming a graphify artifact.

---

## How far the existing `--idf` answer goes

### It already crossed the seam

`mise run kb-query -- "<q>" --idf` **does not call graphify at all.** Verified at
`python/src/kb_setup/graphify_ops.py:253`:

```python
if wants_idf:
    return _idf_query(repo_root, rest)
```

— returning before any `graphify query` subprocess is spawned. `_idf_query` loads
`graphify-out/graph-prose.json` with `lexical.load_index()` and ranks with pure-python
BM25. Confirmed live: my own query printed
`[kb-query] --idf: 2,817 indexed node(s) from graph-prose.json`.

**So the best-measured arm (natural recall 5/8 pairs, vs `--prose` 3/8, vs unscoped 1/8)
is the arm with zero graphify involvement at query time.**

### What `lexical.py` does well (317 lines)

- `INDEXED_FIELDS = ("label", "rationale")` — scope deliberately locked; `source_file`
  and `community_name` rejected because their boilerplate dilutes IDF.
- `K1=1.2`, `B=0.75` at literature defaults, explicitly **untuned** to avoid fitting the
  same golden set that grades it.
- BM25+ IDF (`log(1 + (N-df+0.5)/(df+0.5))`) — floored, not clamped, with the reasoning
  and the reverted-alternative measurement recorded in the docstring.
- Deterministic tie-break by graph-file position.
- Refuses an empty index loudly rather than serving nothing (keeps `evals._arm_defect`
  falsifiable).

This is a genuine retrieval component, not a shim.

### Where it stops — four gaps, all inside OUR layer, none blocked by graphify

1. **It is FLAT, not graph-aware.** `search()` returns ranked `Hit`s and never traverses
   an edge. **Every typed relation the corpus paid to extract is unused at query time.**
   This is the single largest piece of value on the floor, and it is #12's P4.
2. **It is prose-only.** It reads `graph-prose.json`. A question spanning code *and* prose
   has no arm at all — `--prose`/`--idf` drop 138k AST nodes **wholesale** rather than
   scoping or down-weighting. A blunt instrument standing in for the `--kind`/`--source`
   scoping P0 actually wanted.
3. **It returns pointers, not content.** A `Hit` is `(source_file, node_id, label, score)`.
   `graphify query` at least renders a readable subgraph. So the best arm is also the
   **least useful output shape** — it says where to look, not what is there.
4. **It has no second scorer to fuse with.** #12 P2 measured RRF NEGATIVE (4/8 vs 5/8) and
   diagnosed it structurally: graphify returns 7-12 distinct documents against lexical's
   ~75, so consensus degenerates into short-list membership. **That diagnosis is itself
   evidence that graphify's traversal output is not a useful second scorer** — which is an
   argument for owning retrieval, not for fusing with graphify.

---

## (b) Is graphify maintained and moving? — YES, aggressively

PyPI metadata for `graphifyy`, read 2026-08-02:

- **200 releases total.**
- **Near-daily cadence: 25 releases in 26 days** (0.9.8 on 07-06 → 0.9.32 on 08-01).
- Pinned here **0.9.31** (2026-07-30); upstream latest **0.9.32** (2026-08-01), one day old.
- `requires_python >= 3.10`. Repo `Graphify-Labs/graphify`.

The source is dense with recent issue refs (#1219, #1356, #1445, #1446, #1504, #1547,
#1602, #1659, #1704, #1766, #1883, #2032, #2076, #2082, #2141, #2309, #2323) — four-digit
numbers on a young project indicate a high-throughput tracker.

**What 0.9.32 changed** (diffed 0.9.31 → 0.9.32 directly):

- `serve.py` gains `_complete_induced_edges()` (#2323) — traversal returned a *tree*, not
  the induced subgraph, so an edge between two seeds could never be rendered. A real
  retrieval-correctness fix.
- `extract.py` (88 changed lines) — C# `partial class` node merging.
- Also touched: `build.py`, `dedup.py`, `detect.py`, `extractors/engine.py`, `paths.py`,
  `ruby_resolution.py`, `watch.py`.

**Reads both ways:**

- *For depending:* not abandonware; extraction improvements land continuously, for free.
- *Against depending:* a **pre-1.0 project on a near-daily release train**, whose retrieval
  internals are all underscore-private and **none of which is exported from
  `graphify/__init__.py`**.

**Control arm on that last claim:** `__init__.py`'s `_getattr_` `_map` exports 16 names —
`extract`, `collect_files`, `build_from_json`, `cluster`, `score_all`, `cohesion_score`,
`god_nodes`, `surprising_connections`, `suggest_questions`, `generate`, `to_json`,
`to_html`, `to_svg`, `to_canvas`, `to_wiki`, `reflect`, `save_query_result`. So the probe
finds exports fine; the absence of any *query/retrieval* export is a real signal.

> **graphify's public Python API is an EXTRACTION + BUILD + EXPORT API. Retrieval was
> never part of its contract.** That is the strongest single argument that the seam
> belongs exactly where this repo has already put it.

---

## (c) Cost of forking/absorbing, and what would be lost

Measured on the installed tree: **38,640 lines** of top-level python, **6.5 MB** package.

| Component | LOC | Rebuild cost |
|---|---|---|
| `extract.py` — AST extraction engine | **5,717** | prohibitive |
| `extractors/` — 27 per-language modules | (dir) | prohibitive |
| **61 bundled `tree_sitter_*` grammar packages** | vendored | prohibitive — **this is the moat** |
| `cli.py` | 3,888 | mostly not needed |
| `llm.py` — backend detect/dispatch | 3,115 | not needed (we strip all but Claude) |
| `serve.py` — MCP server + query | 2,157 | **the part we'd want** — and already bypassed |
| `install.py` | 2,288 | not wanted (writes `~/.claude` without `--project`) |
| `build.py`/`cluster.py`/`dedup.py`/`analyze.py` | ~3,600 | moderate — Louvain, hub scoring, minhash dedup |
| `export.py` + `exporters/` (neo4j/falkordb push) | ~1,100 | moderate |
| `wiki.py`/`report.py`/`callflow_html.py`/`tree_html.py` | ~3,000 | not needed for a query tool |
| `symbol_resolution.py` + `*_resolution.py` + `scip_ingest.py` | ~1,200 | high — this is #106's territory |

**A fork means owning 61 tree-sitter grammar integrations and a 5,717-line extractor, in
order to fix a retrieval defect living in a 2,157-line file we already bypass.** That
asymmetry decides it.

### What a fork would actually buy — three things, each with a cheaper route

1. `--source`/`--kind` scoping → already achieved by deriving `graph-prose.json`.
2. Ranking the returned set → already achieved in `lexical.py`.
3. Fixing #106 → genuinely upstream. **But see below: it is also fixable as a
   post-extraction graph repair in our layer.**

### Constraints a consumer inherits (the real risks)

- **A 512 MiB graph size cap — but it is TUNABLE, and I initially over-called this.**
  `cli.py:408 _enforce_graph_size_cap_or_exit` → `security.py:357
  check_graph_file_size_cap`, invoked on **7 CLI paths including `query`**, plus direct
  library calls from `serve._load_graph`, `build`, `benchmark`, `tree_html`,
  `callflow_html`, `prs`, `global_graph`, `watch`, `export`. `kb_setup/graph.py` records
  hitting it — a build went "7.6 MiB past graphify's 512 MiB cap and failed outright",
  and our aggregate graph is **382 MB (75% of the default)**.

  **However:** the cap is resolved per call via `_max_graph_file_bytes()` and is
  overridable with **`GRAPHIFY_MAX_GRAPH_BYTES=<bytes>`** (or `=<N>GB`), and the raised
  error message says so. It is a memory-bomb guard, not an architectural ceiling. This
  demotes it from "the largest product risk" to "a default a distributable tool must set
  deliberately for its users". *Recorded as a correction: my first pass reported this as a
  hard ceiling before reading `security.py`.*
- **`graphify query` output is unparseable text** — no `--json`. Any programmatic consumer
  must re-parse rendered prose or read `graph.json`. This alone forces retrieval into our
  layer.
- **Hardcoded `depth=2`** (`cli.py:955`), not a flag.
- **Install-time footprint**: bare `graphify install` mutates `~/.claude`. A distributable
  tool depending on graphify must wrap or document that hazard for its users.

---

## (d) The cleaner seam — extraction-only. And #106 is the test of it.

### #106: the issue's stated root-cause hypothesis is WRONG, and I found the real one

#106 says: *"module-qualified calls (`lexical.build_index(...)`) produce no edge"* and asks
whether that is graphify's extractor or `kb_setup`'s consumption.

**Neither. graphify 0.9.31 HAS a Python module-qualified call resolver.**

`_resolve_python_member_calls` at `extract.py:2200`, registered at `extract.py:2978` as
`LanguageResolver("python_member_calls", frozenset({".py"}), _resolve_python_member_calls)`.
Its **"Module arm (#1883)"** resolves exactly `module.func()` where `module` is imported
into the caller's file, with alias support (#2082). Sibling resolvers exist for Swift,
TypeScript, C++, C#, Java, Obj-C, Ruby.

The module arm bails at four points:

```python
mods = [t for t in imported_by_filenode.get(caller_file, ())
        if t in contains_children
        and (_module_stem_key(t) == rkey or file_aliases.get(t) == rkey)]
if len(mods) != 1: continue          # ← BAIL 1
children = contains_children[mods[0]].get(_key(callee), [])
if len(children) != 1: continue      # ← BAIL 2
```

**Empirical probe against `.self-graph/graphify-out/graph.json`:**

| Probe | Result |
|---|---|
| `build_index` node | 1, at `python/src/kb_setup/lexical.py` |
| callers of `build_index` | **1** — `load_index()`, same file (so tests are missing) |
| **CONTROL ARM:** callers of `tokenize` (direct-call style) | **2** — probe discriminates |
| `contains` children of the `lexical.py` file node | **9** (incl. `build_index()`) — bail 2 would pass |
| `imports_from` edges INTO the `lexical.py` file node | **2** — from `eval_cases.py`, `graphify_ops.py`. **`tests/test_lexical.py` is NOT among them.** |
| **CONTROL ARM:** import edges emitted FROM `tests/` at all | **62** — so tests do emit imports; probe discriminates |
| Where those 62 land | **31 on `python/src/kb_setup/__init__.py`** |

`tests/test_lexical.py:32` is `from kb_setup import lexical` — the *same source form* that
works from `graphify_ops.py`. The difference is the resolution target:

> **ROOT CAUSE (#106):** `from <pkg> import <module>` resolves to the package's
> **`__init__.py`** when the importer is not a sibling of the module. `_module_stem_key`
> then computes `"__init__"`, which never equals the receiver `"lexical"`, so **BAIL 1
> fires** and the module arm never runs. The module-qualified *call* resolver is fine;
> the *import* edge it depends on points at the wrong node.

This is a **src-layout cross-root import-resolution defect**, not a call-resolution defect.
#106's title and its "next step" both aim at the wrong component.

### Why this is the decisive datapoint for the seam

- The bug is in **extraction** — precisely the half we should not own. It needs
  tree-sitter/AST context we would have to reimplement.
- It is **cheaply repairable in our layer anyway**, as a post-extraction graph pass over
  `graph.json`: rewrite an `imports_from` edge targeting `<pkg>/__init__.py` to
  `<pkg>/<name>.py` when a sibling file stem matches the imported name (~30 lines), then
  re-run the module arm's logic. That is a *patch*, and it should be labelled one.
- So the honest split is: **push it upstream** (they are shipping daily and have already
  built #1883/#2082 for exactly this shape), and **carry a local repair pass meanwhile.**

That pattern — upstream the extraction defect, patch locally, own retrieval outright — is
the seam, and #106 is its worked example.

---

## Control-armed negatives

Per `probes-need-a-control-arm.md`. **My first grep sweep was a broken probe and the
control arm caught it** — a zsh quoting fault made `--include=*.py` fail, so *every* term
returned 0 including `networkx`. Re-run with `grep -rilF … --include='*.py'`:

**Control arm (must be non-zero):** `networkx` → 21 · `tree_sitter` → 19 · `louvain` → 3 ·
`idf` → 2 · `trigram` → 1 · `LM Studio` → 2 (the space-spelling trap, deliberately included).

**Negative arm, spelling-varied:** `rerank` 0 · `re-rank` 0 · `re_rank` 0 ·
`cross-encoder` 0 · `cross encoder` 0 · `bm25` 0 · `BM-25` 0 · `okapi` 0 · `faiss` 0 ·
`hnsw` 0 · `cosine` 0 · `sentence-transformer` 0 · `sentence transformer` 0 · `rrf` 0 ·
`reciprocal rank` 0 · `semantic search` 0.

`embedding` → 4 files and `vector` → 5 files, **all incidental and individually inspected**:
"escape for embedding in a YAML/Cypher scalar" (`ingest.py:14`, `export.py:117/340`,
`security.py:397`), Go interface embedding (`extractors/go.py:268`), SSRF "vectors"
(`security.py:75`, `llm.py:267`, `fortran.py:23`), `std::vector` as a C++ generic
(`extractors/engine.py:310/924/2931`), and vector PDF icons (`detect.py:507`). **No
retrieval-embedding machinery.**

| Claim | Probe | Control arm | Verdict |
|---|---|---|---|
| No query `--json` | parse `cli.py:852-975` | `--budget`/`--context`/`--graph` all found in the same block | HOLDS |
| No query/retrieval export | read `__init__.py` `_map` | 16 exports found incl. `save_query_result` | HOLDS |
| No `--source`/`--kind` scoping | same parser block | `--context` found at `cli.py:883/886` | HOLDS |
| No embeddings/rerank/fusion | 19-term spelling-varied grep | 6 known-present terms, all non-zero | HOLDS |
| graphify HAS IDF (contra #12) | `_compute_idf` `serve.py:274`, used `:470`/`:545` | n/a (positive) | **#12 IS STALE** |
| graphify HAS a Python module-call resolver (contra #106) | `extract.py:2200`, registered `:2978` | n/a (positive) | **#106'S HYPOTHESIS IS WRONG** |
| tests→lexical import edge missing | self-graph probe | 62 import edges DO come from `tests/` | HOLDS |

---

## Tradeoffs of the recommendation

**Keeping graphify for extraction:**

- ✅ 61 tree-sitter grammars, 27 extractors, symbol resolution, clustering, exporters,
  MCP server — all free and improving daily.
- ✅ AST extraction stays free (no LLM), which is the corpus economics.
- ❌ Inherits the **512 MiB cap** — a hard product ceiling we are at 75% of.
- ❌ Inherits a pre-1.0, daily-moving dependency and its `~/.claude` install hazard.
- ❌ Extraction defects (#106, #19) are not ours to fix; we wait or patch locally.

**Owning retrieval outright:**

- ✅ No cap, no text-blob parsing, no private-API coupling, full control over ranking.
- ✅ Already the best-measured arm; the code exists and is well-reasoned.
- ❌ We now own BM25/rerank/expansion maintenance forever.
- ❌ **Two retrieval paths currently coexist** (`graphify query` for `--prose`/default,
  `lexical` for `--idf`) with different output shapes. That is the debt this decision
  should retire — pick one, keep the other only as a measurement arm.

**The alternative I rejected — fork/absorb:** buys three things, all of which have a
cheaper route, at the cost of ~38k lines and 61 grammars.

---

## What I could NOT determine

1. **Whether the local `imports_from` → `__init__.py` repair actually restores the
   `affected` edges.** I diagnosed the bail condition from source + graph probes; I did
   **not** implement and re-extract to confirm. Bail 2 looks satisfied (9 `contains`
   children present) but that is inference, not measurement.
2. **Whether 0.9.32 changes #106.** `extract.py` differs by 88 lines, but the diff I read
   is C# partial-class work. I did not diff `extractors/engine.py`'s import handling.
3. ~~Whether the 512 MiB cap is configurable.~~ **RESOLVED** — it is, via
   `GRAPHIFY_MAX_GRAPH_BYTES` (`security.py:357-383`). See the corrected note in (c).
   What remains unknown is whether raising it is *safe* at our scale: a 382 MB
   `graph.json` is parsed into networkx in memory by every graphify path that touches it,
   and I did not measure the resident-set cost.
4. **Whether graphify would accept the #106 fix upstream.** I did not read their
   contributing guide or open a discussion. Given #1883/#2082 exist for exactly this
   shape, the precedent is favourable, but that is a guess.
5. **Issue #19** (12k URL truncation, no boilerplate removal) — I read the issue body
   ("see session handoff", no detail) and did not locate the handoff or verify the
   truncation in `fetch`/`detect`. It is unexamined here.
6. **Any measurement of P4.** I argue neighbour expansion is the largest win on the floor;
   that is reasoning from the corpus's typed edges, **not** a measured recall delta.

---

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — read the installed
  0.9.31 and 0.9.32 sources (`serve.py`, `cli.py`, `extract.py`, `symbol_resolution.py`,
  `__init__.py`, `extractors/`) and PyPI release metadata for `graphifyy`.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issues
  #12, #19, #106; `python/src/kb_setup/` (`lexical.py`, `graphify_ops.py`, `graph.py`);
  `.self-graph/graphify-out/graph.json`.
