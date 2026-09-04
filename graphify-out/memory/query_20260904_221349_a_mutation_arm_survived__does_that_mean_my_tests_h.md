---
type: "query"
date: "2026-09-04T22:13:49.586203+00:00"
question: "A mutation arm survived. Does that mean my tests have a coverage gap?"
contributor: "graphify"
outcome: "corrected"
correction: "# A surviving mutation arm is not a coverage gap until you show the mutant differs\n\nThree survivors in one round on #711, and **not one of them was a missing test**.\nEach needed a different response, and taking any of them at face value would have\nmade the suite worse.\n\n## A5 — the mutant survived because the LINE WAS DEAD\n\n`_closure_members` had `if member == path: continue`, excluding an entry point\nfrom its own import closure. Obviously right by reading. The arm removing it\nkilled no test.\n\nMeasured rather than argued: over a tree of two stub/AGENTS.md pairs, the only\npaths that exclusion ever dropped were `CLAUDE.md` and `docs/CLAUDE.md`, and\nNEITHER classifies as the one class the set is consulted for. The branch could\nnever fire.\n\n**Response: delete the branch.** Not write a test for it. A defensive line\nnothing can reach is a line no arm can protect, and leaving it would have put an\nunarmed conditional inside a function carrying a cross-repo invariant.\n\n## S7 — the mutant survived because it changed no BEHAVIOUR, twice\n\nTwo attempts to arm `_unwrap_runner`'s bounded flag-scan:\n\n- v1 replaced it with `words.index(\"run\")`. Probed over six shapes, the two\n  implementations differed on **0** — a trailing `or words` fallback collapses\n  the only case that could diverge.\n- v2 replaced it with a forward scan for the first python-ish token, which is the\n  historical defect's exact shape. This one DOES change the parse\n  (`uv run pytest -k python` unwraps to `['python']`), and still the deny\n  decision is identical on all six shapes, because three further conditions have\n  to hold downstream.\n\n**Response: drop the arm and record why.** The survival located the real\nprotection somewhere else — in a conjunction that a different arm already covers\nand which died. The line stays, because it is reachable and correct; it is merely\nmasked today.\n\n## F8 — the mutant survived because MY TEST COULD NOT FAIL\n\nThe fix added a `tool_name` check to a hook entry point. The test I wrote beside\nit asserted `main(...) == 0`. But `main` returns 0 unconditionally, by design — a\nhook exiting non-zero on its own confusion breaks every Bash call in the session.\nSo the assertion was true before the fix, after the fix, and under every mutation.\n\n**Response: fix the test.** The observable that separates the behaviours is\nwhether anything is PRINTED, not the return code.\n\nThis is the class `kb-review` §4a rule 1 names, and it is invisible to everything\nelse: a review lane reads the test and it looks fine; a mutation sweep mutates\nproduction code, so a test asserting nothing cannot be seen at all. **The arm is\nthe only instrument that finds it, and only because it survived.**\n\n## The rule\n\nA survivor asks a question; it does not answer one. Before treating it as a\nmissing test, construct an input where the mutant and the original differ **in\nobservable behaviour**, not just in tokens. Three outcomes are all legitimate:\nthe line is dead (delete it), the property is masked (record it), or your test is\ndecoration (fix it). Only the third is \"write a better test\", and it was the\nminority here.\n\nRelated: a clean sweep is never evidence the change is correct. This round scored\n11/11 before the cold lane ran the module and found four P1 defects — including\na quoted `'>'` denying an ordinary `grep`, and one `cd` bypassing the guard\nentirely.\n"
---

# Q: A mutation arm survived. Does that mean my tests have a coverage gap?

## Answer

# A surviving mutation arm is not a coverage gap until you show the mutant differs

Three survivors in one round on #711, and **not one of them was a missing test**.
Each needed a different response, and taking any of them at face value would have
made the suite worse.

## A5 — the mutant survived because the LINE WAS DEAD

`_closure_members` had `if member == path: continue`, excluding an entry point
from its own import closure. Obviously right by reading. The arm removing it
killed no test.

Measured rather than argued: over a tree of two stub/AGENTS.md pairs, the only
paths that exclusion ever dropped were `CLAUDE.md` and `docs/CLAUDE.md`, and
NEITHER classifies as the one class the set is consulted for. The branch could
never fire.

**Response: delete the branch.** Not write a test for it. A defensive line
nothing can reach is a line no arm can protect, and leaving it would have put an
unarmed conditional inside a function carrying a cross-repo invariant.

## S7 — the mutant survived because it changed no BEHAVIOUR, twice

Two attempts to arm `_unwrap_runner`'s bounded flag-scan:

- v1 replaced it with `words.index("run")`. Probed over six shapes, the two
  implementations differed on **0** — a trailing `or words` fallback collapses
  the only case that could diverge.
