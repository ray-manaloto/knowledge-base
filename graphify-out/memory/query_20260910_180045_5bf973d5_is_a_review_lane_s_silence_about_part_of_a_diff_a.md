---
type: "query"
date: "2026-09-10T18:00:45.652502+00:00"
question: "Is a review lane's silence about part of a diff a caveat to note or a defect to prevent?"
contributor: "graphify"
outcome: "corrected"
correction: "The belief was that a review lane's silence about part of a diff is a COVERAGE\nCAVEAT to note afterwards. It is not — it is a SCOPE DEFECT to prevent, and the\ndifference is what the caveat costs.\n\nTwo lanes failed this way on one day, and they are not equally dangerous:\n\n- one said *\"no tests included or modified\"* — a QUIET omission, which invites a\n  second look and is what the existing rule anticipates;\n- the other asserted *\"the code is completely missing\"* with a confidence marker,\n  as its HEADLINE. Acted on, that says the branch is empty prose. A confident\n  false negative is not a weaker version of a quiet one; it is the opposite\n  failure, because it terminates the reader's inquiry instead of prompting it.\n\nThe fix is not vigilance. `kb-review` now excludes `mise.lock` and `uv.lock`\nalongside the prose exclusion AND tells the lane one was withheld — an\nunexplained gap is something a reviewer reasons about; an explained one it can\nset aside. Both halves went into the PROMPT TEMPLATE, not only the skill prose,\nbecause `lanes.md` already records THREE occasions where a lesson reached\nSKILL.md and not the prompt anyone copies.\n\nMeasured: re-running with the exclusion took the lane from 116,172 input tokens\nto 19,235, and it then found six real defects including one that let the new gate\nreport a CRASHED tool as a clean result. The same lane, the same commit, the same\nmodel — only the scope changed.\n"
---

# Q: Is a review lane's silence about part of a diff a caveat to note or a defect to prevent?

## Answer

A review lane's input SCOPE decides whether the review happens at all — and a
generated artifact silently spends the whole budget.

A branch whose real change was one module, one test file and a two-line config
edit was piped to a cold lane with only the `docs/research/**` exclusion:

    total piped        473,216 bytes
    mise.lock           21,716 -> 451,607   = 91%
    mise.toml          451,607
    lock_drift.py      455,990
    test_lock_drift.py 468,478

The lane reported, THREE TIMES and marked `CONFIRMED-FROM-DIFF`, that the check's
code was *"completely missing from this diff"*. It was not; it was past 430 KB of
machine-resolved checksums.


## Outcome

- Signal: corrected
- Correction: The belief was that a review lane's silence about part of a diff is a COVERAGE
CAVEAT to note afterwards. It is not — it is a SCOPE DEFECT to prevent, and the
difference is what the caveat costs.

Two lanes failed this way on one day, and they are not equally dangerous:

- one said *"no tests included or modified"* — a QUIET omission, which invites a
  second look and is what the existing rule anticipates;
- the other asserted *"the code is completely missing"* with a confidence marker,
  as its HEADLINE. Acted on, that says the branch is empty prose. A confident
  false negative is not a weaker version of a quiet one; it is the opposite
  failure, because it terminates the reader's inquiry instead of prompting it.

The fix is not vigilance. `kb-review` now excludes `mise.lock` and `uv.lock`
alongside the prose exclusion AND tells the lane one was withheld — an
unexplained gap is something a reviewer reasons about; an explained one it can
set aside. Both halves went into the PROMPT TEMPLATE, not only the skill prose,
because `lanes.md` already records THREE occasions where a lesson reached
SKILL.md and not the prompt anyone copies.

Measured: re-running with the exclusion took the lane from 116,172 input tokens
to 19,235, and it then found six real defects including one that let the new gate
report a CRASHED tool as a clean result. The same lane, the same commit, the same
model — only the scope changed.
