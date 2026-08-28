# Trackers + breadth sweep: Claude/Codex agent team, limited Fable-5 tokens

Question (Ray, verbatim): "how to build a claude/codex agent team that
optimizes use of limited fable-5 tokens and communication between claude and
codex agents" — end goal: graphify running on the fork's `openai-cli` backend.

Builds on `docs/research/reports/2026-08-27-claude-codex-handoff.md` (not
re-answered here). This report covers: (1) tracker sweeps of
openai/codex, anthropics/claude-code, mar3co/fable-orchestrator; (2) breadth
web sweep; (3) the specific architecture questions about `codex mcp-server` /
`app-server`, `--output-schema`, `exec resume`, and token-budget knobs.

Graph-first check (required before any raw search): `mise run kb-query --
"codex mcp-server app-server output-schema exec resume"` returned 753 nodes
(truncated at 61 shown) confirming this repo's `sources/codex/` clone (pinned
via `sources/codex.manifest`, ref `rust-v0.150.1`, commit
`90854393966b21e9ebfd21b122334eb09a20c93d`) already contains
`codex-rs/app-server-protocol/schema/json/codex_app_server_protocol.schemas.json`,
`codex-rs/codex-mcp/src/mcp/mod.rs`, and the Python SDK. This is corroborating
only — the detailed answers below come from reading the pinned source
directly (a tracker/graph hit is a probe, never a substitute, on a protocol
question — `probes-need-a-control-arm.md`). Note: `sources/codex.manifest`
carries `build = skip` (#417 — `Cargo.toml` produces zero nodes at extraction),
so `graphify-out/graph.json` does NOT contain codex's own source nodes from
this manifest; the 753 nodes above came from other sources referencing codex
(the Python SDK under `sdk/python/`, the TUI). The local `sources/codex/`
clone on disk (gitignored, from a prior fetch attempt) is what every direct
source read below used, cross-checked line-by-line, not the graph.

## Answer (one paragraph)

Two viable transports exist for Claude↔Codex communication, and they are not
mutually exclusive with the pinned source at `rust-v0.150.1`. **(1) MCP tool
transport**: `codex mcp-server` (`codex-rs/cli/src/main.rs:151-152`, "Start
Codex as an MCP server (stdio)") exposes exactly **two** MCP tools —
`codex` (start a session: `prompt`, `model`, `cwd`, `approval_policy`,
`sandbox`, arbitrary `config` overrides, `base_instructions`,
`developer_instructions`, `compact_prompt` — `codex-rs/mcp-server/src/codex_tool_config.rs:105-121`)
and `codex-reply` (continue by `threadId` + `prompt` —
`codex_tool_config.rs:222-240`), both returning `{threadId, content}`. This
is a native, ready-to-register MCP server Claude Code can add via
`.mcp.json` and call like any other tool — session continuation is built in
via `codex-reply`, so it does not need `codex exec resume` at all. **(2) CLI
subprocess transport** (what this repo's `fable-orchestrator` plugin already
uses): `codex exec --output-schema <file>` — a **global** flag on the `exec`
CLI (`codex-rs/exec/src/cli.rs:43-44`) — enforces structured JSON output on
plain `codex exec` and `codex exec resume` (also global, so it composes with
`resume`), but a live, still-open, actively-being-triaged bug means it is
**silently ignored on `codex exec review`** specifically (openai/codex#38545,
opened 2026-08-14, root-caused by two independent community contributors down
to `codex-rs/exec/src/lib.rs`'s `ExecCommand::Review` arm never calling
`load_output_schema`, unfixed as of this sweep) — so a spec dispatched via
`codex exec review --output-schema` is a false-success trap; only plain
`codex exec [resume]` honors the schema contract. `codex exec resume` restores
full conversation/session state (thread id-addressed) but historically lagged
`--output-schema` support until #22998/#23123 closed the gap (merged 2026-05-18,
well before the pinned 0.150.1). **There is no first-class token-budget knob
for a non-interactive `codex exec`/`exec resume` run** — the only budget field
in the config schema is `GoalsToml.max_goal_token_budget`
(`codex-rs/config/src/config_toml.rs:659`), scoped to Codex's own autonomous
"goal mode" loop, not `exec`; a general `--max-steps`/`--max-agent-turns`
execution-budget feature request for `codex exec` is still **OPEN**
(openai/codex#33294). The nearest cost lever for a delegated `exec` call is
`model_reasoning_effort` (already what this repo's `codex-implementer` lane
sets). Separately — not asked for but load-bearing for the "agent team"
framing — Codex ships its **own** native multi-agent subsystem
(`AgentsToml` in `codex-rs/config/src/config_toml.rs:661-690`:
`max_concurrent_threads_per_session`, `default_subagent_model`,
`default_subagent_reasoning_effort`, user-defined named roles), which is a
Codex-internal fan-out orthogonal to a Claude-orchestrated cross-vendor team.

## Ranked sources

**Primary** (read directly from the pinned/local clone, cited by `file:line`):
- `codex-rs/cli/src/main.rs:131-217` (`Subcommand` enum: confirms both
  `McpServer` and `AppServer` exist as top-level subcommands at this ref)
- `codex-rs/mcp-server/src/codex_tool_config.rs:105-240` (the `codex` /
  `codex-reply` MCP tool schemas and dispatch)
- `codex-rs/mcp-server/src/message_processor.rs:356` (`"codex" =>
  self.handle_tool_call_codex(...)`, confirming dispatch)
- `codex-rs/exec/src/cli.rs:43-44,146` (`--output-schema` as `global = true`;
  `Command::Resume(ResumeArgs)`)
- `codex-rs/config/src/config_toml.rs:655-690` (`GoalsToml`, `AgentsToml`)
- `docs/config.md` (in-repo stub — config now lives on
  developers.openai.com, not in this repo; see Not measured)

**Secondary** (trackers + breadth web, corroborating/contextual):
openai/codex issues #38545, #35596, #19816, #40702, #40149, #22998, #33294,
#34215; deepwiki.com and several third-party integration repos (OpenClaw,
Claudian, happy, etienne) independently describing the same `app-server`
JSON-RPC-over-stdio shape as the primary source.

## Tracker sweep: openai/codex

`mise run kb-research-trackers -- openai/codex "<term>"` (searches `is:issue`
and `is:pr` together — the adapter combines both channels per repo's
`has_issues`). All terms ran against `total_count` in the hundreds-to-
thousands range on this repo's very large tracker — `total_count` itself is
noise; only the top-3 ranked hits are load-bearing.

| term | total_count | top hits |
|---|---|---|
| output-schema | 446 | [#38545](https://github.com/openai/codex/issues/38545) `codex exec review` accepts but ignores `--output-schema` (2026-08-18) · [#35596](https://github.com/openai/codex/issues/35596) same bug, earlier report (2026-07-27) · [#19816](https://github.com/openai/codex/issues/19816) `--output-schema` does not apply only to final output (2026-06-28) |
| exec resume | 539 | [#40702](https://github.com/openai/codex/issues/40702) `codex exec resume` overrides persisted cwd when `-C` omitted (2026-08-26) · [#40149](https://github.com/openai/codex/issues/40149) `exec resume` rejects `-s/--sandbox` (2026-08-23) · [#35751](https://github.com/openai/codex/issues/35751) IDE resumed thread loses exec/code-mode tools (2026-08-18) |
| app-server | 5080 | [#41188](https://github.com/openai/codex/issues/41188) support externally managed app-server daemon executables (2026-08-27) · [#39482](https://github.com/openai/codex/issues/39482) app-server marketplace hook refresh test times out (2026-08-19) · [#40953](https://github.com/openai/codex/issues/40953) app-server: add an atomic thread-level interrupt API (2026-08-26) |
| mcp-server | 2705 | [#37471](https://github.com/openai/codex/issues/37471) MCP servers not exposed (2026-08-11) · [#39198](https://github.com/openai/codex/issues/39198) MCP servers disconnect every two hours (2026-08-18) · [#37903](https://github.com/openai/codex/issues/37903) plugin MCP servers: no workspace/project-root signal (2026-08-18) |
| token budget | 324 | [#34215](https://github.com/openai/codex/issues/34215) goal mode cannot increase its token budget and resume after `budget_limited` (2026-07-19) · [#38721](https://github.com/openai/codex/issues/38721) support cost/budget metrics in TUI status_line (2026-08-15) · [#37767](https://github.com/openai/codex/issues/37767) wasting tokens with names and a list of tokens remaining (2026-08-18) |
| agent handoff | 396 | [#35283](https://github.com/openai/codex/issues/35283) Desktop agent-handoff tool lacks parity with Handoff UI (2026-07-25) · [#38365](https://github.com/openai/codex/issues/38365) support reliable cross-provider session handoff with normalized tool history (2026-08-23) · [#33789](https://github.com/openai/codex/issues/33789) App Handoff silently skips non-ignored untracked skill files (2026-07-17) |
| orchestrat | **0**, armed (see below) | — |
| subagent | 1546 | [#40941](https://github.com/openai/codex/issues/40941) allow users to create subagents from the Subagents panel (2026-08-26) · [#40377](https://github.com/openai/codex/issues/40377) context size per subagent (2026-08-24) · [#40919](https://github.com/openai/codex/issues/40919) CLI subagent invalid response body (2026-08-26) |
| exec --json | 1415 | [#36562](https://github.com/openai/codex/issues/36562) `codex exec --json` drops typed `codexErrorInfo` from terminal errors (2026-08-08) · [#39406](https://github.com/openai/codex/issues/39406) `--ephemeral --json`: expose provider-reported model ID on `turn.completed` (2026-08-19) · [#32984](https://github.com/openai/codex/issues/32984) expose `willRetry` in `--json` error events (2026-08-20) |

**Rate-limit episode (environmental, not a tracker defect).** The three `gh
api` calls per term (repo check + issue search + PR search) exhausted
GitHub's **search** rate limit (30/min) after 6 terms:
`gh api rate_limit --jq '.resources.search'` returned
`{"limit":30,"remaining":0,"used":30}` and the next `kb-research-trackers`
call failed with HTTP 403 `API rate limit exceeded for user ID 1428022`.
Per `persistence-gate-retry.md`, this is the environmental signature (not a
`fatal: reference is not a tree` or empty-result-with-hits-elsewhere shape),
so the fix was to wait for `.resources.search.remaining` to recover (polled
via a bounded background loop) rather than retry blind or conclude anything
about the terms that failed. Confirmed recovered:
`{"limit":30,"remaining":30,"used":0}` before resuming.

**Control arm on `orchestrat` → 0 hits** (`probes-need-a-control-arm.md`):
the adapter's own `null_result.arms` for this query —
`gh api -X GET search/issues -f q=repo:openai/codex is:issue` →
`total_count=24675`; `... is:pr` → `total_count=2618`. Both non-zero, so the
search channel discriminates on this repo; "orchestrat" genuinely has zero
matches in openai/codex's tracker (no substring match on "orchestrate" /
"orchestration" either, since GitHub search tokenizes on word boundaries).

## Tracker sweep: anthropics/claude-code

Same adapter shape, `is:issue` only (`has_discussions: false`, and this repo
does not use GitHub Discussions for claude-code — search covered issues + PRs).

| term | total_count | top hits |
|---|---|---|
| agent team | 3492 | [#89509](https://github.com/anthropics/claude-code/issues/89509) `[FEATURE]` a declarative team definition for Agent Teams, with enforced role guardrails (2026-08-25) · [#88085](https://github.com/anthropics/claude-code/issues/88085) feature request: "agent-hours" labor metric for agent teams (2026-08-19) · [#71640](https://github.com/anthropics/claude-code/issues/71640) `[Bug]` Agent Teams conversation blocks navigation back to agents view (2026-08-25) |
| codex | 1656 | [#87596](https://github.com/anthropics/claude-code/issues/87596)/[#87595](https://github.com/anthropics/claude-code/issues/87595) weekly-limit-reset-like-Codex (dup pair, 2026-08-18) · [#78196](https://github.com/anthropics/claude-code/issues/78196) feature request: local control API for external orchestrators (Codex Desktop parity) — blocks replacing Codex for some workflows (2026-08-17) |
| subagent report | 3557 | [#80036](https://github.com/anthropics/claude-code/issues/80036) `[Bug]` Subagent tool stripped in nested subagent calls breaks tool invocation (2026-08-25) · [#90264](https://github.com/anthropics/claude-code/issues/90264) multi-agent session: background-task orphaning, cross-session message holds, and subagent drift (field report, 2026-08-28) · [#86471](https://github.com/anthropics/claude-code/issues/86471) `[Bug]` background subagents report status "completed" with empty/partial results and no output (2026-08-28) |
| token budget | 1396 | [#90206](https://github.com/anthropics/claude-code/issues/90206) `[Bug]` token budget exceeded with repeated TaskStop resumption and scope ignored (2026-08-27) · [#85060](https://github.com/anthropics/claude-code/issues/85060) `[MODEL]` context-budget confabulation/hallucination in the Claude Code harness (2026-08-25) · [#85099](https://github.com/anthropics/claude-code/issues/85099) feature request: credit refund/budget tracking for wasteful subagent patterns (2026-08-25) |
| cross-model | 2736 | [#87323](https://github.com/anthropics/claude-code/issues/87323) `[BUG]` cross-session message written to target transcript but excluded from model's context (2026-08-20) · [#84658](https://github.com/anthropics/claude-code/issues/84658) `[BUG]` Code tab in Claude Desktop resolves models to cross-region IDs Bedrock rejects (2026-08-20) · [#78996](https://github.com/anthropics/claude-code/issues/78996) `[MODEL]` sustained Korean-language sessions degrade, recurring cross-model pattern, repeatedly auto-closed as stale (2026-08-21) |

**Directly load-bearing for this question's "communication between claude and
codex agents" half:** #86471 (background subagents reporting `completed` with
empty/partial results and no output, 2026-08-28) is the *upstream, general*
version of this repo's own `subagent-lanes-go-idle-without-reporting.md`
finding (memory: 4/4 plugin lanes went idle without reporting on 2026-08-28,
recovered by a `SendMessage`). #90264 (multi-agent session field report,
also 2026-08-28) independently reports "background-task orphaning,
cross-session message holds, and subagent drift" — the same failure class,
filed by a different reporter the same day. Neither is a fable-orchestrator
defect; both are Claude Code harness-level, so the mitigation (resend/poll,
never assume dead) generalizes past this repo's own plugin.

## Tracker sweep: mar3co/fable-orchestrator

Small repo — enumerated fully via `gh issue list`/`gh pr list --state all`
(core REST, not the rate-limited search endpoint) rather than the adapter,
since the ask was "every open issue/PR", not a term search.

**All issues (7 total, 1 open):**

| # | state | updated | title |
|---|---|---|---|
| 16 | **OPEN** | 2026-08-09 | Post-bound fix commits ship with self-review only — consider a targeted cold pass |
| 8 | closed | 2026-07-13 | Spec contract: commit ownership is unstated |
| 7 | closed | 2026-07-13 | grok-implementer: narration-of-intent instead of execution |
| 6 | closed | 2026-07-13 | codex-reviewer: non-unique temp diff file can get clobbered by a concurrent lane |
| 5 | closed | 2026-07-12 | grok lanes: one-shot preflight permanently fails on transient auth race |
| 4 | closed | 2026-07-12 | grok-implementer: CLI exits without report/verification; detached process commits after "complete" |
| 1 | closed | 2026-07-11 | Orchestration doctrine: launch lanes with `run_in_background` by default |

**All PRs (15, all merged, 0 open):** #23 (1.21.0, pin grok 4.6 + effort
channel) · #22 (1.20.0, premise provenance gate) · #21 (1.19.0, copy dispatched
spec files, worktree-guard-safe templates) · #20 (drop redundant hooks
manifest field) · #19 (premise gate: PREMISES spec part + premise-verifier
lens) · #18 (1.17.0, user-configurable codex reasoning effort) · #17 (bound
wrapper duties: stat-only preflight, no re-runs) · #15 (1.15.0, doctrine
rebalance) · #14 (sample lane speed benchmark) · #13 (harden shared-checkout
discipline) · #12 (cap wait slices below auto-background threshold) · #11
(v1.12.0, fix grok lane dying on headless permission cancellation) · #10
(harden lane contracts: commit ownership, review-by-ref, grok guardrails) ·
#3 (1.8.0, setup wizard, gate always-on trigger to Fable) · #2 (1.7.0,
background-by-default doctrine).

**Term searches** (`substitut`, `report`, `timeout`):

| term | total_count | top hits |
|---|---|---|
| substitut | **0**, armed (see below) | — |
| report | 19 | #16 (open, above) · #4 grok-implementer CLI exits without report/verification (closed) · #8 commit ownership spec-contract gap (closed) |
| timeout | 6 | #4 (closed) · PR #21 copy dispatched spec files (merged) · PR #22 premise provenance gate (merged) |

**Control arm on `substitut` → 0 hits:** `null_result.arms` —
`is:issue` → `total_count=7`; `is:pr` → `total_count=15` — both match this
repo's exact all-issue/all-PR counts above, confirming the search channel is
live and the null is real: no fable-orchestrator issue or PR has ever used
"substitut(e/ion)" in its title/body.

**Issue #16 full body** (the one open issue, read via `gh issue view 16
--repo mar3co/fable-orchestrator --json title,body,comments`, no comments
yet): argues that the two-respec-round review bound correctly stops thrash,
but fix commits landed *after* the bound with **self-review only**, and an
external reviewer later found real defects in exactly that unreviewed text
(a dissent-settlement rule that could commit work while reporting `CHANGES:
none`, and a shell-unsafe raw `BRANCH` echo). Proposed fix: after the bound,
substantive new doctrine text gets one targeted cold pass scoped to the fix
commits only, while pure wording fixes stay self-reviewed. **This is directly
on-topic for "optimizing limited Fable-5 tokens"**: it is upstream evidence,
from the plugin this repo already runs, that skipping review on post-bound
fix commits to save tokens/rounds has already caused a real regression there
— which is also why this repo's own standing rule is "always consult
fable-advisor before any codex-implementer dispatch"
(`always-consult-fable-advisor-before-codex-implementer.md`), not "trust the
lane's self-report."

## Breadth sweep (Firecrawl / Exa)

Firecrawl `firecrawl_search` (`categories: ["developer"]`) returned non-empty
results for every query run — no Exa control-arm fallback was needed (the
"second index as control on any Firecrawl zero" instruction did not trigger).

- **"codex mcp-server protocol claude code agent team"** → top hits: a
  DeepWiki page on OpenClaw's Codex app-server harness ("JSON-RPC 2.0 over
  stdio or WebSockets"), `jaesolshin.com`'s "Codex App Server Python SDK —
  JSON-RPC v2 over stdio", and **three independent third-party integrations**
  (Claudian, `happy`, `etienne`) all describing the identical shape: spawn
  `codex app-server --listen stdio://` (or default stdio), speak
  newline-delimited JSON-RPC 2.0, handshake `initialize` → `initialized`,
  then `thread/*` and `turn/*` methods. This corroborates (does not
  substitute for) the primary-source read of `codex-rs/app-server/` above —
  three unrelated integrators converged on the same protocol description,
  which is a strong cross-check but every one of them is a **secondary**
  source (their own reverse-engineering/wrapper docs, not OpenAI's).
- **"codex exec --output-schema guarantee json output"** → surfaced
  openai/codex#22998 (feature request: `exec resume --output-schema` parity,
  closed by #23123, merged 2026-05-18 — matches the primary-source read that
  `--output-schema` is `global = true` and therefore composes with `resume`)
  and openai/codex#4181 (a much older, already-fixed bug: schema was
  gated to `model_family.family == "gpt-5"` and silently dropped for other
  model slugs — historical, not current at 0.150.1, included for completeness
  since it shows this flag has a history of silent-drop failure modes beyond
  the current `exec review` one).
- **"codex cli official token budget flag non-interactive run limit max
  tokens"** → surfaced openai/codex#33294 (feature request: `--max-steps`/
  `--max-agent-turns` execution budgets for `codex exec`, confirmed **OPEN**
  via `gh issue view 33294 --json state`) — corroborates the primary-source
  finding that no such flag exists yet. Also surfaced a third-party
  reverse-engineering doc (`johnlindquist/codex-imps`) quantifying codex's
  **system-prompt token overhead** by config knob (`features.apps=false`
  saves ~14K input tokens, disabling imagegen/tool_search/tool_suggest/web
  saves another ~3K) — this is a *prompt-size* budget lever, not an
  *execution-length* budget lever, and it is unofficial/reverse-engineered
  (secondary), not confirmed against the pinned source in this sweep — see
  Not measured.

## Specific answers

**(a) Does `codex mcp-server`/`app-server` exist at the pinned ref, and what
is its protocol?** Both exist, and they are **two different mechanisms**,
confirmed by reading `codex-rs/cli/src/main.rs:131-217` (the `Subcommand`
enum) at commit `90854393966b21e9ebfd21b122334eb09a20c93d` (`rust-v0.150.1`):
  - `codex mcp-server` (line ~151, doc comment "Start Codex as an MCP server
    (stdio)") → standard **MCP** protocol, exposing exactly two tools —
    `codex` and `codex-reply` — implemented in
    `codex-rs/mcp-server/src/codex_tool_config.rs:105-240` and dispatched at
    `codex-rs/mcp-server/src/message_processor.rs:356`. This is the direct
    answer to the handoff report's open question: Claude Code can register
    `codex mcp-server` in `.mcp.json` and call Codex as an ordinary MCP tool
    instead of shelling out to `codex exec`.
  - `codex app-server` (line ~155, doc comment "[experimental] Run the app
    server or related tooling") → a richer, **bidirectional JSON-RPC 2.0
    over stdio** protocol (`codex-rs/app-server/`, methods observed in the
    primary source: `thread/start`, `turn/start`, `turn/interrupt`,
    `turn/moderationMetadata`), the same protocol IDEs/the TUI use
    internally (`codex-rs/tui/src/app/thread_routing.rs`
    `.try_submit_active_thread_op_via_app_server()`). It is explicitly
    marked `[experimental]` in the CLI help text itself, unlike `mcp-server`.
- **(b) Does `codex exec --output-schema` exist, and what does it guarantee?**
  Yes — `codex-rs/exec/src/cli.rs:43-44`: `#[arg(long = "output-schema",
  value_name = "FILE", global = true)] pub output_schema: Option<PathBuf>`.
  Being `global = true` means it is accepted (and, for plain `exec` and
  `exec resume`, honored) across the `exec` subcommand tree. **It does NOT
  guarantee schema-conformant output for `codex exec review`** — confirmed
  open bug openai/codex#38545 (opened 2026-08-14, unresolved as of this
  sweep): the `ExecCommand::Review` dispatch arm in
  `codex-rs/exec/src/lib.rs` builds `InitialOperation::Review` directly and
  never calls `load_output_schema`, so the flag is accepted, silently
  dropped, and the command exits 0 with free-form prose — "automation cannot
  distinguish this from successful schema enforcement" (issue reporter's own
  words, corroborated independently by two other commenters who traced the
  same code path). **Practical implication for the agent-team design: never
  route a schema-dependent Codex call through `exec review`; use plain
  `exec` (or `exec resume`) with `--output-schema`.**
- **(c) Does `codex exec resume` exist, and what state does it restore?**
  Yes — `codex-rs/exec/src/cli.rs:146`: `Resume(ResumeArgs)` as a `Command`
  variant, exercised by `codex-rs/exec/src/cli_tests.rs` and
  `main_tests.rs`. It restores the full prior thread/session context
  (continuing an existing `codex exec` conversation by session id, per the
  top-level `Resume`/`Fork`/`Archive`/`Unarchive` command family at
  `codex-rs/cli/src/main.rs:184-198` and the `ResumeCommand` struct at
  `main.rs:321-`). `--output-schema` composes with it (global flag, and
  #22998/#23123 closed the gap where schema support once lagged behind
  plain `exec`, merged 2026-05-18 — well before this pin). It is not defect
  -free: openai/codex#40702 (2026-08-26, still recent) reports `exec resume`
  silently overriding the persisted working directory when `-C` is omitted,
  and #40149 reports it rejecting `-s/--sandbox` outright — both suggest
  `exec resume`'s flag surface is less mature/more actively-patched than
  plain `exec`'s.
- **(d) Is there an official token-budget knob for a non-interactive run?**
  **No**, not for `codex exec`/`exec resume` specifically. The only
  token-budget config field found in `codex-rs/config/src/config_toml.rs` is
  `GoalsToml.max_goal_token_budget: Option<NonZeroU64>` (line 659, doc
  comment "Maximum token budget allowed for a goal and default budget for
  new goals") — scoped to Codex's separate autonomous **goal-mode** loop
  (matches tracker hit openai/codex#34215, "Goal mode cannot increase its
  token budget and resume after becoming budget_limited"), not to `exec`.
  A general execution-budget feature request for `codex exec` itself —
  `--max-steps`/`--max-agent-turns` — is tracked as openai/codex#33294 and
  confirmed **OPEN** (`gh issue view 33294 --json state` → `"OPEN"`). The
  nearest actual cost lever on a delegated `codex exec` call is
  `model_reasoning_effort` (`codex-rs/config/src/config_requirements.rs:986`,
  values via the `ReasoningEffort` enum) — already what this repo's
  `codex-implementer` fable-orchestrator lane sets (per
  `.claude/CLAUDE.md`'s "codex effort = xhigh" line and PR #23 in the
  fable-orchestrator tracker above, "Pin grok lanes to Grok 4.6 and add the
  grok effort channel"). There is no per-call max-token or max-turn cap to
  bound a single Codex delegation's spend; the only bound available today is
  choosing a cheaper reasoning-effort tier before dispatch, or wrapping the
  call in an external timeout (as `long-running-command-hangs.md` already
  does for other subprocess calls in this repo).

## Not measured

- **`codex mcp-server`'s actual runtime behavior was not exercised** — this
  sweep confirmed the tool schemas and dispatch code exist at the pinned ref
  by reading source, but did not run `codex mcp-server` and drive it with a
  live MCP client to confirm the `{threadId, content}` response shape holds
  in practice, or measure round-trip latency/token overhead vs. `codex exec`.
- **`docs/config.md` in the pinned clone is a 15-line stub** pointing to
  `developers.openai.com/codex/config-{basic,advanced,reference}` — the
  in-repo docs no longer carry the full config reference, so `grep -i "token"
  docs/config.md` returning 0 hits is NOT evidence against a token-budget
  config key existing; it is evidence the docs moved out of the repo. The
  config-field claims above were verified against the **Rust source**
  (`config_toml.rs`), not the docs, specifically because of this.
- **The reverse-engineered prompt-size token table** (`johnlindquist/
  codex-imps`, ~22K→~5.2K input tokens across feature-flag combinations) is
  a secondary, unofficial source; it was not cross-checked against the
  pinned source's `features/src/lib.rs` in this sweep, and is included above
  only as a breadth-sweep lead, not a verified figure.
- **`AgentsToml`'s native multi-agent subsystem was not exercised** — its
  existence and field shapes were read from source
  (`config_toml.rs:661-690`), but whether/how it could substitute for or
  complement a Claude-orchestrated cross-vendor team (e.g., could Codex's own
  named subagent roles be dispatched *from inside* a `codex exec` call that
  Claude Code drives via MCP) is unexplored and is a candidate follow-up
  question, not answered here.
- **Anthropic/Claude Code's own MCP-server-exposure story for Claude Code
  itself was not researched** — this sweep answered "can Claude call Codex
  as an MCP tool" but not "can Codex call Claude the same way"; the question
  as posed is asymmetric (Claude Code as orchestrator) so this was treated as
  out of scope, but flagging it since the earlier handoff report may not have
  covered it either.
- **discussions channel** (`has_discussions: true` for openai/codex) was
  **not searched** — the adapter's `search()` only builds `is:issue`/`is:pr`
  queries against `search/issues`; GitHub Discussions are a separate GraphQL
  surface the adapter does not cover (`python/src/kb_setup/research/
  trackers.py` has no discussions branch). If discussions carry design
  rationale for `app-server`'s experimental status, it was not found here.

## GitHub repos touched

- [openai/codex](https://github.com/openai/codex) — primary source read
  (`codex-rs/cli`, `codex-rs/mcp-server`, `codex-rs/app-server*`,
  `codex-rs/exec`, `codex-rs/config`) at the pinned local clone; tracker
  search across 10 terms; issues #38545, #35596, #19816, #40702, #40149,
  #22998, #4181, #4776, #33294, #34215, #38721, #37767, #35283, #38365,
  #33789, #36562, #39406, #32984, #37471, #39198, #37903, #41188, #39482,
  #40953, #40941, #40377, #40919 read/cited (titles + snippets from search;
  full body fetched for #38545 via Firecrawl).
- [anthropics/claude-code](https://github.com/anthropics/claude-code) —
  tracker search across 5 terms; issues #89509, #88085, #71640, #87596,
  #87595, #78196, #80036, #90264, #86471, #90206, #85060, #85099, #87323,
  #84658, #78996 read (titles + snippets).
- [mar3co/fable-orchestrator](https://github.com/mar3co/fable-orchestrator) —
  full issue/PR enumeration (7 issues, 15 PRs) via `gh issue list`/`gh pr
  list --state all`; tracker search across 3 terms; issue #16 full body read.
- [johnlindquist/codex-imps](https://github.com/johnlindquist/codex-imps) —
  breadth-sweep secondary source, unofficial reverse-engineered token-cost
  table for codex's system prompt (`docs/ISOLATION.md`); not independently
  verified in this sweep.
- [openclaw/openclaw](https://github.com/openclaw/openclaw) (via DeepWiki
  mirror) — breadth-sweep secondary source corroborating the `app-server`
  JSON-RPC-over-stdio protocol shape.
- [yishentu/claudian](https://github.com/yishentu/claudian) — breadth-sweep
  secondary source, same corroboration (`src/providers/codex/AGENTS.md`).
- [slopus/happy](https://github.com/slopus/happy) — breadth-sweep secondary
  source, same corroboration (`docs/plans/codex-app-server-migration.md`).
- [bullorosso/etienne](https://github.com/bullorosso/etienne) — breadth-sweep
  secondary source, same corroboration (`docs/codex-mode-comparison.md`).
