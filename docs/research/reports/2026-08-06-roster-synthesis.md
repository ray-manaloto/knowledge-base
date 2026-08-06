# Roster synthesis — standing subagents for the knowledge-base repo

Synthesist agent, 2026-08-06. Written incrementally; each finding names the route
that produced it (graph query vs file read as control arm).

Status: COMPLETE (2026-08-06). Every §1–§4 finding names its route; §5 is the
proposed roster; §6 is what a human must decide.

## 0. Method log

- `mise run kb-query -- "advisor executor routing doctrine …" --prose --idf` → top hits in
  `media/advisor-executor-fable5-sonnet-routing.md`, `mindstudio-advisor-executor.md`,
  `fable5-orchestrator.md`, `framework-plan-ladybug.md`, `fable-advisor.md` — the ingested
  articles are reachable and dominate the ranking (route: graph).
- `mise run kb-query -- "deep-reasoner fast-worker model binding …" --prose --idf` → the
  dsd article's named nodes surface directly: "Model Binding: deep-reasoner = opus" and
  "Model Binding: fast-worker = sonnet", plus its "CLAUDE.md Orchestration Block" node
  (route: graph).

## 1. Routing doctrine, as the corpus states it

Sources read (route: graph query first, then file as control arm):
`sources/media/fable5-orchestrator-workflow-dsd.md` (datasciencedojo),
`sources/media/advisor-executor-fable5-sonnet-routing.md` (mindstudio "Plan with
Fable 5, Build with Sonnet" — note: the graph's `mindstudio-advisor-executor.md`
source key is the OTHER mindstudio article, vendored as
`advisor-executor-claude-code-fable5.md`).

### Where the sources AGREE

1. **Top model plans/judges; cheaper models execute.** dsd: "use Fable only for
   planning and judgment calls, and delegate the rest to cheaper subagents"
   (`fable5-orchestrator-workflow-dsd.md:10`). mindstudio: "The advisor defines
   *what* to do and *how* to approach it. The executor does the actual work"
   (`advisor-executor-fable5-sonnet-routing.md:28`).
2. **The token VOLUME goes to the executor.** mindstudio: "Workflows that route
   70–80% of token consumption to the executor … typically see 40–60% cost
   reductions" (lines 44, 268). Matches this repo's adopted doctrine (graph node
   "70–80% executor token share").
3. **Review is a separate, advisor-tier step, never self-review.** mindstudio:
   "the executor tends to rationalize its own output rather than critique it
   critically" (line 72) — the corpus node "Self-review is weaker than
   cross-model review". This repo already operationalises a stronger form:
   cross-FAMILY review (kb-review, one cold lane, 2-round bound).
4. **Bounded review loops.** mindstudio Step 5: "Set a maximum number of review
   cycles (usually 2–3)" (line 183) — independently rediscovered by this repo's
   kb-review stop rule (memory: 19/9/3/1 convergence only WITH a stop rule).
5. **Effort discipline.** dsd: `/effort high`, "max effort burned through tokens
   fast for output that wasn't actually better than high" (line 57).
6. **Anthropic's own docs agree on shape** (route: graph, prose hits):
   managed-agents multiagent-orchestration uses an opus-class coordinator with
   cheaper specialized subagents (haiku researcher example); choosing-a-model
   maps "fast+economical strong reasoning + sub-agents → Haiku 4.5".

### The dsd per-role model binding, verbatim

- `deep-reasoner` → **Model: opus** — "Use for reasoning-heavy phases,
  architecture, debugging complex issues, algorithm design. Think thoroughly,
  return a concise conclusion the orchestrator can act on." (recovered appendix,
  `fable5-orchestrator-workflow-dsd.md:143`)
- `fast-worker` → **Model: sonnet** — "Use for mechanical tasks, boilerplate,
  tests, formatting, simple edits. Execute efficiently." (line 149)
- CLAUDE.md block: "You (Fable) are the orchestrator. Plan, decompose,
  synthesize. … For high-stakes decisions, run deep-reasoner twice with slightly
  different framings and synthesize the best of both. Keep your own context
  lean." (line 156)
