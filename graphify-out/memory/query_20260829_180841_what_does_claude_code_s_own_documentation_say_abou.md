---
type: "query"
date: "2026-08-29T18:08:41.912073+00:00"
question: "What does Claude Code's own documentation say about verifying work before claiming completion (desktop.md Auto-verify, skills.md Run and verify your app, best-practices.md verify guidance)?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does Claude Code's own documentation say about verifying work before claiming completion (desktop.md Auto-verify, skills.md Run and verify your app, best-practices.md verify guidance)?

## Answer

# Round answer — verification doctrine cross-check against Claude Code's own docs

Ray asked whether the codex-implementer/codex-reviewer lanes and this repo's
dispatch workflow do proper verification before claiming completion, and
asked for a review of three doc sections for anything relevant to add to the
corpus.

## fable-advisor verdict on the lanes (2026-08-29, session kb-20260829.02)

The current 3-layer discipline is adequate; do NOT add a 4th same-family,
same-sandbox verification dispatch. Evidence: a codex-implementer dispatch
for #572 correctly reported a verification item (`mise run
kb-plugin-validate`) as UNVERIFIED because its sandbox has no network
egress to schemastore — it did not fabricate a pass. The caller then
independently re-ran the real command and found a genuine defect (a
`$comment` field that was schema-valid but broke this repo's own
`claude plugin validate` wrapper). **The gap: that re-run was discretionary,
not enforced.** Filed as knowledge-base#602: a lane report with any
UNVERIFIED verification item must force a caller re-run before "complete"
is accepted, and this repo's known codex-CLI sandbox limits (no new git
refs under `workspace-write`; no network egress) should be baked into the
dispatch spec template so future rounds don't rediscover them.

Also settled: `/grilling -> /to-spec -> /to-tickets -> /implement`
(mattpocock-skills, a human-interview planning chain) and the
fable-orchestrator's inline 7-part spec contract (architect-to-lane dispatch
protocol) are correctly kept SEPARATE — they compose (a ticket becomes a
7-part spec) rather than one replacing the other.

## Corroboration from Claude Code's own docs (claude-code-docs, resynced to
upstream HEAD this round)

- `docs/claude-code/best-practices.md` § "Give Claude a way to verify its
  work": *"Claude stops when the work looks done. Without a check it can
  run, 'looks done' is the only signal available... Give Claude something
  that produces a pass or fail, and the loop closes on its own."* Also names
  the exact pattern this repo already uses — **"By a second opinion: a
  verification subagent... that checks its own findings has a fresh model
  try to refute the result, so the agent doing the work isn't the one
  grading it"** — which is precisely `kb-review`'s cold cross-family lane
  policy. And: *"The trust-then-verify gap... Fix: Always provide
  verification (tests, scripts, screenshots). If you can't verify it, don't
  ship it."* This directly validates re-running `kb-plugin-validate` myself
  rather than trusting codex's unverified diff.
- `docs/claude-code/skills.md` § "Run and verify your app": there is a
  BUNDLED `/verify` skill — *"Build and run your app to confirm a code
  change does what it should, without falling back to tests or type
  checks"* — plus `/run-skill-generator`, which records a per-project launch
  recipe at `.claude/skills/run-<name>/` so later runs and OTHER AGENTS
  follow the same steps instead of rediscovering them. This repo's `run`
  skill (`.claude/skills/run` — not present as of this check, only the
  bundled/marketplace `run` skill entry appears in the session's skill
  list) plays an analogous role to `/run`; `mise run kb-check`/`kb-gates`
  play the role `/verify` plays for a project with no launchable "app".
  Worth a future pass: does this repo's actual `.claude/skills/run/` (if it
  exists) or a `run-<name>` recipe already cover the graphify/mise workflow,
  or would `/run-skill-generator` add anything mise's own task discovery
  doesn't already give an agent?
- `docs/claude-code/desktop.md` § "Auto-verify changes": `autoVerify` (on by
  default, `.claude/launch.json`) makes the DESKTOP APP auto-screenshot and
  check for errors after every edit to a PREVIEW SERVER. Not directly
  actionable here — this repo has no dev-server preview target, it's a CLI
  research tool — but it is more corpus evidence that "verify automatically,
  by default, without being asked" is Anthropic's own house position across
  three separate product surfaces (desktop preview, `/verify` skill,
  best-practices guidance), not just this repo's own `verify-before-advancing.md`
  rule reinventing something.

## Net takeaway

No code change needed from the doc review itself — it corroborates existing
practice rather than revealing a gap. The one real gap (issue #602) came
from the advisor consult on THIS session's own dispatch history, not from
the docs.

## Outcome

- Signal: useful