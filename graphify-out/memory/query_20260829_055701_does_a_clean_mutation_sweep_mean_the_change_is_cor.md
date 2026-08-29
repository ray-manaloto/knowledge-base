---
type: "query"
date: "2026-08-29T05:57:01.774219+00:00"
question: "Does a clean mutation sweep mean the change is correct?"
contributor: "graphify"
outcome: "corrected"
correction: "A CORRECTION. `next-ticket`'s STALE CHAIN preview shipped with a defect that a\n9/9 clean mutation sweep did not see, and the ARCHITECT'S SPEC caused it.\n\nThe spec said: when the entry after the stale one is also closed, \"chase onward\nto the first one that is not — a reader wants the real next task, not the next\npiece of rubbish.\" That sounds obviously right. It made the preview's CLOSED rule\nthe OPPOSITE of the naming rule: `_name` REFUSES a closed candidate, the preview\nSKIPPED one. With `[#1 CLOSED, #2 CLOSED, #3 OPEN]` the tool printed\n`next after removal: #3`; the reader removes #1 exactly as told, re-runs, and\ngets `STALE CHAIN — #2`. The refusal was right both times; the promise attached\nto it was not.\n\nTHREE THINGS THIS IS EVIDENCE FOR.\n\n1. A clean mutation sweep is a statement about the TESTS and never about the\n   PREMISE. The arms proved the chase step existed; no arm can ask whether the\n   step should exist. 9/9 died on the code carrying the defect.\n2. The cold lane found it by EXECUTING the module against a fixture rather than\n   reasoning about it — and control-armed the scope, confirming the two rules\n   agree when only one entry is closed. The same lane's Gemini sub-lane had\n   answered the same question \"no input combination exists\".\n3. A design instruction that sounds obviously right is exactly the shape that\n   ships unexamined. The fix is more useful than the chase ever was: name what\n   the next run will actually say, `#2 ... — also CLOSED, remove it too`, so the\n   reader cleans up both in one commit.\n\nALSO: fixing this promoted a line from untestable to load-bearing. The\nimplementer had honestly flagged `if ticket.issue == removed.issue: continue` as\nredundant-by-invariant — `removed` is always CLOSED, so the closed-skip below\nfiltered it anyway. Removing the closed-skip made it the only thing stopping\n`removed` being named as its own preview, and it became armable.\n"
---

# Q: Does a clean mutation sweep mean the change is correct?

## Answer

A CORRECTION. `next-ticket`'s STALE CHAIN preview shipped with a defect that a
9/9 clean mutation sweep did not see, and the ARCHITECT'S SPEC caused it.

The spec said: when the entry after the stale one is also closed, "chase onward
to the first one that is not — a reader wants the real next task, not the next
piece of rubbish." That sounds obviously right. It made the preview's CLOSED rule
the OPPOSITE of the naming rule: `_name` REFUSES a closed candidate, the preview
SKIPPED one. With `[#1 CLOSED, #2 CLOSED, #3 OPEN]` the tool printed
`next after removal: #3`; the reader removes #1 exactly as told, re-runs, and
gets `STALE CHAIN — #2`. The refusal was right both times; the promise attached
to it was not.

THREE THINGS THIS IS EVIDENCE FOR.

1. A clean mutation sweep is a statement about the TESTS and never about the
   PREMISE. The arms proved the chase step existed; no arm can ask whether the
   step should exist. 9/9 died on the code carrying the defect.
2. The cold lane found it by EXECUTING the module against a fixture rather than
   reasoning about it — and control-armed the scope, confirming the two rules
   agree when only one entry is closed. The same lane's Gemini sub-lane had
   answered the same question "no input combination exists".
3. A design instruction that sounds obviously right is exactly the shape that
   ships unexamined. The fix is more useful than the chase ever was: name what
   the next run will actually say, `#2 ... — also CLOSED, remove it too`, so the
   reader cleans up both in one commit.

ALSO: fixing this promoted a line from untestable to load-bearing. The
implementer had honestly flagged `if ticket.issue == removed.issue: continue` as
redundant-by-invariant — `removed` is always CLOSED, so the closed-skip below
filtered it anyway. Removing the closed-skip made it the only thing stopping
`removed` being named as its own preview, and it became armable.


## Outcome

- Signal: corrected
- Correction: A CORRECTION. `next-ticket`'s STALE CHAIN preview shipped with a defect that a
9/9 clean mutation sweep did not see, and the ARCHITECT'S SPEC caused it.

The spec said: when the entry after the stale one is also closed, "chase onward
to the first one that is not — a reader wants the real next task, not the next
piece of rubbish." That sounds obviously right. It made the preview's CLOSED rule
the OPPOSITE of the naming rule: `_name` REFUSES a closed candidate, the preview
SKIPPED one. With `[#1 CLOSED, #2 CLOSED, #3 OPEN]` the tool printed
`next after removal: #3`; the reader removes #1 exactly as told, re-runs, and
gets `STALE CHAIN — #2`. The refusal was right both times; the promise attached
to it was not.

THREE THINGS THIS IS EVIDENCE FOR.

1. A clean mutation sweep is a statement about the TESTS and never about the
   PREMISE. The arms proved the chase step existed; no arm can ask whether the
   step should exist. 9/9 died on the code carrying the defect.
2. The cold lane found it by EXECUTING the module against a fixture rather than
   reasoning about it — and control-armed the scope, confirming the two rules
   agree when only one entry is closed. The same lane's Gemini sub-lane had
   answered the same question "no input combination exists".
3. A design instruction that sounds obviously right is exactly the shape that
   ships unexamined. The fix is more useful than the chase ever was: name what
   the next run will actually say, `#2 ... — also CLOSED, remove it too`, so the
   reader cleans up both in one commit.

ALSO: fixing this promoted a line from untestable to load-bearing. The
implementer had honestly flagged `if ticket.issue == removed.issue: continue` as
redundant-by-invariant — `removed` is always CLOSED, so the closed-skip below
filtered it anyway. Removing the closed-skip made it the only thing stopping
`removed` being named as its own preview, and it became armable.
