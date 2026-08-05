# graphify — expert operational reference

Distilled from mastering graphify v8 (source `e32c9f4`, pip `graphifyy` 0.9.24 in
source / **0.9.23** installed) by building this KB from its own source. Authoritative
sources: `sources/graphify/` (README, ARCHITECTURE.md, docs/, pyproject.toml, tests),
the CLI (`graphify --help`), and this repo's own graph. **For command syntax, the
README's Full Command Reference is authoritative; this doc is the mental model.**

## Pipeline

`detect() → extract() → build_graph() → cluster() → analyze() → report() → export()`
Plain dicts + NetworkX, no side effects outside `graphify-out/`.

## Extraction — three passes

| pass | inputs | cost | mechanism |
|---|---|---|---|
| **1. code** | 25 tree-sitter languages (incl. JSON) + package manifests (`pyproject.toml`/`go.mod`/`pom.xml` via `is_package_manifest_path` → deterministic tomllib parse, **not** tree-sitter) + SQL/postgres/cargo | **free, no key** | AST |
| **2. video/audio** | `.m4a` etc. | local | faster-whisper (needs **ffmpeg** system binary), prompt seeded with god nodes |
| **3. docs/papers/images** | `.md/.pdf/images` | **tokens** | semantic LLM |

- **A code-only corpus skips pass 3 entirely.** `graphify extract <path> --code-only`
  = pass 1 only, zero key/LLM. `--mode deep` = aggressive INFERRED edges (cache
  namespaced `semantic` vs `semantic-deep` since 0.9.17).
