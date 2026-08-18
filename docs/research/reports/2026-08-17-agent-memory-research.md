# Session-review as configuration? — ranked synthesis (2026-08-17)

Synthesist pass over one marketplace scan (2,281 plugins) + six source-read passes
(claude-vault, longhand, claude-performance, vardoger, skillers, claude-activity-tracker),
plus my own first-party probe of the shipped `claude` binary v2.1.234.

## 1. THE ANSWER IN THREE SENTENCES

**Partly — and much less than the descriptions promise.** The *capture* half is already
solved and costs nothing: Claude Code writes every prompt, tool call, tool result and
per-message `usage` block to `~/.claude/projects/**/*.jsonl` (measured: **229 sessions,
981 MB across all projects on this machine**), so nothing needs to be recorded that isn't
already recorded. Exactly one candidate survives source-reading as an adoptable
off-the-shelf component — **`longhand==1.0.1`** (PyPI, MIT, local SQLite, deterministic
no-LLM session-outcome classifier and problem→fix episode extractor) — and it buys us the
*store* plus a generic analysis layer, not the repo-specific interrogation. Every
repo-specific question `kb-session-reflect` exists to answer (which hand-run commands a
mise task already owns, per-directive violation *rates*, graph-first ratio, cost per round)
remains SQL/python we write: **session review is code, with a configurable substrate.**

## 2. RECOMMENDED DAY-1 MVP

The single cheapest thing to turn on tomorrow, in order:

```toml
# pyproject.toml — isolated group, does not touch the runtime deps
[dependency-groups]
sessions = ["longhand==1.0.1"]
```

```bash
uv sync --locked
# redaction is OPT-IN and OFF by default; the store keeps every credential
# that ever appeared in a transcript. Do this BEFORE the first ingest.
LONGHAND_DATA_DIR=.agent/longhand uv run longhand config --set redact.enabled=true
LONGHAND_DATA_DIR=.agent/longhand uv run longhand ingest --skip-analysis
LONGHAND_DATA_DIR=.agent/longhand uv run longhand doctor --json
```

Then a `kb-sessions` mise task wrapping `kb_setup.sessions` (zero-bash), which imports
`LonghandStore` as a library and answers our questions as SQL over `events`.

Hard constraints on that MVP, all source-verified:

- **Never run `longhand setup` / `longhand hook-install`.** `setup_commands.py:29-31`
  hardcodes `Path.home()/'.claude'/'settings.json'` and installs a `com.longhand.reconcile`
  macOS LaunchAgent — `do-not.md` #11. Nothing in the ingest path needs it; the hooks are
  just `longhand ingest-session` reading `transcript_path` from stdin, so register them in
  **this repo's** `.claude/settings.json` if you want them at all.
- **`--skip-analysis` on the first run** avoids ChromaDB's ~80 MB ONNX model download
  ("zero API calls" is not literally zero network). `.agent/longhand` must be gitignored
  (`.agent/` already is).
- **`longhand` has no cost/token columns** — usage survives only inside its `raw_json`
  column and must be `json_extract`ed. That is one SQL expression, not a blocker.

**On `OTEL_LOG_RAW_API_BODIES=file:<dir>`** — the brief invited this answer, so here is the
verified fact and then the recommendation against it. It is **real and first-party**: in the
shipped binary v2.1.234, `RSS(e)` parses a leading `file:` prefix into
`{mode:"file", dir: resolve(...)}`, and `jjp()` writes
`<request_id>.request.json` / `<request_id>.response.json` into that dir via
`writeFile` (with `mkdir -p` on ENOENT), gated only on the env var being set — **no
exporter, endpoint or `CLAUDE_CODE_ENABLE_TELEMETRY` required for the file write**
(control arm on the probe: `OTEL_LOG_RAW_API_BODIES` → 6 string hits, `OTEL_LOGS_EXPORTER`
→ 15, `ZZQQXX_NONEXISTENT` → 0). It is also in the `Zpu` settings-tier list, so it is
settable from `.claude/settings.json`'s `env` block rather than a shell profile.

**Do not turn it on anyway.** Three reasons: (1) it duplicates data we already have — the
JSONL transcripts carry the same turns *plus* tool results and session structure; (2) it
writes the **entire conversation on every request**, so a long round costs O(n²) disk;
(3) `zjp()` replaces every `thinking` and `redacted_thinking` block with `<REDACTED>`, so
it is strictly lossier than the transcript for reasoning analysis. Its one genuine
advantage — exact per-request wire bodies — answers no question on our list.
*Verified in the binary, not live-run.*

