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
  on v8 — #2076, returns prose → 0 nodes**). **With no key, pass 3 falls to the
  HOST AGENT** — the running Claude Code session dispatches `general-purpose`
  subagents (the `/graphify` skill's Step 3B) that emit graph JSON. This is the
  only no-key prose path here.
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
- **Labeling** names communities via LLM (`graphify label`, batches ~100/call). With
  no key it's **host-agent** (skill Step 5): read each community's node labels, write
  a 2-5 word name → `graphify-out/.graphify_labels.json` (keyed to community ids).
  Unlabeled communities ("Community N") cripple the wiki — always label.

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

## Work memory

`save-result`/`save_query_result` logs query outcomes (`useful|dead_end|corrected`)
→ `graphify reflect` aggregates. (reflect's exact artifact is unconfirmed — the
"LESSONS.md synthesis" claim was refuted in research.)

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the tool (source/docs/issues #2076 #857).
