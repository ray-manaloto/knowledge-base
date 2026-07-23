# Source Registry — ingestion & extraction backlog

Durable checklist of every source queued for the KB. Nothing here is lost; the
system works the list down "as it gets smarter." Update `status` in place as a
source advances. Origin: the Fable-5-orchestrator research program (2026-07-22).

## Legend

**Tier** (extraction depth — decided 2026-07-22):
- **T1** — full semantic (host-agent prose) + code AST. Authoritative / directly on-topic.
- **T2** — light: code AST only, or README-only prose.
- **T3** — deferred: registered but not yet ingested (e.g. live timelines that don't
  extract statically — reach via the trend tool instead).

**Status:** `pending` → `manifest` (repo pinned) → `code` (AST ingested) →
`prose` (host-agent extracted) → `done`; or `deferred` / `tool` (installed & used,
not just ingested).

**Kind:** `repo` (github, manifest+clone+AST) · `docs` (sitemap/page prose) ·
`article` (blog/substack) · `forum` (reddit) · `media` (video → transcript) ·
`timeline` (X/Twitter).

## Backlog

| # | Source | Kind | Tier | Status | Why it's here |
|---|---|---|---|---|---|
| 1 | [platform.claude.com/sitemap.xml](https://platform.claude.com/sitemap.xml) → [multiagent-orchestration](https://platform.claude.com/docs/en/managed-agents/multiagent-orchestration) | docs | T1 | prose | Authoritative: managed-agents + multi-agent orchestration. Core pages extracted (claude-docs-docs.json). |
| 2 | [code.claude.com/sitemap.xml](https://code.claude.com/sitemap.xml) | docs | T1 | prose | Authoritative: Claude Code subagents, model config, hooks, skills. 14 core pages extracted; ~151-page long tail deferred. |
| 3 | [prompting-claude-fable-5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5) | docs | T1 | prose | Fable-5 prompt engineering (orchestrator prompt design). Extracted. |
| 4 | [bytedance/deer-flow](https://github.com/bytedance/deer-flow) | repo | T1 | prose | Multi-agent deep-research framework. Code + prose (README/AGENTS) extracted 2026-07-22. |
| 5 | [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) | repo | T1 | prose | Self-learning / skill optimization. Code + prose extracted 2026-07-22. |
| 6 | [DannyMac180/fable-advisor](https://github.com/DannyMac180/fable-advisor) | repo | T1 | prose | THE advisor-pattern reference. Prose extracted 2026-07-22 (was never code-ingested — prose-only). |
| 7 | [Cjbuilds/Codex-Orchestration](https://github.com/Cjbuilds/Codex-Orchestration) | repo | T1 | prose | Codex handoff / orchestration. Code + prose extracted 2026-07-22. |
| 8 | [Rylaa/fable5-orchestrator](https://github.com/Rylaa/fable5-orchestrator) | repo | T1 | prose | Fable-5 orchestrator + dynamic-workflow instructions. Code + prose extracted 2026-07-22. |
| 9 | [mar3co/fable-orchestrator](https://github.com/mar3co/fable-orchestrator) | repo | T1 | prose | Fable orchestrator. Code + prose extracted 2026-07-22. |
| 10 | [advisor-executor-pattern (mindstudio)](https://www.mindstudio.ai/blog/advisor-executor-pattern-claude-code-fable-5) | article | T1 | prose | THE advisor/executor decision. Extracted 2026-07-22. |
| 11 | [asgeirtj/system_prompts_leaks → claude-fable-5.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/Anthropic/claude-fable-5.md) | repo | T1 | prose | Fable-5 system-prompt leak (behavioral priors). Distilled 2026-07-22. |
| 12 | [linas.substack — Fable-5-lite/Opus-4.8](https://linas.substack.com/p/unlock-claude-fable-5-lite-opus-48) | article | T1 | prose | Fable-5→Opus-4.8 fallback pattern. Extracted 2026-07-22. |
| 13 | [r/claude — fable_5_and_opus_48_prompt](https://www.reddit.com/r/claude/comments/1unhubx/fable_5_and_opus_48_prompt/) | forum | T1 | deferred | BLOCKED: Reddit bot-verification wall ("Please wait for verification"); graphify fetch returns a stub. Fallback covered by #10/#12/#14 (control-arm). |
| 14 | [youtu.be/XTBWVVcF3Pk](https://youtu.be/XTBWVVcF3Pk) | media | T1 | prose | Fallback-pattern walkthrough. Transcribed (whisper) + extracted 2026-07-22. |
| 15 | [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) | repo | T1 | prose | **tool**: trend gap-fill. Code + prose (README/CONCEPTS) extracted 2026-07-22. |
| 16 | [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | repo | T2 | code | Catalog — code-ingested; prose deferred (catalog, low insight density). |
| 17 | [anthropics/claude-plugins-community](https://github.com/anthropics/claude-plugins-community) | repo | T2 | code | Plugin catalog — code-ingested; prose deferred. |
| 18 | [affaan-m/ECC](https://github.com/affaan-m/ECC) | repo | T2 | code | Code-ingested; prose deferred. |
| 19 | [mindstudio blog — tag/claude](https://www.mindstudio.ai/blog/tag/claude) | article | T2 | pending | Broader Claude blog set (light). Deferred. |
| 20 | [x.com/ClaudeDevs](https://x.com/ClaudeDevs) | timeline | T3 | deferred | Live timeline → reach via last30days-skill, not static ingest. |
| 21 | [x.com/ClaudeAI](https://x.com/ClaudeAI) | timeline | T3 | deferred | Live timeline → reach via last30days-skill, not static ingest. |
| 22 | [youtu.be/GnA9xjYWHBg](https://youtu.be/GnA9xjYWHBg) | media | T1 | prose | Ray-added video (graphify KB build walkthrough). Transcribed + extracted 2026-07-22. |
| 23 | [youtu.be/22iy2mDFiF8](https://youtu.be/22iy2mDFiF8) | media | T1 | prose | Ray-added video (AI second-brain / read-once graph). Transcribed + extracted 2026-07-22. |
| 24 | [youtu.be/rtutpoT4SYg](https://youtu.be/rtutpoT4SYg) | media | T1 | prose | Ray-added video — ALREADY extracted (media-docs.json). |
| 25 | [youtu.be/RGVXR0OFNzI](https://youtu.be/RGVXR0OFNzI) | media | T1 | prose | Ray-added video. Transcribed + extracted 2026-07-22. |
| 26 | [youtu.be/mHSOsy_usAg](https://youtu.be/mHSOsy_usAg) | media | T1 | prose | Ray-added video. Transcribed + extracted 2026-07-22. |
| 27 | [youtu.be/0CZtRw0KrXo](https://youtu.be/0CZtRw0KrXo) | media | T1 | prose | Ray-added video. Transcribed + extracted 2026-07-22. |
| 28 | [openai/symphony](https://github.com/openai/symphony) | repo | T1 | code | Conductor + DB-free filesystem/tracker recovery; long-horizon orchestration. AST-ingested 2026-07-23. |
| 29 | [kumanday/OpenSymphony](https://github.com/kumanday/OpenSymphony) | repo | T1 | code | Open port of the Symphony conductor pattern. AST 2026-07-23. |
| 30 | [zaalipro/cymphony](https://github.com/zaalipro/cymphony) | repo | T2 | code | Symphony-family orchestration port. AST 2026-07-23. |
| 31 | [Sugar-Coffee/stokowski](https://github.com/Sugar-Coffee/stokowski) | repo | T2 | code | Symphony-family conductor port. AST 2026-07-23. |
| 32 | [ReyJ94/Sol-Orchestrator](https://github.com/ReyJ94/Sol-Orchestrator) | repo | T1 | code | Durable-goal/disposable-workflow split; blackboard volunteer pattern. AST 2026-07-23. |
| 33 | [ai-boost/awesome-harness-engineering](https://github.com/ai-boost/awesome-harness-engineering) | repo | T2 | code | Harness-engineering catalog. AST 2026-07-23. |
| 34 | [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | repo | T2 | code | CC internals / harness-engineering notes. AST 2026-07-23. |
| 35 | [MarcosNahuel/antigravity-plugin-cc](https://github.com/MarcosNahuel/antigravity-plugin-cc) | repo | T1 | code | antigravity lane wiring for CC. AST 2026-07-23. |
| 36 | [simplybychris/antigravity-plugin-cc](https://github.com/simplybychris/antigravity-plugin-cc) | repo | T1 | code | antigravity lane wiring variant. AST 2026-07-23. |
| 37 | [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | repo | T1 | code | Read-through + MCP memory patterns; markdown substrate. AST 2026-07-23. |
| 38 | [topoteretes/cognee](https://github.com/topoteretes/cognee) | repo | T2 | code | ingest→graph→retrieval memory engine (design ref). AST 2026-07-23. |
| 39 | [lucasrosati/claude-code-memory-setup](https://github.com/lucasrosati/claude-code-memory-setup) | repo | T1 | code | Vault template + chat-import; second-brain prior art. AST 2026-07-23. |
| 40 | [addyosmani — agent-harness-engineering](https://addyosmani.com/blog/agent-harness-engineering/) | article | T1 | prose | Harness = everything but the model; Agent=Model+Harness. Prose extracted 2026-07-23. |
| 41 | [augmentcode — what is loop engineering](https://www.augmentcode.com/blog/what-is-loop-engineering-and-how-are-leading-software-engineering-teams-using-it) | article | T1 | prose | Loop engineering: Trigger→Execute→Verify→Outcome→Improve. Extracted 2026-07-23. |
| 42 | [youmind — loop engineering guide](https://youmind.com/landing/x-viral-articles/loop-engineering-ai-agents-guide) | article | T1 | prose | Loop = recursive goal + verifiable stop condition. Extracted 2026-07-23. |
| 43 | [martinfowler/Böckeler — harness engineering](https://martinfowler.com/articles/harness-engineering.html) | article | T1 | prose | Foundational harness-engineering overview (user-side). Extracted 2026-07-23. |
| 44 | [agent-engineering.dev — harness engineering 2026](https://www.agent-engineering.dev/article/harness-engineering-in-2026-the-discipline-that-makes-ai-agents-production-ready) | article | T1 | prose | Harness = 3rd maturity phase; 5 layers. Extracted 2026-07-23. |
| 45 | [humanlayer — skill-issue harness engineering](https://www.humanlayer.dev/blog/skill-issue-harness-engineering-for-coding-agents) | article | T1 | prose | Most agent failures = config skill-issues, not model weights. Extracted 2026-07-23. |
| 46 | [platform.claude — code execution tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool) | docs | T1 | prose | Sandboxed Python/bash; powers PTC + dynamic filtering. Fetched via mintlify `.md`. Extracted 2026-07-23. |
| 47 | [openai — harness engineering (Codex)](https://openai.com/index/harness-engineering/) | article | T1 | prose | Codex agent-first (Ryan Lopopolo): repo-knowledge as system of record, AGENTS.md-as-TOC, increasing autonomy, entropy GC / golden principles. FULL text recovered via logged-in Chrome (graphify fetch got TOC only; WebFetch 403'd). 2026-07-23. |
| 48 | [platform.claude — programmatic tool calling (PTC)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling) | docs | T1 | prose | PTC: Claude writes Python calling tools as async fns; 20-40% fewer tokens. Vendored + extracted 2026-07-23. |
| 49 | framework plan — long-running autonomous framework (ladybug) | designdoc | T1 | prose | OUR design: kb_search read-through, G1 staleness, single-writer lock, quarantine gate, compounding loop. Vendored 2026-07-23. |
| 50 | second-brain report (2026-07-22b) | designdoc | T1 | prose | OUR research: graphify update ingests md vault free; Capture→Map→Ask→Write-back. Vendored 2026-07-23. |
| 51 | autonomous-execution program bible (2026-07-19) | designdoc | T1 | prose | OUR locked-decisions design for the graphify-substrate autonomous program. Vendored 2026-07-23. |
| 52 | harness-engineering research (2026-07-23) | designdoc | T1 | prose | OUR research: P1-P8 patterns, RAGA, BORROW/AVOID. Vendored 2026-07-23. |
| 53 | [claude-plugins-community — marketplace inventory (235 relevant)](https://github.com/anthropics/claude-plugins-community) | inventory | T2 | prose | Queryable 235-plugin harness/orchestration/memory inventory. Extracted 2026-07-23. |
| 54 | [louisbouchard — Graph Engineering Explained](https://www.louisbouchard.ai/graph-engineering-explained/) | article | T1 | prose | Graph engineering = connecting agent loops; nodes now interpret tasks; Airflow/DAG lineage; organized-nonsense; reality anchors. Canonical home of the LinkedIn "graph-engineering-explained" post (LinkedIn URL = login wall). FULL text via logged-in Chrome. 2026-07-23. |
| 55 | [antigravity.google/docs/cli/permissions](https://antigravity.google/docs/cli/permissions) | docs | T2 | deferred | BLOCKED: JS-rendered SPA — both graphify fetch and browser got marketing nav only, no doc body. R2 antigravity-deny detail lives in the framework plan (#49). |
| 56 | [x.com/towards_AI — "what the hell is graph engineering"](https://x.com/towards_AI/article/2078892237287801283) | article | T1 | prose | Graph = map of who-does-what-next; loops-vs-graphs (graphs contain loops); DAGs vs cycles; reality anchors. RECOVERED via logged-in Chrome (X auth wall). 2026-07-23. |

## Progress log

- **2026-07-23 — long-running-framework wave (sources #28–#56).** Staged ingestion for
  the autonomous-framework program (plan: `we-want-a-long-mighty-ladybug.md`).
  - **12 repos AST-ingested (free, no tokens)** via manifests + `kb-build`: openai/symphony
    + ports (OpenSymphony, cymphony, stokowski), Sol-Orchestrator, awesome-harness-engineering,
    learn-claude-code, both antigravity-plugin-cc, basic-memory, cognee, claude-code-memory-setup.
    Graph 62k → ~120k nodes.
  - **16 focus docs host-agent extracted** (two Claude `Workflow` fan-outs, 0 errors, ~1.78M
    subagent tokens) → 3 combined chunks: `harness-loop-graph-engineering-docs.json` (265n/317e),
    `framework-design-docs.json` (128n/156e — OUR plan + second-brain + autonomous bible + harness
    research), `marketplace-inventory-docs.json` (234 plugin nodes / 219 category edges). Total new
    doc content: 627 nodes / 692 edges.
  - **Browser recovery (logged-in Chrome)** where graphify's fetcher hit walls/JS/12k-cap:
    **openai/Codex harness** (TOC-only + WebFetch-403 → FULL), **X/@towards_AI graph-engineering**
    (auth wall → FULL), **martinfowler/Böckeler** (truncated → FULL), **LinkedIn graph-engineering**
    (login wall → recovered via canonical louisbouchard.ai). One dead-end: **antigravity CLI
    /permissions** (JS SPA, no doc body in DOM either route) — covered by the vendored framework plan.
  - Ingestion path: every source routed THROUGH graphify (`kb-add` fetch, or vendored + host-agent
    extract → `kb-merge`/`kb-build`), per CLAUDE.md invariant 5. Committed = reproducible inputs
    (manifests + extraction chunks + vendored `sources/media/` bodies + this REGISTRY); `graph.json`
    derived/gitignored, reproduced by `kb-build`.

- **2026-07-22 — code layer ingested (free AST, no tokens).** 10 repos code-ingested
  into the aggregate graph (60,893 nodes / 133,003 edges / 2,351 communities):
  deer-flow, skillopt, codex-orchestration, fable5-orchestrator, fable-orchestrator,
  system-prompts-leaks, last30days-skill, awesome-claude-code, claude-plugins-community,
  ecc (+ graphify). **fable-advisor** skipped — prose-only, awaiting the wave.
  Query + MCP (10 tools) verified. Clean `kb-build` reproduces end-to-end.
  **Still PENDING for every repo: T1 host-agent PROSE extraction** (READMEs/skill
  docs — where the orchestrator insight lives). Docs sitemaps (#1–#3), articles/forum/
  media (#10, #12–#14, #19) untouched. X timelines (#20–#21) deferred.

- **2026-07-22 — Claude docs enumerated (wave-1 vendored).** Parsed both Claude
  sitemaps → **173 on-topic English pages** (`sources/claude-docs-backlog.txt`).
  14 crown-jewel pages fetched (Mintlify `.md`) to the **transient** cache
  `sources/raw/claude-docs/` (gitignored): multiagent-orchestration, managed-agents
  overview/define-outcomes, prompting-claude-fable-5, introducing-fable-5,
  choosing-a-model, whats-new-4-8, agent-sdk overview/subagents/cost-tracking/skills,
  model-config, agents, hooks. **PENDING**: host-agent prose extraction → chunk.

- **2026-07-22 — long-running/dynamic-workflow sources added** (Ray) →
  `sources/workflow-sources.txt` (19 URLs, categorized by handling). Feed the
  autonomous-orchestrator design. **7 code.claude.com docs pre-staged** to
  `sources/raw/claude-docs/` (commands, whats-new, best-practices, common-workflows,
  workflows, channels, goal). **11 blog/research articles** are HTML-only → extract
  via **WebFetch** (claude.com/blog dynamic-workflows/loops/verification-loops/
  migration/fable-field-guide, anthropic.com long-running-Claude, claudefa.st,
  towardsdatascience 24h-agents, digg, mindstudio patterns). **1 YouTube** (whisper).
  These are HIGH priority for the orchestrator/Workflow build (phase 4).

- **2026-07-22 — phase 1a DONE: 20 crown-jewel/workflow Claude docs extracted +
  merged.** Host-agent semantic extraction via a resumable `Workflow` fan-out
  (20 parallel Opus extractors, run `wf_06cee647-acc`, 0 errors) → one combined
  chunk `sources/extractions/claude-docs-docs.json` (**621 nodes / 888 edges**,
  provenance-tagged `source_url` + `captured_at=2026-07-22`). Merged into the
  aggregate graph (`_merge_docs.py`, `dedup=False`) → **61,524 nodes / 133,897
  edges / 2,385 communities**. Verified: managed-agent orchestration + dynamic-
  workflow nodes are queryable and cross-link to the deer-flow orchestrator code
  (TokenBudgetConfig, CircuitBreakerConfig, lead_agent, SubagentsAppConfig).
  Recorded via `kb-remember` + `kb-reflect`. `/commands` was extracted earlier
  (`claude-commands-docs.json`). **PENDING phase 1b**: the 12 blog/HTML + 1
  YouTube sources in `workflow-sources.txt` via `graphify add` (the mandate;
  WebFetch note above is superseded by the graphify-ingestion-first rule).

- **2026-07-22 — phase 1b DONE: 11 long-running/dynamic-workflow blog sources
  ingested via graphify.** Fetched through `mise run kb-add` → `graphify add`
  (the mandate path — clean md into `raw/` with graphify's own source_url +
  captured_at frontmatter; no-key `add` fetches but does NOT recluster, so batch-
  fetch → one merge). Host-agent extraction via a resumable Workflow (11 parallel
  Opus extractors, run `wf_910ff42c-45f`, 0 errors, none thin) → one chunk
  `sources/extractions/claude-workflow-blogs-docs.json` (**223 nodes / 319 edges**).
  Merged (`dedup=False`) → **61,747 nodes / 134,209 edges / 2,405 communities**.
  Sources: anthropic.com long-running-Claude; claude.com/blog dynamic-workflows-
  intro / harness-for-every-task / getting-started-with-loops / verification-loops /
  ai-code-migration / fable-field-guide; claudefa.st dynamic-workflows;
  towardsdatascience 24h-agents; digg; mindstudio patterns. Verified: a "keep an
  agent running autonomously for hours" query synthesizes across the new blogs +
  fable-5/agent-sdk docs + orchestrator code. `kb-remember` + `kb-reflect` run.
  **YouTube** (`youtu.be/e3rbymcXeuc`) — DONE: audio downloaded via `graphify add`,
  then transcribed with graphify's bundled faster-whisper
  (`graphify.transcribe.transcribe`, model=base, 37 segments) — NO API key needed
  (whisper is local). Extracted → `sources/extractions/claude-video-docs.json`
  (**20 nodes / 23 edges**: background subagents auto-PR, /fork, /subtask, Sonnet-5
  1M, and the durability suite — network-drop survival, rate-limit report+resume,
  session survives daemon restart, interrupted agents resume). Merged → **61,767
  nodes / 134,232 edges / 2,414 communities**. `raw/` gitignored (transient;
  extraction chunk is the artifact). **Phase 1 COMPLETE: 32 sources ingested.**

- **2026-07-22 — wave 2: orchestrator/advisor/fallback prose + 6 Ray videos (phases 3–4 grounding).**
  Closed the "code-ingested but no prose" gap for the orchestrator repos + the fallback cluster
  + 6 new videos. **Two host-agent Workflow fan-outs (Opus, Claude-only), 16 agents, 0 errors:**
  - **Repos + articles** (`sources/extractions/orchestrator-repos-docs.json`, **261 nodes / 282
    edges**): fable-advisor (#6, prose-only, first ingest — the architect/advisor-executor
    routing doctrine: cheapest-adequate-lane table, cost discipline, five-part spec contract,
    cross-vendor review, verify-before-done), fable5-orchestrator (#8), fable-orchestrator (#9),
    codex-orchestration (#7), deer-flow (#4), skillopt (#5), last30days-skill (#15),
    claude-fable-5 system-prompt leak (#11, priors distilled), + articles mindstudio
    advisor-executor (#10) & linas Fable-5→Opus-4.8 (#12).
  - **Videos** (`sources/extractions/fable-videos-docs.json`, **121 nodes / 139 edges**): 6 Ray
    videos #22/#23/#25/#26/#27 + fallback video #14 — `mise run kb-add` (audio) →
    `mise run kb-transcribe` (local faster-whisper, NO key) → host-agent extract. URL↔hash map
    in `raw/video-map.txt`.
  - Merged (`dedup=False`) → **62,149 nodes / 134,652 edges / 2,354 communities**; relabeled
    (deterministic hub); `kb-artifacts` regenerated (svg skipped >5000 nodes); `kb-remember` +
    `kb-reflect` (10 memories → LESSONS.md). Verified: an advisor/executor+fallback query now
    synthesizes the new prose (linas fallback, fable-advisor lanes, mindstudio "Opus/Sonnet as
    Executor") with deer-flow rate-exhaustion/circuit-breaker code + model-config effort levels.
  - **#13 (r/claude) BLOCKED** — Reddit bot-verification wall; graphify fetch returns a stub.
    Deferred; fallback pattern is control-armed by #10/#12/#14.
  - **Still deferred:** the ~151-page code.claude.com long tail (#2, T2 API/SDK ref), the T2
    catalogs #16/#17/#18 prose, #19 mindstudio tag set, #20/#21 X timelines (T3).

### Freshness policy (mintlify / refetchable prose)

Mintlify doc mirrors go stale — do NOT commit raw `.md` as frozen sources. The
durable artifact is the **extraction chunk** (records `source_url` + `captured_at`).
Raw fetches live in gitignored `sources/raw/`. Refetch + re-extract when a
doc-sourced node is **> 1 month** past its `captured_at`. Going forward, query the
graphify KB (which we control), not external mirrors.

## Program notes

- **graphify-first**: ingest+extract into this KB **before** web search — graphify
  fetches the URL itself, so the graph is the primary research surface.
- **Fallback cluster** (#11–#14): the Fable-5 token-exhaustion → Opus-4.8 fallback
  behavior. Cross-read, don't trust a single source (control-arm the claim).
- **Reference docs already reviewed**: [Fable-5 prompt-engineering] is #3; keep the
  README/CLI as the command authority (the graph is the "how it works" layer).
- Wave 1 (get a queryable graph fast): #1–#9, #11–#14 code+prose. Wave 2: #15–#19.
  #20–#21 stay deferred.