## 3. RANKED CANDIDATES

| # | Name | What it does | Fits | Would replace here | Would still leave us building |
|---|---|---|---|---|---|
| 1 | **longhand** 1.0.1 (`Wynelson94/longhand`) | JSONL → SQLite (`raw_json NOT NULL` per event, indexed) + optional Chroma; CLI + 13 MCP tools; **deterministic no-LLM** session classifier (shipped/fixed/stuck/abandoned) and problem→fix episode extraction | **strong** | The transcript-walking + storage layer; a generic "how did this session end" classifier | The `kb_setup`+mise seam; cost/token extraction from `raw_json`; every repo-specific metric (mise-task bypass census, directive-violation rates, graph-first ratio); a bridge into graphify |
| 2 | **microsoft/SkillOpt** (SkillOpt-Sleep) | Harvests transcripts read-only, mines recurring tasks, replays on your own budget, gates a bounded skill edit on held-out tasks, stages a proposal for human adoption | partial | The *improvement* loop, not the review loop | Everything in need (a)/(c) as we mean it. **Already pinned here** (`pyproject.toml`, `currency.toml [tool.skillopt]`, `kb-skillopt-contract`); the marketplace plugin is deliberately disabled. PREVIEW; a real backend ships truncated transcript excerpts to a provider |
| 3 | **claude-vault** (`hazyhaar/claude-vault`) | ~1,900-LOC Go: walks the JSONL, stores each raw line as SQLite JSONB, 6 MCP tools. Verified live: **371,863 events / 2,340 files in 36.7 s**; watermark re-run returned 16 new events | partial | Only the loader — and `longhand` does the same job in-language | 100% of the mining; see §4 for why its analytical half is unusable |
| 4 | **pensyve** (`major7apps/pensyve`) | Rust+SQLite+ONNX memory runtime, Claude Code plugin, procedural memory with Bayesian action→outcome tracking | partial | Nothing we have | It is *retrieval*, not aggregation; capture is capped (`max_auto_memories_per_session: 10`) so the store is a model's curation, not a record — unauditable, the exact failure `kb-remember --audit` already found |
| 5 | **vardoger** 0.3.2 | PyPI CLI, reads `~/.claude/projects/*.jsonl`, batches the **user's** messages, host agent summarizes, writes a personalization rules file | partial | Nothing | Wrong axis — see §4 |
| 6 | **agentmemory** (`rohitg00/agentmemory`) | SQLite + MiniLM, 12 hooks, 54 MCP tools, has `import-jsonl` for existing transcripts | partial | Nothing | Fails (d) hard: npm-only, and it self-installs a pinned `iii-engine v0.11.2` into `~/.agentmemory/bin` behind two daemons — unpinnable by construction |
| 7 | **claude-self-reflect** | Rust binary, local embeddings, semantic search over past sessions | partial | Nothing | Purpose is retrieval/context-injection; no metric, retro or rule-derivation surface |
| 8 | **skillers** (`agent-sh/skillers`) | Prompt-driven transcript→friction-theme→skill-recommendation | **no** | Nothing | See §4 — 94 lines of real code total |
| 9 | **claude-performance** | 660-line digest over the JSONL; six metrics; appends rules to CLAUDE.md | **no** | Nothing | See §4 — writes `~/.claude/CLAUDE.md`, 2 of 6 metrics dead |
| 10 | **claude-activity-tracker** | Hooks → SQLite of (timestamp, tool name, file path) | **no** | Nothing | See §4 — schema holds nothing reviewable |
| 11 | **cxdb** (`strongdm/cxdb`) | Turn-DAG context store; `cxtx` wraps `claude` behind a local reverse proxy | **no** | Nothing | Captures only sessions launched as `cxtx claude`; zero of our existing history; documented failure mode where the child ignores the injected base URL and capture silently stops |
| 12 | **TencentDB-Agent-Memory** | 3-service stack; captures by `ANTHROPIC_BASE_URL` hijack | **no** | Nothing | Proxies every prompt through a third-party service, mints its own auth token, requires two sets of non-Claude LLM keys — `do-not.md` #4 twice over; floating `:latest` tags |
| 13 | **dash0 / langfuse / promptarc / deeplake-hivemind** | OTel traces / self-hostable observability / cloud session intelligence / cloud memory | **no** | Nothing | (b) fails or costs a Docker+Postgres deployment; `promptarc` and `deeplake-hivemind` ship transcripts off-machine |
| 14 | statusline/usage family (`claude-stats`, cc-usage, claude-cost-tracker, claude-token-stats…) | Render a live number | **no** | Nothing | No persisted multi-session record; cost-only slice of (a) |

