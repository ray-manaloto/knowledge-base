---
type: "query"
date: "2026-08-07T22:35:03.781715+00:00"
question: "What must you do to a mutation-arm spec after refactoring the code it mutates?"
contributor: "graphify"
outcome: "useful"
---

# Q: What must you do to a mutation-arm spec after refactoring the code it mutates?

## Answer

Re-run the whole spec, because a refactor moves the lines the arms are matched against and a spec that no longer matches scores nothing while printing the same shape of report. Measured 2026-08-07: a 5-arm spec ran 5/5 DIED with the control holding, then ruff's C901 complexity limit forced check_many to be split into two helper functions, and two of the six patterns no longer existed in the file at all. kb_setup.arms is what makes this survivable - it reports a pattern that matches zero or two places as a distinct state rather than scoring it, and --dry-run re-checks every pattern against the files for free without running the suite. Run the dry-run after ANY edit to the mutated files, not just after an intentional refactor: the dangerous case is a formatter or a lint autofix moving a line you did not think you had touched. This is the same family as the bytecode-invalidation protection the module already carries - both failure modes produce a report that reads exactly like a successful run.

## Outcome

- Signal: useful