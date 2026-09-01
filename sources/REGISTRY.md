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
| 10 | [advisor-executor-pattern (mindstudio)](https://www.mindstudio.ai/blog/advisor-executor-pattern-claude-code-fable-5) | article | T1 | prose | THE advisor/executor decision. Extracted 2026-07-22. ⚠️ **THAT EXTRACTION WAS TRUNCATED, and it is this corpus's first PROVEN casualty of `kb-add` (#200).** Re-fetched losslessly 2026-08-06 at **17,161 chars**; the 18 nodes in `orchestrator-repos-docs.json` under `source_file = mindstudio-advisor-executor.md` reach only **54%** of the article, with **0 of 17 located concepts past the 60% mark**. Control arm: **16 headings** live past 60% — `## Common Mistakes and How to Avoid Them` and its four named anti-patterns (*Asking the Advisor to Do Too Much*, *Under-Specifying the Executor Prompt*, *Skipping the Structured Output Step*, *Using the Executor for Decision-Making*), 6 FAQ entries and `## Key Takeaways` — and the graph has nothing from any of them. Second control, same batch and path: `linas-fable5-fallback.md` is only 3,140 chars (under the cap), reaches **94%**, and is CLEAN — so the probe discriminates and the mechanism explains the split. **Being re-extracted under the same `source_file` with a chunk-level `supersedes`**, so #189's collision gate replaces the 18 rather than duplicating them. Lossless copy at `sources/media/advisor-executor-claude-code-fable5.md`. |
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
| 57 | [claude.com — The new rules of context engineering for Claude 5 generation models](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models) | article | T1 | prose | **Directly re-scopes our orchestrator doctrine.** 80%+ of Claude Code's system prompt deleted for Opus 5 / Fable 5 with no eval loss. Rules→judgement; examples→interface design; upfront→progressive disclosure; repetition→tool descriptions; CLAUDE.md-memory→auto-memory; simple specs→rich references (incl. rubrics + verifier agents). graphify fetch = nav shell; recovered via WebFetch + Chrome-a11y control arm. 2026-07-24. |
| 58 | [claude.com — Claude models explained: choosing the best model](https://claude.com/blog/claude-models-explained-choosing-the-best-model-for-your-use-case) | article | T1 | prose | **Advisor-strategy economics, quantified.** Start with the most intelligent model + dial effort; cost-per-task often LOWER for smarter models. Mythos/Fable vs Opus vs Sonnet vs Haiku selection rubric. SWE-bench Pro: Sonnet 5 + Fable 5 advisor = within 10% of Fable 5 at 63% of the price. Same fetch path as #57. 2026-07-24. |
| 59 | [claude.com — Building verification loops in Claude Code with skills](https://claude.com/blog/building-verification-loops-in-claude-code-with-skills) | article | T1 | prose | **Names our seam's missing taxonomy.** Verification loop = agent checks own work + fixes before moving on. Four kickoff modes: standalone / embedded / chained / on-every-PR. Built-ins: /verify, toolchain, Code Review preview, GH Actions, spec validation, CMA rubrics + grader agent. Same fetch path as #57. 2026-07-22. |
| 60 | [cerebras.ai — How We Built Our Knowledge Base](https://www.cerebras.ai/blog/how-we-built-our-knowledge-base) | article | T1 | prose | **The KB-architecture benchmark for our gap analysis.** 15k questions/day. One Postgres embeddings table + one connector per source; LLM thread distillation (embed the artifact, not the transcript); bursting (IDF≥4.0, ≥200 chars, reactions); hybrid FTS+vector+IDF+age-decay; CocoIndex language-aware recursive code chunking w/ incremental re-embed; planner→executor→synthesis; RRF k=60 → 0-10 reranker → post-rank context expansion; MCP exposes primitives (Claude Code is the orchestrator); projects = scoped search. **HTTP 500 to ALL non-browser clients; recovered via Chrome.** 2026-07-15. |
| 61 | [jdx/mise](https://github.com/jdx/mise) | repo | T2 | pending | **The dependency that gates every other one here** — every workflow is a `mise run` task, and it self-updates out-of-band. Read extensively 2026-07-27 (all 604 release notes + `docs/templates.md`, `docs/tasks/**`, `docs/environments/**`, the JSON schema) while pinning it; findings in `docs/research/agents/mise-currency.md` and `mise-path-research.md`, and now tracked in `currency.toml` `[tool.mise]`. Registered per `research-repo-enumeration.md`. **T2 not T1**: what we needed was release notes and schema, which are versioned artifacts a manifest pins better than a prose extraction — ingest the repo for AST if a future question needs the source, not to re-answer this one. |
| 62 | [gregceccarelli.com — Goal Engineering](https://www.gregceccarelli.com/goal-engineering) | article | T1 | prose | **The goal+rider convention this repo's `docs/goals/` adopts.** Two files per round: a goal capped at 4,000 chars (the `/goal` payload) + an unbounded rider. Headline-word test, posture-as-negations, the preserve list ("the agent's permission slip" against Goodhart), the eleven-phase depth-test loop, V1-CANDIDATES as overflow valve. Carries the sharpest published critique of `/goal` itself: an LLM-as-judge inside the same harness is "opinion, not evidence" — his `dr-gate` re-runs the checks and signs results with a secret the agent cannot read. Vendored `sources/media/goal-engineering-ceccarelli.md`; extracted 2026-07-27. |
| 63 | [sabrina.dev — 6 INSANE Projects to Learn Claude Fable and /goal](https://www.sabrina.dev/p/6-insane-projects-to-learn-claude-fable-loop-engineering) | article | T1 | prose | **The 5-part condition template** — TASK / WHY / OUTCOME / CONSTRAINTS / VERIFICATION — plus six worked VERIFICATION lines. "'Make it good' isn't a finish line. 'Scores over 8+ out of 10 using my custom grading skill' is." Names both failure directions: without VERIFICATION an agent "either stops too early or loops forever guessing". Free post (HTTP 200, `audience:everyone`), verified not paywalled. Caveat: the URL slug says loop-engineering but the mechanics live in a separate prior post, NOT fetched. Vendored `sources/media/loop-engineering-sabrina.md`; extracted 2026-07-27. |
| 64 | [code.claude.com/docs/en/goal.md](https://code.claude.com/docs/en/goal.md) | docs | T1 | prose | **The authority on `/goal` semantics, and the only one that changes under us.** The evaluator "does not call tools, so it can only judge what Claude has already surfaced in the conversation" — the constraint every clause in a goal condition must satisfy. Also the 4,000-char cap, the turn clause as the only bound, `{ok, reason}` with the reason fed back as Claude's next instruction, and resume semantics. Fingerprinted in `currency.toml` `[tool.claude-code]` `docs_watch` so a revision surfaces as DOCS DRIFT rather than silently staling the `goal-engineering` skill. Vendored `sources/media/claude-code-goal-docs.md`; extracted 2026-07-27. |
| 65 | [mrkhachaturov/agent-harness-docs](https://github.com/mrkhachaturov/agent-harness-docs) | repo | T1 | prose | **The docs-mirror pin — the mechanism, not just a source.** Auto-synced every 3h by GH Actions cron; 549 `.md` across `docs/{claude-code,cursor,codex,opencode,pi}/`. MEASURED 2026-07-30 at the pinned SHA `03853a01`: `docs/claude-code/{goal,hooks,skills}.md` are **byte-identical** to the live `code.claude.com` pages (control arm: a bogus path at the same SHA -> 404), so the ingestion path and `docs_watch`'s fingerprints agree by construction. First `kind = docs` manifest — no AST pass, and `kb-update` prints the changed-page worklist from `git diff <old>..<new>`, which is what #76 lacked when three sha256 values moved with no way to read the delta. claude-code goal/hooks/skills extracted -> `claude-code-docs-mirror-docs.json`; codex/cursor/opencode/pi deferred to #82. Derivative of [ericbuess/claude-code-docs](https://github.com/ericbuess/claude-code-docs) (ships its MIT LICENSE verbatim); MIT covers the tooling, the content stays Anthropic's/each vendor's. |
| 66 | [deusdata/codebase-memory-mcp](https://github.com/deusdata/codebase-memory-mcp) | repo | T1 | pinned | **Peer retrieval tool #1 for the Navigable gap analysis** (2026-08-01). C, MIT, 167MB (38.4MB C), claims 158 languages and sub-ms queries. Most of the C is a **vendored tree-sitter runtime** at `internal/cbm/vendored/ts_runtime/` per its own `THIRD_PARTY.md` — ingested anyway, no exclusions (Ray's call, backed by the measured 1.3x source→graph expansion). Pinned `d6be58ef`. |
| 67 | [tirth8205/code-review-graph](https://github.com/tirth8205/code-review-graph) | repo | T1 | pinned | **Peer retrieval tool #2.** Python, MIT, 12MB (3.4MB Py). MCP server + CLI over a persistent code map — the closest structural analogue to what graphify does for us, so the gap analysis runs in BOTH directions (what it has that graphify lacks, and the reverse). Pinned `c3f3a668`. |
| 68 | [cosmtrek/mindwalk](https://github.com/cosmtrek/mindwalk) | repo | T1 | pinned | **NOT a retrieval tool — a harness-observability lens.** Go, MIT, 4MB. Replays Claude Code / Codex **session logs** on a 3D repo map; it does not index or retrieve code, so comparing it to graphify on retrieval is a category error (Ray, 2026-07-31). Its question is instead: can it show what a `kb-review` lane or a `codex` implementer actually touched during a round, versus what the spec scoped? **Default branch is `master`, not `main`** — `kb-manifest-add` failed with *"ref 'main' not found"*, which is a DIFFERENT failure from a missing repo (that one dies in `git ls-remote` with exit 128), so the two are distinguishable. Pinned `e208b6b8`. |
| 69 | [getzep/graphiti](https://github.com/getzep/graphiti) | repo | T2 | pending | **Fourth-peer-tool CANDIDATE only** — proposed 2026-08-01 for the Settled round's P3, NOT approved and NOT pinned. Temporal knowledge graph for agent memory; the closest peer on the *memory* axis rather than the retrieval one. Size and licence are UNVERIFIED here on purpose: P3 must re-check them live, because a candidate list is exactly the place an inherited number goes unchallenged. |
| 70 | [oraios/serena](https://github.com/oraios/serena) | repo | T2 | pending | **Candidate only**, same caveat as #69. LSP-backed semantic code toolkit exposed over MCP — answers symbol questions from a language server rather than from a stored graph, which is the sharpest available contrast with graphify's AST-extraction model. **2026-08-26 update (tool-funnel gap-sweep delta D2):** GitHub issue **#276** names Serena explicitly — quoted verbatim: *"Start `ty` LSP through an existing free/local adapter where possible; evaluate Serena `python_ty` before writing a JSON-RPC client."* — proposing its `python_ty` adapter as the thing to evaluate before hand-writing a `ty` JSON-RPC LSP client (see row 122). `sources/serena.manifest` now pins the repo (SHA-resolved 2026-08-26); Status here stays `pending` rather than `manifest` deliberately — the two columns are allowed to disagree, and the manifest is what this row was missing, not a status change. |
| 71 | [blarApp/blarify](https://github.com/blarApp/blarify) | repo | T2 | pending | **Candidate only**, same caveat as #69. Converts a codebase into a graph (Neo4j-backed) — structurally the nearest analogue to `graphify extract` + `push_to_neo4j()`, so a gap analysis would run in both directions. |
| 72 | [Aider-AI/aider](https://github.com/Aider-AI/aider) | repo | T2 | pending | **Candidate only**, same caveat as #69. Its *repo-map* ranks a tree-sitter graph by PageRank to fit a context budget — the one candidate whose approach to "what matters in this repo" is genuinely different from ours, and therefore the most likely to surface a real gap. Much larger than the other three; verify the cost before proposing it. |
| 73 | [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph) | repo | T1 | pinned | **Fourth peer tool, APPROVED and ingested** (Ray, 2026-08-02) — he proposed it and GitNexus over all four candidates above, and rows 69–72 stay `pending` because none was chosen. C, MIT, 678 files / 16 MB, 64.0k stars, pushed the day it was pinned. Its own description is almost graphify's pitch — *"Pre-indexed code knowledge graph, auto syncs on code changes, for Claude Code… 100% local"* — including the auto-sync that mirrors `kb-watch`, and an independent C implementation rather than another Python variation. **`scope = corpus`, deliberately**: this round measured that `scope = study` sits in a file nothing routinely queries, so it cannot reproduce the one mechanism the peer track has ever paid off through (cognee's 10,099 test↔src edges were visible because a query over the AGGREGATE reached them). Pinned `49c11fc2`. 6,386 nodes / 16,013 edges. |
| 74 | [abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus) | repo | T1 | pinned | **Fifth peer tool, APPROVED and ingested** (Ray, 2026-08-02). TypeScript, 4,692 files / 51 MB, 44.9k stars, pushed the day it was pinned. Client-side in-browser knowledge graph + Graph RAG agent, zero-server — the most architecturally distant peer, which is what makes its gap analysis able to say something ours cannot. ⚠️ **PolyForm Noncommercial 1.0.0**, and GitHub reports it as `NOASSERTION` (unclassifiable, not absent) — control-armed against `topoteretes/cognee`, which also returns `NOASSERTION` while its licence is Apache-2.0, so that field is simply unpopulated. Nothing here redistributes it (manifest pins a URL + SHA, clone and derived graph are gitignored), but the noncommercial condition travels with the corpus. **`scope = study`**: 51 MB against ~147 MiB of headroom under graphify's 512 MiB cap, and sub-graph→aggregate expansion is far worse than 1:1. Pinned `911151e2`. 24,671 nodes / 53,462 edges. |
| 75 | [mattpocock/skills](https://github.com/mattpocock/skills) | docs | T1 | prose | **The skills this repo actually runs, and the corpus knew nothing about them** (Ray, 2026-08-02) — `wayfinder`, `grilling`, `to-spec`, `to-tickets`, `code-review`, `domain-modeling` are all invoked here, yet `mattpocock` returned **0 hits** across 32 manifests. MIT. Pinned `f34d927` on **`changeset-release/main`**, `kind = docs`, 103 markdown files (node_modules excluded). ⚠️ **The pinned commit is NOT on `main`.** `kb-manifest-add` wrote `ref = main` while pinning a commit only reachable from the changesets bot's release branch; `main` is `2ab9580`, this commit's parent. `ref` was corrected to match the commit — see the manifest's own comment. **A first draft of this row claimed changesets are "ABSENT from `main`" and that was FALSE**: `.changeset/ship-as-claude-plugin.md` and the two wayfinder ones ARE present at real `main`, and absent only at the *release* commit we pinned. The probe read the clone at the pinned commit and its result was reported as a fact about `main` — a bounded probe reported as an answer (`probes-need-a-control-arm.md` rule 3). Both surfaces carry the rationale: `CHANGELOG.md` at this pin, `.changeset/` at `main`. **6 of 103 extracted so far** (the 8-chunk batch included 2 aihero pages counted in row 76). ~141k tokens/file measured, so the remaining 97 are ~13.7M — deferred deliberately, not forgotten. |
| 76 | [aihero.dev skills pages](https://www.aihero.dev/skills) | docs | T1 | prose | Matt Pocock's editorial pages for the same skills. **NOT COMMITTED — bodies live in gitignored `sources/aihero-skills/`** (matched by `.gitignore` `sources/*/`), the same posture as every pinned clone: on disk for offline use, never republished. Provenance in **`sources/aihero-skills.pages.toml`** (sitemap + per-page `content_sha256`); deliberately not `*.manifest`, since `kb_setup.manifest` requires url+ref+commit and clones with git while this upstream is a website. **8 pages, not 29**: the other 21 fetched 2026-08-02 were dropped as REDUNDANT — measured **100% token-set overlap** with the MIT repo's `docs/engineering|productivity/<name>.md` (388/388, 304/304, 230/230, 313/313, 174/174), aihero adding only site chrome. These 8 have no repo counterpart. ⚠️ **aihero.dev is a commercial site; its editorial prose is all-rights-reserved.** `robots.txt` permits CRAWLING (`Allow: /`, `GPTBot` explicit, `/skills-*` not disallowed — control-armed against `claude.com/robots.txt`) which is **not** permission to redistribute. **No JS-shell risk**: real markdown twins, control-armed with `/zqx-no-such-8814.md` → **404**. `/ai-coding-dictionary/skill.md` → 404 is the site's design — `llms.txt` lists twins for posts/workshops/tutorials/products/cohorts/events/skills, not the dictionary. **2 of the original 29 were extracted, and both are in the redundant 21**, so their content is also held MIT via row 75. |
| 77 | [anthropics/claude-code](https://github.com/anthropics/claude-code) | repo | T1 | pinned | **Claude Code's own repo — pinned `kind = docs` @ `v2.1.222`, 2026-08-05.** No product source is published, so there is nothing to AST: the payload is `CHANGELOG.md`, `feed.xml`, `plugins/`, `examples/`, `.github/`, `.claude/`. ⚠️ **Its changelog was ALREADY in the corpus** via the pinned mirror — `sources/agent-harness-docs/docs/claude-code/changelog.md`, **5,322 lines** at the mirror's current pin `cc1c1603`, whose header credits it to "the Claude Code repository". So this pin adds only `feed.xml`, the plugin/example sources and the git tags; it is NOT the route to the changelog. *(A first draft of this row said 5,258 lines and quoted the header as "generated from the CHANGELOG.md on GitHub". Both were true at the mirror's PREVIOUS pin `03853a01` and were carried across the bump this same round advanced — `probes-need-a-control-arm.md` rule 6, "a number can be invalidated by the very commit that writes it". The old file really is 5,258 lines with that exact header; a cold review caught the drift.)* The 2.1.220→2.1.222 review found two items landing on this repo directly: PreToolUse auto-allow hooks could bypass tool restrictions in background agent tasks (our entire graphify invariant enforcement is a PreToolUse deny), and a zsh `[[ ]]` permission-check bypass in the Bash tool. |
| 78 | [Rootly-AI-Labs/rootly-graphify-importer](https://github.com/Rootly-AI-Labs/rootly-graphify-importer) | repo | T2 | pinned | **`scope = study`, deliberately — it is a FORK of graphify, not a consumer** (Ray asked for it 2026-08-05, linked from graphify.com/blog). MIT, 42 stars, Python. Its value is the one thing the corpus lacks: how a NON-CODE domain (incidents/alerts/teams) becomes graphify nodes+edges — `ingest.py`, `rootly_flow.py`, `models_rootly.py`, `rootly_export.py`. ⚠️ **Its `pyproject.toml` declares `name = "graphifyy"`, `version = "0.3.6"`** and it vendors graphify's own modules (`build.py`, `cluster.py`, `extract.py`, `analyze.py`, …). Last pushed **2026-04-21**, so those copies are ~3.5 months stale against our 0.9.33. As corpus code it would answer "how does graphify work" from April source sitting in a disjoint namespace **nothing can flag** — the exact failure `sources/graphify.manifest`'s own comment records from 2026-07-23. Study scope keeps it out of `graph.json`; verified two-sided (0 hits in the corpus graph, 1,173 in `study-graph.json`, with five corpus sources as PRESENT controls). Pinned `07eed6a5`. |
| 79 | [ramakay/claude-self-reflect](https://github.com/ramakay/claude-self-reflect) | repo | T1 | prose | **`scope = study`. THE prior art for the self-reflection loop** — Ray flagged it for close review 2026-08-06, twice. A single 44 MB Rust binary + MCP server that indexes past Claude Code transcripts, task outcomes and plan documents and makes them searchable; no database, container or API key. MIT, 219 stars, v9.4, 720+ tests. ⚠️ **It has ZERO skills and ZERO agents** — no `skills/`, no `agents/`, no SKILL.md; its value is the ARCHITECTURE, in 56 markdown files. ⚠️ **282 MB clone, of which ~79 MB is images** (43 `.png`; the three largest are 7.99 / 4.84 / 4.55 MB) — study scope keeps that out of `graph.json`. Reachability verified both arms: `--graph graphify-out/study-graph.json` returns `reflect_on_past()` (`csr-engine/src/mcp/tools.rs:108`), `ConversationChunk`, `count_unindexed_transcripts()`, while the SAME question against the aggregate returns pkl/React/cognee hits and **zero** csr-engine. Pinned `86afb4a3`. |
| 80 | [AllanHarlen/cc-orchestrador-subagents](https://github.com/AllanHarlen/cc-orchestrador-subagents) | repo | T2 | pinned | **`scope = study`. ⚠️ NO LICENCE DECLARED UPSTREAM** (`gh api` → `licence: NONE`, checked 2026-08-06) — pinned for study only, never redistributed. Thinnest of the 2026-08-06 batch: 27 files, **1 SKILL.md**, 2 commands (`orchestrador.md` + `orchestrator.md`, both spellings), and a `.claude/settings.json`. 1 star, last push 2026-07-14. 2.44 MB of its 2.86 MB is a single `banner.png`. Prose extraction deliberately NOT run — Ray's curated subset excludes it unless the synthesis asks. Pinned `911ce1af`. |
| 81 | [2389-research/claude-plugins](https://github.com/2389-research/claude-plugins) | repo | T2 | pinned | **`scope = study`. It is a plugin MARKETPLACE INDEX, not the plugins.** 143 files / 65 `.md`, but **0 SKILL.md and 0 agent files** — the payload is `.claude-plugin/marketplace.json` plus `docs/AGENTS.md`. MIT, 90 stars. Registered because a marketplace index is the map of what exists, but prose extraction is skipped for the same reason rows 16/17 were: catalogue, low insight density. Pinned `6b82b81a`. |
| 82 | [adihebbalae/Attacca](https://github.com/adihebbalae/Attacca) | repo | T1 | prose | **`scope = study`. The DENSEST skill/agent collection of the batch — 26 SKILL.md + 3 agent files** (`critic.md`, `researcher.md`, `security-auditor.md`) + 5 hooks, under a plugin layout (`plugins/<name>/skills/**`), plus `AGENTS.md`, `template/AGENTS.md` and a `.claude/settings.json`. ⚠️ **Two manifest traps, both hit:** its default branch is **`master`** not `main` (so `kb-manifest-add` needs `--ref master`, or `git ls-remote` finds nothing), and it is a GitHub **template repo** (`is_template: true`). Licence `NOASSERTION`. Only the 2 core agents extracted this round; the 26 skills are sampled, not exhaustive — 26 × the measured ~113k tokens/file is the shape that produced #118's estimate. Pinned `34a52ce0`. |
| 83 | [Jaan-Mustafa/10x-Team](https://github.com/Jaan-Mustafa/10x-Team) | repo | T1 | prose | **`scope = study`. A WORKED 13-ROLE ROSTER — the closest direct comparator to the roster this repo is designing.** `skills/{cto,principal-architect,staff-engineer,senior-engineer,sde,sre,dba,devops-engineer,qa-engineer,security-engineer,product-manager,engineering-manager}/SKILL.md` plus a dispatching `skills/10x-team/SKILL.md` and `AGENTS.md`. MIT, 11 stars, 168 KB — the cheapest high-value source of the batch. Note it ships a `.cursor-plugin/plugin.json`, i.e. it targets Cursor as well. Pinned `ea01f826`. |
| 84 | [felixgeelhaar/cclint](https://github.com/felixgeelhaar/cclint) | repo | T1 | pinned | **`scope = study`. A peer VALIDATOR, and it settled a live disagreement within minutes of being pinned** (Ray added it 2026-08-06). Lints the files Claude Code reads — `CLAUDE.md`, skills, **subagents**, hooks — flagging stale/invalid subagent model IDs, unresolved `@path` imports, circular imports, dangerous bash, duplicate monorepo content, and vague instructions. MIT, TypeScript, 10 stars, npm `@felixgeelhaar/cclint`. **Its `src/rules/data/claude-models.ts:28` reads `MODEL_FAMILIES = ['opus','sonnet','haiku','fable']`** — which is how we learned agnix 0.40.0's rejection of `model: fable` was agnix being stale, not the docs being wrong. Control arm: the same grep finds `opus` in the same file. Pinned `da801da4`. |
| 85 | [seojoonkim/agentlinter](https://github.com/seojoonkim/agentlinter) | repo | T2 | pinned | **`scope = study`. "ESLint for AI Agents" — 8 scoring dimensions over a whole agent workspace, with auto-fix.** 77 stars, TypeScript, 1.5 MB. ⚠️ **NO LICENCE DECLARED** and **last pushed 2026-04-20** — 3½ months stale, which for a linter whose job is knowing the current frontmatter surface means it predates `effort`, `isolation`, `memory` and the `fable` alias. Expect its SCHEMA checks to be behind agnix; its SCORING DIMENSIONS are the part worth reading, because a rubric does not age the way a schema does. Pinned `e3ee53eb`. |
| 86 | [datasciencedojo — Fable 5 as Orchestrator](https://datasciencedojo.com/blog/claude-code-fable-5-orchestrator-workflow/) | article | T1 | prose | Fable-5-as-orchestrator with cheaper executor subagents; the concrete 10-minute setup, the two subagents, effort-level guidance, and $/MTok per tier. **Fetched losslessly via `mise run kb-fetch`** (trafilatura, 8,798 chars, roundtrip 11 tokens sampled / 0 missing) → `sources/media/`. ⚠️ **`kb-add` would have mangled this one worst of the four**: its mega-menu and case-study cards markdownify to 8,514 chars BEFORE the article starts, so 71% of graphify's 12,000-char budget goes to navigation and only **30.8%** of the body survives (#200). No `llms.txt`, no AMP, no print view — DSD's `/amp/` and `/llms.txt` both return **200 and mean absent** (soft-404 to the homepage), which is why the control arm mattered. |
| 87 | [mindstudio — Fable 5 vs Sonnet 5 for dynamic workflows](https://www.mindstudio.ai/blog/claude-fable-5-vs-sonnet-5-dynamic-workflows-cost) | article | T1 | prose | Model-selection economics for dynamic workflows: cost, quality, and the decision rules for when to switch tiers. Fetched losslessly (19,013 chars, 38 tokens sampled / 0 missing); `kb-add` would have discarded **7,013 chars (37%)**. |
| 88 | [mindstudio — Advisor-Executor: plan with Fable 5, build with Sonnet](https://www.mindstudio.ai/blog/advisor-executor-pattern-fable-5-sonnet-model-routing) | article | T1 | prose | The routing criteria and the handoff-artifact shape for the advisor/executor split. Fetched losslessly (19,296 chars, 24 tokens sampled / 0 missing); `kb-add` would have discarded **7,296 chars (38%)**. Companion to #10, which is the same pattern applied to Claude Code specifically. |
| 89 | [hynek/structlog](https://github.com/hynek/structlog) | repo | T2 | code | **§2 R1/R2/R3 — the leading structured-logging candidate.** R10 **PASS**, last commit 2026-08-06. The parallel dotfiles session's D20 recommends it *as an event layer only* — "structlog vs loguru is NOT the axis", because structlog produces an event dict and hands off, while stdlib owns the sink layer via `ProcessorFormatter` + `QueueHandler`/`QueueListener`. Ingested so that framing is testable here rather than inherited. |
| 90 | [Delgan/loguru](https://github.com/Delgan/loguru) | repo | T2 | code | **§2 R1 — the complete-system alternative** (own sinks, single API). **R10 SCREEN FAIL**: last commit 2026-06-13, 57 days at measurement (2026-08-09). Ingested anyway on Ray's ruling — AST extraction is free, so a rejected candidate stays *citable* and "why not loguru?" is a query rather than an assertion. Default branch is `master` (see #262). |
| 91 | [getlogbook/logbook](https://github.com/getlogbook/logbook) | repo | T2 | code | **§2 R1/R3 — surfaced by the parallel dotfiles session, missed by this repo's own sweep.** Their ledger calls it *"alive, real handler-stack model — under-considered"*. Independently R10 **PASS**, last commit 2026-08-05. The handler-stack model is a third architecture distinct from structlog's processors and loguru's sinks. This row is R11 paying for itself. |
| 92 | [microsoft/picologging](https://github.com/microsoft/picologging) | repo | T2 | code | **§2 R1/R8 — the mature-looking C++ option, and it is dead.** **R10 SCREEN FAIL by all three routes**: last commit on `main` 2025-06-17, latest release 0.9.4 / 2024-09-13. ⚠️ Its `pushed_at` reads **2026-04-24** and is the *wrong instrument* — it counts any branch, so it shows ten months of life that never reached the default branch. Ingested so the dead end is citable instead of re-litigated. |
| 93 | [muhammad-fiaz/logly](https://github.com/muhammad-fiaz/logly) | repo | T2 | code | **§2 R8 — a live Rust-backed Python logging library.** R10 **PASS**, last commit 2026-08-07. ⚠️ Maturity caveat: PyPI **0.2.2**, 379 stars. ⭐ **Found only after re-sorting the GitHub search by stars** — `sort=updated` buried it under ★0–2 hobby repos and nearly produced a false "no Rust-backed option exists". The dotfiles session's PyPI-name-guessing route never surfaced it at all. |
| 94 | [Indosaram/logxide](https://github.com/Indosaram/logxide) | repo | T2 | code | **§2 R8 — the second live Rust-backed option**, "13x faster Python logging, stdlib-compatible". R10 **PASS**, last commit 2026-07-14 (26 days — near the threshold, stated so the judgement is checkable). 35 stars. Same discovery caveat as #93. |
| 95 | [koxudaxi/datamodel-code-generator](https://github.com/koxudaxi/datamodel-code-generator) | repo | T2 | code | **§2 R6 — the named source of truth for generated models.** R10 **PASS**, last commit 2026-08-06. ⚠️ `git log -S datamodel --all` → **0** hits in this repo's history (control: 361 for `graphify`), so R6 is **adoption, not restoration**. The dotfiles session reports it silently drops `unevaluatedProperties: false` for `msgspec.Struct` output while `--extra-fields forbid` works for pydantic — refuting or confirming that is R11 work and needs this source in the graph. **39,520 nodes / 69,950 edges** on ingestion. |
| 96 | [jcrist/msgspec](https://github.com/jcrist/msgspec) | repo | T2 | code | **§2 R7 — C-backed serialisation plus `Struct` models.** R10 **PASS**, last commit 2026-07-20. The target of the `datamodel-code-generator` extra-fields gap in #95, and the subject of 65 mentions in the dotfiles ledger. Also carries the known `pathlib.Path` cost: no support in either direction, needing a non-global `dec_hook`+`enc_hook` that threads through every call site — a direct charge against R7 for a `Path`-saturated codebase. |
| 97 | [ijl/orjson](https://github.com/ijl/orjson) | repo | T2 | code | **§2 R7/R8 — Rust-backed JSON, and the proof R8 is satisfiable on the serialisation side.** **R10 SCREEN FAIL**: last commit 2026-05-06, 95 days. Ingested because low churn reads as maturity for a serialiser rather than abandonment — the date is stated so a reader can disagree with that reading. Default branch is `master` (#262). |
| 98 | [pytest-dev/pytest](https://github.com/pytest-dev/pytest) | repo | T2 | code | **§2 R12 (Ray's twelfth requirement, "parallel python pytest and related sources") — the base framework.** R10 **PASS**, last commit 2026-08-09. Kept `kind = code` at 41 MB: proportionate, and the plugin/hook *source* is the R12 question. Contrast #101. |
| 99 | [pytest-dev/pytest-xdist](https://github.com/pytest-dev/pytest-xdist) | repo | T2 | code | **§2 R12 — the process-parallel axis.** R10 **PASS**, last commit 2026-08-03. Why it belongs with the logging program rather than beside it: under `-n auto` every worker is a separate process writing to one stdout, so today's 414 direct `print` sites interleave and R9's "review the logs for warnings that might be silently skipped" becomes unanswerable. R12 is a **constraint on R1/R3's sink design**. Default branch is `master` (#262). |
| 100 | [Quansight-Labs/pytest-run-parallel](https://github.com/Quansight-Labs/pytest-run-parallel) | repo | T2 | code | **§2 R12 — the thread-parallel axis, which xdist does not cover.** R10 **PASS**, last commit 2026-08-04. Free-threaded Python means a *shared* process, so the thread-safety of any logging handler is live rather than sidestepped by process isolation. ⚠️ It lives under **`Quansight-Labs`**, not `pytest-dev` — the natural guess 404s. |
| 101 | [pydantic/pydantic](https://github.com/pydantic/pydantic) | repo | T1 | **deferred → docs** | **§2 R6 — deliberately NOT pinned `kind = code`.** R10 **PASS** (last commit 2026-08-09) and it is `datamodel-code-generator`'s default output target, so R6 is not fully answerable without it — but what R6 needs is pydantic's **contract**, not its validator internals, which is why the deferral is to a `kind = docs` mirror rather than a drop. At **430 MB it is 2.3× `ruff` (185 MB)**, the repo the warning below this table is written about. Ray's ruling: defer to a `kind = docs` mirror in the docs PR, alongside the 3–4 libraries that survive R1/R7 screening. Prose extraction is the only LLM path in this corpus, so it is spent on winners, not on all thirteen candidates. |
| 102 | [anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python) | repo | T2 | candidate | **§2 R5 — the primary evidence for the typed-error-surface question.** R10 **PASS**, last commit on the default branch 2026-08-07 (`009b035305e0`, read via shallow clone; not pinned). Its `_exceptions.py` is the shape R5's phase 2 recommends — an exception hierarchy carrying the code as a class attribute — and it is the *counter*-example to R5's wording: **0 `from enum import` across 1,097 `.py` files** (control: 939 match `class `, 748 match `Literal[`). See `docs/research/reports/2026-08-09-r5-typed-error-surface.md`. |
| 103 | [pallets/click](https://github.com/pallets/click) | repo | T2 | candidate | **§2 R5 — the origin of this repo's undeclared `rc 2 = usage error`.** R10 **PASS**, last commit 2026-08-09 (`9c4dfdaebe0e`). `ClickException.exit_code = 1` / `UsageError.exit_code = 2` as `ClassVar[int]` on the exception class. Small, stable, and the CLI-conventions half of R5 that the SDK sources do not cover. |
| 104 | [openai/openai-python](https://github.com/openai/openai-python) | repo | T3 | **not recommended** | Read for R5 as a second route to #102 and found to be **the same Stainless generator** — `_exceptions.py` agrees line for line, `status_code: Literal[400] = 400` included. Recorded so a future session does not spend the ingestion believing it is independent corroboration; it is one decision counted twice. R10 PASS (2026-08-04, `0c09a3fe8151`) but that is not the reason to skip it. |
| 105 | [encode/httpx](https://github.com/encode/httpx) | repo | T3 | deferred | **§2 R5 — the no-codes-at-all end of the design range** (a pure exception hierarchy, `httpx/_exceptions.py`). **R10 SCREEN FAIL**: last commit 2026-02-23 (`b5addb64f016`), 167 days. Deferred rather than dropped — it is already present in the corpus *as a graphify worked example* (`graphify/worked/httpx/review.md`), which is a different artifact from its source and should not be mistaken for it. |
| 106 | [DopplerHQ/cli](https://github.com/DopplerHQ/cli) + [official Doppler docs](https://docs.doppler.com/llms.txt) | repo + docs | T1 | offline | **Critical secret-delivery dependency.** Exact CLI 3.76.1 is pinned in `mise.toml`, `currency.toml`, and `sources/doppler.manifest`. Eleven official Markdown sources are stored losslessly with per-page SHA-256/character receipts in `sources/doppler-docs.pages.toml`; the 38,448-character `llms.txt` index proves the direct Graphify URL path would discard 69%, so these offline files are the semantic-extraction inputs. AST and semantic extraction are deliberately pending until the next scoped Graphify build/extraction run; registration is not misreported as graph coverage. |
| 107 | [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — 5 secret docs, vendored | docs (vendored) | T1 | **partial — 5 of 449 .md** | **The sibling repo that OWNS credential management, and had never been ingested** despite consuming `kb_setup` as a SHA-pinned git dependency. Armed 2026-08-21: `fnox` → **0** nodes in the prose graph against a **955**-node `graphify` control, so a session asking "how do I add a secret?" got nothing. Not a `sources/*.manifest`: `kind` is `code`\|`docs` **whole-repo with no subpath scoping** (`python/src/kb_setup/manifest.py:82`), and dotfiles is 449 `.md` — `code` skips every one of them, `docs` is a ~449-file semantic extraction. So the files this repo actually needs are vendored at commit `6c9c5273df89` as `sources/media/dotfiles-secrets-{guide,rule,evidence,decision,takeover-spec}.md` (**5 files, 2,446 lines, re-derived 2026-08-22**). dotfiles is PUBLIC and the docs hold no values by their own contract (gitleaks clean on all five, re-scanned 2026-08-22). The remaining 444 `.md` and 146 `.py` stay un-ingested — a real gap, deliberately not paid for here. ⚠️ **Every count in this cell is invalidated by the next commit that vendors a file, and three of them already were**: this row said "3 of 449 / 446 remaining / 1,355 lines" while five files were committed on the same branch, and the cold lane on `870c020c` is what noticed. Re-derive with `ls sources/media/dotfiles-secrets-*.md | wc -l` before citing. ⚠️ **Bare `#N` in these files is another repo's tracker** (dotfiles or macos-development-environment), and this corpus's own #418/#432/#441 exist and are unrelated; not derivable which, so each file carries an `issue_refs` AMBIGUOUS caveat in its frontmatter. See `docs/secrets.md`. |
| 108 | [repowise-dev/repowise](https://github.com/repowise-dev/repowise) — hosted MCP at `api.repowise.dev` | repo + tool | T2 | **tool — MCP registered, source NOT ingested** | **The code-health bot that posts the advisory check on every PR here, reachable as an MCP since 2026-08-22.** Registered project-scoped in `.mcp.json` with `"Authorization": "Bearer ${REPOWISE_KNOWLEDGE_BASE_API_KEY}"` — **never the literal**; the key is in Claude Code's own process env (armed: key PRESENT, `HOME` PRESENT, bogus name ABSENT, in both the tool env and `zsh -ic`), which is the env `.mcp.json` expansion actually reads. Server `repowise 0.17.1`, protocolVersion **`2025-03-26`**, stateless (no `Mcp-Session-Id`), **10 read-only tools**. ⚠️ **Registered rather than reached via `mcp2cli`, deliberately** (`research-doc-sources.md` prefers mcp2cli): **mcp2cli 3.6.0 cannot negotiate with this server** — `--transport auto` sends a GET and gets 405, `--transport streamable` fails on version negotiation because the server advertises an older protocol than mcp2cli offers. The cheap arm of the chain is therefore unavailable, the working path is a hand-built JSON-RPC POST, and the surface is needed once per PR — which is the "register when frequent" branch. ⚠️ **The 405 is a TRANSPORT artifact, not an auth failure** — the same URL and bearer return 200 to a POST; do not read it as "key wrong" or "endpoint dead". Auth arms: real bearer → **200**, no header → **401 `Missing authorization header`**, garbage bearer → **401 `Invalid or revoked API key`** — so an unexpanded `${VAR}` (which Claude Code passes through as-is, warning only in `claude mcp list`) fails as *Invalid or revoked API key*, not as a missing variable. ⚠️ **`get_security` is PAYWALLED** (`state: upgrade_required`, `required_tier: pro`) — dependency CVEs, secret detection and SBOM are unreadable on the current plan, and the tool instructs the caller to say so rather than retry. **The source repo is a live ingestion candidate and is deliberately NOT pinned here**: Python, **113 MB**, 6,153 stars, pushed 2026-08-22 (measured) — bigger than `ruff` (185 MB) is the wrong comparison, but it is well past the "small and stable" bar, and prose extraction is spent on winners. |
| 109 | hosted graphify MCP at `api.graphify.com/mcp` (Ray's `ray-manaloto` workspace, Pro) | tool | — | **tool — MCP registered, INTERIM, exit condition unmet** | **Registered in `.mcp.json` since `98b116fd` (2026-08-15) as scaffolding, because `kb-build` fails closed and the repo had no queryable graph.** It is **NOT** `mise run kb-serve` and does **NOT** serve this corpus: `list_repositories` (re-measured 2026-08-22) returns a workspace of **TWO** repos — `ray-manaloto/knowledge-base` (10,497 nodes) and `ray-manaloto/dotfiles` (7,776) — both `queryable: true`, indexed from `main`. **23 tools** load as `mcp__graphify__*`. OAuth on first use, **no key in the file**. ⚠️ **Its exit condition is HALF MET** (`docs/graphify-reference.md`): `mise run kb-query` exits 0 ✓, but "a freshly built graph" ✗ — `graphify-out/.currency-stamp.json` is absent and `.build-failure.json` records `stage: build` failing 2026-08-21T17:56:05Z. Blocker is **#397/#417**, not #289 (which `5308c69c` cleared and which is **still OPEN** — control-armed against #242, whose timeline returns `closed 2026-08-08`). ⚠️ **This row exists because `currency.toml` CANNOT hold it**, and that was armed rather than assumed: all three admissible shapes are refused — a row with no `owners`/`expected`/`source_only` raises, `source_only` without a `manifest` raises, and an `expected` row reports permanent **false DRIFT** *"…is not installed on this host"* because `spec.binary` defaults to the tool NAME and `shutil.which` misses it (control: the same call on `claude`, a real binary, reaches a `version` finding instead — so the probe discriminates). A permanent false drift is worse than no row: it trains a reader to ignore the line. ⚠️ **The server version is NOT observable here** — `claude mcp get` prints none, and the control proves that is a probe bound, not a fact: it prints none for `repowise` either, whose version *is* known (0.17.1, via a hand-built `initialize`). graphify's is OAuth, so reading it would mean touching Claude Code's token store. **Keep-and-track ruled by Ray 2026-08-22; whether to keep it at all is #450**, which also carries the tension with his 2026-08-02 directive (*"integrating the graphify python library instead of the graphify cli/mcp"*). |
| 110 | [platform.claude — PTC cookbook](https://platform.claude.com/cookbook/tool-use-programmatic-tool-calling-ptc) | docs | T1 | pending | The worked-example half of row 48, which holds the concept doc only. Named by Ray 2026-08-23 in the U9 set. ⚠️ **Ingestion is gated on `kb-build` being green** (#397/#417) — a manifest cannot reach the graph while the build fails closed, so this stays a backlog row until U0 lands. ⚠️ **Truncation is the live hazard here, not a hypothetical**: row 47 records a fetch that returned a table of contents and looked like a successful ingestion. Check length and section count against the live page before merge, then `mise run kb-validate-chunks` — a chunk that parses is not a chunk that captured anything. |
| 111 | [daly2211/open-ptc](https://github.com/daly2211/open-ptc) | repo | T2 | pending | **The only CODE source of the five Ray named**, so it is `mise run kb-manifest-add` + free AST extraction — no LLM, no cost. An open implementation of programmatic tool calling, which is the mechanism behind row 48's claimed 20–40% token reduction. Same U0 gate as row 110: registering the manifest makes it a build input, so it waits. |
| 112 | [anthropic.com/engineering/advanced-tool-use](https://www.anthropic.com/engineering/advanced-tool-use) | article | T1 | pending | Named by Ray 2026-08-23. Sits directly on his standing *"reduce agent token usage"* theme and feeds the session-review `telemetry` lane's brief, which asks which repeated sequence should become a task. Same truncation arm as row 110 — `anthropic.com` engineering posts have previously come back as a nav shell (rows 57–59 all needed a second fetch route). |
| 113 | [platform.claude — reproduce agentic-search benchmarks](https://platform.claude.com/cookbook/evals-agentic-search-reproduce-agentic-search-benchmarks) | docs | T1 | pending | Named by Ray 2026-08-23. An evals recipe for agentic search — the closest external reference this corpus has to its own retrieval-quality question (`kb-query --prose --idf` measured at 1/8 → 3/8 → 5/8 natural recall). Same U0 gate and same truncation arm. |
| 114 | [xt765/mermaid-trace](https://github.com/xt765/mermaid-trace) | repo | T2 | manifest | **2026-08-26 tool-funnel pin (1 of 8).** RUN-OK: the `@trace` decorator produced a real `sequenceDiagram`, 6 participants / 10 lines, 0.02s wall clock. Quoted verbatim: *"No elimination — this is the shape the diagram-gen report's Ranked Recommendation section treats as viable evidence, not rejected."* `kb-build` is currently FAILING (#397/#417 detect-preflight) — this is a pin only; Status stays `manifest`, never `code`, until a build succeeds. Verdict source: `.agent/kb/reports/agents/diagram-tool-status-2026-08-26.md`. |
| 115 | [getappmap/appmap-python](https://github.com/getappmap/appmap-python) (+ companion [getappmap/appmap-js](https://github.com/getappmap/appmap-js), not pinned) | repo | T2 | manifest | **2026-08-26 tool-funnel pin (2 of 8).** Default branch is `master`, not `main`. EVALUATED-ONLY, never run. Quoted verbatim: *"the most serious engineering and the only live project, but it is config-driven not annotation-driven, needs a Node toolchain beside Python, and its natural unit is 'one diagram per test' — the largest adoption cost by far."* No Mermaid output. `kb-build` is currently FAILING — pin only, Status `manifest` not `code`. |
| 116 | [mkdocstrings/griffe](https://github.com/mkdocstrings/griffe) | repo | T2 | manifest | **2026-08-26 tool-funnel pin (3 of 8).** Not a diagram tool — static API-surface diffing (`griffe check ... -a <ref>`). Quoted verbatim: *"Recommend it, but as a separate ticket, not as part of the diagram work."* Proposed pin `griffe==2.2.0` confirmed NOT present in `pyproject.toml`. `kb-build` is currently FAILING — pin only, Status `manifest` not `code`. |
| 117 | [mitmproxy/pdoc](https://github.com/mitmproxy/pdoc) | repo | T2 | manifest | **2026-08-26 tool-funnel pin (4 of 8).** No diagrams produced by design — a docstring renderer, recommended for the separate documentation-generation ask (U10 in `docs/plans/2026-08-23-directive-execution-plan.md`), never run. `kb-build` is currently FAILING — pin only, Status `manifest` not `code`. |
| 118 | [sverweij/dependency-cruiser](https://github.com/sverweij/dependency-cruiser) | repo | T2 | manifest | **2026-08-26 tool-funnel pin (5 of 8).** EVALUATED-ONLY, never run. Quoted verbatim: *"Best-designed gate in the whole survey"* but *"no — **JS/TS only**. Right tool for `.claude/workflows/*.js`, irrelevant to the four pipelines."* `kb-build` is currently FAILING — pin only, Status `manifest` not `code`. |
| 119 | [ast-grep/ast-grep](https://github.com/ast-grep/ast-grep) | repo | T2 | manifest | **2026-08-26 tool-funnel pin (6 of 8).** PENDING — named only as *"the maintained tree-sitter-based tool if that layer is ever wanted"*; never itself evaluated as a diagram generator. `kb-build` is currently FAILING — pin only, Status `manifest` not `code`. |
| 120 | [Technologicat/pyan](https://github.com/Technologicat/pyan) | repo | T2 | manifest | **2026-08-26 tool-funnel pin (7 of 8).** Default branch is `master`, not `main`. Pushed 2026-08-22, so LIVE (corrects an older "dormant" reading). Quoted verbatim: *"REJECT: pydeps / pyan3 / py2puml — all alive-enough, all strict subsets of graphify's existing python edges."* Eliminated as a diagram source, but its call resolution is the exact capability graphify's own measured gap (`_build_checked` missing from `.self-graph`) is about — pinned so that comparison is queryable later. `kb-build` is currently FAILING — pin only, Status `manifest` not `code`. |
| 121 | [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) (`sources/graphify.manifest`) | repo | T2 | manifest | **Catch-up row — the manifest predates this row.** This repo's core fork has been pinned since the earliest ingestion wave but never had its own `REGISTRY.md` line (2026-08-26 funnel inventory, independently re-verified this session: 0 grep hits for `ray-manaloto/graphify` anywhere in this file). Also folds in two 2026-08-26 diagram-survey findings ABOUT graphify itself, both PROTOTYPED: the `graph.json` self-graph adapter ("Shape C") works (7,054 nodes, 4,364 `calls` edges, 7.5s) but exposes a real extraction gap — `_build_checked` *"is not a node in `.self-graph` at all"*, a genuine miss, not staleness; and `export callflow-html` (the CLI's own native diagram exporter) is PENDING — *"It has never been run here."* See `sources/graphify.manifest` for the fork's own pin history. |
| 122 | [astral-sh/ty](https://github.com/astral-sh/ty) (`sources/ty.manifest`) | repo | T2 | manifest | **Catch-up row — the manifest predates this row.** Pinned 2026-08-02 as a toolchain source (#81) but never had its own `REGISTRY.md` line (2026-08-26 funnel inventory, independently re-verified this session: 0 grep hits for `astral-sh/ty` anywhere in this file). **2026-08-26 update:** the diagram survey's own PENDING verdict — *"never named or evaluated in any of the four reports… would likely generalize, but that is an inference, not a measurement"* — is OVERTURNED by the gap sweep: GitHub issue **#276** (open, created 2026-08-11, six days before the diagram directive) names `ty` LSP explicitly with a full pipeline design and 12 acceptance criteria, quoted verbatim: *"neither consumes `ty` language-server navigation results. Consequently, current impact analysis cannot distinguish what Graphify knows from definition/reference/call-hierarchy evidence that only a type-aware language server can provide."* Never connected to the 2026-08-24 diagram bake-off. See `sources/ty.manifest` for the pin-invariant history. |
| 123 | [scottrogowski/code2flow](https://github.com/scottrogowski/code2flow) | repo | — | not recommended | **2026-08-26 tool funnel.** RUN-OK — real mermaid output on disk (1,313 nodes / 1,978 edges, rc=0), but adoption rejected. Quoted verbatim: *"documentation.js (2024-01-30) / code2flow (2023-01-08) / madge (2024-08-05) — dormant."* Also 51 unresolved lazy-import call sites, and cannot see `_build_checked → graph.build()` at all. Not one of the eight pinned (dormant tool, code irrelevant per the pin criterion). Verdict source: `.agent/kb/reports/agents/diagram-tool-status-2026-08-26.md`. |
| 124 | [lucsorel/py2puml](https://github.com/lucsorel/py2puml) | repo | — | not recommended | **2026-08-26 tool funnel.** RUN-FAIL on the real target — 7 separate runs against real `kb_setup`, every one `rc=1`, `ValueError: Could not resolve type T` (the resolver cannot follow `TypeVar`/generics). Succeeds only on toy fixtures. Also the wrong diagram kind (274 classes vs 1,307 functions). Not pinned. |
| 125 | [brijeshkulkarni/sequenceDiagram](https://github.com/brijeshkulkarni/sequenceDiagram) (both the unpatched package and a hand-patched fork of it) | repo | — | not recommended | **2026-08-26 tool funnel. 0-byte LICENSE — a record and no clone**, per this round's own rule: legally unusable in this repo regardless of quality. Quoted verbatim: *"**Verdict: name Ray's memory as confirmed, then disqualify it. Do not adopt.**"* Unpatched: crashes on numeric args, `resetseq()` is a no-op, wrong participant names. A hand-patched fork DOES produce a real `sequenceDiagram` HTML (941 B, rc=0) against this repo's own types, but quoted verbatim: *"it does not fix the 0-byte-license blocker … which is independent of the bug"*. No manifest. |
| 126 | [lucsorel/pydoctrace](https://github.com/lucsorel/pydoctrace) | repo | — | candidate | **2026-08-26 tool funnel.** RUN-OK — *"rc=0. Both diagrams written."* on py3.14.7 (PlantUML sequence + component), but artifacts landed outside both checked evidence dirs. Last release 0.3.0 (2024-02-27); 0 non-bot commits since 2026-02-24. No loop folding — a function called twice produces two full duplicate sequence blocks. Not one of the eight pinned. |
| 127 | [pylint-dev/pylint](https://github.com/pylint-dev/pylint) (ships `pyreverse`) | repo | — | candidate | **2026-08-26 tool funnel.** EVALUATED-ONLY, never run. Quoted verbatim: *"274 classes vs 1,307 functions means it draws the wrong layer of this codebase. Do not make it the answer to Ray's ask."* Proposed pin `pylint==4.0.7` confirmed NOT applied. Not one of the eight pinned. |
| 128 | `pylint-pyreverse` — UNKNOWN, PyPI name only, no repository URL stated in either source report | tool | — | not recommended | **2026-08-26 tool funnel.** Quoted verbatim: *"`pylint-pyreverse` on PyPI is a **squatted 0.0.0 stub** from 2023-04-04 with an empty summary. Do not pin it."* Not the same package as row 127's `pyreverse`-in-`pylint` — easy to confuse. No URL guessed, per `probes-need-a-control-arm.md`. |
| 129 | `pydeps` — UNKNOWN, PyPI name only, no repository URL stated in either source report | tool | — | not recommended | **2026-08-26 tool funnel.** Quoted verbatim: *"**REJECT: pydeps / pyan3 / py2puml** — all alive-enough, all strict subsets of graphify's existing python edges."* No URL guessed. |
| 130 | `mkdocstrings-python` — UNKNOWN, PyPI name only, no repository URL stated in either source report | tool | — | candidate | **2026-08-26 tool funnel.** EVALUATED-ONLY: *"no diagrams… no"*. Noted as `pdoc`'s (row 117) griffe-backed drop-in fallback. Never run. No URL guessed. |
| 131 | `Sphinx` — UNKNOWN, PyPI name only, no repository URL stated in either source report | tool | — | candidate | **2026-08-26 tool funnel.** Quoted verbatim: *"Sphinx/mkdocstrings — docstring rendering, not topology."* Never run. No URL guessed. |
| 132 | [mingrammer/diagrams](https://github.com/mingrammer/diagrams) | repo | — | not recommended | **2026-08-26 tool funnel.** Quoted verbatim: *"**REJECT: diagrams/mingrammer** (hand-authored — derives nothing)."* Not pinned. |
| 133 | `erdantic` — UNKNOWN, PyPI name only, no repository URL stated in either source report | tool | — | candidate | **2026-08-26 tool funnel.** Wrong diagram kind (ER diagrams from pydantic/attrs models only), "low" maintenance. Not in the report's explicit REJECT list; never run. No URL guessed. |
| 134 | `PlantUML` — UNKNOWN, no repository URL stated in either source report | tool | — | not recommended | **2026-08-26 tool funnel.** Quoted verbatim: *"**REJECT** … **PlantUML** (JVM)."* No URL guessed. |
| 135 | [terrastruct/d2](https://github.com/terrastruct/d2) | repo | — | not recommended | **2026-08-26 tool funnel.** Quoted verbatim: *"**D2** (third format, no new capability)."* Not pinned. |
| 136 | `Structurizr` / `Structurizr CLI` — UNKNOWN, no repository URL stated in either source report | tool | — | not recommended | **2026-08-26 tool funnel.** Quoted verbatim: *"**Structurizr** (archived + hand-authored)."* U10 adds: *"Structurizr CLI — ARCHIVED 2026-02-01, JVM, and hand-authored rather than code-derived."* No URL guessed. |
| 137 | [tree-sitter/tree-sitter-graph](https://github.com/tree-sitter/tree-sitter-graph) | repo | — | not recommended | **2026-08-26 tool funnel — the tool Ray explicitly named.** Quoted verbatim: *"**Verdict: REJECT.**"* Last push 2024-12-11 (~20.5mo dormant); its consumer [github/stack-graphs](https://github.com/github/stack-graphs) (row 150) is **archived**; **no PyPI distribution** (404, control `tree-sitter`→200); Rust-only; no renderer; and *"the layer tree-sitter-graph occupies is the layer graphify already occupies in this repo."* Not pinned. |
| 138 | LSP call-hierarchy (`pylsp` / `pyright`, generic category — explicitly NOT `ty`) — UNKNOWN, no single repository named | tool | — | not recommended | **2026-08-26 tool funnel.** Quoted verbatim: *"**REJECT: LSP call-hierarchy** (python-only, needs a live server, strictly weaker than the AST graph we own)."* See row 122, which the gap sweep separately overturns to NAMED-NEVER-EVALUATED for `ty` specifically via issue #276. No URL guessed — this is a category, not one repo. |
| 139 | [CodeBoarding/CodeBoarding](https://github.com/CodeBoarding/CodeBoarding) | repo | — | not recommended | **2026-08-26 tool funnel.** Quoted verbatim: *"CodeBoarding — LLM-in-the-loop, collides with `do-not.md` #4"* — this repo's hard ban on any non-Claude LLM backend. Not pinned. |
| 140 | `Doxygen` — UNKNOWN, no repository URL stated in either source report | tool | — | not recommended | **2026-08-26 tool funnel.** Quoted verbatim: *"Doxygen — with `\"\"\"` docstrings **none of its special commands work and text renders verbatim** unless every docstring is rewritten (`doc/docblocks.dox`)."* No URL guessed. |
| 141 | `documentation.js` — UNKNOWN, no repository URL stated in either source report | tool | — | not recommended | **2026-08-26 tool funnel.** Quoted verbatim: *"documentation.js (2024-01-30) / code2flow (2023-01-08) / madge (2024-08-05) — dormant."* No URL guessed. |
| 142 | `madge` — UNKNOWN, no repository URL stated in either source report | tool | — | not recommended | **2026-08-26 tool funnel.** Same dormant-group quote as row 141. No URL guessed. |
| 143 | SCIP (SourceGraph code-intel protocol) — UNKNOWN, no repository URL stated; a protocol/spec, not one repo | tool | — | candidate | **2026-08-26 tool funnel.** Named twice from two independent angles (U10 and issue #276). Quoted verbatim: *"SCIP is technically the richest source … but you would write the renderer."* Not rejected, not adopted. No URL guessed. |
| 144 | `graphviz` / `dot` — UNKNOWN, no repository URL stated; a system-package render backend | tool | — | candidate | **2026-08-26 tool funnel.** Quoted verbatim: *"already installed at 16.0.0 and unpinned"*; recommended as the shared render target for `pyreverse` (row 127) / `dependency-cruiser` (row 118) / Doxygen (row 140) output. Confirmed still absent from `mise.toml` `[tools]` — this is a **mise pin action**, not a corpus source; no manifest is applicable. No URL guessed. |
| 145 | [pinetr2e/napkin](https://github.com/pinetr2e/napkin) | repo | — | not recommended | **2026-08-26 tool funnel.** Quoted verbatim: *"It never reads your production code. It is a nicer syntax for authoring PlantUML… **Zero automation value here.**"* Last commit 2021-07-18. Not pinned. |
| 146 | [Softoft-Orga/pdgen](https://github.com/Softoft-Orga/pdgen) | repo | — | not recommended | **2026-08-26 tool funnel.** Fails recency by ~3.5mo AND has a disqualifying silent-loss bug. Quoted verbatim: *"A module-level function decorated with `@include_in_uml` is silently dropped — no error, no diagram entry, just a wrapper."* Drops the majority of `kb_setup` (1,307 top-level functions vs 274 classes). Not pinned. |
| 147 | `kb_setup.diagrams` / `mise run kb-diagram` — n/a, internal to this repo, not an external source | tool | — | pending | **2026-08-26 tool funnel.** The survey's own **#1 Ranked Recommendation** — build it ourselves, quoted verbatim: *"adds ZERO new external dependencies."* Confirmed: *"no such module exists"* (`find python/src/kb_setup -iname '*diagram*'` → no hits) and no `kb-diagram` task. The `/tmp/diagram-proto/emit.py` bake-off spike is the closest prototype (four static-extraction layers, three depth adapters) but none of that spike code has been ported into `python/src/kb_setup/` or wired to a mise task. Recorded here — rather than left un-tracked — because it is the survey's own headline conclusion, not an external tool; n/a Kind/Tier reflect that. |
| 148 | `snakefood` — UNKNOWN, PyPI name only, no repository URL stated in either source report | tool | — | pending | **2026-08-26 tool funnel.** Zero mentions across all five checked sources (control-armed against `pyreverse`, 16 hits). Quoted verbatim: *"Named in the task's candidate list; never evaluated anywhere in this repo's research."* No URL guessed. |
| 149 | `erdify` / `mermaidx` / `mermaid-py` / `pymermaider` / `pumla` / `infigraph` / `ridge` / `ast-to-mermaid` / `projectmind` — nine breadth-sweep GitHub/PyPI discoveries, no repository URL stated for any of them | tool | — | pending | **2026-08-26 tool funnel — grouped honestly, one row for nine names, not nine rows.** Quoted verbatim: *"Metadata (stars, `pushed_at`, PyPI version) was fetched for triage, but none was installed or run against this codebase, and none reached a capability verdict beyond the metadata table."* None of the nine was installed, run, or evaluated beyond that triage metadata — this row is NOT nine evaluations. No URLs guessed. |
| 150 | [github/stack-graphs](https://github.com/github/stack-graphs) | repo | — | not recommended | **2026-08-26 tool funnel (gap-sweep delta D3).** Confirmed **archived** as tree-sitter-graph's (row 137) principal downstream consumer. Issue #276 separately frames it as an unevaluated fallback on its own merits, quoted verbatim: *"If such a gap exists, compare GitHub Stack Graphs and SCIP before writing a custom grammar or graph engine."* Archived status is the harder fact; not pinned. |
| 151 | `mermaid-cli` / `mmdc` — UNKNOWN repository URL stated in either source report; the gap sweep names only the mise/npm package `npm-mermaid-js-mermaid-cli` | tool | — | tool | **2026-08-26 tool funnel (gap-sweep delta D4).** Already `mise`-installed and in productive use as the render backend for this repo's existing `.mmd` → HTML pipeline (the same job `code2flow.html` / `graphify.html`, row 121, use). Quoted verbatim: *"it is a **render backend** … not a code→diagram extraction tool and was never evaluated as one."* Not a "pinned-but-unused" find — it IS used, just for a different job than this survey asked about. No URL guessed. |
| 152 | [chenrui333/codex-docs](https://github.com/chenrui333/codex-docs) | repo | T1 | manifest | **2026-08-29, in response to Ray's correction on the restored row 65 (`mrkhachaturov/agent-harness-docs`).** Community-maintained periodic mirror of OpenAI Codex CLI content, MIT, auto-synced every 6h via GitHub Actions (pinned `a7412e5e` at registration). Covers SIX categories row 65's `docs/codex/` does not: `developers.openai.com/codex/*` pages (the one category row 65 shares), Codex-related cookbook/resources pages, markdown mirrored from the `openai/codex` repo itself (README/CHANGELOG/`docs/*.md`/CLI-Rust docs), linked platform tool guides, CLI-materialized system skills, and a generated `docs/codex_capabilities.json` capability inventory. Row 65's Codex coverage is a confirmed STRICT SUBSET of this repo's for Codex specifically (verified by reading both READMEs live, 2026-08-29) — **decided (#605) as the replacement for row 65's Codex tier**: registered in `sources/codex-docs.manifest`; `sources/agent-harness-docs.manifest` now defers its `docs/codex/` extraction here. |

### Toolchain docs — the gap this registry did not show (2026-07-30)

Of the 26 `sources/*.manifest` pins, **only `graphify` is a tool this repo runs.** mise, hk,
fnox, uv, ruff, ty, pkl, taplo, rumdl, gitleaks, typos and agnix are all absent, which is why
`kb-currency` `curl`s release notes instead of querying the graph. Tracked as **#81** with the
full scan; suggested order is the jdx trio (mise/hk/fnox), then the astral trio (uv/ruff/ty).

**Do not pin them `kind = code`** — that AST-extracts the *source* and skips every `.md`, so it
misses the docs entirely while adding ruff's 176MB and uv's 183MB of AST to a graph already
crowding prose out of the query budget (#12). `kind = docs` is the path.


## Progress log

- **2026-08-07 — colibri pinned (local-LLM runtime).** `sources/colibri.manifest`
  → [JustVugg/colibri](https://github.com/JustVugg/colibri) at the **v1.5.0
  release** (`5e4b5c6a…`), `kind=code`, AST-only — free, no LLM, which is the
  point: Ray flagged *"we are burning too many tokens w the graphify agent
  work"*, and colibri runs models locally. Pinned to a release rather than
  `main` on Ray's instruction. The next session evaluates it against
  `/Users/rmanaloto/agy-graphify-research` before any of it is adopted; this pin
  only makes the code queryable in the meantime.
  **Caveat, filed as #235:** v1.5.0 is an **annotated** tag, so the recorded
  `commit` is the tag OBJECT, not the commit (`8f512fc8…`). Control-armed —
  fetch and checkout both rc=0 and HEAD peels correctly, so the pin works and is
  left as-is. **CORRECTED 2026-08-07:** the comparison path is fine — `latest_commit`
  passes the exact ref name, which returns only the tag-object line, so it compares
  tag-SHA to tag-SHA. #235's premise was refuted by measurement.

- **2026-08-07 — the local-LLM face-off gains its two Apple-native arms.**
  `sources/turbo-fieldfare.manifest` → [drumih/turbo-fieldfare](https://github.com/drumih/turbo-fieldfare)
  at release **0.4.1** (`417f3893…`), and `sources/nativ.manifest` →
  [Blaizzy/nativ](https://github.com/Blaizzy/nativ) at **v0.2.2** (`ab99cfa0…`).
  Both `kind=code`, AST-only — free, no LLM. Added by Ray to sit beside colibri
  in the local-LLM evaluation.
  **Why they are not redundant with colibri:** both are Swift and target Apple
  silicon directly (turbo-fieldfare runs Gemma 4 26B-A4B in ~2 GB of RAM on any
  M-series MacBook; nativ drives MLX models). colibri does not cover that axis —
  its `discover_gpus()` is NVIDIA→AMD only and returns `[]` on this M2 Max, and
  its `memory_available()` reports ~26 GB against 96 GB of real memory because it
  counts only reclaimable pages (both measured live, 2026-08-07; see
  `docs/research/reports/2026-08-07-colibri-hardware-preflight.md`).

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

## Backlog added 2026-09-01 — agentsview, the Codex half of session review

| # | Source | Kind | Tier | Status | Why it's here |
|---|---|---|---|---|---|
| 84 | [kenn-io/agentsview](https://github.com/kenn-io/agentsview) | repo | T2 | tool | Local session viewer that reads Claude Code AND Codex transcripts. **Installed and wired**, not ingested — see below. |

**Adopted 2026-09-01 (Ray).** Pinned in `mise.toml` as
`"github:kenn-io/agentsview" = "0.41.1"`; wrapped by `mise run kb-session-search`
(`kb_setup.agentsview`). It closes a measured gap: every existing session task
here reads `~/.claude/projects/` only, while this machine also holds **2,658**
files under `~/.codex/sessions/` and **978** archived — and since 2026-08-31
every lane in this repo runs on codex.

**Status is `tool`, NOT `manifest`, and that is a deliberate deferral.** A
`sources/agentsview.manifest` would make an already-failing `kb-build`
(`IncompleteGraphifyOperationError`, 2026-08-31T12:15Z) responsible for an
unmeasured new source, against a `graph-size` already at 736 MiB of 1,024.
`build = skip` was considered and REJECTED — #417 measured that exact shape
producing a stale clone that three readers then cited from the wrong version.
**Promote this row to `manifest` once `kb-build` is green**; the pin to use is
tag `v0.41.1` → commit `a902515a2f8256ffb95716a2ca860c1887d35da5`.

**The UI is deliberately un-wrapped.** `agentsview serve` starts a local web
browser UI; run it by hand. It is not a mise task because a server gives an
agent no bounded output and `long-running-command-hangs.md` rule 2 forbids
`&`-detaching a local `mise run`. `agentsview daemon stop` ends the background
daemon the search path autostarts.

**Two facts measured here that its own docs get wrong**, worth carrying because
the next reader will hit them:

1. **Only `usage daily` reads SQLite directly.** `session search`, `session
   list`, `stats`, `projects` and `health` all exit 1 with *"daemon autostart is
   disabled"* under `AGENTSVIEW_NO_DAEMON=1` — including `session list`, which
   the README annotates as *"read from the daemon if warm, otherwise SQLite"*.
2. **`open_issues_count` is not the issue count.** The REST field read **94** on
   2026-09-01; the issues-only search reads **71**, and there are **23** open
   PRs. Both numbers are right; only one of them is issues. Do not let either be
   "corrected" to the other without naming the field.

## Program notes

- **graphify-first**: ingest+extract into this KB **before** web search — graphify
  fetches the URL itself, so the graph is the primary research surface.
- **Fallback cluster** (#11–#14): the Fable-5 token-exhaustion → Opus-4.8 fallback
  behavior. Cross-read, don't trust a single source (control-arm the claim).
- **Reference docs already reviewed**: [Fable-5 prompt-engineering] is #3; keep the
  README/CLI as the command authority (the graph is the "how it works" layer).
- Wave 1 (get a queryable graph fast): #1–#9, #11–#14 code+prose. Wave 2: #15–#19.
  #20–#21 stay deferred.

## Backlog added 2026-08-27 — prior art on mechanized control arms

Surfaced by the `aggregated-research` skill's self-referential run
(`docs/research/reports/2026-08-27-aggregated-research-prior-art.md`, P3 of the
Aggregated round). All three are published agent prompts that mechanize a
negative control — the discipline `.claude/rules/probes-need-a-control-arm.md`
states in prose and `kb_setup.arms` implements. **Read once, not yet ingested.**

- <https://github.com/purpleailab/decepticon> — `validate_workspace_finding`
  requires a positive command AND an equivalent negative-control command before a
  finding is promoted. The closest published analogue to `kb-arms`.
- <https://github.com/cybersecurityup/neurosploit> — a false-positive filter agent
  whose method is "default to not a finding", per-class refutation, a
  negative-control re-test, and mandatory reproduction.
- <https://github.com/terrylica/cc-skills> — the `crucible` plugin's
  research-foundations skill: shuffled-null design (three null types chosen by
  hypothesis class) and agent significance corrections.

Two more repos were read only as that report's control arm and are **not**
proposed as sources: `jamie-bitflight/claude_skills`,
`alma-oss/spirit-design-system`.

## Backlog added 2026-08-27 — Claude↔Codex handoff doctrine

Surfaced by the `aggregated-research` skill's P4 run
(`docs/research/reports/2026-08-27-claude-codex-handoff.md`). **Read once, not yet
ingested.** They carry the doctrine the corpus does not have — the standing
finding is that this corpus indexes its dependencies and not its decisions.

- <https://github.com/pipeshub-ai/pipeshub-ai> — `docs/multi-agent-best-practices.md`,
  a synthesis of Anthropic's multi-agent guidance: decompose by context boundary
  rather than role type; typed contracts at every handoff; externalize large state
  to an artifact store and return a pointer plus summary.
- <https://github.com/shanraisshan/claude-code-best-practice> — the cross-model
  Claude+Codex workflow that reviews the PLAN against the codebase before
  implementation, inserting phases rather than rewriting them.
- <https://github.com/kryota-dev/actions> — ADR-006: the analysing agent holds no
  write access; a deterministic engine posts results.

Read only for figures or context and **not** proposed as sources:
`jgwill/miadi-orchestration-kit`, `rmusser01/tldw_server`.

## Backlog added 2026-08-27b — the plugin build's own sources

Surfaced while designing `aggregated-research` as a marketplace plugin
(`.agent/plans/session-2026-08-27-g.md`). **Read once, not yet ingested.**

Tools the plugin will wrap — each needs a prototype before a module is written:

- <https://github.com/lycheeverse/lychee> — link/citation-rot checker, Rust.
  Publishes its own **binary** to PyPI as `lychee-bin` 0.24.2, so it is
  `uv add`-able. `--format json` confirmed from source at tag `lychee-v0.24.2`
  (`lychee-bin/src/config/output.rs:16-23`). This repo has **551 unique external
  URLs** in tracked markdown and nothing checks any of them.
- <https://github.com/modelcontextprotocol/python-sdk> — the `mcp` PyPI package,
  2.1.1 (2026-08-25, re-derived as latest). The client for `mcp.grep.app`, which
  has **zero** Python packages of its own.
- [google/deps.dev](https://github.com/google/deps.dev) — keyless HTTP plus a
  published API v3 protobuf. The schema-only provenance pin and committed
  generator input landed for #575; `build = skip` keeps the Go repository out
  of ordinary corpus ingestion.
- [googleapis/googleapis](https://github.com/googleapis/googleapis) — canonical
  `google/api/annotations.proto` and `google/api/http.proto` dependencies for
  the deps.dev schema, pinned in `sources/deps-dev.manifest` comments for #575.
  Registered here rather than as another corpus-ingestion manifest.

Prior art for the two we would otherwise have written from scratch:

- <https://github.com/terrylica/cc-skills> — its `link-tools` plugin (★61, pushed
  2026-08-26) already wraps lychee as two Claude skills with a `config/lychee.toml`.
  Read before building ours.
- <https://github.com/jaredpalmer/claude-plugins> · <https://github.com/krmcbride/claude-plugins>
  — both wrap `grep.app` via its MCP.
- <https://github.com/anthropics/claude-plugins-official> — 289 plugins; the source
  of `plugin-dev`, and the marketplace-manifest reference implementation.

Read only as a control arm for the plugin-prior-art search and **not** proposed as
sources: `tarqd/skills`, `nq-rdl/agent-extensions`, `a5c-ai/babysitter`,
`liby/vibe-coding-plugins`.

### 2026-08-27 — the lychee-from-Python sweep (`docs/research/reports/2026-08-27-lychee-from-python.md`)

- <https://github.com/jb--/lychpy> — the only PyO3 binding for lychee-lib; pushed
  2023-09-26, "not ready for usage". T3 `deferred` — dead, kept as the negative result.
- <https://github.com/firecrawl/firecrawl-claude-plugin> — the `firecrawl-developer-index`
  and `firecrawl-search` skills; the developer index's three surfaces are documented there. T2.
- <https://github.com/firecrawl/cli> — `firecrawl developer <query>`, the passage-returning
  surface our connector lacks; pinned here as `npm:firecrawl-cli`. T2.
- <https://github.com/yuting0624/antigravity-for-claude-code> — `commands/research.md` +
  the skill's deep-research recipe, read from the 0.23.0 plugin cache. T2.
- <https://github.com/PyO3/pyo3> — touched only as a lychee CONSUMER (its CI). T3.
- <https://github.com/bamr87/it-journey> — `scripts/validation/link-checker.py`, prior art
  for the subprocess + `--format json` bridge (reads a `fail_map` key 0.24.2 does not emit). T3.
- <https://github.com/jdx/hk> — the aggregated-research spine's issues-DISABLED fixture:
  `has_issues` false, `has_discussions` true, `is:issue` structurally 0 while `is:pr` → 1005
  (re-measured 2026-08-28 by three premise-verifier passes). Its source is the `hk` we run. T2.
- <https://github.com/cli/cli> — `gh`'s exit-code and stream split probed for the trackers
  adapter contract (404 → rc 1, JSON body on stdout, `gh: Not Found (HTTP 404)` on stderr;
  `search/issues` default page 30). T3.

### 2026-08-28 — the agent-team transport round (`docs/research/reports/2026-08-28-agent-team-transport.md`)

- <https://github.com/wtyler2505/protopulse> — `docs/collab/`, a Claude↔Codex protocol
  co-design; first surfaced codex's non-interactive flag set (baseline round). T3.
- <https://github.com/johnlindquist/codex-imps> — `docs/ISOLATION.md`, an unofficial
  reverse-engineered token-cost table for codex's system prompt; unverified. T3.
- <https://github.com/openclaw/openclaw> · <https://github.com/yishentu/claudian> ·
  <https://github.com/slopus/happy> · <https://github.com/bullorosso/etienne> — four
  independent integrations that describe `codex app-server` as JSON-RPC 2.0 over stdio
  (`thread/start`, `turn/start`, `turn/interrupt`); the only corroboration the
  `[experimental]` subcommand has. T3 `deferred` until `mcp-server`'s removal lands.
- <https://github.com/ray-manaloto/claude-code-marketplace> — Ray's own marketplace, the
  decided home of the `aggregated-research` plugin (2026-08-27 g §1 decision 4); measured
  2026-08-28: `main` only, one plugin (`mise-toolkit`), 0 tags, last push 2026-04-08. T2
  `pending` — becomes a manifest once the plugin lands there.

### 2026-08-28 — the aggregated-research plugin round (`docs/research/reports/2026-08-28-{codex-plugin-cc-anatomy,mcp-1to1-and-lsp,mise-oci-container-ci,plugin-bundle-spec,cli-plugin-anatomy}.md`)

- <https://github.com/openai/codex-plugin-cc> — OpenAI's Claude Code plugin for Codex
  (installed here as `codex@openai-codex` 1.0.6): the `codex app-server` broker
  transport in production. Read from the installed cache + `gh api`; T2 `pending` — a
  manifest is warranted, it is the only production Claude↔Codex transport besides ours.
- <https://github.com/modelcontextprotocol/modelcontextprotocol> · <https://github.com/modelcontextprotocol/python-sdk>
  — the MCP spec (revision `2026-07-28`) and `mcp` 2.1.1 (`FastMCP`→`MCPServer` rename);
  Ray asked for the latest standard and the official sdk. The sdk is ALREADY registered
  above (2026-08-27b backlog, T2); this line adds only the spec repo. T2 `pending`.
- <https://github.com/facebook/pyrefly> — the second Python LSP Ray named (`pyrefly lsp`,
  `pipx:pyrefly` 1.2.0, pushed 2026-08-28). T3 `deferred` — probed, not read.
- <https://github.com/jdx/mise-action> · <https://github.com/actions/upload-artifact> ·
  <https://github.com/softprops/action-gh-release> — the GHA pieces of the container
  test; versions gh-verified 2026-08-28. T3 `tool`.
- <https://github.com/firecrawl/firecrawl-claude-plugin> · <https://github.com/upstash/context7> —
  the two plugins dissected as the pattern (and the ctx7 CLI's upstream). firecrawl already
  registered above (T2); context7 T2 `pending`.
