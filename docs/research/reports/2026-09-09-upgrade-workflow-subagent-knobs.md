# Upgrade pipeline: workflow + subagent customisation knobs

Read-only fact-finding report. Written incrementally. Today: 2026-09-09.

## 1. Workflow script API (from the `workflow-authoring` skill, verbatim where short)

Source: the `workflow-authoring` skill body returned by the Skill tool this session
(not a repo file — this skill's content lives in the harness, not under
`sources/claude-code/`; no `file:line` to cite for this subsection).

### `meta` literal (required, PURE LITERAL — no variables/calls/spreads/interpolation)

```js
export const meta = {
  name: 'find-flaky-tests',
  description: 'Find flaky tests and propose fixes',   // one-line, shown in permission dialog
  phases: [                                             // one entry per phase() call
    { title: 'Scan', detail: 'grep test logs for retries' },
    { title: 'Fix', detail: 'one agent per flaky test' },
  ],
}
```

Required fields: `name`, `description`. Optional: `whenToUse` (shown in the workflow
list), `phases`. `phase()` calls must reuse the SAME titles as `meta.phases` entries
(matched exactly) — a `phase()` call with no matching `meta.phases` entry still gets
its own progress group, it just isn't pre-declared. Add `model` to a `phase` entry
in `meta.phases` when that phase uses a specific model override.

### `agent(prompt, opts)` — the full opts object

```
agent(prompt: string, opts?: {
  label?: string,
  phase?: string,
  schema?: object,        // JSON Schema; forces a StructuredOutput tool call
  model?: string,         // overrides model for THIS call; omit to inherit session model
  effort?: string,        // 'low'|'medium'|'high'|'xhigh'|'max'; omit to inherit session effort
  isolation?: 'worktree', // fresh git worktree per agent; EXPENSIVE (~200-500ms + disk); only when
                          // parallel agents mutate files and would conflict; auto-removed if unchanged
  agentType?: string,     // custom subagent type, e.g. 'general-purpose', 'code-reviewer' — resolved
                          // from the SAME REGISTRY as the Agent tool. Composes with schema (a
                          // StructuredOutput instruction is appended to the custom agent's system prompt).
}): Promise<any>
```

- Without `schema`: returns the subagent's final text as a string (subagents are told
  their final text IS the return value, not a human-facing message — they return raw data).
- With `schema`: returns the validated object. Schema needs `{type:'object', properties:{...}}`
  at root; `required` must be a subset of `properties`; an unsatisfiable schema throws
  at `agent()` call time.
- Returns `null` if the user skips the agent mid-run, or the subagent dies on a terminal
  API error after retries — filter with `.filter(Boolean)`.
- `opts.label` overrides the display label.
- `opts.phase` explicitly assigns the call to a progress group — needed inside
  `pipeline()`/`parallel()` stages to avoid races on the global `phase()` state (same
  phase string -> same group box).
- `opts.model` / `opts.effort`: default is to OMIT both (inherit the resolved session
  model/effort) unless highly confident a different tier fits.
- Workflow agents can reach all session-connected MCP tools via ToolSearch (schemas load
  on demand per agent) — EXCEPT interactively-authenticated MCP servers (e.g. claude.ai),
  which may be absent in headless/cron runs.
- Subagents get the SAME CLAUDE.md files injected at start as the parent got, except
  built-in agent types that omit them (Explore, Plan) — don't tell them to re-read those
  files; name the specific rule a stage needs, if any.

### `agentType` addressability — directly answers the team-lead's question

`opts.agentType` is how a workflow script addresses a NAMED subagent (this repo's
`.claude/agents/*.md` roster included) — "resolved from the same registry as the Agent
tool". The skill body does not state a model/effort precedence rule for this composition
(i.e., whether the named agent's own frontmatter `model:`/`effort:` wins over an `opts.model`/
`opts.effort` passed alongside `agentType` in the same `agent()` call) — this is a genuine
gap in the skill text, not an oversight in this report. **UNVERIFIED, flagged, not
guessed.** Section 2 below independently establishes the general (Agent-tool, not
workflow-script) precedence rule from this repo's own `CLAUDE.md`.

### `pipeline` / `parallel` / other helpers

- `pipeline(items, stage1, stage2, ...): Promise<any[]>` — each item runs through all
  stages independently, NO barrier between stages (item A can be in stage 3 while item B
  is still in stage 1). DEFAULT for multi-stage work; wall-clock = slowest single-item
  chain, not sum-of-slowest-per-stage. Every stage callback receives `(prevResult,
  originalItem, index)`. A stage that throws drops that item to `null` and skips its
  remaining stages.
- `parallel(thunks: Array<() => Promise<any>>): Promise<any[]>` — concurrent, but a
  BARRIER: awaits all thunks before returning. A throwing thunk resolves to `null` in the
  array (the call itself never rejects) — `.filter(Boolean)` before use. Use ONLY when
  all results are genuinely needed together (dedup across a full set, an early-exit
  count check, or a prompt that references "the other findings").
- `log(message: string): void` — a progress narrator line.
- `phase(title: string): void` — starts a new phase; subsequent `agent()` calls group
  under it in the progress display.
- `args: any` — the value passed to Workflow's `args` input, verbatim (`undefined` if
  not given). Pass arrays/objects as real JSON values in the tool call, NOT as a
  JSON-encoded string (a stringified list arrives as one string and `args.filter`/
  `args.map` throw).
- `budget: {total: number|null, spent(): number, remaining(): number}` — the turn's
  token target from a user "+500k"-style directive. `spent()` is a POOL SHARED across
  the main loop and all workflows, not per-workflow. `remaining()` is `Infinity` when no
  target was set. `total` is a HARD ceiling — once `spent()` reaches it, further
  `agent()` calls throw.
- `workflow(nameOrRef, args?): Promise<any>` — runs another workflow inline as a
  sub-step. Pass a name (same registry as `{name: "..."}`) or `{scriptPath}`. The child
  shares the parent's concurrency cap, agent counter, abort signal, and token budget; its
  agents appear under a "▸ name" progress group; its tokens count toward
  `budget.spent()`. **Nesting is one level only — `workflow()` inside a child throws.**
  Throws on unknown name / unreadable scriptPath / child syntax error (catchable).

### Concurrency / scale limits

