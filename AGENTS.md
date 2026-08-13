# knowledge-base — shared research substrate for Codex agents

A mise/hk/uv project whose single purpose is to be the **knowledge graph any
Codex agent connects to**: add research sources, query the graph, and use
every other graphify feature. Built on
[graphify](https://github.com/Graphify-Labs/graphify) (local, deterministic AST
parsing; every edge tagged EXTRACTED/INFERRED; no vector store).

Codex-only by design — one self-contained `AGENTS.md`, no `AGENTS.md` stub.
`.Codex/AGENTS.md` holds graphify's skill pointer (auto-loaded).

## Invariants (do NOT violate)

1. **graphify is PROJECT-SCOPED, never global.** Install only with
   `graphify install --project`. Never bare `graphify install` (mutates
   `~/.Codex`), never `graphify extract --global` / `graphify global add`
   (shared mutable machine state → non-reproducible, collides across hosts).
   The graph lives in this repo's `graphify-out/`.
2. **This repo edits only PROJECT settings.** It never touches `~/.Codex` or
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

- CLI: `mise run kb-query -- "how does X work?"` (deterministic, no LLM,
  source-cited). Asking about the DOCUMENTS? **`--prose`** reads the prose-only
  graph (2,553 nodes, not 140,295 of which 138k are code AST crowding prose out
  of the budget; both re-derived 2026-08-02); **`--idf`** also ranks the
  RETURNED SET by BM25/IDF — best arm, natural recall 1/8 -> 3/8 -> 5/8 (#12
  P0/P1). NOT unscored BFS — it ranks SEEDS by IDF; evidence in `mise.toml`.
- MCP: `mise run kb-serve` starts the read-only server pinned to this graph.
  A consumer repo reaches it via `mcp2cli` (one-off) or a `.mcp.json`
  registration (frequent use). All MCP tools are graph reads and spend **zero
  LLM tokens** — the LLM cost is entirely at build/extraction time.

### Adding sources — Codex ONLY, and every graphify op is a mise task

Two hard mandates (Ray, 2026-07-22, machine-enforced):

1. **Never run graphify by hand — drive it through a mise task.** `kb-add` /
   `kb-build` / `kb-prose` / `kb-update` / `kb-merge` / `kb-label` / `kb-transcribe` /
   `kb-query` / `kb-remember` / `kb-reflect` / `kb-artifacts`. The PreToolUse guard
   `kb_setup.hook_guard` (wired in `.Codex/settings.json`) DENIES a raw `graphify …`
   / `_merge_docs.py` / graphify-bundled-python call and prints the task to use. See
   `.Codex/skills/kb-curator` for the full workflow.
2. **All LLM work is Codex — NEVER Gemini or any auto-detected key.** A global
   `GEMINI_API_KEY` (a mise secret) exists, so this is NOT "no API key" — it is a
   *forbidden* key: `kb_setup.graphify_env.clean_env()` strips every non-Codex
   backend trigger (Gemini/Google/OpenAI/Kimi/DeepSeek/Azure/**Bedrock via
   `AWS_REGION`**/Ollama) from every graphify subprocess, so graphify's
   `detect_backend()` selects only the permitted path. `ANTHROPIC_*` is kept.

Concretely:

- **Code repo** (common): add `sources/<name>.manifest` (url+ref+commit);
  `mise run kb-build` clones at the pinned SHA + AST-extracts (**free, no LLM**) +
  replays committed doc chunks. `mise run kb-update -- <name>` advances to upstream.
- **Prose (docs/URLs/blogs)**: `mise run kb-add -- <url>` fetches to `./raw`; semantic
  extraction is the **Codex host agent** (a Workflow fan-out of `general-purpose`
  subagents that read each raw file → `{nodes,edges}` → one combined chunk in
  `sources/extractions/`), then `mise run kb-merge -- <chunk>`. This is the only LLM
  path and it is Codex — graphify's `Codex-cli` backend is broken (#2076,
  prose-wrapped JSON), Ollama/other backends are stripped.
- **Video**: `mise run kb-add -- <yt-url>` then `mise run kb-transcribe -- raw/<yt>.m4a`
  (local faster-whisper — no key, no LLM), then host-agent extract the transcript.
