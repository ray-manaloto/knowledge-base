# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.recall` — the ranked read path over `graphify-out/memory/`.

All fixtures use an isolated `tmp_path` directory, never the live
`graphify-out/memory/` (`.claude/rules/probes-need-a-control-arm.md` +
the U-R9 spec §5: tests use isolated state).

The load-bearing tests here are the two arms the spec makes mandatory:

* :func:`test_a_known_term_finds_its_fixture_memory` — the POSITIVE arm. At 364
  live documents the corpus is an order of magnitude smaller than the
  2,553-node prose graph `lexical.py` was measured on, so a false negative
  (zero terms shared between a differently-phrased question and a genuinely
  relevant record) is the expected failure mode here, not an edge case.
* :func:`test_an_unrelated_question_returns_nothing` — the CONTROL arm. A
  ranking verified only on a query that matches is not verified
  (`probes-need-a-control-arm.md` rule 2).

:func:`test_relevance_dominates_outcome_and_recency` is the third mandatory
property (spec §4): the outcome/recency multiplier must never be able to
reorder a clearly-better lexical match above a clearly-worse one. It is
written as an assertion on real scores, not a comment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kb_setup import recall
from kb_setup.result import Err, Ok, Rc

if TYPE_CHECKING:
    from pathlib import Path


def _memory(path: Path, name: str, *, question: str, answer: str, **meta: str) -> Path:
    """Write a memory file in the exact shape `graphify save-result` produces.

    Verified against every file currently under `graphify-out/memory/`:
    frontmatter, a `# Q:` title, `## Answer`, then `## Outcome` /
    `## Source Nodes`. `**meta` carries the optional `outcome` (default
    `useful`), `correction` and `date` — kept out of the named signature so
    this fixture stays under ruff's PLR0913 argument-count budget.
    """
    outcome = meta.pop("outcome", "useful")
    correction = meta.pop("correction", None)
    date = meta.pop("date", "2026-08-01T00:00:00+00:00")
    if meta:
        msg = f"_memory() got unexpected keyword argument(s): {', '.join(meta)}"
        raise TypeError(msg)
    lines = [
        "---",
        'type: "query"',
        f'date: "{date}"',
        f'question: "{question}"',
        f'outcome: "{outcome}"',
    ]
    if correction is not None:
        lines.append(f'correction: "{correction}"')
    lines += [
        "---",
        "",
        f"# Q: {question}",
        "",
        "## Answer",
        "",
        answer,
        "",
        "## Outcome",
        "",
        f"- Signal: {outcome}",
    ]
    target = path / f"{name}.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


# --- the two mandatory arms (spec §5) -------------------------------------


