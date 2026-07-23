# Program plan — Autonomous execution on a graphify-centric knowledge substrate (2026-07-19)

Produced by a `/grilling` session (13 decisions). This is the **program
roadmap** (per the repo's plan-vs-spec split: program = plan; each buildable
component = its own `/to-spec` PRD → tickets). NOT a single PRD.

## Vision
Run fully autonomous execution of well-specified tickets, with all agents
standing on graphify as a shared, self-improving knowledge substrate, and the
human pulled in only for genuine decisions they can't resolve after research.

## Sequencing (DECISION: foundation-first, research in parallel)
1. **Foundation** — graphify Phase 0 (T3–T7, #314–#318) is the substrate. In flight.
2. **Cross-cutting research (NOW, parallel — depends on nothing):** Track A + B below.
3. **On the finished substrate:** knowledge layer → specialists → orchestrator.
4. **`/to-spec` per buildable component AFTER research** (knowledge layer → orchestrator → specialists); each PRD grounded in findings, → `ready-for-agent` tickets the orchestrator eventually runs.

## Components
- **① Foundation:** graphify Phase 0 (T3 guarded refresh+doc-guard, T4 gated real tests, T5 wiring contract, T6 docs, T7 dogfood build). See `project_graphify_phase0` memory + `session-2026-07-19-b.md`.
- **② Knowledge layer:** all agents query graphify FIRST; precedence over web for **stable** knowledge; volatile facts (tool versions) still hit the live source via `tool-currency`. Miss → answer now + **queue** the finding with provenance (source, agent, timestamp, confidence); a **gated batched update** drains the queue on Ray's cadence (respects #310 US9 — no auto-hook build). Provenance + confidence labels prevent poisoning (web/informal = lower-confidence, per `research-doc-sources`).
- **③ Specialists:** per-tool god-node agents — docker, mise, hk, uv, ruff, python, github-actions, gh-cli, claude-code, graphite, … — each anchored on graphify god nodes + the tool's live docs.
- **④ Orchestrator:** batch-per-DAG autonomous loop (prove on graphify #312–#318), graduating to a standing `ready-for-agent` puller. Mac-local (ship/land are Mac-pinned). Escalation channels + observability below.

## Locked execution policy (the 13 decisions)
1. **Autonomy scope:** execute well-specified tickets end-to-end; escalate on genuine decisions.
2. **Merge boundary:** auto-merge on green, review after (trusts gate coverage).
3. **Forks:** pick documented default + log; escalate only if costly-to-reverse, spends money, or spec/research can't settle it.
4. **Surprises:** mandatory cross-check; self-correct the agent's OWN assumptions; escalate SPEC conflicts or probe disagreement.
5. **Cadence:** batch-per-DAG now → standing puller once trusted.
6. **Task scope:** only well-specified `ready-for-agent` tickets; spec-authoring (`/to-spec`, `/to-tickets`, `/grilling`) stays human.
7. **Failure:** fail-stop the batch on an unfixable red gate (respects zero-skip / verify-before-advancing); park-and-continue (other unblocked tickets) on a pending question.
8. **Escalation channels:** fan out to GitHub issues + GitHub Discussions + Slack + Discord (new server) + channels.
9. **Observability:** curated timestamped, per-agent EVENT stream (findings/decisions/escalations/gates) → `.omc/logs/` + channel mirror; raw CC transcript as drill-down backing store.
10. **Graphify-first:** all agents query graphify before web; precedence for stable knowledge.
11. **Write-back:** queued + gated + provenanced (not inline/auto).
12. **Prior-art gate:** research existing graphify usage + tools BEFORE building the knowledge layer (`use-tool-builtins`).
13. **Plan vs spec:** program = this plan; each component = `/to-spec` PRD after research.

## Residual risks (consciously held)
- Auto-merge-on-green: a chain of subtly-wrong-but-green merges is caught only post-hoc (curated event stream + review + git revert), not by a per-merge gate.
- Mac-local only — Cloud Routines can't run the sync-full/ship gate.
- Channels + observability are a real build surface, separate from the core loop.
- Knowledge poisoning mitigated by provenance/confidence, not eliminated.

## Research scope (running now)
- **Track A — CC autonomy primitives:** `/fork` + `/subtask` exact semantics; Claude Code changelog/release-notes for autonomy-relevant features; settings/hooks/permission-modes (`canUseTool`, `defer` hook decision, `dontAsk`/`auto`) for an unattended-but-escalating loop.
- **Track B — graphify usage + prior art:** graphify best practices + real usage (god nodes / query / update / provenance done right?); existing-solutions scan — does graphify natively or an adjacent tool (GraphRAG, MCP memory servers, agent-memory-over-KG) already provide read-through/write-back, provenance, staleness, per-domain sub-graphs — adopt/extend vs build.

## Immediate next actions
1. (done) This plan persisted.
2. Run Track A + B research → findings + substrate/orchestrator/specialist proposal.
3. graphify Phase 0 (T3 #314) continues as its own track (`session-2026-07-19-b.md`).
4. After research: `/to-spec` the knowledge layer first.

## Research verdict (2026-07-19, both tracks verified against load-bearing claims)
- **Track A (CC autonomy):** unattended-but-escalating loop is MOSTLY NATIVE — auto mode + `autoMode.environment`, the `defer` hook decision (park→exit→resume), **channels with two-way permission relay** (approve in Slack/Discord — your escalation requirement, native), `/goal` (work-until-condition), Routines, headless `-p`, session fork/resume. `/fork` real (copy→background session), **`/subtask` real** (side task → subagent reporting back — Track A wrongly said it doesn't exist; cross-check via commands.md corrected it), `/subfork` not real. BUILD = orchestrator glue only (ticket→session map, DAG frontier, cost tracking).
- **Track B (graphify + prior art):** graphify ALREADY ships provenance/confidence/citation primitives (0.9.20 `llm.py:437`: node `source_url`/`captured_at`/`author`/`contributor`; edge `confidence` EXTRACTED|INFERRED|AMBIGUOUS + `confidence_score`; query `[src=]` cited `serve.py:827`). ~70% built-in. Corrections: no `graphify god-nodes` CLI (MCP `god_nodes` tool + GRAPH_REPORT.md only); no first-class per-domain god-node views; `captured_at` stored but never SCORED (no staleness invalidation).
- **use-tool-builtins VERDICT: BUILD ON graphify (hybrid); do NOT adopt a graph-DB memory service.** Graphiti/Zep alone beats it (bi-temporal invalidation) but needs Neo4j+resident server (violates host-only). mem0/cognee heavier (Qdrant/Postgres). Letta not-a-fit. GraphRAG offline. The MCP memory server in our `.mcp.json` is superseded by graphify.
- **Four gaps to fill (the only new engine work):** G1 age-based staleness SCORING (borrow Graphiti's *pattern*, not its infra); G2 optional lightweight single-fact append; G3 per-tool expert-view selection layer; G4 the read-through routing seam. Confidence HIGH on facts, MEDIUM on adopt/no-adopt.
- Reports: `.omc/research/research-20260719-autonomous-program/agents/track-{a,b}-*.md`.

## Follow-up research (2026-07-19, Ray's challenge — both verified directly)
- **Graphiti embedded (G1):** Ray was right that "Neo4j-only" was FALSE — embedded backends exist (Kuzu = **deprecated**; FalkorDB-Lite = mature pkg w/ cp314 wheels but Graphiti driver is a **draft unmerged PR #1250**). No GA non-deprecated embedded Graphiti today. **G1 verdict SURVIVES for a sounder reason:** adopting Graphiti for staleness = a 2nd LLM-fed graph store + pay-twice re-ingest, disproportionate to a `captured_at` post-filter. **Build age-scoring on graphify.** (cognee correction: now fully embedded — Track B's "too heavy" outdated; still a 2nd store, doesn't flip G1.)
- **Graphify maturity (bus-factor):** NOT niche/abandoned — **91,451★** (gh-api verified), 8,918 forks, 1.4M PyPI dl/mo, 188 releases/3.5mo (~1 every 1-2 days), YC S26, MIT, active daily. **Effectively ONE maintainer** (safishamsi 853 vs 27 vs 17). Pre-1.0 (v1.0.0 tag is a throwaway behind 0.9.x). Real 3rd-party agent-memory use: `lucasrosati/claude-code-memory-setup` (867★), DEV writeups, 105 repos commit `graph.json`. **Risk = MEDIUM, well-mitigated** (risk is pre-1.0 churn + 1-maintainer, NOT abandonment; mitigations = pin 0.9.20, host-only/removable, portable NetworkX JSON we own, thin skill coupling). → **BUILD ON graphify CONFIRMED; the Graphiti-as-primary reopening does NOT trigger.**
- **Operational findings folded into the design:**
  - VALIDATES US9/no-auto-hook: a real user hit CPU/swap exhaustion (load 12+) wiring `graphify update` into PostToolUse/Stop hooks. Our gated/manual-build + forbid-`hook install`/`--watch` decisions are exactly right.
  - graphify ships its OWN agent-memory overlay (`save-result`/`reflect` → `LESSONS.md`, nodes tagged preferred/tentative/contested) — **evaluate for write-back (may shrink G2)**.
  - Provenance is native `add --author/--contributor` → G2 maps to it.
  - mcp2cli-first VALIDATED (MCP server injects ~6000 tokens of schemas).
  - Pre-1.0 churn → pin + `tool-currency` watch for breaking changes; `source_file` flipped relative→basename at 0.9.16 (#1941) = a read-through path-stability gotcha for **G4**.
  - Divergence noted: graphify recommends commit `graphify-out/` + `hook install`; we deliberately diverge (project-only, gated, wiki-only) — keep.
- Reports: `followup-graphiti-embedded.md`, `followup-graphify-adoption.md`.

## Infra research (2026-07-19 — Postgres vs SQLite queue; iceoryx)
- **iceoryx: OUT (category mismatch).** Hard-real-time zero-copy shared-mem IPC (`<1µs`, automotive/ROS2). Our workload is ~10⁹–10¹⁰× slower / ~10⁶–10⁸× lower-freq; same-machine-only; EPHEMERAL (no restart durability — the one thing we need). Zero-copy buys nothing for KB JSON every few minutes.
- **Postgres+pgmq: OVER-ENGINEERED for single-Mac.** pgmq mature (visibility timeout, exactly-once-in-VT, archive DLQ, no bgw — pure SQL); but pg_cron REQUIRES a resident server (bgw via shared_preload_libraries); LISTEN/NOTIFY non-durable. Embedded path (PGlite+`@electric-sql/pglite-pgmq`) exists but is SQLite's weight class AND excludes pg_cron — dominated by plain SQLite.
- **Recommendation: SQLite (WAL) + atomic-claim/lease table** (or a file/dir queue for inspectability) for queue+state, + **native harness primitives** (Routines/`schedule`, `/loop`, background tasks, SessionEnd/Stop hooks) for scheduling/event-loop. NO daemon — truest "write only your logic" + consistent with host-only.
- **FLIP POINT (load-bearing):** Postgres becomes justified ONLY when the control plane must be **shared across >1 machine** OR a concurrent worker pool contends on one queue (dozens+ claims/sec). A *coordination* threshold, not data-size. Below it, SQLite fits and Postgres is weight without payoff.
- Reports: `followup-postgres-infra.md`, `followup-iceoryx-fit.md`.

## Infra research CORRECTED (2026-07-19, Ray's challenge — both prior verdicts revised)
- **iceoryx (corrected):** prior "same-machine only" was FALSE — iceoryx2 Zenoh network tunnel (v0.7.0, 2025-09-13) carries pub-sub+event cross-machine; blackboard done + Python-first-class (v0.8/v0.9 GIL-released); v1.0 end-2026. BUT survives-for-our-use as NO-for-control-plane on the RIGHT basis: **non-durable** (volatile shm; no reboot persistence) + network tier carries only pub-sub/event, **not** request-response/blackboard cross-host (the coordination we'd need). Real use = robotics (Copper, rmw_iceoryx2) which pick **Zenoh** for distributed; **no AI-agent-orchestration adopters**. NEW: iceoryx2 is a real candidate for a FUTURE co-located zero-copy **data tier** (large artifacts between polyglot processes); **Zenoh** surfaced as the cross-machine bus if we go multi-machine.
- **Postgres (corrected — FLIPS to attractive):** the "over-engineered" call rested on host-only, which **does NOT apply in a container** (Postgres in the devcontainer = every cost is a disposable container concern). Prior report also only saw Postgres-as-queue. **Postgres-as-agent-backbone is the mainstream 2026 pattern:** LangGraph `PostgresSaver` (37.6k★, prod standard), pgvector (22.3k★), Temporal (21.7k★ on PG), pgmq (5.0k★=Supabase Queues), Apache AGE (4.7k★ openCypher-in-PG). **Standout: DBOS Transact (1.5k★)** — pip lib, durable `@workflow`/queues/scheduling, **backend-agnostic (Postgres OR SQLite since 2026-06)**, first-party Pydantic-AI/OpenAI-Agents-SDK/LlamaIndex integrations = the truest "just add our logic." Microsoft `pg_durable` (2.7k★, in-DB durable exec, OSS 2026-06).
- **REVISED axis — not "SQLite vs Postgres" but CONSOLIDATION vs MINIMALISM, bridged by DBOS:** DBOS runs on EITHER backend with the SAME code → **start DBOS-on-SQLite (host, zero-server) → graduate to DBOS-on-containerized-Postgres** (pgvector memory + LISTEN/NOTIFY + pgmq + optional Apache AGE) when many-specialist-agents/observability/vector-memory earns consolidation. No rewrite. graphify stays the KG substrate (host-only); Postgres would be control-plane state (+ optional vector-memory tier), NOT a graphify replacement. AGE-co-locating-the-graph = a maintainer decision, flagged (graphify is the KG).
- Reports: `followup2-iceoryx-corrected.md`, `followup2-postgres-realprojects.md`.
- DECISION PENDING: DBOS-on-SQLite (start minimal, graduate later) vs DBOS-on-containerized-Postgres now (consolidate); iceoryx = deferred data-tier candidate only.

## Cost / multi-model architecture research (2026-07-19)
- **$0 ingestion is real:** graphify `--backend ollama` (Ollama 0.19+ is MLX-powered on Apple Silicon; qwen3:14b; JSON-schema constrained) = zero Claude tokens. Fallbacks: free NIM (`integrate.api.nvidia.com/v1`, OpenAI-compat, free NVIDIA key, ~40 RPM) via `--backend openai`+`OPENAI_BASE_URL`; Gemini free tier `--backend gemini`. So the "Claude-baseline cost trial" may be moot — ingest FREE locally, measure that.
- **Orchestrator shape (fable-orchestrator, read from source):** strong model = ARCHITECT ONLY (never types), enforced by a **PreToolUse deny-hook** no-touch list; cheap workers get a **five-part spec contract** (zero shared context), return **compressed report shapes**; **external ledger** for state across compaction; **machine completion contract** (`STATUS:` + wall/stall watchdog) so autonomy can't hang/fake success. TECHNIQUES to build, not a product.
- **Cheap-model quality = the VERIFICATION LOOP, not the model:** self-repair vs real execution feedback (+4.9–17.1 HumanEval), cap ~3 iterations. **We already own the oracle** — `mise run lint`/`pytest`/`verify run`. Cheap worker writes → our gate judges → self-repair ≤3×.
- **Highest-leverage synergy: RAG the graphify graph INTO workers** — the whole graphify investment pays off as cheap source-cited context instead of workers re-reading files/burning tokens.
- **Routing seam to BUILD: LiteLLM** fronts BOTH graphify's OpenAI backend AND Claude Code's Anthropic endpoint (`ANTHROPIC_BASE_URL`) — one config routes graphify + Claude Code + subagents. Rules cascade first, learned router later. + embedding-dedup + confidence-gated escalation in front of graphify. Adopt GPTCache/LLMLingua/RouteLLM patterns.
- **Providers:** local Ollama+MLX ($0 default) → free NIM (stronger fallback) → Gemini free (third) → Claude for orchestration/synthesis ONLY. Codex `codex exec` scriptable but subscription-priced; Antigravity absorbed Gemini CLI (2026-06-18).
- CAVEATS (control-armed): benchmark deltas are secondary/condition-bound (direction only); NIM ~40 RPM + Gemini RPD cut (verify live); some NIM model IDs unconfirmed; graphify default gemini model differs by version (pass `--model`).
- Reports: `followup-multiprovider.md`, `followup-orchestrator-trends.md`, `followup-fable-opus-orchestrator.md`.
- **Orchestrator dispatch (Fable/Opus):** Agent-SDK `model` override is **Claude-only** (fable/opus/sonnet/haiku — no per-subagent PROVIDER field), so a Claude orchestrator fans out only Claude subagents. **Cross-vendor path = Bash shell-out** (`codex exec`, `gemini`, `graphify --backend`, LiteLLM CLI) wrapped in a completion-contract launcher — how fable-orchestrator reaches Grok. `ANTHROPIC_BASE_URL` is session-wide (can't express strong-orch+cheap-worker). Cleanest: native Claude orchestrator + Seam A (Claude workers) + Seam B (non-Claude/local via shell-out).
- **"Opus 4.8 w/ Fable 5 prompts" — HONEST:** the leaked ~120k-char "Fable 5 prompt" is the Claude PRODUCT HARNESS (tool schemas/artifacts), NOT an orchestrator mode, Anthropic-unconfirmed. Real guidance = Anthropic's public **"Prompting Claude Fable 5"** doc. A prompt transfers workflow/format, NOT Fable's *trained* long-horizon autonomy/delegation. TRAPS: show-your-reasoning triggers Fable's `reasoning_extraction` refusal; over-prescriptive skills DEGRADE Fable — transfer is asymmetric.
- **Worker guardrails = THE LEVER (confirms Ray's instinct):** guardrail intensity ∝ INVERSE of worker capability (thin prose for Fable, thick prose + machine gates for cheap/local). The objective **verify-gate is the one load-bearing guardrail — and we already own it** (lint/pytest/verify). Anthropic's doc primary-sources the stop-contract, progress-grounding ("nearly eliminated fabricated status reports"), fresh-context verifier subagents, scope containment.
- **Orchestrator REC:** Fable 5 @ effort high, token-thin, thin prompt from PUBLIC Fable snippets (not the leak); Opus 4.8 as refusal-fallback + cheaper-orch option; doctrine as on-demand skill; five-part spec = the only worker interface; workers guarded by deny-hook + constrained output + completion-contract launcher + verify-gate. Re-measure eval deltas locally (secondary/unreproduced).

## graphify GitHub mining (2026-07-19 — tempers optimism, VALIDATES gaps)
- **SOLID + free:** `graphify extract . --code-only` = local AST, **0 tokens, maintainer-endorsed** (#1734, Disc #1931). This is what we already built (3157 nodes). Lean on it.
- **SEMANTIC DOC ingestion is RISKY — validate before depending:** chunking is file-count-based not output-size-aware → **~35% of subagent chunks silently crash past the 64k output cap** (#1758); **53% of docs lost even with gpt-5** (#1890); **AST↔semantic layers largely DISCONNECTED** (#198, fusion needs exact node-id collisions); `--update` runbook omits `kind="ast"` → silently re-extracts whole corpus semantically (#2033); cost.json never appends (#1769 — measuring cost is itself broken); #730 truncation → 3× cost.
- **Free non-Claude backends less ready than the multiprovider report implied:** OpenAI-compat **base-URL is an OPEN issue** (#959/#981/#723) — NIM/vLLM/local-via-OPENAI_BASE_URL may NOT work yet; Ollama wired but buggy (#820/#798/#1686); no NIM/MLX mentions. Backend auto-detect order: Gemini→Kimi→Claude→OpenAI→DeepSeek→Bedrock→Ollama (#1086).
- **OUR GAPS VALIDATED by real issues:** **G1 staleness must be QUERY-TIME** (#2051: 1,444 stale nodes for deleted files — incl. deleted SECURITY files — returned authoritative); **G4 read-through needs an always-on rule** telling agents to query graphify first (#749, Disc #921) — exactly what graphify's *forbidden* `claude install` writes, so we build our OWN project `.claude/` rule. Confidence is **bimodal/miscalibrated** (#540) → confidence-gating must account for it.
- **CORRECTION to Track B:** provenance `add --author/--contributor` **did NOT surface in any issue — UNVERIFIED in practice** (schema has the fields per llm.py:437, but the workflow is unproven; durable human corrections unsolved, PR #1871). Re-verify before relying.
- **Strategic:** graphify is **commercializing** (graphify.com + Enterprise early-access, YC S26), pre-1.0, single-maintainer, ~daily releases, schema churn across patches (#1941/#1789), non-determinism (#1090). Reinforces: pin, host-only/removable, own the portable JSON, lean on the deterministic code layer.
- Net: **AST/structural graph = the solid bet; semantic doc-enrichment = validate-on-our-corpus-first, don't bet the KB on it yet.**
- Reports: `followup-graphify-github-mining.md`, `followup-fable-opus-orchestrator.md`.

## codex-plugin-cc + Fable-prompt + Discord (2026-07-19, final research round)
- **codex-plugin-cc:** NOT plain `codex exec` — slash commands → Node dispatcher → persistent **warm app-server broker** (avoids cold-start) + `state.json` job ledger + optional **Stop-hook review gate** (README warns it can loop/drain usage). Bidirectional: Codex-as-executor (Paluy claims ~60% token savings, author-reported/unbenchmarked) AND Codex-as-peer-reviewer. Heavier, official, **Codex-only**, missing the STATUS/watchdog rails.
- **Fable-prompt-on-Opus — SETTLED:** the leaked ~1,585-line prompt = product harness; "Fable 5 Lite" author admits intelligence gain is **"actually zero"** → REJECT the leaked prompt. ADOPT the **procedure** patterns instead (dev.to/toffy: pre-read routine, **`VERIFIED/REASONED/ASSUMED` evidence labels**, hypothesis-before-fix, ordered verification — "the gap is not intelligence"). imCorfitz gist = direct match: Fable-5 orch + Claude subagents (Seam A) + Codex (Seam B).
- **Trends:** a `*-plugin-cc` bridge family standardized this quarter (Codex→Gemini forks); peer-review-as-a-plugin (`jcputney/agent-peer-review`); Claude Code Router (`ccr`) = session-wide proxy seam.
- **Orchestration substrate DECISION:** **launcher-wrapped `codex exec`/CLI shell-out** (cross-vendor, carries hang/fake-success rails, fits our governance) — NOT the codex-plugin-cc plugin (Codex-only, watchdog-less), NOT LiteLLM/ccr (session-wide, can't split roles). Cherry-pick 3 plugin ideas: warm broker (if cold-start dominates), background-job ledger, a BOUNDED Stop-hook review gate. Cheap Claude workers via Seam A (`.claude/agents` `model:`). Worker reports use the `VERIFIED/REASONED/ASSUMED` label → maps 1:1 onto our verify-gate.
- **Discord: SKIP mining.** Official plugin = messaging not mining (bot API has no search, ≤100 msg lookback). Only `lycfyi/community-agent-plugin` mines (sync-to-local-then-search) but needs a graphify ADMIN to add a bot (Ray has only a member invite) or a ToS-risky user-token self-bot. GitHub mining already covered the substance → skip.
- Reports: `followup-discord-plugins.md`, `followup-codex-plugin-fable-prompt.md`.

## Prior art in-repo (do NOT reinvent — feed Track B)
`agent-report-persistence` + `.omc/research/**` (verbatim reports); `notepad-enforcement`; CC transcripts (timestamped, per-session JSONL); `command_audit`/`hook_guard` (self-learning loop); `tool-currency` (staleness); `research-doc-sources` (the doc chain graphify-first would prepend to); `md_budget`/agnix (doc linting). The landscape plan `proud-munching-mist.md` WS1/WS5/WS6 overlap heavily.
