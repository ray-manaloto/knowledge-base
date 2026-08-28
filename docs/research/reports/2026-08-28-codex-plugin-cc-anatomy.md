# How `openai/codex-plugin-cc` works (installed as the `codex` plugin, v1.0.6)

Status: COMPLETE.

Question (Ray, verbatim): "did we review how https://github.com/openai/codex-plugin-cc works?" — answer: no, until now.

## Graph orientation (control arm)

`mise run kb-query -- "codex plugin app-server transport companion"` returned 612 nodes, all
from **`codex-rs`** (the openai/codex CLI source, already an ingested corpus source) and unrelated
noise (opensymphony-codex, pkl-server, vfox, mattpocock-skills, opencode). **Zero nodes** from
`openai/codex-plugin-cc` itself — confirms the team-lead's stated control: this plugin repo has no
source in the corpus. Proceeding on direct file reads of the installed plugin + `gh api` for upstream.

## Tree (installed copy, `~/.claude/plugins/cache/openai-codex/codex/1.0.6/`)

```
.claude-plugin/plugin.json      — manifest: name=codex, version=1.0.6, author=OpenAI
CHANGELOG.md, LICENSE, NOTICE
agents/codex-rescue.md          — the one agent
commands/
  adversarial-review.md  cancel.md  rescue.md  result.md  review.md  setup.md  status.md  transfer.md
hooks/hooks.json                — SessionStart, SessionEnd, Stop
prompts/
  adversarial-review.md         — template interpolated into a structured-output turn
  stop-review-gate.md           — template for the Stop hook's review turn
schemas/review-output.schema.json — JSON schema forcing structured review output
scripts/
  app-server-broker.mjs         — a per-repo Unix-socket JSON-RPC proxy in front of ONE `codex app-server`
  codex-companion.mjs           — the CLI entry point invoked by every command/hook (subcommands: setup, review,
                                   adversarial-review, task, transfer, task-worker, status, result,
                                   task-resume-candidate, cancel)
  session-lifecycle-hook.mjs    — SessionStart/SessionEnd hook body
  stop-review-gate-hook.mjs     — Stop hook body (900s timeout in hooks.json)
  lib/
    app-server-protocol.d.ts    — TS types for the app-server JSON-RPC surface
    app-server.mjs              — CodexAppServerClient: spawns/talks to `codex app-server`
    args.mjs, broker-endpoint.mjs, broker-lifecycle.mjs, claude-session-transfer.mjs,
    codex.mjs, fs.mjs, git.mjs, job-control.mjs, process.mjs, prompts.mjs, render.mjs,
    state.mjs, tracked-jobs.mjs, workspace.mjs
skills/
  codex-cli-runtime/SKILL.md    — internal contract, used only by codex-rescue subagent
  codex-result-handling/SKILL.md — internal contract for presenting helper output
  gpt-5-4-prompting/            — prompt-writing reference (SKILL.md + 3 reference docs)
```

`CLAUDE_PLUGIN_DATA` (`~/.claude/plugins/data/codex-openai-codex/state/`) stores, per-workspace
(keyed by a slug of the repo path + hash, e.g. `graphify-10ff02207a5d937e/`): `state.json` (config,
e.g. `stopReviewGate`) and `jobs/<job-id>.json` + `.log` — one file pair per tracked job (task or
review), containing the job record (status, threadId, turnId, summary, pid, logFile) and a plain-text
progress log. This IS this repo's own prior usage — several `graphify-*` and `modern_cpp_kb-*` job
files exist here already, meaning this plugin has been used in this session's own machine before.

## (a) TRANSPORT — confirmed: `codex app-server` JSON-RPC, NOT `codex exec`

`scripts/lib/app-server.mjs` (`CodexAppServerClient`) spawns/connects to **`codex app-server`**
and speaks line-delimited JSON-RPC over its stdio (or over a broker socket — see below). This is
categorically different from the `codex exec --sandbox … -` stdin-pipe pattern this repo's own
`.claude/rules/ai-cli-invocation.md` documents and from `fable-orchestrator`'s `codex exec` calls
(see §g). Every companion action (`review`, `adversarial-review`, `task`) goes through
`runAppServerTurn` / `runAppServerReview` (imported into `codex-companion.mjs:10-23` from
`./lib/codex.mjs`), which drive the JSON-RPC methods `turn/start`, `review/start`,
`thread/compact/start` (the `STREAMING_METHODS` set in `app-server-broker.mjs:12`) and
`turn/interrupt` (`app-server-broker.mjs:36-38`, called from `interruptAppServerTurn` on
`/codex:cancel`, `codex-companion.mjs:976`).

