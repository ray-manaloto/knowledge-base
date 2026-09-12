# S7 External Search: Session Handoff / Cross-Session Memory Prior Art

Question: how should an AI coding agent hand work from one session to the
next, and what already exists we should use instead of what we built
(`/clear-prep` handoff markdown + `/session-resume` + planning-with-files +
bespoke `next-ticket` TOML chain reader)?

Owner has ruled: handoff pointer goes away, planning-with-files plan file
becomes the sole next-task carrier. This search is use-the-existing-tool-
before-building-one, not a survey.

---

## Surface note: last30days skipped

The `last30days` skill requires an interactive first-run setup wizard
(browser-cookie consent via AskUserQuestion, GitHub device-auth flow for
ScrapeCreators, etc.) that cannot run headlessly from this delegated lane.
Proceeding with Firecrawl, Exa, Context7, and direct `gh api` GitHub search
instead — these are the three MCP surfaces plus GitHub the task explicitly
authorized, and they do not require interactive consent.

## GitHub repo search (bare query, uncontrolled — for context only)

`gh api search/repositories -f q='claude code memory session handoff'`
returned (top by stars), 2026-09-12:

- JamesShi96/project-butler (372) — "Project memory system for AI coding
  assistants (Claude Code, Cursor, Codex): session logs, project wiki, rules,
  TODOs, and handoff."
- awrshift/agent-memory-kit (34) — "Agent memory as plain files... the agent
  proposes, you approve, every line dated... session handoffs..."
- mworldorg/markdown-memory (25) — "cross-platform, file-based persistent
  memory and prompt bridge for Claude Code, claude.ai, and Antigravity IDE.
  Synchronizes project passports, handoffs, and session logs in an Obsidian
  Vault."
- AxmeAI/axme-code (14) — "Persistent memory, architectural decision
  enforcement, pre-execution safety hooks, and session handoff for Claude
  Code. MCP server plugin."
- IlyaGorsky/memory-toolkit (13) — "Session memory lifecycle plugin for
  Claude Code — structured markdown memory, workstreams, handoff, auto-save
  hooks"
- sunososobro-hub/claude-octopus (10) — "Token-frugal session memory &
  usage tracking for Claude Code — curated nap/wake handoff instead of full-
  session resume, plus real 5h/7d rate-limit tracking."
- buildoak/eywa-continuum (7) — "Cross-session memory for Claude Code — MCP
  server for context handoffs"
- RRFRRF/project-memory-skill (7) — "Lightweight project memory system for
  AI coding agents — cross-session state, bug queue, ADR decisions, and
  handoff notes as Markdown files."
- skymanbp/cc-memory (7) — "Persistent memory for Claude Code. Survives
  compaction and session boundaries: anti-patch reconcile-on-write with LLM-
  judged de-duplication, a forced PROGRESS.md handoff, a live PLAN.md anchor
  with an enforced directive ledger, FTS5 search, MCP tools and a GUI. Pure
  stdlib Python, zero runtime dependencies."
- AnastasiyaW/mclaude (6) — "Multi-session collaboration for Claude Code:
  atomic locks, handoffs, memory graph, messaging, hub server, bridge, voice
  I/O. 166 tests. Zero core deps."

**Control-arm note:** this is a bare, unqualified query — noisy by
construction per this repo's own doctrine (research-doc-sources.md). Star
count is a popularity proxy, not a quality/adoption proxy for a category
this small (all under 400 stars — this whole space is nascent/niche).
Treating any of these as "the" answer without reading the actual repo would
repeat the mistake this task exists to avoid.

## Firecrawl developer_search: "Claude Code session handoff memory between sessions after /clear"

**1. ddaanet/handoff** — https://github.com/ddaanet/handoff (README)
- Shipped Claude Code PLUGIN, not a blog post. Quote: "A task snapshot that
  survives a context reset in Claude Code — whether that reset is a `/clear`
  or a `/compact`. Designed as a narrow complement to Claude Code's
  auto-memory: memory holds durable facts... this plugin holds the
  *ephemeral task frame* memory avoids."