- **Pass-3 backends** (`--backend`): `gemini/openai/kimi/deepseek/claude/bedrock`
  (need keys), `ollama` (local), `claude-cli` (routes through `claude -p`, **BROKEN
  on v8 — #2076, returns prose → 0 nodes**). **This KB FORBIDS every non-Claude
  backend**: `kb_setup.graphify_env.clean_env()` strips Gemini/Google/OpenAI/Kimi/
  DeepSeek/Azure/**Bedrock (`AWS_REGION`)**/Ollama from every graphify subprocess, so
  `detect_backend()` returns None (keeping only `ANTHROPIC_*`). Do NOT read "no key"
  as "no key present" — a global `GEMINI_API_KEY` exists and is deliberately blocked.
  Prose extraction therefore falls to the **HOST AGENT** (Claude) — the running Claude
  Code session dispatches a `Workflow` fan-out of `general-purpose` subagents that emit
  graph JSON. That is the only prose path here, and it is Claude.
- **Incremental:** `graphify update <path>` re-extracts only files whose MD5 changed
  (`detect_incremental` diffs `graphify-out/manifest.json`). CLI `update` is
  **code-only**; changed docs still need a host-agent pass. Semantic cache
  (`graphify-out/cache/`) is content-hashed → unchanged docs replay free.
- **⚠️ NEVER `graphify hook install`** — its post-commit `update` stamps AST hashes
  that make a later semantic `extract` silently skip edited files (#857, shared
  `manifest.json`).

## Community detection + labeling

- **Leiden** (graspologic) requires `python_version < '3.13'` → **≤ 3.12 only**.
  On 3.14 it auto-skips → **Louvain fallback** (accepted). Louvain numbering is
  **non-deterministic** — re-clustering renumbers communities.
- **Labeling** (`mise run kb-label` — NEVER `graphify label` by hand). This KB uses
  the **deterministic, LLM-free hub labeler**: each community is named after its
  highest-degree node → `graphify-out/.graphify_labels.json` (keyed to community ids;
  gitignored/derived). Why not LLM names: the only non-Gemini LLM backend is
  `claude-cli`, and it is **broken for labeling (#2076)**; and Gemini is FORBIDDEN
  (`clean_env` strips it). `mise run kb-label` prints "no LLM backend configured;
  keeping Community N placeholders" — MISLEADING: the deterministic hub labels are
  still applied during clustering (verified 2026-07-22: 2,409/2,409 named, 0
  placeholders). Always relabel after a merge (Louvain renumbers).

## Outputs (`graphify export <fmt>` = 8 formats + more)

| output | command | notes |
|---|---|---|
| graph | `graph.json` | source of truth (NetworkX node-link) |
| report | `cluster-only` | `GRAPH_REPORT.md` (re-clusters!) |
| interactive viz | `export html` | aggregates to community view >5000 nodes |
| tree viz | `tree` | `GRAPH_TREE.html` (D3 collapsible) |
| call-flow | `export callflow-html` | Mermaid architecture |
| static viz | `export svg` | **needs scipy** (spring_layout); slow + hairball at scale |
| Gephi/yEd | `export graphml` | `graph.graphml` |
| graph DB | `export neo4j`/`falkordb` | `cypher.txt`, or `--push <uri>` to a live DB |
| agent wiki | `export wiki` | `wiki/` index + article per community + god-node |
| Obsidian | `export obsidian` | one `.md` per node ([[wikilinks]]) |
| **MCP server** | `mise run kb-serve` | stdio/http; **10 read-only tools + 6 resources**, zero LLM tokens; `project_path` routes per-project; NO add/mutate tool. Narrow it with `KB_MCP_TOOLS` — see below |
| analysis | `god-nodes` / `benchmark` / `diagnose multigraph` | stdout |

## Serving over MCP — `mise run kb-serve`

**`raw = true` on the task is REQUIRED, not tuning.** Without it `mise run` reads a
task's stdio by line instead of connecting it, so the stdio server hits EOF on its
first read and exits — rc=0, empty stderr. Measured 2026-08-02 (#105): the task
served NOTHING while `graphify-mcp` on the same absolute path answered in 9.8s.
A clean exit is why no check caught it; `tests/test_mcp_serve.py` now speaks real
JSON-RPC against the task, which is the only arm that can.

Expect the first reply to take **~10s** on the aggregate graph — that is the 393 MB
load, not a hang (the 3.4 MB prose graph answers in 0.6s).

### Narrowing the advertised surface

graphify has no `--tools` flag in **0.9.31 or 0.9.32**, and Claude Code has no
client-side per-tool filter — only server-level toggles. So the allowlist lives
here, in `kb_setup.mcp_serve`, and it is **opt-in**:

```bash
KB_MCP_TOOLS=query_graph,shortest_path KB_MCP_RESOURCES=graphify://stats \
  mise run kb-serve
```

- The two variables are **independent** — set either alone to narrow only that
  surface. They are shown together above because the measured figure below is
  the combined one, and an env assignment scopes to the single command it
  prefixes: two separate invocations would each narrow one surface and neither
  would reproduce it.
- **Unset = no filtering AND no relay** — the child inherits stdio directly.
- **Blank or all-separators also means unset**, deliberately: it fails OPEN,
  because a server advertising zero tools looks exactly like a broken one.
- Measured: unset → 10 tools / 5,828 B / 6 resources; the invocation above →
  2 tools / 1,516 B / 1 resource.

**Whether this is worth setting depends on the consumer, and the condition
matters.** Under Claude Code's default *tool search*, MCP tools are deferred and
only NAMES load (118 B ≈ 30 tokens), so trimming buys almost nothing. It buys the
full 5,828 B back only where schemas load upfront — `ENABLE_TOOL_SEARCH=false`, a
custom `ANTHROPIC_BASE_URL`, Bedrock, Google Cloud's Agent Platform, Microsoft
Foundry. The other reason is independent of tokens: a tool's mere presence steers
a model into picking it.

An allowlist plus `--transport http` is **REFUSED (rc=2)** rather than served: the
relay only rewrites JSON-RPC on the child's pipes, so it could not enforce the
allowlist over a listener socket, and serving unfiltered under a "narrowed to N"
banner is worse than not filtering.

## The Python-3.14 scientific-stack gap (bit us twice)

graspologic (`leiden`) needs `<3.13` and **transitively pulls scipy**. On 3.12,
installing `[all]` gets Leiden AND scipy (so `export svg` works). On **3.14**:
graspologic skipped → no Leiden AND **no scipy → `export svg` breaks**
(`nx.spring_layout` needs it). graphify's `svg` extra never declares scipy — inject
it (`kb-ensure-deps`). Choosing 3.14 = Louvain + a scipy inject; 3.12 = both native.

## Install / scoping (project-only invariants)

- `graphify install --project` = writes only `./.claude/**` + `./CLAUDE.md`. **Never**
  bare `graphify install` (mutates `~/.claude`), never `extract --global` / `global
  add` (shared mutable machine state). `--strict` install blocks the first raw read
  → redirects to `graphify query` (toggle `GRAPHIFY_HOOK_STRICT`).

## Aggregate graph (many sources → one, ongoing)

The KB grows by MERGING per-source graphs into one aggregate — the intended model,
extended every time a source is ingested:

- **`graphify merge-graphs <g1> <g2> [...] --out <path>`** — union-merge 2+ graph.json
  into one **cross-repo** graph. This is the code layer's merge path and is
  multi-repo-safe (no cross-project dedup).
- **Cross-project dedup is DISABLED by design.** `build`/`build_merge` run
  `deduplicate_entities`, which **raises** once nodes span >1 repo (`main` in repo A
  ≠ repo B). Each source is already single-repo-deduped at extraction, so at
  merge-into-aggregate time dedup MUST be off — `kb-build`'s doc merge passes
  `dedup=False` for exactly this (see `_merge_docs.py`). This was a real 60k-node
  build failure, now fixed.
- **`graphify merge-driver <base> <cur> <other>`** — a git merge driver that
  union-merges `graph.json` on branch merges (wired by `hook install` — which we do
  NOT run, #857). Relevant to the deferred concurrency design: git-native graph merge
  is one candidate for serializing parallel adds.
- Re-label after a merge: **`mise run kb-label`** (deterministic hub labels). Do NOT
  use `--missing-only` after a merge: Louvain **renumbers every community**, so the
  surviving labels are pinned to the wrong ids — a FULL relabel is required, which
  `kb-label` does. (`--missing-only` is only correct when community numbering is
  stable, which it never is after a merge.)

### Merge N-ARY, never pairwise (#120)

`merge-graphs` takes **N paths in one call** — that is what the bullet above means
by "2+", and calling it that way is not an optimisation, it is the correctness
requirement. `prefix_graph_for_global` (`build.py:1449`) prefixes every input
unconditionally with `<repo_tag>::` and has **no already-prefixed guard**, so
feeding the accumulator back in once per source re-prefixes everything already
merged.

Measured 2026-08-03, before and after, on the same repo:

| | pairwise loop | one N-ary call |
|---|---|---|
| node-id `::` depth | 1–22, mode 10 | **1–2** |
| duplicate-prefix waste | 184 MB, **33% of the file** | **0.00%** |

Depth 2 is the floor, not a leak: one prefix from the corpus composition, one from
the final self-merge that runs after the base snapshot. `kb_setup.graph._merge_sources_into`
is the only place this is spelled; `tests/test_merge_prefixes_once.py` holds the
unit, integration and control arms.

### Provenance is in the node ID, NOT in `repo` (#164)

That second prefix pass has a cost nobody had read off the artifact until
2026-08-05. `prefix_graph_for_global` sets `data["repo"] = repo_tag`
**unconditionally** while `local_id` uses `setdefault` — so the self-merge
overwrites every already-merged node's tag. Measured: `repo` has exactly **two**
values, `knowledge-base` (331,251) and `.self-graph` (3,235), across 46 sources.

**Read `node["id"].split("::")[1]`** for the source — 40+ distinct tags, and it is
correct for all 328,387 depth-2 nodes. The `setdefault` asymmetry is also the proof
of exactly two passes: a sampled node's `local_id` lacks the `OpenSymphony::`
segment its `id` carries.

### Cross-source edges are IMPOSSIBLE via merge — by design

`merge-graphs` is `nx.compose` over inputs each relabelled into a disjoint
`<tag>::` namespace (`cli.py:2166-2172`). `compose` unifies nodes by id equality
only, so no node is ever identified across sources and no edge can span two.
**Measured: 0 cross-source edges of 816,538**, control-armed three ways (the
sharpest: 100% of edges classified by id prefix, 0 skipped, while the same parser
finds 108,647 edges crossing a *community* boundary). Upstream #1729 confirms the
intent — colliding prefixes were the defect, because they "invent cross-runtime
edges".

The one mechanism that DOES span sources is a **single `extract` over a single
root**: `resolve_cross_file_raw_calls` (`symbol_resolution.py:307-376`) builds a
global label→id index over the whole scanned tree and emits `calls`/INFERRED/0.8
for uniquely-resolving bare names. So connectivity is bought at extraction time,
never at merge time. See #167.

### 0.9.33's incremental fix can fail open, silently

0.9.33 fixes `update` dropping member-call/`indirect_call` edges into unchanged
targets (#2437/#2438). The new incremental-resolution context calls
`check_graph_file_size_cap(existing_graph_path)` and wraps the block in
`except Exception: _ctx_nodes, _ctx_edges = [], []` — so **on an oversized graph
the fix reverts to the old lossy behaviour with no warning and no rc change**.
At 552 MB against this repo's `GRAPHIFY_MAX_GRAPH_BYTES = 1GB` we are fine; the
protection disappears without announcing itself as the corpus grows.

### Growing the corpus — the ladder, cheapest rung first

The 512 MiB `_MAX_GRAPH_FILE_BYTES` is a **soft, per-file memory-bomb guard**, not
an architectural ceiling: `_max_graph_file_bytes()` honours `GRAPHIFY_MAX_GRAPH_BYTES`
(bytes, or a binary `MB`/`GB` suffix), re-read on every call. This repo sets `1GB`
in `mise.toml [env]`. Measured cost of a parse: **3.7x the file size in peak RSS**
(557,996,319 bytes → 2,068,955,136 RSS, 1.6 s).

⚠️ **mise `[env]` does not reach a bare `graphify …` typed at a shell** — `command -v
graphify` resolves to the raw `mise/installs/…/bin` dir, not a shim. Use
`mise exec -- graphify explain …` while the aggregate is above the stock default.

Raising the cap is a **bridge, never a strategy** — a cap raised once per ingestion
is a ratchet. Since #120 removed the superlinear `O(sources x edges x len(prefix))`
term, growth is **linear in ingested bytes**, which makes *what* we ingest the only
lever that still matters. In order:

1. **Ingestion intent** — do not pay AST for a repo pinned to track a version.
   Measured: the 13 toolchain pins are **266 MB, 49%** of all sub-graph bytes
   (`codex` alone 133 MB) against `graphify`'s 11 MB. See #123, #81, and
   `docs-mirror-is-the-ingestion-path`: *never pin a tool's own repo `kind = code`
   to get its docs.*
2. **`kind = docs`** — skips a guaranteed-empty AST pass over a docs mirror.
3. **`scope = study`** — fully ingested, routed to `study-graph.json`, out of the
   ranked corpus.
4. **Federate (#130) or push to a graph DB** — `push_to_neo4j()` /
   `push_to_falkordb()` / `--push <uri>` are native. Measured 2026-08-03: the merged
   aggregate has **0 cross-source edges of 815,481** across 40 namespaces
   (control-armed — an injected crossing moves the count to 1), because
   `merge-graphs` namespaces each input before `compose`. So federation costs
   nothing in recall. It is still last: it is a retrieval rewrite, while rung 1 is a
   manifest field.

## Work memory (the self-learning loop) — USE IT

Two verbs turn query outcomes into durable, graph-aware lessons. Record load-bearing
research findings here so the corpus improves itself.

- **`graphify save-result`** → appends a Q&A record to `graphify-out/memory/`.
  `--question` (req) · `--answer`/`--answer-file` · `--type query|path_query|explain`
  · `--nodes L1 L2 …` (cited node labels) · `--outcome useful|dead_end|corrected` ·
  `--correction TEXT` (with `corrected`). One record per meaningful result.
- **`graphify reflect`** → aggregates `memory/` into a **deterministic** (no-LLM)
  lessons doc `graphify-out/reflections/LESSONS.md`. `--half-life-days N` (default 30;
  signal weight halves) · `--min-corroboration N` (default 2 distinct `useful` to
  PREFER a node). With `--graph`, groups lessons by community, drops stale nodes, and
  writes the work-memory overlay **`.graphify_learning.json`** tagging nodes
  preferred/tentative/contested (recency-weighted, with provenance); `explain`/`query`
  then surface a "Lesson:" hint, flagged "code changed — re-verify" when the source
  moved on.
- **Corrects** the prior "reflect artifact unconfirmed / LESSONS.md refuted" note —
  verified against the installed **0.9.23** CLI: `reflect` definitively writes
  `reflections/LESSONS.md`.
- **Version-gated (0.9.24+, NOT in installed 0.9.23; control-armed 2026-07-22):**
  `reflect --if-stale` (no-op when LESSONS.md newer than every input) and
  `extract --dedup-llm` (LLM tiebreaker for 75–92 Jaro-Winkler entity pairs). Bump
  the `graphifyy` pin before relying on either.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the tool (source/docs/issues #2076 #857).
