# knowledge-base — shared research substrate for Claude Code agents

A mise/hk/uv project whose single purpose is to be the **knowledge graph any
Claude Code agent connects to**: add research sources, query the graph, and use
every other graphify feature. Built on
[graphify](https://github.com/Graphify-Labs/graphify) (local, deterministic AST
parsing; every edge tagged EXTRACTED/INFERRED; no vector store).

`AGENTS.md` DOES exist (tracked, 51 lines, codex's minimum) — a sibling, not an
`@import` stub, so no budget counts it. `.claude/CLAUDE.md` is auto-loaded.

## Invariants (do NOT violate)

1. **graphify is PROJECT-SCOPED, never global.** Never run `graphify install`
   by hand — the hook denies it even with `--project`; use
   `mise run kb-skill-refresh`. Never `graphify extract --global` /
   `graphify global add` (shared mutable machine state → non-reproducible,
   collides across hosts). The graph lives in this repo's `graphify-out/`.
2. **This repo edits only PROJECT settings.** It never touches `~/.claude` or
   any global/system/user config.
3. **Inputs are reproducible.** Every source is committed — either the content
   itself, or a `sources/<name>.manifest` pointing at a pinned upstream commit
   re-cloned at build time. `graphify-out/graph.json` is gitignored and rebuilt
   from sources.
4. **TWO graph servers, two names** (#668): `graphify` = hosted (23 tools we
   lack); **`kb`** = `uv run kb-setup serve`, the 359k aggregate + PR tools
   hosted lacks. One shared name BROKE codex. Why: `docs/setup-inventory.md`.
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
  graph (**11,330** nodes vs **359,026** aggregate — 99% is code AST crowding
  prose out; re-derived 2026-09-02 from the first green build since the N0 resync, both STALE ON SIGHT); **`--idf`** ranks the
  RETURNED SET by BM25/IDF — best arm, natural recall 1/8 -> 3/8 -> 5/8 (#12
  P0/P1). NOT unscored BFS — it ranks SEEDS by IDF; evidence in `mise.toml`.
- MCP: `mise run kb-serve` starts the read-only server pinned to this graph.
  A consumer repo reaches it via `mcp2cli` (one-off) or a `.mcp.json`
  registration (frequent use). All MCP tools are graph reads and spend **zero
  LLM tokens** — the LLM cost is entirely at build/extraction time.

### Adding sources — Claude Code ONLY, and every graphify op is a mise task

Two hard mandates (Ray, 2026-07-22, machine-enforced):

1. **Never run graphify by hand — drive it through a mise task.** `kb-add` /
   `kb-build` / `kb-prose` / `kb-update` / `kb-merge` / `kb-label` / `kb-transcribe` /
   `kb-query` / `kb-remember` / `kb-reflect` / `kb-artifacts`. The PreToolUse guard
   `kb_setup.hook_guard` (wired in `.claude/settings.json`) DENIES a raw `graphify …`
   / `_merge_docs.py` / graphify-bundled-python call and prints the task to use. See
   `.claude/skills/kb-curator` for the full workflow.
2. **Corpus LLM work runs on `claude-cli` or `openai-cli`, chosen by an EXPLICIT
   `--backend`** (Ray, 2026-08-25) — with one known gap: `ANTHROPIC_API_KEY` is a
   deliberate, test-locked exception letting `claude-cli` auto-select via
   `detect_backend()`'s priority tuple instead (`do-not.md` #4; #685/#686).
   Every OTHER key-detected backend stays forbidden: a global `GEMINI_API_KEY`
   (a mise secret) exists, so `clean_env()` strips every non-Claude key
   trigger (Gemini/Google/OpenAI/Kimi/DeepSeek/Azure/**Bedrock via `AWS_REGION`**/Ollama).

Concretely:

- **Code repo** (common): add `sources/<name>.manifest` (url+ref+commit);
  `mise run kb-build` clones at the pinned SHA + AST-extracts (**free, no LLM**) +
  replays committed doc chunks. `mise run kb-update -- <name>` advances to upstream.
- **Prose (docs/URLs/blogs)**: `mise run kb-add -- <url>` fetches to `./raw`; semantic
  extraction is the **Claude host agent** (a Workflow fan-out of `general-purpose`
  subagents that read each raw file → `{nodes,edges}` → one combined chunk in
  `sources/extractions/`), then `mise run kb-merge -- <chunk>`.
- **Video**: `mise run kb-add -- <yt-url>` then `mise run kb-transcribe -- raw/<yt>.m4a` (local faster-whisper — no key, no LLM), then host-agent extract the transcript.
- **Label** after every merge: `mise run kb-label` — deterministic hub labels (no LLM, Gemini-free); LLM-named communities via claude-cli remain untested (#2076).

## Quick start

```bash
mise install && mise deps                     # tools + locked Python runtime (Graphify SDK/CLI)
mise run kb-skill-refresh                     # install + repair project-scoped skill + graphify-out/
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

## Tool currency

`currency.toml` declares what to keep current; `kb_setup.currency` is the shared
engine (dotfiles consumes the same package). Six steps: **1** in-sync check,
**2–3** new version + release notes, **4** tracked-issue movement, **5** the
AskUserQuestion interview, **6** a committed report under `docs/currency/`.

```bash
mise run kb-currency-check    # step 1: offline ~10ms, silent when clean; + pin-vs-upstream
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
  report drift that is not drift. **`backend_probes` is its sibling**: not "did an
  extra deliver a package" but "did a declared BACKEND survive the upgrade" —
  `openai-cli` is a patch our FORK carries, and losing it lets extraction fall back
  to the METERED OpenAI API while every version number still agrees.
- **Step 5 can never live in a hook.** A hook is a shell command; only the model
  can call `AskUserQuestion`. The SessionStart hook therefore runs step 1 only and
  is **silent unless something drifted** — always exiting 0, because a session must
  not be blocked over a version pin. Two things it does NOT stay silent about: a
  missing `currency.toml` (silence is this design's "clean", so an absent config
  must announce that step 1 did not run) and an unknown `--tool` (exit 2).
- **An unambiguous bump may apply itself**, where unambiguous means all six gates
  pass: patch-level · latest has a readable GitHub release · no breaking marker ·
  extras unchanged · no tracked issue moved · step 1 green. It **fails closed** —
  anything unreadable is ambiguity, not consent. PyPI is the installable truth
  (mise installs from it); GitHub is only the narrative.
- **"Could not check" is never rendered as green.** Three distinct states, kept
  distinct because collapsing them is how every defect in this engine's review
  happened: DRIFT (checked, disagrees) · SKIP (not applicable here) · OK. A run of
  nothing-but-SKIPs reports *not verifiable here*, never "in sync"; an unreachable
  upstream reports *latest UNKNOWN*, never "current"; a tracked issue whose lookup
  failed blocks gate 5 rather than passing it; and a binary that is simply not
  installed on a host where it *should* be is DRIFT, not SKIP.
- **`mise run kb-currency` always exits 0** and can never serve as a CI gate — an
  out-of-date tool is a signal, not a failure. Read the report, not the rc.

## Layout

| Path | Purpose |
|---|---|
| `sources/*.manifest` | github-repo pins (url+SHA); the clone `sources/<name>/` is gitignored, re-fetched on build. |
| `sources/media/` | Vendored non-refetchable sources (video transcripts, docs, PDFs) — committed. |
| `sources/extractions/*.json` | Committed host-agent doc/media extraction chunks (not free to regenerate). |
| `graphify-out/` | `graph.json` is DERIVED — **gitignored**, rebuilt via `kb-build` (**528 MB measured 2026-09-02**, the fifth re-measure — this figure goes stale; far past git/GitHub limits; consumers query via `kb-serve` MCP or a pushed graph DB, not a git blob). `graph-prose.json` is derived from THAT (by every task that writes `graph.json` — `kb-build`/`kb-merge`/`kb-label` — or `kb-prose` alone): the same graph minus every `_origin=ast` node, which is what `kb-query --prose` reads. Committed: **`memory/`** (authored work-memory) and **`graphify-semantic-slice/`** (retained provider evidence, 5 files, #317) — the two committed subdirectories. A separate, now-removed evidence tree (`graphify-semantic-corpus-chunks/`) went with the rest of the semantic-corpus layer, 2026-08-24 (`docs/archive/README.md`). `manifest.json`, `.graphify_labels.json`, and all views (wiki/graphml/svg/obsidian/report) are derived — regenerable via `kb-build`/`kb-artifacts`. |
| `python/` | `kb_setup` (build/update/artifacts/manifest/chunks/env — thin helpers, zero-bash-logic) + `kb_setup.currency`, the tool-currency engine dotfiles also depends on. |
| `currency.toml` | Per-tool currency config (`[tool.<name>]`): pin, extras, source manifest, build stamp, tracked issues. |
| `docs/currency/` | Committed run log: `README.md` (one row per run) + `runs/<date>-<tool>.md` (detail, only when a run found something). |
| `docs/goals/` · `docs/direction/` | **goals**: committed goal+rider PAIRS, one round each — `*-goal.md` is the ≤4,000-char `/goal` payload (its bytes ARE the artifact, so it is excluded from hk's md builtins), `*-rider.md` the unbounded detail; audit with `kb-goal-check`, record the outcome with `kb-goal-outcome`. **direction**: Ray's directives VERBATIM, the standing brief every round is measured against — `clear-prep` reads the newest one, and until 2026-08-17 nothing did, so a directive could be filed and never consulted. |
| `.claude/workflows/` | Saved Claude workflows the skills compose — `kb-extract.js` (host-agent extraction fan-out). |
| `tests/` | Pytest (`uv run pytest tests/`); config in the root `pyproject.toml`. |
| `mise.toml` | Tool pins + tasks: `kb-build`/`kb-prose`/`kb-update`/`kb-query`/`kb-serve`/`kb-add`/`kb-manifest-add`/`kb-assemble`/`kb-validate-chunks`/`kb-artifacts`/`kb-ensure-deps`/`kb-handoff-check`/`kb-gates`/`kb-session-state`/`kb-session-select` (resolves WHICH sessions a review covers — `--current`/`--sessions`/`--last N`/`--since..--until`; birthtime cross-checked against each transcript's own first record, and it REFUSES rather than returning a partial list)/`kb-session-review-archive` (writes `docs/session-review/runs/<date>-<n>/` from a run's return, verbatim; refuses to overwrite or partially write; regenerates the README)/`kb-goal-check`/`kb-goal-outcome`/`kb-review-receipt`/`kb-skill-score`/`kb-skill-lint`/`kb-distill`/`kb-arms` (mutation arms from a TOML spec — never hand-write the harness, #160)/`kb-attribute-write` (what the transcripts recorded around a tracked file's mtime — built because ELEVEN reproductions across two incidents failed to name the `.codex/config.toml` writer; advisory, and it REFUSES rather than returning an empty list when nothing was EXAMINED)/`kb-affected`/`kb-insights`/`kb-check` (the DEV LOOP: ruff+format+ty+those paths' own tests over named paths, real exit codes — `check` is whole-repo and `kb-gates` is the ship gates, so nothing answered "are these two files clean?" and it got answered 35 times in one session by a pipe that discards the rc)/`hk-test` (a SHIP GATE, in `GATE_TASKS` since 2026-08-19: runs hk's 46 step-defined tests — every one a bad-file/good-file PAIR shipped by a builtin, so it is the only gate that exercises the linters' FAIL direction. NOT a bare `hk test`, which exits 0 whenever it runs nothing — a filter that matches no step, or a config that stopped declaring testable ones; `kb_setup.hk_test` asserts a floor on the count BEFORE reading hk's rc). **`timeout` is declared on the 10 slow tasks** (0 of 75 until 2026-08-19, while `long-running-command-hangs.md` rule 1 named it as the answer to the 7-hour hk wedge), and `lint` writes `HK_TIMING_JSON`/`HK_OUTPUT_FILE` into `.agent/kb/gates/` so a failure has evidence beside its rc. |
| `pyproject.toml` | The ONE Python config and Graphify owner: exact `graphifyy[all]==0.9.53`, installed from OUR FORK by git rev (never plain PyPI — `sources/graphify.manifest` says why), + `msgspec==0.21.1`, isolated exact codegen group, ruff/ty/pytest. `mise [deps.uv]` runs `uv sync --locked`. |
| `hk.pkl` | Git-hook lint: ruff/ty (python), taplo (toml), rumdl (md), gitleaks (secrets), typos, pkl, hygiene + `no-lint-skip`. All logic in `kb_setup` (zero-bash). |
| `docs/graphify-reference.md` | Expert operational reference for graphify itself. |
| `.claude/` | Skills (graphify, kb-curator, goal-engineering, kb-review, tool-currency, orchestrator-routing, clear-prep) + project-scoped settings/hooks/rules. Skills are SCORED by `kb-skill-score` (plugin-eval's static layer, advisory) against the committed baseline in `docs/skills/` — a structure check, not a correctness one, so read the Δ. `kb-review` is the REAL review gate — ONE cold cross-family lens, bounded at 2 rounds, then a receipt BOTH `kb-ship` and `kb-land` refuse without; CodeRabbit is advisory, never blocks. **`agents/` is the standing roster** — 7 subagents: `kb-advisor` (fable) at commitment boundaries; `kb-adversarial-verifier` and `kb-synthesist` (opus) for judgment; `kb-corpus-curator`, `kb-tool-researcher` and `kb-extraction-worker` (sonnet) for execution — those six each declare `model` + `effort`. The 7th, `kb-codex-advisor`, declares NEITHER, and that is deliberate: its reasoning runs inside `codex exec`, pinned there to `--model gpt-5.6-sol` at `xhigh` (both sides, 2026-08-31 — before that the model was inherited from `~/.codex/config.toml`, a file this repo neither owns nor watches). All seven are instructed to query the graph FIRST. **As of Claude Code 2.1.251, `model` frontmatter and an explicit per-spawn model outrank `CLAUDE_CODE_SUBAGENT_MODEL`** — that env var now sets only the default when neither is given (reversed from the prior "env var wins" resolution order; `CHANGELOG.md:62` at tag `v2.1.251`, commit `f1af9b1f4b1fd4c776135381606edada82ef638e`: *"Changed `CLAUDE_CODE_SUBAGENT_MODEL` to set the default subagent model rather than override everything: an agent definition's `model:` and an explicit per-spawn model now take precedence over it"*), so frontmatter is closer to a guarantee than before, not merely a preferred default. |

## Stack conventions

- **mise-first**: tools are pinned in `mise.toml`; Python applications/libraries are locked in `pyproject.toml` + `uv.lock` and synchronized by `[deps.uv]`.
- **uv for Python**: `uv run …` from the repo root (single root `pyproject.toml`).
- **Zero bash**: no `.sh` scripts, no inline shell in hk.pkl/mise.toml — every check is
  `kb_setup` python invoked via `uv run kb-setup <cmd>` / a mise task.
- **hk for hooks**: `mise run lint` (read-only ≡ CI); `mise run fmt` to fix.
- **Exact pins**: no floating ranges; Renovate-friendly.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:

- For codebase questions, first run `mise run kb-query -- "<question>"` when graphify-out/graph.json exists (`--prose` for questions about the DOCUMENTS). Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts — those two are read-only, have no task equivalent, and are allowed direct. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `mise run kb-watch` to keep the AGGREGATE graph current (AST-only, no API cost). Never bare `graphify update .` — `kb_setup.hook_guard` denies it, and a root-path extraction would try to overwrite the merged graph.
