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
| **MCP server** | `graphify-mcp <abs graph.json>` | stdio/http; **10 read-only tools**, zero LLM tokens; `project_path` routes per-project; NO add/mutate tool |
| analysis | `god-nodes` / `benchmark` / `diagnose multigraph` | stdout |

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
