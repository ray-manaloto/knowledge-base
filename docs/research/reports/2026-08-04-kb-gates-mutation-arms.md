# kb-gates (#146) — 30 mutation arms, and the reviews that outran them

**Date:** 2026-08-04 · **Subject:** `python/src/kb_setup/gates.py`,
`python/src/kb_setup/pr.py`, `tests/test_gates.py`

A gate verified only on clean input is decoration
(`verify-before-advancing.md`). This is the FAIL direction of everything #146
adds: for each guarantee, a line-grained mutation that removes it, and the test
that must go red. Every arm deletes or inverts the **wiring that carries the
behaviour** — none renames a definition, because a renamed symbol still contains
the original as a substring and a substring check would pass while the probe,
not the gate, was the no-op.

The harness lives at `scratchpad/mutate.py` for this session only; the table
below is the durable record, and the rows under "What the harness found
about itself" are the reason it is worth committing rather than summarising.

## Results — 30/30 caught

Control row first: an unmutated `tests/test_gates.py` must be green, or every
"FAIL" below is indistinguishable from a broken harness.

| # | Mutation | Test that caught it | rc |
|---|---|---|---|
| — | **CONTROL (unmutated)** | whole file | **0** |
| 1 | stop-on-failure never engages (the flag becomes a no-op) | `test_run_with_stop_leaves_later_gates_unrun` | 1 |
| 2 | an unreached gate is DROPPED instead of recorded as not-run | `test_run_with_stop_leaves_later_gates_unrun` | 1 |
| 3 | a gate that never ran counts as passed | `test_a_gate_that_never_ran_has_not_passed` | 1 |
| 4 | the gate list is not validated against declared tasks | `test_undeclared_names_a_gate_this_repo_does_not_declare` | 1 |
| 5 | main refuses nothing — the undeclared check is dropped | `test_main_refuses_an_undeclared_gate_without_running_anything` | 1 |
| 6 | main exits 0 even when a gate failed | `test_main_exits_non_zero_when_a_gate_fails` | 1 |
| 7 | main never records (the run happens, the artifact does not) | `test_main_records_even_though_the_run_failed` | 1 |
| 8 | the record drops the per-gate sha and timestamp | `test_record_writes_every_field_the_ticket_names` | 1 |
| 9 | HEAD is read once for the run instead of per gate | `test_run_reads_head_per_gate_so_a_mid_run_amend_is_visible` | 1 |
| 10 | the mid-run HEAD drift is never reported | `test_render_flags_a_sha_that_moved_mid_run` | 1 |
| 11 | the runner captures output (criterion 8's live-output loss) | `test_run_invokes_the_gate_task_unwrapped` | 1 |
| 12 | ship ignores a refusal and ships anyway | `test_ship_gate_runner_refuses_an_undeclared_gate` | 1 |
| 13 | ship reports green while a gate failed | `test_ship_gate_runner_stops_and_still_records` | 1 |
| 14 | an unreadable HEAD no longer refuses (writes gates-.json) | `test_ship_gate_runner_refuses_an_unreadable_head` | 1 |
| 15 | an unknown flag is silently ignored | `test_main_refuses_an_unknown_flag` | 1 |
| 16 | the summary counts unrun gates without naming them | `test_render_names_unrun_gates_in_the_summary` | 1 |
| 17 | run_and_record stops recording (the sequence's one owner) | `test_ship_gate_runner_delegates_and_records` | 1 |
| 18 | the tree is always reported clean | `test_tree_dirty_reads_a_real_repo` | 1 |
| 19 | a failed git call reads as a clean tree | `test_tree_dirty_is_unknown_outside_a_repo` | 1 |
| 20 | the record drops whether the tree was dirty | `test_record_writes_every_field_the_ticket_names` | 1 |
| 21 | the dirty-tree caveat is never printed | `test_render_says_when_the_tree_was_dirty` | 1 |
| 22 | unknown cleanliness is silently treated as clean | `test_render_distinguishes_unknown_cleanliness_from_clean` | 1 |
| 23 | run() stops capturing the tree state | `test_run_records_whether_the_tree_was_dirty` | 1 |
| 24 | an interrupt discards the gates that already finished | `test_an_interrupt_still_records_the_gates_that_finished` | 1 |
| 25 | unreached gates are dropped instead of padded as not-run | `test_an_interrupt_still_records_the_gates_that_finished` | 1 |
| 26 | the record is written in place, truncating the previous one | `test_record_never_truncates_a_previous_record_in_place` | 1 |
| 27 | a failed atomic write leaves its temp file behind | `test_record_never_truncates_a_previous_record_in_place` | 1 |
| 28 | an empty per-gate HEAD read is stored as a real sha | `test_a_gate_whose_head_read_failed_is_not_bound_to_a_commit` | 1 |
| 29 | a completed gate bound to no commit is never reported | `test_a_gate_whose_head_read_failed_is_not_bound_to_a_commit` | 1 |
| 30 | a decode failure crashes instead of reporting unknown | `test_tree_dirty_is_unknown_when_git_output_cannot_be_decoded` | 1 |

Arms 1–20 are the original set; the rest were added by three successive review
passes (two-axis, then two cold rounds). **Nine arms had to be RE-POINTED** as
the code moved under them, and every one reported `MUTATION DID NOT APPLY`
rather than quietly passing — the guard doing its job, six separate times. The
fix that finally stuck was to build each anchor by READING the file instead of
retyping it, which is the generated-table lesson one level down.

**This table is GENERATED from the harness's own `ARMS` list**, not transcribed:
the script imports `mutate.py`, asserts every arm appears as caught in the run
log, and fails if the two disagree. A regex over a generator's source silently
dropped a row and mislabelled two on the #145 report; a hand-typed table is a
probe with no control arm.

## What the harness found about the CODE

**Arm 3 survived the first run.** A mutation changing `GateResult.passed` from
`self.rc == 0` to `self.rc in (0, None)` — "a gate that never ran counts as
passed" — passed every behavioural test in the file.

It was not a test that could be strengthened end-to-end. `stopped` is only ever
set *after* a gate fails, so today an unrun gate always travels beside a failing
one, and `all(r.passed for r in results)` is already False via **that** gate.
The property was defensive code carrying a docstring that asserted a contract
nothing in the system could exercise — a dead detector with a confident comment,
which is the shape this repo has paid for before.

Deleting it was the other option and is the wrong one: the next state that
produces an unrun gate *without* a preceding failure (a "not applicable here"
skip, say) would then pass silently. So the contract stays and is pinned
directly on the dataclass, the only level that can see it.

## What the harness found about ITSELF

**Arm 18 reported SURVIVED, and that was a false negative.** Applied by hand,
the identical mutation fails the identical test correctly (rc=1, with pytest
printing the rendered string that no longer contains "uncommitted").

The cause is in the harness, not the gate. CPython invalidates a cached `.pyc`
by comparing the source's **size and mtime in whole seconds**. This harness
rewrites one file many times inside a single second, so two different mutations
that happen to leave the file the same size reuse the first one's bytecode —
and the second arm silently runs the first arm's code. The fix is to clear every
`__pycache__` and set `PYTHONDONTWRITEBYTECODE=1` per arm.

**This was not a discovery — it was a REGRESSION of a lesson already written
down.** `2026-08-04-kb-handoff-check-mutation-arms.md`, committed hours earlier
for #145, says in its own index entry that it "clears every `__pycache__` per arm
because CPython invalidates on `(mtime, size)`, so a line-swap mutation is
otherwise served stale bytecode and reports a false pass". This harness was
written fresh and did not carry that forward. The first draft of this section
claimed the defect "would corrupt any mutation harness in this repo, including
the one committed for #145"; that is false, #145's harness handles it, and the
claim was removed on checking rather than left to read as a finding.

Two lessons:

1. **A mutation harness needs a control arm of its own.** Cross-checking a
   surprising result by a second route — applying the mutation by hand — settled
   which side was broken in about a minute, and it was the probe. A `SURVIVED`
   row is not evidence of a blind test until it has been reproduced by hand.
2. **A lesson recorded in a report is not a lesson carried into the next
   harness.** The prior harness is one directory over and already had the fix;
   nothing made re-deriving it necessary except not looking. If a third harness
   is written, it should import this one rather than restate it.

Two further arms reported `MUTATION DID NOT APPLY` on an intermediate run, when
the `dirty` field landed between the lines they anchored on. That is the harness
working — it refuses to score an arm it could not apply, rather than reporting a
pass — and it is the reason each arm asserts its `old` string matches exactly
once before running anything.

## What the first 20 arms did NOT catch — the review round

Two review axes ran after the first 20 arms were green. Both found real defects, and the
sharpest one was a **blind test inside this very suite**, which is worth stating
plainly given what this document is about.

**A test that could not fail.** `test_render_names_the_unrun_gates` asserted
`"gamma" in out`. `render` emits a per-gate row for every result, so that string
is present no matter what the summary says — dropping the named list from the
summary passed all 42 tests. The standards lane mutated the clause, showed the
survival, and ran a control arm proving its probe discriminated. Re-confirmed
here before fixing. **The first 20 arms had no row for that clause**, which is how
a suite full of control arms still shipped one assertion that could only pass.
Now an arm of its own, and the test asserts on the summary line rather than the whole output.

**A guard enforced in one of two callers.** `gates.main` refused an unreadable
HEAD; `pr.run_gates` open-coded the same sequence and did not, so a ship with an
unreadable HEAD would write `gates-.json` carrying `"sha": ""` — a file that
reads as a gate record and names no commit, the exact artifact #146 exists to
abolish. Found *independently by both lanes*. The standards lane also named the
cause: the two callers duplicated the five-step sequence, and the commit message
had claimed delegation made them "the same numbers read once — they cannot
disagree", which was true of the loop and false of the sequence around it. Fixed
by extracting `run_and_record`, so the invariant has one home.

**A silently swallowed flag.** `--stopp` was dropped from the task list by the
`startswith("-")` filter *and* failed the `--stop` test, so the run took the
opposite position of the only flag the command has and exited 0/1 as though that
had been asked for. Now rc 2, which the module already reserved for a request it
cannot honour.

The general lesson: **mutation arms only cover the claims you thought to
mutate.** Every arm here passed, and a second reader still found an assertion
that could not fail. Arms are a floor, not a ceiling.

## What the review round did NOT catch either — the cold lane

A third pass, `kb-review`'s one cold cross-family lane (codex/GPT-5.6 Sol, by
ref, no design context), over code that was by then green on 23 arms, 45 tests
and two review axes. It found two more, both P2, and both the same shape: the
gate LOGIC was correct and the ARTIFACT was not durable — which is the only
thing this module exists to produce.

**Ctrl-C discarded every completed gate.** `record()` ran once, after `run()`
returned in full. `KeyboardInterrupt` is a `BaseException`, caught by nothing,
so an interrupt partway through a four-minute run propagated out of the
result-building loop and took the finished gates' evidence with it — no record
at all. The likeliest way a real run ends early, arriving through the door
nobody watched. `run()` is now a generator (`iter_run`) so the caller holds what
it already has, and `run_and_record` records in a `finally`, padding the
unreached gates as `rc: null` rather than leaving a short list that would read
as a complete run.

**The write truncated the previous record in place.** `Path.write_text`
truncates first, and `record()` overwrites a prior record for the same commit by
design — so an interrupt or a full disk mid-write destroyed a good record and
left unparsable bytes where it had been. This repo already had the fix and the
language for it: `skill_eval._atomic_write`, temp-then-rename, with a docstring
explaining exactly this failure. The new writer simply did not use it. It now
lives in `kb_setup.atomic` with both callers, which is what this repo's
two-callers-earn-a-module rule is for.

**A lint rule tried to reintroduce the first bug.** `ruff`'s PERF402 wanted
`results = list(...)` in place of the accumulate-then-`extend`. They look
interchangeable and are not: `list()` builds its own list and binds it only on
success, so an interrupt leaves the accumulator empty and the `finally` records
nothing. The tidier spelling *is* the bug. `extend` retains what was already
yielded — and because that retention is load-bearing, it is pinned by a test
rather than assumed from interpreter behaviour.

**Three arms were rejected by the harness before they could lie.** One anchored
on a line the fix had moved; one "caught" its target only by breaking SYNTAX, so
pytest exited 4 on a collection error and proved nothing about the test; one
failed twice more because a comment sits between the anchor lines. The fix for
the last was to build the anchor by READING the file rather than retyping it —
the same lesson as the generated table, one level down.

## Round 2 of the cold lane — and the SHA I fabricated

The bound is two rounds, so this was the last. Over code green on 27 arms, 48
tests and three prior passes, it found **eight more** (7 P2, 1 P3) — and caught
an error of mine before the gate could.

**I fabricated a full SHA.** The report save-path I handed the lane named
`db0a770a4d4bfbf3aa60bc4b6a56aad5faf1e2fc`, a commit that does not exist: I
extended the 7-char prefix `db0a770` into a plausible-looking 40 rather than
reading `git rev-parse HEAD`. The lane checked with `git cat-file -t`, said so
first, and saved a correctly-named copy alongside. Had it not, the receipt would
have refused for "the lane left no report" — a gap wearing a typo's clothes.
This is `a-line-number-is-a-measurement` with 33 more characters: a SHA is read,
never composed.

The eight, condensed:

- **A transiently-empty per-gate HEAD read became a passing row bound to nothing.**
  `run_and_record` guards HEAD once before the loop; `iter_run` re-read it per
  gate with no guard, and `render`'s drift check filters falsy shas *by design* —
  so a `0` exit code was recorded against `""` and nothing said so. Now `None`
  (the same three-state shape as `dirty`) with a `bound_to_a_commit` report.
- **The `finally` padding called the in-flight gate "never invoked".** True for a
  gate the run never reached, false for the one that was running when the
  interrupt landed. They are genuinely indistinguishable from there, so the fix
  was to weaken the *claim* — `ran` now means "produced a result" — rather than
  assert a stronger one that is sometimes false.
- **The paired test asserted that same false contract**, which is why the
  implementation and its test agreed: both were consistent with a wrong claim.
- **`atomic.write_text`'s temp name was per-destination, not per-process.**
  Correctly labelled PRE-EXISTING — inherited verbatim from `skill_eval` — but
  the extraction gave it a second caller whose concurrent case (two `kb-gates`
  runs at one commit) is plausible, so it is fixed rather than carried forward.
- **`tree_dirty` did not catch `UnicodeDecodeError`** (P3). `text=True` decodes
  inside `subprocess.run`, and a `ValueError` is neither `OSError` nor
  `SubprocessError` — so a non-UTF-8 path raised straight past a handler whose
  whole contract is to return "unknown" instead of raising.
- **Three doc defects, all mine.** `agent-artifact-conventions.md` glossed
  `dirty` with **inverted polarity** ("was the tree clean") on the very field
  added to stop a false reading; `ci-local-parity.md` named `gates.run` +
  `gates.record` when both callers use `run_and_record`, inviting a maintainer to
  open-code the two-call form and lose the interrupt-safe recording; and
  `clear-prep`'s self-verify checked only the top-level `sha` when the format
  explicitly lets each row carry its own `sha` and `dirty`.

**The pattern across four passes.** Twenty arms, then a two-axis review, then two
cold rounds — each found real defects the previous had been green over, and the
later ones were increasingly about the *artifact* rather than the logic. Arms
prove the claims you thought of; a different reader finds the claims you did not.
Three of the last eight were prose that would have actively misled someone.

## Reproduction

```bash
uv run python <scratchpad>/mutate.py    # 30/30 arms caught, restored tree green
uv run pytest tests/test_gates.py -q    # 52 passed
```

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the subject; `kb_setup.gates`, `kb_setup.pr` and their tests.
