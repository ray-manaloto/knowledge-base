# codegraph vs graphify — peer-tool gap analysis (lens: retrieval)

Source: `sources/codegraph` @ `49c11fc2e0c02170742be8411e66a31af611f4b7`
(github.com/colbymchenry/codegraph), scope=corpus, MIT.
graphify pin: read from `graphify_exe` (see below), NOT a bare PATH binary.

STATUS: in progress — written incrementally.

## Orientation notes

- Manifest describes codegraph as a "C" implementation. **First correction:**
  the tree is TypeScript (`src/**`) + a **Rust** native kernel
  (`codegraph-kernel/Cargo.toml`), with tree-sitter grammars in C.
  Verifying below.

## CORRECTION 1 (refuted, my own briefing) — codegraph is not "a C implementation"

Briefing said "C, pre-indexed local code knowledge graph". Verified against the
pinned tree:
- `sources/codegraph/src/**` is **TypeScript** (CLI, MCP server, sync, search, db).
- `sources/codegraph/codegraph-kernel/Cargo.toml` — the extraction kernel is
  **Rust** (README: "Kernel powered by Rust", "native Rust kernel ... 20 languages").
- C appears only as vendored tree-sitter grammar C sources.
So the "independent C implementation" framing in the manifest comment is wrong;
it is a TypeScript/Node tool with a Rust native kernel, distributed on npm with a
bundled Node runtime. **REFUTED: 1.**

## codegraph capability inventory (from pinned README + source, to be verified)

- Storage: **SQLite** (`.codegraph/codegraph.db`) + **FTS5** full-text search.
- MCP surface: deliberately **ONE listed tool** `codegraph_explore`; 7 others
  (`node`/`search`/`callers`/`callees`/`impact`/`files`/`status`) exist but are
  unlisted, re-enabled via `CODEGRAPH_MCP_TOOLS`.
- Auto-sync: native FSEvents/inotify/ReadDirectoryChangesW watcher, 2000ms debounce
  (`CODEGRAPH_WATCH_DEBOUNCE_MS`, clamped 100ms–60s), plus a **per-file staleness
  banner** in MCP responses and **connect-time (size,mtime)+content-hash catch-up**.
- `codegraph affected [files...] --stdin` — transitive import trace to **test files**.
- Framework route extraction for 17 web frameworks → `route` nodes.
- Cross-language bridging: Swift↔ObjC, RN legacy bridge/TurboModules/Fabric/Paper,
  Expo Modules, RN native→JS events; edges tagged `provenance:'heuristic'` with
  `metadata.synthesizedBy`.
- Multi-agent installer (Claude Code, Cursor, Codex, opencode, Hermes, Gemini,
  Antigravity, Kiro) + `uninstall`.
- Anonymous telemetry (opt-out), npm trusted publishing + SLSA attestations.
- Zero LLM: "No API keys. No external services." — same determinism claim as graphify.

## Probe environment (armed)

- graphify read from the **pin**, not PATH: `kb_setup.graphify_env.graphify_exe(.)`
  → `/Users/rmanaloto/.local/share/mise/installs/pipx-graphifyy/0.9.31/bin/graphify`,
  `graphify --version` → `graphify 0.9.31`. Package source read at
  `…/graphifyy/lib/python3.14/site-packages/graphify/` (80 .py files).
- codegraph read from `sources/codegraph` at the manifest SHA.
- Aggregate-graph control arm: `graphify explain "codegraph"` → "Ambiguous: matches
  2 nodes" (`package.json`, `src/index.ts`), so codegraph IS in
  `graphify-out/graph.json` and the probe discriminates. (Per the manifest it is
  `scope = corpus`, so it is NOT in `study-graph.json` — my briefing's pointer to
  the study graph was wrong for this source.)

## Findings — what codegraph does that graphify cannot

### C1. SQLite + FTS5 store vs a whole-graph JSON loaded into RAM (ARMED)
codegraph persists to `.codegraph/codegraph.db` (SQLite, WAL, FTS5 full-text index);
queries hit indexed tables. graphify's store is `graph.json` deserialized into a
networkx graph in memory.
Control arm: `grep -rl "sqlite\|FTS5\|fts5" <graphify pkg> --include='*.py'` → **0**;
same command shape for `networkx` → **19**, for `json` → **44**. So the probe
discriminates and the 0 is real. Consequence here: this repo's aggregate
`graph.json` is **393 MB** and every query pays a full parse.

