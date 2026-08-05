---
type: "query"
date: "2026-08-05T23:13:48.589671+00:00"
question: "Can the currency stamp detect a derived view that is stale because nothing regenerated it, and what does kb-merge owe the stamp? (#181, #182)"
contributor: "graphify"
outcome: "useful"
---

# Q: Can the currency stamp detect a derived view that is stale because nothing regenerated it, and what does kb-merge owe the stamp? (#181, #182)

## Answer

The ticket's own specced fix was wrong, and only RUNNING it showed that. #182 proposed an ordering rule (a derived view older than the graph is stale by construction, called "a genuine ordering fact, not a proxy"). Implemented and run against the live corpus, its first output flagged GRAPH_REPORT.md, which graphify label writes 18.7s BEFORE the graph.json it exactly describes (12:12:07 vs 12:12:25) while graph.graphml was genuinely 11h behind. An ordering rule cannot separate those, because a run writes its outputs in some order and the primary is not always last. Replaced with provenance: the stamp records, per view, the graph fingerprint the view was last observed to be generated FROM. Stale is an equality, no clock. Generalises: a fingerprint answers "did it move", never "is it still true" - a view stale precisely BECAUSE nothing regenerated it never moves, so size:mtime_ns read OK for it forever. Also: a directory's mtime is not its content (it moves only when an entry is added or removed, measured both ways), and that blind spot SURVIVED the redesign because the replacement reused the same shallow primitive - a blind spot fixed at one layer reappears at the next layer that reuses it. Also: a remedy that does not clear the message it prints is the defect - the printed kb-artifacts ran, exited 0, restamped, and left all three views reading provenance unknown. Found only by running my own remedy and reading the output after. The cold cross-family review (codex, 2 rounds, 5 findings, 0 blocking) found 2 defects in my own fixes, including a FALSE PASS (views certified against a graph they predate, after a silently-failed best-effort restamp) and an inversion of a docstring I had written one commit earlier ("silence on this path is consent", implemented for one of the two silent states). Both hid because tests/test_currency_run.py stubs _run_one, so nothing exercised the wiring end to end. A mutation arm also DISPROVED a claim I had written as fact in a docstring.

## Outcome

- Signal: useful