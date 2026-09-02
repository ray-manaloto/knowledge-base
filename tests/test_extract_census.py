# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.extract_census` — the classifier and the report.

The subprocess half is not exercised here: it runs graphify over a real clone and
is what the task itself measures. What IS testable, and what a wrong answer would
quietly corrupt, is the split of one extraction's stderr into the two known
classes plus a verbatim residue.
"""

from __future__ import annotations

from kb_setup import extract_census as ec

_SYNTAX_LINE = (
    "warning: 10 file(s) had syntax errors and may be partially extracted: "
    "src/main/index.d.ts (first error at line 1, no symbols extracted), "
    "test/config-utl/__mocks__/webpackconfig/invalid.config.js "
    "(first error at line 1, no symbols extracted) (+8 more)"
)
_COLLISION_LINE = (
    "[graphify] WARNING: node 'types_dependency_cruiser' is minted by two different "
    "files — keeping '../../types/dependency-cruiser' from 'types/dependency-cruiser', "
    "dropping '../../types/dependency-cruiser.js' from 'types/dependency-cruiser.js'."
)


def test_clean_stderr_is_not_blocked() -> None:
    """The control arm: an empty stderr must classify as nothing at all."""
    syntax, ids, samples, residue = ec._classify("")
    assert (syntax, ids, samples, residue) == (0, (), (), "")
    assert not ec.SourceOutcome(name="x", returncode=0).blocked


def test_syntax_count_comes_from_the_number_not_the_paths() -> None:
    """Graphify truncates its own path list, so the count must not be derived from it."""
    syntax, ids, samples, residue = ec._classify(_SYNTAX_LINE)
    assert syntax == 10
    assert ids == ()
    assert len(samples) == 2  # only the two graphify actually printed
    assert "src/main/index.d.ts" in samples
    assert residue == ""


def test_collisions_are_counted_by_distinct_id_not_by_line() -> None:
    """One id warns once per referencing site; 37 lines was 7 ids on dependency-cruiser."""
    stderr = "\n".join([_COLLISION_LINE] * 5)
    syntax, ids, _samples, residue = ec._classify(stderr)
    assert syntax == 0
    assert ids == ("types_dependency_cruiser",)
    assert residue == ""


def test_unknown_stderr_survives_verbatim() -> None:
    """A class this module does not know is exactly what a summary must not swallow."""
    stderr = "[graphify] fail-closed: kept node(s) from 1 source file(s)"
    syntax, ids, _samples, residue = ec._classify(stderr)
    assert (syntax, ids) == (0, ())
    assert residue == stderr


def test_mixed_stderr_splits_into_both_classes() -> None:
    syntax, ids, samples, residue = ec._classify(f"{_SYNTAX_LINE}\n{_COLLISION_LINE}\nodd line")
    assert syntax == 10
    assert ids == ("types_dependency_cruiser",)
    assert samples
    assert residue == "odd line"


def test_report_lists_only_blocked_sources_and_names_them() -> None:
    census = ec.Census(started_at="2026-09-02T00:00:00+00:00")
    census.sources = [
        ec.SourceOutcome(name="clean-one", returncode=0, nodes=42),
        ec.SourceOutcome(name="broken-one", returncode=0, syntax_files=3, nodes=7),
    ]
    assert [s.name for s in census.blocked] == ["broken-one"]
    rendered = ec._render(census)
    assert "`broken-one`" in rendered
    assert "`clean-one`" not in rendered
    assert "Blocked: 1." in rendered


def test_report_elides_long_collision_lists_but_says_how_many() -> None:
    ids = tuple(f"id_{n}" for n in range(ec._MAX_LISTED_IDS + 5))
    census = ec.Census(started_at="2026-09-02T00:00:00+00:00")
    census.sources = [ec.SourceOutcome(name="many", returncode=0, collision_ids=ids)]
    rendered = ec._render(census)
    assert f"{len(ids)} distinct colliding id(s)" in rendered
    assert "… 5 more" in rendered
    assert "`id_0`" in rendered
    assert "`id_16`" not in rendered


def test_routine_merge_progress_is_stripped_but_nothing_else_is() -> None:
    """`graph._run` refused a build over a line the receipt path calls routine.

    Both directions armed: the narration must vanish, and a real warning sharing
    the same stderr must survive — recognising one benign line is never license
    to wave the rest through.
    """
    from kb_setup import graphify_health as gh

    routine = "[graphify] Replaced 20 node(s) from re-extracted source file(s)."
    assert gh.strip_routine_narration(routine).strip() == ""

    real = "warning: 3 file(s) had syntax errors and may be partially extracted: a.py"
    both = f"{routine}\n{real}"
    assert gh.strip_routine_narration(both).strip() == real


def test_label_no_backend_narration_is_stripped_but_a_real_one_is_not() -> None:
    """The no-LLM-backend line is the configuration `do-not.md` #4 REQUIRES.

    Armed both ways: the narration goes, and a different label warning in the
    same stderr survives to refuse the build.
    """
    from kb_setup import graphify_health as gh

    narration = (
        "[graphify label] no LLM backend configured; keeping Community N placeholders. "
        "Set an API key (e.g. GOOGLE_API_KEY) or pass --backend."
    )
    assert gh.strip_routine_narration(narration).strip() == ""

    other = "[graphify label] failed to label 12 communities"
    assert gh.strip_routine_narration(f"{narration}\n{other}").strip() == other


def test_build_receipt_reads_the_schema_graphify_actually_writes() -> None:
    """The receipt demanded a top-level `edges` key graphify never writes.

    Both arms, and the FAIL arm is the point: the real node-link shape must
    resolve, and a genuinely malformed graph must still be refused — a check
    that only ever passes is what this replaced.
    """
    import pytest
    from kb_setup.graph import _graph_collections

    real = {"nodes": [1], "links": [2, 3], "graph": {"hyperedges": [4]}}
    got = _graph_collections(real)
    assert [len(got[k]) for k in ("nodes", "edges", "hyperedges")] == [1, 2, 1]

    # Hyperedges promoted to the top level are the other shape prose handles.
    promoted = {"nodes": [], "links": [], "hyperedges": [1, 2], "graph": {}}
    assert len(_graph_collections(promoted)["hyperedges"]) == 2

    # The FAIL direction, one field at a time.
    for broken in (
        {"nodes": "x", "links": [], "graph": {"hyperedges": []}},
        {"nodes": [], "links": "x", "graph": {"hyperedges": []}},
        {"nodes": [], "links": [], "graph": {"hyperedges": "x"}},
    ):
        with pytest.raises(SystemExit, match="is not an array"):
            _graph_collections(broken)


# --- Cold review of 69c126cbaef8: the census must not report clean without asking ---


def test_a_bad_returncode_alone_blocks_a_source() -> None:
    """The exit code is part of the verdict, not a printed column.

    `fable-advisor` exits 1 with an empty graph. It happened to carry residue
    that caught it, so a source failing closed with CLEAN stderr would have
    printed `ok` — the gap this closes.
    """
    assert ec.SourceOutcome(name="rc-only", returncode=1).blocked
    # The control arm: rc 0 and nothing else is still not blocked.
    assert not ec.SourceOutcome(name="fine", returncode=0).blocked


def test_docs_manifests_are_not_selected_because_the_build_never_opens_them(
    tmp_path,
) -> None:
    """A `kind = docs` source cannot block a build that never AST-scans it.

    Scanning one produced a blocked row for `codex-docs` that then drove a
    registration. The predicate is `is_ast_scanned`, never `is_built`.
    """
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "a-code.manifest").write_text(
        "url = https://example.com/a\nref = main\ncommit = " + "0" * 40 + "\nkind = code\n"
    )
    (sources / "b-docs.manifest").write_text(
        "url = https://example.com/b\nref = main\ncommit = " + "0" * 40 + "\nkind = docs\n"
    )
    names = [m.name for m in ec.selected(tmp_path)]
    assert names == ["a-code"], names


def test_a_source_with_no_clone_is_recorded_not_dropped(tmp_path) -> None:
    """`missing` is the visible record; `examined` is the honest denominator."""
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "gone.manifest").write_text(
        "url = https://example.com/g\nref = main\ncommit = " + "0" * 40 + "\nkind = code\n"
    )
    census = ec.run(tmp_path)
    assert census.missing == ["gone"]
    assert census.examined == 0
    assert census.sources == []


def test_an_all_missing_run_refuses_rather_than_reporting_zero_blocked(tmp_path) -> None:
    """The house rule: never return "0 blocked" for a corpus nobody examined."""
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "gone.manifest").write_text(
        "url = https://example.com/g\nref = main\ncommit = " + "0" * 40 + "\nkind = code\n"
    )
    assert ec.main(tmp_path, []) == ec.Rc.NOT_RUN


def test_an_only_name_matching_nothing_is_a_bad_request(tmp_path) -> None:
    """A typo filtered the worklist to empty and still exited 0."""
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "real.manifest").write_text(
        "url = https://example.com/r\nref = main\ncommit = " + "0" * 40 + "\nkind = code\n"
    )
    assert ec.main(tmp_path, ["--only", "no-such-source"]) == ec.Rc.BAD_REQUEST
    # The control arm: a name that DOES match gets past the request check.
    assert ec.main(tmp_path, ["--only", "real"]) != ec.Rc.BAD_REQUEST


def test_report_elides_long_stderr_but_says_how_many() -> None:
    """The sibling collision branch said so; this one did not, under "verbatim"."""
    residue = "\n".join(f"line {n}" for n in range(ec._MAX_LISTED_STDERR + 4))
    census = ec.Census(started_at="2026-09-02T00:00:00+00:00")
    census.sources = [ec.SourceOutcome(name="noisy", returncode=0, other_stderr=residue)]
    rendered = ec._render(census)
    assert "… 4 more line(s)" in rendered
    assert "line 0" in rendered
    assert "line 12" not in rendered


def test_report_names_the_sources_it_could_not_examine() -> None:
    census = ec.Census(started_at="2026-09-02T00:00:00+00:00")
    census.sources = [ec.SourceOutcome(name="ok-one", returncode=0, nodes=5)]
    census.missing = ["never-cloned"]
    rendered = ec._render(census)
    assert "NOT EXAMINED" in rendered
    assert "`never-cloned`" in rendered
