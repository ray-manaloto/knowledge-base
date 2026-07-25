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

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import eval_cases, evals

if TYPE_CHECKING:
    import pytest

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
        "tier2.kb-retrieval",
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


# --- the tier-2 golden retrieval set ------------------------------------------


def test_the_retrieval_case_is_advisory_and_slow() -> None:
    """Both flags are decisions, not defaults, and both were locked 2026-07-25.

    ADVISORY because the baseline it exists to make citable is 0/119 relevant
    nodes (knowledge-base#12) and a floor of zero is the check that can only
    pass. SLOW because 18 queries each reload a ~350 MB graph, and a gate that
    takes minutes is one people learn to skip.
    """
    case = next(c for c in _cases() if c.name == "tier2.kb-retrieval")
    assert not case.gated
    assert case.slow
    assert not case.live


def test_the_retrieval_case_declares_a_control_arm_that_fails() -> None:
    """Not required for an advisory case — declared anyway, and it must work.

    The failure it defends against is the one that would silently invalidate
    every number this case prints: a matcher that counts a hit for a document
    the corpus does not contain.
    """
    case = next(c for c in _cases() if c.name == "tier2.kb-retrieval")
    assert case.control is not None
    assert case.control().verdict is evals.Verdict.FAIL


def test_the_golden_set_is_eight_pairs_plus_both_negatives() -> None:
    """Pinned by shape: a pair quietly losing a half stops measuring the gap."""
    queries = eval_cases.GOLDEN_QUERIES
    natural = [q for q in queries if q.phrasing is evals.Phrasing.NATURAL]
    echo = [q for q in queries if q.phrasing is evals.Phrasing.ECHO]
    absent = [q for q in queries if q.phrasing is evals.Phrasing.ABSENT]
    assert len(natural) == len(echo) == 8
    assert {q.topic for q in natural} == {q.topic for q in echo}
    assert len(absent) == 2


def test_the_two_negatives_probe_different_failures() -> None:
    """The two negatives probe different failures.

    Off-topic catches a corpus that answers anything at all; near-miss catches a
    sloppy matcher counting a lexically-adjacent document as a hit.
    """
    absent = {q.topic: q for q in eval_cases.GOLDEN_QUERIES if q.expects_absent}
    assert set(absent) == {"absent-off-topic", "absent-near-miss"}
    assert absent["absent-near-miss"].must_appear == (eval_cases.NEAR_MISS_TARGET,)


def test_no_golden_query_is_reused() -> None:
    """A duplicated query inflates the set without adding a measurement.

    The ABSENT rows are excluded on purpose: the near-miss negative REUSES the
    `beyond-similarity` question verbatim, because what it varies is the
    declared target, not the phrasing.
    """
    texts = [q.query for q in eval_cases.GOLDEN_QUERIES if not q.expects_absent]
    assert len(texts) == len(set(texts))


def test_every_golden_query_declares_a_target() -> None:
    """A query with no target scores 0/0 forever and reads as a real number."""
    naked = [q.topic for q in eval_cases.GOLDEN_QUERIES if not q.must_appear]
    assert naked == []


def test_the_node_line_parser_reads_a_real_graphify_line() -> None:
    """Captured verbatim from `graphify query` on 2026-07-25.

    The whole measurement rests on this regex: if it stops matching, every
    query returns an empty list, every recall is 0, and the harness reports a
    retrieval collapse that never happened.
    """
    line = "NODE Hook exit codes [src=code.claude.com_docs_en_hooks.md loc=L12 community=hooks]"
    match = eval_cases._NODE_LINE.match(line)
    assert match is not None
    assert match.group("src") == "code.claude.com_docs_en_hooks.md"


def test_the_node_line_parser_ignores_everything_else() -> None:
    """CONTROL ARM: a parser that matched every line would pass the test above."""
    for line in (
        "EDGE a --contains [EXTRACTED]--> b at=x.py:L1",
        "Traversal: BFS depth=2 | Start: ['x'] | 539 nodes found",
        "[!] TRUNCATED: showing 58 of 539 nodes",
        "",
    ):
        assert eval_cases._NODE_LINE.match(line) is None


def test_the_retrieval_case_skips_without_the_slow_flag() -> None:
    """It must not silently ride the free tier it was excluded from."""
    report = evals.run_cases(_cases())
    row = next(r for r in report.results if r.case.name == "tier2.kb-retrieval")
    assert row.outcome.verdict is evals.Verdict.SKIP
    assert "--slow" in row.outcome.detail


def test_the_real_offline_run_is_green_on_this_tree() -> None:
    """The live gate: this repo's own offline cases must pass here.

    Hides nothing — a SKIP is visible in the report, and an all-SKIP run exits
    non-zero by construction.
    """
    rc, report = evals.run(_cases(), live=False)
    assert rc == 0, report


def test_the_retriever_pins_the_query_to_this_repos_graph(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A bare `graphify query` resolves the graph against the process cwd.

    Caught in review of PR #30. The corpus stamp and the fixture-integrity scan
    both read `repo_root/graphify-out/graph.json`; if the query resolved
    somewhere else, the printed recall would carry a stamp for a corpus it was
    never measured against — exactly what the stamp exists to prevent. Binds the
    real argv, so a refactor that drops the flag fails here.
    """
    calls: list[tuple[list[str], object]] = []

    def fake_run(argv: Sequence[str], **kwargs: object) -> tuple[int, str]:
        calls.append((list(argv), kwargs.get("cwd")))
        return 0, "NODE Some label [src=wanted.md loc=L12 community=c]\nEDGE a --x--> b\n"

    monkeypatch.setattr(eval_cases.evals, "run_command", fake_run)
    retrieve = eval_cases._retrieval(tmp_path)
    rc, sources = retrieve(eval_cases.GOLDEN_QUERIES[0])

    assert rc == 0
    assert sources == ["wanted.md"]
    argv, cwd = calls[0]
    assert cwd == tmp_path
    assert "--graph" in argv
    assert argv[argv.index("--graph") + 1] == str(tmp_path / "graphify-out" / "graph.json")