**The broker layer** (`app-server-broker.mjs`) is a `net.createServer` Unix-socket (or the
`broker-endpoint.mjs`-parsed target) JSON-RPC proxy sitting in front of exactly ONE
`CodexAppServerClient.connect(cwd, { disableBroker: true })` (`app-server-broker.mjs:68`) — i.e. one
live `codex app-server` process per repo/workspace, shared across concurrent Claude Code sessions in
that workspace. It enforces single-flight semantics: a second caller gets a `BROKER_BUSY_RPC_CODE`
JSON-RPC error (`app-server-broker.mjs:170-182`) unless it's a `turn/interrupt` on the currently
streaming thread, which is let through directly (`allowInterruptDuringActiveStream`,
`app-server-broker.mjs:170-171,184-195`). Every incoming socket also gets `initialize`/`initialized`
handshake responses and a `broker/shutdown` RPC that tears the whole broker + underlying app-server
down (`app-server-broker.mjs:146-164`). So: **one companion process per workspace, arbitrated by a
broker; the broker is the actual long-lived process, and it owns one `codex app-server` child.**

This is what the `codex-cli-runtime` skill name and the `CODEX_COMPANION_SESSION_ID` /
`CODEX_COMPANION_TRANSCRIPT_PATH` env vars the task description flagged point at — pending confirmation
of exactly where those two vars are set/read (not yet located in the files read so far; continuing).

## (b) Prompt/context passing and result return

**In (never files, never the Claude transcript directly):** `buildTurnInput(prompt)` wraps the prompt
string as `[{ type: "text", text: prompt, text_elements: [] }]` and ships it as the `input` field of
a `turn/start` JSON-RPC request (`lib/codex.mjs:86-88,1136-1142`). The prompt text itself comes from
`readTaskPrompt()` in `codex-companion.mjs:643-650` — positional CLI args joined, OR `--prompt-file`
read via `fs.readFileSync`, OR piped stdin (`readStdinIfPiped`). There is no automatic inclusion of
the Claude conversation transcript in a task/review turn — only `/codex:transfer` reads the Claude
transcript file (see §c). Review turns instead pass a structured `target` object
(`{ type: "uncommittedChanges" }` or `{ type: "baseBranch", branch }`, `codex-companion.mjs:259-269`)
straight to the app-server's native `review/start` RPC, which does its own git diff collection
server-side — Claude never assembles the diff for a native `/codex:review`. Only
`/codex:adversarial-review` builds a prompt Claude-side (`collectReviewContext` + `git.mjs`, then
`buildAdversarialReviewPrompt` interpolates `prompts/adversarial-review.md`,
`codex-companion.mjs:241-250,409-410`) and forces a JSON `outputSchema`
(`schemas/review-output.schema.json`) on the turn, so that path IS structured.

**Out:** JSON-RPC notifications stream back over the SAME live connection — `thread/started`,
`turn/started`, `item/started`/`item/completed` (per-item: `commandExecution`, `fileChange`,
`mcpToolCall`, `agentMessage`, `reasoning`, `collabAgentToolCall`, `exitedReviewMode`, `webSearch`),
`turn/completed`, `error` (`lib/codex.mjs:490-557`). `captureTurn()` (`lib/codex.mjs:559-611`)
accumulates these into a `TurnCaptureState` and resolves a promise on `turn/completed` (or on an
INFERRED completion 250ms after a `final_answer` agentMessage with no pending subagent turns —
`scheduleInferredCompletion`, `lib/codex.mjs:373-394` — a heuristic completion detector, not a
protocol guarantee). The final shape returned to the CLI layer is plain fields, not raw JSON-RPC:
`{ status, threadId, turnId, finalMessage, reasoningSummary, turn, error, stderr, fileChanges,
touchedFiles, commandExecutions }` (`lib/codex.mjs:1146-1159`). `codex-companion.mjs` then renders
this either as human text (`renderTaskResult`/`renderReviewResult`, `lib/render.mjs`, not yet read
line-by-line but imported at `codex-companion.mjs:56-65`) or, with `--json`, as the raw payload
object (`outputCommandResult`, `codex-companion.mjs:99-101`). Structured (schema-validated) output is
opt-in per turn via `outputSchema` on `turn/start` — used only by `/codex:adversarial-review` and
parsed with `parseStructuredOutput()` (`lib/codex.mjs:1188-1213`, a bare `JSON.parse` with a
`parseError` field on failure — not schema-validated client-side, despite the schema file existing;
the schema is passed to the app-server as the request's `outputSchema`, so validation, if any, is
server-side and unconfirmed from these files alone).

