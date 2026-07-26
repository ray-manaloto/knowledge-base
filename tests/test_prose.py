"""Tests for the prose-only derived graph (kb_setup.prose).

The load-bearing test in this file is not "AST nodes are dropped" — any filter
does that. It is :func:`test_a_prose_node_labelled_code_survives`: the drop rule
is PROVENANCE (`_origin`), and the near-synonym (`file_type == "code"`) would
delete ten real prose nodes, one of them from a golden-set target. The two read
as the same rule and are not, so the difference is pinned here rather than left
to a docstring.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from kb_setup import prose


def _node(node_id: str, **fields: object) -> dict[str, object]:
    return {"id": node_id, "label": node_id, **fields}


def _graph(**overrides: object) -> dict[str, object]:
    """A miniature graph of the same shape graphify writes."""
    graph = {
        "directed": False,
        "multigraph": False,
        "built_at_commit": "deadbeef",
        "graph": {"hyperedges": []},
        "nodes": [
            _node("sym", _origin="ast", file_type="code", source_file="a.py"),
            _node("doc", file_type="concept", source_file="a.md"),
        ],
        "links": [],
    }
    graph.update(overrides)
    return graph


def _derive(tmp_path: Path, graph: dict[str, object]) -> dict[str, object]:
    """Write ``graph``, derive from it, and return the derived JSON."""
    src = tmp_path / "graph.json"
    src.write_text(json.dumps(graph), encoding="utf-8")
    out = tmp_path / prose.PROSE_GRAPH_NAME
    prose.derive(src, out)
    return json.loads(out.read_text(encoding="utf-8"))


def _ids(items: object) -> list[str]:
    """The ``id`` of every entry in a derived list.

    One place for the JSON-shape casts, so each test asserts what survived
    rather than re-establishing that a list is a list.
    """
    assert isinstance(items, list)
    return [str(entry["id"]) for entry in cast("list[dict[str, object]]", items)]


def _key(obj: object, key: str) -> object:
    """Read one key out of a nested JSON object."""
    assert isinstance(obj, dict)
    return cast("dict[str, object]", obj)[key]


def test_ast_nodes_are_dropped_and_prose_survives(tmp_path: Path) -> None:
    """The direction the artifact exists for."""
    derived = _derive(tmp_path, _graph())
    assert _ids(derived["nodes"]) == ["doc"]


def test_a_prose_node_labelled_code_survives(tmp_path: Path) -> None:
    """`file_type` is a LABEL; `_origin` is provenance. Only the second is the rule.

    Measured on the real corpus 2026-07-25: ten nodes carry ``file_type ==
    "code"`` with no ``_origin`` — doc-extraction nodes *about* code, one of them
    from ``fable-orchestrator.md``, which is a golden-set target. Filtering on
    the label as well would delete them, and the topic they belong to would then
    read as unretrievable in the arm built to make it retrievable.
    """
    graph = _graph(
        nodes=[
            _node("sym", _origin="ast", file_type="code", source_file="a.py"),
            _node("about_code", file_type="code", source_file="fable-orchestrator.md"),
        ]
    )
    derived = _derive(tmp_path, graph)
    assert _ids(derived["nodes"]) == ["about_code"]


def test_ast_nodes_that_are_not_labelled_code_are_still_dropped(tmp_path: Path) -> None:
    """The other side of the same distinction — and the bulk of the mass.

    26,361 nodes on the real corpus are ``_origin=ast`` with ``file_type =
    rationale`` (docstrings lifted out of source) and 1,313 with ``concept``
    (package.json dependency names). A filter keyed on the label would leave all
    of them behind, which is most of what makes the unscoped graph unusable.
    """
    graph = _graph(
        nodes=[
            _node("docstring", _origin="ast", file_type="rationale", source_file="a.py"),
            _node("dep", _origin="ast", file_type="concept", source_file="package.json"),
            _node("doc", file_type="concept", source_file="a.md"),
        ]
    )
    derived = _derive(tmp_path, graph)
    assert _ids(derived["nodes"]) == ["doc"]


def test_a_link_to_a_dropped_node_is_removed(tmp_path: Path) -> None:
    """A dangling endpoint is a corrupt graph, not a smaller one."""
    graph = _graph(
        nodes=[
            _node("sym", _origin="ast", file_type="code"),
            _node("doc", file_type="concept"),
            _node("doc2", file_type="concept"),
        ],
        links=[
            {"source": "doc", "target": "sym", "relation": "mentions"},
            {"source": "doc", "target": "doc2", "relation": "relates_to"},
        ],
    )
    derived = _derive(tmp_path, graph)
    assert derived["links"] == [{"source": "doc", "target": "doc2", "relation": "relates_to"}]


def test_a_hyperedge_losing_a_member_is_dropped_whole(tmp_path: Path) -> None:
    """All-or-nothing: a pruned hyperedge asserts something never extracted.

    A hyperedge says *these* nodes participate in one relation. Silently
    removing a member leaves a claim about a different set of nodes, still
    stamped with the extractor's confidence.
    """
    graph = _graph(
        nodes=[
            _node("sym", _origin="ast", file_type="code"),
            _node("doc", file_type="concept"),
            _node("doc2", file_type="concept"),
        ],
        hyperedges=[
            {"id": "mixed", "nodes": ["doc", "sym"], "relation": "form"},
            {"id": "prose_only", "nodes": ["doc", "doc2"], "relation": "form"},
        ],
        graph={
            "hyperedges": [
                {"id": "mixed", "nodes": ["doc", "sym"], "relation": "form"},
                {"id": "prose_only", "nodes": ["doc", "doc2"], "relation": "form"},
            ]
        },
    )
    derived = _derive(tmp_path, graph)
    assert _ids(derived["hyperedges"]) == ["prose_only"]
    # graphify writes the list in BOTH places; a consumer reading the other one
    # would otherwise see hyperedges pointing at nodes this file does not hold.
    assert _ids(_key(derived["graph"], "hyperedges")) == ["prose_only"]


def test_unrelated_top_level_keys_are_carried_through(tmp_path: Path) -> None:
    """The derived file is the same graph, minus mass — not a new format."""
    derived = _derive(tmp_path, _graph())
    assert derived["built_at_commit"] == "deadbeef"
    assert derived["directed"] is False
    assert derived["multigraph"] is False


def test_deriving_a_graph_with_no_prose_refuses_to_write(tmp_path: Path) -> None:
    """An empty graph resolves and knows nothing — it must not be written.

    Written, it would answer every query with nothing, which the eval harness
    reports as a dead query path. That is the correct verdict but the wrong
    diagnosis, and it would arrive minutes later instead of here.
    """
    src = tmp_path / "graph.json"
    src.write_text(json.dumps(_graph(nodes=[_node("sym", _origin="ast")])), encoding="utf-8")
    out = tmp_path / prose.PROSE_GRAPH_NAME
    with pytest.raises(ValueError, match="no non-AST nodes"):
        prose.derive(src, out)
    assert not out.exists()


def test_the_stats_report_both_sides_of_every_count(tmp_path: Path) -> None:
    """Principle 8: surface the counts seen, never a prose summary of them."""
    src = tmp_path / "graph.json"
    src.write_text(json.dumps(_graph()), encoding="utf-8")
    stats = prose.derive(src, tmp_path / prose.PROSE_GRAPH_NAME)
    assert (stats.nodes_in, stats.nodes_out) == (2, 1)
    assert "1/2 nodes" in stats.line


def test_deriving_without_a_built_graph_says_which_task_builds_it(tmp_path: Path) -> None:
    """A "could not look" answer must name the fix, not read as "no prose here"."""
    with pytest.raises(SystemExit, match="kb-build"):
        prose.derive_for(tmp_path)


def test_a_failed_derivation_removes_the_previous_prose_graph(tmp_path: Path) -> None:
    """Fail closed: an aborted derive must leave NO prose graph, not a stale one.

    Nothing downstream can tell the two apart — `kb-query --prose` and the eval
    precondition both ask only whether the file exists — so a surviving artifact
    would go on answering from a corpus derived before the rebuild that just
    failed. Same rule as `graph._clear_stamp` (caught in review of PR #31).
    """
    out = tmp_path / prose.PROSE_GRAPH_NAME
    out.write_text('{"nodes": [{"id": "yesterday"}]}', encoding="utf-8")
    src = tmp_path / "graph.json"
    src.write_text(json.dumps(_graph(nodes=[_node("sym", _origin="ast")])), encoding="utf-8")

    with pytest.raises(ValueError, match="no non-AST nodes"):
        prose.derive(src, out)
    assert not out.exists(), "a stale prose graph outlived the derivation that failed"


def test_a_successful_derivation_replaces_the_previous_prose_graph(tmp_path: Path) -> None:
    """CONTROL ARM: clearing first must not turn a good derive into a deletion."""
    out = tmp_path / prose.PROSE_GRAPH_NAME
    out.write_text('{"nodes": [{"id": "yesterday"}]}', encoding="utf-8")
    src = tmp_path / "graph.json"
    src.write_text(json.dumps(_graph()), encoding="utf-8")

    prose.derive(src, out)
    assert _ids(_key(json.loads(out.read_text(encoding="utf-8")), "nodes")) == ["doc"]