- Mechanism: skills at both boundaries (`/handoff:handoff` before `/clear`,
  `/handoff:precompact` before `/compact`), plus `/handoff:autoname`,
  `/handoff:restart` (exit+relaunch `--resume` for config changes — "unlike
  `/clear` it costs no context at all"), `/handoff:pending` (report current
  task frame without writing). **Both write the same file; a `SessionStart`
  hook injects it back, verbatim, into whatever comes next.**
- This is nearly IDENTICAL in shape to this repo's own `/clear-prep` +
  `/session-resume`, but as a portable, reusable Claude Code plugin using
  native hook wiring (SessionStart) instead of a skill instructing the user
  to read a file. Would work here: this repo already uses SessionStart hooks
  (kb_setup.currency check) and could add a SessionStart injection instead
  of relying on session-resume skill's "find newest file" logic.
- Failure mode reported: none documented yet in the README excerpt fetched;
  worth reading the actual issues tab before adopting.

**2. mehmeteminduran/claude-session-handoff-plugin** — via Exa
  https://github.com/mehmeteminduran/claude-session-handoff-plugin
- Also a shipped Claude Code plugin. Quote: "`/handoff [session]` — write the
  current session's state into `HANDOFF-<session>.md`; `/resume [session]` —
  read that file, reconcile with `git status`, and execute the next concrete
  step; A **PreCompact hook** that blocks context compaction until a fresh
  handoff exists, so Claude Code never silently summarizes away your unsaved
  state."