### C2. Agent-facing staleness signalling (ARMED)
codegraph's MCP responses prepend a `⚠️` per-file staleness banner for files edited
inside the debounce window, footer-list other pending files, and run a
connect-time `(size,mtime)`+content-hash reconciliation before answering the first
query. graphify's `serve.py` caches on `Path(graph.json).stat()` →
`(st_mtime_ns, st_size)` (serve.py:141) — that detects a **changed graph file**,
not source-file drift, and nothing is reported to the agent.
Control arm: `grep -i "stale|fresh|mtime|outdated"` in serve.py → 7 hits, all
either PR-status ("STALE" base branch), the LRU docstring, or the graph-file stat;
control `grep -ci tool serve.py` → 63, so the file is being read.

### C3. `affected` maps changed FILES → affected TEST files (ARMED)
`codegraph affected src/a.ts --stdin --depth 5 --filter 'e2e/*' --quiet` traces
import deps transitively and returns test files, designed for a CI/pre-commit hook.
graphify's `affected` is a different verb: `graphify affected "X"` — reverse
traversal from a **node label**, `--relation`/`--depth`, no file input, no stdin,
no test-file notion. Control arm: `grep -i "test|spec" affected.py` → **1 hit**, a
comment; control `grep -c "def "` → 9, so the file was read.

### C4. Framework route extraction across 17 web frameworks — PARTIAL, NOT absent
codegraph emits `route` nodes for Django/Flask/FastAPI/Express/NestJS/Laravel/
Drupal/Rails/Spring/Play/Gin/chi/gorilla/Axum/actix/Rocket/ASP.NET/Vapor/React
Router/SvelteKit/Vue-Nuxt/Astro, with measured per-framework coverage.
**graphify is NOT routeless** — `extractors/dart.py` synthesizes `route` nodes for
GoRouter/AutoRoute/Navigator and `extractors/razor.py` for Razor `@page`. So the
honest claim is *breadth*, not existence: 2 route-emitting extractors vs ~22
framework shapes. (I nearly wrote "graphify has no route nodes" — refuted by grep.
**REFUTED: 2.**)

### C5. Native OS file events vs a POLLING observer on macOS (ARMED, and narrower than it looks)
Both tools watch. codegraph uses FSEvents/inotify/ReadDirectoryChangesW with a
2000ms debounce (`CODEGRAPH_WATCH_DEBOUNCE_MS`, clamped 100ms–60s).
graphify HAS `watch.py` (1,629 lines) with `--debounce` (default **3.0s**) on
`watchdog` — but `watch.py:1592`:
`observer = PollingObserver() if sys.platform == "darwin" else Observer()`
i.e. **on macOS graphify polls**, with an explicit comment "FSEvents can miss rapid
saves in some editors". So: not "graphify has no watcher" (that would be false);
the gap is native-events-on-macOS and a shorter floor.

### C6. Multi-agent installer — REFUTED as a codegraph advantage
codegraph auto-configures **8** agents (Claude Code, Cursor, Codex, opencode,
Hermes, Gemini, Antigravity, Kiro). `graphify --help` lists install/uninstall for
**19** platforms (claude, windows, codebuddy, codex, opencode, aider, amp, agents,
claw, droid, trae, trae-cn, gemini, cursor, antigravity, hermes, kiro, pi, devin)
plus vscode/copilot. graphify is the broader one. **REFUTED: 3.**

### C7. Single-tool MCP surface as a deliberate context-budget decision
codegraph lists exactly **one** MCP tool (`codegraph_explore`); the other seven
stay functional but unlisted, re-enabled via `CODEGRAPH_MCP_TOOLS`. Stated reason:
"one strong tool steers agents better than a menu of narrower ones — fewer
mis-picks, and it saves context every session". graphify's `serve.py` registers
**10** tools unconditionally (`query_graph`, `get_node`, `get_neighbors`,
`get_community`, `god_nodes`, `graph_stats`, `shortest_path`, `list_prs`,
`get_pr_impact`, `triage_prs` — serve.py:1296-1440) with no env-var gate.
This is a *design* difference, not a missing capability; a graphify consumer that
wants a one-tool surface has no switch. NOT-COMPARABLE on capability, real on cost.

