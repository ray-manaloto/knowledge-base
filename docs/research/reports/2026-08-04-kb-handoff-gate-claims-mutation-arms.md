# #147 mutation arms — gate-claim verification

**19 arms; 17 caught by single-site mutation.** Control green before
and restored green after. The 2 that survived are **one property guarded at
two sites**, and it IS armed — see the last section, which is the point of this
report rather than a footnote to it.

Harness: `PYTHONDONTWRITEBYTECODE=1` (CPython keys a `.pyc` on source size and
mtime in whole SECONDS, so a harness rewriting one file per second serves the
previous mutation's bytecode), anchors READ from the file with a loud
`DID NOT APPLY` on a miss, and pytest `rc=4` reported as `SYNTAX ONLY` rather
than as a catch.

Both tables are **generated from the harness's own `ARMS` list** and asserted
row-for-row against the run log, per `probes-need-a-control-arm.md` rule 8 — a
transcribed evidence table has already dropped a row and mislabelled two in this
repo.

## What each arm claims is load-bearing

| arm | file | the property it defends |
|---|---|---|
| block-binding: bind to every sha in the document | `citations.py` | a claim must not inherit a commit from another block |
| distributive: drop the colon anchor | `citations.py` | a trailing parenthetical must not introduce a task list |
| distributive: let it re-claim a task that has its own rc | `citations.py` | a direct rc wins; agreeing by luck is not verification |
| parser: read `all` as a task name | `citations.py` | `all rc=0` names no gate |
| parser: accept a branch name as a commit | `citations.py` | `Gates on `main`` binds a claim to nothing |
| parser: require a digit run after rc= | `citations.py` | `rc=$?` is prose about exit codes, not a claim |
| lookup: answer with a record from another commit | `gates.py` | a record at another commit never vouches for this one |
| lookup: resolve an ambiguous abbreviation by picking one | `gates.py` | answering an ambiguous prefix with either match is a guess |
| lookup: trust the JSON shape | `gates.py` | valid JSON is not a valid record |
| lookup: coerce an unknown dirty to False | `gates.py` | `could not ask` must not render as a clean tree |
| summarise: count an unrun gate as passed | `gates.py` | a `--stop` record cannot vouch for a green runner claim |
| verdict: skip the per-row commit binding | `handoff.py` | criterion 3 — a row recorded against another commit |
| verdict: drop the no-result branch and let != speak for it | `handoff.py` | `rc: null` is never a pass |
| verdict: pass a claim that names no commit (outer guard only) | `handoff.py` | NO-OP by construction — find_record's empty-sha guard still catches it |
| lookup: accept an empty sha and match every record | `gates.py` | an unbound claim must not match the first record in the directory |
| verdict: report a dirty-tree result as clean | `handoff.py` | a result over a dirty tree does not describe the commit |
| verdict: report an unbound row as verified | `handoff.py` | a row bound to no commit can vouch for none |
| verdict: check every token, not just declared tasks | `handoff.py` | `returns rc=127` is prose, and reporting it buries real findings |
| verdict: fold `no record` into `wrong` | `handoff.py` | a fresh clone has no records; that is not evidence of a lie |

## Run log, verbatim

| arm | outcome | detail |
|---|---|---|
| CONTROL (no mutation) | GREEN | rc=0 |
| block-binding: bind to every sha in the document | CAUGHT | rc=1, 2 failed, first: tests/test_citations.py::test_a_claim_does_not_inherit_a_commit_from_anot |
| distributive: drop the colon anchor | CAUGHT | rc=1, 1 failed, first: tests/test_citations.py::test_a_distributive_phrase_needs_its_colon - ... |
| distributive: let it re-claim a task that has its own rc | CAUGHT | rc=1, 1 failed, first: tests/test_citations.py::test_a_task_with_its_own_rc_is_not_claimed_twice |
| parser: read `all` as a task name | CAUGHT | rc=1, 5 failed, first: tests/test_citations.py::test_a_branch_name_is_not_a_commit - ValueErr... |
| parser: accept a branch name as a commit | CAUGHT | rc=1, 1 failed, first: tests/test_citations.py::test_a_branch_name_is_not_a_commit - Assertio... |
| parser: require a digit run after rc= | CAUGHT | rc=1, 1 failed, first: tests/test_citations.py::test_an_rc_with_no_number_is_not_a_claim - Va... |
| lookup: answer with a record from another commit | CAUGHT | rc=1, 1 failed, first: tests/test_gates.py::test_find_record_does_not_return_a_record_from_anoth |
| lookup: resolve an ambiguous abbreviation by picking one | CAUGHT | rc=1, 1 failed, first: tests/test_gates.py::test_find_record_refuses_an_ambiguous_abbreviation |
| lookup: trust the JSON shape | CAUGHT | rc=1, 2 failed, first: tests/test_gates.py::test_find_record_treats_a_record_with_no_gates_key_a |
| lookup: coerce an unknown dirty to False | CAUGHT | rc=1, 1 failed, first: tests/test_gates.py::test_a_record_round_trips_every_field_the_checker_re |
| summarise: count an unrun gate as passed | CAUGHT | rc=1, 1 failed, first: tests/test_handoff.py::test_a_runner_claim_fails_when_a_gate_was_never_re |
| verdict: skip the per-row commit binding | CAUGHT | rc=1, 1 failed, first: tests/test_handoff.py::test_a_row_recorded_against_a_different_commit_fai |
| verdict: drop the no-result branch and let != speak for it | CAUGHT | rc=1, 1 failed, first: tests/test_handoff.py::test_a_gate_recorded_as_not_run_never_passes_a_cla |
| verdict: pass a claim that names no commit (outer guard only) | SURVIVED | no test failed — the claim is unarmed |
| lookup: accept an empty sha and match every record | SURVIVED | no test failed — the claim is unarmed |
| verdict: report a dirty-tree result as clean | CAUGHT | rc=1, 1 failed, first: tests/test_handoff.py::test_a_claim_recorded_over_a_dirty_tree_is_reporte |
| verdict: report an unbound row as verified | CAUGHT | rc=1, 1 failed, first: tests/test_handoff.py::test_a_claim_whose_row_could_not_read_head_is_unve |
| verdict: check every token, not just declared tasks | CAUGHT | rc=1, 1 failed, first: tests/test_handoff.py::test_a_token_that_is_not_a_declared_task_is_not_a_ |
| verdict: fold `no record` into `wrong` | CAUGHT | rc=1, 3 failed, first: tests/test_handoff.py::test_a_claim_with_no_record_at_that_commit_is_unve |
| RESTORED | GREEN | rc=0 |

## The two SURVIVED arms are one property, guarded twice

`GateClaim.sha` returns `""` for a claim naming zero or two commits, and
`find_record` refuses an empty sha. Bypassing either guard alone leaves the
other standing, so **neither single-site mutation can discriminate** — which is
why both are reported here as survivors rather than quietly dropped.

Mutating **both** sites in one run, by hand:

```
BOTH-GUARDS ARM rc= 1 failures: 1
    FAILED tests/test_handoff.py::test_a_claim_naming_no_commit_is_unverifiable
```

So the property is armed. What the harness cannot show is that it takes two
edits to break it, and a count of "17/19" read without this section would
report defended code as unarmed.

## Four arms that first reported SURVIVED, and why each was the PROBE

Recorded because the count alone would have read as unarmed code, and all four
were defects in the arm rather than in the subject
(`mutation-arms-are-a-floor-not-a-ceiling`).

1. **`rc=$?` digit rule.** The fixture was `` `out=$(pytest); rc=$?` `` — excluded
   by the `;` before `rc=`, never by the digit requirement. A fixture that
   cannot exhibit the harm. Replaced with `lint rc=$?`, where the task token is
   adjacent, and the arm caught.
2. **JSON shape guard.** The fixture `{"sha": "x", "gates": "lint"}` is caught by
   the per-row check further down, so removing the shape guard changed nothing —
   a mutation masked by the next guard. Replaced with a record carrying no
   `gates` key at all, which has no row loop to reach.
3. **Null-rc branch.** The first mutation was `return None or "no result …"`,
   which is a no-op. The second targeted `if row.rc != claim.rc`, unreachable for
   `None` because the branch above it returns first. The real arm deletes that
   branch — the realistic break, since it is the line a "simplification" removes.
4. **Unbound claim.** The section above. Genuinely two guards, not a bad probe —
   but indistinguishable from one until the two-site arm was run.

Four stale anchors also reported `DID NOT APPLY` after the review round moved
the code. That is the harness working: every one was re-pointed by reading the
file, never by retyping the line.

## GitHub repos touched

_None._ Every probe ran against this repository's own working tree.

## Round 2 of the cold review: three more arms, at a later commit

**The 19-arm table above was measured at `1bdc64d`**, before the cold lane's two
rounds. It is left as measured rather than re-run, and this section states the
condition instead of letting the table quietly imply it covers later code.

Round 2's finding was that one of round 1's own fix-tests **could not fail** —
`test_a_row_with_an_empty_sha_is_unbound_at_the_point_of_use` went through
`gates.record()` → `find_record` → `_parse`, and `_parse` normalises `"" → None`
at read time, so the point-of-use predicate it claimed to pin never saw an empty
string. Reverting `not r.sha` to the pre-fix `r.sha is None` left it green. Its
docstring asserted it was hand-built on purpose; it was not. This is the
"fix surviving inside its own fix" pattern arriving in the TEST rather than in
the code, and no amount of code-side mutation could have surfaced it — only
mutating the fix and re-running its own test does.

Re-armed at `ed4e4e3`, all three by single-site mutation:

| arm | outcome |
|---|---|
| point-of-use empty-sha guard (the former tautology) | CAUGHT (rc=1) |
| a malformed `rc` rejects the whole record | CAUGHT (rc=1) |
| a same-task contradiction survives the distributive dedup | CAUGHT (rc=1) |

The first row is the one worth keeping: before the fix that same command
returned **rc=0**, which is what "a test that cannot fail" looks like from the
outside — indistinguishable from a passing suite.