def test_a_known_term_finds_its_fixture_memory(tmp_path: Path) -> None:
    """POSITIVE arm: a term known to be in one fixture returns that fixture."""
    _memory(
        tmp_path,
        "target",
        question="How does the heredoc tokeniser handle quote awareness?",
        answer=(
            "The guard's shlex-based tokeniser now tracks whether a heredoc "
            "delimiter was itself quoted, which changes whether bash performs "
            "expansion inside the body."
        ),
    )
    _memory(
        tmp_path,
        "distractor",
        question="How do we pin the graphify version?",
        answer="Bump the exact pin in pyproject.toml and re-lock with uv.",
    )
    request = recall.check_recall(["heredoc tokeniser quote awareness"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert report.value.hits, "a term present verbatim in one fixture found nothing"
    assert report.value.hits[0].path == "target.md"


def test_an_unrelated_question_returns_nothing(tmp_path: Path) -> None:
    """CONTROL arm: a topic the store does not cover reports 0 matched, exit 0."""
    _memory(
        tmp_path,
        "only",
        question="How does the heredoc tokeniser handle quote awareness?",
        answer="The guard's shlex-based tokeniser tracks quoting state.",
    )
    request = recall.check_recall(["zzzqx no such topic in this corpus xk938"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert report.value.hits == []
    assert report.value.searched == 1
    rendered = recall.render_report(report.value)
    assert "0 of 1 matched" in rendered


# --- outcome + recency weighting (spec §4) --------------------------------


def test_relevance_dominates_outcome_and_recency(tmp_path: Path) -> None:
    """A clearly-worse lexical match cannot out-rank a clearly-better one.

    However favourable its outcome/recency weight.
    """
    # Strong relevance, weak outcome, old date: three query terms present.
    _memory(
        tmp_path,
        "strong",
        question="What broke the mise install lock during the renovate hang?",
        answer=(
            "The renovate npm-backend postinstall recursed into its own "
            "mise install, holding the mise install lock for hours."
        ),
        outcome="useful",
        date="2026-07-22T00:00:00+00:00",
    )
    # Weak relevance (one term), strong outcome+recency: corrected, today.
    _memory(
        tmp_path,
        "weak",
        question="What is the mise pin for uv?",
        answer="uv is pinned exact in mise.toml; renovate proposes bumps.",
        outcome="corrected",
        correction="uv is pinned exact, never a range.",
        date="2026-09-03T00:00:00+00:00",
    )
    request = recall.check_recall(["mise install lock renovate hang recursed postinstall"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    hits = report.value.hits
    assert len(hits) == 2
    assert hits[0].path == "strong.md", (
        "the weak-relevance-but-favoured-outcome record out-ranked the strong "
        "lexical match — the multiplier is overpowering relevance"
    )


def test_corrected_ranks_at_least_as_high_as_useful_at_equal_relevance(
    tmp_path: Path,
) -> None:
    """Two records with identical relevance: `corrected` must not rank below `useful`."""
    _memory(
        tmp_path,
        "useful_one",
        question="How does the antigravity delegate lane report cost?",
        answer="Antigravity delegate lane reports a token-cost digest per run.",
        outcome="useful",
        date="2026-08-01T00:00:00+00:00",
    )
    _memory(
        tmp_path,
        "corrected_one",
        question="How does the antigravity delegate lane report cost differently",
        answer="Antigravity delegate lane reports a token-cost digest per run.",
        outcome="corrected",
        correction="the digest excludes retries.",
        date="2026-08-01T00:00:00+00:00",
    )
    request = recall.check_recall(["antigravity delegate lane report cost"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    scores = {hit.path: hit.score for hit in report.value.hits}
    assert scores["corrected_one.md"] >= scores["useful_one.md"]


def test_dead_end_is_weighted_low_but_never_excluded(tmp_path: Path) -> None:
    """The live store holds zero `dead_end` records.

    This is a synthetic fixture, required by spec §4 because that path is
    otherwise untestable.
    """
    _memory(
        tmp_path,
        "dead",
        question="Does the falkordb push exporter work on this graph size?",
        answer="Attempted push_to_falkordb on the aggregate graph; it timed out.",
        outcome="dead_end",
        date="2026-08-01T00:00:00+00:00",
    )
    request = recall.check_recall(["falkordb push exporter graph size"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert len(report.value.hits) == 1
    assert report.value.hits[0].outcome == "dead_end"


# --- filters -----------------------------------------------------------------


def test_outcome_filter_narrows_the_search_pool(tmp_path: Path) -> None:
    _memory(
        tmp_path,
        "u",
        question="How does kb-build reproduce the graph?",
        answer="kb-build clones every pinned manifest and re-extracts.",
        outcome="useful",
    )
    _memory(
        tmp_path,
        "c",
        question="How does kb-build reproduce the graph differently now?",
        answer="kb-build clones every pinned manifest and re-extracts.",
        outcome="corrected",
        correction="it also re-derives the prose graph.",
    )
    request = recall.check_recall(["kb-build reproduce graph", "--outcome", "corrected"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert report.value.searched == 1
    assert all(hit.outcome == "corrected" for hit in report.value.hits)


def test_outcome_filter_to_a_pool_with_none_matching_is_ok_not_findings(
    tmp_path: Path,
) -> None:
    """Filtering the store to zero records is a looked-and-found-nothing OK.

    Never a NOT_RUN — the store itself was read successfully.
    """
    _memory(
        tmp_path,
        "u",
        question="How does kb-build reproduce the graph?",
        answer="kb-build clones every pinned manifest and re-extracts.",
        outcome="useful",
    )
    request = recall.check_recall(["kb-build", "--outcome", "corrected"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert report.value.hits == []
    assert report.value.searched == 0
    assert report.value.total == 1


def test_since_filter_excludes_older_dates(tmp_path: Path) -> None:
    _memory(
        tmp_path,
        "old",
        question="How does the goal engineering skill audit a condition?",
        answer="goal-engineering audits a completion condition for ambiguity.",
        date="2026-07-01T00:00:00+00:00",
    )
    _memory(
        tmp_path,
        "new",
        question="How does the goal engineering skill audit a condition too?",
        answer="goal-engineering audits a completion condition for ambiguity.",
        date="2026-08-25T00:00:00+00:00",
    )
    request = recall.check_recall(
        ["goal engineering skill audit condition", "--since", "2026-08-01"]
    )
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert report.value.searched == 1
    assert report.value.hits[0].path == "new.md"


def test_top_bounds_the_number_of_hits(tmp_path: Path) -> None:
    for i in range(3):
        _memory(
            tmp_path,
            f"m{i}",
            question=f"How does the mise task registry handle task {i}?",
            answer="The mise task registry handles task registration cleanly.",
        )
    request = recall.check_recall(["mise task registry handle task", "--top", "2"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert len(report.value.hits) == 2


# --- exit states (spec §4) ----------------------------------------------------


def test_missing_memory_dir_is_not_run(tmp_path: Path) -> None:
    request = recall.check_recall(["anything"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path / "does-not-exist")
    assert isinstance(report, Err)
    assert report.rc is Rc.NOT_RUN


def test_empty_memory_dir_is_not_run(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    request = recall.check_recall(["anything"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path / "empty")
    assert isinstance(report, Err)
    assert report.rc is Rc.NOT_RUN


def test_empty_question_is_bad_request() -> None:
    request = recall.check_recall(["   "])
    assert isinstance(request, Err)
    assert request.rc is Rc.BAD_REQUEST


def test_no_question_at_all_is_bad_request() -> None:
    request = recall.check_recall([])
    assert isinstance(request, Err)
    assert request.rc is Rc.BAD_REQUEST


def test_bad_outcome_value_is_bad_request() -> None:
    request = recall.check_recall(["q", "--outcome", "bogus"])
    assert isinstance(request, Err)
    assert request.rc is Rc.BAD_REQUEST


def test_bad_since_format_is_bad_request() -> None:
    request = recall.check_recall(["q", "--since", "not-a-date"])
    assert isinstance(request, Err)
    assert request.rc is Rc.BAD_REQUEST


def test_bad_top_value_is_bad_request() -> None:
    request = recall.check_recall(["q", "--top", "0"])
    assert isinstance(request, Err)
    assert request.rc is Rc.BAD_REQUEST

    request = recall.check_recall(["q", "--top", "not-a-number"])
    assert isinstance(request, Err)
    assert request.rc is Rc.BAD_REQUEST


def test_unknown_argument_is_bad_request() -> None:
    request = recall.check_recall(["q", "--nope"])
    assert isinstance(request, Err)
    assert request.rc is Rc.BAD_REQUEST


# --- rendering -----------------------------------------------------------------


def test_json_rendering_round_trips_the_hit_fields(tmp_path: Path) -> None:
    import json

    _memory(
        tmp_path,
        "one",
        question="How does the antigravity setup skill verify auth?",
        answer="antigravity setup runs a live call to verify auth.",
        outcome="corrected",
        correction="it also checks plugin version.",
    )
    request = recall.check_recall(["antigravity setup skill verify auth"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    payload = json.loads(recall.render_json(report.value))
    assert payload["hits"][0]["path"] == "one.md"
    assert payload["hits"][0]["correction"] == "it also checks plugin version."


def test_answer_body_extraction_stops_at_the_next_heading() -> None:
    text = (
        '---\ntype: "query"\n---\n\n# Q: x\n\n## Answer\n\nbody text here\n\n'
        "## Outcome\n\n- Signal: useful\n"
    )
    assert recall._answer_body(text) == "body text here"


def test_answer_body_extraction_with_no_heading_is_empty() -> None:
    assert recall._answer_body("no frontmatter or heading here") == ""
