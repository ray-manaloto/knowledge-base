---
type: "query"
date: "2026-08-07T03:15:47.672326+00:00"
question: "Can command-frequency mining over session transcripts find manual steps that should become mise tasks?"
contributor: "graphify"
outcome: "useful"
---

# Q: Can command-frequency mining over session transcripts find manual steps that should become mise tasks?

## Answer

Frequency over command shapes CANNOT find "a manual step that should become a
task" in this repo. Measured before building, #219, 2026-08-07, over the 60 most
recent session transcripts (32,826 shaped command steps), six matching forms:

  raw 3-grams, >=2 sessions                        2,317 candidates
  + scaffolding dropped, tasks as run boundaries     321
  exact distinct-shape SET of a run                    3
  3-itemsets, >=5 sessions                           835
  exact SET + repo-specific-marker filter              2
  itemsets + marker filter                         1,528

At every threshold and every form the top of the list is git add/commit/status/log
and grep - commands that recur constantly and will never become a kb-* task.
Loosen the rule and git dominates; tighten it and recurrence collapses. There is
no threshold in between: rows 2 to 3 go 321 -> 3 by changing only the matching
form, not the data.

The targets ARE in the data; frequency is just not how to reach them.
`git rev-parse -> git diff -> git log` appears in 22 of 60 sessions and is
kb-review step 1 run by hand. `uv run pytest -> python3 -> uv run pytest`
appears in 6 and is the mutation harness (#160).

What works instead: detect the ACT, not the frequency. Writing a throwaway
script and running it - a python3 heredoc, a scratchpad .py - is precisely
detectable, needs no threshold, and yields a real FAIL arm (a session that wrote
no ad-hoc script proposes nothing). Shipped as kb_setup.distill /
`mise run kb-distill`, wired into the clear-prep skill.

Live measurement over 40 sessions: 785 ad-hoc scripts, 45 candidates. The
largest group is `python/src/kb_setup` at 121 scripts across 17 sessions - patch
a source file, run tests, restore. That is the mutation harness, hand-written
five times, still open as #160.

Two design facts worth not rediscovering:

- An IMPORT-only signature is too coarse: it put 153 of 785 scripts in one
  `json` bucket. Group by the repo SURFACE a probe touches plus its imports -
  imports say which library was used, surfaces say which question was asked, and
  the question is the axis a distilled module would be named along.
- Do not mint a skill per task. The trigger here is "a round just ended", which
  is what the clear-prep skill already is, so the task wires in there at zero
  skill-listing budget.

## Outcome

- Signal: useful