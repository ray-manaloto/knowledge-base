# kb-tool-researcher — GitNexus (lens: retrieval)

Pinned source: `sources/GitNexus/` @ `911151e2304f298a995fcc69c738ad2c6db9393a`
(manifest `sources/GitNexus.manifest`, `ref = main`, `scope = study`).
Study graph: `graphify-out/study-graph.json` — 68,670 nodes / 208,570 links total,
of which **23,485** carry a `source_file` under a GitNexus top-level directory
(briefing said 24,671; the remainder are `.claude/**` and root files also owned by
GitNexus — e.g. `.claude/skills/gitnexus-plan/…`).

⚠️ **`repo` does NOT discriminate**: every study node reports one of only two
values — `knowledge-base` (65,825) and `mindwalk` (2,845). GitNexus is attributed
to *neither* as a distinct value, so counting by `repo` returns 0 for a source
that is fully present. Filter on `source_file`. (Control arm: filtering by
`source_file` prefix returns 23,485; filtering `repo == "GitNexus"` returns 0.)

## STATUS: complete

## Correction to the dispatch briefing (before any gap claim)

The briefing describes GitNexus as *"TypeScript, client-side in-browser knowledge
graph + Graph RAG agent, **zero-server**"*. The **installed source at the pinned
SHA contradicts the zero-server framing**: the repo ships `Dockerfile.cli`,
`Dockerfile.web`, `docker-compose.yaml`, `docker-server.mjs`, a `deploy/` tree, an
npm CLI (`gitnexus`), an MCP server (`.mcp.json`, `server.json`, `glama.json`), and
links a hosted SaaS (`akonlabs.com`). Its README self-describes as *"The nervous
system for agent context… exposes it through smart MCP tools so AI agents never
miss code."* The in-browser web UI is one of several front-ends, not the whole
product. Gap claims below are written against the source, not the briefing.

License: PolyForm Noncommercial 1.0.0 (confirmed, `LICENSE` line 1).
Size: 4,692 tracked files; 2,057 `.ts` + 73 `.tsx`, but also 297 `.py`, 232 `.java`,
209 `.rs`, 185 `.cs`, 153 `.php`, 146 `.kt`, 133 `.cpp`, 108 `.go`, 97 `.rb`,
63 `.swift`, 38 `.dart` — those are largely **grammar/fixture** files, checked below.

---

## What GitNexus is, at the pinned SHA (retrieval lens)

Read from `sources/GitNexus/README.md`, `gitnexus/src/core/search/*`, `gitnexus/src/core/embeddings/*`,
and confirmed structurally via `graphify explain "bm25-index" --graph graphify-out/study-graph.json`
(31 edges; control arm `graphify explain "zqxjvwmp-nonexistent"` → *"No node matching … found"*, so
the graph probe discriminates).

- **Two front-ends, one core.** CLI + MCP server (LadybugDB native, tree-sitter native bindings,
  persistent) and a browser Web UI (LadybugDB **WASM**, tree-sitter WASM, in-memory per session,
  ~5k-file ceiling). `gitnexus serve` bridges them.
- **17 MCP tools** (15 per-repo + 2 group): `query`, `context`, `impact`, `trace`, `detect_changes`,
  `check`, `rename`, `cypher`, `route_map`, `tool_map`, `shape_check`, `api_impact`, `explain`,
  `pdg_query`, `list_repos`, `group_list`, `group_sync`. Plus 10 MCP **resources** and 2 MCP **prompts**.
- **Hybrid retrieval**: BM25 (LadybugDB FTS) + semantic (ONNX local embeddings) fused with
  **Reciprocal Rank Fusion, `RRF_K = 60`** — `gitnexus/src/core/search/hybrid-search.ts:18`.
  Degrades to semantic-only when FTS is unavailable (`hybrid-search.ts:176-181`), and
  `mergeWithRRF` null-guards both arms (`:56-57`).
