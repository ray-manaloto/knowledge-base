# graphify

- **graphify** (`.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

# Issue tracker

GitHub Issues on `ray-manaloto/knowledge-base`, via `gh`. **See
`docs/issue-tracker.md`** — it carries the conventions plus the "Wayfinding
operations" section `/mattpocock-skills:wayfinder`, `to-spec`, `to-tickets`,
`triage` and `code-review` read.

This pointer is load-bearing, not a courtesy: those skills fall back to a
local-markdown tracker when no tracker doc has been provided, and nothing else
in the auto-loaded context names the file. It lives here rather than in the root
`CLAUDE.md` because that file is **at** its 200-line budget.

Two companions, same reason for their paths: **`docs/triage-labels.md`** (the five
canonical triage roles; all five labels now exist) and **`docs/domain.md`** (how
skills consume this repo's vocabulary — single-context, and `CONTEXT.md`/`docs/adr/`
are created lazily by `/domain-modeling`, never scaffolded empty). All three sit in
`docs/` rather than `docs/agents/` because agnix rejects an `**/agents/*.md` without
YAML frontmatter — re-probed control-armed 2026-08-03, rc=1 there vs rc=0 in `docs/`.

PRs are opened and merged with `mise run kb-ship` / `mise run kb-land`, never
`gh pr create` / `gh pr merge`. Read-only `gh pr view` / `gh pr checks` stay
fine — `gh pr view` is how you resolve whether a bare `#42` is an issue or a PR.

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

Four more were enabled 2026-08-03 without needing a note here — `pr-review-toolkit`,
`skill-creator`, `claude-md-management` (all `@claude-plugins-official`) and
`mise@brentmitchell25`, all Ray's, all ordinary tooling. **Ten plugins are enabled in
total**, which is what `md-size-budgets.md` § the skill-listing budget is about.

Two are enabled for skill self-improvement and DO need a note, both PROJECT-scope
(`do-not.md` #11 — `extraKnownMarketplaces` + `enabledPlugins` here, never a write to
`~/.claude`):
`plugin-eval@claude-code-workflows` (`/eval`, `/certify`, `/compare`; its static layer is what
`mise run kb-skill-score` wraps) and `skillopt-sleep@skillopt-sleep` (`/skillopt-sleep`, from
`microsoft/SkillOpt`, tracked as a `source_only` entry in `currency.toml`). SkillOpt-Sleep stages
bounded edits to memory and skills behind a held-out gate and changes **nothing** until
`/skillopt-sleep adopt` — that human review is the control, not a formality.

- **Route with the graph.** Before a non-trivial routing/fallback decision, ground it in this repo's
  KB graph: `mise run kb-query -- "<routing question>"` (the doctrine lives there — advisor/executor,
  cheapest-adequate lane, five-part spec, Fable-5→Opus fallback). See
  `.claude/skills/orchestrator-routing/SKILL.md` for the unified 3-lane doctrine.
- **Lanes**: `codex` (GPT-5.6 Sol) for correctness-critical work; `antigravity` (Gemini 3.x) for
  broad/mechanical or a second-opinion; cross-family review keeps the reviewer a different family
  than the implementer; terminal fallback is always a Claude Opus subagent (never silent).