## 4. RULED OUT, AND WHY — the descriptions that did not survive source-reading

This is the section worth keeping. **Five of the scan's eight "strong" ratings were
downgraded by the source-read pass**, and in every case the description was *literally
accurate* — what failed was the inference drawn from it. That is the durable lesson: a
marketplace description is author copy, and "reads session JSONL and derives rules" can be
true of a tool that is 94 lines of regex.

### claude-performance — `strong` → **no** (the headline feature is forbidden here)

- Its self-improvement write-back targets `MEMORY_FILE = Path.home()/'.claude'/'CLAUDE.md'`
  (:519, appended :560-562), a **module constant with no flag or env override**. That is
  `do-not.md` #11 and CLAUDE.md invariant 2 — worse than the md-budget collision the scan
  predicted; it is the wrong file in the forbidden directory.
- **A metric that can never fire**: :202 dispatches on `rec_type in {'tool_result','tool_error'}`.
  Measured over 70 real local session files: `type=='tool_result'` → **0**,
  `type=='tool_error'` → **0**, control `type=='assistant'` → **5,783**. No such record type
  exists; real errors are 3,083 `tool_result` *blocks* nested inside `user` records. So
  diagnostic D6 RECURRING ERROR is dead code. A second metric (hookify firings) regex-scans
  for a different plugin's output — dead here too. **2 of 6 advertised metrics are inert.**
- No cost/token capture at all (grep `usage|input_tokens|cost` → docstring + prose only;
  control `one_shot` → 13), despite `message.usage` being populated on 5,783/5,783 assistant
  turns. It never reads user prompts (`grep '"user"'` rc=1; control `'"assistant"'` → 2).
- Hard-wired to the author's personal Obsidian vault (`VAULT_ROOT/'⚙️ Meta'/'Performance'`);
  `--dry-run` is not side-effect-free (mkdir at :626 precedes the guard at :631 — measured,
  it created a directory outside its own clone).
- Not a package: no `pyproject.toml`/`setup.py`/tag/release (control: `ls README.md`
  succeeded). (d) fails outright.
- **Bonus honest finding from that agent**: it *expected* `DELEGATE_TOOLS={'Agent'}` to be
  wrong and measured `Agent`→22, `Task`→0. The script was right; the suspicion was reported
  as refuted rather than shipped as a finding.

### skillers — `strong` → **no** (there is no implementation)

- Whole repo is 1,685 lines / 19 files. The **only executable code** is
  `lib/sanitize.js` (94 lines of regex + Shannon-entropy redaction), its test, and a
  structure self-validator. Path resolution, JSONL reading, clustering, `calculateWeight`
  (30-day half-life), `classifyPrimitive` are **illustrative JavaScript inside two SKILL.md
  files** (316 + 282 lines) that the LLM is told to reproduce each run. No test covers any
  formula. "Configuration rather than code" is precisely what this cannot give: it is a
  prompt.
- Captures the wrong half of (a): its vocabulary is user-friction prose
  (pain/repeat/task/wish/workflow). Control-armed grep over the clone:
  `tool_use` / `toolUse` / `costUSD` / `token_count` / `"tool call"` → **0 files each**,
  against controls `observation` → 7 files, `weight` → 7, `jsonl` → 6.
- Bounded to a sample by instruction: "NEVER read more than 20 transcripts at once",
  "sample the first 200 and last 300 lines", `--days` default 7 — an LLM re-read, not an index.
- (d) fails with both arms: npm `@agentsys/skillers` → **404** vs control
  `@anthropic-ai/sdk` → 200; `"bin"` in package.json → 0 vs control `"scripts"` → 1.
- Default `--scope global` writes `~/.claude/skillers/` and reads *every* project's
  transcripts. `--scope=repo` is mandatory and is the non-default.