- v2 replaced it with a forward scan for the first python-ish token, which is the
  historical defect's exact shape. This one DOES change the parse
  (`uv run pytest -k python` unwraps to `['python']`), and still the deny
  decision is identical on all six shapes, because three further conditions have
  to hold downstream.

**Response: drop the arm and record why.** The survival located the real
protection somewhere else — in a conjunction that a different arm already covers
and which died. The line stays, because it is reachable and correct; it is merely
masked today.

## F8 — the mutant survived because MY TEST COULD NOT FAIL

The fix added a `tool_name` check to a hook entry point. The test I wrote beside
it asserted `main(...) == 0`. But `main` returns 0 unconditionally, by design — a
hook exiting non-zero on its own confusion breaks every Bash call in the session.
So the assertion was true before the fix, after the fix, and under every mutation.

**Response: fix the test.** The observable that separates the behaviours is
whether anything is PRINTED, not the return code.

This is the class `kb-review` §4a rule 1 names, and it is invisible to everything
else: a review lane reads the test and it looks fine; a mutation sweep mutates
production code, so a test asserting nothing cannot be seen at all. **The arm is
the only instrument that finds it, and only because it survived.**

## The rule

A survivor asks a question; it does not answer one. Before treating it as a
missing test, construct an input where the mutant and the original differ **in
observable behaviour**, not just in tokens. Three outcomes are all legitimate:
the line is dead (delete it), the property is masked (record it), or your test is
decoration (fix it). Only the third is "write a better test", and it was the
minority here.

Related: a clean sweep is never evidence the change is correct. This round scored
11/11 before the cold lane ran the module and found four P1 defects — including
a quoted `'>'` denying an ordinary `grep`, and one `cd` bypassing the guard
entirely.


## Outcome

- Signal: corrected
- Correction: # A surviving mutation arm is not a coverage gap until you show the mutant differs

Three survivors in one round on #711, and **not one of them was a missing test**.
Each needed a different response, and taking any of them at face value would have
made the suite worse.

## A5 — the mutant survived because the LINE WAS DEAD

`_closure_members` had `if member == path: continue`, excluding an entry point
from its own import closure. Obviously right by reading. The arm removing it
killed no test.

Measured rather than argued: over a tree of two stub/AGENTS.md pairs, the only
paths that exclusion ever dropped were `CLAUDE.md` and `docs/CLAUDE.md`, and
NEITHER classifies as the one class the set is consulted for. The branch could
never fire.

**Response: delete the branch.** Not write a test for it. A defensive line
nothing can reach is a line no arm can protect, and leaving it would have put an
unarmed conditional inside a function carrying a cross-repo invariant.

## S7 — the mutant survived because it changed no BEHAVIOUR, twice

Two attempts to arm `_unwrap_runner`'s bounded flag-scan:

- v1 replaced it with `words.index("run")`. Probed over six shapes, the two
  implementations differed on **0** — a trailing `or words` fallback collapses
  the only case that could diverge.
- v2 replaced it with a forward scan for the first python-ish token, which is the
  historical defect's exact shape. This one DOES change the parse
  (`uv run pytest -k python` unwraps to `['python']`), and still the deny
  decision is identical on all six shapes, because three further conditions have
  to hold downstream.

**Response: drop the arm and record why.** The survival located the real
protection somewhere else — in a conjunction that a different arm already covers
and which died. The line stays, because it is reachable and correct; it is merely
masked today.

## F8 — the mutant survived because MY TEST COULD NOT FAIL

The fix added a `tool_name` check to a hook entry point. The test I wrote beside
it asserted `main(...) == 0`. But `main` returns 0 unconditionally, by design — a
hook exiting non-zero on its own confusion breaks every Bash call in the session.
So the assertion was true before the fix, after the fix, and under every mutation.

**Response: fix the test.** The observable that separates the behaviours is
whether anything is PRINTED, not the return code.

This is the class `kb-review` §4a rule 1 names, and it is invisible to everything
else: a review lane reads the test and it looks fine; a mutation sweep mutates
production code, so a test asserting nothing cannot be seen at all. **The arm is
the only instrument that finds it, and only because it survived.**

## The rule

A survivor asks a question; it does not answer one. Before treating it as a
missing test, construct an input where the mutant and the original differ **in
observable behaviour**, not just in tokens. Three outcomes are all legitimate:
the line is dead (delete it), the property is masked (record it), or your test is
decoration (fix it). Only the third is "write a better test", and it was the
minority here.

Related: a clean sweep is never evidence the change is correct. This round scored
11/11 before the cold lane ran the module and found four P1 defects — including
a quoted `'>'` denying an ordinary `grep`, and one `cd` bypassing the guard
entirely.
