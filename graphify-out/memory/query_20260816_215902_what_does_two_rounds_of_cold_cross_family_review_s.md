---
type: "query"
date: "2026-08-16T21:59:02.554582+00:00"
question: "What does two rounds of cold cross-family review say about where defects concentrate?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does two rounds of cold cross-family review say about where defects concentrate?

## Answer

Two rounds of one cold cross-family review found **12 findings, 5 of them P1**,
and the distribution is the lesson rather than the count.

**Three of round 2's four P1s were inside the commit written to fix round 1.**
Fix code arrives wearing a finding's authority, is written by whoever already
misunderstood the area once, and is the least-reviewed code in the diff. Two
concrete shapes, both observed here:

* The round-1 fix moved an unlink into a `finally` to stop a stranded `O_EXCL`
  marker cascading — and the case it was written for never enters that function,
  because a chunk whose provider call FAILS never reaches the callback at all.
  The fix was correct about the mechanism and wrong about the path.
* The round-1 fix added a resume skip that returned early WITHOUT rotating the
  evidence, reintroducing the very cascade a neighbouring fix had just closed.

**A finding is a SAMPLE of a class, not an instance.** Round 1's P1 was the slice
module's `SOURCE_PATH` leaking into the corpus path via a shared reduction. That
was fixed, and nothing else was looked at — so round 2 found `_model_reasons`
doing the identical thing with the slice's MODEL constants, which would have made
the adapter reject every corpus chunk as `model-identity-invalid`. The correct
response to the second instance was a sweep of every slice constant reachable
from a corpus call, which is a checkable claim; fixing the instance is not.

**An arm written alongside its fix routinely cannot fail, and a mutation sweep
cannot see that.** The first attempt at arming the round-1 P1 passed with the fix
fully reverted: the tests exercised the two reduction FUNCTIONS and never the
driver's CHOICE between them. Only reverting the fix and watching for red exposed
it. The replacement discriminates on which of two error messages the driver
reaches — fixed, it dies on absent adapter metadata; reverted, on fragment scope.

**Prose defending a choice disarms the next reader, including its author.** The
export comment read "one definition ... so a second reduction cannot quietly
disagree" — true of the reduction and false of the scope it hardcoded. Nobody
re-reads a comment they agree with, which is why the defect survived to a
reviewer with no stake in the reasoning.

**A docstring that describes a guard which no longer exists is the same failure
in slow motion.** After round 1 the module docstring still claimed single fixed
marker paths and "deliberately no skip-if-staged check"; both had just become
false. Correcting prose is part of the fix, not bookkeeping after it.


## Outcome

- Signal: useful