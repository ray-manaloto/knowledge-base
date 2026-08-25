---
type: "query"
date: "2026-08-25T05:01:42.769964+00:00"
question: "What did the cold review of the 18 unshipped commits find, and what was done about it?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the cold review of the 18 unshipped commits find, and what was done about it?

## Answer

The cold cross-family review of the 18 unshipped commits on
`corpus-partial-merge-20260823` (base `408593510b06`, 186 files, +5,943/-18,705)
found THREE BLOCKING defects, and all three were in ONE module —
`kb_setup.graphify_native_extract`, the newest and largest new code on the branch,
and the module Ray's own ranking already marks a STOPGAP for the SDK path.

The three, each confirmed by constructing the case that produces it rather than by
reading the code and agreeing with it:

1. `_parse` takes the token after `--out` as its value without asking whether that
   token is a flag. `--out --dry-run` therefore sets `dry_run=False` and runs a
   REAL, token-spending extraction into a directory named `--dry-run`. Control arm:
   `--dry-run` alone still parses True.
2. `_refuse_out` guards the `--out` FLAG, but `graphify/paths.py:26` reads
   `GRAPHIFY_OUT` from the environment and `clean_env()` passes it through, so the
   output root relocates without meeting the guard. Armed end to end.
3. `_run_real`/`_run_cluster` — the only functions that spawn the subprocess — have
   ZERO coverage. Stubbing both to `return 0` leaves all 42 tests green.

Ray's disposition was PARK, not fix: remove the CLI subcommand and the mise task
together so the defective paths are unreachable, leave the module and its tests as
groundwork, and file the defects (#479/#480/#481). Rationale: the blast radius was
confined to a module already ranked temporary, and the other 15 commits carried
zero blocking findings, so hardening a stopgap would have been the expensive
answer.

Two process findings worth more than the defects:

* A lane that returns "NO FINDINGS" with no citations has not demonstrated it read
  anything. The first batch-A lane returned four bullets ending "the code is robust
  and functions as described" — it had been told NOTHING about what the change was
  for, so "as described" was pure happy-path confirmation. Rejected and re-dispatched
  to a different family WITH a hard citation requirement; the same 1,155 lines then
  yielded all three blockers. The difference was entirely whether citations were
  demanded.
* Round 2 found three things and TWO were in round 1's own work: a parking claim
  wider than the truth, and a set of line citations that round 1's own commit had
  invalidated by inserting 25 lines above them.


## Outcome

- Signal: useful