- Concurrent `agent()` calls capped at `min(16, available CPUs - 2)` per workflow;
  excess calls queue.
- Total agent count across a workflow's lifetime capped at 1000 (runaway-loop backstop).
- A single `parallel()`/`pipeline()` call accepts at most 4096 items — more is an
  explicit error, not silent truncation.

### Language constraints

Plain JavaScript, NOT TypeScript (type annotations/interfaces/generics fail to parse).
Async context — use `await` directly. Standard JS built-ins available EXCEPT
`Date.now()` / `Math.random()` / argless `new Date()` — these THROW (they would break
resume). Pass timestamps via `args`; stamp results after the workflow returns; vary
agent prompts/labels by index instead of using randomness. No filesystem or Node.js API
access from the script body itself.

### How a saved workflow is invoked, and how `args` arrive — this repo's own pattern

Verified in this repo: `.claude/workflows/kb-extract.js:34-46` (see Section 1b below)
parses `args` as EITHER an object OR a JSON string, defensively — i.e., this repo's own
saved workflow does not trust that the caller passed a real JSON value even though the
skill's guidance says to always pass one. This is a house pattern to imitate if the
upgrade workflow will also be invoked with hand-typed args.

### Resume semantics

- The tool result includes a `runId`. Resume after a pause/kill/script edit via
  `Workflow({scriptPath, resumeFromRunId})` — the longest UNCHANGED PREFIX of `agent()`
  calls returns cached results instantly; the first edited/new call and everything after
  it runs live. Same script + same args -> 100% cache hit.
- Before diagnosing an empty/unexpected result from a completed workflow: read
  `<transcriptDir>/journal.jsonl` — it records each agent's actual return value; do not
  assume a cached result is non-empty.
- What BREAKS resume: `Date.now()` / `Math.random()` / argless `new Date()` (hence
  disallowed in-script). Fallback with no journal available: read `agent-<id>.jsonl`
  files in the transcript directory and hand-author a continuation script.

### Ultracode section

When a system-reminder confirms ultracode is ON: that opt-in is standing — author and
run a workflow for every substantive task by default; token cost is not a constraint;
multi-phase work (understand -> design -> implement -> review) often means several
workflows in sequence, staying in the loop between them; lean toward orchestrating with
workflows and adversarially verifying findings unless the work is trivial or already
verified; solo only for conversational turns or trivial mechanical edits. When a
reminder says ultracode is OFF, revert to the tool description's opt-in rule (i.e. the
default described at the top of this section — call Workflow for comprehensiveness/
confidence/scale, scout inline first to discover the work-list, then pipeline over it).

### `.claude/workflows/*.js` — what THIS repo's three existing workflows actually use

Confirmed by reading each file's head (-80 lines) plus `grep -n "agent("`:

