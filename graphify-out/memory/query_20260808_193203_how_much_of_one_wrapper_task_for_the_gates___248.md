---
type: "query"
date: "2026-08-08T19:32:03.841399+00:00"
question: "How much of one-wrapper-task-for-the-gates (#248) is already native in mise, and where does the wall clock actually go?"
contributor: "graphify"
outcome: "useful"
---

# Q: How much of one-wrapper-task-for-the-gates (#248) is already native in mise, and where does the wall clock actually go?

## Answer

249s to 61s (3.95x), and the ticket's own premise was refuted by its own measurement. Of the 249s baseline, the test gate alone was 219.2s (88%), so parallelising the four GATES has a ceiling of 12%. The real term was the single-process suite: 2,059 tests over 71 files with a long tail, which pytest-xdist -n auto took to 57s with ZERO test changes. Both runs emitted exactly 2,059 progress characters, which is the control arm against xdist quietly collecting less. -n auto lives on the mise task, not in addopts, so a one-test debugging run stays serial and keeps its traceback.

Native research first, probed against the INSTALLED mise 2026.8.3 rather than docs: depends runs deps in PARALLEL, a failing dep CANCELS its running siblings, the rc is the failing task's own, -c is report-everything, and wait_for orders a task only when the other is also running. Exactly one thing is missing and it is the whole reason kb_setup.gates exists: mise surfaces per-task results only as stderr prose and -o has no structured form, so a depends wrapper collapses four gates into one exit code. That is the citable justification for keeping the fan-out custom.

Concurrency is BATCHED and fail-CLOSED: consecutive CONCURRENT_SAFE gates share a batch, everything else runs alone. The four were cleared by measurement, not reasoning - find -newer over a real run showed lint writing .rumdl_cache and test writing .pytest_cache, disjoint, no tracked files.

Three defects, all in code this round wrote, and none findable by reading:

1. Concurrency broke a line nobody edited. The padding tasks[len(results):] was correct only while results arrived in requested order.
2. in_requested_order keyed positions by LAST occurrence, so a non-adjacent repeat sorted its first row to the back. All eleven concurrency tests used ADJACENT repeats, the one case where first-write and last-write agree, so the 7/7 mutation sweep was green over that exact line.
3. The HIGH: as_completed stopped handing over results when an exception left the loop, but the pool waited for the siblings anyway, so gates that RAN TO COMPLETION were recorded rc None, the state meaning did not run. The module's own purpose inverted, reachable on the ship path. The test standing there ASSERTED the bug - it called lint unrun while its own 1.01s runtime was lint's sleep.

Two lessons that outlive the round. First, giving the review lane a MUTATING instruction is what found all of it; every one of these was invisible to reading and to mutation sweeps of production code. Second, an arm that SURVIVES can be the finding: the revert-the-sweep arm survived because the sweep guards a main-thread Ctrl-C, a shape no test had constructed, while the round-2 case actually needed future.exception(). Three shapes, three mechanisms, one arm each. Final: 11/11 arms died, 1/1 control held.

One honest regression, stated rather than discovered later: all four GATE_TASKS are concurrency-safe so they form ONE batch, and stop_on_failure now skips nothing. A ship whose lint fails goes from about 12s to about 61s. Still far better than the 249s sum, but it is a loss in the case the flag is named for, and the right fix if it ever bites is a smaller batch, never a cancel loop that cannot fire.

## Outcome

- Signal: useful