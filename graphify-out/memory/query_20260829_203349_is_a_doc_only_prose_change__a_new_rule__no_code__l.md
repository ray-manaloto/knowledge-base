---
type: "query"
date: "2026-08-29T20:33:49.893444+00:00"
question: "Is a doc-only prose change (a new rule, no code) low-risk enough to skip cold review, and does lint passing mean the prose is correct?"
contributor: "graphify"
outcome: "corrected"
correction: "Wrong belief: a doc-only, prose-only change (a new rule + a sandbox-limits\nsection, zero code) is low-risk enough that one cold pass would be\nsufficient, or that lint passing (agnix --strict, hk check --all) is a\nmeaningful signal of correctness for prose.\n\nWhat actually happened: TWO cold-review rounds on this doc-only diff each\nfound a real, confirmed defect that lint could never catch, because lint\nchecks markdown syntax and budgets, not factual claims. Round 1: the rule's\nown worked example cited the wrong issue number. Round 2: the rule's OTHER\nworked example told readers to route a command through `mise run kb-gates`\nthat `kb-gates` cannot actually run correctly (it can't forward the\ncommand's required positional argument), so the rule's own advice would\nalways fail for reasons unrelated to what it claims to check.\n\nCorrection: doc/rule changes are not exempt from the \"fix can be the defect\"\nrisk this repo already tracks for code\n(`four-cold-passes-four-defects-in-the-fix.md`,\n`probes-need-a-control-arm.md` rule 2's \"arm your own fixes\"). A rule whose\nown worked examples are broken is worse than no rule — it actively misleads\nwhoever follows it. Cold review earns its cost even on prose, and prose\nciting a command needs the command's actual argument contract checked\nagainst the code, not just against the rule's own internal logic.\n"
---

# Q: Is a doc-only prose change (a new rule, no code) low-risk enough to skip cold review, and does lint passing mean the prose is correct?

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

- Signal: corrected
- Correction: Wrong belief: a doc-only, prose-only change (a new rule + a sandbox-limits
section, zero code) is low-risk enough that one cold pass would be
sufficient, or that lint passing (agnix --strict, hk check --all) is a
meaningful signal of correctness for prose.

What actually happened: TWO cold-review rounds on this doc-only diff each
found a real, confirmed defect that lint could never catch, because lint
checks markdown syntax and budgets, not factual claims. Round 1: the rule's
own worked example cited the wrong issue number. Round 2: the rule's OTHER
worked example told readers to route a command through `mise run kb-gates`
that `kb-gates` cannot actually run correctly (it can't forward the
command's required positional argument), so the rule's own advice would
always fail for reasons unrelated to what it claims to check.

Correction: doc/rule changes are not exempt from the "fix can be the defect"
risk this repo already tracks for code
(`four-cold-passes-four-defects-in-the-fix.md`,
`probes-need-a-control-arm.md` rule 2's "arm your own fixes"). A rule whose
own worked examples are broken is worse than no rule — it actively misleads
whoever follows it. Cold review earns its cost even on prose, and prose
citing a command needs the command's actual argument contract checked
against the code, not just against the rule's own internal logic.
