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
    graph_checks.assert_composition(path)  # must not raise


def test_a_clean_graph_with_no_hyperedges_passes(tmp_path):
    """CONTROL ARM's sibling: the hyperedge check must not fire on an empty list.

    Without this, a check that raises on `not hyperedges` — rather than only on
    an unresolved MEMBER — would refuse every ordinary build; hyperedges are
    the exception here, not the rule.
    """
    path = _write(tmp_path / "graph.json", _graph(nodes=[{"id": "graphify::foo"}]))
    graph_checks.assert_composition(path)  # must not raise


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
    graph_checks.assert_composition(path)
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
        graph_checks.assert_composition(path)
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
    graph_checks.assert_composition(path)  # must not raise


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
        graph_checks.assert_composition(path)
    assert "graphify::vanished" in str(exc.value), (
        f"the refusal must name the offending member; it said {exc.value!r}"
    )


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
        graph_checks.assert_composition(path)
    message = str(exc.value)
    assert "outer::graphify::foo" in message
    assert "graphify::vanished" in message
