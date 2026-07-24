# graphify

- **graphify** (`.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

# Cross-vendor orchestration (Fable-5 architect + executor lanes)

- When the session model is Fable, without being reminded: non-trivial implementation runs the fable-orchestrator architect-as-orchestrator flow — invoke the fable-orchestrator:orchestration skill before delegating and follow it as authoritative for routing, verification, review tiers, and advisor consults.
- fable-orchestrator: implementation lane = codex

The first line is the **trigger**, Fable-gated by design (sessions on other models skip the
flow). Until 2026-07-24 only the mode line existed, which the plugin's setup wizard calls
"inert without the trigger". Default `/model` is **Opus 5**; switch to **Fable 5** to arm
this flow. `grok` CLI is not installed → `codex` is the only viable fixed mode.

Adopted plugins (enabled in `.claude/settings.json`): `fable-orchestrator@fable-orchestrator`
(Claude/Fable-5 architect + `codex` implementer lane + cross-family reviewers + supervisor + terminal
Opus fallback) and `antigravity@antigravity-for-claude-code` (Google Antigravity/Gemini 3.x lane via
`agy`). The Claude architect plans and **verifies evidence** before "done"; only execution is delegated.

- **Route with the graph.** Before a non-trivial routing/fallback decision, ground it in this repo's
  KB graph: `mise run kb-query -- "<routing question>"` (the doctrine lives there — advisor/executor,
  cheapest-adequate lane, five-part spec, Fable-5→Opus fallback). See
  `.claude/skills/orchestrator-routing/SKILL.md` for the unified 3-lane doctrine.
- **Lanes**: `codex` (GPT-5.6 Sol) for correctness-critical work; `antigravity` (Gemini 3.x) for
  broad/mechanical or a second-opinion; cross-family review keeps the reviewer a different family
  than the implementer; terminal fallback is always a Claude Opus subagent (never silent).
