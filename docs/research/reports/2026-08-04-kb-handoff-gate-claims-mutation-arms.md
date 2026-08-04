# #147 mutation arms — gate-claim verification

**18 arms, 18/18 caught**, control green before and
restored green after. Harness: `PYTHONDONTWRITEBYTECODE=1`, anchors READ from the
file with a loud `DID NOT APPLY` on a miss, and pytest `rc=4` reported as
`SYNTAX ONLY` rather than as a catch.

Both tables below are **generated from the harness's own `ARMS` list** and
asserted row-for-row against the run log, per
`probes-need-a-control-arm.md` rule 8 — a transcribed evidence table has already
dropped a row and mislabelled two in this repo.

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
| verdict: pass a claim that names no commit | `handoff.py` | an unbound claim is unverifiable, not verified |
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
| verdict: pass a claim that names no commit | CAUGHT | rc=1, 1 failed, first: tests/test_handoff.py::test_a_claim_naming_no_commit_is_unverifiable |
| verdict: report a dirty-tree result as clean | CAUGHT | rc=1, 1 failed, first: tests/test_handoff.py::test_a_claim_recorded_over_a_dirty_tree_is_reporte |
| verdict: report an unbound row as verified | CAUGHT | rc=1, 1 failed, first: tests/test_handoff.py::test_a_claim_whose_row_could_not_read_head_is_unve |
| verdict: check every token, not just declared tasks | CAUGHT | rc=1, 1 failed, first: tests/test_handoff.py::test_a_token_that_is_not_a_declared_task_is_not_a_ |
| verdict: fold `no record` into `wrong` | CAUGHT | rc=1, 3 failed, first: tests/test_handoff.py::test_a_claim_with_no_record_at_that_commit_is_unve |
| RESTORED | GREEN | rc=0 |

## Three arms that first reported SURVIVED, and why each was the PROBE

Recorded because the count alone would have read as 15/18 unarmed code, and all
three were defects in the arm rather than in the subject
(`mutation-arms-are-a-floor-not-a-ceiling`).

1. **`rc=$?` digit rule.** The fixture was `` `out=$(pytest); rc=$?` `` — excluded
   by the `;` before `rc=`, never by the digit requirement. A fixture that
   cannot exhibit the harm. Replaced with `lint rc=$?`, where the task token is
   directly adjacent, and the arm caught.
2. **JSON shape guard.** The fixture `{"sha": "x", "gates": "lint"}` is caught by
   the PER-ROW check further down, so removing the shape guard changed nothing —
   a mutation masked by the next guard. Replaced with a record carrying no
   `gates` key at all, which has no row loop to reach.
3. **Null-rc branch.** The first mutation was `return None or "no result …"`,
   which is a no-op. The second targeted `if row.rc != claim.rc`, unreachable for
   `None` because the explicit branch above it returns first. The real arm
   deletes that branch — the realistic break, since it is the line a
   "simplification" would remove.

## GitHub repos touched

_None._ Every probe ran against this repository's own working tree.
