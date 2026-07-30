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

import pytest
from kb_setup import eval_cases, evals, prose

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
        "tier1.mise-redaction-legible",
        "tier1.lane-health",
        "tier2.guard-fixtures",
        "tier2.kb-retrieval",
    }


# --- the mise redaction-legibility case ---------------------------------------


def _redaction_case() -> evals.Case:
    return next(c for c in _cases() if c.name == "tier1.mise-redaction-legible")


def test_the_redaction_case_is_advisory_and_still_carries_a_control_arm() -> None:
    """Advisory waives the REQUIREMENT for a control, not the discipline.

    It is advisory because the only remedy lives in the USER-level mise config
    (`_.fnox-env`), which `do-not.md` #11 forbids this repo from editing — a
    gated case would be a ship blocker no agent could ever clear. That is a
    reason to not gate it, never a reason to leave it unarmed.
    """
    case = _redaction_case()
    assert not case.gated
    assert case.control is not None


def test_the_redaction_control_arm_really_fails() -> None:
    """The FAIL direction, against real mise — not a stubbed value list.

    `test_every_control_arm_actually_fails` above skips advisory cases, so
    without this the one advisory case in the repo would be the only one whose
    control is never checked to fail.

    It asserts the CANARY IS NAMED, not merely that something failed. A FAIL alone
    would also be produced by any short secret already on the host, so the arm
    could look healthy while its canary had quietly stopped loading — and on the
    now-steady all-long host set that regression returns PASS, which means NOT
    ARMED. Raised by the silent-failure review lane (F2).
    """
    control = _redaction_case().control
    assert control is not None
    outcome = control()
    assert outcome.verdict is evals.Verdict.FAIL
    assert "shorter than" in outcome.detail
    assert eval_cases.REDACTION_CANARY in outcome.detail, (
        "the arm failed, but not demonstrably on its own canary — a short host "
        "secret would produce the same FAIL"
    )


def test_the_redaction_case_skips_without_mise() -> None:
    """CONTROL ARM: "mise is absent" must not read as "the set is clean".

    An empty redaction set is a PASS (mise cannot mask what it does not hold),
    so an unreadable one has to be a distinct verdict or the two collapse into
    the false green this whole module exists to refuse.
    """
    case = _redaction_case()
    assert case.precondition is not None
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(eval_cases.shutil, "which", lambda _name: None)
        outcome = case.precondition()
    assert outcome is not None
    assert outcome.verdict is evals.Verdict.SKIP


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


def test_the_retrieval_case_is_gated_and_slow() -> None:
    """Both flags are decisions, not defaults, and the first one flipped in P2.

    GATED since 2026-07-27: it was advisory while the number it exists to make
    citable was 0/119 (knowledge-base#12), because a floor at or below zero is
    the check that can only pass, and P0-P2 moved it far enough for
    `RETRIEVAL_FLOOR` to mean something. STILL SLOW, which is what keeps the
    gating off the ship path — see the next test.
    """
    case = next(c for c in _cases() if c.name == "tier2.kb-retrieval")
    assert case.gated
    assert case.slow
    assert not case.live


def test_the_gated_retrieval_case_still_does_not_bite_on_ship() -> None:
    """The inert-by-design property, asserted rather than merely written down.

    `kb-ship`'s eval gate does not pass --slow, so this case is SKIPPED on every
    PR and SHIP DOES NOT CHECK RETRIEVAL. That was accepted when the floor landed
    (~4 minutes is a gate people route around), on condition it is stated
    explicitly — and a stated property nothing checks is exactly the inert
    declaration dotfiles#354 exists to catch. So the claim is pinned here: gated
    AND slow, and a default run skips it.

    ONE CASE, not the whole suite. This ran `run_cases(_cases())` and then asserted
    `not report.failed` over EVERY case — so a unit test about one case's SKIP flag
    could go red because a lane CLI was absent from PATH or the 130k-node graph
    answered differently. It did: one full-suite run failed here and would not
    reproduce across five more, and the assertion only reports a COUNT, so which
    case failed was unrecoverable. `run_cases` treats cases independently (each
    iteration appends its own `Result`), so passing the single case proves the same
    property with none of the ambient dependency. What the other cases do is
    `mise run kb-eval`'s business, not this test's. (Found at clear-prep, 2026-07-29.)
    """
    case = next(c for c in _cases() if c.name == "tier2.kb-retrieval")
    assert case.gated
    assert case.slow
    report = evals.run_cases([case])
    row = next(r for r in report.results if r.case.name == "tier2.kb-retrieval")
    assert row.outcome.verdict is evals.Verdict.SKIP
    assert not report.failed


