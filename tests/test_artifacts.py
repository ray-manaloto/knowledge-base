"""kb-artifacts helpers: node counting + the large-graph svg skip."""

import json

from kb_setup import artifacts


def test_node_count_reads_graph(tmp_path) -> None:
    g = tmp_path / "graph.json"
    g.write_text(json.dumps({"nodes": [{"id": "a"}, {"id": "b"}], "edges": []}))
    assert artifacts._node_count(g) == 2


def test_node_count_missing_is_zero(tmp_path) -> None:
    assert artifacts._node_count(tmp_path / "nope.json") == 0


def test_svg_in_default_registry_but_gated_by_limit() -> None:
    # svg ships in the registry (runnable via `only=['svg']`) but the limit exists
    # so a large-graph default run drops it. Guards against the #2076-adjacent crash.
    names = [a[0] for a in artifacts._ARTIFACTS]
    assert "svg" in names
    assert artifacts._SVG_NODE_LIMIT == 5000