- Named sessions -> multiple parallel handoff threads can coexist in one
  repo (this repo's `.agent/plans/session-<date>[-letter].md` scheme is a
  weaker, unenforced version of the same idea — a letter suffix, not a name,
  and nothing blocks compaction if the handoff wasn't written).
- Explicit multi-TOOL handoff angle: Claude Code -> Codex -> Cursor -> fresh
  Claude, "the conversation contains the *what*, not the *why*."
- **The PreCompact-hook-blocks-compaction mechanism is the single most
  interesting piece found so far** — it is stronger than what this repo has:
  right now `/clear-prep` is advisory (a skill you must remember to invoke);
  a PreCompact hook that structurally BLOCKS compaction until a handoff
  exists would close exactly the "forgot to run /clear-prep" gap this repo's
  clear-prep skill exists to paper over via user reminder text.

**3. anthropics/claude-code#70555** — "Working-state continuity: survive
  compaction and /clear (the long-session 'goes dumb' problem)" — a live,
  OPEN GitHub issue on the anthropics/claude-code repo itself, naming this
  exact problem as unsolved upstream: "Cold-start amnesia after `/clear` or
  compaction. A fresh session reloads `CLAUDE.md` but has no sense of _where
  we just were_... That handoff across the clear boundary is the single
  weakest link." This CONFIRMS there is no first-party native solution yet —
  third-party plugins above are filling a real gap, not reinventing a wheel
  Anthropic already shipped.

**4. anthropics/claude-code#72745** — "Quality regression: no cross-session
  context retention, repeated failures on same task" — another live issue,
  reporting 9 separate sessions repeating the same failed commands with zero
  awareness of prior attempts. Corroborates #70555; this is a well-known,
  currently-unfixed pain point, not a fringe complaint.

**5. hivellm/rulebook — docs/analysis/session-auto-cleanup/README.md**
  (https://github.com/hivellm/rulebook) — a RESEARCH DOC (not a tool) that
  surveyed 7 agent tools' approaches to context accumulation, dated
  2026-07-14. Verdict quoted verbatim: **"Do NOT rebuild the retired v6
  handoff (forced Stop-hook + /clear ritual — F-010). The native harness
  already ships a three-tier compaction pipeline; Rulebook's job is to make
  sessions *cheap to end and cheap to start* (state on disk, one-call
  resume) and to surface context pressure through channels that cost zero
  hooks: tool responses and the statusline."**
  This is directly on-point for our question: another project explicitly
  DECIDED AGAINST building a forced-hook handoff ritual (which is close to
  what `/clear-prep` + `/session-resume` is) and instead leaned on cheap
  disk state + native compaction. Their landscape summary:
  - Claude Code (native): microcompaction, auto-compact ~83.5%, manual
    `/compact <focus>`, CLAUDE.md survives compaction.
  - Codex CLI: session-memory substitution, then server-side compact ~167k
    tokens.
  - OpenCode: selective pruning, last 40k tokens protected.
  - Roo Code: auto-condense at configurable threshold.
  - Cline Memory Bank: durable markdown state files + `/newtask` — "fresh
    session is cheap" philosophy — CLOSEST philosophical match to what Ray
    wants (plan file as sole carrier).
  - Aider: background summarization with a weak model.

**6. code.claude.com/docs/en/sessions — "Manage sessions"** (official docs)
  Quote: "Sessions are saved continuously to local transcript files as you
  work, so you can return to one after exiting or running /clear." This is
  Claude Code's OWN native `--resume`/`claude --continue` mechanism — full
  transcript resume, distinct from a curated handoff file. Worth explicitly
  comparing: `--resume` restores the RAW transcript (expensive, full detail,
  no curation) vs a handoff file (cheap, curated, lossy). These are
  complementary, not substitutes — this repo's session-resume skill layers
  on top of raw resume by reading a curated file instead of replaying the
  whole transcript.

**7. dev.to (Dhruv Anand) — "Stop losing AI coding context between
  sessions: Continue Later (skills + CLI)"** — a blog post, but describing a
  SHIPPED "Continue Later" skill/CLI package with explicit multi-tool
  support (Cursor, Claude Code, Codex, Gemini, OpenCode). Another instance
  of the same shape: local handoff skill + CLI, not a hosted service.

**8. claudefa.st blog — "Claude Code Session Memory: Automatic Cross-Session
  Context"** — describes what reads as an ANTHROPIC-NATIVE feature called
  "Session Memory" that runs automatically in the background with no user
  input. **UNVERIFIED — this is a third-party blog, not an anthropic.com or
  code.claude.com URL, and needs a primary-source check before being relied
  on.** Flagging rather than asserting it's real; if genuine this could be
  the actual native answer to Ray's question and everything above would be
  redundant for it specifically.

## Native Claude Code mechanisms (Context7, code.claude.com/docs — primary source)

Confirmed via Context7 docs query against `/websites/code_claude` (high-
reputation indexed docs, 7834 snippets):

1. **`PreCompactHookInput` type exists NATIVELY** (Agent SDK / hooks):
   ```typescript
   type PreCompactHookInput = BaseHookInput & {
     hook_event_name: "PreCompact";
     trigger: "manual" | "auto";
     custom_instructions: string | null;
   };
   ```
   This is the SAME hook the `claude-session-handoff-plugin` (found above)
   uses to BLOCK compaction until a handoff is written. It is a first-class,
   documented Claude Code hook event — not a hack.

2. **`SessionStart` with `matcher: "compact"` re-injects context natively**,
   straight from code.claude.com/docs/en/hooks-guide:
   ```json
   { "hooks": { "SessionStart": [ { "matcher": "compact", "hooks": [
     { "type": "command", "command": "echo 'Reminder: ...'" } ] } ] } }
   ```
   This is EXACTLY the mechanism `ddaanet/handoff`'s plugin uses ("a
   `SessionStart` hook injects it back, verbatim"). This repo does NOT
   currently use a `SessionStart(compact)` matcher — `/session-resume` is a
   skill the user must remember to invoke, not a hook that fires
   automatically.

3. **`SessionEnd` with `matcher: "clear"` exists** for cleanup specifically
   on `/clear` (distinct from other exits) — could be the natural place to
   fire a handoff WRITE automatically instead of relying on the user to run
   `/clear-prep` first.

4. **`/context` (SDKContextUsage) reports `memory_files` as a first-class
   category** alongside mcp_tools, agents, skills — confirming Claude Code's
   own model of "memory files" as a distinct, budgeted context category,
   separate from a session transcript.

**This directly answers the question "does Claude Code have a native
mechanism for this we're reimplementing":** partially yes. The HOOK
PRIMITIVES (PreCompact, SessionStart[compact], SessionEnd[clear]) are
native and this repo is not using them for handoff — it relies entirely on
a skill (`/clear-prep`) the user/agent must remember to invoke, with no
hook enforcing that a handoff exists before `/clear` or compaction happens.
The actual FILE FORMAT and content curation (what goes in the handoff) is
NOT something Claude Code ships — that part genuinely has to be authored,
and planning-with-files' plan file (see below) is the strongest existing
candidate for it.

## Confirmed open GitHub issues on anthropics/claude-code (this exact problem, unsolved upstream)

`gh api search/issues -f q='repo:anthropics/claude-code PreCompact hook state'`
(qualified query, not bare):

- **#70555** OPEN — "Working-state continuity: survive compaction and
  /clear (the long-session 'goes dumb' problem)" — the closest match to our
  exact question, still open.
- **#80883** OPEN — "feat: Add context-safety-net plugin to mitigate
  auto-compact context loss"
- **#90212** OPEN — "[FEATURE] Programmatic / fleet compaction:
  compact-on-idle, cross-session /compact, runtime-adjustable autocompact"
- **#17428** OPEN — "[Feature Request] Enhanced /compact with file-backed
  summaries and selective restoration" — literally proposes what a
  plan-file-as-carrier design would need natively.
- **#91910** OPEN — a real subtlety: PreCompact/SessionStart(compact) hooks
  "fire for a SUBAGENT's compaction without agent fields" and SubagentStop
  fires with a never-created transcript path — a known rough edge in the
  hook mechanism itself if we build on it.
- **#86716** OPEN — "Agent teams: per-agent autocompact control + a
  protocol to compact a context-exhausted teammate" — relevant if the
  handoff design needs to cover subagent/teammate compaction too, not just
  the main session.

**Control arm for this GitHub search:** the earlier bare-query search
(`search/repositories -f q='claude code memory session handoff'`) returned
78,695 total hits with mostly noise (confirmed separately for
`search/issues -f q='agent session handoff memory'`, 78,695 total_count,
first hit an unrelated `loopx` issue). This qualified `repo:` + keyword
query above returned a small, precise, on-topic set — demonstrates the
qualifier discipline this repo's own `research-doc-sources.md` prescribes
actually matters here.

## planning-with-files ALREADY has a documented handoff/resume path — we are not using it

This is the single most load-bearing finding for the task. `othmanadi/planning-with-files`
is the upstream of the `planning-with-files` plugin already installed in
this repo (per MEMORY.md: "planning-with-files installed run plan first").
**It carries 23,946 stars** (via tomevault.io mirror listing) — several
orders of magnitude more adoption than anything else found in this search,
including the memory-toolkit repos above.

Findings from its own docs (Firecrawl developer_search, all URLs pinned to
commit SHAs):

1. **The "5-Question Reboot Test"**
   (github.com/othmanadi/planning-with-files/blob/1ec8f4eb.../docs/workflow.md):
   | Question | Answer Source |
   |---|---|
   | Where am I? | Current phase in `task_plan.md` |
   | Where am I going? | Remaining phases in `task_plan.md` |
   | What's the goal? | Goal statement in `task_plan.md` |
   | What have I learned? | `findings.md` |
   | What have I done? | `progress.md` |
   This is a genuine, documented completeness bar for what a resume needs
   to answer — stronger and more specific than this repo's own ad hoc
   handoff prose convention.

2. **A documented "Topic Handoff Pattern"** exists, added via
   `othmanadi/planning-with-files#170` (merged commit `c5afda4`, released as
   v2.42.0): for a long-running topic sharing one root plan, keep
   `progress.md` concise and move durable detail into
   `handoffs/<topic>.md` — "Current state, commands, validation, risks,
   rollback, PR links." **This is effectively the same content shape as
   this repo's `.agent/plans/session-<date>.md` handoff**, but living
   INSIDE the planning-with-files convention rather than as a parallel,
   separately-maintained skill.

3. **Explicit claim: "Supports automatic session recovery after /clear"**
   (from the Arabic-language skill description mirrored at tomevault.io,
   consistent with the English description). This is planning-with-files'
   own stated value proposition, not something bolted on.

4. **Concurrent/multi-topic support already solved**: `PLAN_ID` env var +
   `init-session.sh <slug>` + `set-active-plan.sh` for switching between
   named plans, with an explicit warning that "on recovery, resolve the
   selected plan first and read all three files from that directory. Do
   not substitute a root `task_plan.md` for a selected named plan." This is
   MORE robust than this repo's letter-suffix scheme
   (`session-<date>[-letter].md`) for concurrent work.

5. **Explicit answer to "what happens to plan files after completion"**:
   they are gitignored working memory, NOT archived automatically — "the
   next task overwrites the root plan, and a slug directory just stops
   being active." This matches a caution already recorded in this repo's
   own memory (archiving an unfinished plan destroys the restore-after-
   `/clear` — gate on `check-complete.sh`), so the failure mode is already
   known to this repo from direct experience and is independently
   documented upstream.

6. **Open issue `othmanadi/planning-with-files#19`** — "For multi-step /
   complex tasks, how should this skill be used properly?" confirms the
   simplest working resume prompt is exactly: *"Read task_plan.md,
   findings.md, progress.md and continue from Phase X."* This is the
   PLAIN, minimal resume mechanism Ray is asking to make canonical.

**Failure mode reported for planning-with-files specifically:** issue #169
("resolve init-session POSIX shell loop") found `init-session.sh` failing
under `/bin/sh` on Ubuntu/dash before v2.42.0 — a real, fixed portability
bug, not a design flaw. No reports found (in this search) of the file-based
resume mechanism itself losing state or being unreliable.

**Would it work here?** Yes, cleanly. This repo is mise+uv+hk+zero-bash;
planning-with-files' own scripts are shell (`init-session.sh` etc.), which
is a friction point against this repo's zero-bash-logic invariant if the
scripts are invoked directly — but the FILE FORMAT and skill-driven
read/write pattern (task_plan.md/findings.md/progress.md, resumed via a
plain "read and continue" prompt) needs no shell integration at all; the
skill's own commands (`/planning-with-files:plan`, `/planning-with-files:status`)
already wrap the mechanics.

## Ranked digest — the two/three mechanisms most likely to replace what we built

**1. `othmanadi/planning-with-files`'s own documented handoff path (task_plan.md
+ findings.md + progress.md + the Topic Handoff Pattern's `handoffs/<topic>.md`)
is the strongest candidate, and it is ALREADY INSTALLED here.** 23,946 stars,
an explicit "5-Question Reboot Test" completeness bar, a documented
resume-from-plain-prompt path ("Read task_plan.md, findings.md, progress.md
and continue from Phase X"), and a purpose-built durable-detail extension
(Topic Handoff Pattern, PR #170) for exactly the case Ray described — long-
running work needing state carried forward. Adopting IT as the sole
next-task carrier (as Ray has ruled) means retiring `/clear-prep`'s bespoke
markdown format and `/session-resume`'s "find the newest file" logic in
favor of reading this plugin's own files — less to build, and it inherits
whatever fixes/hardening upstream ships (e.g. #169's POSIX fix already
landed).

**2. The native `PreCompact` + `SessionStart(matcher:"compact")` +
`SessionEnd(matcher:"clear")` hook triad should be wired to ENFORCE that
the plan file exists/is current, the way `mehmeteminduran/claude-session-
handoff-plugin`'s PreCompact hook "blocks context compaction until a fresh
handoff exists."** This is the piece this repo is missing regardless of
which file format wins: right now nothing stops a `/clear` or auto-compact
from happening with a stale or absent plan file. This is a genuinely native,
documented mechanism (confirmed via Context7 against code.claude.com/docs)
that costs no third-party dependency to adopt, and closes the exact gap
`next-ticket`'s TOML chain-reading currently exists to route around by hand.

**3. `ddaanet/handoff`, worth reading in full before deciding NOT to use it**
— structurally closest existing plugin to this repo's own `/clear-prep` +
`/session-resume` pair (skill-pair at the /clear boundary and the /compact
boundary, SessionStart hook injects the file back verbatim), but it is a
SEPARATE plugin from planning-with-files rather than an extension of it.
Given Ray's ruling that planning-with-files' plan file becomes the SOLE
carrier, this repo likely wants planning-with-files' OWN Topic Handoff
Pattern (#170) rather than a second, parallel handoff mechanism — but
`ddaanet/handoff`'s SessionStart-hook-injects-file-verbatim wiring is a
good reference implementation to copy the mechanics from even if the
plugin itself is not adopted.

**Not recommended:** any of the standalone "memory toolkit" repos found via
the bare GitHub repo search (project-butler, agent-memory-kit, markdown-
memory, axme-code, memory-toolkit, claude-octopus, eywa-continuum,
project-memory-skill, cc-memory, mclaude) — all under 400 stars, a fragmented
and duplicative space, none with the adoption or documentation depth of
planning-with-files, and adopting one would mean introducing a SECOND
planning/memory convention alongside the one already installed, which cuts
against Ray's explicit instruction that the plan file becomes the SOLE
carrier.

**Anthropic's own native "Session Memory" is UNVERIFIED** — surfaced via one
third-party blog (claudefa.st), not confirmed against code.claude.com/docs
or the Context7-indexed docs in this search. If it turns out to be real and
automatic, it could make some of the above moot; recommend a direct check
of code.claude.com/docs/en/memory or CHANGELOG.md before finalizing the
design, since this repo's own MEMORY.md and CLAUDE.md rules already track
Claude Code version-specific behavior changes closely (e.g. the
`CLAUDE_CODE_SUBAGENT_MODEL` precedence change) and would want the same
rigor applied here.

## GitHub repos touched

- [ddaanet/handoff](https://github.com/ddaanet/handoff) — closest existing Claude Code plugin analog to this repo's own /clear-prep + /session-resume pair; SessionStart-hook-injects-file-verbatim reference implementation.
- [mehmeteminduran/claude-session-handoff-plugin](https://github.com/mehmeteminduran/claude-session-handoff-plugin) — PreCompact-hook-blocks-compaction pattern, multi-tool (Claude Code/Codex/Cursor) handoff angle.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — issues #70555, #72745, #80883, #90212, #17428, #91910, #86716 read to confirm this is a live, unsolved upstream problem and to check native hook primitives (PreCompact, SessionStart, SessionEnd).
- [othmanadi/planning-with-files](https://github.com/othmanadi/planning-with-files) — the primary finding; already-installed plugin's own docs (workflow.md, quickstart.md), issue #19, and merged PR #170 (Topic Handoff Pattern) read in full to determine its existing handoff/resume path.
- [hivellm/rulebook](https://github.com/hivellm/rulebook) — research doc surveying 7 agent tools' context-accumulation strategies; cited for its "do not rebuild a forced-hook handoff ritual" verdict and native-Claude-Code compaction summary.
- [huangruiteng/loopx](https://github.com/huangruiteng/loopx) — surfaced only as noise in an unqualified control-arm GitHub search; not read further, flagged as an example of why bare queries are unreliable here.
- JamesShi96/project-butler, awrshift/agent-memory-kit, mworldorg/markdown-memory, AxmeAI/axme-code, IlyaGorsky/memory-toolkit, sunososobro-hub/claude-octopus, buildoak/eywa-continuum, RRFRRF/project-memory-skill, skymanbp/cc-memory, AnastasiyaW/mclaude — surveyed via one bare GitHub repo-search result set only (titles/descriptions, not read in depth); listed for completeness as candidate backlog entries, none recommended for adoption (see digest above).

_Note: no `sources/<name>.manifest` exists for any of these yet; none were ingested into the graph — this search's job was survey, not ingestion. Per this repo's own `research-repo-enumeration.md`, `othmanadi/planning-with-files` (already the installed plugin's upstream) is the strongest candidate to add to `sources/REGISTRY.md` if a deeper query-able reference is wanted later._

## ADDENDUM: agentsview `recall brief` — verdict requested by team-lead

**Primary source, quoted verbatim** (agentsview.io/docs/recall/, via Firecrawl
search snippet, and the pinned upstream doc
`github.com/wesm/agentsview/blob/0a24031.../docs/recall.md`):

> "Recall is an experimental layer for durable, provenance-linked knowledge
> from past agent sessions. It stores compact facts, procedures, preferences,
> and warnings as entries that can be listed, queried, and packed into a
> task brief."

> Current surface: "`recall query` for ranked lexical, vector, or hybrid
> retrieval; `recall brief` for a packed, trusted task briefing"

From the front page (agentsview.io/):
> "Recall (experimental) extracts provenance-linked knowledge from your
> archive: **decisions, gotchas, and project facts**, each with evidence
> links back to the sessions that produced it."

**Entry review states** (from `kenn-io/agentsview` mirror of `docs/recall.md`):
`human_reviewed` / `unreviewed_auto` / `calibrated_auto` / `eval_raw` — a
provenance/trust pipeline over EXTRACTED FACTS, not a workflow-state model.
There is no "phase," "next step," or "goal" field anywhere in the entry
schema surfaced in any of these sources — only `type` (implied: decisions,
gotchas, procedures, preferences, warnings, project facts), evidence
(message ordinals + digest back to the source transcript), and review
state.

### Verdict: retrieval-over-history, NOT a task-state/next-step carrier

**`recall brief` cannot carry a round's next-task state.** It has no
concept of "where the round currently is" or "what remains to be done" —
its unit is a durable FACT extracted from a past session (a decision made,
a gotcha hit, a preference stated), not a live plan with phases/goals/open
items. This is structurally the same shape as this repo's OWN
`graphify-out/memory/` work-memory store (`kb-remember`/`kb-reflect`) —
which this repo's own MEMORY.md already flags as **write-only, 0 graph
nodes** (`graphify-memory-store-is-write-only.md`) — not the shape of
`othmanadi/planning-with-files`' `task_plan.md` (current phase, remaining
phases, goal statement).

**Concretely, against Ray's ruling that the plan file becomes the sole
next-task carrier:** `recall brief` is **orthogonal to, not a replacement
for,** that plan file. It answers "what have we learned/decided/hit before
on this topic across ALL past sessions" (a corpus-wide durable-fact
lookup); the plan file answers "where is THIS round right now and what's
next" (a single round's live task state). A resume flow could legitimately
use BOTH — `recall brief <task>` to surface relevant prior gotchas/decisions
before resuming, and the plan file's `task_plan.md`/`progress.md` to
resume the actual state — but `recall brief` cannot substitute for the
latter. This mirrors the distinction `ddaanet/handoff`'s own README draws
for Claude Code's native auto-memory: "memory holds durable facts... this
plugin holds the *ephemeral task frame* memory avoids."

**No explicit "not meant for" statement found in the docs** — the search
did not surface a line where agentsview's own docs say "recall is not for
carrying task state." The verdict above is inferred from the entry schema
and the explicit list of entry types (facts/procedures/preferences/
warnings/decisions/gotchas/project facts), all of which are backward-
looking extractions, never a forward-looking phase/goal/remaining-work
structure. Flagging as inferred-not-quoted for that specific negative claim.

**Setup-gap facts as reported, both control-armed by their own error
text** (not independently re-verified by this lane — team-lead's own probe):
- `agentsview recall list` → `(no entries)` — extractor never run here.
- `agentsview embeddings list` → `fatal: vector search is not enabled` —
  only `lexical` mode works today.

**`agentsview skills install`** was flagged by team-lead as possibly
shipping harness-integration skill files. Not independently probed by this
lane (team-lead's instruction was to report install location without
running it, and that check is better done locally against the installed
binary than via external search) — recommend team-lead or another lane run
`agentsview skills install --help` and inspect for a `--dry-run`/`--print`
flag before invoking, per this repo's `do-not.md` #11 (never write to
`~/.claude` or `~/.codex`).

### Updated ranked digest (recall brief inserted)

1. **`othmanadi/planning-with-files`'s own plan file + Topic Handoff
   Pattern** — still the top candidate for the plan/next-task carrier
   itself (unchanged from the original digest).
2. **Native `PreCompact`/`SessionStart(compact)`/`SessionEnd(clear)`
   hooks** — still the missing enforcement layer (unchanged).
3. **`agentsview recall brief`** — a genuinely complementary, ALREADY-
   INSTALLED tool for the durable-knowledge side of the problem (the
   "what have we learned across all past sessions" query this repo
   currently answers via its own `graphify-out/memory/` + `kb-reflect`
   pipeline, which is a bespoke reimplementation of exactly what `recall
   brief` does natively). Worth a follow-up question to Ray: should this
   repo's own `kb-remember`/`kb-reflect` work-memory loop be RETIRED in
   favor of `agentsview recall`, now that recall's extractor/review/
   evidence pipeline appears to duplicate it near feature-for-feature?
   That is a separate decision from the plan-file question this search was
   scoped to, but it is the same use-tool-builtins.md question applied to
   a second custom mechanism this repo built before checking if the tool
   already did it.
