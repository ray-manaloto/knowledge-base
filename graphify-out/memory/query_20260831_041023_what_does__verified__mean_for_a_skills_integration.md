---
type: "query"
date: "2026-08-31T04:10:23.906714+00:00"
question: "What does 'verified' mean for a skills integration, and what actually catches defects?"
contributor: "graphify"
outcome: "corrected"
correction: "The overturned belief: that running the applicable gates and reporting their\nexit codes constitutes verification.\n\nIt does not. In this round `md-budget`, `skill-lint`, `lint-docs` and\n`mirror_drift` all returned 0 against a skills integration that was missing\nthree P1 behaviours, promised an advisory that cannot fire, and contained a\nchecklist row contradicting a rule two paragraphs above it. Every gate was\nhonest; none of them was asking the question.\n\nThree corollaries, each measured this round:\n\n1. A HOOK'S GREEN CAN DESCRIBE A TREE THAT NO LONGER EXISTS. `md_size_budget`\n   passed, then hk's `rumdl_format` reflowed the file in the same commit and\n   added a line, shipping 501 against a 500 cap. Run the formatter BEFORE the\n   measurement, and re-run any size gate against the COMMITTED tree.\n\n2. A DIFF REVIEW CANNOT SEE INCOMPLETENESS. It reviews what changed. When the\n   defect is that something was never written, only a full-content read against\n   the dependency's own source finds it.\n\n3. THE AUTHOR IS THE WRONG AUDITOR OF THEIR OWN FIX. Two fixes this round each\n   introduced a new defect, and one contradicted its own conditional rule inside\n   the same commit that created it.\n\nAnd the failure shape behind most of it: stating a claim slightly stronger than\nits source supports. Three instances in one round — a `~90 tokens` figure that\nmeasured 440, a \"the plugin recommends slug mode\" scoped in the source to\nparallel sessions only, and \"silently stops reaching context\" against a source\nthat echoes a notice. Each was caught externally; none by re-reading my own words.\n"
---

# Q: What does 'verified' mean for a skills integration, and what actually catches defects?

## Answer

# Round kb-20260830.003 — what it asked and what it found

The round installed and integrated the `planning-with-files` plugin, landed PR
#637, corrected GitHub issue #638's measured claims, and moved the mise pin.

The durable finding is not any of those. It is this: **every real defect in this
round was caught by something external to the author.**

- A **mutation arm** found that `.gitignore`'s `.planning/` was unanchored, and
  later that the archive command could not execute at all (`mkdir -p` missing,
  `&&` short-circuit leaving the stale plan selected). Both look correct on the
  page. A read-only review found neither.
- A **dissenting implementer lane** refused a spec whose premise said an
  un-re-attested plan "silently" stops reaching context. `inject-plan.sh` echoes
  an explicit notice. The word was the architect's; the source never said it.
- A **cold full-content review** — not a diff review — found the skills
  integration was INCOMPLETE in three P1 ways that no diff could show, because
  nothing in the diff was wrong.
- **Ray asking "were the changes verified?"** exposed that "verified" had meant
  "the gates passed", which proves files are well-formed and nothing about
  whether an integration is correct or complete.

Gates confirm form. Arms, cold lanes and the user confirm truth. They are not
substitutes.


## Outcome

- Signal: corrected
- Correction: The overturned belief: that running the applicable gates and reporting their
exit codes constitutes verification.

It does not. In this round `md-budget`, `skill-lint`, `lint-docs` and
`mirror_drift` all returned 0 against a skills integration that was missing
three P1 behaviours, promised an advisory that cannot fire, and contained a
checklist row contradicting a rule two paragraphs above it. Every gate was
honest; none of them was asking the question.

Three corollaries, each measured this round:

1. A HOOK'S GREEN CAN DESCRIBE A TREE THAT NO LONGER EXISTS. `md_size_budget`
   passed, then hk's `rumdl_format` reflowed the file in the same commit and
   added a line, shipping 501 against a 500 cap. Run the formatter BEFORE the
   measurement, and re-run any size gate against the COMMITTED tree.

2. A DIFF REVIEW CANNOT SEE INCOMPLETENESS. It reviews what changed. When the
   defect is that something was never written, only a full-content read against
   the dependency's own source finds it.

3. THE AUTHOR IS THE WRONG AUDITOR OF THEIR OWN FIX. Two fixes this round each
   introduced a new defect, and one contradicted its own conditional rule inside
   the same commit that created it.

And the failure shape behind most of it: stating a claim slightly stronger than
its source supports. Three instances in one round — a `~90 tokens` figure that
measured 440, a "the plugin recommends slug mode" scoped in the source to
parallel sessions only, and "silently stops reaching context" against a source
that echoes a notice. Each was caught externally; none by re-reading my own words.
