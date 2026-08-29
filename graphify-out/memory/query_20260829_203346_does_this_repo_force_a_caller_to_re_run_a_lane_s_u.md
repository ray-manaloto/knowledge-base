---
type: "query"
date: "2026-08-29T20:33:46.131520+00:00"
question: "Does this repo force a caller to re-run a lane's UNVERIFIED verification item before calling a task done, and are codex's sandbox limits documented? (#602)"
contributor: "graphify"
outcome: "useful"
---

# Q: Does this repo force a caller to re-run a lane's UNVERIFIED verification item before calling a task done, and are codex's sandbox limits documented? (#602)

## Answer

Ticket #602 asked whether this repo's dispatch discipline forces a caller to
independently re-run a lane's UNVERIFIED/claim-only/not-run verification item
before treating the task as done, and whether codex's two known sandbox
limits are documented for future dispatches.

Answer: no such rule existed before this round. Built it — a new section in
`.claude/rules/verify-before-advancing.md` states a lane report with any
UNVERIFIED/claim-only/not-run item is not "done" until the caller
independently re-runs that item and records the real result (via
`mise run kb-gates` for a no-argument gate task, or directly plus
`mise run brain-remember` for one needing a positional argument like
`kb-plugin-validate`). Documented codex's two sandbox limits (no git-ref
creation under workspace-write, no network egress) in
`.claude/skills/orchestrator-routing/SKILL.md`.

Process note, itself a finding: two full cold-review rounds each caught a
real, confirmed defect in the fix — round 1 found the rule's own worked
example cited the wrong issue number (said #602 landed something #572 did);
round 2 (after antigravity failed twice on infra grounds, fell back to a
Claude Opus cold pass) found the rule's OTHER worked example was flatly
broken: `mise run kb-gates` cannot forward the positional argument
`kb-plugin-validate` requires, so following the rule as written would always
fail with a usage error unrelated to the thing being checked. Shipped as
PR #609, merged, #602 closed.


## Outcome

- Signal: useful