## (c) Session continuity / thread resume

Each Codex "thread" is the app-server's own native session object, addressed by `threadId` and
persisted **by codex itself** (`thread/start` with `ephemeral: false` for `task`,
`lib/codex.mjs:1117`; reviews stay `ephemeral: true`, `lib/codex.mjs:1013`). The plugin layers THREE
resume mechanisms on top:
1. **`--resume-last`** (`task` command): `resolveLatestTrackedTaskThread()`
   (`codex-companion.mjs:336-356`) looks at this plugin's OWN job-tracking file (not codex's thread
   list) for the newest `task`-class job belonging to the current Claude session id
   (`CODEX_COMPANION_SESSION_ID`, filtered via `filterJobsForCurrentClaudeSession`,
   `codex-companion.mjs:298-304`), and falls back to codex's `thread/list` RPC filtered by name prefix
   `"Codex Companion Task"` (`findLatestTaskThread`, `lib/codex.mjs:1162-1182`) only when there is no
   Claude session id at all.
2. **Thread NAMING for discoverability**: every non-resumed task thread is named
   `"Codex Companion Task: <56-char prompt excerpt>"` via `thread/name/set`
   (`buildTaskThreadName`/`startThread`, `lib/codex.mjs:107-110,732-748`) — this is how
   `thread/list … searchTerm:` finds prior threads later; a version of `codex app-server` that
   doesn't support `thread/name/set` degrades silently (caught and swallowed if the error message
   contains "unknown variant"/"unknown method", `lib/codex.mjs:738-745`).
3. **`/codex:transfer`**: a ONE-WAY import of an existing Claude Code session transcript INTO a new
   Codex thread via the `externalAgentConfig/import` RPC (`lib/codex.mjs:701-730,1058-1093`),
   deduplicated via a SHA-256 content hash recorded in `~/.codex/external_agent_session_imports.json`
   (`importedThreadIdForSource`, `lib/codex.mjs:661-679`) — this is the Claude→Codex handoff path, not
   a per-turn context feed.

Reviews are NOT persisted the same way — confirmed by upstream issue #529 ("Review commands should
persist their Codex threads (write rollouts) like task runs do", still open), matching what
`runAppServerReview` shows: it never calls `thread/name/set` and always starts `ephemeral: true`.

## (d) Timeout / token-budget / effort knobs