- Fallback: "You can run this exact structure with Opus as the orchestrator
  instead, and Sonnet as the sole subagent. The delegation logic … stays the
  same." (line 105) — the corpus's written form of the house Fable→Opus
  procedural fallback.
- Pricing ground: Fable $10/$50 ≈ 2× Opus 4.8, 3–5× Sonnet 5 (lines 20–27).
- Gotcha worth a roster note: safety classifiers can silently reroute a Fable
  session to Opus 4.8 (line 95) — the fallback must be *procedural*, checked at
  dispatch, exactly as this repo's `.claude/CLAUDE.md` already encodes.

### Where the sources DISAGREE (or diverge in naming)

- **Two tiers vs three.** mindstudio is strictly two-role (Fable advisor /
  Sonnet executor); dsd is three-tier (Fable orchestrates, **Opus** takes
  reasoning-heavy delegated work, Sonnet mechanical). dsd's FAQ concedes the
  three-tier version "comes from the community", not Anthropic.
- **Lane naming.** `fable-advisor` (the pinned plugin source) names an
  *architect pattern* with a fable-advisor consult agent — advisor is a
  SECOND-OPINION consult at commitment boundaries, not the orchestrator itself.
  This repo's `.claude/CLAUDE.md` uses a third naming again: architect
  (Claude/Fable) + implementation lanes (`codex`/`antigravity`) + cross-family
  reviewers + terminal Opus fallback. The three namings are compatible in
  mechanism but NOT interchangeable in text — a roster must pick one vocabulary
  (this repo's) and map the others onto it.
- **Who reviews.** mindstudio has the SAME advisor model review; this repo's
  doctrine (and kb-review memory) requires a different model FAMILY. The corpus
  supports the stronger local rule ("self-review is weaker"); the roster should
  keep cross-family, not regress to advisor-reviews-own-plan.
- **Where implementation runs.** The articles are Anthropic-only (sonnet
  executor); this repo's adopted lanes delegate implementation OUT of family
  (codex = GPT-5.6 Sol). Note the articles do not contradict this — they never
  consider cross-vendor — but the roster must not cite them as evidence FOR
  cross-vendor lanes.
- **Whether the top model ever implements.** dsd/mindstudio: never (advisor
  "advises only"). The pinned `fable-advisor` repo DISAGREES with itself
  usefully: it ships THREE agents — `fable-advisor` (model: fable, tools
  Read/Grep/Glob, "Advises only — never implements", consulted at commitment
  boundaries + once at end-of-deliverable), `codex-implementer` (routine lane),
  AND `fable-implementer` (model: fable, full write tools) — "the escalation
  lane … for the small minority of tasks where getting it right matters more
  than the token bill … one-off escalations, never the default"
  (`sources/fable-advisor/agents/fable-implementer.md:3,10`). So the corpus's
  most worked-out source says: top-model implementation exists but only as a
  bounded escalation, and it must self-report broken routing ("If you find
  yourself receiving routine, fully-specified work, say so — the routing is
  broken", line 38). Its spec contract is the five-part spec: objective, files,
  interfaces, constraints, verification command (line 14).

## 2. Anti-patterns

From `advisor-executor-fable5-sonnet-routing.md` ("Common Mistakes That
Undermine the Pattern", lines 230–250) — the four named advisor/executor failure
modes:

1. **Underspecifying the advisor prompt** — "If the advisor prompt is vague,
   the plan it produces will be vague. The executor has no margin to interpret
   ambiguity." Spend prompt-engineering effort on the advisor side.
2. **Sending too much context to the executor** — "only what it needs for the
   current subtask"; full history + codebase + requirements "degrades output
   quality".
3. **Skipping the review step** — "executor errors compound, and catching them
   downstream is more expensive than catching them immediately."
4. **Using the pattern for simple tasks** — "If your task has two or three
   steps with no ambiguity, one model is fine." (= the antigravity plugin's
   break-even rule, independently.)
5. **Hardcoding the task boundary** — "Treat the routing logic as a
   configuration parameter you revisit periodically." (graph node "Mistake —
   hardcoding the task boundary".)

Also present as an explicit termination rule, not a mistake but a constraint:
**unbounded review loops** — cap at 2–3 cycles then escalate to a human
(line 183, 276).

From dsd: **max-effort waste** (effort=max not better than high, line 57) and
**silent model fallback** (safety classifier reroute, line 95 — check which
model is actually active before diagnosing).

From the graph (route: kb-query "failure modes", nodes in
`claudefa_st_blog_guide_development_dynamic-workflows.md` and
`media/fable5-vs-sonnet5-dynamic-workflows-cost.md`): "All three failure modes
get worse the longer a single context window runs and the more jobs are piled
into it" — i.e. context-hoarding in one long session; and "Define failure modes
before you run". 10x-Team's AGENTS.md and SKILL.md carry their own
"Anti-Pattern sections" (read in §3).

From mindstudio's OTHER article (source key `mindstudio-advisor-executor.md`,
graph nodes): "Mistake: skipping the structured output step" and "Keep analysis
and execution in separate scoped sessions" — same family as №2.

## 3. The 10x-Team roster

Route: graph (`10x-Team roles roster dispatching skill` --prose --idf → the
roster/dispatch nodes), then `sources/10x-Team/AGENTS.md` and
`sources/10x-Team/skills/10x-team/SKILL.md` as the control arm.

**Shape.** A Claude Code plugin of 12 role SKILLs + one `/10x-team`
orchestrator skill (13 files). The roles are NOT subagents — they are *lenses*
one model switches between ("You are not one person. You are a full engineering
team", SKILL.md:8; "the roles aren't sequential within a phase — they're
lenses", SKILL.md:526). Dispatch is phase-driven: Phase 0 brainstorm →
strategy (CTO+PM) → design (Architect+Staff) → planning (EM+Senior) →
implementation (SDE+Senior+DBA) → verification (QA+Security) → delivery
(DevOps+SRE), each phase gated by a `<HARD-GATE>` that refuses progress until
state files are written to `.10x/decisions/<role>/<feature-slug>.md`.

**What transfers to this repo:**

- **File-based handoff as team memory** — "The state files ARE the team's
  memory. Without them, you're a solo developer, not a team" (SKILL.md:30).
  This repo already has the same organs (`.agent/plans/`, `.agent/kb/reports/`,
  `graphify-out/memory/`); 10x-Team validates making every roster agent
  write-at-checkpoint mandatory, which `agent-report-persistence.md` already
  demands.
- **Hard gates at phase boundaries** — same mechanism as kb-ship/kb-land
  refusing without a review receipt.
- **Structural validation of the role files themselves** — their
  `validate-skills.test.js` ≈ this repo's `kb-skill-score` + agnix.
- **Scaling rules** ("Scaling to Task Size", SKILL.md:507-520) — process depth
  scales with task size but never to zero; matches the mindstudio "don't use
  the pattern for simple tasks" anti-pattern from §2.
- **Description is load-bearing** — "Frontmatter `description` is how the
  harness decides when to trigger" (AGENTS.md:53); directly applicable to
  `.claude/agents/*.md` descriptions here.
- **Curated roster over quantity** — "New skills need explicit user approval —
  this plugin's value comes from a curated set of roles, not quantity"
  (AGENTS.md:49). Constrains §5: propose FEW agents.

**What does NOT transfer.** This is a corpus/knowledge tool, not a product
team. CTO, Product Manager, Engineering Manager, DevOps, SRE, DBA have no
referent here (no runtime, no deploys, no schema, no customers). QA maps onto
the existing gate tasks (`kb-gates`), not an agent. Security maps onto gitleaks
in `hk.pkl`. The transferable roles are: Architect (≈ the session/architect
itself, not a subagent), Senior/Staff review (≈ kb-review's cold cross-family
lane, which this repo deliberately keeps OUT of family — stronger than
10x-Team's same-model lenses), SDE (≈ the implementation lanes codex/agy,
already owned by plugins, not this roster), and researcher/curator/verifier
roles 10x-Team doesn't have at all. Conclusion: adopt 10x-Team's *mechanics*
(state files, hard gates, load-bearing descriptions, curation), not its role
list.

## 4. Prior art: claude-self-reflect (CSR)

Route: graph (prose hits in `claude-self-reflect/CLAUDE.md` + `README.md`;
study graph reached the engine: `csr-engine/src/mcp/tools.rs` →
`reflect_on_past()`, `.store_reflection()`, `scoring.rs`), then
`sources/claude-self-reflect/CLAUDE.md` read as control arm.

**What it indexes.** `~/.claude/projects/*.jsonl` (past conversations, primary
corpus), `~/.claude/tasks/<session>/` (authoritative task state → episode
outcomes), `~/.claude/plans/*.md`, `~/.claude/history.jsonl` (session spine,
never embedded). Deliberate NON-goals: memories and paste-cache are NOT indexed
— "circularity / privacy — deliberate non-goals" (CLAUDE.md:26), and the README
carries the sharper form the graph surfaced: **"Self-recording memory
contaminates its own eval."**

**How reflection is surfaced.** Six hooks, not agent turns: SessionStart
injects past context "framed as history, not instructions"; UserPromptSubmit
does predictive injection; Stop stores iteration learnings; SessionEnd stores a
narrative (CLAUDE.md:118-127). Enrichment runs in a background daemon.

**Tool surface.** 15 MCP tools (CLAUDE.md:44-62): `csr_reflect_on_past`
(semantic search), `store_reflection`, recency/file/concept search,
`get_session_learnings` ("iteration memory for Ralph loops"), `csr_code_graph`
(which conversations shaped a function), `csr_why` (provenance chain), and —
the governance-relevant one — **`csr_resolve`**: verdicts
(resolved/still_open/regressed) are recorded on chunks and "resolved demote +
annotate in future searches", with completed tasks only *proposing* resolutions
that "a human promotes via `csr_resolve`" (CLAUDE.md:23,61).

**Scoring of past outcomes.** Local embeddings (FastEmbed 384-dim) + HNSW;
age-decay is in the retrieval scoring (mtime-based decay noted for plans;
`scoring.rs` in the engine). Outcome scoring is verdict-based via `csr_resolve`
rather than automatic.

**What transfers here.** (a) The reflection WRITE path stays gated by a human
(csr_resolve promotion ≈ this repo's `/skillopt-sleep adopt` control). (b)
Injected memory is history, not instruction — matching how this repo's memory
system already frames recalled notes. (c) Outcome verdicts on past answers are
a concrete design for scoring `graphify-out/memory/` entries — `kb-remember`
already records `--outcome useful`; CSR adds the *revisit* verb (a later
session can mark a remembered lesson regressed/still-open). (d) The
contamination warning constrains any kb-reflector agent: it must never score
its own outputs as evidence of its own quality.

## 5. Proposed roster

Constraints honoured: valid frontmatter keys only
(`sources/agent-harness-docs/docs/claude-code/sub-agents.md:276-297`); `model`
∈ sonnet|opus|haiku|fable|full-id|inherit; `effort` ∈ low|medium|high|xhigh|max;
NO per-subagent thinking setting — effort is the only depth lever; names carry
no `:`. Session model is Opus 5, so `inherit` = Opus here; every binding below
is explicit precisely so the roster does not silently ride the session model.
Curation rule from 10x-Team (§3): few roles, explicitly approved — 4
re-attributed + 2 new + 1 deferred, not 13.

**Tier mapping used throughout** (from §1): advisor-tier work (decompose,
judge, review, synthesize) → `opus`; executor-tier work (spec-driven volume) →
`sonnet`; `fable` is deliberately ABSENT from the standing roster — the
fable-advisor consult and Fable-as-architect are already owned by the
fable-orchestrator plugin and the session itself, and duplicating them here
would violate use-tool-builtins and the "expensive, consulted sparingly"
doctrine. Effort: `high` for judgment roles (dsd: high is the ceiling default;
"max … wasn't actually better", line 57), `medium` for executors.

### 5.1 Re-attribute in place (the four existing agents)

| agent | model | effort | tools | why |
|---|---|---|---|---|
| `kb-adversarial-verifier` | `opus` | `high` | `Bash, Read, Grep, Glob` (drop inherit-all) | Refutation is advisor-duty-2 work (mindstudio: review/validate is an advisor task; "the executor tends to rationalize its own output", line 72). Constructing a probe that CAN return the other answer is judgment, not volume. Read-only + Bash matches Attacca's critic shape (`model: sonnet, tools: Read, Bash, Grep, Glob` — we go opus because this repo's verifier history shows sonnet-grade probes being the thing that failed: five false negatives in one session, memory-documented). It never edits, so Write/Edit should not be inheritable. |
| `kb-corpus-curator` | `sonnet` | `medium` | inherit (needs Bash + Write/Edit for manifests, chunks) | Pure executor profile: a fully-specified pipeline of `kb-*` tasks (dsd fast-worker = sonnet, "mechanical tasks … Execute efficiently"; mindstudio executor conditions — clear instructions, defined output format, bounded scope — are exactly what the agent file already provides). Its own doc says escalate rather than decide on headroom ("stop and report — that is a decision for a human"), so opus depth buys nothing. |
| `kb-synthesist` | `opus` | `high` | `Read, Grep, Glob, Write, Edit` (no Bash needed — it must NOT re-run probes) | mindstudio names "synthesizing complex research into a structured brief" as an advisor task (line 113). Carrying each fact's condition, refusing to fill holes, and noise-floor reasoning are judgment. Denying Bash enforces its own contract ("you do not research and you do not verify"). |
| `kb-tool-researcher` | `sonnet` | `high` | inherit | Research-lane precedent is mid-tier: Attacca researcher = sonnet; Anthropic's multiagent-orchestration example uses an even cheaper researcher (haiku) under a capable coordinator. But this researcher must ARM absences (its own doc), which is why effort is high, not medium — depth of skepticism, not model class, is what its failure history demanded. Haiku rejected: the armed-absence discipline is exactly what a fast model skips. |

### 5.2 New agents

| agent | model | effort | tools | role |
|---|---|---|---|---|
| `kb-extraction-worker` | `sonnet` | `medium` | `Read, Write, Grep, Glob` | One raw file → one `{nodes,edges}` chunk, the kb-extract fan-out unit. THE textbook executor: bounded scope, defined output format, advisor (the orchestrating session) has already decomposed (mindstudio Step 3 "Keep executor prompts tight", line 153-162; dsd fast-worker binding). Today the fan-out uses `general-purpose` agents — a standing def pins the model (cost control at 164-source/~18.5M-token backlog scale), the output contract, and the incremental-persistence instruction (`agent-report-persistence.md` rule 3). No Bash: it must not "helpfully" run kb-merge itself; validation and merging stay with the curator/session. |
| `kb-fallback-reviewer` | `opus` | `high` | `Bash, Read, Grep, Glob` | The terminal review fallback the house doctrine already names ("terminal fallback is always a Claude Opus subagent (never silent)", `.claude/CLAUDE.md`) but which exists nowhere as a definition — today it would be improvised at the worst moment (both CLI lanes down). Shape copied from fable-orchestrator's reviewers: cold, by REF, no design context, findings with file:line, never edits. Used ONLY when codex/agy are unavailable; its description must say so, since description is what triggers dispatch (10x-Team AGENTS.md:53). |

### 5.3 Deferred to the self-reflection round (design sketched, not proposed for creation now)

`kb-reflector` — aggregates `graphify-out/memory/` + reflections, proposes
verdict updates on past lessons (CSR's `csr_resolve` revisit verb, §4c) and
bounded memory/skill edits. `model: opus`, `effort: high`. Two hard constraints
from §4: every write is STAGED behind a human adopt gate (CSR promotion ≈
`/skillopt-sleep adopt`), and it never scores its own output (contamination).
Whether it exists as an agent at all — vs extending `kb-reflect` + SkillOpt —
is open question 3.

### 5.4 Roster-wide conventions (from the corpus, applicable to all defs)

- **Description is load-bearing and trigger-oriented** (10x-Team AGENTS.md:53);
  Attacca adds a `Delete when:` line per agent — worth adopting: each def
  states the condition under which it should be retired
  (`tool-currency-and-native-first.md` in file form).
- **Model tiers, never dated model ids** (Attacca CLAUDE.md) — matches the
  sub-agents doc's alias list and survives model generations.
- **Every findings-bearing agent persists incrementally** to
  `.agent/kb/reports/agents/<name>.md` — already in kb-tool-researcher; should
  be stated in all defs (two agents died holding everything in memory; a prior
  agent THIS session did too, per the dispatch note).
- **No `memory` frontmatter for now** — CSR's contamination warning + this
  repo's work-memory already provides the durable layer through a reviewed,
  committed path (`graphify-out/memory/`), not per-agent auto-memory.

## 6. Open questions

1. **Does the kb-extract workflow adopt `kb-extraction-worker`?**
   `.claude/workflows/kb-extract.js` currently fans out `general-purpose`
   subagents. Wiring the named agent in changes a committed workflow; and at
   backlog scale (~18.5M tokens, 164 sources) the sonnet-vs-haiku choice is a
   real cost fork the corpus does not settle (Anthropic's example uses haiku
   for researchers; extraction chunks are committed forever, arguing for
   sonnet). Human call on both.
2. **Should `kb-fallback-reviewer` exist as a standing def, or does the
   fable-orchestrator plugin's fallback doctrine suffice?** Risk of a standing
   def: it gets dispatched when the CLI lanes are UP (same-family review, which
   kb-review exists to prevent). Mitigation is description wording, which is
   soft. The corpus has no evidence either way on standing-vs-improvised
   fallbacks.
3. **Reflection governance.** Agent vs task-extension; whether verdict
   revisiting (CSR `csr_resolve`) enters `kb-remember`'s schema; who holds the
   adopt gate. The corpus gives the constraints (§4) but not the shape.
4. **Tools-allowlist tightening on the existing four** (5.1 proposes dropping
   inherit-all for verifier and synthesist) — a permissions change to
   already-working agents; cheap to do, but it is a behavior change to shipped
   defs and should be its own reviewed diff.
5. **Effort inheritance ambiguity.** `effort` "inherits from session" when
   omitted; the session's effort varies by how Ray runs it. The bindings above
   pin effort everywhere to avoid that variance — confirm that is wanted
   (it costs flexibility).

## GitHub repos touched

All URLs verified against `sources/*.manifest` (my first-guess owners for
10x-Team, Attacca and fable-advisor were WRONG — the manifests refuted them;
worked instance of the inherited-number rule):

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — kb-query/explain CLI used for every graph route in this report
- [Jaan-Mustafa/10x-Team](https://github.com/Jaan-Mustafa/10x-Team) — pinned study source; roster + dispatch analysis (§3)
- [ramakay/claude-self-reflect](https://github.com/ramakay/claude-self-reflect) — pinned study source; self-reflection prior art (§4)
- [adihebbalae/Attacca](https://github.com/adihebbalae/Attacca) — pinned study source; critic/researcher agent defs (§1, §5)
- [DannyMac180/fable-advisor](https://github.com/DannyMac180/fable-advisor) — pinned source; advisor/implementer lane naming and five-part spec (§1)

(The four articles are vendored under `sources/media/` with `source_url`
frontmatter — datasciencedojo, mindstudio ×2, claudefa.st — provenance is the
vendored file, per `research-repo-enumeration.md`'s manifest-beats-list rule.)