def test_the_gated_case_really_passes_its_floor_to_the_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTROL ARM for the floor, at the CASE level rather than the engine's.

    `test_evals.py` proves the engine compares a floor it is given. What it cannot
    prove is that this case hands one over — a probe that dropped the ``floor=``
    argument would leave every engine test green and the gate silently advisory
    again, which is the inert-declaration defect one level up.

    The mutation is the realistic regression: arms that find nothing, i.e. recall
    collapsing below the floor. They still return a non-empty list, so the
    silent-corpus defect does not fire first and the floor is what is being
    measured. Both stand-ins are needed because the real ones shell out to
    graphify for minutes; nothing else about the case is replaced.
    """
    flat = (evals.Arm("stand-in", lambda _q: (0, ["filler.md"])),)
    monkeypatch.setattr(eval_cases, "_retrieval_arms", lambda _root: flat)
    monkeypatch.setattr(eval_cases, "_corpus_stamp", lambda _root: "stand-in corpus")
    case = next(c for c in _cases() if c.name == "tier2.kb-retrieval")
    outcome = case.probe()
    assert outcome.verdict is evals.Verdict.FAIL
    assert "REGRESSED below the floor" in outcome.detail
    assert f"floor is {eval_cases.RETRIEVAL_FLOOR}" in outcome.detail


def test_the_retrieval_floor_is_one_below_the_measured_best() -> None:
    """Pinned so raising it to the measured value is a visible diff.

    4, against a measured 5 for `prose+idf` on the 2026-07-26 corpus. It guards
    regression rather than asserting aspiration: at 5 a corpus rebuild that moved
    one topic would redden the run for a reason unrelated to the code.
    """
    assert eval_cases.RETRIEVAL_FLOOR == 4
    pairs = {q.topic for q in eval_cases.GOLDEN_QUERIES if not q.expects_absent}
    assert 1 <= eval_cases.RETRIEVAL_FLOOR < len(pairs)


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
    """CONTROL ARM for the whole before/after: four arms, and no two are the same run.

    If two arms resolved the same corpus with the same retriever the report would
    still print a table, a SUITE line per arm and a DELTA of zero — a before/after
    that structurally cannot show a difference. So what each arm actually does is
    bound here.

    The P1 arm differs from the first two along the OTHER axis: it reads the same
    file as `prose` but does not shell out at all, which is why it contributes no
    ``seen`` entry. Scoping and scoring are separate changes, and an arm that
    quietly re-ran graphify would report P0's number under P1's name. The P2 arm
    shells out ONCE more, against the prose graph — it fuses graphify's order with
    the lexical one, so a fused arm that had lost its graphify input would leave
    ``seen`` two entries long and still print a plausible table.
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
        eval_cases.RRF_ARM,
    ]
    # The graphify-backed arms shell out and name different graphs; the fused arm
    # adds the third call, against the prose graph it shares with P0/P1.
    assert seen == [
        str(tmp_path / "graphify-out" / "graph.json"),
        str(tmp_path / "graphify-out" / prose.PROSE_GRAPH_NAME),
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


def _ranks(*sources: str) -> evals.Retrieve:
    """An input retriever for the fused arm: always returns this ranked list."""
    return lambda _query: (0, list(sources))


def test_the_fused_arm_combines_both_inputs() -> None:
    """The direction that must work: consensus from two orders, not one passed through.

    `both.md` is 3rd in the first input and 2nd in the second; `solo.md` is 1st in
    the first and absent from the second. A retriever that forwarded either input
    unchanged would put `solo.md` (or `x.md`) first.
    """
    retrieve = eval_cases._FusedRetriever(
        (_ranks("solo.md", "a.md", "both.md"), _ranks("x.md", "both.md"))
    )
    rc, returned = retrieve(eval_cases.GOLDEN_QUERIES[0])
    assert rc == 0
    assert returned[0] == "both.md"


@pytest.mark.parametrize("failing", [0, 1])
def test_the_fused_arm_reports_a_real_rc_from_either_input(failing: int) -> None:
    """BOTH directions, because "checks the first input" also passes one of them.

    A fused arm that swallowed one input's failure would print a plausible ranking
    built from half the evidence — a defective arm reporting a recall number
    instead of a defect. The rc must be the input's own, and no rows may come back
    with it.
    """
    inputs = [_ranks("a.md"), _ranks("b.md")]
    inputs[failing] = lambda _query: (7, [])
    rc, returned = eval_cases._FusedRetriever(inputs)(eval_cases.GOLDEN_QUERIES[0])
    assert rc == 7
    assert returned == []


def test_the_fused_arm_returns_nothing_when_its_inputs_do() -> None:
    """No padding, or `_arm_defect`'s silent-corpus check stops being able to fire."""
    retrieve = eval_cases._FusedRetriever((_ranks(), _ranks()))
    assert retrieve(eval_cases.GOLDEN_QUERIES[0]) == (0, [])


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
