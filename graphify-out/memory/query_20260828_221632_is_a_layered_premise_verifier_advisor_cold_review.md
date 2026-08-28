---
type: "query"
date: "2026-08-28T22:16:32.493362+00:00"
question: "Is a layered premise-verifier/advisor/cold-review flow worth it for a single small module?"
contributor: "graphify"
outcome: "corrected"
correction: "A layered pre-dispatch review is not ceremony; each lens caught a defect the\nothers structurally could not.\n\n- The PREMISE VERIFIER found both clear-prep skill copies pinned at exactly\n  500/500 lines, zero headroom, mirror byte-enforced. A naive edit would have\n  failed lint twice at ship time. It also measured that `gh api graphql`\n  returns rc 0 with parseable JSON on a partial failure, which refuted my own\n  fail-closed rule (\"any non-parse is UNVERIFIABLE\") before a lane implemented\n  it.\n- The ADVISOR found that my test instruction would have left the classifier\n  untested: substituting above the response classifier makes every assertion\n  pass while the branch that matters never runs. Green fixtures around dead\n  detection.\n- MY OWN diff read caught the lane silently killing `$ARGUMENTS` while the\n  skill still advertised taking one.\n- The COLD REVIEW found the rc != 0 branch discarding gh's error text, against\n  the sibling it claimed to mirror.\n\nAnd the fix for that last one ARRIVED UNARMED: the existing test constructed\nthe error object directly, so it exercised the renderer, not the branch.\nReverting the fix broke nothing until a new assertion was added. A fix whose\nown test cannot fail is decoration — the arm is not optional, it is the fix.\n"
---

# Q: Is a layered premise-verifier/advisor/cold-review flow worth it for a single small module?

## Answer

A layered pre-dispatch review is not ceremony; each lens caught a defect the
others structurally could not.

- The PREMISE VERIFIER found both clear-prep skill copies pinned at exactly
  500/500 lines, zero headroom, mirror byte-enforced. A naive edit would have
  failed lint twice at ship time. It also measured that `gh api graphql`
  returns rc 0 with parseable JSON on a partial failure, which refuted my own
  fail-closed rule ("any non-parse is UNVERIFIABLE") before a lane implemented
  it.
- The ADVISOR found that my test instruction would have left the classifier
  untested: substituting above the response classifier makes every assertion
  pass while the branch that matters never runs. Green fixtures around dead
  detection.
- MY OWN diff read caught the lane silently killing `$ARGUMENTS` while the
  skill still advertised taking one.
- The COLD REVIEW found the rc != 0 branch discarding gh's error text, against
  the sibling it claimed to mirror.

And the fix for that last one ARRIVED UNARMED: the existing test constructed
the error object directly, so it exercised the renderer, not the branch.
Reverting the fix broke nothing until a new assertion was added. A fix whose
own test cannot fail is decoration — the arm is not optional, it is the fix.


## Outcome

- Signal: corrected
- Correction: A layered pre-dispatch review is not ceremony; each lens caught a defect the
others structurally could not.

- The PREMISE VERIFIER found both clear-prep skill copies pinned at exactly
  500/500 lines, zero headroom, mirror byte-enforced. A naive edit would have
  failed lint twice at ship time. It also measured that `gh api graphql`
  returns rc 0 with parseable JSON on a partial failure, which refuted my own
  fail-closed rule ("any non-parse is UNVERIFIABLE") before a lane implemented
  it.
- The ADVISOR found that my test instruction would have left the classifier
  untested: substituting above the response classifier makes every assertion
  pass while the branch that matters never runs. Green fixtures around dead
  detection.
- MY OWN diff read caught the lane silently killing `$ARGUMENTS` while the
  skill still advertised taking one.
- The COLD REVIEW found the rc != 0 branch discarding gh's error text, against
  the sibling it claimed to mirror.

And the fix for that last one ARRIVED UNARMED: the existing test constructed
the error object directly, so it exercised the renderer, not the branch.
Reverting the fix broke nothing until a new assertion was added. A fix whose
own test cannot fail is decoration — the arm is not optional, it is the fix.
