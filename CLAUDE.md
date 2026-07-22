# knowledge-base — shared research substrate for Claude Code agents

A mise/hk/uv project whose single purpose is to be the **knowledge graph any
Claude Code agent connects to**: add research sources, query the graph, and use
every other graphify feature. Built on
[graphify](https://github.com/Graphify-Labs/graphify) (local, deterministic AST
parsing; every edge tagged EXTRACTED/INFERRED; no vector store).

Claude-only by design — one self-contained `CLAUDE.md`, no `AGENTS.md` stub.
`.claude/CLAUDE.md` holds graphify's skill pointer (auto-loaded).

## Invariants (do NOT violate)

1. **graphify is PROJECT-SCOPED, never global.** Install only with
   `graphify install --project`. Never bare `graphify install` (mutates
   `~/.claude`), never `graphify extract --global` / `graphify global add`
   (shared mutable machine state → non-reproducible, collides across hosts).
   The graph lives in this repo's `graphify-out/`.
2. **This repo edits only PROJECT settings.** It never touches `~/.claude` or
   any global/system/user config.
3. **Inputs are reproducible.** Every source is committed — either the content
   itself, or a `sources/<name>.manifest` pointing at a pinned upstream commit
   re-cloned at build time. `graphify-out/graph.json` is gitignored and rebuilt
   from sources.
4. **One MCP server per graph.** The server binds to an ABSOLUTE `graph.json`
   path (`mise run kb-serve`), so multiple graphify projects on one host never
   collide.
5. **Every source is ingested THROUGH graphify (and its extensions), never an
   ad-hoc fetch.** `graphify clone`/`add`/`extract` are the entry points (see the
   `kb-curator` skill MANDATE). `curl`/WebFetch is a fallback only when graphify
   cannot reach a source, and even then the content is routed into the graph. One
   ingestion path = uniform provenance + freshness + reproducibility.

## The two verbs

graphify's surface splits by transport AND by liveness:

| verb | transport | needs a live agent? | how |
|---|---|---|---|
| **query** | read-only MCP server, or the CLI | no — headless/always-on | `mise run kb-query -- "<question>"`; or `mise run kb-serve` + connect over MCP |
| **add** | local CLI + host-agent extraction | **yes** — the connecting agent IS the extraction LLM | see below |

### Querying (any consumer, e.g. the dotfiles repo)

- CLI: `mise run kb-query -- "how does X work?"` (deterministic BFS/DFS, no LLM,
  source-cited). Also `graphify path "A" "B"`, `graphify explain "X"`,
  `graphify god-nodes`.
- MCP: `mise run kb-serve` starts the read-only server pinned to this graph.
  A consumer repo reaches it via `mcp2cli` (one-off) or a `.mcp.json`
  registration (frequent use). All MCP tools are graph reads and spend **zero
  LLM tokens** — the LLM cost is entirely at build/extraction time.

### Adding sources — Claude Code ONLY, and every graphify op is a mise task

Two hard mandates (Ray, 2026-07-22, machine-enforced):

1. **Never run graphify by hand — drive it through a mise task.** `kb-add` /
   `kb-build` / `kb-update` / `kb-merge` / `kb-label` / `kb-transcribe` / `kb-query` /
   `kb-remember` / `kb-reflect` / `kb-artifacts`. The PreToolUse guard
   `kb_setup.hook_guard` (wired in `.claude/settings.json`) DENIES a raw `graphify …`
   / `_merge_docs.py` / graphify-bundled-python call and prints the task to use. See
   `.claude/skills/kb-curator` for the full workflow.
2. **All LLM work is Claude — NEVER Gemini or any auto-detected key.** A global
   `GEMINI_API_KEY` (a mise secret) exists, so this is NOT "no API key" — it is a
   *forbidden* key: `kb_setup.graphify_env.clean_env()` strips every non-Claude
   backend trigger (Gemini/Google/OpenAI/Kimi/DeepSeek/Azure/**Bedrock via
   `AWS_REGION`**/Ollama) from every graphify subprocess, so graphify's
   `detect_backend()` can never pick one. `ANTHROPIC_*` is kept (the Claude path).

