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
| 1 | [platform.claude.com/sitemap.xml](https://platform.claude.com/sitemap.xml) → [multiagent-orchestration](https://platform.claude.com/docs/en/managed-agents/multiagent-orchestration) | docs | T1 | pending | Authoritative: managed-agents + multi-agent orchestration. |
| 2 | [code.claude.com/sitemap.xml](https://code.claude.com/sitemap.xml) | docs | T1 | pending | Authoritative: Claude Code subagents, model config, hooks, skills. |
| 3 | [prompting-claude-fable-5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5) | docs | T1 | pending | Fable-5 prompt engineering (orchestrator prompt design). |
| 4 | [bytedance/deer-flow](https://github.com/bytedance/deer-flow) | repo | T1 | pending | Multi-agent deep-research framework — blueprint candidate. |
| 5 | [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) | repo | T1 | pending | Self-learning / skill optimization — feeds the self-learning loop. |
| 6 | [DannyMac180/fable-advisor](https://github.com/DannyMac180/fable-advisor) | repo | T1 | pending | Fable-5 advisor pattern reference. |
| 7 | [Cjbuilds/Codex-Orchestration](https://github.com/Cjbuilds/Codex-Orchestration) | repo | T1 | pending | Codex handoff / orchestration reference. |
| 8 | [Rylaa/fable5-orchestrator](https://github.com/Rylaa/fable5-orchestrator) | repo | T1 | pending | Fable-5 orchestrator reference. |
| 9 | [mar3co/fable-orchestrator](https://github.com/mar3co/fable-orchestrator) | repo | T1 | pending | Fable orchestrator reference. |
| 10 | [advisor-executor-pattern (mindstudio)](https://www.mindstudio.ai/blog/advisor-executor-pattern-claude-code-fable-5) | article | T1 | pending | Directly on the advisor/executor decision. |
| 11 | [asgeirtj/system_prompts_leaks → claude-fable-5.md](https://github.com/asgeirtj/system_prompts_leaks/blob/main/Anthropic/claude-fable-5.md) | repo | T1 | pending | Fable-5 system-prompt leak (behavioral priors). |
| 12 | [linas.substack — Fable-5-lite/Opus-4.8](https://linas.substack.com/p/unlock-claude-fable-5-lite-opus-48) | article | T1 | pending | Fable-5→Opus-4.8 fallback pattern. |
| 13 | [r/claude — fable_5_and_opus_48_prompt](https://www.reddit.com/r/claude/comments/1unhubx/fable_5_and_opus_48_prompt/) | forum | T1 | pending | Fable-5/Opus-4.8 fallback prompt discussion. |
| 14 | [youtu.be/XTBWVVcF3Pk](https://youtu.be/XTBWVVcF3Pk) | media | T1 | pending | Fallback-pattern walkthrough (transcribe via whisper). |
| 15 | [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) | repo | T1 | pending | **tool**: install+configure for Reddit/X/HN trend gap-fill. |
| 16 | [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | repo | T2 | pending | Catalog — extract structure/pointers, don't fan out every link. |
| 17 | [anthropics/claude-plugins-community](https://github.com/anthropics/claude-plugins-community) | repo | T2 | pending | Plugin catalog — pointers to reusable agents/skills. |
| 18 | [affaan-m/ECC](https://github.com/affaan-m/ECC) | repo | T2 | pending | Notable resource (evaluate on ingest). |
| 19 | [mindstudio blog — tag/claude](https://www.mindstudio.ai/blog/tag/claude) | article | T2 | pending | Broader Claude blog set (light). |
| 20 | [x.com/ClaudeDevs](https://x.com/ClaudeDevs) | timeline | T3 | deferred | Live timeline → reach via last30days-skill, not static ingest. |
| 21 | [x.com/ClaudeAI](https://x.com/ClaudeAI) | timeline | T3 | deferred | Live timeline → reach via last30days-skill, not static ingest. |

## Progress log

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
