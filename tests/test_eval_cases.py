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

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import eval_cases, evals, prose

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
    graph = tmp_path / "graphify-out" / "graph.json"
    retrieve = eval_cases._retrieval(tmp_path, graph)
    rc, sources = retrieve(eval_cases.GOLDEN_QUERIES[0])

    assert rc == 0
    assert sources == ["wanted.md"]
    argv, cwd = calls[0]
    assert cwd == tmp_path
    assert "--graph" in argv
    assert argv[argv.index("--graph") + 1] == str(graph)


def test_each_arm_reads_its_own_corpus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CONTROL ARM for the whole before/after: three arms, and no two are the same run.

    If two arms resolved the same corpus with the same retriever the report would
    still print a table, a SUITE line per arm and a DELTA of zero — a before/after
    that structurally cannot show a difference. So what each arm actually does is
    bound here.

    The P1 arm differs from the other two along the OTHER axis: it reads the same
    file as `prose` but does not shell out at all, which is why it must not
    appear in ``seen``. Scoping and scoring are separate changes, and an arm that
    quietly re-ran graphify would report P0's number under P1's name.
    """
    seen: list[str] = []

    def fake_run(argv: Sequence[str], **_kwargs: object) -> tuple[int, str]:
        seen.append(argv[argv.index("--graph") + 1])
        return 0, "NODE L [src=wanted.md loc=L1 community=c]\n"

    monkeypatch.setattr(eval_cases.evals, "run_command", fake_run)
    arms = eval_cases._retrieval_arms(tmp_path)
    for arm in arms:
        arm.retrieve(eval_cases.GOLDEN_QUERIES[0])

    assert [a.name for a in arms] == [
        eval_cases.UNSCOPED_ARM,
        eval_cases.PROSE_ARM,
        eval_cases.IDF_ARM,
    ]
    # Only the two graphify-backed arms shell out, and they name different graphs.
    assert seen == [
        str(tmp_path / "graphify-out" / "graph.json"),
        str(tmp_path / "graphify-out" / prose.PROSE_GRAPH_NAME),
    ]


def test_the_lexical_arm_reports_a_real_rc_when_it_cannot_read_its_corpus(tmp_path: Path) -> None:
    """The P1 arm's ``rc`` must be earned, not hardcoded.

    It is the first arm whose retriever does not shell out, so `_arm_defect`'s
    ``rc != 0`` check has no subprocess exit code to inherit — and a check that
    cannot fire is not a check. Here the prose graph does not exist, which is a
    genuinely reachable state (the graphs are gitignored and derived), and the
    arm must surface it rather than reporting an honest-looking empty result.
    """
    retrieve = eval_cases._LexicalRetriever(tmp_path / "graphify-out" / prose.PROSE_GRAPH_NAME)
    rc, returned = retrieve(eval_cases.GOLDEN_QUERIES[0])
    assert rc == eval_cases._LexicalRetriever.UNREADABLE
    assert rc != 0
    assert returned == []


def test_the_lexical_arm_builds_its_index_once_across_queries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """18 queries, one index build. Rebuilt per query, the arm would time JSON parsing."""
    graph = tmp_path / "prose.json"
    graph.write_text(
        json.dumps({"nodes": [{"id": "a", "label": "alpha beta", "source_file": "a.md"}]}),
        encoding="utf-8",
    )
    builds = 0
    real_load = eval_cases.lexical.load_index

    def counting_load(path: Path) -> object:
        nonlocal builds
        builds += 1
        return real_load(path)

    monkeypatch.setattr(eval_cases.lexical, "load_index", counting_load)
    retrieve = eval_cases._LexicalRetriever(graph)
    for query in eval_cases.GOLDEN_QUERIES[:3]:
        retrieve(query)
    assert builds == 1


def test_every_arm_carries_its_own_membership_oracle() -> None:
    """Fixture rot is per-corpus: a target dropped by scoping is rot in that arm.

    Shared, the prose arm would be checked against the full graph, where every
    target trivially exists — so a positive target the scoping filter removed
    would report recall 0 forever and read as a retrieval failure.
    """
    arms = eval_cases._retrieval_arms(Path("/nonexistent"))
    assert all(arm.present is not None for arm in arms)


def test_the_retrieval_case_skips_when_the_prose_graph_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A half-present pair of corpora must skip the case, never drop the arm.

    Dropping it would print the baseline alone under a report still shaped like
    a before/after — which reads as "scoping changed nothing".

    The CLI gate is PINNED. `_retrieval_precondition` checks for graphify first,
    so on a host without it the SKIP that comes back is the install one — a
    green assertion here would then be measuring the wrong absence entirely
    (caught in review of PR #31).
    """
    monkeypatch.setattr(eval_cases.shutil, "which", lambda _name: "/usr/bin/graphify")
    (tmp_path / "graphify-out").mkdir()
    (tmp_path / "graphify-out" / "graph.json").write_text("{}")
    outcome = eval_cases._retrieval_precondition(tmp_path)
    assert outcome is not None
    assert outcome.verdict is evals.Verdict.SKIP
    assert "kb-prose" in outcome.detail


def test_the_retrieval_case_skips_when_graphify_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CONTROL ARM: the two SKIP reasons are different and must not collapse.

    "graphify is not installed here" and "the prose graph has not been derived"
    have different fixes, and one of them is not a defect in this repo at all.
    """
    monkeypatch.setattr(eval_cases.shutil, "which", lambda _name: None)
    outcome = eval_cases._retrieval_precondition(tmp_path)
    assert outcome is not None
    assert outcome.verdict is evals.Verdict.SKIP
    assert "not installed" in outcome.detail
    assert "kb-prose" not in outcome.detail