- **Worth stealing**: `lib/sanitize.js` (MIT-declared in-file) and the evidence thresholds —
  5+ occurrences across 3+ distinct sessions, weight ≥ 0.2, 30-day half-life. `kb-distill`'s
  "written twice" rule currently has no such floor.

### claude-activity-tracker — `strong` → **no** (the store holds nothing reviewable)

- Entire schema (`src/db.py:27-52`) is `sessions(id, started_at, ended_at, project,
  total_tools, total_requests, git_branch)` and `events(session_id, ts, type, tool_name,
  file_path, project)`. **No column can hold a prompt, a command string, a tool argument, a
  result, an error, a cost or a token.** It discards at the hook deliberately: for Bash it
  keeps the first whitespace token only if it contains `/` or `.`, so
  `mise run kb-query -- "..."` records an *empty path*. The README calls this a privacy
  feature — and it is; it is also a strict signal downgrade versus the raw transcripts.
- `total_requests` is fabricated from a >30 s inter-tool-gap heuristic, so any long
  `kb-build` inflates it.
- Session identity is a **single global file** `~/.claude-activity/current_session` and it
  mints its own UUID, ignoring the `session_id` Claude Code passes — concurrent sessions
  merge into one row, unsound exactly where need (c) lives.
- (d): no PyPI (404; controls `graphifyy` → 200, `mcp` → 200), no tags, no releases
  (control: `astral-sh/uv` populated). Install is `curl | bash` off a moving branch, and it
  rewrites `~/.claude/settings.json`, does `claude mcp add --scope user`, installs a global
  `~/.claude/skills/activity.md`, `pip3 install mcp --break-system-packages`, and appends to
  `~/.zshrc` — five `do-not.md` #11 violations.
- Description doesn't survive: the installer copies `skills/activity.md`, the repo ships
  `skills/activity/SKILL.md` (control-armed) — the advertised skill silently never installs.
- 19 commits, all on 2026-05-12 over ~4 hours, nothing since.

### vardoger — `strong` → **partial** (right shape, inverted axis)

- **Prose only.** `history/claude_code.py:32` keeps `RELEVANT_TYPES = {"user","assistant"}`
  and :129 calls `extract_text` with default `text_types=("text",)`, so `tool_use` /
  `tool_result` blocks are dropped; the Pydantic models are `extra="ignore"` with only
  `{type,text}` / `{type,message}`, so timestamp, sessionId, cwd and usage are parsed away.
  Control-armed: `tool_use|tool_result|toolUse` → 0 hits (rc=1) vs control `text_types` → 5.
- **Decisive**: `digest.py:5-7` verbatim — *"Assistant messages are excluded — the user's
  words reveal their preferences and style"*, enforced at :44. It mines the **human** to
  personalize the agent. We need to mine the **agent** to review it. The half we care about
  is filtered out before any model sees it.
- Genuinely local ((b), control-armed: the only `requests|httpx|api_key|ANTHROPIC` hits are
  docstrings) and genuinely pinnable ((d): PyPI 200 for 0.3.2, bogus name → 404). Default
  `--scope global` writes `~/.claude/rules/vardoger.md`, and `~/.vardoger/state.json` has no
  override (`--state-dir` → 0 hits vs control `--platform` → 3).
- **Two things worth carrying**: its prepare → host-agent-summarizes → write loop is the
  same host-agent pattern `kb-extract` already uses (so LLM-assisted mining needs no API
  key), and its ~200-line reader + sha256 checkpoint is small enough that writing our own —
  *keeping* the `tool_use` and `usage` fields — is the better trade.

### claude-vault — `strong` → **partial** (the loader is real; the analysis belongs to a stranger)

The scan rated it strong on a **GitHub one-line description field with nothing behind it**:
1 commit dated 2026-03-21, 0 stars, 0 forks, **zero git tags** (control: `astral-sh/uv`
returns tags), **no README**. The ingest core verified excellent — built clean, 371,863
events in 36.7 s, watermark proven on re-run, 21 test funcs, control-armed clean of
`net/http`/`os/exec` (control `database/sql` → 2 hits). Then:

- **R1 — a lie inside text a model reads to choose a tool**: `sessions_stats`' own MCP
  description advertises *"tokens, coût estimé, durée"* and the SQL computes **none**
  (`token|cost|usage` over both .go files → exactly 2 hits: the description string at
  `mcp.go:128` and an unrelated redaction regex at :431).