### C8. Per-project zero-config exclusion + `codegraph.json` include/exclude/extensions
codegraph honours `.gitignore` (including in non-git projects, root and nested),
skips ~all dependency/build dirs by default even with no `.gitignore`, skips >1 MB
files, and takes `codegraph.json` `{exclude, include, extensions}` to force
committed vendored trees out or SVN/Perforce source back in, plus custom-extension
→ language mapping. graphify has `--no-gitignore` / `.graphifyignore` but I did not
find a per-extension→language override. **UNVERIFIED** — I did not run the
extension-override probe on graphify's source, so treat C8's second half as
unarmed.

## Findings — what graphify does that codegraph cannot

### G1. Non-code corpora: prose, PDFs, images, video/audio (ARMED both ways)
graphify ingests URLs, PDFs, images and video/audio: `ingest.py` branches on
`.pdf` and `.png/.jpg/.jpeg/.webp/.gif` (ingest.py:77-79, 234-240),
`transcribe.py` exists, and term counts across the installed package are
pdf→36 files, whisper→31, youtube→16, png|jpg→23, markdown→52.
codegraph is **code only**: `src/extraction/languages/` enumerates 28 code
language modules and no markdown/doc extractor; the whole tree returns
pdf→0, youtube→0, whisper→0.
Control arm on codegraph (same command shape): sqlite→59, explore→67,
tree-sitter→103, blast→12 — the greps discriminate.
This is the single largest divergence: codegraph cannot be the substrate this
repo actually is (docs, transcripts, blog posts, marketplace listings).

### G2. Community detection / clustering / god nodes (ARMED)
graphify: `cluster.py`, `graphify cluster-only`, `graphify label`, `god-nodes`,
`get_community` MCP tool; louvain→4 files, leiden→4 files in the installed package.
codegraph: louvain→0, leiden→0 (the 4 apparent "leiden" hits are all
`firstSimpleIdentifier`, a substring false positive — checked line by line), and
`god node|godNode`→0.
**But NOT "codegraph has no graph analytics"**: it runs a **PageRank**-style
expansion from matched seed nodes over the call/reference graph
(`src/mcp/tools.ts:2539`, `src/mcp/query-worker.ts:6`) and uses centrality for
de-noising (tools.ts:2816). The gap is *community structure and hub naming*, not
ranking. (I nearly claimed the broader version. **REFUTED: 4.**)

### G3. Graph-database and interchange export (ARMED)
graphify: `exporters/graphdb.py`, `--push <uri>`, neo4j→33 files, falkordb→31,
plus graphml/svg/wiki/obsidian/D3-tree/callflow-HTML views.
codegraph: neo4j→0, falkordb→0, graphml→0, cypher→0 across `src`, `__tests__`,
`docs` — with the controls above non-zero, so the 0s are real. The index is
SQLite and stays SQLite; there is no scale-out or interchange surface.

### G4. Cross-repo / aggregate graph (ARMED)
graphify: `merge-graphs`, `global add/remove/list/path`
(`~/.graphify/global-graph.json`), `--global --as <tag>`.
codegraph: `global graph`→0, `mergeGraph`→0; the two literal `cross-repo` hits are
both benchmark prose in `docs/design/*.md`, not a feature. Its multi-project story
is per-call `projectPath` switching between separate `.codegraph/` indexes — N
databases queried one at a time, never one merged graph. This repo's whole model
(26 sources merged into one `graph.json`) has no codegraph equivalent.

### G5. Semantic/LLM layer and provenance classes (ARMED)
graphify: `llm.py`, `graphify extract --mode deep` for INFERRED edges, backends
gemini/kimi/claude/openai/deepseek/ollama, `label` for LLM community naming.
codegraph is deterministic-only and says so — `src/mcp/tools.ts:2547`:
"deterministic, no embeddings". Zero LLM, zero API keys.
Both tag provenance, differently: graphify EXTRACTED/INFERRED; codegraph tags
synthesized cross-language edges `provenance:'heuristic'` with
`metadata.synthesizedBy` naming the channel (`swift-objc-bridge`,
`rn-event-channel`, `fabric-native-impl`, `expo-module-extract`).
For this repo the LLM layer is the point — the corpus is prose extraction — so
G5 is a hard blocker on substitution, not a preference.

### G6. Live-system and non-filesystem sources (ARMED)
graphify `extract --postgres DSN` (live PostgreSQL schema → tables/views/functions
+ FK edges), `--cargo` (crate→crate deps), `--google-workspace`, `mcp_ingest.py`,
`manifest_ingest.py`, `prs.py` (+ the `list_prs`/`get_pr_impact`/`triage_prs` MCP
tools). codegraph reads the working tree and nothing else.

