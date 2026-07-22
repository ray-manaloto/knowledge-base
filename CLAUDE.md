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

### Adding sources (host-agent extraction — no API key, no Ollama)

Adding is inherently an **agent-in-repo** operation: graphify exposes **no "add"
tool over MCP** (the server is read-only — confirmed from its own graph:
`serve.py`'s neighbors are all read/query helpers). With no provider key set,
**semantic extraction falls to the host agent itself** — this Claude Code session
dispatches `general-purpose` subagents that read each source and emit graph JSON,
then merges. Code is extracted structurally (AST) with **no LLM at all**.

The python add-path graphify already exposes (wrappable):
`graphify.ingest.ingest(url, target_dir)` fetches a URL → graphify-ready file in
`sources/`; `graphify.extract.extract()` builds. CLI equivalents:
`graphify clone <url>` (GitHub repo), `graphify add <url>`, `graphify extract <path>`.

- **A code repo** (common case): clone under `sources/`, add a manifest, rebuild:
  ```bash
  git clone --branch <ref> <url> sources/<name>     # or graphify clone <url>
  mise run kb-build                                  # AST — no LLM, no key
  ```
  For a first build of a fresh corpus use
  `graphify extract sources/<name> --code-only --out .` (headless AST → repo-root
  `graphify-out/`). `mise run kb-build` (`graphify update`) refreshes an existing
  graph.
- **A URL / doc / paper**: `mise run kb-add -- <url>` fetches into `sources/` and
  updates the graph. Prose triggers host-agent semantic extraction (this
  session's subagents), so run it from a Claude Code session, not a bare shell.
- **Never** prompt for or block on `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` — a
  code-only corpus needs no key, and prose extraction uses the host agent.

## Quick start

```bash
mise install                                  # tools (python, uv, hk, pkl, typos, graphify)
graphify install --project                    # project-scoped skill + graphify-out/
graphify extract sources/<name> --code-only --out .   # first build (code, AST, free)
mise run kb-query -- "what does this corpus cover?"
mise run kb-serve                             # read-only MCP server for other agents
mise run lint && mise run test                # gates
```

## Layout

| Path | Purpose |
|---|---|
| `sources/` | The corpus. Committed content or `<name>.manifest` pointers (pinned SHA); vendored clones are gitignored + rebuilt. |
| `graphify-out/` | Generated graph (`graph.json`, report, html). Gitignored, rebuilt from sources. |
| `python/` | `kb_setup` package (uv-managed; thin helpers only, zero-bash-logic). |
| `tests/` | Pytest suite (`uv run --project python pytest tests/`). |
| `mise.toml` | Tool pins + tasks (`lint`, `test`, `kb-build`, `kb-query`, `kb-serve`, `kb-add`). |
| `hk.pkl` | Git-hook lint config (typos, pkl). |
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
