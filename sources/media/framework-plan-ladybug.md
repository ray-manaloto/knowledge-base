# Plan — Long-running autonomous multi-agent research framework on Fable-5 + graphify/Obsidian KB

> **STATUS: DRAFT (plan mode).** Phase-1 exploration in flight (explore-kb / explore-orch /
> explore-autonomous). This skeleton holds what is already firmly established this session; the
> exploration results + a Plan-agent design pass will fill the architecture and the file-level steps.

## Context

**What the user wants:** a *long-running autonomous multi-agent framework* that
1. uses the **Fable-5 orchestrator/advisor** (adopted this session — fable-orchestrator + antigravity
   plugins; Claude architect → codex/antigravity lanes → Opus fallback);
2. integrates **graphify + Obsidian** as the knowledge substrate agents use *for research*;
3. has agents **read the KB repo's graphify/Obsidian graph** to ground each research pass; and
4. **compounds the knowledge base on every pass** — writing findings back and **re-shaping the graph
   topology** (communities, god-nodes, edges) as knowledge grows.

**Why now / what prompted it:** this is the convergence of two in-flight programs —
- the **autonomous-execution program** (research done 2026-07-19: cost-routed orchestrator on a graphify
  KB, DBOS control plane, verify-gate oracle; design agreed, build pending), and
