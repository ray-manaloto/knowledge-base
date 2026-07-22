# graphify

- **graphify** (`.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

# Cross-vendor orchestration (Fable-5 architect + executor lanes)

fable-orchestrator: implementation lane = codex

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
