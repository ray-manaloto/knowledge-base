---
type: "query"
date: "2026-07-30T17:05:51.917985+00:00"
question: "How do you tell a test that guards a regression from one that only looks like it does?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you tell a test that guards a regression from one that only looks like it does?

## Answer

Apply the regression the test NAMES and read the suite rc. On #59, the old tests exited 0 under both 'push the branch instead of the validated sha' and '_check_blocking removed from _CHECKS' — fully blind, not merely weak. Two causes recur: (1) a stub that answers the same value to two different questions (git rev-parse HEAD vs --abbrev-ref HEAD both returned 'feat/x', so the asserted refspec was what BOTH the correct code and the regression produce); (2) a fixture missing the setup needed to REACH the check under test, so an earlier gate refuses first and the later one is never consulted. Fix (1) by making the stub discriminate, (2) by removing every other reason to refuse. Assert the specific MESSAGE, not just the exit code, whenever several layers can produce the same rc.

## Outcome

- Signal: useful