- the **graphify second-brain research** (this session: `graphify update` ingests a markdown vault free;
  deterministic `kb-query`; the collision-safe `kb-remember`/`kb-reflect` learning overlay; and the
  dogfood-pass finding that the **Capture→Map→Ask→Write-back self-maintaining loop** + `kepano/obsidian-skills`
  "hands" + `lucasrosati/claude-code-memory-setup` prior art already exist — novelty narrows to
  **grounding the orchestrator's routing in the graph** and to the **autonomous compounding loop**).

**Intended outcome:** a design (this plan) + a prototype path for an autonomous loop that runs research
passes, grounds each in the KB graph, writes results back through the learning overlay, and periodically
re-clusters the graph — the whole thing driven by the Fable-5 architect and cheap executor lanes.

## Firmly-established building blocks (verified this session — do not re-derive)

- **Ingest (free):** `graphify update <path>` = structural quick-scan, 0 LLM tokens; wikilinks→edges.
  Flock-serialized (`.rebuild.lock`, #1059) so concurrent `update` is safe. Plain `graphify <path>`
  build routes markdown to a PAID semantic pass that writes nothing on no-key failure — avoid.
- **Query (free, deterministic):** `mise run kb-query -- "<q>"` → source-cited subgraph, 0 tokens,
  budget-capped, sub-second. CLI shell-out is the default grounding surface (no MCP schema tax);
  `kb-serve` MCP is opt-in for query-heavy runs.
- **Write-back (cheap, collision-safe):** `kb-remember` appends one `memory/*.md` per outcome (never
  touches `graph.json`); `kb-reflect` aggregates → `LESSONS.md` + a learning overlay tagging nodes
  preferred/tentative/contested → later queries surface a "Lesson:" hint.
- **Topology growth:** new knowledge needs the expensive `kb-merge`/re-cluster (Louvain). `graph.json`
  merge is the ONE operation with a lost-update risk (no flock) → needs a single serialized writer.
- **The "hands":** `kepano/obsidian-skills` (MIT, cross-agent) writes valid Obsidian (Markdown/Bases/
  Canvas/CLI/Defuddle) — the concrete write-back mechanism.
- **Prior art to fork, not rebuild:** `lucasrosati/claude-code-memory-setup`, `albertludi/second-brain-claude`.

## Open design questions (to resolve before the final plan)

1. **Autonomy mechanics** — how the loop stays alive long-running (DBOS durable workflows? the Workflow
   tool for fan-out? the run-lane supervisor beating the 10-min cap? cron/schedule?). Reconcile with the
   prior autonomous-program decision.
2. **The compounding loop's write path** — outcome notes (collision-safe, fan out freely) vs the
   serialized `graph.json` merge/re-cluster (single writer). Cadence of re-clustering as the graph grows.
3. **Semantic-enrichment cadence** — free structural layer always-on vs paid semantic rebuild trigger
   (#1915: semantic supersedes structure).
4. **Where the vault/graph lives + who writes it** — KB repo (exists) vs new; the single graph-writer.
5. **Grounding-in-routing** — how the architect actually queries the graph mid-decision (the genuinely
   novel seam; the orchestrator-routing skill prescribes it but the loop must wire it).

## Phase-1 exploration findings (direct — Explore agents stalled, read the sources myself)

### This is a REFOCUS of an already-designed program (don't re-litigate the 13 locked decisions)
The prior `/grilling` (`.omc/plans/plan-20260719-autonomous-execution-program.md`) already locked the
architecture for an autonomous graphify-substrate program. The new user vision = its **Knowledge layer
(②) + a research-specialized orchestrator loop (④)**, with **Obsidian** added as the read/write surface.
Already-settled and reused as-is:
- **Build ON graphify** (hybrid); do NOT adopt a graph-DB memory service (Graphiti/Zep/mem0/cognee all
  lose on host-only + pay-twice re-ingest). graphify maturity risk = MEDIUM, well-mitigated (pin, own the
  portable JSON, lean on the free AST layer).
- **Cost-routed orchestrator = ADOPTED plugins** (fable-orchestrator + antigravity): architect-only strong
  model (never types, deny-hook no-touch list) → cheap executor lanes via **six-part spec** → **verify-gate
  (lint/pytest/verify) = the one load-bearing quality oracle we already own**. Cross-vendor = Bash shell-out
  via `run-lane.sh` (the long-running supervisor — see below).
- **Graphify-first read-through** (agents query the graph before web) + **RAG the graph into workers** as
  cheap source-cited context (the whole payoff).
- **Write-back = queued + gated + provenanced, NOT inline/auto** (locked decision #11) — knowledge-poisoning
  + staleness risk (#1758 ~35% chunk loss, #2051 stale nodes returned authoritative) makes auto-ingest
  dangerous. graphify's own `save-result`/`reflect` overlay (= KB's `kb-remember`/`kb-reflect`) is the
  low-risk write-back tier.
- **Four gaps = the only genuinely-new engine work:** G1 query-time age-staleness scoring; G2 lightweight
  single-fact append; G3 per-tool expert-view selection; G4 the read-through routing rule.
- **Long-running autonomy is MOSTLY NATIVE** (CC auto-mode + `defer` hook + channels + `/goal` + Routines +
  `/loop` + background tasks + SessionEnd/Stop hooks). "BUILD = orchestrator glue only."

### The KB repo already has the machinery (verified in `mise.toml`)
`kb-build` (free reproduce), `kb-update <name>` (advance source + incremental AST), `kb-query` (deterministic,
0-token), `kb-serve` (MCP, absolute-graph-pinned), `kb-add <url>` (Gemini-blanked), **`kb-merge <chunk.json>`**
(build_merge + **Louvain re-cluster** = the topology-growth op, no-LLM), `kb-label` (deterministic labeler),
`kb-transcribe` (local whisper), `kb-artifacts` (incl. **obsidian export**), **`kb-remember`** (append
`memory/*.md`, git-tracked), **`kb-reflect`** (→ `LESSONS.md` + `.graphify_learning.json` overlay tagging
nodes preferred/tentative/contested). The compounding loop's primitives EXIST; what's missing is the
**autonomous outer loop that drives them research-pass after research-pass**.

### The long-running supervisor exists (`run-lane.sh`, fable-orchestrator)
`start <lane> <spec> [secs] [model]` launches a detached CLI + watchdog (beats the harness 10-min cap;
process-group discipline `kill -- -PID`; `EXIT:`/`WATCHDOG:` markers), `wait <pid>` (≤90s bounded slices),
`reap`. Lanes: `codex`/`grok` implement, `codex-review`/`grok-review`, **`grok-research`** (web+read
allowlist). antigravity lane via the antigravity plugin. This IS the "launcher-wrapped shell-out with
completion-contract" the prior research prescribed — now maintained upstream.

### The genuinely-new design surface (this vision's delta)
1. **The autonomous RESEARCH-COMPOUNDING loop** — architect decomposes a research question → routes
   sub-questions to lanes (each queries the KB graph FIRST, researches, returns a structured finding) →
   findings persisted (agent-report-persistence) → **gated** write-back (`kb-remember` always; `kb-merge`
   re-cluster on approved batches) → next pass stands on the compounded graph. Loop driver = native
   `/loop`/Routines/background + the run-lane supervisor.
2. **Topology-growth cadence** — when `kb-merge` re-clusters (Louvain) as nodes accrete; G1 staleness so
   grown-but-stale nodes don't dominate; keeping community labels stable across regrows.
3. **Obsidian as the human+agent surface** — `kb-artifacts` obsidian export (graph→vault) + `kepano/obsidian-skills`
   "hands" for agent-authored notes back into the vault → re-ingested. The human curates/reviews here (the
   gate for write-back).
4. **DECISION PENDING (inherited): the long-running substrate** — native CC primitives (`/loop`+SQLite claim
   table, "glue only", host-only) vs **DBOS Transact** durable workflows (SQLite→containerized-Postgres,
   same code, more robust). Prior work leaned native-first; not finalized.

## Open forks for the user (blocking the final plan) — see AskUserQuestion
1. **Deliverable this arc:** design doc only, or design + a working prototype of one compounding loop?
2. **Write-back cadence:** the locked "gated/batched" (safe, human-approves each compound) vs "auto-compound
   every pass" (the literal ask, but carries the poisoning/staleness risk the prior program deliberately avoided).
3. **Long-running substrate:** native CC primitives (light) vs DBOS durable workflows (robust).
4. **Home:** default = the **knowledge-base repo** (has every `kb-*` task) unless told otherwise.

## DECISIONS LOCKED (user, this session)
- **Write-back: auto-compound every pass, BUT build G1 query-time staleness scoring FIRST** so stale/
  low-confidence nodes are down-weighted at query time (makes auto-compounding safe — overrides the prior
  program's "gated" decision #11 consciously).
- **Substrate: native CC primitives** (**`/goal`** work-until-condition + `/loop` + Routines + background
  tasks + a SQLite claim/lease table + the `run-lane.sh` supervisor). No DBOS now (it stays the documented
  graduation path). **`/goal` is the native outer-loop driver** — see the appendix `/goal` finding.
- **Home: the knowledge-base repo** (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base`).
- **Deliverable: design + a phased prototype** (Ray's "go all the way" arc); immediate buildable = Phase 0+1.
- **NO NEW BASH SCRIPTS — everything in python** (`dotfiles_setup` and/or `kb_setup`), mise tasks as thin
  seams only. Extends the existing `zero-bash-logic` rule to BOTH repos. **`run-lane.sh` MUST be ported to a
  python lane-supervisor module** (its logic — detached launch, watchdog, process-group reap, completion
  contract — moves into python; OUR research loop calls the python supervisor, not the plugin's bash). We
  adopt the fable-orchestrator *doctrine* (architect + six-part spec + routing) but not its bash lane-launch.
  Audit the KB repo for any other bash and port it; extend the `bash_budget`-style gate to the KB repo.

## THE CORE INVARIANT (user, this session — reshapes everything below)
**The KB library is the ONLY way an agent can search. Agents have NO direct web access.** Every research
lookup goes through one tool — `kb_search(question)` — which is a **read-through proxy**:
1. Query graphify (`kb-query`, staleness-scored) → **hit** (fresh, confident): return the cited subgraph.
2. **Miss** (absent / stale / low-confidence): the **library itself** does the web search, fetches, extracts,
   and **ingests into graphify** (`kb-add`/host-agent-extract → `kb-merge` re-cluster), THEN returns the
   now-ingested, cited result.
Consequence: **no fact reaches an agent without being captured into the graph** — the KB compounds on every
external lookup, through one network-egress point (the library). **Per review R1, capture is
*eventually*-synchronous, not by-construction:** the READ tier is a pure deterministic call safe for any
lane; a miss *enqueues* an ingest job the Claude architect drains out-of-band (the miss-leg's host-agent
extraction is a Claude `Task`/`Workflow` step, not runnable inside a codex/antigravity lane). "Any new
research must be added to graphify if it doesn't exist" still holds — just asynchronously. **Enforcement is
a per-family deny-hook matrix (R2), not a `tools:` allowlist.**

## Programmatic Tool Calling (PTC) — researched; feasibility verdict
Doc: `platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling` (fetched + to be
**dogfood-ingested into graphify as Phase-0 step 1** per the invariant above).
- **What it is:** an Anthropic **Messages API** feature — Claude writes Python in a code-execution sandbox
  that calls your custom tools as `async` functions; intermediate tool results stay in the code, only the
  final output enters context (20–40% fewer input tokens on 10–49-tool workloads; +11%/−24% tokens on
  agentic-search benchmarks — a STRONG fit for our research/retrieval loop).
- **Enforcement caveat (load-bearing):** `allowed_callers` (`["direct"]` / `["code_execution_20260120"]`) is
  **explicitly NOT a security boundary** — "Do not rely on `allowed_callers`." So PTC is **not** what
  prevents web search.
- **The real enforcement = tool availability:** give each research agent exactly ONE knowledge tool
  (`kb_search`) and NO WebSearch/WebFetch/web tool at all. `run-lane.sh` already does allowlisting (its
  `grok-research` lane passes `--tools 'web_search,...'`); we invert it — allowlist `kb_search` only, drop
  web tools. The library holds the sole network egress.
- **PTC availability:** API-only (Claude API / AWS / MS Foundry — NOT Claude Code subagents, NOT the
  codex/antigravity CLI lanes, NOT Bedrock/GCP). **MCP tools cannot be PTC-called** → the KB library must be
  exposed as a NON-MCP custom function to use PTC. Needs `code_execution_20260120`+ and the code-execution tool.
- **VERDICT: the KB-only read-through design is fully achievable NOW via tool allowlisting** (CC-subagent
  `tools:` + the CLI-lane allowlists). **PTC is an optional efficiency layer for a future Messages-API-built
  research worker** (where `kb_search` is the only defined function → nothing else exists to call, which is
  also the hardest enforcement). Adopt tool-allowlisting first; treat PTC as a measured optimization later.

## ADVERSARIAL REVIEW OUTCOME (36-agent workflow, 30 findings → 21 survived refutation)
Full findings: `/private/tmp/claude-501/.../tasks/w712jw8et.output` + workflow journal. Verdict: **sound
to execute after R1–R5; ⓪ `kb_search` needs a redesign (a scoping correction, not an architecture
teardown).** These revisions SUPERSEDE the affected sections below.

- **R1 (blocker) — split `kb_search` into two tiers.** The miss-leg (web→fetch→**host-agent extract**→
  kb-merge) is a Claude `Task`/`Workflow` step (KB `CLAUDE.md:41,75-80`), NOT pure Python — it cannot run
  inside a codex/antigravity lane nor a Claude subagent holding only `kb_search`. So: **(a) READ tier** =
  deterministic `kb-query` (staleness-scored, 0-token) — safe to hand any lane; **(b) miss** = *enqueue* a
  "not-yet-known" ingest job the **Claude architect drains out-of-band** (existing kb-add→host-extract→
  kb-merge fan-out, already at loop level in step 5). Invariant softens from "captured **by construction**"
  → **eventually-captured** (still: no research escapes the graph, just asynchronously). *[USER-VISIBLE
  change to the stated invariant — confirm.]*
- **R2 (blocker) — enforcement is a per-family matrix + a PreToolUse Bash deny-hook, NOT `tools:` allowlist.**
  `kb_search` is `mise run kb-search` (Bash), so lanes must hold Bash, which is superset egress
  (`python3 -c urllib`, `nc`) that `tools:` can't scope. Fix per family: **CC/Claude** → PreToolUse deny-hook
  allowing Bash only for `mise run kb-search` (dotfiles `hook_guard.py` already owns this pattern); **grok** →
  `run_terminal_command` calling `mise run kb-search`, `--tools read_file,list_dir,grep`, NO MCP bridge;
  **codex** → `-c tools.web_search=false` + `--sandbox workspace-write` (network-off); **antigravity** →
  **CORRECTED (user challenge + antigravity.google/docs/cli/permissions): it HAS native fine-grained
  enforcement** in `~/.gemini/antigravity-cli/settings.json` — `deny`/`ask`/`allow` lists with `action(target)`
  rules. Lock KB-only: `deny:["read_url(*)","execute_url(*)","mcp(*)","command(*)"]` +
  `allow:["command(mise run kb-search*)"]` (denies web-fetch/browser/MCP/terminal BEFORE the agent runs;
  allow re-opens only the KB command — confirm specific-allow-over-broad-deny precedence + `command()` regex).
  So antigravity STAYS a full KB-only research lane; the review's "un-strippable web" was the `yuting0624`
  plugin's `--yolo` wrapper, not the CLI's own permission model (`toolPermission`/`enableTerminalSandbox` also
  exist). macOS: for GROK the boundary is **policy/deny-hook, not sandbox** (its kernel sandbox doesn't
  confine child-process network); codex `workspace-write` is network-off; antigravity is config-denied.
- **R3 (blocker) — re-scope G1; `confidence` is NOT a truth signal.** graphify `confidence` is **edge-only**
  and `captured_at` is **null on the free AST layer**; worse, `EXTRACTED=1.0` (verbatim web copy) scores
  HIGHEST, so G1-as-specified rewards the poisoning path. Score real fields: `captured_at` where host-
  extraction set it (define the structural-node default explicitly), git/source mtime for age, and node
  `verification="unverified"` (llm.py:619) as the low-confidence signal. Control-arm on a REAL AST node with
  no `captured_at`.
- **R4 (blocker) — reuse graphify's `_rebuild_lock`, don't add a new flock (②).** `graphify.watch._rebuild_lock`
  on `.rebuild.lock` already exists; a separate kb_setup flock reinvents it (use-tool-builtins) AND doesn't
  serialize against a concurrent `graphify update`. Acquire graphify's lock; control-arm the REAL race
  (kb-merge vs `graphify update`).
- **R5 (blocker, 2 findings CONFIRMED) — DROP the run-lane.sh python port (⑥); call it via a thin seam.**
  `run-lane.sh` is a maintained third-party plugin; **`plugins/**` is explicitly EXEMPT from zero-bash-logic**
  (rule line 26), so "the no-bash rule requires the port" is factually false, and re-porting forks a
  maintained upstream (use-tool-builtins HARD GATE). Prefer `mise run kb-lane` → subprocess call of the
  vendored script (a wrapper, not new logic). *[REVERSES the user's "port run-lane.sh to python" directive —
  needs the user's call; see AskUserQuestion.]*
- **R6 (major) — real egress control-arm.** Replace "inspect the tool list" with: from each live lane family,
  attempt a non-curl fetch (urllib/nc) to a canary and assert it **FAILS**; assert the lane CAN reach the KB.
- **R7 (major) — name the web-SEARCH backend** (graphify `add` is URL-fetch only; question→URL search is
  net-new, held solely inside the library, an external-service egress dependency).
- **R8 (major) — narrow the poisoning safety CLAIMS to match reality.** Delete "makes auto-compounding safe"
  / "G1 ensures freshness" as a *safety* argument (staleness≠correctness; a fresh-but-wrong node returns
  authoritative). Keep the risk-accepted framing; add: amplification (a poisoned node gains corroborating
  edges → Louvain hub; add provenance-aware down-weighting or accept as residual), Obsidian review is
  **after-the-fact observability not a write gate** under autonomy, and note ingest's 12000-char truncation
  + #1758 ~35% chunk loss make a compounded node a *distorted copy*.
- **R9 (minor) — make the gated fallback a real one-flag toggle** (gate whether ③ auto-fires `kb-merge`).
- **R10 (minor) — fix the Obsidian contradiction:** demote the "hands"/write-back-mechanism references to
  "evaluated & rejected (Model B)"; Obsidian is a derived human-curation view, not "the substrate agents use."

## Final architecture — the autonomous research-compounding loop

One **research pass** (the unit the loop repeats), all in the KB repo, driven by the Fable-5 architect:

1. **Frame** — a research question is pulled from a queue (a `questions/` file or the SQLite claim table).
2. **Ground (staleness-aware)** — architect runs `kb-query` through the **new G1 staleness scorer** to see
   what the KB already knows, down-weighting stale/low-confidence nodes → decomposes into sub-questions,
   routing each per `orchestrator-routing` (codex / antigravity / grok-research / Opus).
3. **Delegate** — each sub-question → a lane via the **python lane-supervisor** (`mise run kb-lane -- start
   <lane> <spec>`, ⑥) with a six-part spec: "your ONLY search tool is `kb_search`; return a structured finding
   with provenance." Watchdog-supervised (beats the 10-min cap; process-group reaping). Agents get NO web tool.
4. **Collect + persist** — findings persisted verbatim (`agent-report-persistence`) with provenance (source,
   agent, timestamp, confidence).
5. **Compound (auto + staleness-guarded)** — `kb-remember` logs every outcome (git-tracked); new knowledge is
   host-agent-extracted into chunks and **`kb-merge`'d under the single-writer lock** → `build_merge` +
   **Louvain re-cluster** grows the graph and adjusts its topology. Provenance/confidence tags travel with
   the nodes; G1 ensures the NEXT pass treats them by freshness.
6. **Reflect** — `kb-reflect` → `LESSONS.md` + the `.graphify_learning.json` overlay (nodes tagged
   preferred/tentative/contested), so lessons surface on later queries.
7. **Surface** — `kb-artifacts` obsidian export (graph→vault, one derived view); the human browses / curates /
   repairs in Obsidian (the safety valve under auto-compound), and edits round-trip back via `graphify update`
   (export preserves non-owned notes, #1506). No agent-side "hands" — agents write only through `kb_search`.
8. **Loop** — the native driver advances to the next queued question (or a frontier the architect names);
   the SQLite claim/lease table prevents double-work and records pass outcomes; escalate to the human on a
   genuine decision (locked policy #1/#7), never silently.

## The genuinely-new engine work (everything else is existing tasks + glue)

All in the KB repo; **zero-bash-logic** (logic in `python/` `kb_setup`, thin mise-task seam); each ships
with control-armed tests.

- **⓪ The `kb_search` read-through library + tool-allowlist enforcement (THE CENTERPIECE).**
  - `kb_setup/kb_search.py` + `mise run kb-search -- "<question>"` (and a Python callable for API/PTC use):
    query graphify (staleness-scored, via ①) → on hit return the cited subgraph; on **miss/stale**, do the
    web search (the ONLY component with web egress), fetch (Defuddle/clean-markdown), host-agent-extract →
    `kb-merge` (under the ② lock), then return the freshly-ingested cited result. Every miss compounds the graph.
  - **Enforcement:** research agents/lanes are configured with `kb_search` as their ONLY knowledge tool and
    **no** WebSearch/WebFetch. CC subagents via the Agent `tools:` allowlist; CLI lanes via `run-lane.sh`
    allowlists (invert `grok-research`'s `--tools` to drop web, add the KB tool); document that agent prompts
    must never be handed raw web tools.
  - Control-arm: an agent given only `kb_search` cannot reach the web directly (no web tool present); a
    miss triggers ingest (graph node-count grows) then returns; a second identical query is now a hit (no
    re-fetch). Both directions.
  - PTC is the optional later accelerant (expose `kb_search` as a non-MCP function to a Messages-API worker).
- **① G1 staleness scorer (BUILD FIRST — the safety prerequisite).**
  - New `kb_setup/staleness.py`: score `kb-query` result nodes by `captured_at` age + `confidence`
    (`confidence_score` / EXTRACTED|INFERRED|AMBIGUOUS); graphify STORES these (`llm.py`) but never scores
    them (#2051 = stale nodes returned authoritative). Expose as a query post-filter that demotes/flags.
  - Wire into `kb-query` (a `--fresh`/scored mode, default-on for the loop).
  - Control-arm: a synthetically-aged low-confidence node is demoted below a fresh high-confidence one; a
    fresh node is NOT demoted (both directions).
- **② Single-writer graph lock (BUILD FIRST — the correctness prerequisite).**
  - `kb-merge` / full-build export have the lost-update risk (no flock — only `update`/`watch` self-lock via
    `.rebuild.lock`, #1059). Add an `fcntl.flock` around the merge/export write in `kb_setup.graphify_ops`
    so concurrent passes serialize on `graph.json`.
  - Control-arm: two concurrent `kb-merge` calls both land (no lost update) — reproduce the race, prove the
    lock holds.
- **③ The research-pass driver.**
  - `kb_setup/research_loop.py` + `mise run kb-research -- "<question>"`: ground (staleness-aware query) →
    emit sub-question specs → `run-lane.sh` per lane → collect findings → auto-compound (`kb-remember` +
    locked `kb-merge`) → `kb-reflect`. Returns a structured pass report.
  - Tests with MOCKED lanes (no live codex/antigravity) — assert the pass sequence + that a finding grows the
    graph node-count and changes communities.
- **④ The autonomous outer loop + queue.**
  - A `questions/` queue (files) or a SQLite claim/lease table (`kb_setup/queue.py`) for in-flight tracking +
    double-work prevention + pass-outcome log. Driven by native `/loop` / a Routine / background tasks (no
    daemon). SessionEnd/Stop hooks + the run-lane completion contract keep it honest.
  - Escalation seam: park-and-continue on a pending question; fail-stop on an unfixable gate (reuse locked
    policy #7).
- **⑤ Obsidian surface — the vault is a DERIVED HUMAN view; NO "hands" on the critical path.**
  - The vault is generated by `kb-artifacts obsidian` (graph→vault: one `.md`/node, `[[wikilinks]]`, community
    overviews, Canvas). Agents write to the GRAPH via `kb_search`/`kb-merge`, never to the vault — so
    `kepano/obsidian-skills` ("the hands") is NOT needed. Verified (graphify `export.py` `to_obsidian`, #1506):
    the export tracks graphify-owned files in `.graphify_obsidian_manifest.json` and **never overwrites a file
    it didn't create** → human-authored notes survive re-export, so the vault is a durable curation surface and
    human edits round-trip into the graph via `graphify update`.
  - **Model A (ADOPTED):** graph/library = the interface; vault = the human read/curate view; round-trip via
    `graphify update`. **Rejected Model B** (agent authors notes directly in the vault via "hands"): it is a
    SECOND write path that bypasses `kb_search` + the staleness pipeline — contrary to the core invariant.
  - Work here = just wiring: point `--obsidian-dir` at a committed vault path, regenerate on compound, document
    the human curation loop. `kepano/obsidian-skills` stays an OPTIONAL later enhancement (Bases/Canvas
    authoring, Defuddle clipping) — not a dependency.
- **⑥ Lane supervisor — DECIDED (user): THIN SEAM, do NOT port.** `mise run kb-lane` shells out to the
  vendored `run-lane.sh` (a wrapper, not new logic; `plugins/**` is zero-bash-EXEMPT so this honors the rule).
  New work = only the lanes `run-lane.sh` lacks: the **antigravity lane** (its own `agy --print` + the
  settings.json deny config from R2) and the **Opus terminal fallback** (in-terminal architect, not a spawned
  lane). Reuse run-lane.sh's codex/grok arms as-is. Control-arm the seam (hung lane reaped via the script;
  clean exit detected). *Original port text below retained only for the watchdog/process-group details the
  seam still relies on:*
  - `kb_setup/lane_supervisor.py` (KB repo, the framework home) + `mise run kb-lane -- start|wait|reap ...`:
    a faithful python port of `run-lane.sh` — detached subprocess launch (`os.setsid`/new process group),
    a watchdog that kills the whole group on timeout (beats the harness 10-min cap), bounded `wait` slices
    (≤90s, under the ~2-min auto-background threshold), `reap`, and the completion contract (`STATUS`/`EXIT`
    markers → structured return). Must preserve the CLI-lane specifics (codex `--model gpt-5.6-sol -c
    model_reasoning_effort=high --sandbox workspace-write --output-last-message`; antigravity `--print
    --mode plan`; the grok bypassPermissions quirk if grok is ever used) and the process-group `kill -- -PID`
    discipline. OUR research-loop lanes call THIS, not the plugin bash.
  - Control-arm: a deliberately-hung lane is reaped (group dead, no orphans); a clean-exiting lane is
    detected as EXITED with its final message; a timeout fires the watchdog. Both directions.

- **⑦ Write-path quarantine gate (DECIDED, user — the poisoning fix for R8/staleness-is-not-correctness).**
  A read-through miss returns the result to the agent AND ingests it, but new nodes enter as **PROVISIONAL /
  `verification="unverified"`** and are **excluded from authoritative query results and from becoming Louvain
  hubs** until either (a) a second INDEPENDENT source corroborates the same fact, or (b) a human confirms in
  Obsidian. Promotion flips the node to verified and lets it re-cluster. `kb_setup/quarantine.py` + a
  provenance-origin tag on each node so amplification is detectable (down-weight edges tracing to ONE origin
  fetch). This directly kills "fresh-but-wrong returns authoritative" + the amplification loop, and keeps
  compounding automatic. Control-arm: an uncorroborated provisional node is NOT returned as authoritative and
  does NOT gain hub centrality; a second-source corroboration promotes it. G1 (①) scores recency; ⑦ scores
  *trust/corroboration* — the two are orthogonal and both required.

## Reused as-is (do NOT rebuild)
`kb-query`/`kb-merge`/`kb-remember`/`kb-reflect`/`kb-artifacts`/`kb-add`/`kb-update` (KB `mise.toml`);
the fable-orchestrator/antigravity **doctrine** (architect + six-part spec + `orchestrator-routing` skill +
Opus fallback) — but its `run-lane.sh` is **ported to python (⑥)**, not reused as bash;
the verify-gate oracle (lint/pytest/verify); `agent-report-persistence`/`notepad-enforcement`/provenance.

## Phased build
- **Phase 0 — dogfood + foundations:**
  - **Step 1 (ingest the knowledge to build this — the invariant applied to ourselves).** Audit done this
    session; the graph has good conceptual coverage but these primary sources are gaps (mentions ≠ content):
    - HIGH: the **full PTC doc** + **code-execution tool doc** (only a Fable-5 launch-page mention exists);
      **`lucasrosati/claude-code-memory-setup`** (vault template + chat-import, ⑤); **`basicmachines-co/basic-memory`**
      (read-through + MCP patterns, ⓪).
    - MED: CC subagent **`tools:` allowlist** doc + **antigravity CLI** doc (⓪/⑥); **`topoteretes/cognee`**
      (ingest→graph→retrieval); **our own design docs** (this plan + the 2026-07-22b second-brain report +
      the 2026-07-19 autonomous plan bible) so the framework rationale is graph-queryable.
    - LOW/later: `microsoft/graphrag` + `llama_index` GraphRAGStore (the later community-summary phase);
      `kepano/obsidian-skills`, `albertludi/second-brain-claude` (optional-enhancement only).
    - Ingest via the graphify skill / `kb-add` (URLs) + `kb-build` clone flow (repos) + host-agent extract →
      `kb-merge`. Already-covered (do NOT re-ingest): `fable-orchestrator` incl. `run-lane.sh`/`watchdog.py`,
      CC hooks/best-practices/Agent-SDK/Routines docs, graphify's own code. This is also the first live
      exercise of the read-through pipeline.
  - **Post-review foundations (R1–R7):** ⓪ `kb_search` as a **READ tier (deterministic, lane-safe) + async
    INGEST queue** (R1); the **per-family egress deny-hook matrix** (R2: CC PreToolUse hook, codex
    `tools.web_search=false`, grok `--tools`, antigravity settings.json `deny read_url/execute_url`) with a
    real **egress control-arm** (R6); ① the **corrected** staleness scorer (R3: real fields, not edge
    `confidence`); ② reuse graphify's **`_rebuild_lock`** (R4); ⑥ the **thin `kb-lane` seam** (R5) + the new
    antigravity/Opus lanes; ⑦ the **quarantine gate**; the named **web-search backend** (R7). Each ships a
    control-armed test. These are the safety + enforcement prerequisites; nothing else is correct without them.
- **Phase 1 — one compounding pass (the PROTOTYPE):** ③ `kb-research` one-pass driver (agents use ONLY
  `kb_search`) + ⑤ Obsidian surface. Prove end-to-end on ONE real research question: a miss ingests, the
  graph grows + re-clusters, the next query is a hit, the vault reflects it.
- **Phase 2 — autonomy:** ④ the outer loop + queue/claim table + escalation, on native primitives.
- **Phase 3 — hardening (later):** cross-family review pass, the curated observability EVENT stream
  (`.omc/logs/` + channel mirror, locked policy #9), scale; PTC-accelerated Messages-API research worker if
  measured token savings justify it; DBOS graduation only if multi-machine/contention earns it.

## Verification (end-to-end)
- **Prototype (Phase 0+1) acceptance:** `mise run kb-research -- "<test question>"` runs a full pass →
  `graph.json` node-count grows and `communities` change (topology adjusted) → a follow-up `kb-query` surfaces
  the new nodes WITH staleness scoring → `kb-artifacts obsidian` reflects the grown graph.
- **Read-through + enforcement (⓪):** an agent configured with only `kb_search` has NO web tool (inspect its
  tool list); a miss triggers web-fetch→ingest (node-count grows) then returns cited; the same query next is
  a hit with no re-fetch. Dogfood proof: the PTC doc is queryable from the graph after Phase-0 step 1.
- **Staleness (①):** control-armed both directions (stale demoted, fresh not).
- **Single-writer (②):** reproduce the concurrent-merge race; prove no lost update with the lock, and show it
  CAN lose without it (control arm).
- **Loop dry-run (③/④):** mocked lanes; assert pass sequencing, queue claim/release, escalation park-and-continue.
- **Gates:** KB repo `mise run lint` + `pytest` + `verify` green; no `~/.claude` mutation; graphify stays
  Claude-only for its own backend (existing mandate).

## Risks / consciously held
- **Auto-compound poisoning** — mitigated (not eliminated) by G1 staleness + provenance/confidence + the
  Obsidian human-review surface; NOT by a per-merge gate. If drift shows, fall back to gated batches (the
  prior default is one flag away).
- **Semantic doc-ingestion is fragile** (#1758 ~35% chunk loss, #198 AST↔semantic disconnect) — the loop
  leans on the FREE structural layer + host-agent extraction; treat semantic enrichment as validate-first.
- **graphify pre-1.0 churn** — pinned; own the portable JSON; `tool-currency` watch.
- **Agent liveness** (hit this session) — the run-lane completion contract + watchdog + transcript-growth
  checks are the guard; never wait on a corpse.

---

# APPENDIX — Long-running-autonomy / harness-engineering research (2026-07-23, for LATER)

**Ray's framing: Fable-5 orchestrator ships FIRST; this is "think while we build," reused when we layer
long-running autonomy on top. Don't lose it.** 6-agent research workflow (`wf_ca9694ec-de0`), 5 clusters:
Symphony + CC ports, graph/harness engineering, Augment loop-engineering, marketplace inventory, own SOTA
research. **Full findings + per-agent detail:** `.../tasks/w37wn01j2.output` (73 KB) + workflow journal.
**Complete marketplace lists:** tool-results `bodhg6ygp.txt` (all 2263) + `bifuwn81x.txt` (235 relevant).

## Sequencing (research CONFIRMS our order)
Symphony / Augment / Sol all show the same split: **Fable-5 orchestrator = the INNER per-task executor**
(architect + codex/antigravity/Opus lanes + verify-gate + escalation boundary); the **long-running
autonomous OUTER loop layers on top** and reuses those components verbatim. So Phase-1 (Fable-5) is the
prerequisite, not a detour.

## RAGA validates our core design
The **Read-Search-Verify-Construct** KG-ingest loop (Vadim autonomous-KG; 2026 KG-memory surveys) IS our
read-through invariant: **Search-before-write against graphify = "the library is the only search" (⓪)**;
**Verify-before-Construct = the write-time quarantine gate (⑦)**; CREATE-only + bi-temporal soft-
invalidation = don't-hard-delete provenance. This is external corroboration that ⓪+⑦ are the right shape.

## The 8 patterns to design toward (Phase 2+)
- **P1 Journal + replay-boundary durability** — record every LLM/codex/Opus/tool/KB-write/ship as a
  run_id/step_id boundary; resume from the last boundary. Recommend **DBOS** (in-process Postgres, zero new
  infra) or LangGraph checkpointer; Symphony proves a **DB-free filesystem+KB-tracker recovery** suffices for
  small DAGs. **This is the structural fix for the repo's Mac-side "backgrounded task gets reaped" hazard —
  a durable pause is not a live process.**
- **P2 Persistent per-task workspace + session-resume** — one deterministic dir per research question that
  survives restarts (`claude -p --resume <session_id>`; continuation turns send only NEW guidance).
- **P3 Two-layer typed state machine + REVIEW gate** — claim states (prevent duplicate dispatch) + run-attempt
  lifecycle; jobs return to a REVIEW state the architect gates. **"user-input-required turn = HARD FAILURE"**
  (an autonomous lane escalates to a gate state, never silently blocks).
- **P4 Event-driven scheduling (wait, don't poll)** — per-tick reconcile / stall-detect (kill silent lane ~5min)
  / exponential backoff (cap 300s); durable awakeables for human-gate + CI-waits. Polling burns tokens.
- **P5 KG as compounding memory via RAGA** (see above).
- **P6 Cost routing FIRST-CLASS** — per-stage model+lane, confidence/risk/load-aware. **Symphony explicitly
  PUNTS cost routing → we must OWN it** (it's the Fable-5 architect-plans/executor-implements/Opus-fallback
  split as per-stage config). Self-reported confidence = routing signal only, never calibrated probability.
- **P7 Verification = separate deterministic-under-agent control-armed gate** — cheap `lint`/`verify` under
  agent-review; every recurring failure becomes a permanent hk/suites.toml constraint (repo already does this).
- **P8 Four-tier human escalation + async-durable approval + progressive-trust knob** — read-only/reversible
  autonomous; external/irreversible (ship/land/merge/KB-publish) need approval persisting the exact
  artifact+version hash (replay can't approve modified content); lower approval frequency as lanes prove out.
- **Cross-cutting:** durability/verification/provenance are **write-time & incremental, never end-of-run**
  (the repo's agent-report-persistence rule made structural/journal-backed).

## BORROW / AVOID (highlights)
- **BORROW:** Symphony conductor + DB-free tracker recovery (KB = our tracker); Sol durable-goal/disposable-
  workflow split + `agents_inspect` narrow evidence materialization (architect never ingests raw lane
  transcripts) + blackboard **volunteer** pattern (lanes claim by capability); Augment 5-stage loop
  (Trigger→Execute→Verify→Outcome→Improve) + trace-driven Improve + Context-Engine fresh-index; agentsatlas
  fresh-subagent-per-plan (stop long-horizon decay); wake/spend budgets.
- **AVOID:** Symphony's **no-fan-out** worker model (it parallelizes across ISSUES, not agents on one task —
  research wants intra-task fan-out + shared KB); SaaS-tracker-as-canonical-state (our blackboard is the KB);
  throwing away ALL scheduler state on restart (checkpoint partial progress); transcript-passing between
  lanes (context pollution — the recurring failure); polling/synchronous-approval/end-of-run capture;
  trusting self-reported confidence as calibrated; over-adopting marketplace plugins as deps (borrow shapes,
  vendor selectively); treating the Augment blog as an impl spec (conceptual only — we design our own
  durability layer).

## Marketplace inventory (`anthropics/claude-plugins-community`)
**2263 plugins total; 235 genuinely harness/orchestration/graph/memory/multi-agent-relevant** (full
categorized list at tool-result `bifuwn81x.txt`; the workflow's cluster-D curated the ~44 highest-signal
`agent*/ai*` ones with categories — see `w37wn01j2.output`). Standouts to study as design references (NOT
deps): `agent-knowledge` (typed KG memory, 11 edge types, BFS, confidence/decay), `agent-recall` (SQLite KG
+ MCP), `agent-memory` (cross-agent memory bus, token-budgeted injection), `agent-tasks` (stage-gated task
graph + approvals), `agentsatlas` (context-reset waves), `agent-trace-triage` (loop-detection self-healing
observability), `ai-team-os` ("company loop engine"), `agent-handoff` (durable plan→execute→verify),
`agentic-swe` (stateful pipeline + human gates + evidence artifacts). `agnix` is already used here.

## Sources reached / FAILED (close if load-bearing)
- **Failed:** `openai.com/index/harness-engineering/` → **HTTP 403** (recovered via WebSearch + humanlayer
  secondary; primary unread); marketplace `d–z` not byte-complete via web tool (closed here via raw curl →
  235 relevant); arXiv 2510.01285 (blackboard) abstract-only. Re-fetch these if they become load-bearing.

## `/goal` — the native work-until-condition primitive (already in KB graph; doc reviewed 2026-07-23)
`code.claude.com/docs/en/goal` (+ the loop-engineering blog) are ALREADY ingested — no re-ingest. Findings
that shape the outer loop (Phase 2, native-primitives path):
- **`/goal <condition>` keeps Claude working across turns until a FRESH small-model evaluator (Haiku)
  confirms the condition after every turn** — completion decided by a different model than the one working
  (P7 "separate verifier" + P3 "REVIEW gate", NATIVE). It is **a wrapper around a session-scoped prompt-based
  Stop hook.** Condition ≤4000 chars; bound it with an "…or stop after N turns" clause (P4 bounds).
- **Headless = a one-invocation autonomous loop:** `claude -p "/goal <condition>"` runs the whole loop to
  completion; add `--output-format stream-json --verbose` for progress. **The outer-loop driver can BE this**,
  not a hand-rolled loop. Pair with **auto mode** (`/goal` removes per-TURN prompts; auto mode removes
  per-TOOL prompts — complementary) for unattended turns.
- **Durability:** an active goal **survives `--resume`/`--continue`** (condition carries; turn/timer/token
  baselines reset) — a native session-level resume primitive (P2).
- **CONSTRAINT (load-bearing):** the evaluator judges ONLY what Claude has surfaced in the transcript — it
  does NOT run tools or read files. So (a) goal conditions must be **transcript-provable** ("`npm test` exits
  0" works because Claude runs it and the result lands in the transcript); (b) **deterministic gates
  (lint/pytest/verify) belong in a CUSTOM Stop hook**, not the `/goal` evaluator — use `/goal` for
  model-evaluated conditions, a custom Stop hook (script) for deterministic ones. Requires workspace trust;
  unavailable under `disableAllHooks`/`allowManagedHooksOnly`.
- **Design use:** the research loop's outer driver = `claude -p "/goal <research-goal + stop-after-N>"` + auto
  mode, with a custom Stop hook running the deterministic KB/verify checks the /goal evaluator can't. This
  replaces a hand-rolled `while` loop with a native, evaluator-gated, resumable primitive.

## Phase 2+ additions (priority order — Fable-5 first, then:)
(a) durable-execution journal + idempotent tool wrappers on every graphify write + PR/commit/ship;
(b) RAGA read-through KB loop (validates ⓪+⑦); (c) designed cost-router (own Symphony's gap);
(d) Sol-style event-driven lane supervisor with blackboard volunteering + narrow evidence materialization;
(e) four-tier async-durable escalation + progressive-trust; (f) trace-driven Improve + periodic entropy-GC
agent over the KB + rules. **Durable-execution engine decision (DBOS vs DB-free tracker) deferred to the
Phase-2 design session.**

## STAGED graphify ingestion (run at BUILD time — plan mode blocks writes now)
Per the core invariant (all new research → graphify first), ingest these sources when we execute. In the KB
repo: URL docs via `mise run kb-add -- <url>`; GitHub repos via the `kb-build` clone flow (add to
`sources/` + manifest, then host-agent extract → `mise run kb-merge`). Sources: openai/symphony,
kumanday/OpenSymphony, zaalipro/cymphony, Sugar-Coffee/stokowski, ReyJ94/Sol-Orchestrator,
ai-boost/awesome-harness-engineering, shareAI-lab/learn-claude-code, MarcosNahuel/antigravity-plugin-cc,
simplybychris/antigravity-plugin-cc, the antigravity.google CLI docs, addyosmani + augmentcode + claude-world
+ youmind + linkedin + towards_AI articles, this plan, this session's research outputs, and (for a queryable
inventory) the `claude-plugins-community` marketplace.json. Then `mise run kb-reflect`.