- **Label** after every merge: `mise run kb-label` — deterministic hub labels (no LLM,
  Gemini-free). Do not expect LLM-named communities (Codex-cli #2076).

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
(`.Codex/skills/kb-curator/`): register → ingest → merge → cluster → label →
`kb-remember` (record the outcome) → `kb-reflect` (aggregate lessons).
Every successful ingestion completes that sequence,
so the corpus gets smarter every ingestion. `sources/REGISTRY.md` is the durable
source backlog. See `docs/graphify-reference.md` for the graphify mental model.

## Tool currency

`currency.toml` declares what to keep current; `kb_setup.currency` is the shared
engine (dotfiles consumes the same package). Six steps: **1** in-sync check,
**2–3** new version + release notes, **4** tracked-issue movement, **5** the
AskUserQuestion interview, **6** a committed report under `docs/currency/`.

```bash
mise run kb-currency-check    # step 1: offline ~10ms, silent when clean; + pin-vs-upstream
mise run kb-currency          # the full loop; writes docs/currency/
```

Currency completion means the effective executable, exact pin, lock, source
manifest/checkout, generated skill stamp, and post-build artifact stamp agree.
`kb-build` writes `graphify-out/.currency-stamp.json` from the executable that
actually ran. `extra_probes` checks installed capabilities rather than trusting
configuration text. Upstream lookup failures and non-applicable probes remain
distinct from clean results. `mise run kb-currency` is report-producing and may
exit zero with findings, so read its report; use the repository gates for a
blocking result. A hook may run the cheap offline check, while human decisions
about ambiguous releases stay in the explicit currency workflow.

## Layout

| Path | Purpose |
|---|---|
| `sources/*.manifest` | github-repo pins (url+SHA); the clone `sources/<name>/` is gitignored, re-fetched on build. |
| `sources/media/` | Vendored non-refetchable sources (video transcripts, docs, PDFs) — committed. |
| `sources/extractions/*.json` | Committed host-agent doc/media extraction chunks (not free to regenerate). |
| `graphify-out/` | Gitignored derived graphs, labels, manifests, and views. Rebuild with `kb-build`; regenerate views with `kb-artifacts`. Only authored `memory/` is durable input. |
| `python/` | `kb_setup` (build/update/artifacts/manifest/chunks/env — thin helpers, zero-bash-logic) + `kb_setup.currency`, the tool-currency engine dotfiles also depends on. |
| `currency.toml` | Per-tool currency config (`[tool.<name>]`): pin, extras, source manifest, build stamp, tracked issues. |
| `docs/currency/` | Committed run log: `README.md` (one row per run) + `runs/<date>-<tool>.md` (detail, only when a run found something). |
| `docs/goals/` | Committed goal+rider PAIRS — one round of agent work each. `*-goal.md` is the ≤4,000-char `/goal` payload (its bytes ARE the artifact, so it is excluded from hk's md builtins); `*-rider.md` is the unbounded detail. Audit with `kb-goal-check`; record how a round went with `kb-goal-outcome`. |
| `.Codex/workflows/` | Saved Codex workflows the skills compose — `kb-extract.js` (host-agent extraction fan-out). |
| `tests/` | Pytest (`uv run pytest tests/`); config in the root `pyproject.toml`. |
| `mise.toml` | Exact tool pins and the task interface. Use task help/listing as the current command inventory; `kb-check` is focused development validation and `kb-gates` is the ship gate. |
| `pyproject.toml` | The ONE python config (repo root): `[project]` + ruff (`select=ALL`) + ty + pytest. `uv run` uses it for `python/src` AND `tests/`. |
| `hk.pkl` | Git-hook lint: ruff/ty (python), taplo (toml), rumdl (md), gitleaks (secrets), typos, pkl, hygiene + `no-lint-skip`. All logic in `kb_setup` (zero-bash). |
| `docs/graphify-reference.md` | Expert operational reference for graphify itself. |
| `.Codex/` | Project-scoped skills, hooks, rules, and the standing agent roster. `kb-skill-score` is advisory structure analysis; `kb-review` produces the required cold-review receipt. Agent profiles query the graph first. |

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

- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
