"""Tests for `graph_checks.assert_composition` — the in-build invariant guard (#175).

Two invariants, two failure fixtures, and controls for each: `test_merge_
prefixes_once.py` proves the depth-1 claim against the real graphify binary,
but only when the suite runs. This module's function runs the SAME check on
every `build()`, against the artifact `build()` just produced — these tests
cover its own logic directly, against hand-built fixtures, so they need no
binary and no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import graph_checks


def _write(path: Path, data: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _graph(
    nodes: list[dict[str, object]], hyperedges: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": nodes,
        "links": [],
        "hyperedges": hyperedges or [],
    }


def test_a_clean_graph_passes(tmp_path):
    """CONTROL ARM for both checks: a depth<=1 id and a resolving hyperedge must NOT raise.

    Covers all three id shapes this restructure produces: corpus
    (`graphify::foo`), self (`.self-graph::bar`), and an unprefixed semantic
    doc node — `_merge_docs.py` never routes through `merge-graphs`.
    """
    path = _write(
        tmp_path / "graph.json",
        _graph(
            nodes=[
                {"id": "graphify::foo"},
                {"id": ".self-graph::bar"},
                {"id": "some_doc_node"},
            ],
            hyperedges=[{"id": "he1", "nodes": ["graphify::foo", ".self-graph::bar"]}],
        ),
    )
    graph_checks.assert_composition(path, tag="kb-build")  # must not raise


def test_a_clean_graph_with_no_hyperedges_passes(tmp_path):
    """CONTROL ARM's sibling: the hyperedge check must not fire on an empty list.

    Without this, a check that raises on `not hyperedges` — rather than only on
    an unresolved MEMBER — would refuse every ordinary build; hyperedges are
    the exception here, not the rule.
    """
    path = _write(tmp_path / "graph.json", _graph(nodes=[{"id": "graphify::foo"}]))
    graph_checks.assert_composition(path, tag="kb-build")  # must not raise


def test_a_passing_build_still_reports_the_hyperedge_census(tmp_path, capsys):
    """Silence is the wrong success signal, so the counts are printed either way (#176).

    Nothing else in the toolchain reports them — `kb-insights` covers
    provenance, community spans, cross-origin edges and size, but not
    hyperedges. Before this line the only way to answer "how many does the
    aggregate hold, and do their members resolve?" was an ad-hoc probe, and
    #176 asks for that figure after every change. Asserting on the NUMBERS and
    not merely that something was printed is the point: a census that prints
    `0 hyperedge(s)` on a graph holding five is worse than no census.
    """
    path = _write(
        tmp_path / "graph.json",
        _graph(
            nodes=[{"id": "graphify::foo"}, {"id": ".self-graph::bar"}, {"id": "doc_node"}],
            hyperedges=[{"id": "he1", "nodes": ["graphify::foo", ".self-graph::bar", "doc_node"]}],
        ),
    )
    graph_checks.assert_composition(path, tag="kb-build")
    out = capsys.readouterr().out
    assert "3 node ids" in out, out
    assert "1 hyperedge(s) / 3 member(s)" in out, out
    assert "0 dangling" in out, out


def test_a_depth_two_id_fails(tmp_path):
    """The #120 shape: an id carrying TWO `::` separators must be refused.

    It means an input was merged more than once — a pairwise loop, or a
    second `merge-graphs` call feeding the aggregate back into itself as an
    input.
    """
    path = _write(
        tmp_path / "graph.json",
        _graph(nodes=[{"id": "graphify::foo"}, {"id": "outer::graphify::foo"}]),
    )
    with pytest.raises(SystemExit) as exc:
        graph_checks.assert_composition(path, tag="kb-build")
    assert "outer::graphify::foo" in str(exc.value), (
        f"the refusal must name the offending id; it said {exc.value!r}"
    )


def test_a_single_separator_id_is_not_a_violation(tmp_path):
    """CONTROL ARM for the test above: exactly one `::` is the NORMAL shape.

    It must not trip the check — without this arm, a check that flags any id
    containing `::` at all (rather than more than one) would refuse every
    healthy build, and the test above could not distinguish the two.
    """
    path = _write(tmp_path / "graph.json", _graph(nodes=[{"id": "graphify::foo"}]))
    graph_checks.assert_composition(path, tag="kb-build")  # must not raise


def test_a_dangling_hyperedge_member_fails(tmp_path):
    """A hyperedge whose member does not resolve to any node id must be refused.

    The same class of loss `hyperedges.py` documents graphify's OWN
    revalidation silently causing, now caught as a build-time refusal instead
    of a silent drop the next reader has to discover on their own.
    """
    path = _write(
        tmp_path / "graph.json",
        _graph(
            nodes=[{"id": "graphify::foo"}],
            hyperedges=[{"id": "he1", "nodes": ["graphify::foo", "graphify::vanished"]}],
        ),
    )
    with pytest.raises(SystemExit) as exc:
        graph_checks.assert_composition(path, tag="kb-build")
    assert "graphify::vanished" in str(exc.value), (
        f"the refusal must name the offending member; it said {exc.value!r}"
    )


def test_census_reports_a_nonzero_dangling_count(tmp_path, capsys):
    """A census that hardcodes '0 dangling' would survive the existing test.

    `test_a_passing_build_still_reports_the_hyperedge_census` above asserts
    `"0 dangling" in out` on a graph whose members all resolve — the ONE field
    that check never varies. Mutating `f"{len(dangling)} dangling"` to a
    hardcoded `"0 dangling"` literal survives it, which is exactly the
    "a census that prints 0 hyperedge(s) on a graph holding five is worse than
    no census" failure that same test's docstring names. This proves the
    printed count reflects a GENUINELY dangling member, on a graph where the
    census print (before the `SystemExit`) and the refusal both fire.
    """
    path = _write(
        tmp_path / "graph.json",
        _graph(
            nodes=[{"id": "graphify::foo"}],
            hyperedges=[{"id": "he1", "nodes": ["graphify::foo", "graphify::vanished"]}],
        ),
    )
    with pytest.raises(SystemExit):
        graph_checks.assert_composition(path, tag="kb-build")
    out = capsys.readouterr().out
    assert "1 dangling" in out, out
    assert "0 dangling" not in out, out


def test_tag_kb_build_reaches_the_output_and_kb_watch_does_not(tmp_path, capsys):
    """`tag` must actually reach the printed line, and name the RIGHT caller.

    Written as a twin with the test below so neither can be satisfied by a
    hardcoded string: a hardcoded "[kb-build]" would pass this test and fail
    its sibling, and vice versa.
    """
    path = _write(tmp_path / "graph.json", _graph(nodes=[{"id": "graphify::foo"}]))
    graph_checks.assert_composition(path, tag="kb-build")
    out = capsys.readouterr().out
    assert "[kb-build]" in out, out
    assert "[kb-watch]" not in out, out


def test_tag_kb_watch_reaches_the_output_and_kb_build_does_not(tmp_path, capsys):
    """CONTROL ARM / twin of the test above — see its docstring."""
    path = _write(tmp_path / "graph.json", _graph(nodes=[{"id": "graphify::foo"}]))
    graph_checks.assert_composition(path, tag="kb-watch")
    out = capsys.readouterr().out
    assert "[kb-watch]" in out, out
    assert "[kb-build]" not in out, out


def test_a_non_string_hyperedge_member_is_reported_as_a_shape_problem(tmp_path):
    """A member that is not a string id must say SO, not 'renamed or dropped'.

    Before #176 round 2, `dangling.extend(str(m) for m in members if str(m)
    not in ids)` coerced EVERY member with `str()` before comparing — so an
    object member like `{"id": "a"}` produced `"{'id': 'a'} dangling"`,
    asserting a cause (renamed/dropped) that is false: nothing was renamed,
    the member was never a valid id to begin with. `str()` never raises here,
    so the old code did not crash — it just told the reader the wrong story,
    sending them hunting for a missing node when the real problem is the
    extraction's shape.
    """
    path = _write(
        tmp_path / "graph.json",
        _graph(
            nodes=[{"id": "graphify::foo"}],
            hyperedges=[{"id": "he1", "nodes": ["graphify::foo", {"id": "a"}]}],
        ),
    )
    with pytest.raises(SystemExit) as exc:
        graph_checks.assert_composition(path, tag="kb-build")
    message = str(exc.value)
    assert "not string ids" in message, message
    assert "SHAPE problem" in message, message
    assert "renamed or dropped" not in message, (
        f"a non-string member was blamed on a rename/drop that never happened: {message}"
    )


def test_a_dangling_string_member_still_gets_the_renamed_or_dropped_message(tmp_path):
    """CONTROL ARM: a genuinely unresolved STRING member keeps the old message.

    The split above must not turn every dangling member into a 'shape
    problem' — only a non-string one is. Re-asserted here alongside the
    shape-problem test above so a regression that merges the two branches
    back into one is caught from both sides at once.
    """
    path = _write(
        tmp_path / "graph.json",
        _graph(
            nodes=[{"id": "graphify::foo"}],
            hyperedges=[{"id": "he1", "nodes": ["graphify::foo", "graphify::vanished"]}],
        ),
    )
    with pytest.raises(SystemExit) as exc:
        graph_checks.assert_composition(path, tag="kb-build")
    message = str(exc.value)
    assert "renamed or dropped" in message, message
    assert "SHAPE problem" not in message, message


def test_both_violations_are_reported_together(tmp_path):
    """Neither check may short-circuit the other.

    A build with both problems must not report only whichever one happened to
    be checked first, or a fix-then-rebuild cycle discovers its problems one
    at a time instead of all at once.
    """
    path = _write(
        tmp_path / "graph.json",
        _graph(
            nodes=[{"id": "outer::graphify::foo"}],
            hyperedges=[{"id": "he1", "nodes": ["graphify::vanished"]}],
        ),
    )
    with pytest.raises(SystemExit) as exc:
        graph_checks.assert_composition(path, tag="kb-build")
    message = str(exc.value)
    assert "outer::graphify::foo" in message
    assert "graphify::vanished" in message
