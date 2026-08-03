---
type: "query"
date: "2026-08-03T21:00:50.513486+00:00"
question: "Two cold-review rounds passed PR #139. What did a Standards+Spec review find afterwards, and what does that say about the one-lane policy?"
contributor: "graphify"
outcome: "useful"
---

# Q: Two cold-review rounds passed PR #139. What did a Standards+Spec review find afterwards, and what does that say about the one-lane policy?

## Answer

A two-axis Standards+Spec review over PR #139 -- run AFTER two rounds of cold cross-family review had already passed it -- found 15 more findings. That is the measured case for not collapsing the axes.

The Standards axis found what a correctness reviewer structurally will not look for: two docs whose stated counts were falsified by the very commit they describe (a rule file said "five enabled plugins" while that PR took it to ten), a fact hardcoded in one file that the same PR declared as config in another, and a false negative where a mistyped skill name printed "no skill directories" while seven existed -- in a module whose own docstring cites probes-need-a-control-arm and insists "could not measure" and "measured badly" are different answers.

The Spec axis found the thing no code reviewer can see, because it requires reading the brief rather than the diff: the one skill the round authored is 305 lines of step-by-step agent instructions, violating the standing protocol it was built to serve -- "automate agents work into skills to reduce tokens instead of having agents follow step by step instructions". It also caught that issue #124 named THREE tools and only two were researched, with SkillLens getting 0 hits in the diff against 43 for SkillOpt (control-armed), and that #124/#125 were still open with zero comments: the artifact was built and the analysis it was supposed to produce was never written.

This is why kb-review's one-lane "by-policy-one-lane" stand-down of standards and spec is a MEASURED trade, not a free one. It was chosen for proportion after four lanes cost 2.93M tokens on #67, and that reasoning still holds -- but the coverage given up is real and this run priced it: 15 findings on a diff two cold rounds had cleared.

Also worth carrying: verify a subagent's claims before repeating them. The Spec agent reported "adds no new mise task" when the diff adds tasks.kb-skill-score and the skill calls it three times. The narrower finding survived; the headline as stated was wrong. And both agents went idle without sending their reports until asked directly -- a skill that spawns findings-bearing subagents without instructing them to persist incrementally is one silent death away from losing the whole review.

## Outcome

- Signal: useful