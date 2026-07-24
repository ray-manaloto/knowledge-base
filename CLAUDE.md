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

## Tool currency

`currency.toml` declares what to keep current; `kb_setup.currency` is the shared
engine (dotfiles consumes the same package). Six steps: **1** in-sync check,
**2–3** new version + release notes, **4** tracked-issue movement, **5** the
AskUserQuestion interview, **6** a committed report under `docs/currency/`.

```bash
mise run kb-currency-check    # step 1 only — offline, ~10ms, silent when clean
mise run kb-currency          # the full loop; writes docs/currency/
```

- **Step 1 is the new part.** Bumps were already covered (Renovate,
  `mise outdated --bump`); what nothing checked was whether the binary a shell
  actually reaches matches the pin, and whether the *installed* version built
  `graphify-out/`. It caught a live defect on day one: `MISE_ENV_CACHE=1` had a
  stale `pipx-graphifyy/0.9.23/bin` on PATH ahead of the mise shims.
- **graphify stamps no version into its own output** — `export.to_json()` writes
  only `built_at_commit` — so `kb-build` writes `graphify-out/.currency-stamp.json`
  recording the version that ACTUALLY RAN (never the pin, which would launder
  drift). A rebuild that bypasses `kb-build` is detected via a **content
  fingerprint** (`size:mtime_ns`) and reports *version unknown*, never a false
  green. It deliberately does NOT key off `built_at_commit`: that is the git HEAD,
  so every rebuild at one commit writes the same value — and rebuilding repeatedly
  at one commit is the normal rhythm, which made the old check almost never able
  to fire while claiming it could.
- **`extra_probes` checks the install, not the config.** Two files agreeing that
  `extras = ["all"]` says nothing about whether the extra delivered anything, so
  the config also names packages that must be present. It is author-chosen on
  purpose: `graspologic`/`leidenalg`/`igraph` auto-skip by PEP 508 marker on
  Python 3.14 (the accepted Louvain fallback), so demanding every extra would
  report drift that is not drift.
- **Step 5 can never live in a hook.** A hook is a shell command; only the model
  can call `AskUserQuestion`. The SessionStart hook therefore runs step 1 only and
  is **silent unless something drifted** — always exiting 0, because a session must
  not be blocked over a version pin.
- **An unambiguous bump may apply itself**, where unambiguous means all six gates
  pass: patch-level · PyPI latest has a matching GitHub tag · no breaking marker ·
  extras unchanged · no tracked issue moved · step 1 green. It **fails closed** —
  anything unreadable is ambiguity, not consent. PyPI is the installable truth
  (mise installs from it); GitHub is only the narrative.

## Layout

| Path | Purpose |
|---|---|
| `sources/*.manifest` | github-repo pins (url+SHA); the clone `sources/<name>/` is gitignored, re-fetched on build. |
| `sources/media/` | Vendored non-refetchable sources (video transcripts, docs, PDFs) — committed. |
| `sources/extractions/*.json` | Committed host-agent doc/media extraction chunks (not free to regenerate). |
| `graphify-out/` | `graph.json` is DERIVED — **gitignored**, rebuilt via `kb-build` (at aggregate scale 119MB+ exceeds git/GitHub limits; consumers query via `kb-serve` MCP or a pushed graph DB, not a git blob). Committed: **only `memory/`** (authored work-memory). `manifest.json`, `.graphify_labels.json`, and all views (wiki/graphml/svg/obsidian/report) are derived — regenerable via `kb-build`/`kb-artifacts`. |
| `python/` | `kb_setup` (build/update/artifacts/manifest/chunks/env — thin helpers, zero-bash-logic) + `kb_setup.currency`, the tool-currency engine dotfiles also depends on. |
| `currency.toml` | Per-tool currency config (`[tool.<name>]`): pin, extras, source manifest, build stamp, tracked issues. |
| `docs/currency/` | Committed run log: `README.md` (one row per run) + `runs/<date>-<tool>.md` (detail, only when a run found something). |
| `.claude/workflows/` | Saved Claude workflows the skills compose — `kb-extract.js` (host-agent extraction fan-out). |
| `tests/` | Pytest (`uv run pytest tests/`); config in the root `pyproject.toml`. |
| `mise.toml` | Tool pins + tasks: `kb-build`/`kb-update`/`kb-query`/`kb-serve`/`kb-add`/`kb-manifest-add`/`kb-assemble`/`kb-validate-chunks`/`kb-artifacts`/`kb-ensure-deps`. |
| `pyproject.toml` | The ONE python config (repo root): `[project]` + ruff (`select=ALL`) + ty + pytest. `uv run` uses it for `python/src` AND `tests/`. |
| `hk.pkl` | Git-hook lint: ruff/ty (python), taplo (toml), rumdl (md), gitleaks (secrets), typos, pkl, hygiene + `no-lint-skip`. All logic in `kb_setup` (zero-bash). |
| `docs/graphify-reference.md` | Expert operational reference for graphify itself. |
| `.claude/` | graphify skill + project-scoped settings/hooks. |

## Stack conventions

- **mise-first**: tools pinned in `mise.toml`; use mise binaries, not `npx`.
- **uv for Python**: `uv run …` from the repo root (single root `pyproject.toml`).
- **Zero bash**: no `.sh` scripts, no inline shell in hk.pkl/mise.toml — every check is
  `kb_setup` python invoked via `uv run kb-setup <cmd>` / a mise task.
- **hk for hooks**: `mise run lint` (read-only ≡ CI); `mise run fmt` to fix.
- **Exact pins**: no floating ranges; Renovate-friendly.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:

- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