Concretely:
- **Code repo** (common): add `sources/<name>.manifest` (url+ref+commit);
  `mise run kb-build` clones at the pinned SHA + AST-extracts (**free, no LLM**) +
  replays committed doc chunks. `mise run kb-update -- <name>` advances to upstream.
- **Prose (docs/URLs/blogs)**: `mise run kb-add -- <url>` fetches to `./raw`; semantic
  extraction is the **Claude host agent** (a Workflow fan-out of `general-purpose`
  subagents that read each raw file → `{nodes,edges}` → one combined chunk in
  `sources/extractions/`), then `mise run kb-merge -- <chunk>`. This is the only LLM
  path and it is Claude — graphify's `claude-cli` backend is broken (#2076,
  prose-wrapped JSON), Ollama/other backends are stripped.
- **Video**: `mise run kb-add -- <yt-url>` then `mise run kb-transcribe -- raw/<yt>.m4a`
  (local faster-whisper — no key, no LLM), then host-agent extract the transcript.
- **Label** after every merge: `mise run kb-label` — deterministic hub labels (no LLM,
  Gemini-free). Do not expect LLM-named communities (claude-cli #2076).

## Quick start

```bash
mise install                                  # tools (python, uv, hk, pkl, typos, graphify, ffmpeg)
graphify install --project                    # project-scoped skill + graphify-out/
mise run kb-build                             # reproduce graph.json from committed inputs (no LLM)
mise run kb-query -- "what does this corpus cover?"
mise run kb-serve                             # read-only MCP server for other agents
mise run kb-artifacts                         # regenerate all derived outputs (wiki/graphml/svg/…)
mise run kb-update -- <name>                  # advance a github source to latest + re-extract
mise run kb-reflect                           # aggregate work-memory -> reflections/LESSONS.md + overlay
mise run lint && mise run test                # gates
```

**Adding sources is automated + self-improving** via the `kb-curator` skill
(`.claude/skills/kb-curator/`): register → ingest → merge → cluster → label →
**always** `kb-remember` (record the outcome) + `kb-reflect` (aggregate lessons),
so the corpus gets smarter every ingestion. `sources/REGISTRY.md` is the durable
source backlog. See `docs/graphify-reference.md` for the graphify mental model.

Deep graphify operational reference: `docs/graphify-reference.md`.

## Layout

| Path | Purpose |
|---|---|
| `sources/*.manifest` | github-repo pins (url+SHA); the clone `sources/<name>/` is gitignored, re-fetched on build. |
| `sources/media/` | Vendored non-refetchable sources (video transcripts, docs, PDFs) — committed. |
| `sources/extractions/*.json` | Committed host-agent doc/media extraction chunks (not free to regenerate). |
| `graphify-out/` | `graph.json` is DERIVED — **gitignored**, rebuilt via `kb-build` (at aggregate scale 119MB+ exceeds git/GitHub limits; consumers query via `kb-serve` MCP or a pushed graph DB, not a git blob). Committed: **only `memory/`** (authored work-memory). `manifest.json`, `.graphify_labels.json`, and all views (wiki/graphml/svg/obsidian/report) are derived — regenerable via `kb-build`/`kb-artifacts`. |
| `python/` | `kb_setup` (build/update/artifacts/env — thin helpers, zero-bash-logic). |
| `tests/` | Pytest (`uv run --project python pytest tests/`). |
| `mise.toml` | Tool pins + tasks: `kb-build`/`kb-update`/`kb-query`/`kb-serve`/`kb-add`/`kb-artifacts`/`kb-ensure-deps`. |
| `hk.pkl` | Git-hook lint (typos, pkl). |
| `docs/graphify-reference.md` | Expert operational reference for graphify itself. |
| `.claude/` | graphify skill + project-scoped settings/hooks. |

## Stack conventions

- **mise-first**: tools pinned in `mise.toml`; use mise binaries, not `npx`.
- **uv for Python**: `uv run --project python …` (never `--directory`).
- **hk for hooks**: `mise run lint` (read-only ≡ CI); `mise run fmt` to fix.
- **Exact pins**: no floating ranges; Renovate-friendly.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