- **CJK tokenisation** for FTS (`gitnexus/src/core/search/cjk-segmentation.ts`, 200 lines).
- **PDG / taint analysis** (`analyze --pdg`) surfaced as `explain` (source→sink findings) and
  `pdg_query` (statement-level control/data dependence).
- Precomputed-at-index-time structure: Leiden clusters, "processes" (execution flows),
  confidence scoring — the README's "Precomputed Relational Intelligence" claim.
- Incremental/staleness: `core/incremental/`, `core/git-staleness.ts`, `core/index-freshness.ts`;
  per-branch indexes (`analyze --branch`) plus a workspace index that follows the working tree.
- Editor integrations with **hooks**: Claude Code, Cursor, Antigravity, Codex (PreToolUse graph
  enrichment + PostToolUse stale-index detection), plus MCP-only Windsurf/OpenCode/CodeBuddy/Qoder.
- Generates repo-specific agent skills from Leiden communities (`analyze --skills`).

## Armed probes against graphify 0.9.31 (the PINNED binary)

Binary resolved via `kb_setup.graphify_env.graphify_exe(Path("."))` →
`/Users/rmanaloto/.local/share/mise/installs/pipx-graphifyy/0.9.31/bin/graphify`, `graphify 0.9.31`.
Package source: `…/graphifyy/lib/python3.14/site-packages/graphify/` (80 `.py` files).

Same `grep -rniE … --include='*.py' -l` shape over that tree:

| pattern | files | verdict |
|---|---|---|
| `louvain\|leiden` | **5** (`build.py`, `hooks.py`, `callflow_html.py`, `cluster.py`, `analyze.py`) | **CONTROL ARM — probe discriminates** |
| `cypher` | 3 (`export.py`, `cli.py`, `exporters/graphdb.py`) | present (as an *export* target) |
| `tree.sitter` | many (`extract.py`, `extractors/*`) | present |
| `bm25` | **0** | absent |
| `reciprocal.rank\|rrf` | **0** | absent |
| `faiss\|chroma\|qdrant\|vector_store\|vectorstore` | **0** | absent |
| `embedding` | 5 hits, **all false positives** — the English word in docstrings about escaping strings for YAML/JSON/Cypher (`ingest.py:14`, `security.py:397`, `export.py:117,340`) and Go *interface embedding* (`extractors/go.py:268`) | no vector embeddings |
| `\bidf\b` | `serve.py` (7 hits incl. `_compute_idf`, `G.graph['_idf_cache']`) | **PRESENT — graphify DOES have IDF term weighting, natively, in its MCP server** |

The `idf` row is the one that would have been a false negative: this repo's `--idf` flag is
`kb_setup`'s, but graphify **also** ships IDF weighting inside `serve.py`. Reporting "graphify has no
lexical scoring" would have been wrong.

## Claims I REFUTED against myself (all were about to be reported)

Each came from a `git grep -rilE` over `gitnexus/src`, `gitnexus-web/src`, `gitnexus-shared`
with the control arm `tree-sitter|tree_sitter` → **263 files** in the same command shape.

