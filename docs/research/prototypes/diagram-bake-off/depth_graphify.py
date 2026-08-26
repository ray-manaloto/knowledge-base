"""Depth adapter C: read the pre-built `graphify-out/graph.json`, filter to
our own code, and derive intra-Python call edges from `links`.

Two facts from the spec's PREMISES that would silently break this adapter if
ignored:

- `graph.json` has NO `edges` key — the field is `links`.
- The aggregate graph is 492,654 nodes across 58 `repo` values; our own code
  is `repo == ".self-graph"`, exactly 7,054 nodes (1.43%). An unfiltered read
  produces a diagram about `codex` and `ruff`, not this repo.

Probed this session (not in the spec's premises, since it required actually
touching the 736MB file): `links[*].relation` includes `calls`, `references`,
`imports`, `imports_from`, `extends`, `contains`, `defines`, among others — a
call edge is `relation == "calls"`, not `references` (which dominates and is
mostly attribute/type mentions, not invocations).

This adapter NEVER writes `graphify-out/graph.json` — only `graphify-out/`
WRITER tasks (`kb-build`/`kb-merge`/`kb-label`/`kb-artifacts`/`watch`) may,
and none of those run here. Streams via `ijson` rather than `json.load`
because the file is 736MB — loading it whole works but is needlessly slow
and memory-heavy for what is a two-pass filter.
"""

from __future__ import annotations

import time
from pathlib import Path

#: Populated by `depth_edges` as a side effect — see emit.py's driver.
STATS: dict = {}

_SELF_REPO = ".self-graph"


def depth_edges(repo_root: Path) -> list[tuple[str, str]]:
    """Intra-Python `calls` edges among our own (`.self-graph`) nodes."""
    import ijson

    graph_path = repo_root / "graphify-out" / "graph.json"
    if not graph_path.is_file():
        STATS.clear()
        STATS.update({"graphify_error": f"missing {graph_path}"})
        return []

    # Pass 1: which node ids are ours, and what to label them.
    #
    # QUALIFIED by source_file, not bare `label` — measured this session:
    # 90 of 3,401 distinct callable labels in `.self-graph` are reused across
    # more than one file (`main()` in 17 files, `_run()` in 11, `build()` in
    # 2 — including the exact function this adapter seeds its BFS from). A
    # bare-label diagram would silently merge unrelated functions into one
    # node; code2flow avoids this for free (its `name` field is already
    # `file::qualname`), so Shape C needs the same qualification to be a fair
    # comparison rather than a structurally worse one.
    t0 = time.monotonic()
    self_labels: dict[str, str] = {}
    with open(graph_path, "rb") as f:
        for node in ijson.items(f, "nodes.item", use_float=True):
            if node.get("repo") == _SELF_REPO:
                label = node.get("label") or node["id"]
                source_file = node.get("source_file") or "?"
                self_labels[node["id"]] = f"{source_file}::{label}"
    pass1_s = time.monotonic() - t0

    # Pass 2: `calls` links where BOTH ends are ours.
    t1 = time.monotonic()
    edges: list[tuple[str, str]] = []
    connected: set[str] = set()
    total_links = 0
    calls_links = 0
    with open(graph_path, "rb") as f:
        for link in ijson.items(f, "links.item", use_float=True):
            total_links += 1
            if link.get("relation") != "calls":
                continue
            calls_links += 1
            src, dst = link.get("source"), link.get("target")
            if src in self_labels and dst in self_labels:
                edges.append((self_labels[src], self_labels[dst]))
                connected.add(src)
                connected.add(dst)
    pass2_s = time.monotonic() - t1

    STATS.clear()
    STATS.update(
        {
            "graphify_self_node_count": len(self_labels),
            "graphify_total_links_scanned": total_links,
            "graphify_calls_links_total": calls_links,
            "graphify_self_call_edges": len(edges),
            "graphify_self_nodes_with_call_edges": len(connected),
            "graphify_self_nodes_with_call_edges_pct": round(
                100 * len(connected) / len(self_labels), 1
            )
            if self_labels
            else 0.0,
            "graphify_pass1_node_scan_s": round(pass1_s, 2),
            "graphify_pass2_link_scan_s": round(pass2_s, 2),
        }
    )

    build_chain_edges = _filter_to_build_chain(edges)
    STATS["graphify_build_chain_edges"] = len(build_chain_edges)
    return build_chain_edges


#: Preferred BFS seeds, tried in order. `_build_checked` (cli.py:540) is
#: the dispatch target the spec's worked example names — but it is ABSENT
#: from `.self-graph` entirely (measured this session: 32 callable nodes
#: extracted from cli.py total, `_build_checked` not among them, despite
#: existing at the graph's own `built_at_commit` — confirmed via
#: `git merge-base --is-ancestor`, so this is a real extraction gap, not
#: staleness). Fall back to `graph.build()`, the function it calls, which
#: IS present.
_SEED_CANDIDATES = (
    "python/src/kb_setup/cli.py::_build_checked()",
    "python/src/kb_setup/graph.py::build()",
)


def _filter_to_build_chain(edges: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Narrow to nodes reachable from the kb-build chain — same shape as
    depth_code2flow's filter, so the three diagrams are comparable at the
    same scope rather than one being the whole self-graph call slice.
    """
    adjacency: dict[str, set[str]] = {}
    for a, b in edges:
        adjacency.setdefault(a, set()).add(b)

    start = next((s for s in _SEED_CANDIDATES if s in adjacency), None)
    if start is None:
        return edges  # fall back to the whole self-graph call slice

    seen = {start}
    frontier = [start]
    while frontier:
        node = frontier.pop()
        for nxt in adjacency.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)

    return [(a, b) for a, b in edges if a in seen and b in seen]


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    e = depth_edges(root)
    print(f"{len(e)} edges, stats={STATS}")