### G7. Work-memory / reflection loop (ARMED)
graphify `save-result` + `reflect` (half-life-weighted, corroboration-gated
`LESSONS.md`) — the mechanism this repo's `kb-remember`/`kb-reflect` sit on.
codegraph has telemetry (anonymous counts, no queries/paths/symbols) but no
per-query outcome memory that feeds retrieval.

### G8. SCIP ingestion — TRUE BUT WEAKER THAN IT READS
graphify ships `scip_ingest.py`. Its own docstring: *"NOT a full SCIP protobuf
implementation — this is a skeleton… **Not wired to the CLI in this phase**."*
So graphify has an LSP/SCIP-shaped ingestion path in source that a user cannot
invoke from the CLI. codegraph has none (`\bSCIP\b`→0; the 10 case-insensitive
hits were all `script`). Recording it as a *latent* graphify advantage, not a
shipped one — asserting the strong form is the failure mode this round exists to
avoid.

## Retrieval lens — the two ranking pipelines, side by side (ARMED, re-derived)

**graphify (`graphify query`, pinned 0.9.31)** — `cli.py:852` → `serve._query_graph_text`
(serve.py:1033):
1. `_score_query(G, terms)` — IDF-weighted node scoring (`_compute_idf`, serve.py:275,
   cached in `G.graph['_idf_cache']`), producing `qs.ranked` + per-term winners.
2. `_pick_seeds(...)` — gap-based seed selection.
3. `_bfs`/`_dfs` at **depth=2** over the **undirected** graph (explicit comment:
   forcing a DiGraph "would silently drop every caller-side result").
4. `_subgraph_to_text(..., token_budget, seeds=…)` — renders **seed-first in
   traversal order** and truncates at the budget.
So: **seeds ARE IDF-scored; the returned set is NOT re-scored.** I re-derived this
rather than repeating the inherited "unscored BFS" phrasing — the strong form
("graphify's query is unscored") is FALSE. **REFUTED: 5.**

**codegraph (`codegraph_explore`)** — `src/mcp/tools.ts`:
1. FTS5/bm25 lexical match → seed nodes.
2. `computeGraphRelevance` (tools.ts:2538+) — **Random-Walk-with-Restart /
   personalized PageRank** from the seeds: undirected adjacency restricted to 9
   edge kinds (`calls, references, extends, implements, overrides, instantiates,
   returns, type_of, imports`), restart α=0.25, 25 power iterations, bounded to the
   already-relevant subgraph. Its own comment: *"the ranking signal text search
   (FTS/bm25) CANNOT provide … relevance by STRUCTURE, not words … Immune to the
   tokenization trap that fools term matching, deterministic, no embeddings."*
   Worked example in the comment: `LensSwitcher.swift` matches the word "switch"
   lexically but calls nothing in the cluster, so it accrues only restart mass and
   ranks ~0.
3. Output = verbatim source grouped by file + call paths + blast-radius summary,
   with a `; tested via callers: …` / `; no tests found within N caller hops`
   evidence tail (tools.ts ~2520).

**The gap, precisely:** graphify scores *which nodes to start from*; codegraph
additionally scores *how relevant each reached node is*, structurally.
Control arm on graphify: `pagerank`→1 file, and that one hit
(`callflow_html.py:976`) only *reads* a pre-existing `pagerank`/`centrality`
attribute for display — it computes none. `random_walk`→0, `personalized`→0,
`bm25`→0; controls `bfs`→35 files, `degree`→26, `idf`→16. The probe discriminates.

## Operational finding for THIS repo (armed, and it is close)

`graphify.security._MAX_GRAPH_FILE_BYTES = 512 * 1024 * 1024` (512 MiB), enforced
by `check_graph_file_size_cap` **before** `json.loads`, on `query`, `serve`,
`build`, `benchmark`, `tree_html`, `callflow_html`, `prs`, `global_graph`, `watch`,
`export`. Measured now: `graphify-out/graph.json` = **393,297,284 bytes = 375 MiB**,
i.e. **73% of the hard cap**. Raising it needs `GRAPHIFY_MAX_GRAPH_BYTES`; the
failure mode past it is a hard `error: … exceeds …-byte cap`, on every one of those
commands at once. codegraph's SQLite+FTS5 store has no equivalent ceiling because
nothing is ever fully rehydrated. This is the C1 architectural difference showing
up as a dated, quantified risk rather than a preference.

## CORRECTION 2 (refuted, my own briefing) — "auto-sync mirrors kb-watch" is wrong

