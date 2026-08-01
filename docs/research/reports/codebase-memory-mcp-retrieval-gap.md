# codebase-memory-mcp vs graphify — retrieval gap analysis

- **Tool:** [DeusData/codebase-memory-mcp](https://github.com/deusdata/codebase-memory-mcp) ("CBM")
- **Pinned at:** `d6be58ef9d43c574a2d1b0827ecc1e3c4846f0fe` (`sources/codebase-memory-mcp.manifest`, `kind = code`, `scope = study`)
- **Language / licence:** C (+ one C++ file), MIT
- **Compared against:** graphify **0.9.31**
- **Lens:** retrieval
- **Status:** COMPLETE

## Version provenance (armed)

`graphify_exe(repo_root)` resolves to
`~/.local/share/mise/installs/pipx-graphifyy/0.9.31/bin/graphify` → `graphify 0.9.31`.
A bare `graphify` on PATH resolves through the mise shim to the **same** 0.9.31,
so for this session the PATH binary and the pin agree — but every claim below was
read off the pinned install's `site-packages/graphify/`, not the shim.

> Reading note: most of the C line count in CBM is **not CBM's logic**.
> `internal/cbm/vendored/ts_runtime/` is a vendored tree-sitter runtime and
> `internal/cbm/vendored/grammars/<lang>/` holds 159 pre-generated grammar
> parsers (per the repo's own `THIRD_PARTY.md`). Claims below are anchored to
> CBM's own extractors (`internal/cbm/extract_*.c`), pipeline (`src/pipeline/`),
> query surface (`src/mcp/`, `src/cypher/`) and store (`src/store/store.c`).

---

## 1. Indexing model

| | CBM | graphify 0.9.31 |
|---|---|---|
| Parse | tree-sitter AST, 158–159 vendored grammars compiled into one static binary | AST extraction per language, `graphify update` is AST-only and free |
| Beyond AST | **Hybrid LSP** — a hand-written C re-implementation of type resolution for ~12 languages (`internal/cbm/lsp/{go,rust,java,…}_lsp.c`): parameter binding, return-type inference, generic substitution, trait/UFCS resolution | `symbol_resolution.py`; also an LSP/SCIP path (`scip_ingest.py`) |
| Embeddings | **Static, precomputed, offline.** `vendored/nomic/code_vectors.bin` — 40,856 tokens × 768d **int8** vectors distilled from `nomic-ai/nomic-embed-code`, embedded via `.incbin`. Generated once by `scripts/extract_nomic_vectors.py` (~2–3 h GPU). **No model runs at index or query time** | no vector store by design |
| Store | SQLite (`src/store/store.c`), persists to `~/.cache/codebase-memory-mcp/` | `graphify-out/graph.json` (+ optional Neo4j/FalkorDB push) |
| Input kinds | code + IaC (Dockerfile, K8s, Kustomize) + ADRs | code, **documents, papers, images, video/transcripts, URLs** |

**The embedding finding is the sharpest thing about CBM's design.** Its "semantic
search" is not a live embedding model — it is a frozen token→vector lookup table
compiled into the binary. That makes semantic scoring *deterministic and offline*,
which is the property graphify achieves by having no vectors at all. Two different
routes to the same "no API key, no daemon, reproducible" outcome.

## 2. Query surface, and what a query returns

CBM's dispatch table (`src/mcp/mcp.c:10900–10947`) — exactly 15 tools:

`list_projects`, `get_graph_schema`, `search_graph`, `query_graph`, `index_status`,
`check_index_coverage`, `delete_project`, `trace_path` (alias `trace_call_path`),
`get_architecture`, `index_repository`, `get_code_snippet`, `search_code`,
`detect_changes`, `manage_adr`, `ingest_traces`.

**REFUTED (my own draft claim).** I first read the README's
"Semantic search (`semantic_query`)" against that dispatch list and drafted
*"the README advertises a `semantic_query` tool that does not exist."* False.
`semantic_query` is a **parameter** of `search_graph`, not a tool
(`src/mcp/mcp.c:420` input schema; `run_semantic_query_core` at `:3067`).
Probe: `semantic_query` → 16 hits in CBM's own C, control `search_graph` → 77.
The first run of this probe returned 0 for *both* arms because zsh refused the
unquoted `--include=*.c` glob — a uniform negative, i.e. a broken probe, not a
finding.

**Where the surfaces genuinely differ:**

- **Cypher: CBM *accepts* it, graphify only *emits* it.** CBM has a Cypher-like
  query engine (`src/cypher/`), e.g.
  `MATCH (f:Function)-[:CALLS]->(g) WHERE f.name='main' RETURN g.name`, exposed as
  the `query_graph` tool. My draft said "graphify has no Cypher" — **refuted**:
  `cypher` → 29 hits in installed 0.9.31 (control `neo4j` → 24, so the probe
  discriminates). But reading them shows they are all **export-side**:
  `exporters/graphdb.py` (Neo4j/FalkorDB push), `export.py:339 _cypher_escape`,
  injection-sanitising for emitted statements. graphify **generates** Cypher for a
  graph DB; it does not **accept** Cypher as a query input, and `--help` exposes no
  such verb. The precise claim is therefore: *graphify has no Cypher **input**
  surface* — advantage CBM for direct structural selection, though graphify reaches
  the same place indirectly by pushing to Neo4j/FalkorDB and querying there.
- CBM returns **code snippets** (`get_code_snippet`) and does graph-scoped grep
  (`search_code`). graphify's `query` returns nodes with `src=`/`loc=` anchors and
  a token budget, leaving the file read to the agent.
- **Both optimise for the LLM context window, by opposite mechanisms — and each
  lacks the other's.** graphify's `query` takes a **`--budget N` token cap** and
  *reports its own truncation* ("TRUNCATED: showing 70 of 487 nodes… raise
  `--budget`"). CBM instead makes the output **denser**: `src/mcp/compact_out.h`
  emits **TOON** (Token-Oriented Object Notation), declaring tabular fields once in
  a header and streaming rows, "cutting 40–60% of tokens on homogeneous result
  sets".
  Armed: `max_tokens|token_budget|"budget"` → **0** hits in `src/mcp/`, control
  `"limit"` → **7**. So CBM has a result-count `limit` but **no token budget**, and
  graphify has no dense output encoding. This corrects my earlier guess that
  `compact_out.c` might be CBM's budget — it is a different mechanism entirely.

## 3. Blast radius — "what breaks if I change this"

Both have an answer, and they answer *different questions*:

- **graphify `affected "X"`** — reverse traversal from a named node,
  `--relation R` (repeatable), `--depth N`. Input is a **symbol**; output is
  everything upstream of it in the graph. Answers *"if I change this function,
  what depends on it?"*
- **CBM `detect_changes`** — maps **uncommitted git changes** to affected symbols
  with risk classification. Input is the **working tree diff**; output is the
  symbols your actual edits touch.

Neither subsumes the other. CBM's is stronger for "I already made an edit, what did
I just endanger"; graphify's is stronger for "before I touch X, who is downstream".
CBM can reach graphify's shape via `trace_path(direction="inbound")` or Cypher;
graphify has no diff-driven entry point in 0.9.31's `--help` verb list.

## 4. Freshness / incremental update

- **CBM**: `file_hashes` table (`src/store/store.c:233`) drives incremental
  re-index; a **background watcher** (`src/watcher/watcher.c`) plus a per-account
  **coordination daemon** shared across Claude Code / Codex / OpenCode re-indexes on
  change automatically. Also ships a **team-shared artifact**:
  `.codebase-memory/graph.db.zst` (zstd-compressed SQLite, two tiers, auto
  `merge=ours` gitattributes) so a teammate skips the reindex.
- **graphify**: `graphify update <path>` (AST-only, free) and `graphify watch <path>`.
  This repo drives it via `mise run kb-watch` because `watch` refreshes only that
  path's scoped sub-graph and cannot update the merged aggregate.

**Advantage CBM, clearly, on both axes.** Automatic multi-client freshness with no
task wrapper, and a committable compressed graph artifact — versus this repo's
situation where `graphify-out/graph.json` is 382 MB and *cannot* be committed
(`do-not.md` invariant 5), so consumers must go through `kb-serve` MCP.

## 5. Provenance — extracted vs inferred

**REFUTED (my own draft claim).** I drafted *"CBM has no edge provenance, unlike
graphify's EXTRACTED/INFERRED."* That is wrong in the direction that matters.

- **graphify**: `confidence` is a first-class edge attribute over a **validated
  closed vocabulary** — `VALID_CONFIDENCES = {"EXTRACTED","INFERRED","AMBIGUOUS"}`
  (`validate.py:5`), with default scores `{EXTRACTED:1.0, INFERRED:0.5,
  AMBIGUOUS:0.2}` (`export.py:159`), preserved through GraphML export
  (`export.py:977`), and surfaced as a dedicated MCP **audit resource**
  `graphify://audit` — "EXTRACTED/INFERRED/AMBIGUOUS edge breakdown"
  (`serve.py:1758`), with percentage rollups at `serve.py:1569`/`:1792`.
  Control arm: bogus token `ZZQQNOTATOKEN` → 0 hits, `INFERRED` → 85,
  `EXTRACTED` → 188. The probe discriminates.
- **CBM**: carries a **numeric confidence plus a named resolution strategy** in the
  edge `properties` JSON — e.g. `pass_calls.c:355` writes
  `{"callee":…,"confidence":%.2f,"strategy":"%s","candidates":%d}`, and
  `pass_configlink.c:182` writes `{"strategy":"key_symbol","confidence":…}`.
  So CBM records *how* an edge was resolved and *how sure*, per edge.

The real difference is **shape, not presence**:

| | graphify | CBM |
|---|---|---|
| vocabulary | closed, validated (3 values) | open — free-form `strategy` string + float |
| storage | first-class edge attribute | JSON blob in `properties` |
| audit surface | yes — `graphify://audit` MCP resource with % rollup | none found (**UNVERIFIED**: I did not exhaustively search CBM's MCP resources for an equivalent) |
| granularity | every edge, uniform | per-pass; `CALLS`/config-link passes set it, and I did **not** verify every pass does |

graphify's is *auditable in aggregate*; CBM's is *more informative per edge* (a
strategy name beats a 3-value enum for debugging one bad edge) but cannot be rolled
up or validated, because nothing constrains the strategy vocabulary.

## 6. Determinism and LLM requirement

- **CBM: no LLM anywhere.** README states it outright ("it does **not** include an
  LLM"), and the design corroborates it — the embedding table is frozen at build
  time, community detection is Louvain, scoring is TF-IDF/BM25/MinHash. The MCP
  client is the only intelligence layer. **No API key at index or query time.**
- **graphify: free for code, LLM for the rest.** AST extraction (`update`) and
  `query`/`path`/`explain`/`affected` are deterministic and LLM-free. But
  **community labelling** takes `--backend`/`--model` and calls an LLM
  (`graphify label`), and **prose/document extraction** is an LLM path entirely
  (`llm.py`) — in this repo that is a Claude host-agent fan-out.

This is the cleanest single-sentence gap: **CBM is LLM-free end to end; graphify is
LLM-free for code but needs an LLM for prose ingestion and for human-readable
community names.** This repo already lives with that (deterministic hub labels via
`kb-label` instead of LLM-named communities).

---

## Verdict: both directions

### What CBM does that graphify (0.9.31) cannot

1. **Cypher-like query *input* surface** (`query_graph`) — precise pattern selection
   graphify's BFS/DFS `query` cannot express. graphify only *emits* Cypher toward a
   graph DB.
1b. **TOON dense output encoding** (`compact_out.h`) — 40–60% fewer tokens on
   homogeneous result sets. graphify caps output instead of compressing it.
2. **Diff-driven impact** (`detect_changes`) — maps uncommitted git changes to
   symbols with risk classification. graphify's `affected` needs a symbol name.
3. **Deterministic offline semantic search** via a compiled-in int8 token-vector
   table — vocabulary-mismatch recall with no vector store, no API key, no daemon.
   graphify has no vector path at all.
4. **Committable graph artifact** — `.codebase-memory/graph.db.zst`, 8–13:1
   compressed, with `merge=ours` conflict avoidance. This repo's graph is 382 MB
   and gitignored by invariant.
5. **Automatic cross-client freshness** — one coordination daemon shared across
   Claude Code / Codex / OpenCode, with a background watcher.
6. **Cross-service linking** — HTTP route↔call-site, gRPC/GraphQL/tRPC,
   `EMITS`/`LISTENS_ON` channel edges. graphify has no service-topology layer.
7. **IaC as graph nodes** — Dockerfile/K8s/Kustomize with `IMPORTS` edges.
8. **Zero-dependency single static binary**, 158 languages, no Python runtime.

### What graphify does that CBM cannot

1. **Ingest non-code inputs, and extract prose *semantics*.** Documents, papers,
   URLs (`graphify add <url>`), images, video/transcripts.
   **Refined after arming** — the naive claim "CBM cannot represent prose" is too
   strong. CBM *does* parse markdown structurally: `lang_specs.c:834–836` maps
   `document` → module and `atx_heading`/`setext_heading` → class-like nodes, with
   `extract_markdown_heading_name()` at `extract_defs.c:3630`. So CBM gives you a
   free, deterministic **heading outline** of a markdown file.
   What it has no path to is prose *semantics* — concepts, claims, and the
   relations between them, which is what graphify's `llm.py` extraction produces.
   And the non-markdown formats are not merely unsupported but **actively
   excluded**: `.pdf`, `.doc(x)`, `.xls(x)`, `.ogg`, `.mkv`, `.webm` sit in
   `src/discover/discover.c:73`'s skip list. Armed: `youtube`/`whisper`/`fetch_url`
   → 0 files each, `pdf` → 1 (that exclusion list), `transcribe` → 2 (both Rust
   *macro transcribers*, unrelated); control `Dockerfile` → 8 files.
   **For this repo this is decisive**: the prose graph is 2,553 indexed nodes of
   research material of which CBM could recover only the heading skeleton.
2. **Auditable edge provenance over a closed vocabulary** — `graphify://audit`
   gives an EXTRACTED/INFERRED/AMBIGUOUS breakdown with percentages. CBM's
   per-edge strategy strings cannot be rolled up or validated.
3. **Token-budgeted query output** (`--budget N`) that *reports its own
   truncation* — retrieval sized for an LLM context window.
4. **Cross-repo merge into one graph** — `merge-graphs`, plus a git **merge driver**
   for `graph.json`. CBM has `CROSS_*` edges within one store, which is a different
   mechanism (**UNVERIFIED** whether it can union two independently-built stores).
5. **Graph-DB scale-out** — native Neo4j/FalkorDB push. CBM is SQLite-only.
6. **Multi-platform agent-skill install** across 19 platforms with a `--project`
   scope, and derived views (wiki, GraphML, SVG, Obsidian).
7. **Hyperedges** (`llm.py:478` schema) — n-ary relations. CBM's edge table is
   strictly binary `(source_id, target_id, type)`.

### Adoption read for this repo

CBM is **not a replacement** — it cannot hold the prose corpus that is this repo's
reason to exist. It is a plausible **complement** for the code half: its
`detect_changes`, Cypher surface, and automatic watcher freshness cover real gaps.
The blockers are that it is a second store with a second provenance model, and that
this repo's invariants route every graph operation through a `kb-*` mise task.

---

## Claims I refuted during this work

**I refuted 5 of my own claims**, plus one broken probe.

1. *"The README advertises a `semantic_query` MCP tool that isn't in the dispatch
   table."* — False; it is a **parameter** of `search_graph`
   (`src/mcp/mcp.c:420`, `run_semantic_query_core` at `:3067`).
2. *"CBM has no edge provenance."* — False; it stores per-edge `confidence` +
   `strategy` in `properties` JSON (`pass_calls.c:355`,
   `pass_configlink.c:182`). The real gap is vocabulary validation and aggregate
   audit, not presence.
3. *"graphify has no Cypher."* — False as stated; 29 hits, control `neo4j` → 24.
   Corrected to: graphify **emits** Cypher (Neo4j/FalkorDB export) but has no
   Cypher **input** surface.
4. *"CBM cannot represent prose / markdown."* — Too strong. It extracts a markdown
   **heading outline** deterministically (`lang_specs.c:834`,
   `extract_defs.c:3630`). What it lacks is prose *semantics*.
5. *"`compact_out.c` is probably CBM's answer to `--budget`."* — False; it is
   **TOON** dense output encoding, a different mechanism. CBM has result-count
   `limit` but **no token budget** (armed 0 vs control 7).

**Broken probe (not a claim):** `grep -rn "semantic_query" --include=*.c` returned
0 for *both* the test and its control, because zsh rejected the unquoted glob.
A uniform negative is a broken probe, not a finding. Re-run quoted: 16 vs 77.
A second probe (`add_parser` → 0) was uninformative rather than wrong —
`cli.py` hand-rolls dispatch instead of using argparse; `graphify --help` is the
correct arm.

## Explicitly UNVERIFIED

- Whether CBM exposes any aggregate edge-confidence audit surface equivalent to
  `graphify://audit`.
- Whether *every* CBM extraction pass sets `confidence`/`strategy`, or only the
  `CALLS` and config-link passes I read. Two passes confirmed; the rest not
  checked.
- Whether CBM's `CROSS_*` edges can union two independently-built stores the way
  `graphify merge-graphs` unions two `graph.json` files.
- Whether graphify's `scip_ingest.py` LSP path covers the same ~12 languages as
  CBM's Hybrid LSP. I confirmed the path exists but did not compare coverage.
- **All CBM performance figures** (Linux kernel in 3 min, <1 ms Cypher, 120× fewer
  tokens, and the arXiv 83% / 10× / 2.1× numbers) are **the vendor's own,
  unreproduced here**. I did not build or run the binary, and no benchmark in this
  report was re-derived. An inherited number is not a measurement.
- The "158 languages" count is taken from the repo's own `THIRD_PARTY.md` (which
  says 159 grammars) and its README badge (158). I did not reconcile the
  off-by-one or verify per-language extraction quality — a vendored grammar proves
  a file *parses*, not that CBM's extractors emit useful nodes for it.

## GitHub repos touched

- [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) — the tool under analysis; read its README, `THIRD_PARTY.md`, `src/mcp/mcp.c`, `src/store/store.c`, `src/pipeline/pass_calls.c`, `src/pipeline/pass_configlink.c`, `internal/cbm/lsp/*`, `vendored/nomic/*`, `scripts/extract_nomic_vectors.py`.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the comparison baseline; read the **installed 0.9.31** `validate.py`, `export.py`, `serve.py`, `llm.py`, `build.py`, `symbol_resolution.py`, `callflow_html.py`, and `graphify --help`.
- [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter) — vendored runtime + grammars in CBM; read only to establish that it is third-party and not CBM's own logic.
- [nomic-ai/nomic-embed-code](https://huggingface.co/nomic-ai/nomic-embed-code) (HuggingFace, not GitHub) — the source model for CBM's compiled-in static vector table.