| tentative claim | raw hits | why it was WRONG |
|---|---|---|
| "GitNexus ingests SCIP/LSP indexes" | `scip` → 28 files | every hit is **"di*scip*line"** in a doc comment (`reaching-defs.ts:36` "COMPLEXITY DISCIPLINE"; `javascript/query.ts:118` "Anchor discipline"). No SCIP anywhere. |
| "GitNexus handles PDFs" | `pdf` → 3 files | `control-dependence.ts` uses **`PDF` = post-dominance frontier**; the only literal `.pdf` is in the **ignore** list (`ignore-service.ts:158`) — proof of the opposite. |
| "GitNexus does audio transcription" | `whisper\|transcri` → 4 files | all `preserveAssistantTranscript` — LLM **conversation** transcript replay for DeepSeek, not audio. |
| "GitNexus does OCR" | `ocr` → 8 files | case-insensitive substring of `rowToCrossing`, `parseJsDocReturn`, `extractPhpDocReturnType`. |
| "graphify has SCIP/LSP ingestion" (inherited from a prior session's note) | `scip_ingest.py` exists | **the module is UNWIRED**: grepping `scip_ingest\|ingest_scip` across the whole 0.9.31 package returns only the 3 lines *inside `scip_ingest.py` itself*, and its own docstring says *"Not wired to the CLI in this phase."* Control arm: `transcribe` → 3 hits **including callers** (`ingest.py`, `callflow_html.py`). So "graphify has SCIP" is true of the tarball and false of the product. |

**5 claims refuted.**

## Armed absence probes — graphify 0.9.31 vs GitNexus

One `grep -rniE … --include='*.py' -l` invocation over the graphify package, so control and test
rows share the command shape:

| pattern | graphify hits | note |
|---|---|---|
| `obsidian` | 6 (`export.py`, `wiki.py`, `cli.py`, `report.py`, `callflow_html.py`, `exporters/base.py`) | CONTROL — present |
| `graphml` | 3 | CONTROL — present |
| `neo4j\|falkordb` | 3 (`exporters/graphdb.py`) | CONTROL — present |
| `reflect` / `save_result` | 6 / 3 | CONTROL — present |
| `taint` | **0** | absent |
| `\bpdg\b\|program dependence` | **0** | absent |
| `control.dependence\|post.domin` | **0** | absent |
| `reaching.def` | **0** | absent |
| `data.?flow` | 1 — a **path string in a comment** (`build.py:434`, `d_projects_myrepo_docs_dataflow`) | absent as a feature |

Against GitNexus, which ships `gitnexus/src/core/ingestion/taint/` (**19 modules**, incl.
`interproc-solver.ts`, `call-summary-harvest.ts`, per-language `java-model.ts` /
`python-model.ts` / `typescript-model.ts`, `source-sink-registry.ts`) and
`gitnexus/src/core/ingestion/cfg/` (**12 modules** + `visitors/`, incl. `post-dominators.ts`,
`control-dependence.ts`, `reaching-defs.ts`).

Reverse direction, same shape over GitNexus source (control `tree-sitter` → 263):
`graphml` → **0**, `obsidian` → **0**, `neo4j|falkordb` → **0**, `youtube|yt-dlp` → **0**.
graphify's `ingest.py:73-80` dispatches URL types **`youtube` / `pdf` / `image`**, and
`transcribe.py` wraps `faster-whisper` over
`{.mp4,.mov,.webm,.mkv,.avi,.m4v,.mp3,.wav,.m4a,.ogg}` — every one of which sits in GitNexus's
**ignore** list (`gitnexus/src/config/ignore-service.ts`, "Documents" and "Media" blocks).

## Retrieval mechanics, side by side (the lens)

| axis | GitNexus @ 911151e | graphify 0.9.31 (pinned) |
|---|---|---|
| lexical scoring | **BM25 over LadybugDB FTS**, 21 indexed tables (`File`,`Function`,`Class`,`Method`,`Interface`,`Constructor`,`Struct`,`Enum`,`Trait`,`Impl`,`Macro`,`Namespace`,`TypeAlias`,`Typedef`,`Const`,`Property`,`Record`,`Union`,`Static`,`Variable`), each on `name` + `content` + `description` (`fts-schema.ts:19-46`); stemmer (`DEFAULT_FTS_STEMMER`) + CJK segmentation | **IDF only, and only over node LABELS.** `serve.py:275 _compute_idf` computes df by *substring containment*: `if t in norm_label`. No document body is scored. No BM25 saturation/length norm. |
| semantic | ONNX local embeddings (`core/embeddings/`, 20 modules: chunker, AST-aware `structural-extractor`, `embedder`, `exact-search`, on-demand runtime install into `~/.gitnexus/embedding-runtime`) | **none** — `faiss\|chroma\|qdrant\|vector_store` → 0 files; all 5 `embedding` grep hits are the English word in escaping docstrings / Go interface embedding |
| fusion | **RRF, `RRF_K = 60`** (`hybrid-search.ts:18`), graceful degradation to semantic-only when FTS is unavailable (`:176-181`) | none |
| graph traversal | Cypher (raw `cypher` MCP tool) over LadybugDB; `trace` = shortest directed path; `impact` = depth-grouped blast radius | BFS/DFS with `--budget N` token cap; `path`, `affected --depth N`, `god-nodes`. Cypher only as an **export dialect** (`exporters/graphdb.py` → Neo4j/FalkorDB), not a query surface. |
| dataflow | interprocedural **taint** (19 modules) + **CFG/PDG** (12 modules: post-dominators, control-dependence, reaching-defs) exposed as `explain` / `pdg_query` | absent (`taint`→0, `pdg`→0, `control.dependence\|post.domin`→0, `reaching.def`→0; control rows `obsidian`→6, `graphml`→3, `neo4j\|falkordb`→3 in the same command) |
| cross-repo | **semantic**: Contract Registry from real protocol extractors — `grpc-extractor`, `http-route-extractor`, `thrift-extractor`, `topic-extractor`, 7 workspace extractors (`core/group/extractors/`, 19 files) → `group_sync`, `cross-impact`, `cross-trace` | **set union**: `merge-graphs`, `global add/remove/list`. graphify's only `grpc\|protobuf\|openapi` hits (`extract.py:1062,1066,1143`) are about **skipping generated files**; every `route\|endpoint` hit in `build.py` is a *graph edge endpoint*. |
| edge provenance | numeric per-resolution-pass confidence (`graph-bridge/edges.ts:133,220` `0.85`; `imports-to-edges.ts:49` `1.0`; `callable-value-flow.ts:733` `0.8`/`0.7`; `references-to-edges.ts:113` propagates `ref.confidence`) | binary tier `EXTRACTED`/`INFERRED` + a 3-valued `confidence_score`. Measured on `study-graph.json`: `1.0`→177,708, `0.8`→29,285, `0.5`→1,577; `EXTRACTED`→177,707 / `INFERRED`→30,863. |
| MCP surface | **17 tools + 10 resources + 2 prompts**; editor **hooks** (PreToolUse graph enrichment, PostToolUse stale-index detection) for Claude Code / Cursor / Antigravity / Codex | **10 tools** (`serve.py:1297-1405`): `query_graph`, `get_node`, `get_neighbors`, `get_community`, `god_nodes`, `graph_stats`, `shortest_path`, `list_prs`, `get_pr_impact`, `triage_prs`. No MCP resources/prompts found. |

## Where graphify is ahead

- **Non-code corpora.** `ingest.py:73-80` dispatches `youtube` / `pdf` / `image` URL types;
  `transcribe.py` wraps `faster-whisper` over 10 A/V extensions; `--google-workspace` exports
  `.gdoc/.gsheet/.gslides`; `--postgres DSN` extracts a **live database schema**; `--cargo` reads
  crate deps; `manifest_ingest.py` / `mcp_ingest.py` exist. Every document and media extension
  graphify ingests is on GitNexus's **ignore** list. GitNexus is a *code*-graph tool by construction.
- **LLM-inferred semantic edges.** graphify's `extract --mode deep` produces `INFERRED` edges
  (30,863 of them in this repo's study graph, relations incl. `rationale_for`) across prose and code.
  GitNexus's LLM touchpoint is only `core/ingestion/cluster-enricher.ts` (cluster *names*,
  keywords, descriptions) — its edges are all deterministic. (I nearly claimed GitNexus's indexer
  never calls an LLM at all, on the strength of its own `CLAUDE.md`; the enricher refutes that.)
- **Work-memory + reflection.** `save-result` (`--outcome useful|dead_end|corrected`) and
  `reflect` (half-life-weighted, `--min-corroboration N`) produce a deterministic lessons doc.
  No equivalent in GitNexus (its `.beads/` is issue tracking, not query-outcome memory).
- **Export breadth.** GraphML, Obsidian vault, wiki, D3 collapsible `tree`, `callflow-html`,
  Neo4j/FalkorDB push. GitNexus: `graphml`→0, `obsidian`→0, `neo4j|falkordb`→0.
- **Agent-platform breadth.** ~20 `<platform> install` targets in `graphify --help` vs GitNexus's
  8-editor table.
- **PR-graph tooling.** `prs.py` + MCP `list_prs`/`get_pr_impact`/`triage_prs`, incl.
  `--conflicts` (PRs sharing graph communities → merge-order risk). GitNexus's PR story is the
  `/gitnexus-review` skill over a local diff, not a graph-aware queue.

## Where GitNexus is ahead (retrieval lens)

- Hybrid BM25+semantic+RRF vs label-substring IDF (above).
- FTS over `content` **and** doc-comment `description` (Javadoc/KDoc/JSDoc/Doxygen/godoc/RDoc),
  so a natural-language question can hit a symbol whose *name* shares no token with the query.
  graphify's IDF only ever sees `norm_label`.
- CJK query segmentation (`cjk-segmentation.ts`).
- Taint / PDG retrieval (`explain`, `pdg_query`) — a security-shaped retrieval axis graphify has none of.
- Per-branch indexes + workspace index following the checked-out tree; git-staleness detection
  wired into PostToolUse hooks so the agent is *told* the index went stale.
- Cross-service contract retrieval (`route_map`, `tool_map`, `shape_check`, `api_impact`).
- Response-size discipline: `query`/`context`/`impact` take `maxTokens` bounding the **complete
  formatted response** including hints and error text (README:352). graphify's `--budget` caps
  the traversal output only.
- Browser-only deployment: LadybugDB WASM + tree-sitter WASM, no install, no server
  (~5k-file ceiling). graphify has no WASM/browser target.

## UNVERIFIED / not armed

- **Retrieval *quality*.** No side-by-side recall measurement was run. This repo's own eval
  (`kb_setup.eval_cases`) reports `prose+idf` at 5/8 natural pairs, but that number is on **this
  corpus with this repo's own BM25 scorer** (`kb_setup/lexical.py`), not graphify's `_compute_idf`,
  and there is no GitNexus arm at all. Any "X retrieves better" statement is unverified.
- **GitNexus's ~5k-file browser ceiling** and "unlimited via backend mode" are README claims;
  not measured here.
- **GitNexus's 17 MCP tools** were read from the README table, not from the tool-registration
  source. graphify's 10 were read from `serve.py:1297-1405`, so the two counts are not
  symmetrically sourced.
- **PolyForm Noncommercial 1.0.0** (`LICENSE:1`) makes GitNexus non-adoptable for commercial use;
  I did not check graphify's licence for comparison.

## GitHub repos touched

- [abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus) — the peer tool under
  study; read `README.md`, `LICENSE`, `CLAUDE.md`, `gitnexus/src/core/search/*`,
  `core/embeddings/*`, `core/ingestion/{taint,cfg,group,languages}/*`, `config/ignore-service.ts`.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the baseline; read the
  **installed 0.9.31** package (`cli.py`, `serve.py`, `ingest.py`, `transcribe.py`, `scip_ingest.py`,
  `extract.py`, `build.py`, `prs.py`, `exporters/graphdb.py`) plus `graphify --help`.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — `mise.toml`,
  `python/src/kb_setup/{graphify_ops,lexical,eval_cases,graphify_env}.py`, `graphify-out/*.json`.

**Claims refuted during this work: 7.**
(GitNexus-SCIP, GitNexus-PDF, GitNexus-transcription, GitNexus-OCR, graphify-SCIP-is-wired,
graphify-lacks-numeric-confidence, GitNexus-indexer-never-calls-an-LLM — plus a near-miss on
graphify-handles-protobuf/gRPC, which was generated-file *exclusion* logic.)
