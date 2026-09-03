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

The third mandatory property (spec §4) is now TWO tests, not one — a round-2
cold review (`.agent/kb/review/reports/review-062ab296…-cold.md`, P1) found the
original `test_relevance_dominates_outcome_and_recency` asserting a guarantee
("a clearly-worse lexical match cannot out-rank a clearly-better one") the code
does not provide, using a single fixture whose lexical gap happened to sit
outside the multiplier's own worst-case band. `test_no_reorder_when_the_
lexical_gap_exceeds_the_multiplier_band` keeps that fixture as what it actually
is: the OUTER bound. `test_reorder_is_possible_when_the_lexical_gap_is_inside_
the_multiplier_band` is the INNER bound, the cold review's own constructed
counterexample — a `dead_end`, six-year-stale record that matches every query
term still loses to a `corrected`, same-day record that matches one fewer.
Together they are the property the module docstring now actually claims.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
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


def test_no_reorder_when_the_lexical_gap_exceeds_the_multiplier_band(tmp_path: Path) -> None:
    """A lexical gap wider than the multiplier's own worst-case band survives it.

    `strong.md` is given the WORST possible multiplier (`dead_end`, dated 2020 —
    `0.6 x 0.85 = 0.51`) and `weak.md` the BEST (`corrected`, dated today — `1.15
    x 1.0 = 1.15`) — the full ~2.255x band the multiplier can spend, both spent
    against `strong.md`. It still wins, because the underlying BM25 gap between
    the two texts is far wider than 2.255x (verified independently at ~4.07x
    with the multiplier disabled). This is the OUTER bound: the module's
    "relevance dominates" claim holds for gaps this wide.
    """
    _memory(
        tmp_path,
        "strong",
        question="What broke the mise install lock during the renovate hang?",
        answer=(
            "The renovate npm-backend postinstall recursed into its own "
            "mise install, holding the mise install lock for hours."
        ),
        outcome="dead_end",
        date="2020-01-01T00:00:00+00:00",
    )
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
        "the weak-relevance-but-maximally-favoured record out-ranked the strong "
        "lexical match even at the multiplier's own worst case — the band is "
        "wider than documented"
    )


def test_reorder_is_possible_when_the_lexical_gap_is_inside_the_multiplier_band(
    tmp_path: Path,
) -> None:
    """A lexical gap INSIDE the multiplier's band can flip the ranking.

    This is the documented limitation, not a defect: `better.md` matches all
    three query terms, `worse.md` matches two of three (unweighted BM25 ratio
    ~1.66x — comfortably inside the ~2.255x band). With `better.md` given the
    worst multiplier and `worse.md` the best, `worse.md` wins. If this test
    ever starts failing because the module got MORE conservative (the band
    narrowed, or the ordering is now preserved here too), that is a real
    improvement — update the module docstring's claim and this test's docstring
    together rather than treating a fix as broken.
    """
    _memory(
        tmp_path,
        "better",
        question="How does the wombat quokka numbat interact in the sanctuary?",
        answer=(
            "The wombat quokka numbat all share the same enclosure at the sanctuary this season."
        ),
        outcome="dead_end",
        date="2020-01-01T00:00:00+00:00",
    )
    _memory(
        tmp_path,
        "worse",
        question="How does the wombat quokka behave without a numbat present?",
        answer="The wombat quokka pairing was studied without any numbat present at all.",
        outcome="corrected",
        correction="the pairing study excluded the numbat entirely.",
        date="2026-09-03T00:00:00+00:00",
    )
    request = recall.check_recall(["wombat quokka numbat"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    hits = report.value.hits
    assert len(hits) == 2
    assert hits[0].path == "worse.md", (
        "expected the documented inside-the-band reorder; if this now preserves "
        "the better-relevance document, the module improved — update both "
        "docstrings rather than this assertion alone"
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


def test_weight_combines_outcome_and_recency_as_documented() -> None:
    """Direct unit test on `_weight`.

    A round-2 cold review (P2) found four of
    the module's five ranking constants surviving their own suite under a
    mutation sweep (`dead_end`'s penalty, `_RECENCY_SPAN`, `_HALF_LIFE_DAYS`,
    `_EXCERPT_CHARS` — recency had no test at all). Asserting the exact,
    hand-computed multiplier for each combination — using LITERAL expected
    values, not a re-reference to the module's own constants — arms all three
    of the outcome/recency constants at once: mutating `_OUTCOME_WEIGHT["dead_
    end"]`, `_RECENCY_FLOOR`, `_RECENCY_SPAN`, or `_HALF_LIFE_DAYS` changes one
    of these four expected numbers and fails this test.
    """
    now = datetime(2026, 9, 3, tzinfo=UTC)
    fresh_useful: dict[str, object] = {"outcome": "useful", "date": now.isoformat()}
    # 3650 days is >> the 30-day half-life, so decay is effectively 0 and the
    # recency multiplier bottoms out at its floor (0.85).
    stale_useful: dict[str, object] = {
        "outcome": "useful",
        "date": (now - timedelta(days=3650)).isoformat(),
    }
    dead_end: dict[str, object] = {"outcome": "dead_end", "date": now.isoformat()}
    corrected: dict[str, object] = {"outcome": "corrected", "date": now.isoformat()}

    assert recall._weight(fresh_useful, now) == pytest.approx(1.0, abs=1e-6)
    assert recall._weight(stale_useful, now) == pytest.approx(0.85, abs=1e-6)
    assert recall._weight(dead_end, now) == pytest.approx(0.6, abs=1e-6)
    assert recall._weight(corrected, now) == pytest.approx(1.15, abs=1e-6)


def test_excerpt_is_bounded_to_320_characters(tmp_path: Path) -> None:
    """The DISPLAY excerpt is bounded.

    A round-2 cold review (P2) found
    `_EXCERPT_CHARS` surviving a mutation to `5` with no test failing. 320 is
    the module's current `_EXCERPT_CHARS` value, written as a literal (not
    `recall._EXCERPT_CHARS`) so a mutation to that constant is what this test
    is meant to catch, rather than trivially agreeing with it.
    """
    long_answer = "wombat quokka numbat " * 40  # far longer than 320 chars
    assert len(long_answer) > 320
    _memory(tmp_path, "long", question="wombat quokka numbat excerpt bound", answer=long_answer)
    request = recall.check_recall(["wombat quokka numbat excerpt bound"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert len(report.value.hits[0].excerpt) == 320


# --- filters -----------------------------------------------------------------


def test_outcome_filter_accepts_dead_end(tmp_path: Path) -> None:
    """`--outcome dead_end` must not be refused.

    `_OUTCOME_WEIGHT`'s own comment promises "only `--outcome` can exclude" a
    `dead_end` record — a round-2 cold review (P2) found `_OUTCOME_FILTERS`
    refusing the exact value that comment names.
    """
    _memory(
        tmp_path,
        "d",
        question="Does the falkordb push exporter work on this graph size?",
        answer="Attempted push_to_falkordb on the aggregate graph; it timed out.",
        outcome="dead_end",
    )
    _memory(
        tmp_path,
        "u",
        question="Does the falkordb push exporter work differently now?",
        answer="Attempted push_to_falkordb on the aggregate graph; it timed out.",
        outcome="useful",
    )
    request = recall.check_recall(["falkordb push exporter", "--outcome", "dead_end"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert report.value.searched == 1
    assert all(hit.outcome == "dead_end" for hit in report.value.hits)


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


def test_since_filter_uses_real_date_comparison_not_string_comparison(tmp_path: Path) -> None:
    """A valid but timezone-shifted date must not defeat `--since` via string comparison.

    A round-2 cold review (P2) found `--since` comparing date STRINGS
    (`str(r.get("date") or "") >= since`). A round-trippable, genuinely PARSEABLE
    ISO 8601 date exposes it: `"2026-09-03T01:00:00+05:00"` is, in UTC, actually
    `2026-09-02T20:00:00Z` — the DAY BEFORE `--since 2026-09-03`. Lexically the
    string is `>= "2026-09-03"` (it starts with that exact prefix and is longer,
    so Python's string ordering ranks it after), so the old code WRONGLY kept
    it. A real (timezone-aware) datetime comparison correctly excludes it.
    """
    _memory(
        tmp_path,
        "shifted",
        question="How does the mise task registry validate a bad pin?",
        answer="The mise task registry validates a pin against its schema.",
        date="2026-09-03T01:00:00+05:00",  # = 2026-09-02T20:00:00Z, before the cutoff
    )
    _memory(
        tmp_path,
        "after",
        question="How does the mise task registry validate a bad pin too?",
        answer="The mise task registry validates a pin against its schema.",
        date="2026-10-15T00:00:00+00:00",
    )
    request = recall.check_recall(["mise task registry validate bad pin", "--since", "2026-09-03"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert report.value.searched == 1, (
        "the timezone-shifted (actually pre-cutoff) record survived --since — "
        "the filter is comparing strings, not real datetimes"
    )
    assert report.value.hits[0].path == "after.md"


def test_since_filter_and_recency_treat_an_undated_record_consistently(tmp_path: Path) -> None:
    """An undated/unparsable record is not silently dropped by `--since`.

    A round-2 cold review (P2) found `_filter_records` treating an undated
    record as infinitely old (dropped by any `--since`) while `_decay` treats
    it as maximally fresh (full recency weight) — two contradictory readings
    of the same absent field. Both now route through `_parse_record_date`:
    "no information" keeps the record, consistent with `_decay`'s "undated
    keeps full weight".
    """
    _memory(
        tmp_path,
        "undated",
        question="How does the antigravity setup skill verify auth without a date?",
        answer="antigravity setup runs a live call to verify auth.",
        date="",
    )
    request = recall.check_recall(
        ["antigravity setup skill verify auth without a date", "--since", "2026-08-01"]
    )
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert report.value.searched == 1, "an undated record must survive --since, not be dropped"
    assert report.value.hits[0].path == "undated.md"


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


def test_kb_setup_usage_lists_recall(capsys: pytest.CaptureFixture[str]) -> None:
    """`kb-setup` with no subcommand must mention `recall` in its usage banner.

    A round-2 cold review found `cli._print_usage` never listing `recall` —
    every other subcommand this module dispatches (`remember`, `goal-check`,
    …) is there; `recall` alone was missing, so `kb-setup` with no args (or
    `--help`-shaped confusion) would never surface it.
    """
    from kb_setup import cli

    cli._print_usage()
    assert "recall <question>" in capsys.readouterr().out


def test_check_recall_never_raises_on_a_malformed_flag_value() -> None:
    """`--top` with a dangling flag value must return an `Err`, not exit the process.

    A round-2 cold review (measured: `kb-recall q --top` exited 2 with a usage
    banner on stderr) found `check_recall` contradicting its own docstring,
    "Returns, never raises, PRINTS NOTHING" — stock `argparse` calls
    `sys.exit(2)` from inside `parse_known_args` on this shape, bypassing every
    other `Err` path in the module. `_NonExitingParser.error` now raises
    `_ArgumentError` instead, caught here.
    """
    # `--top` at the end of argv with nothing after it: argparse's own
    # "expected one argument" case, previously a bare SystemExit(2).
    request = recall.check_recall(["a question", "--top"])
    assert isinstance(request, Err)
    assert request.rc is Rc.BAD_REQUEST


def test_corrected_with_no_correction_field_renders_none_not_the_string_none(
    tmp_path: Path,
) -> None:
    """A `corrected` record with no `correction` value must render `None`, not `"None"`.

    A round-2 cold review (P3) found `str(record.get("correction"))` — with no
    `outcome == "corrected"` guard on the VALUE, only on the outcome — turning a
    missing correction into the literal string `"None"` (`str(None) ==
    "None"`), which a `--json` consumer reads as a real correction. Unreachable
    on the live store today (`kb-remember` refuses this shape), reachable from
    any other writer.
    """
    _memory(
        tmp_path,
        "corrnofield",
        question="How does the antigravity delegate lane report cost with no correction?",
        answer="Antigravity delegate lane reports a token-cost digest per run.",
        outcome="corrected",
    )
    request = recall.check_recall(["antigravity delegate lane report cost no correction"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert report.value.hits[0].correction is None


def test_total_reports_the_real_file_count_and_surfaces_unparsable_files(
    tmp_path: Path,
) -> None:
    """`total` must count files on disk, not just what parsed — and say what didn't.

    A round-2 cold review (P3) found `RecallReport.total` documented as "how
    many memories exist in the store" while actually counting only what
    `load_memory_docs` could parse — a file it silently dropped (invalid UTF-8)
    was counted nowhere and reported nowhere.
    """
    _memory(
        tmp_path,
        "good",
        question="How does kb-build reproduce the graph?",
        answer="kb-build clones every pinned manifest and re-extracts.",
    )
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe not valid utf-8 \x00\x01")
    request = recall.check_recall(["kb-build reproduce graph"])
    assert isinstance(request, Ok)
    report = recall.run_recall(request.value, tmp_path)
    assert isinstance(report, Ok)
    assert report.value.total == 2, "total must count the real file on disk, not just parsed ones"
    assert report.value.unparsable == 1
    rendered = recall.render_report(report.value)
    assert "1 file present but unreadable" in rendered


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


def test_answer_body_keeps_a_narrative_outcome_subheading_written_by_the_answer() -> None:
    """An answer may legitimately title one of its OWN sections "Outcome".

    It must not be truncated at that heading — a round-2 cold review (P1) measured this
    exact shape on 3 live records (a narrative "## Outcome" retrospective
    followed, further down, by graphify's real `- Signal:` footer) and found
    the naive "next `## ` heading" rule truncating 51 of 364 live records
    overall (23.5% of all answer bytes) this way.
    """
    text = (
        '---\ntype: "query"\n---\n\n# Q: x\n\n## Answer\n\n'
        "## Outcome\n\nThis section of the ANSWER narrates what happened; "
        "it is prose, not a footer.\n\n"
        "## Outcome\n\n- Signal: corrected\n- Correction: the actual footer text.\n"
    )
    body = recall._answer_body(text)
    assert "narrates what happened" in body
    assert "the actual footer text" not in body


def test_answer_body_stops_at_the_real_footer_even_when_correction_has_headings() -> None:
    """A `correction` value written raw into the body can itself contain headings.

    Measured on a live record: a multi-paragraph correction with
    nested `## ` subheadings). Those headings must never be mistaken for the
    boundary of the ANSWER body — the boundary is the writer's own `## Outcome`
    heading plus its `- Signal:`/`- Correction:` bullet, which appears exactly
    once, before the correction's own text.
    """
    text = (
        '---\ntype: "query"\n---\n\n# Q: x\n\n## Answer\n\n'
        "the real answer body.\n\n"
        "## Outcome\n\n- Signal: corrected\n"
        "- Correction: a correction whose own text has\n\n"
        "## A nested heading inside the correction\n\n"
        "more correction prose here.\n"
    )
    assert recall._answer_body(text) == "the real answer body."