- **Reasoning effort**: `none | minimal | low | medium | high | xhigh` (`VALID_REASONING_EFFORTS`,
  `codex-companion.mjs:71`), passed straight through as the `effort` field on `turn/start`
  (`lib/codex.mjs:1140`) — **left UNSET (codex's own default) unless the user explicitly asks**, per
  `skills/codex-cli-runtime/SKILL.md:21`. No forced default here, unlike `fable-orchestrator`'s hard
  default of `high` (see §g table).
- **Model**: unset by default too (`skills/codex-cli-runtime/SKILL.md:22`); one alias,
  `spark → gpt-5.3-codex-spark` (`MODEL_ALIASES`, `codex-companion.mjs:72`).
- **Sandbox / write mode**: `--write` maps to `sandbox: "workspace-write"`; its absence to
  `"read-only"` (`executeTaskRun`, `lib/codex.mjs:491`) — approvalPolicy is hardcoded `"never"`
  (`buildThreadParams`, `lib/codex.mjs:67`), i.e. **fully autonomous, no interactive approval prompts
  ever surface** through this transport.
- **Timeouts**: `status --wait` polls up to `DEFAULT_STATUS_WAIT_TIMEOUT_MS = 240000` (4 min,
  `codex-companion.mjs:69`, `--timeout-ms` overridable). The Stop-gate review itself is bounded by
  `STOP_REVIEW_TIMEOUT_MS = 15 * 60 * 1000` (15 min) inside `stop-review-gate-hook.mjs:16`, wrapped
  inside the OUTER 900s (15 min) `hooks.json:32` Stop-hook timeout declared to Claude Code — i.e. the
  two 15-minute bounds are set independently in two files and happen to agree; nothing enforces they
  stay in sync. **No per-turn/task timeout at all** for `task`/`review` invoked directly (not via the
  Stop hook) — confirmed by open issues #520 ("`task --background`: detached worker has no timeout or
  stall watchdog") and #183 ("`runTrackedJob`/`captureTurn` can hang in `phase: finalizing`
  indefinitely (no timeout)"). This is the single biggest reliability gap versus `fable-orchestrator`'s
  lane (see §g).
- **No token-budget knob found anywhere** in these scripts — no `max_tokens`, no context-window
  parameter surfaced to the user; token/cost control is entirely `effort` + `model` + `FAST MODE`-style
  service-tier knobs on the codex CLI side, not this plugin's.

## (e) Stop-time review gate

Hooked on `Stop` (`hooks.json:26-36`, `stop-review-gate-hook.mjs`, 900s timeout). **Off by default** —
gated by a per-workspace `stopReviewGate` boolean in `CLAUDE_PLUGIN_DATA/state/<slug>/state.json`,
toggled only via `/codex:setup --enable-review-gate` (`codex-companion.mjs:229-235`); when off, the
hook just logs a note about any still-running background job and returns with NO decision object
(`stop-review-gate-hook.mjs:154-157`) — i.e. it is a genuine no-op, not merely non-blocking (matches
upstream issue #684, a DIFFERENT bug where `/codex:setup --enable-review-gate` writes the flag to a
state root the hook doesn't read, silently failing open even when "enabled").

When ON: it builds a prompt from `prompts/stop-review-gate.md` interpolated with the
`last_assistant_message` the hook receives on stdin (`buildStopReviewPrompt`,
`stop-review-gate-hook.mjs:48-57`), then **spawns a synchronous CHILD `codex-companion.mjs task --json`
process** (`spawnSync`, NOT the same in-process JSON-RPC connection — `runStopReview`,
`stop-review-gate-hook.mjs:98-140`) bounded at the 15-min timeout. The task's raw output is expected to
start with a literal `ALLOW:` or `BLOCK:<reason>` first line (`parseStopReviewOutput`,
`stop-review-gate-hook.mjs:69-96`) — a hand-rolled two-token protocol, not the JSON review schema used
by `/codex:adversarial-review`. On `BLOCK:`, the hook emits `{"decision":"block","reason":…}` to
stdout — the standard Claude Code Stop-hook block mechanism — forcing the session to continue instead
of stopping. On any failure mode (empty output, non-zero exit, timeout, invalid JSON, an answer that's
neither `ALLOW:` nor `BLOCK:`), it also BLOCKS, with a message telling the user to run
`/codex:review --wait` manually or bypass the gate — i.e. **the gate fails CLOSED on a broken review,
not open** (contrast with `stop-review-gate-hook.mjs`'s own fail-open when merely disabled). Two
matching upstream bugs on this exact mechanism: #548 ("Stop-review gate hook loops until
`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` (missing `stop_hook_active` guard)") and #676 ("Stop review gate
fails open when hook stdin is malformed JSON" — the opposite failure direction from what the code
above suggests, meaning the fail-closed behavior above has at least one bypass via malformed hook
input).

## (f) What it bundles / requires

**Bundles**: 1 agent (`codex-rescue`), 8 commands (`rescue`, `setup`, `review`, `adversarial-review`,
`transfer`, `status`, `result`, `cancel`), 3 hooks (`SessionStart`, `SessionEnd`, `Stop`), 3 internal
skills (`codex-cli-runtime`, `codex-result-handling`, `gpt-5-4-prompting`), 1 JSON output schema, 2
prompt templates. **No `.mcp.json` anywhere in the tree** — confirmed by the full file listing above.
This plugin does **NOT** register an MCP server and does not speak MCP to Claude Code at all; "MCP"
only appears inside the app-server JSON-RPC protocol's OWN concept of `mcpToolCall` items (codex
calling ITS OWN configured MCP tools mid-turn, `lib/codex.mjs:252-253,283-284`) — unrelated to how
Claude reaches this plugin. Claude reaches it purely through ordinary command/agent/hook invocation of
a local Node script.

**Requires**: Node + npm on PATH (`binaryAvailable("node"/"npm", …)`, `codex-companion.mjs:184-185`),
the `codex` CLI installed globally (`npm install -g @openai/codex`, checked via
`codex --version` AND `codex app-server --help` both succeeding — `getCodexAvailability`,
`lib/codex.mjs:886-904` — i.e. it explicitly checks for the app-server subcommand's presence, not
just any codex binary), and `codex login` (ChatGPT OAuth, device-auth, or API key — checked via the
app-server's own `account/read` RPC, `getCodexAuthStatusFromClient`, `lib/codex.mjs:868-884`). **No
codex CLI version PIN found anywhere** in the plugin — `plugin.json` (`.claude-plugin/plugin.json`)
has no dependency/engines field, and `getCodexAvailability` only checks binary presence, not a version
string — so this plugin is coupled to whatever `codex app-server`'s JSON-RPC surface looks like on
the user's globally-`npm install -g`'d CLI, with no compatibility gate. This is a **structural**
difference from `fable-orchestrator`'s `codex exec` invocation, which pins no version either but at
least targets `codex exec`'s far more stable stdin/stdout CLI surface rather than an internal RPC
protocol.

## (g) Comparison vs `fable-orchestrator`'s `codex-implementer`

| Axis | `openai/codex-plugin-cc` (installed `codex` plugin) | `fable-orchestrator`'s `codex-implementer` lane |
|---|---|---|
| Transport | `codex app-server` JSON-RPC over stdio, brokered through a per-workspace Unix-socket proxy (`app-server-broker.mjs`) shared across concurrent Claude sessions | `codex exec --sandbox workspace-write -c model_reasoning_effort=… --skip-git-repo-check --cd "$(pwd)"`, one-shot CLI process per task, via `run-lane.sh` |
| Process model | ONE long-lived `codex app-server` child per workspace, kept alive across the whole Claude session (started on demand, torn down on `SessionEnd`) | Fresh detached `codex exec` process per task, launched + watchdog-wrapped + reaped by `run-lane.sh`; no shared daemon |
| Prompt delivery | JSON-RPC `input` array field on `turn/start`, built from CLI args / `--prompt-file` / stdin | Spec written to a `mktemp` prompt file, `cat`'d into codex's stdin — no RPC |
| Result shape | Structured JSON-RPC notification stream (`item/started`, `item/completed`, `turn/completed`, …) captured into a typed state object; optional JSON-Schema-validated final message for `/codex:adversarial-review` only | Plain captured stdout/stderr log (`$LOG`), graded `captured` / `captured-fail` / `claim-only` by whether the verification command's execution is visible in the log — no structured schema at all |
| Session continuity | Native `threadId` persisted by codex itself; plugin layers `--resume-last` (own job-tracking file + session-id filter) and thread naming/search on top; `/codex:transfer` does a ONE-TIME Claude→Codex transcript import | None — each dispatch is a fresh `codex exec`; the caller's own doctrine (this repo's `orchestrator-routing`) handles cross-task continuity, not the lane itself |
| Effort default | Unset (defers to codex's own default) unless the user asks | Hardcoded default `high`, overridable only via the dispatch's `EFFORT:` line |
| Timeout | **None** at the turn/task level (open bugs #520, #183 confirm); only the Stop-gate's own wrapper is bounded (15 min) | A pure-bash watchdog wraps every launch (`run-lane.sh … <timeout-seconds>`, default 1800s / dispatch-configurable), because the harness caps a foreground call at 10 min and a background launch needs a wall-clock ceiling of its own |
| Approval / sandbox | `approvalPolicy: "never"` hardcoded — fully autonomous; sandbox toggled only read-only vs workspace-write via `--write` | `--sandbox workspace-write` always, never `danger-full-access` — same posture, but codex's own approval semantics aren't touched at all (bypassed identically by both) |
| Review gate | An opt-in Stop-hook that BLOCKS session end pending a fresh Codex review of the last turn — fails CLOSED on a broken review, fails OPEN when merely disabled or (per issue #676) on malformed hook stdin | No equivalent — review is a separate reviewer lane/agent (`codex-reviewer`), invoked explicitly by the architect, never gates session end |
| Evidence discipline | The plugin reports raw stdout/JSON; NO grading of "did the verification command actually run and pass" — that judgment is left entirely to whatever reads the output (a human, or `codex-result-handling`'s presentation rules) | Explicit `VERIFIED: captured / captured-fail / claim-only` grade is the lane's own contractual job — "codex said it works" is never accepted as evidence |
| Commit ownership | Not modeled by the plugin at all — codex may or may not commit; nothing here inspects `git log`/`reflog` for foreign writes, stability anchors, or backstop-commits an uncommitted tree | Explicit `BASELINE`/`BRANCH` stability-anchor checks before AND after the run, reflog inspection for foreign rewinds, and a backstop commit if codex leaves the tree dirty |
| Premise verification | None — no concept of a spec, let alone a PREMISES block | A hard preflight gate: aborts before launch if the dispatch lacks a `PREMISES` block, or (when an emission/security-tier row is present) a `PREMISES-VERIFIED:` attestation |
| Concurrency safety | The broker enforces single-flight per workspace (`BROKER_BUSY_RPC_CODE` on a second concurrent caller) — but is shared ACROSS Claude sessions in that workspace, and upstream issue #671 shows any session's `SessionEnd` tears down the shared broker, killing OTHER sessions' in-flight jobs | Each lane invocation gets its own `mktemp` spec file and its own detached process; parallel lanes are isolated by construction (explicitly documented to avoid "fixed paths corrupt each other") |
| Cost/token controls | None beyond effort/model/service-tier; `FAST MODE` (`service_tier=fast`) exists on both sides via `-c` flags | `LANE_CODEX_FAST=1` env var maps to the same `-c service_tier=fast -c features.fast_mode=true` |
| Known reliability gaps (upstream, all OPEN as of this read) | Broker leaks/orphans (#543: 34 chains/272 procs/~2.2GB; #605; #629 leaks ~50 processes per test run); SessionEnd/Stop hook timeout races on Windows (#403, #530, #670); duplicate env exports crash the Bash tool after ~28 session starts (#661, #664); `--resume` flag-vs-prompt-text parsing ambiguity (#570, #539) | Not independently verified in this session — `fable-orchestrator` is closed-source relative to this KB's read access; no equivalent public issue tracker was consulted |

**Bottom line difference in one sentence**: `codex-plugin-cc` is OpenAI's own always-on companion
transport — a shared, long-lived, JSON-RPC-native process reused across a whole Claude session,
optimized for low-latency interactive review/task/resume — while `fable-orchestrator`'s
`codex-implementer` is a one-shot, heavily-instrumented process-supervision WRAPPER around the far
simpler `codex exec` CLI surface, optimized for auditable, isolated, spec-gated delegation with an
explicit evidence grade. They are not competing implementations of the same idea; they are transport
choices for two different reliability postures (throughput/continuity vs. auditability/isolation).

## What our transport recommendations already cover, and what they do not

The team's baseline research (`docs/research/reports/2026-08-28-agent-team-transport.md` §3, not
re-read line-by-line in this pass — flagging for cross-check by whoever owns that doc) argues for
typed output, resume, and file-first prompt delivery as transport improvements for THIS repo's own
Claude↔Codex path. Cross-referencing against what `codex-plugin-cc` demonstrates in production:

- **Typed output**: `codex-plugin-cc` PARTIALLY validates this — its `outputSchema` mechanism exists
  and is used for `/codex:adversarial-review`, but is NOT used for the default `/codex:review`
  (native app-server review, free-text) or for `task` (free-text `finalMessage`) — i.e. even OpenAI's
  own plugin treats schema-typed output as the exception, not the rule, for its highest-volume path
  (`task`). This is evidence FOR typed output being valuable (it exists and is reached for when
  structure actually matters) but also evidence that a JSON-RPC transport does not make typed output
  free — someone still has to define+wire the schema per call-site.
- **Resume**: `codex-plugin-cc`'s three-mechanism resume story (native threadId + plugin-side
  job/session tracking + one-way transcript import) is considerably richer than "resume" as a single
  concept — it distinguishes SAME-Claude-session resume, cross-session resume, and one-time
  cross-tool migration. If our transport recommendation only proposes "resume a thread," it should
  specify WHICH of these three shapes it means; conflating them is where `codex-plugin-cc` itself
  shows friction (issue #570/#539: `--resume` as a flag vs. as prompt text is ambiguous).
- **File-first prompt delivery**: NOT what `codex-plugin-cc` does for its primary paths — it uses
  JSON-RPC field delivery (`turn/start.input`), not a file `cat`'d into stdin. `fable-orchestrator`'s
  `codex-implementer` is the one using file-first delivery (via `codex exec`'s stdin), specifically to
  avoid quoting hazards under a harness Bash-analyzability guard that has nothing to do with codex
  itself. So file-first is a `codex exec`-transport-specific mitigation, not something the JSON-RPC
  transport needs or benefits from — if this repo were to consider adopting an app-server-style
  transport, the file-first recommendation would not carry over.
- **NOT covered by our stated recommendations, but worth flagging given what this plugin's issue
  tracker shows**: (1) NO timeout at the turn level is a demonstrated, currently-open production bug
  class (#520, #183) — any transport recommendation for this repo should treat a per-call timeout as
  load-bearing, not optional, which `fable-orchestrator`'s watchdog already does and our own
  `long-running-command-hangs.md` doctrine already independently arrived at; (2) shared-daemon
  concurrency hazards (#671: one session's teardown kills another's in-flight job) are a real cost of
  the "long-lived shared process" transport shape that a one-shot-process transport (`codex exec`)
  structurally avoids — this is a concrete point in favor of this repo's/`fable-orchestrator`'s
  per-invocation-process model over a shared-daemon model, if that tradeoff hadn't already been made
  explicit elsewhere.

## Not measured / out of scope for this pass

- `lib/render.mjs` (the exact human-readable rendering of task/review results) — not read line by
  line; only its export surface was seen.
- `lib/git.mjs`, `lib/prompts.mjs`, `lib/state.mjs`, `lib/job-control.mjs`, `lib/tracked-jobs.mjs`,
  `lib/workspace.mjs`, `lib/args.mjs`, `lib/broker-endpoint.mjs`, `lib/process.mjs`,
  `lib/claude-session-transfer.mjs`, `lib/fs.mjs`, `app-server-protocol.d.ts` — read only via what
  other files imported from them; not opened directly. Nothing above depends on their internals beyond
  what's cited.
- `commands/*.md`, `agents/codex-rescue.md`, `prompts/adversarial-review.md`,
  `prompts/stop-review-gate.md`, `skills/gpt-5-4-prompting/**` — not read; the two SKILL.md files that
  were read (`codex-cli-runtime`, `codex-result-handling`) fully cover the transport-relevant contract
  the task asked about.
- The app-server's OWN JSON-RPC method surface beyond what's used here (`app-server-protocol.d.ts`
  types were not enumerated) — e.g. whether `codex app-server` exposes anything for token-budget
  control was inferred as "not surfaced by this plugin," not confirmed absent from the protocol
  itself.
- Upstream issue full-text bodies were not read — only titles from `search/issues`, which is sufficient
  to confirm the CLASS of each bug (control-armed: nonsense-term search returned 0, `is:issue`/`is:pr`
  filters split cleanly) but not root-cause detail.
- `fable-orchestrator`'s `scripts/run-lane.sh` itself was not read directly — everything in the
  comparison table about it is drawn from `codex-implementer.md`'s description of what the script
  does, not from the script's own source.

## GitHub repos touched

- [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) — the plugin under review.
  Upstream: default branch `main`, `pushed_at: 2026-07-08T00:17:31Z` (**~7.5 weeks stale relative to
  today, 2026-08-28** — the installed v1.0.6 matches the latest upstream tag `v1.0.6`, so "stale" here
  means upstream itself hasn't shipped since, not that the install is behind), 32,475 stargazers,
  issues enabled, discussions disabled, 671 total issues+PRs (control-armed: a nonsense-term search on
  the same repo returned 0, confirming the `repo:` qualifier discriminates and these are real counts,
  not an unscoped org-wide search)
- [openai/codex](https://github.com/openai/codex) — implied runtime dependency (`codex app-server`,
  `npm install -g @openai/codex`); already an ingested KB source as `codex-rs`, confirmed present via
  the mandatory graph query above
- `mar3co/fable-orchestrator` — read via its locally-installed plugin cache
  (`~/.claude/plugins/cache/fable-orchestrator/fable-orchestrator/1.21.0/agents/codex-implementer.md`),
  not a public GitHub URL resolved in this pass — flagging in case it has a public repo worth the same
  `gh api` treatment in a follow-up.
