---
type: "query"
date: "2026-08-10T11:32:06.712447+00:00"
question: "What did R5 tranche 4 and the #270 fix establish that the conversion recipe did not predict?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did R5 tranche 4 and the #270 fix establish that the conversion recipe did not predict?

## Answer

R5 tranche 4 converted goal/hook_guard/gates/launch to the Result/Rc boundary (12 of ~35), and closed #270. Three findings the round produced that nothing else records:

1. HALF A RULED LIST DID NOT FIT ITS OWN CRITERION. The tranche-4 ruling named eight boundaries; measuring them against recipe rule 3 (the boundary prints nothing) before converting any showed only four are render-once. pr.ship_main, pr.land_main, skill_refresh.refresh and launch.cc_main print progressively between subprocess and network calls -- the same shape as the graphify_ops family already deferred. Measuring a ruled list before executing it cost one probe and prevented making kb-land silent for its whole check-wait.

2. A SURVIVING MUTATION ARM CAN BE AN INERT MUTANT RATHER THAN A COVERAGE GAP, AND THE SWEEP OUTPUT RENDERS THEM IDENTICALLY. An arm meant to prove gates.main funnels through exit_code replaced it with a hand-rolled 0-if-passed-else-1 and survived. Rc.OK IS 0 and Rc.FINDINGS IS 1, so the mutation is extensionally equal across the whole Ok branch -- proved by running both directions, not argued. The consequence is durable: "funnels through the single documented conversion" is an UNOBSERVABLE property in that function today. The diagnosis step is cheap and must be separate from the sweep: ask whether the mutated expression and the original can EVER disagree.

3. TWO BOUNDARIES DELIBERATELY NEVER RETURN Rc.FINDINGS, and a mechanical conversion would have broken both. hook_guard: a PreToolUse hook's verdict travels in its stdout JSON, so an rc of 1 means the hook CRASHED. goal: kb-goal-check is advisory by ruling. Both departures now carry a test with a control arm, and both are armed against the realistic break -- a reviewer making the odd ones out consistent with the other ten.

Also: both cold-review findings, and one near-miss of my own, were PROSE. A docstring's opening line is its oldest claim, so it is the part an editor adding a paragraph is least likely to re-read and the part every reader sees first. And a justification that points at sibling cases goes stale the moment a sibling moves -- goal.py said the no-input branch was left at Rc.OK "for the same reason the other three were", which was true when written and false one commit later, since #270 closed two of the three. My own near-miss was arguing that closing the case would break --text piping; armed it, --text is the FIRST branch in main and can never reach the no-input else. Removed rather than shipped.

## Outcome

- Signal: useful