# code-review-graph vs graphify — retrieval gap analysis

**Status: COMPLETE.** Written incrementally against the pinned source; every
negative claim carries its control arm inline.

- **Tool**: [tirth8205/code-review-graph](https://github.com/tirth8205/code-review-graph)
  (CRG), Python, MIT, pinned at `c3f3a6681791f6c6d870e8e437ecfe4e8500e377`
  (2026-07-31, "docs(changelog): note the Voyage embedding provider (#783)").
- **Baseline**: graphify **0.9.31**, the version pinned in `mise.toml` and
  resolved by `graphify_exe` →
  `~/.local/share/mise/installs/pipx-graphifyy/0.9.31/bin/graphify`.
  Every graphify claim below is read off that installed tree, not the issue
  tracker.
- **Lens**: retrieval. CRG is the closest structural analogue to graphify in
  the peer set — MCP server + CLI over a persistent code map.
- **Scale**: 41,753 lines of Python across 158 modules under
  `code_review_graph/`.

## Orientation receipts (probes and their control arms)

| Probe | Result | Control arm |
|---|---|---|
| `mise run kb-query -- "how does graphify retrieval and MCP server work…" --prose --idf` | 2,553 indexed prose nodes, top hits on graphify's MCP/retrieval doctrine | non-empty, so the prose graph is live |
| `graphify query … --graph graphify-out/study-graph.json` | **DENIED** by `kb_setup.hook_guard` | the team-lead's suggested command is not runnable here; the guard redirects to `mise run kb-query`. Read the study graph directly with `json` instead. |
| study graph node count | 43,999 nodes / 155,108 links | team-lead said 7,758; that is the **per-source** graph at `sources/code-review-graph/graphify-out/graph.json` (7,758 nodes / 16,743 links). Both verified. |
| CRG nodes present in the merged study graph | 2,612 nodes whose `source_file` contains `code_review_graph` | control: `code_review_graph/parser.py` alone → 604 nodes, so the corpus is really there |

### Side finding (about THIS repo, not the tool)

Every node in `graphify-out/study-graph.json` carries `repo` ∈
`{knowledge-base (41,154), mindwalk (2,845)}`. **No node is attributed to
`code-review-graph`** even though 2,612 nodes have `code_review_graph/…`
source paths. The merge in `kb_setup.graph._build_study_graph` seeds from the
first study source and merges the rest; the `repo` field does not survive that
as a per-source discriminator. Consequence: you cannot filter the study graph
by tool via `repo`. Filter on `source_file` instead. (Reported for the
team-lead; out of scope for this report's edits.)

## Provenance model — both graphs tag edges

graphify study-graph links carry `confidence: "EXTRACTED"`, `_origin: "ast"`,
`confidence_score: 1.0`, and a `source_file`/`source_location` pair. Edge
relations observed in the study graph: `calls` (77,195), `references`
(34,511), `contains` (31,012), `method`, `imports`, `rationale_for`, `uses`,
`defines`, `indirect_call`, `imports_from`, `extends`, `inherits`,
`re_exports`, `implements`, `case_of`.

**CRG uses the SAME two-tier vocabulary.** `code_review_graph/graph.py:104`
declares `confidence_tier TEXT DEFAULT 'EXTRACTED'` alongside a numeric
`confidence REAL DEFAULT 1.0`, and `edge_to_dict` (`graph.py:2230`) surfaces
both on every serialised edge.

But the tagging is far thinner than graphify's. `INFERRED` is written in
exactly **two** modules across 41,753 lines:

| file:line | what it demotes |
|---|---|
| `scoped_resolver.py:480,489` | an edge whose target was rewritten by scope resolution |
| `event_resolver.py:107` | a publisher→listener edge synthesised from event names |

Control arm: `grep -rn INFERRED` over `code_review_graph/**.py` → 4 hits in 2
files; the same grep for `EXTRACTED` → 4 hits, all in `graph.py`, **zero in
`parser.py`**. So every one of the 16,080 lines of tree-sitter extraction
emits edges that take the schema default. Practical reading: CRG's tier is a
*demotion marker on two specific heuristics*, not a provenance discipline
applied at extraction time.

### Where CRG's edge payload is RICHER than graphify's

`edge_to_dict` also carries `ambiguous_targets` / `unresolved_targets` (capped
at 20) plus `*_target_count` and `*_targets_truncated` flags. That is an
explicit, machine-readable record of *what the resolver could not decide*,
returned to the agent inside the query result. It is the one place CRG's
provenance model is strictly more informative than a confidence tier.

## Staleness: CRG answers "is this graph current?" per call; graphify does not

Every CRG MCP tool wraps its result in `with_provenance()`
(`tools/_common.py`), attaching a `_graph` envelope:

```
{"updated_at", "age_seconds", "built_at_sha", "built_on_branch",
 "head_sha", "head_matches_build"}
```

`head_matches_build` is a live `git rev-parse --verify HEAD` (1s timeout,
`stdin=DEVNULL`) compared against the `git_head_sha` row in the SQLite
`metadata` table. The docstring is explicit that it compares **commits only**
and deliberately does not claim staged/unstaged files are represented —
citing their issue #458 as the reason the older `is_stale=False` contract was
withdrawn. The whole path is `try/except`-wrapped so a missing or locked DB
degrades to *no envelope* rather than a failed tool call, and the read uses a
50 ms SQLite timeout so a concurrent build never blocks a query.

**graphify 0.9.31 has no equivalent.** Armed:

- `built_at_commit` IS written — `export.py:317`, from `_git_head()`.
- It is read by `callflow_html.py` and `report.py` (the HTML/markdown views)
  and popped as noise by `watch.py:677,689`.
- `grep -rn "built_at_commit" serve.py` → **0 hits**; `grep -n "stale"
  serve.py` → 2 hits, both unrelated (a `learning=` suffix and the word
  "stale" inside the `triage_prs` description text). `rev-parse` → 0 hits.
- **Control arm**: `grep -c "token_budget" serve.py` → 20, so the probe
  discriminates on this file.

So an agent talking to `mise run kb-serve` gets no signal about whether the
graph it is reading predates the working tree. This repo compensates *out of
band* with `kb-currency-check` + `graphify-out/.currency-stamp.json`, but that
is a repo-level offline check the MCP consumer never sees. **This is the
single clearest capability CRG has that graphify lacks.**

## Query surface: a fixed relation vocabulary vs a keyword traversal

The two tools answer questions in fundamentally different shapes.

**graphify** (`serve.py:1294–1418`) exposes **11** MCP tools:
`query_graph`, `get_node`, `get_neighbors`, `get_community`, `god_nodes`,
`graph_stats`, `shortest_path`, `list_prs`, `get_pr_impact`, `triage_prs`
(+ a `project_path` parameter injected into every schema for multi-project
use). Its primary tool takes a **natural-language question** and does a
BFS/DFS walk at `depth ≤ 6` under a `token_budget`, returning `NODE`/`EDGE`
text lines with `[EXTRACTED]` tags and `src=…:L…` anchors.

**CRG** (`main.py`) registers **30** `@mcp.tool()` functions. Control arm:
`grep -c "@mcp.tool()" main.py` → 30, and the function list enumerates 30
distinct names. Its primary query tool takes **`pattern` + `target`**, where
`pattern` is one of a closed set of 16 (`tools/query.py:_QUERY_PATTERNS`):

`callers_of`, `references_to`, `callees_of`, `imports_of`, `importers_of`,
`children_of`, `tests_for`, `inheritors_of`, `triggers_of`, `triggered_by`,
`publishers_of`, `listeners_of`, `handlers_of`, `endpoints_for`,
`consumers_of`, `file_summary`.

That is a **relational query language, not a search**. "Who calls X" is a
single indexed SQLite lookup with an exact answer; in graphify the same
question is a fuzzy keyword BFS whose recall depends on the question's tokens
matching node labels — the exact failure mode this repo's own
`probes-need-a-control-arm.md` documents ("`lmstudio` → 0, `LM Studio` → 3").

Six of those 16 patterns (`triggers_of`, `triggered_by`, `publishers_of`,
`listeners_of`, `handlers_of`, `endpoints_for`, `consumers_of`) are
**framework-semantic**, not language-semantic: they encode Spring schedulers,
event buses, HTTP endpoint handlers, and Spring config-property consumers. CRG
ships dedicated `spring_resolver.py`, `event_resolver.py`, `hcl_resolver.py`,
`tsconfig_resolver.py`, `jedi_resolver.py`, `rescript_resolver.py`.

CRG also ships a noise filter graphify has no analogue for: `_BUILTIN_CALL_NAMES`
in `tools/_common.py`, ~190 JS/TS builtin method names (`map`, `then`, `get`,
`expect`, …) excluded from **reverse** call tracing only — kept in the graph so
`callees_of` still shows them. The comment states the motivation plainly:
"Who calls .map()? returns hundreds of hits and is never useful."

## Retrieval mechanics: FTS5+RRF vs IDF-seeded graph walk

### CRG

`search.py` docstring, verbatim: *"Hybrid search engine combining FTS5 (BM25)
and vector embeddings. Uses Reciprocal Rank Fusion (RRF) to merge results from
full-text search and semantic similarity, with query-aware kind boosting and
context-file boosting."* The FTS index is a real SQLite virtual table:

```sql
CREATE VIRTUAL TABLE nodes_fts USING fts5(
    name, qualified_name, file_path, signature,
    content='nodes', content_rowid='rowid',
    tokenize='porter unicode61')
```

Porter stemming + unicode61 folding at the index, so `parsing` matches
`parse`. Rebuild is wrapped in `BEGIN IMMEDIATE` so a crash cannot leave the DB
with no FTS table (their #259).

### graphify — and a claim of this repo's I had to REFUTE

`serve._query_graph_text` (`serve.py:1033`) is what BOTH the MCP `query_graph`
tool and the CLI `graphify query` run — `cli.py:856` does
`from graphify.serve import _query_graph_text` and calls it at `cli.py:952`.
So `mise run kb-query` and `kb-serve` share one retrieval path.

I went in expecting to write *"graphify's BFS is unscored, which is why this
repo bolted on `--idf`"* — that is close to how `mise.toml:279` and
`CLAUDE.md` describe it. **The installed source refutes the strong reading.**
`_score_query` (`serve.py:433`) calls `_compute_idf` (`serve.py:275`), whose
own docstring says: *"Common terms like 'error' or 'exception' … get low
weights; rare identifiers like 'FooBarService' get high weights."* The scorer
also does a trigram candidate prefilter, multi-tier label matching
(source-exact / exact / prefix / substring), coverage scaling across query
terms, and an IDF-weighted whole-query bonus.

The accurate statement is narrower: **graphify ranks the SEEDS by IDF, then
returns an unranked BFS/DFS neighbourhood of those seeds truncated at the
token budget.** `kb_setup`'s `--idf` arm ranks the *returned set*, which
graphify does not. That distinction is real and this repo's measured 1/8 →
5/8 recall gain stands — but "graphify has no IDF" would have been false, and
I would have written it.

### What that difference means in practice

| | CRG | graphify 0.9.31 |
|---|---|---|
| lexical ranking | FTS5/BM25 over `name`, `qualified_name`, `file_path`, `signature`, Porter-stemmed | IDF-weighted tiered label match over `norm_label`/`label_tokens`/`source`; substring, **no stemming** |
| semantic ranking | optional vector embeddings, RRF-fused with BM25 | **none** — armed: `grep -rln "bm25\|fts5\|reciprocal rank"` over the whole installed package → **0 files**; `grep -rln "embedding\|cosine"` → 4 files, and all four hits are the English word ("escape … for embedding in YAML", "interface embedding" in the Go extractor), not a vector index. Control arm: `networkx` → present in both `serve.py` and `cli.py`. |
| result shape | ranked rows | a subgraph (nodes+edges), seed-first, budget-truncated |

## Does either need an LLM?

**Neither, for structure.** This is the axis on which they agree most.

- CRG: `grep -rn "chat/completions\|messages.create\|anthropic\|generate_content"`
  over `code_review_graph/**.py` → **0 hits**. Control arm: the same grep style
  for embedding endpoints → 44 hits in `embeddings.py`. So CRG calls *embedding*
  APIs and never a chat/completion API. Structure comes from Tree-sitter.
- CRG's embeddings are **optional and can be fully local**:
  `LocalEmbeddingProvider` uses `sentence-transformers`, and
  `CLOUD_PROVIDERS = {"google", "minimax", "openai", "voyage"}` are the opt-in
  alternatives. `semantic_search_nodes_tool`'s own docstring says it "uses
  vector embeddings … **when available**", falling back otherwise.
- graphify: AST extraction is free/no-LLM (this repo depends on that
  invariant), and its LLM path (`llm.py`) is for *semantic* extraction of prose,
  not for code structure or for query.

Difference worth noting: CRG's optional cloud embedding providers would be a
**hard invariant violation here** — `do-not.md` rule 4 and
`kb_setup.graphify_env.clean_env()` strip Google/OpenAI triggers from every
graphify subprocess. Adopting CRG's semantic search would mean either the local
sentence-transformers provider only, or an explicit exemption. The local
provider makes that tractable; it is not a blocker.

## Blast radius — and a SECOND claim I had to refute

### graphify `affected` (`affected.py`, 273 lines)

`graphify affected "<node-or-label>" [--relation R] [--depth N]`.
`resolve_seed(graph, query)` picks **one** node (returns `None` and prints
"No unique node match" on ambiguity), then `affected_nodes` does a
relation-filtered **reverse** BFS over `in_edges` to `depth` (default 2). Each
hit carries `via_relation` + the *call-site* file:line taken from the same edge
dict whose relation matched — deliberately, per an inline `#BUG1` note, so the
location is where you would click, not the callee's def line. There is a
`method`/`contains` seed-expansion hop (`#1669`) so a class's callers are
reachable when callers bound to the method node.

No score, no truncation flag, no cap: it returns every hit at that depth.

### CRG `get_impact_radius` (`graph.py:1317`)

Seeds are **every node in a set of changed FILES** (`_impact_seed_qns`), not
one symbol. The default engine is a bounded best-score relaxation executed
**inside SQLite** (`get_impact_radius_sql`), with `CRG_BFS_ENGINE=networkx` as
a legacy fallback. Each edge kind carries a `(weight, direction)` policy row in
a temp table; scores decay per hop (`IMPACT_DEPTH_DECAY`), stop at
`IMPACT_SCORE_FLOOR`, and only the *best* path score per node is kept — the
docstring explains this is precisely to avoid the exponential path enumeration
a recursive CTE would hit on dense cyclic graphs. Returns `changed_nodes`,
`impacted_nodes` (ordered by score), `impacted_files`, `edges`,
`impact_scores`, `total_impacted`, and **`truncated`**. Bounds:
`CRG_MAX_IMPACT_DEPTH=2`, `CRG_MAX_IMPACT_NODES=500`.

### The refutation

I expected to write *"graphify's `affected` is single-seed only; it has no
change-set blast radius."* **False.** `prs.py:252
compute_pr_impact(files, G)` takes a **list of changed files** and returns
`(communities_touched, nodes_affected)`; `PRInfo.blast_radius` renders it;
`graphify prs --conflicts` surfaces PRs sharing communities as merge-order
risk; and the MCP tools `list_prs` / `get_pr_impact` / `triage_prs` expose all
of it. graphify has change-set impact.

The **true** distinctions, each armed:

| | graphify 0.9.31 | CRG |
|---|---|---|
| change-set source | `gh pr diff <n> --name-only` (`prs.py:230`) — **requires GitHub + an open PR** | local `git diff` / `git status`, incl. staged+unstaged (`get_staged_and_unstaged`), and SVN |
| granularity | **community-level**: which communities, how many nodes | **node-level**, each with a decayed path score |
| scoring | none | per-edge-kind weight × depth decay, best-path |
| truncation honesty | no cap, so no flag needed on `affected`; `compute_pr_impact` is a count | explicit `truncated: bool` on both `get_impact_radius` and `find_dependents` (a `DependentList` subclass carrying `.truncated`, their #261) |
| "which tests must I run?" | **absent** | `TESTED_BY` edges + `get_transitive_tests` |

That last row is the one clean, fully-armed absence. `grep -rln
"tested_by\|TESTED_BY\|tests_for"` over the entire installed graphify package →
**0 files**. Control arm: `grep -c affected cli.py` → non-zero on the same
tree, so the probe discriminates. CRG: `grep -rn TESTED_BY` → **63** hits, with
`get_transitive_tests` (`graph.py:541`) following direct `TESTED_BY` edges plus
indirect coverage through `CALLS` hops, fan-out capped at
`CRG_MAX_TRANSITIVE_FRONTIER=50` per hop to avoid O(N·M) on hub functions.

**graphify cannot answer "which tests cover this change".** CRG can, and
exposes it as the `tests_for` query pattern.

## Indexing model

| | CRG | graphify 0.9.31 |
|---|---|---|
| parser | Tree-sitter (`parser.py`, 16,080 lines) | its own AST extractors (`extractors/`) |
| store | **SQLite** (`nodes`, `edges`, `metadata` + 9 indexes + an FTS5 virtual table) | a single **`graph.json`** loaded into NetworkX in memory |
| unit of change | per-file SHA-256 (`file_hash` column); a file whose hash is unchanged is skipped outright | `graphify update` (AST-only, free) |
| reindex scope | changed files **plus dependents**, discovered by walking `IMPORTS_FROM`/`CALLS`/`INHERITS`/`IMPLEMENTS` edges backwards up to `CRG_DEPENDENT_HOPS=2` | whole-path re-extract, then merge |
| deletion handling | `_reconcile_stale_files` + `remove_files_permanently` | `_check_shrink` refuses a shrinking overwrite (this repo's `do-not.md` note on `watch`) |
| parallelism | thread/process pool, serial below 8 files (`CRG_SERIAL_PARSE`) | — |
| schema evolution | `migrations.py` + a `_CPP_IDENTITY_METADATA_KEY` version check that forces a **full rebuild** when the C++ identity format changes | — |

The SQLite choice is the structural difference with the largest downstream
consequence for THIS repo. `graphify-out/graph.json` is 119 MB at aggregate
scale — too large for git, and `kb-query` pays a whole-file JSON parse and
NetworkX materialisation per invocation (this repo measured ~9.5 s unscoped
vs ~0.3 s on the prose graph, which is the same cost showing up as a
size-proportional constant). CRG's queries are indexed point lookups against
a file that is never fully loaded, and its impact traversal runs *in the
database*. That is why `MAX_IMPACT_NODES=500` is a product decision for CRG and
`--budget` is a survival mechanism for graphify.

The corresponding graphify answer already exists and this repo already knows
it: native `push_to_neo4j()` / `push_to_falkordb()` exporters plus `--push`
(`use-tool-builtins.md`). So "graphify cannot scale queries without loading
the whole graph" would be **too strong** — it can, via an external graph DB.
The honest framing: CRG gets indexed retrieval with **zero** infrastructure;
graphify needs a server for the same property.

## The review-specific angle — does the name earn itself?

Yes, and it is more than a general code graph rebranded. `changes.py`
docstring: *"Maps git/svn diffs to affected functions, flows, communities, and
test coverage gaps. Produces risk-scored, priority-ordered review guidance."*

Concretely, review-only machinery with no graphify counterpart:

1. **Line-range precision.** `parse_git_diff_ranges` runs `git diff
   --unified=0` and extracts `(start_line, end_line)` **hunks per file**, then
   intersects them against node `line_start`/`line_end`. graphify's PR impact
   works at file granularity (`gh pr diff --name-only`), so a one-line change
   in a 3,000-line file has the same blast radius as a rewrite.
2. **Risk scoring** with `SECURITY_KEYWORDS` (`constants.py`) folded in;
   `get_review_context` emits `risk ∈ {low, medium, high}` and
   `_generate_review_guidance` produces prose guidance, priority-ordered.
3. **Test coverage gaps** — changed nodes with no reachable `TESTED_BY`.
4. **Flows** (`flows.py`, `get_affected_flows`): named end-to-end call paths
   with a criticality score, so "this change sits on the checkout flow" is
   answerable.
5. **`get_review_context`** bundles impact + the actual changed source lines
   (`max_lines_per_file`, default 200) + guidance in one call, with a
   `detail_level: minimal|standard` token dial on nearly every tool.
6. Prompt-level entry points registered as MCP **prompts**, not tools:
   `review_changes`, `architecture_map`, `debug_issue`, `onboard_developer`,
   `pre_merge_check`.
7. `refactor_tool` / `apply_refactor_tool` — graph-driven rename that
   **writes files**. graphify's MCP server is read-only by design; this is a
   capability difference *and* a threat-surface difference.

Injection/abuse hygiene worth noting since this repo would be the host:
`_validate_repo_root` refuses any `repo_root` without `.git`/`.svn`/
`.code-review-graph`, git refs are validated against
`^[A-Za-z0-9_.~^/@{}\-]+$` before reaching `subprocess`, every `subprocess.run`
uses `stdin=DEVNULL` + an explicit timeout, and `http_origin_guard.py` exists
for the HTTP transport. That is more hardening than a hobby project usually
carries.

## Direction 1 — what CRG does that graphify 0.9.31 cannot

Each row armed against the installed graphify tree.

| Capability | Evidence CRG has it | Evidence graphify lacks it |
|---|---|---|
| **Per-query staleness** (`head_matches_build`) | `tools/_common.py graph_provenance()`, wrapped onto every tool result | `grep built_at_commit serve.py` → 0; `rev-parse` → 0. Control: `token_budget` → 20 |
| **Test-impact mapping** ("which tests cover this change") | 63 `TESTED_BY` sites; `get_transitive_tests`; `tests_for` pattern | `grep -rln "TESTED_BY\|tests_for"` over the package → **0 files**. Control: `affected` → present in `cli.py` |
| **BM25 lexical ranking with stemming** | FTS5 `tokenize='porter unicode61'` | `grep -rln "bm25\|fts5\|reciprocal rank"` → **0 files** |
| **Vector/semantic search** | `embeddings.py`, 5 providers, RRF-fused | `grep -rln "embedding\|cosine"` → 4 files, **all English-prose hits** (YAML escaping, Go interface embedding) — no vector index |
| **Indexed store; no full-graph load** | SQLite + 9 indexes + FTS5; impact BFS runs *in SQL* | `graph.json` → NetworkX in memory. Mitigated but not removed by `push_to_neo4j`/`push_to_falkordb` |
| **Diff-hunk granularity** | `git diff --unified=0` line ranges ∩ node spans | `prs.py:230` uses `--name-only` |
| **Local uncommitted-change review** | `get_staged_and_unstaged`; SVN too | `prs.py` requires `gh` + an open PR |
| **Risk score + review guidance + coverage gaps** | `changes.py`, `tools/review.py` | no analogue |
| **Explicit truncation flags** | `DependentList.truncated`, `get_impact_radius(...)["truncated"]` | `affected` is uncapped (so no flag needed); nothing else reports a bound |
| **Ambiguity carried in the payload** | `edge_to_dict` emits `ambiguous_targets` / `unresolved_targets` + counts + truncation flags | graphify surfaces ambiguity at *seed resolution* (`find_node_ambiguity`), not per-edge |
| **Graph-driven refactor that writes** | `refactor_tool` / `apply_refactor_tool` | read-only server |
| **~190-name reverse-call noise filter** | `_BUILTIN_CALL_NAMES` | no analogue found |
| **16-name closed relational query vocabulary incl. framework semantics** | `_QUERY_PATTERNS`; Spring/event/HCL/tsconfig/jedi/rescript resolvers | graphify has `--relation` filters and `context_filter`, but no framework-semantic patterns |
| **Tool-surface breadth** | **30** MCP tools | **11** |

## Direction 2 — what graphify does that CRG cannot

| Capability | Evidence graphify has it | Evidence CRG lacks it |
|---|---|---|
| **Ingest anything that is not code** — URLs, web pages, tweets, arXiv, PDFs, YouTube (+ transcription) | `ingest.py:64 _detect_url_type` returns `youtube`/`pdf`/`arxiv`/`tweet`/`web`; `safe_fetch` in `security.py` | **The only network code in the entire CRG package is `embeddings.py`** — `grep -rln "urlopen\|urllib.request\|socket.connect"` over `code_review_graph/**` → 1 file, `embeddings.py`. CRG cannot fetch a URL at all. Its `get_docs_section_tool` reads CRG's **own packaged** `LLM-OPTIMIZED-REFERENCE.md`, not user documentation. |
| **Semantic (LLM) extraction of prose into graph nodes** | `llm.py`, and this repo's whole `kb-extract` fan-out | `grep -rn "chat/completions\|messages.create\|anthropic\|generate_content"` over CRG → **0 hits**. Control: 44 embedding-endpoint hits. CRG has no LLM path of any kind. |
| **Shortest path between two concepts** | MCP `shortest_path`; `graphify path "A" "B"` | `grep -rln "shortest_path\|dijkstra\|bidirectional"` over CRG → **0 files**. Control: `networkx` present in `graph.py`. CRG's `traverse_graph_tool` is one-seed BFS/DFS, not A→B. |
| **Reflection over work-memory** (decay-weighted lesson aggregation → `LESSONS.md` + learning overlay) | `reflect.py`: `_decay(half_life_days)`, `aggregate_lessons`, `render_lessons_md`, community mapping of memory docs | CRG **does** have `memory.py` (`save_result`/`list_memories`/`clear_memories`) — a near-shape-identical port down to a markdown `<repo>/.code-review-graph/memory/` dir — but `grep -rln "reflect\|LESSONS\|half_life\|decay"` over CRG → 1 file, `context_savings.py`, unrelated. **Memory yes, reflection no.** |
| **Query telemetry** | `querylog.log_query` records every MCP and CLI query with corpus, mode, depth, budget, duration | no analogue found |
| **Non-tree-sitter structural sources**: SCIP/LSP index ingest, MCP-server introspection, Postgres and Cargo introspection, Google Workspace | `scip_ingest.py`, `mcp_ingest.py`, `pg_introspect.py`, `cargo_introspect.py`, `google_workspace.py`, `manifest_ingest.py` | CRG's only input is tree-sitter over VCS-tracked files |
| **A multi-source aggregate corpus** | this repo merges 26 pinned sources into one graph | CRG's registry is multi-**repo** (`list_repos_tool`, `cross_repo_search_tool`) but every repo must be a local working tree it parsed itself |

### What is NOT a graphify advantage (assumptions I killed)

CRG independently ships: community detection (`communities.py`,
`list_communities`, `get_community`), hub and bridge nodes
(`get_hub_nodes_tool`, `get_bridge_nodes_tool` — graphify's `god_nodes`), a
generated wiki (`generate_wiki_tool`, `get_wiki_page_tool`), an architecture
overview, graph stats, an eval harness (`eval/` with benchmarks for multi-hop
retrieval, impact accuracy, token efficiency, search quality, flow
completeness), visualization/exports, and multi-repo cross-search. Every one
of those was on my initial "graphify-only" list and none of them survived.

## Verdict for this repo

**Not a replacement; a complement with one clean adoption target.**

CRG's ingest surface is strictly narrower than what this repo exists to do —
it cannot read a URL, a PDF, a transcript, or a prose doc, which is most of
this corpus. It is not a candidate to replace `graphify-out/graph.json`.

Three ideas are worth stealing rather than adopting:

1. **Per-response staleness.** `head_matches_build` inside the tool payload is
   strictly better than an offline `kb-currency-check` the MCP consumer never
   sees, and it is ~40 lines. This repo already has `built_at_commit` in
   `graph.json` — the data is there and `kb-serve` simply does not surface it.
   Highest value-to-effort item in this report.
2. **Explicit truncation flags.** `DependentList.truncated` is the same
   discipline this repo's own workflow guidance states as "no silent caps",
   implemented in a type. `kb-query`'s budget truncation is currently silent.
3. **`--idf` is the right instinct and CRG proves the ceiling.** FTS5 with
   Porter stemming is a strictly stronger version of what `kb_setup`'s IDF
   arm approximates, and SQLite gives it for free. But note the refutation
   above: graphify already does IDF at seed selection, so the gain is
   stemming + ranking the *returned* set, not "adding scoring".

Not worth stealing: the review-specific stack (risk scores, guidance prose,
coverage gaps) overlaps this repo's `kb-review` skill, which is a cross-family
*model* review rather than a structural one — different failure modes, and the
`kb-review` receipt gate is the part that actually blocks a ship.

## Claims marked UNVERIFIED

- I did **not execute** CRG. No `build`, no MCP handshake, no measurement.
  Every claim here is read off source at the pinned SHA. The README's
  "38x–528x token reduction" and "~10 seconds for a 500-file project" numbers
  are **UNVERIFIED** and are not repeated as findings anywhere above.
- CRG's exact supported-language count is **UNVERIFIED**. It delegates to
  `tree_sitter_language_pack.get_parser(grammar)` at runtime, so the set is a
  property of the installed pack, not a literal in the source I could count.
  graphify's 28 `extractors/*.py` modules were counted directly and are a
  lower bound on its own set, not a like-for-like comparison.
- The claim "no analogue found" for `querylog` and `_BUILTIN_CALL_NAMES`
  rests on keyword greps of the other tree; a differently-named equivalent
  could exist. Weaker than the rows with an explicit control arm.

## GitHub repos touched

- [tirth8205/code-review-graph](https://github.com/tirth8205/code-review-graph) — the tool under analysis; read at the pinned SHA.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the baseline; read the INSTALLED 0.9.31 tree (`serve.py`, `affected.py`, `prs.py`, `export.py`, `ingest.py`, `reflect.py`, `querylog.py`, `cli.py`, `extractors/`).

Referenced by CRG but **not** read here (no claim rests on them):
tree-sitter, `tree_sitter_language_pack`, sentence-transformers, Voyage AI.

## Claims refuted

**Four**, all of them my own drafts, killed by the installed source before they
reached this file:

1. *"graphify's query is an unscored BFS — it has no IDF."* **Refuted** by
   `serve.py:275 _compute_idf`, called from `_score_query`. graphify does IDF
   at seed selection; only the *returned* set is unranked.
2. *"graphify's `affected` is single-seed only; it has no change-set blast
   radius."* **Refuted** by `prs.py:252 compute_pr_impact(files, G)` and the
   `list_prs`/`get_pr_impact`/`triage_prs` MCP tools.
3. *"Communities, god nodes, wiki generation and multi-repo search are
   graphify-only."* **Refuted** — CRG ships all four
   (`communities.py`, `get_hub_nodes_tool`/`get_bridge_nodes_tool`,
   `generate_wiki_tool`, `cross_repo_search_tool`).
4. *"Work-memory (`save-result`) is graphify-only."* **Refuted** by CRG's
   `memory.py` (`save_result`/`list_memories`/`clear_memories`). The surviving,
   narrower claim is that CRG has memory but **no reflection layer**.

A fifth was *narrowed* rather than refuted: "graphify cannot do indexed
retrieval without loading the whole graph" — true of the JSON path, false as
stated, since `push_to_neo4j`/`push_to_falkordb` exist.