The briefing framed codegraph's auto-sync as mirroring this repo's `kb-watch`.
`kb_setup.graph.refresh_self` (graph.py:231) says the opposite, in a comment
headed **"WHY THIS IS NOT A WATCHER"**: it is a one-shot re-extract-and-merge of
`python/` + `tests/` into the aggregate, chosen over a homegrown poll loop, because
`graphify watch <path>` rebuilds only `<path>/graphify-out/graph.json` and cannot
reach the aggregate that `affected` and `currency.toml` read.
So this repo has **no continuous auto-sync at all** — the honest comparison is
codegraph's native-event, adaptive-debounce, agent-visible-staleness loop against
a manual `mise run kb-watch`. **REFUTED: 6.**

## C2 armed on both sides (evidence)

codegraph, positive arm in source:
- `src/mcp/server-instructions.ts:62` — the exact agent-facing text, and there are
  **two** banners: the per-file one ("Some files referenced below were edited since
  the last index sync…", with the explicit contract *"Every file NOT in that banner
  is fresh, so still trust codegraph"*) and a whole-index one ("CodeGraph auto-sync
  is DISABLED…").
- `src/sync/watcher.ts:306` `private pendingFiles = new Map<…>` with
  `firstSeenMs`/`lastSeenMs`; **adaptive debounce** (watcher.ts:63) — a small
  pending set fires on a quick quiet window instead of the full debounce.
- `src/mcp/engine.ts:287-311` `catchUpSync()` — "Reconcile the index with the
  current filesystem once, right after open", gated so the first tool call waits
  (`setCatchUpGate`).
graphify, negative arm: `serve.py` has no per-source-file staleness concept
(see C2 above); its only freshness mechanism is reloading `graph.json` when that
file's own `(st_mtime_ns, st_size)` changes.

## Summary of directions

**codegraph does that graphify cannot:** SQLite+FTS5 incremental store with no
whole-graph rehydration (C1); agent-visible per-file + whole-index staleness
signalling plus connect-time reconciliation (C2); file→test-file `affected` with
stdin/glob for CI (C3); ~22 web-framework route shapes vs 2 (C4, breadth not
existence); native OS file events + adaptive debounce vs a macOS polling observer
(C5); a structural RWR/personalized-PageRank rerank of the returned set (retrieval
lens); a one-tool MCP surface as an explicit context-budget lever (C7).

**graphify does that codegraph cannot:** ingest non-code corpora — prose, URLs,
PDFs, images, video/audio (G1); community detection, clustering and god-node hubs
(G2); graph-DB and interchange export, neo4j/falkordb/graphml/wiki/D3 (G3);
cross-repo merged and global graphs (G4); an LLM semantic layer with INFERRED edges
across six backends (G5); live PostgreSQL / Cargo / Google-Workspace / PR ingestion
(G6); a work-memory + reflection loop that feeds retrieval (G7); 19 agent
platforms vs 8 (C6); a latent-but-unwired SCIP path (G8).

**Verdict for this repo:** codegraph is not a substitute — G1 alone disqualifies it,
because this corpus is mostly prose. It is a credible *complement* for the code
half, and its two cheapest transplantable ideas are (a) agent-visible staleness
signalling on `kb-serve` responses, which this repo has no analogue of and which is
exactly the failure mode `kb-currency-check` catches only out-of-band, and (b) a
structural rerank of `kb-query`'s returned set, which today is IDF at the seed
stage and traversal-order after it.

## Claims I could NOT arm (UNVERIFIED)

- codegraph's benchmark table (89% fewer tool calls, 60% cheaper, 69% fewer tokens,
  n=4 median per arm). Vendor-run, self-reported, no noise floor published, and the
  README itself flags Time as "the noisiest metric". Do not repeat these numbers as
  measurements.
- codegraph's per-language "fair coverage" percentages — same reason.
- The "2–7× faster than the fastest competing indexer" claim: the competitor is
  never named, so it is unfalsifiable as written.
- C8's second half (graphify has no per-extension→language override). Not probed.

## GitHub repos touched

- [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph) — the peer tool under analysis; README, `src/**`, `docs/design/**` read at the pinned SHA.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the incumbent; read from the INSTALLED pinned 0.9.31 package, not the tracker.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — `kb_setup.graph.refresh_self`, `graphify_ops`, `mise.toml` for the kb-watch / --idf comparison.

**Claims refuted during this work: 6.**