| Workflow | `agent()` opts actually used | Notes |
|---|---|---|
| `.claude/workflows/kb-extract.js:278` | `agent(promptFor(s), {...})` — schema present (need offset read to see full opts; label/phase used per the file's single `phase()` block at meta) | One `agent()` call inside `parallel()`/pipeline of sources; args accepted as object OR JSON string (`kb-extract.js:34-46`, matches skill's warning about args arriving as a string) |
| `.claude/workflows/kb-tool-review.js:118,131,183,199,216` | Uses `schema` (`CLAIMS_SCHEMA` etc. built inline), multiple phases (`Research`/`Verify`/`Review`/`Synthesize` declared in `meta.phases`), a verifier fan-out with `??` null-coalescing on `agent()`'s null-on-death contract (comment at :136,:153) | Explicitly invoked by **`scriptPath`, never `name`** — the file's own header comment (`kb-tool-review.js:14-19`) documents that `name:` resolves to a STALE CACHED COPY (issue #13: kb-extract.js was edited, re-invoked by name, and returned pre-patch behavior). This is a load-bearing house convention for iterating on a workflow script |
| `.claude/workflows/session-review.js:778,997,1123-1139` | `model` and `effort` explicitly overridden — `agent(prompt, { ...opts, model: 'fable', effort: 'high' })` then a second call `{ ...opts, model: 'opus', effort: 'xhigh' }` (lines 1136,1139) as an escalation pair; a per-lane `CONTRACT` string is prepended to every lane's prompt (line 778) | Also documents its own syntax-check gotcha: `node --check` returns rc=0 on broken code because the file's leading `export` makes the CJS parser bail early — the real check pipes the body through an IIFE wrapper first (file header comment) |

None of the three repo workflows use `isolation: 'worktree'` or `agentType` in the calls grepped above — this repo's existing house pattern leans on the DEFAULT workflow subagent plus schema/model/effort overrides, not on addressing a named `.claude/agents/*.md` subagent from a workflow script. **This is a gap the upgrade pipeline would be the first to fill if it uses `agentType: 'kb-advisor'` etc.**

### Quality patterns named in the skill (for the upgrade pipeline to pick from)

Adversarial verify (N independent skeptics, kill if >= majority refute); perspective-
diverse verify (distinct lenses per verifier, not N identical refuters); judge panel (N
independent attempts, scored, synthesize from winner grafting runner-up ideas);
loop-until-dry (keep spawning finders until K consecutive rounds return nothing new);
multi-modal sweep (parallel agents searching differently, blind to each other); the
completeness critic ("what's missing — modality not run, claim unverified, source
unread?"); and the "no silent caps" rule — `log()` any bounded coverage (top-N,
no-retry, sampling) rather than let it read as complete.

---

## 2. Subagent frontmatter (Claude Code docs)

**Docs source**: `sources/claude-code-docs/content/en/docs/claude-code/sub-agents.md`
(this repo's pinned mirror clone — a doc source, not the code repo). This is a
DIFFERENT pin from `sources/claude-code.manifest`; the docs mirror has its own
`CLAUDE.md` describing it as "3,900+ docs from 12 sources; active sources
auto-updated four times daily." No `ref`/`commit` pin is recorded for this docs
mirror the way `sources/claude-code.manifest` pins `v2.1.258` — it is a live-refetched
mirror, not a SHA-pinned snapshot, so treat its currency as "as of whenever this repo's
clone was last refreshed," not as a fixed version the way the CHANGELOG citations below
are.

**CHANGELOG source** (version-pinned): `sources/claude-code.manifest` pins
`url = https://github.com/anthropics/claude-code`, `ref = v2.1.258`,
`commit = aef74afe01f65b602258d6102b0da9730ac6f0aa`, `kind = docs`. The CHANGELOG lives
at `sources/claude-code/CHANGELOG.md`.

### Complete frontmatter field table (`sub-agents.md:286-309`, "Supported frontmatter fields")

Only `name` and `description` are required. Verbatim field list:

| Field | Required | Description (condensed from `sub-agents.md:290-308`) |
|---|---|---|
| `name` | Yes | Unique id, lowercase + hyphens. Hooks receive it as `agent_type`. Cannot contain `:` (reserved for plugin-scoped ids like `my-plugin:reviewer`) |
| `description` | Yes | When Claude should delegate to this subagent |
| `tools` | No | Allowlist; inherits every tool available to subagents if omitted. `Skill` should NOT be listed here to preload skills — use `skills` instead |
| `disallowedTools` | No | Denylist, removed from the inherited/specified list. If both set: `disallowedTools` applied first, then `tools` resolved against what remains; a tool in both is removed |
| `model` | No | `sonnet`, `opus`, `haiku`, `fable`, a full model ID (e.g. `claude-opus-5`), or `inherit`. Omitted -> subagent model order (below) |
| `permissionMode` | No | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan`, or `manual` (alias for `default`, needs >=2.1.200). **Ignored for plugin subagents** |
| `maxTurns` | No | Max agentic turns before the subagent stops; output is then marked partial and resumable (partial-marking needs >=2.1.246) |
| `skills` | No | Skills to preload — FULL content injected at startup, not just description. Subagent can still invoke unlisted skills via the Skill tool |
| `mcpServers` | No | MCP servers for this subagent only — a name referencing an already-configured server, or an inline full server config. **Ignored for plugin subagents**. Inline defs need the agent file's folder to be trusted (since v2.1.238) |
| `hooks` | No | Lifecycle hooks scoped to this subagent (PreToolUse/PostToolUse/Stop, converted to SubagentStop). **Ignored for plugin subagents**. Needs the containing folder trusted (project-level) or none needed (user-level `~/.claude/agents/`, or `--agents`-supplied) |
| `memory` | No | `user` / `project` / `local` — persistent memory scope (see table below). Requires auto memory to be ON |
| `background` | No | `true` keeps the subagent backgrounded even if Claude asks foreground |
| `effort` | No | `low`/`medium`/`high`/`xhigh`/`max`; overrides session effort; availability depends on model |
| `isolation` | No | `worktree` — fresh git worktree, branched from the default branch (not parent's HEAD); auto-cleaned if unchanged |
| `color` | No | `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan` |
| `initialPrompt` | No | Auto-submitted first user turn when this agent runs as the MAIN session agent (`--agent`) — not relevant to subagent dispatch |
| `experimental` | No | Map; `cacheTtl: 5m`\|`1h` sets prompt-cache TTL for this subagent's requests (needs >=2.1.248; ignored during usage-credit billing for `1h`) |

Memory scope table (`sub-agents.md:580-584`):

| Scope | Location | Use when |
|---|---|---|
| `user` | `~/.claude/agent-memory/<name-of-agent>/` | remember across all projects |
| `project` | `.claude/agent-memory/<name-of-agent>/` | project-specific, shareable via VCS (recommended default) |
| `local` | `.claude/agent-memory-local/<name-of-agent>/` | project-specific, NOT checked into VCS |

**Not asked for by the team-lead's list but present in the doc and worth flagging for
the upgrade pipeline design**: `disallowedTools`, `maxTurns`, `mcpServers`, `hooks`,
`memory`, `background`, `experimental.cacheTtl`. The team-lead's ask enumerated most of
the important ones (name/description/tools/disallowedTools/model/effort/
permissionMode/maxTurns/skills/hooks/memory/background/isolation/color) — this table
confirms all of those exist verbatim, plus `mcpServers`, `initialPrompt` (main-session
only) and `experimental.cacheTtl` which weren't named in the ask.

### Model precedence — CONFIRMS this repo's CLAUDE.md claim, with one addition

`sub-agents.md:347-352`, "Choose a model": When Claude invokes a subagent, Claude Code
resolves the model in this order:

1. The per-invocation `model` parameter
2. The subagent definition's `model` frontmatter (`inherit` -> main conversation's model)
3. `CLAUDE_CODE_SUBAGENT_MODEL` env var, when set to a model alias or ID
4. The main conversation's model

`sub-agents.md:356`: **"Before v2.1.251, `CLAUDE_CODE_SUBAGENT_MODEL` came first in
this order and overrode both the per-invocation parameter and the frontmatter,
including `model: inherit`."**

This CONFIRMS this repo's `.claude/CLAUDE.md` claim verbatim. Cross-checked against the
CHANGELOG independently (`sources/claude-code/CHANGELOG.md:181`):

> "Changed `CLAUDE_CODE_SUBAGENT_MODEL` to set the default subagent model rather than
> override everything: an agent definition's `model:` and an explicit per-spawn model
> now take precedence over it"

This matches this repo's `.claude/CLAUDE.md` citation of `CHANGELOG.md:62` at tag
`v2.1.251` word-for-word — **the exact line number differs (this pinned CHANGELOG.md
copy has it at line 181, not 62) which is expected**: `CHANGELOG.md` is prepended-to on
every release, so the same entry's line number drifts as newer entries are added above
it; this repo's CLAUDE.md was written against the file as it stood when v2.1.251 was
the newest release. **Not a discrepancy in the claim, only in the citation's line
number, which the CLAUDE.md itself doesn't pin to a specific `claude-code.manifest` SHA
for that citation.**

**One thing CLAUDE.md does NOT mention, found in the same CHANGELOG file and directly
relevant to "tuning knobs":** `sources/claude-code/CHANGELOG.md:13`:

> "Added `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` to apply `CLAUDE_CODE_SUBAGENT_MODEL` (or
> the main model) to every subagent, ignoring per-spawn and agent-definition model
> overrides"

This is a newer env var than the one this repo's CLAUDE.md discusses — it is the
"force everyone onto one model regardless of frontmatter" escape hatch, useful if the
upgrade pipeline ever needs a hard model pin across the whole subagent roster
regardless of individual `.claude/agents/*.md` files. Also at
`sources/claude-code/CHANGELOG.md:2304`: "Fixed `CLAUDE_CODE_SUBAGENT_MODEL` not
applying to teammate processes spawned by agent teams" — i.e. the env var's reach to
AGENT TEAM teammates (as opposed to Agent-tool subagents) was a separate, later fix.
**These two CHANGELOG lines are UNVERIFIED against the current `model-config.md` doc
body** (not re-read past line 521 of 857 for this report — the sub-agents.md
precedence section already gave an unambiguous, doubly-sourced answer to the actual
question asked, and chasing the FORCE var further was out of scope for this pass).

A graph query surfaced a node labelled *"CLAUDE_CODE_SUBAGENT_MODEL outranks
frontmatter and the tool parameter"* sourced to `model-config.md` — this reads as the
graph's community-detection label having picked up the **"Before v2.1.251"** clause
from `sub-agents.md:356` (which does say exactly that, as the PRE-fix behavior) rather
than a live contradiction; the primary doc text read directly above is unambiguous
about the CURRENT order. Flagging this per `probes-need-a-control-arm.md` rather than
silently discarding it: the graph node's `src` field pointing at `model-config.md`
specifically (not `sub-agents.md`) was not independently traced to a specific line in
the unread remainder of that file (lines 522-857) — so treat "the graph found a node
that looks like the old behavior" as the finding, not "the graph is wrong."

### Precedence between project / user / plugin subagents (`sub-agents.md:159-175`)

Explicit priority table when multiple subagents share the same `name`, highest wins:

| Priority | Location | Scope |
|---|---|---|
| 1 (highest) | Managed settings | Organization-wide |
| 2 | `--agents` CLI flag | Current session |
| 3 | `.claude/agents/` | Current project |
| 4 | `~/.claude/agents/` | All your projects |
| 5 (lowest) | Plugin's `agents/` directory | Where plugin is enabled |

Additional precedence details:
- **Nested project directories**: "Project subagents are discovered by walking up from
  the current working directory, so every `.claude/agents/` between there and the
  repository root is scanned. As of v2.1.178, when more than one of these nested
  directories defines the same `name`, Claude Code uses the definition closest to the
  working directory." (`sub-agents.md:173`)
- **Identity is the `name` field only** — subdirectory structure under `.claude/agents/`
  or `~/.claude/agents/` doesn't affect identity or invocation (`sub-agents.md:179`).
  **Exception: plugin `agents/` subfolders DO become part of the scoped id** — a file at
  `agents/review/security.md` in plugin `my-plugin` registers as
  `my-plugin:review:security` (`sub-agents.md:183`).
- **Duplicate names in the SAME directory tree**: Claude Code loads only one, by
  filesystem read order (undocumented precedence) — `/doctor` reports the collision
  (`sub-agents.md:181`).
- **Plugin subagents ignore `hooks`, `mcpServers`, `permissionMode`** in their
  frontmatter — "For security reasons, plugin subagents don't support [these] fields...
  If you need them, copy the agent file into `.claude/agents/` or `~/.claude/agents/`."
  (`sub-agents.md:233`) — directly relevant if the upgrade pipeline's subagents are ever
  distributed as a plugin rather than kept project-local.
- **`--add-dir` directories**: also load that directory's `.claude/agents/`, but Claude
  Code does NOT watch it for live changes the way it watches the main project/user
  dirs, and its inline MCP servers/hooks need separate trust (`sub-agents.md:175,249,497`).

### `agentType` in a Workflow script vs the Agent tool — same registry, precedence UNSTATED for the composed case

Section 1 already flagged that the `workflow-authoring` skill text does not state
whether `opts.model`/`opts.effort` passed ALONGSIDE `agentType: 'some-named-agent'` in
one `agent()` call would override or lose to that named agent's own frontmatter
`model:`/`effort:`. The **general** (non-workflow, Agent-tool) rule from `sub-agents.md`
above is unambiguous — an explicit per-invocation `model` parameter outranks the
agent-definition frontmatter (rule 1 beats rule 2 in the four-step order above) — and
`opts.model`/`opts.effort` in a workflow's `agent()` call is described in the skill text
as exactly this per-invocation parameter for a workflow-spawned agent. **By extension it
is reasonable to expect the SAME precedence order applies** (per-invocation > frontmatter
> `CLAUDE_CODE_SUBAGENT_MODEL` > session model) when `agentType` names a `.claude/agents/`
file from inside a workflow script, since the skill states `agentType` is "resolved from
the SAME REGISTRY as the Agent tool." This is an INFERENCE from two separately-confirmed
facts, not a directly-read statement about the composed case — flagged as such rather
than asserted as read.

### This repo's 7 existing subagents vs the field table — what they use, what they leave unset

Read from `.claude/agents/*.md` frontmatter (`head -8` each):

| Agent | model | effort | tools | color | Unset (of the full field table) |
|---|---|---|---|---|---|
| `kb-adversarial-verifier` | opus | high | Bash, Read, Grep, Glob, Write, Edit | red | disallowedTools, permissionMode, maxTurns, skills, mcpServers, hooks, memory, background, isolation, experimental |
| `kb-advisor` | fable | high | Bash, Read, Grep, Glob | orange | (same list) |
| `kb-codex-advisor` | **unset (neither field present)** | **unset** | Bash, Read, Grep, Glob, Write | teal | model, effort, plus the rest — **deliberate**, per this repo's `CLAUDE.md`: "The 7th, `kb-codex-advisor`, declares NEITHER, and that is deliberate: its reasoning runs inside `codex exec`, pinned there to `--model gpt-5.6-sol` at `xhigh`" |
| `kb-corpus-curator` | sonnet | medium | (none listed — inherits all) | green | tools (deliberately omitted -> inherits every tool), plus the rest |
| `kb-extraction-worker` | sonnet | medium | Read, Write, Grep, Glob | blue | (same list) |
| `kb-synthesist` | opus | high | Bash, Read, Grep, Glob, Write, Edit | purple | (same list) |
| `kb-tool-researcher` | sonnet | high | (none listed — inherits all) | cyan | tools (deliberately omitted), plus the rest |

**None of this repo's 7 agents use**: `disallowedTools`, `permissionMode`, `maxTurns`,
`skills`, `mcpServers`, `hooks`, `memory`, `background`, `isolation`, `color` beyond the
basic 8-color set already used, or `experimental.cacheTtl`. This is a genuinely UNUSED
surface here — an upgrade-pipeline agent roster is the first candidate in this repo to
reach for `memory` (durable per-agent learnings across upgrade rounds), `maxTurns`
(bounding a runaway upgrade-scan agent), or `skills` (preloading e.g. `tool-currency`
into an upgrade-scout agent's context at spawn rather than making it discover the skill
mid-run).

---

## 3. Codex-side reusable agents — YES, and this repo already built the mirror

**Answer to "does codex support project-level custom subagents/roles": yes, natively,
via `[agents]` config + per-role `.toml` files under an `agents/` subdirectory of each
config layer — and this repo already has a 7-file `.codex/agents/*.toml` roster
mirroring the Claude `.claude/agents/*.md` roster.** This mechanism is REAL and
IMPLEMENTED in the pinned codex source (`sources/codex.manifest`: `ref = rust-v0.153.4`,
`commit = 3d2ee51ca2d5db578f328aa75e20aa22c0197c9a`, `kind = code` — **note this manifest
is currently `build = skip` (excluded from `kb-build` since 2026-08-20, tracked in #417:
`Cargo.toml` produces zero nodes), so the graph itself cannot answer questions about
this — everything in this section came from reading the gitignored clone's Rust source
directly, not from a graph query**), but it is **UNDOCUMENTED in the prose docs** —
`sources/codex/docs/config.md` is a 15-line stub that only links out to
`developers.openai.com/codex/config-basic|config-advanced|config-reference` (external
URLs, not fetched for this report — reaching them would be a network call outside this
task's read-only/local-source scope). A recursive grep across
`sources/codex/docs/*.md` for `subagent`/`custom agent`/`[agents]`/`agent profile`/
`per-agent` returned **zero hits** — control-armed against a known-present term
(`default_subagent_model`, confirmed to exist in `.codex/config.toml:22`), which
**also returned zero hits inside `docs/`** — so the negative is real, not a broken
grep: this feature's only documentation is the Rust source itself and this repo's own
`.codex/config.toml` comments.

### The mechanism, read directly from `codex-rs` source

**Config struct fields** (`sources/codex/codex-rs/core/src/config/mod.rs:869-891`):

```rust
/// Whether multi-agent tools are enabled through `[agents]`.
pub agents_enabled: bool,
/// User-configured maximum number of spawned agent threads per session.
pub agent_max_threads: Option<usize>,
/// Default model for spawned subagents when the spawn call does not select one.
pub agent_default_subagent_model: Option<String>,
/// Default reasoning effort for spawned subagents when the spawn call does not select one.
pub agent_default_subagent_reasoning_effort: Option<ReasoningEffort>,
/// Whether to record a model-visible message when an agent turn is interrupted.
pub agent_interrupt_message_enabled: bool,
/// Maximum nesting depth for V1 agent threads. Ignored by V2.
pub agent_max_depth: i32,
/// User-defined role declarations keyed by role name.
pub agent_roles: BTreeMap<String, AgentRoleConfig>,
```

These map directly onto this repo's `.codex/config.toml:21-23`:
```toml
[agents]
default_subagent_model = "gpt-5.6-sol"
default_subagent_reasoning_effort = "high"
```
— confirming this repo's own comment at `.codex/config.toml:9` ("An agent that declares
its own model or effort still wins") is CORRECT, by the same per-call-overrides-default
precedence pattern as Claude Code's `CLAUDE_CODE_SUBAGENT_MODEL`: read directly at
`sources/codex/codex-rs/core/src/tools/handlers/multi_agents_common.rs:271`:
```rust
let requested_model = requested_model.or(turn.config.agent_default_subagent_model.as_deref());
```
i.e. an explicit per-spawn `requested_model` wins; the config default is the fallback
only.

**Role-file schema** (`sources/codex/codex-rs/agent-roles/src/agent_role_config.rs:20-28`):
a `.codex/agents/<name>.toml` file deserializes as `name`, `description`,
`nickname_candidates` (candidate display names for spawned instances of this role) PLUS
`#[serde(flatten)] config: ConfigToml` — **the SAME struct that backs the top-level
`.codex/config.toml`**. This means a role file can override **any** top-level codex
config key scoped to that role alone: `model`, `model_reasoning_effort`,
`sandbox_mode`/`sandbox_permissions`, `approval_policy`, `developer_instructions`, etc.
— not a small fixed knob set. `developer_instructions` is **required** for a role file
unless a `role_name_hint` is supplied (`agent_role_config.rs:67-71,134-157` —
`validate_agent_role_file_developer_instructions` errors if blank/absent and
`require_present` is true).

**Discovery**: `sources/codex/codex-rs/agent-roles/src/discovery.rs:7-40` —
`collect_agent_role_files` recursively walks a directory collecting every `*.toml` file
(sorted). Confirmed call site at `sources/codex/codex-rs/agent-roles/src/loader.rs:78`:
`&config_folder.join("agents")` — i.e. each codex config LAYER (project `.codex/`,
user `$CODEX_HOME`, and presumably any other layer in codex's layered-config stack) gets
its own `agents/` subdirectory scanned this way. This is the direct codex-side analogue
of Claude Code's project/user/plugin `.claude/agents/` precedence table in Section 2,
though this report did NOT trace the exact layer-precedence order for same-named roles
across layers (out of scope for the time budget on this pass — flagged as unverified
rather than guessed).

### What this repo's 7 `.codex/agents/*.toml` files actually use

Read `kb-advisor.toml` in full, and grepped `model_reasoning_effort`/`developer_instructions`/
`model` across all seven files:

- All 7 declare `name`, `description`, `developer_instructions` (a large multiline system
  prompt, structurally mirroring the corresponding `.claude/agents/*.md` body).
- `model_reasoning_effort = "high"` appears at least in `kb-advisor.toml:3` (and,
  per `.codex/config.toml`'s own control-arm comment at line 259, `kb-codex-advisor.toml`
  is the file that would carry an explicit reasoning-effort bump if the default at
  `.codex/config.toml:22` changes).
- **None of the 7 files override `model` directly** — a repo-wide grep for a `model =`
  key across `.codex/agents/*.toml` found zero real hits (one false-positive substring
  match was inside `kb-advisor.toml`'s prose body, not a TOML key). So every codex-side
  role currently rides the `[agents].default_subagent_model = "gpt-5.6-sol"` default
  rather than pinning its own model — the per-role override capability the `ConfigToml`
  flatten provides is, like several Claude-side fields in Section 2, an **unused
  surface** an upgrade-pipeline role could be the first to use (e.g. a cheaper/faster
  model for a mechanical upgrade-scan role vs. a higher-effort role for the actual
  dependency-bump implementation).

### `codex exec --help` flags that customise a lane (full list, read-only introspection)

Confirmed live on the installed binary (version not re-queried this pass; pinned source
is `rust-v0.153.4` per the manifest above):

| Flag | Effect |
|---|---|
| `-m, --model <MODEL>` | model for the agent |
| `-c, --config <key=value>` | override ANY config value by dotted path, TOML-parsed (e.g. `-c model_reasoning_effort=high`, `-c developer_instructions="..."`, `-c sandbox_workspace_write.network_access=true` — all three used elsewhere in this repo's `.claude/rules/ai-cli-invocation.md`) |
| `--enable <FEATURE>` / `--disable <FEATURE>` | shorthand for `-c features.<name>=true/false` |
| `--strict-config` | error on unrecognized config.toml fields |
| `-i, --image <FILE>...` | attach images to the initial prompt |
| `--oss` / `--local-provider <lmstudio\|ollama>` | open-source/local provider routing |
| `-p, --profile <NAME>` | layer `$CODEX_HOME/<name>.config.toml` on top of base config |
| `-s, --sandbox <read-only\|workspace-write\|danger-full-access>` | sandbox policy |
| `--approve-for-me` | route approvals through automatic review under workspace-write |
| `--dangerously-bypass-approvals-and-sandbox` | no sandbox at all (externally-sandboxed environments only) |
| `--dangerously-bypass-hook-trust` | run hooks without persisted trust (see this repo's `ai-cli-invocation.md` — REQUIRED for any lane that must run this repo's guard-stack hooks) |
| `-C, --cd <DIR>` | working root |
| `--add-dir <DIR>` | additional writable dirs (REQUIRED alongside any gate-running lane per `ai-cli-invocation.md`, for uv's cache dir) |
| `--thread-source <SOURCE>` | classification for new/forked threads |
| `--skip-git-repo-check` | allow running outside a git repo |
| `--ephemeral` | don't persist session files (this repo's rule says NOT to use this — see `ai-cli-invocation.md`, it breaks `resume --last` and session-search tooling) |
| `--ignore-user-config` | skip `$CODEX_HOME/config.toml` (auth still via `CODEX_HOME`) |
| `--ignore-rules` | skip user/project execpolicy `.rules` files |
| `--output-schema <FILE>` | JSON Schema constraining the final response shape — direct codex analogue of the Workflow `agent()` `schema` option |
| `--color <always\|never\|auto>` | output color |
| `--json` | JSONL event stream to stdout |
| `-o, --output-last-message <FILE>` | write the agent's last message to a file |
| `resume` / `fork` / `review` subcommands | resume a session by id/`--last`; fork a session; run a code review |

**`-c developer_instructions=...` is a real, generic mechanism** (via the `-c`
dotted-path override) — not a named flag of its own, but it works because
`developer_instructions` is a top-level `ConfigToml` field, same as any other `-c`
override, and it is **global** (applies regardless of `--base`, per this repo's
`.claude/CLAUDE.md`: "once the METHOD paragraph goes through `-c developer_instructions`
(global, so `--base` does not block it)"). This report did not re-verify that specific
claim against source in this pass (it is an existing MEMORY.md entry,
`codex-review-is-a-real-cold-lane.md`, cited here as INHERITED — not independently
re-derived this session).

---

## 4. The fable-orchestrator plugin's lane contract

Plugin location: `/Users/rmanaloto/.claude/plugins/cache/fable-orchestrator/fable-orchestrator/1.21.0/`
(version `1.21.0` — the `.in_use` marker file lives beside `agents/`, `hooks/`,
`scripts/`, `commands/`, `skills/orchestration/`). Agent roster in `agents/`:
`codex-implementer.md`, `codex-reviewer.md`, `fable-advisor.md`, `grok-implementer.md`,
`grok-researcher.md`, `grok-reviewer.md`, `premise-verifier.md` (7 files; the
grok-* siblings were not read for this report — out of scope, this repo runs `grok` as
NOT installed per `.claude/CLAUDE.md`).

### Frontmatter of the four requested agents

| Agent | model | tools | effort field? |
|---|---|---|---|
| `codex-implementer.md:1-6` | `sonnet` | `Bash, Read, Grep, Glob` | none in frontmatter — effort is a runtime `-c model_reasoning_effort=<level>` flag the agent passes to the codex CLI it drives, not a frontmatter field on the WRAPPER agent itself (the wrapper runs on Claude Sonnet; the actual work happens inside `codex exec`, a separate process) |
| `codex-reviewer.md:1-6` | `sonnet` | `Bash, Read, Grep, Glob` | same pattern — the wrapper is Sonnet, GPT-5.6 Sol does the review inside the CLI |
| `fable-advisor.md:1-6` | `fable` | `Read, Grep, Glob` (no Bash — advisor never executes commands) | none — advisor reads code directly on Fable, no CLI subprocess |
| `premise-verifier.md:1-6` | `opus` | `Read, Grep, Glob` (no Bash) | none — same shape as fable-advisor, runs directly on Opus |

**Structural point worth flagging for the upgrade pipeline's own agent design**: the two
CLI-wrapper agents (`codex-implementer`, `codex-reviewer`) both declare `model: sonnet`
for THEMSELVES — the wrapper's own reasoning is cheap (Sonnet) because its job is
supervision/transport/grading, not the actual work; the expensive reasoning
(`gpt-5.6-sol` at `high` effort by default) happens one process down, inside the
detached `codex exec` subprocess the wrapper launches and polls. This is a DIFFERENT
shape from this repo's own `kb-codex-advisor` (`.claude/agents/kb-codex-advisor.md`),
which declares **neither** `model` nor `effort` at all in its own frontmatter (relying
entirely on `.codex/agents/kb-codex-advisor.toml`'s `model_reasoning_effort` for the
actual reasoning tier) — both patterns solve the same problem (a cheap Claude-side
wrapper driving an expensive codex-side worker) but this repo's version omits the
wrapper's own model/effort fields entirely rather than pinning them to `sonnet`.

### How `codex-implementer` actually invokes codex — NOT a direct `codex exec` call from the agent

The agent does **not** shell out to `codex exec` inline. It launches through the
plugin's own process supervisor script, `scripts/run-lane.sh` (resolved via
`${CLAUDE_PLUGIN_ROOT}/scripts/run-lane.sh`, `codex-implementer.md:127`), which:

1. Is invoked as `"$RL" start codex "$SPEC" 1800` (`codex-implementer.md:136`) —
   `codex` is a lane-name argument to the wrapper script, `$SPEC` is a path to a
   prompt file the agent assembled via `cat`/heredoc (never inline shell quoting,
   `codex-implementer.md:48`), `1800` is the timeout in seconds (overridable by the
   dispatch's `TIMEOUT:` line).
2. Detaches the actual `codex exec` process and runs a "pure-bash watchdog" wrapping it
   (`codex-implementer.md:124`) — because the harness caps a single foreground Bash call
   at ~10 minutes, and a long codex run would otherwise kill the wrapper's supervision
   mid-run while codex kept running as an orphan.
3. The agent polls with `"$RL" wait <PID>` in <=90-second foreground slices
   (`codex-implementer.md:145-151`) until `EXITED`, then `"$RL" reap <PID> <WATCHDOG>`
   to confirm the process group is dead (`codex-implementer.md:156-159`).

**The exact codex flags the supervisor enforces, non-negotiable** (verbatim table,
`codex-implementer.md:163-172`):

| Enforcement | Why |
|---|---|
| `--sandbox workspace-write` | Codex writes code, scoped to the working tree. Never `danger-full-access`. |
| `-c model_reasoning_effort=<level>` | Defaults to high; overridden only by the dispatch's `EFFORT:` line, validated by the supervisor. |
| `--skip-git-repo-check` + `--cd "$(pwd)"` | Deterministic working root. |
| Spec via stdin from a file | No quoting hazards, no truncated specs. |
| Detached launch + watchdog | Survives the harness's 10-minute foreground cap. |
| `-c service_tier=fast -c features.fast_mode=true` (only under `LANE_CODEX_FAST=1`) | Opt-in fast tier when the dispatch says `FAST MODE: on`; never applied by default. |

**Overrides the CALLER can pass, and how they travel** — answering the team-lead's exact
question (model/effort/sandbox/network/add-dir, in-prompt or via env):

- **Effort**: a dispatch-prompt line `EFFORT: <level>` (`none|low|medium|high|xhigh|max`,
  case-normalized) — the agent reads this out of its OWN prompt (not the spec text
  codex sees) and translates it into `LANE_CODEX_EFFORT=<level>` prefixed onto the
  `run-lane.sh` launch (`codex-implementer.md:141`). So: **in-prompt, translated to
  env by the wrapper agent**, not a raw pass-through.
- **Fast tier** (a codex-side speed/cost knob, not requested by the team-lead but
  directly analogous to effort): dispatch-prompt line `FAST MODE: on` ->
  `LANE_CODEX_FAST=1` prefix (`codex-implementer.md:141`).
- **Model**: "To use a different codex model than the documented `gpt-5.6-sol` default,
  pass it as the fourth argument [to `run-lane.sh start`]; the slug is a default, not a
  constant." (`codex-implementer.md:143`) — i.e. `"$RL" start codex "$SPEC" 1800
  <model-slug>`, a POSITIONAL argument to the wrapper script, not a prompt line.
- **Sandbox**: **NOT caller-configurable** — hardcoded to `--sandbox workspace-write`
  in the enforcement table above, "Never `danger-full-access`." No dispatch-prompt line
  or env var is documented to change it.
- **Network / `--add-dir`**: **NEITHER appears in the enforcement table at all** — the
  fixed flag set is exactly the six rows above, and none of them is a network-access or
  `--add-dir` override. This directly corroborates (rather than merely repeats) this
  repo's own `.claude/rules/ai-cli-invocation.md` findings that `workspace-write`
  blocks network egress by default and that uv's cache needs an explicit `--add-dir`
  — **the stock `codex-implementer` lane, as shipped by this plugin version (1.21.0),
  has no documented path for a dispatch to request either**. A spec that needs
  `codex-implementer` to run a `mise run kb-*` gate (which needs uv's cache dir) or to
  fetch anything over the network (which an upgrade-pipeline dependency check almost
  certainly needs) would hit exactly the walls this repo's own MEMORY.md already
  recorded (`codex-lane-cannot-write-agents-or-run-uv-gates.md`,
  `a-codex-lane-has-no-network-by-default.md`) — **UNLESS the upgrade pipeline's own
  subagent/workflow bypasses this stock plugin agent and drives `codex exec` directly**
  (the way this repo's `.codex/agents/*.toml` + a direct `codex exec` invocation
  following `.claude/rules/ai-cli-invocation.md`'s patterns already does), or unless a
  newer plugin version added these overrides (this report did not check for a newer
  cached version directory beside `1.21.0/`).
- **`developer_instructions`**: not mentioned in `codex-implementer.md` at all — the
  spec text itself (the seven-part spec, below) is what reaches codex; there is no
  documented mechanism in this agent file for the caller to inject a SEPARATE
  `developer_instructions` override the way `.codex/agents/*.toml` role files or a raw
  `-c developer_instructions=...` flag can.

### `codex-reviewer` — same wrapper shape, one more enforced flag

`codex-reviewer.md:93`: "The `codex-review` lane pins `sandbox_mode` to **read-only**"
— stricter than the implementer's `workspace-write`, consistent with "Never edits
files" in its own description (`codex-reviewer.md:3`). It uses the `codex exec review`
SUBCOMMAND specifically (`codex-reviewer.md:74`: "`codex exec review` reviews the repo
it is launched in"), matching the `review` subcommand confirmed live in
`codex exec --help` (Section 3 above). Same `EFFORT:`/`FAST MODE:` dispatch-line ->
`LANE_CODEX_EFFORT`/`LANE_CODEX_FAST` env-prefix pattern as the implementer
(`codex-reviewer.md:91`).

### The seven-part spec contract — part names verbatim

Source: `.../skills/orchestration/SKILL.md:115-121`, "The spec contract" section:

1. **Objective** — the outcome to achieve and the failure scenario it prevents, one
   paragraph. Outcome, not keystrokes.
2. **Files** — exact paths to create or modify.
3. **Interfaces** — signatures, types, or API shapes the code must match.
4. **Constraints and invariants** — project conventions, things not to touch, invariants
   with their known consumers named, pointers to context the lane cannot infer. Any
   artifact the spec tells the CLI to read is cited by absolute path and must exist at
   dispatch (the wrapper stats it, never reads it).
5. **Verification** — the smallest command bundle that proves the change works (not the
   full suite).
6. **Commit** — who commits: `lane` (default) or `caller`.
7. **Premises** — a block headed `PREMISES`, closing the spec: one row per factual claim
   the spec rests on, each citing where it was read THIS session. Five row types: `L`
   literal/constant, `I` interface, `P` precedent, `E` emission, `A` assumption. Routed
   to `premise-verifier` before dispatch when the spec emits telemetry/errors/events or
   touches security/concurrency/migration paths; the dispatch then carries a
   `PREMISES-VERIFIED: <path>` attestation line that a plugin PreToolUse hook enforces
   (presence-only, cannot judge row quality).

Two standing clauses ride with every spec via the lane wrappers' fixed closing block
(`SKILL.md:125`), so the architect never retypes them: **licensed dissent** (an
implementer whose reading of the code contradicts the spec stops and reports rather
than implementing the wrong thing) and **test craft** (isolated state, no
wall-clock-dependent assertions, every assertion must fail if the change is reverted).

**`fable-advisor` and `premise-verifier` are exempt from the spec contract** — they
"receive no implementation spec" (`SKILL.md:121`, last sentence) — consistent with
their own frontmatter carrying no Bash/Write tools and their descriptions being purely
advisory/verification roles.

---

## 5. GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — pinned at
  `sources/claude-code.manifest` (`v2.1.258`, `aef74afe01f65b602258d6102b0da9730ac6f0aa`,
  `kind=docs`); read `CHANGELOG.md` for the `CLAUDE_CODE_SUBAGENT_MODEL` precedence
  history and `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`.
- [anthropics/claude-code-docs mirror source](https://code.claude.com/docs) (vendored
  in this repo as `sources/claude-code-docs`, a live-refetched docs mirror, not a
  SHA-pinned clone of a single upstream repo — its own `CLAUDE.md` names
  `code.claude.com`, `platform.claude.com`, `claude.com/docs`, `modelcontextprotocol.io`,
  `support.claude.com`, and `github.com/anthropics/*` as its 12 sources) — read
  `content/en/docs/claude-code/sub-agents.md` (full frontmatter field table, model
  precedence, scope precedence) and `content/en/docs/claude-code/model-config.md`
  (partial — first 521 of 857 lines, for the `availableModels`/subagent-model-allowlist
  section).
- [openai/codex](https://github.com/openai/codex) — pinned at `sources/codex.manifest`
  (`rust-v0.153.4`, `3d2ee51ca2d5db578f328aa75e20aa22c0197c9a`, `kind=code`, currently
  `build = skip` per #417 so this source is NOT in the graph). Read `docs/config.md`,
  `docs/agents_md.md`, and — the load-bearing reads for Section 3 —
  `codex-rs/core/src/config/mod.rs` (Config struct fields, `agent_roles` loading call
  site), `codex-rs/core/src/tools/handlers/multi_agents_common.rs` (per-spawn model
  override precedence), `codex-rs/agent-roles/src/agent_role_config.rs` (role-file
  schema, the `ConfigToml` flatten), and `codex-rs/agent-roles/src/discovery.rs`
  (recursive `agents/` directory `.toml` discovery).
- [mar3co/fable-orchestrator](https://github.com/mar3co/fable-orchestrator) — the
  installed plugin (cache version `1.21.0`, homepage confirmed via its own
  `.claude-plugin/*.json` manifest). Read `agents/codex-implementer.md`,
  `agents/codex-reviewer.md`, `agents/fable-advisor.md`, `agents/premise-verifier.md`,
  and `skills/orchestration/SKILL.md` (the spec contract, review tiers, lane routing).
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this
  repo: `.claude/workflows/{kb-extract,kb-tool-review,session-review}.js`,
  `.claude/agents/*.md` (all 7), `.codex/agents/*.toml` (all 7, one read in full),
  `.codex/config.toml`, `.claude/CLAUDE.md`, `.claude/rules/ai-cli-invocation.md`
  (cited, not re-read this session), and the `graphify-out/graph.json` KB graph itself
  via `mise run kb-query`.




Adversarial verify (N independent skeptics, kill if >= majority refute); perspective-
diverse verify (distinct lenses per verifier, not N identical refuters); judge panel (N
independent attempts, scored, synthesize from winner grafting runner-up ideas);
loop-until-dry (keep spawning finders until K consecutive rounds return nothing new);
multi-modal sweep (parallel agents searching differently, blind to each other); the
completeness critic ("what's missing — modality not run, claim unverified, source
unread?"); and the "no silent caps" rule — `log()` any bounded coverage (top-N,
no-retry, sampling) rather than let it read as complete.


## GitHub repos touched

_Appended by the architect session on 2026-09-09 after the agent went idle without a final hand-back; derived from the sources cited above, nothing new read._

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — pinned clone `sources/claude-code/` (`CHANGELOG.md`) and the docs mirror `sources/claude-code-docs/…/sub-agents.md`
- [openai/codex](https://github.com/openai/codex) — pinned clone `sources/codex/` (`codex-rs/core/src/config/mod.rs`, `agent-roles/*`, `tools/handlers/multi_agents_common.rs`, `docs/config.md`)
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — `.claude/workflows/*.js`, `.claude/agents/*.md`, `.codex/config.toml`, `.codex/agents/*.toml`
- fable-orchestrator plugin 1.21.0 — read from the local plugin cache (`~/.claude/plugins/cache/fable-orchestrator/…`); its source repository was not consulted