- **R2** — `extractNamespaceTags` (`mcp.go:872-906`) is a hardcoded slice of the author's
  private projects (siftrag, repvow, horum, HORAG, archaix…); zero match anything of ours,
  and `sessions_filter` **defaults** to hardcoded NLnet include/exclude tags and prints
  "## Sessions NLnet-relevant".
- **R3** — the structured report mode ATTACHes `vault.entities`/`vault.relations`, tables
  owned by a *separate* tool (`hazyhaar/context-vault`) that nothing here populates.
- **R4** — the redaction regex is `/home/[a-z]…` with zero `/Users` handling: `redact:true`
  **silently no-ops on darwin while reporting success**.
- **R5** — the SELECT guard is a bare `HasPrefix`, and ATTACH interpolates an env var into SQL.
- Disagreement with the scan, resolved: the scan said "plugin-only, no pinnable artifact";
  the source-read proved `go install …@db09b46` rc=0 (control `@deadbeef` rc=1). **Believe the
  source-read on the mechanism** — but the shipped `.claude-plugin/.mcp.json` uses
  `go run …@latest`, so the pin exists only if you bypass what it ships. Moot: `longhand`
  does the same job in-language.

### Two more scan-level corrections worth recording

- **longhand's "17 MCP tools" is wrong** — `mcp_server.py` declares **13** at v1.0.1. Its
  "~126 ms/query" and its Glama A/A/A grade are inherited vendor numbers; no benchmark
  harness was read, so both stay unverified. The scan's "(d) plugin-only" caveat is
  **refuted**: it is an ordinary PyPI sdist/wheel with a console script.
- **The scan's own bound, restated because it governs every absence above**: the filter
  matched **name + description only** over 2,281 entries. "Not in the candidate list" means
  "no description-token match", not "does not exist". Its probe was control-armed
  (`claude code` → 920, `sqlite` → 28, `jsonl` → 13, `opentelemetry` → 3,
  `zzqqxx-nonexistent` → 0), so the zeros are answers — about descriptions.

### The structural finding behind all of it

Of 2,281 marketplace plugins, ~120 tier-1 hits are **memory** (inject context so the agent
"remembers") and **exactly three** describe reading raw session JSONL and deriving
behavioural rules: `claude-performance`, `vardoger`, `skillers`. All three were source-read
above; **all three were downgraded.** The marketplace is saturated with memory and empty of
mining. That is the answer to the framing question, arrived at independently by the scan and
confirmed by every source-read: the *store* is available off the shelf, the *mining* is not.

## 5. OPEN QUESTIONS

| Question | The probe that would settle it |
|---|---|
| Does `longhand ingest --skip-analysis` truly avoid constructing/embedding through Chroma end-to-end? `LonghandStore` always constructs a `VectorStore`, so the ONNX download may only be *deferred*. | Run the MVP command on a fresh `LONGHAND_DATA_DIR` **with the network off** (or with `HF_HUB_OFFLINE=1`) and read the real rc; control-arm with a run that *does* analyze. |
| Does `OTEL_LOG_RAW_API_BODIES=file:<dir>` behave as the binary reads? Verified statically only. | Set it in a throwaway project's `.claude/settings.json` `env`, run one trivial session, and `ls` the dir; control arm = same session with the var unset → empty dir. |
| Does mise's `go:` backend accept a bare commit SHA in `mise.toml`? Only the underlying `go install <pkg>@<sha>` was armed (rc=0; bogus SHA rc=1). | Add a throwaway `go:` entry pinned to a SHA and run `mise install`; control-arm with a bogus SHA expecting a non-zero rc. Moot unless claude-vault is reconsidered. |
| Does `skillopt-sleep` actually read `~/.claude/projects/**`? Its doc names exact harvest paths for Cursor and Pi but **not** for Claude. | `uv run skillopt-sleep dry-run --max-sessions 1` with the mock backend and read what it lists; control-arm against a directory known to contain transcripts vs an empty one. |
| Is the transcript `usage` block complete enough for a per-round cost figure (cache reads, cache creation, per-model rates)? | `json_extract` `message.usage.*` over one known round and reconcile against `/cost` for the same session; a mismatch names the missing field. |
| Does `longhand`'s LIKE-scan search (no FTS5: grep `fts5|VIRTUAL TABLE` → 0; control `LIKE ? ESCAPE` → 4 sites) stay usable at our volume? | Time a `search` against the full 229-session ingest; if it is slow, we add FTS5 ourselves — it is one `CREATE VIRTUAL TABLE`. |
| The two follow-up repos named at `claude-performance` README:22 — `adelaidasofia/claude-daily-journal`, `adelaidasofia/claude-insights` — were never read. Same author, so assume the Mycelium install-ping (a `POST https://myceliumai.co/api/install` from an unconditional SessionStart hook, opt-out via `MYCELIUM_NO_PING=1`) until probed. | Clone at a SHA and grep for `myceliumai.co` with a control term from the same file. |
| Marketplaces this repo already enables were never surveyed — notably `claude-code-workflows`, which ships the plugin-eval static layer `kb-skill-score` already wraps. | Re-run the scan's tier-1 filter against those manifests. |

