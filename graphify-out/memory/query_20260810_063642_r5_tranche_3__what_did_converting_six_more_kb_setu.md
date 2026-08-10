---
type: "query"
date: "2026-08-10T06:36:42.117255+00:00"
question: "R5 tranche 3: what did converting six more kb_setup boundaries to the Result surface actually teach, beyond the mechanics?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Result", "Rc", "Ok", "Err", "External", "check_skill_lint", "check_md_budget", "check_skill_score", "record_baseline"]
---

# Q: R5 tranche 3: what did converting six more kb_setup boundaries to the Result surface actually teach, beyond the mechanics?

## Answer

Three things the recipe did not predict. (1) MOST OF THE SPLIT ALREADY EXISTED: md_budget, skill_lint and handoff each already had a pure check() -> Report walker plus an int-returning renderer, so R5 typed an existing seam rather than inventing one. That is why six modules fit in one tranche where two filled the last. (2) THE NEVER-ASKED GAP IS IN THREE PLACES AND ONE MODULE SAYS SO OUT LOUD: skill_lint returns Rc.NOT_RUN when its glob matches nothing, but md_budget (counted == 0) and distill (no transcripts) both return Rc.OK. distill PRINTS "the detector did not run. This is not a clean result" and still reports success -- the contradiction was already on stdout and invisible to every test. Filed as issue 270 and pinned by *_is_the_documented_divergence tests rather than fixed, because a conversion that also changes an rc destroys the regression arm it depends on. (3) THE CLOSED Ok GUARD CHANGED A DESIGN: skill_eval printed its score table and THEN returned 2 on a failed --write. Err carries a message not a table, and Ok(rc=BAD_REQUEST) is unrepresentable by construction, so that partial success could not be flattened -- it became two boundaries, check_skill_score and record_baseline. First time the type refused a shape rather than merely validating one. ALSO: the conversion denominator was wrong. An AST walk finds 95 functions annotated -> int (control: 0 unannotated of 887), but most are quantity-returners; the real surface is the ~35 functions cli.py dispatches to, of which 8 are now done. TWO CHEAP TRAPS: narrow on Ok never against Err, because Result has a third variant (External) with no .value and ty catches it; and a same-named test in two files can mis-target a mutation arm, so boundary tests are now module-prefixed. Finally, kb-arms --dry-run caught a stale anchor before the sweep ran -- the tranche-2 spec anchored on a line this split deleted and reported PROBE BROKEN rather than passing. Third recorded instance of a refactor invalidating a mutation spec.

## Outcome

- Signal: useful

## Source Nodes

- Result
- Rc
- Ok
- Err
- External
- check_skill_lint
- check_md_budget
- check_skill_score
- record_baseline