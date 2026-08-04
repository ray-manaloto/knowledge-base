---
type: "query"
date: "2026-08-04T11:25:46.687168+00:00"
question: "What did building #147's gate-claim verifier teach about the limits of mutation arms and green gates?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did building #147's gate-claim verifier teach about the limits of mutation arms and green gates?

## Answer

Nineteen mutation arms over kb-handoff-check's gate-claim verifier caught 18 of
19 and proved nothing about the tests themselves. A cold cross-family lane then
found 8 defects across two rounds, every one reproduced by execution, in code
that had already passed lint, ty, agnix, a full suite AND those arms.

Round 1's five were one shape: a FALSE claim judged OK by the tool built to stop
exactly that. A runner claim of rc=2 confirmed by a record, though 2 means the
runner REFUSED and writes no record. Two distributive phrases bleeding, so the
parser emitted the OPPOSITE of what was authored. A duplicate row resolved by
silently picking the one that AGREED with the claim. A row with sha="" passing
both commit checks because it is falsy for one and not-None for the other. And
"rc": true parsing as an exit code, because bool IS an int in Python and
True == 1.

Round 2's sharpest finding was in one of round 1's own FIX-TESTS: it could not
fail. Its docstring claimed it asserted against a hand-built row on purpose to
bypass the parser; it went through record() -> find_record -> _parse, and _parse
normalises "" -> None at read time, so the predicate it claimed to pin never saw
an empty string. Reverting the fix left it green. Mutation arms mutate PRODUCTION
code, so no number of them could have found it — only mutating the fix and
re-running its own test does. The lesson generalises past this repo: a test
written in the same breath as its fix inherits the fix's blind spot, and the
cheapest check is to revert the fix and watch the test fail.

Round 2 also found a state collapse: a malformed "rc": true was COERCED to None,
which is exactly the value a legitimately unreached gate carries — so corruption
became indistinguishable from "did not run" and helped confirm a claim. Absent
and present-but-wrong-typed are different, and a field of the wrong type now
makes the whole record unreadable.

Two design rules that held up under both rounds. A gate claim binds to the commit
named in its OWN block, never the nearest preceding sha (a gotchas paragraph
would vouch for the gate list below it) and never HEAD by default (that
manufactures the false green). And FAIL means the record CONTRADICTS the claim
while UNVERIFIABLE means nothing can speak to it — .agent/ is machine-local, so
failing on an absent record would break the checker in exactly the situation it
exists for.

## Outcome

- Signal: useful