## GitHub repos touched

- [anthropics/claude-plugins-community](https://github.com/anthropics/claude-plugins-community) — fetched and parsed `.claude-plugin/marketplace.json` (2,281 entries); the scan's sole source read.
- [hazyhaar/claude-vault](https://github.com/hazyhaar/claude-vault) — full source-read of both non-test `.go` files, build + live ingest + pinned `go install` arm.
- [Wynelson94/longhand](https://github.com/Wynelson94/longhand) — source-read at HEAD `2983efcb`: `sqlite_store.py`, `storage/store.py`, `mcp_server.py`, `analysis/`, `setup_commands.py`, `redaction.py`.
- [adelaidasofia/claude-performance](https://github.com/adelaidasofia/claude-performance) — cloned at `8be48d0`, read all 1,044 lines, executed `--dry-run` against 70 real session files.
- [dstrupl/vardoger](https://github.com/dstrupl/vardoger) — source-read of `history/`, `digest.py`, `analyze.py`, `checkpoint.py`, `writers/`, `cli.py`, `prompts/`, `plugins/claude-code/`.
- [agent-sh/skillers](https://github.com/agent-sh/skillers) — full clone read (1,685 lines / 19 files), incl. both SKILL.md pipelines and `lib/sanitize.js`.
- [Sent1nelX/claude-activity-tracker](https://github.com/Sent1nelX/claude-activity-tracker) — source-read of `src/db.py`, `src/server.py`, `hooks/`, `install.sh`.
- [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) — docs + install surface read; already pinned in this repo's `pyproject.toml` / `currency.toml`.
- [major7apps/pensyve](https://github.com/major7apps/pensyve) — README + install paths; PyPI/crates.io availability probed.
- [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory) — README + hook/`import-jsonl` design; npm-only distribution confirmed.
- [strongdm/cxdb](https://github.com/strongdm/cxdb) — README + `cxtx` capture design and its documented bypass failure mode.
- [TencentCloud/TencentDB-Agent-Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) — `INSTALL.md` base-URL-hijack and dual-LLM-key requirements.
- [topoteretes/cognee](https://github.com/topoteretes/cognee) — quickstart; requires an LLM API key.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — used as the control arm for the `gh api` repo probe.
- [astral-sh/uv](https://github.com/astral-sh/uv) — used as the control arm for git-tag / releases probes.
- [Pratham-Mishra04/trail](https://github.com/Pratham-Mishra04/trail), [ankitkr3/compounded](https://github.com/ankitkr3/compounded), [lisn0/learned-behavior](https://github.com/lisn0/learned-behavior), [mmmprod/claude-eta](https://github.com/mmmprod/claude-eta), [akzarma/claude-find-conversation](https://github.com/akzarma/claude-find-conversation) — description-layer only (scan pass); no source read. Named because each contributes one idea worth stealing (local-JSONL-over-MCP transport, promotion/demotion gating, hook-observed behaviour without self-report, error-content fingerprinting for repair loops, stdlib-only transcript search).

_First-party artifact also inspected, not a repo: the shipped `claude` binary
`~/.local/share/claude/versions/2.1.234` (Mach-O arm64) — `strings` probe of the
`OTEL_LOG_RAW_API_BODIES` file-mode implementation (`RSS`/`Bjp`/`jjp`/`zjp`), control-armed._
