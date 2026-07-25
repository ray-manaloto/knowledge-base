"""Tests for this repo's eval cases (kb_setup.eval_cases).

The RUNNER is tested in `test_evals.py`. What is tested here is the CASES — and
above all that every gated one carries a control arm that really fails, because
that is the property the whole harness rests on and the one an author adding a
case will forget.

This file is the sibling of dotfiles' `tests/test_eval_cases.py` and did not
exist until #354 PR 3: KB declared cases and tested only the engine, so the
control-arm property was checked at `mise run eval` time and never at commit
time. That is the difference between a red gate and a red gate you understand.
"""

from __future__ import annotations

from pathlib import Path

from kb_setup import eval_cases, evals

_ROOT = Path(__file__).parent.parent.absolute()


def _cases() -> list[evals.Case]:
    return eval_cases.cases(_ROOT)


def test_every_gated_case_declares_a_control_arm() -> None:
    """Design principle 1, checked statically."""
    naked = [c.name for c in _cases() if c.gated and c.control is None]
    assert naked == [], f"gated cases with no control arm: {naked}"


def test_every_control_arm_actually_fails() -> None:
    """The load-bearing half — and the one that is easy to get wrong.

    A case can carry a control arm pointed at the wrong thing that comes back
    SKIP or PASS; then the case LOOKS armed and is still a coin with one face.
    This ran red on the first attempt here, because the obvious control for the
    graph canary (a graph path that does not exist) returns SKIP by design.
    """
    for case in _cases():
        if not case.gated or case.control is None:
            continue
        outcome = case.control()
        assert outcome.verdict is evals.Verdict.FAIL, (
            f"{case.name}: control arm returned {outcome.verdict.name}, not FAIL "
            f"— the probe cannot be shown to discriminate ({outcome.detail})"
        )


def test_the_expected_cases_are_declared() -> None:
    """A case silently disappearing is the inert declaration one level up."""
    assert {c.name for c in _cases()} == {
        "tier1.lanes-declared-or-degraded",
        "tier1.graphify-resolves",
        "tier1.graph-answers",
        "tier1.lane-health",
        "tier2.guard-fixtures",
    }


def test_only_the_doctor_case_is_live() -> None:
    """`doctor.sh` has NO offline mode — it is the live half, entirely.

    If another case is ever marked live, the offline gate gets cheaper by doing
    less, which is the wrong direction.
    """
    assert [c.name for c in _cases() if c.live] == ["tier1.lane-health"]


# --- the tier-2 fixture corpus ------------------------------------------------


def test_the_guard_corpus_carries_both_halves() -> None:
    """Stated here as well as enforced in the engine, because it is the point.

    The engine fails a single-direction table at run time; this says so at
    commit time, and names the reason a deny-only corpus is worthless: it grades
    the guard on the direction that has never failed.
    """
    denies = [f for f in eval_cases.GUARD_FIXTURES if f.expected is evals.Decision.DENY]
    allows = [f for f in eval_cases.GUARD_FIXTURES if f.expected is evals.Decision.ALLOW]
    assert denies, "no must-DENY rows"
    assert allows, "no must-ALLOW rows"


def test_every_fixture_row_says_what_it_defends() -> None:
    """A row whose `why` is empty is a string nobody can maintain."""
    silent = [f.command for f in eval_cases.GUARD_FIXTURES if not f.why.strip()]
    assert silent == [], f"fixture rows with no stated reason: {silent}"


def test_no_duplicate_fixture_commands() -> None:
    """A duplicated row inflates the corpus without adding coverage."""
    commands = [f.command for f in eval_cases.GUARD_FIXTURES]
    assert len(commands) == len(set(commands))


def test_the_measured_false_positives_are_pinned_as_allow_rows() -> None:
    """The two rows that were actually DENIED before the fix (2026-07-25).

    Pinned by content, not by count: a future edit that drops them would
    otherwise silently remove the only rows that have ever caught a real defect
    in this guard.
    """
    allow = {f.command for f in eval_cases.GUARD_FIXTURES if f.expected is evals.Decision.ALLOW}
    assert 'grep -rn "import graphify" python/' in allow
    assert 'rg "_merge_docs.py" .' in allow


def test_the_real_offline_run_is_green_on_this_tree() -> None:
    """The live gate: this repo's own offline cases must pass here.

    Hides nothing — a SKIP is visible in the report, and an all-SKIP run exits
    non-zero by construction.
    """
    rc, report = evals.run(_cases(), live=False)
    assert rc == 0, report
