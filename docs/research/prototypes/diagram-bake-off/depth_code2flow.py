"""Depth adapter A: static call graph via code2flow, over `python/src/kb_setup`.

Re-measured this session (not the inherited premise number — see the spec's
PREMISES, row A): `uv run --with code2flow -- code2flow python/src/kb_setup
--output out.json --language py --skip-parse-errors` wrote 1,313 nodes / 1,978
edges in 1.37s wall clock, and reported 51 call sites it could not resolve to
a single definition (`Skipped processing these calls because the algorithm
linked them to multiple function definitions: [...]`) — dynamic dispatch
(`getattr`, `.resolve()` methods across several unrelated classes, etc.)
defeats a purely static resolver. Close to the inherited "~49" but not
identical, which is exactly why the spec called re-measurement out.

Output JSON shape (probed this session, not documented anywhere obvious):
    {"graph": {"directed": bool,
               "nodes": {uid: {"uid", "label", "name"}},
               "edges": [{"source": uid, "target": uid, "directed": bool}]}}
`name` is `"<file-stem>::<qualified.symbol>"` (or `(global)` for module-level
calls) — that's the only field worth using as an edge label.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROTO_ROOT = Path(__file__).resolve().parent
OUT_DIR = PROTO_ROOT / "out"

#: Populated by `depth_edges` as a side effect — see emit.py's driver.
STATS: dict = {}


def _run_code2flow(repo_root: Path, out_json: Path) -> tuple[dict, list[str]]:
    target = repo_root / "python" / "src" / "kb_setup"
    proc = subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "code2flow",
            "--",
            "code2flow",
            str(target),
            "--output",
            str(out_json),
            "--language",
            "py",
            "--skip-parse-errors",
        ],
        capture_output=True,
        text=True,
    )
    (OUT_DIR / "code2flow-stderr.log").write_text(proc.stderr)
    skip_line = next(
        (
            line
            for line in proc.stderr.splitlines()
            if line.startswith("Code2Flow: Skipped processing these calls")
        ),
        "",
    )
    # The line is a python-repr'd list embedded in prose; count entries by
    # counting the `', '` separators between quoted call names (n-1 for n
    # items) rather than re-parsing it — good enough for a spike stat.
    skipped_call_sites = skip_line.count("', '") + 1 if skip_line else 0
    skipped_examples = []
    if skip_line:
        inside = skip_line.split("[", 1)[-1].rsplit("]", 1)[0]
        skipped_examples = [s.strip(" '") for s in inside.split("', '")][:8]

    data = json.loads(out_json.read_text()) if out_json.exists() else {"graph": {}}
    return data, skipped_examples, skipped_call_sites  # type: ignore[return-value]


def depth_edges(repo_root: Path) -> list[tuple[str, str]]:
    """Intra-Python call edges from a fresh code2flow run over kb_setup."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = OUT_DIR / "code2flow-raw.json"
    data, skipped_examples, skipped_call_sites = _run_code2flow(repo_root, out_json)

    graph = data.get("graph", {})
    nodes = graph.get("nodes", {})
    edges: list[tuple[str, str]] = []
    for edge in graph.get("edges", []):
        source = nodes.get(edge["source"], {}).get("name", edge["source"])
        target = nodes.get(edge["target"], {}).get("name", edge["target"])
        edges.append((source, target))

    build_chain_edges = _filter_to_build_chain(edges)

    STATS.clear()
    STATS.update(
        {
            "code2flow_node_count": len(nodes),
            "code2flow_edge_count": len(graph.get("edges", [])),
            "code2flow_skipped_call_sites": skipped_call_sites,
            "code2flow_skipped_examples": skipped_examples,
            "code2flow_build_chain_edges": len(build_chain_edges),
        }
    )
    # The diagram gets the narrowed build-chain slice, not the whole 1,978
    # edge module graph — the full graph is dumped separately for inspection
    # (out/code2flow-raw.json) but is not a readable diagram at that size.
    return build_chain_edges


#: Preferred BFS seeds, tried in order. `cli::_build_checked` IS a node (code2flow
#: parses live source, so unlike graphify's stale pre-built graph it never misses
#: a function that exists) but has ZERO resolved outgoing edges — measured this
#: session: it calls `graph.build(repo_root)` through a function-LOCAL
#: `from kb_setup import ... graph ...` (this codebase's deliberate lazy-import
#: pattern, see cli.py's own comment: "one lazy import per branch"), which
#: defeats code2flow's static import resolution. Fall back to `graph::build`,
#: which IS reachable via module-level imports inside graph.py and has 16
#: resolved outgoing edges.
_SEED_CANDIDATES = ("cli::_build_checked", "graph::build")


def _filter_to_build_chain(edges: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Narrow the whole-module call graph to nodes reachable from the
    kb-build chain — code2flow gives us the whole graph; the worked example
    only wants that slice.
    """
    adjacency: dict[str, set[str]] = {}
    for a, b in edges:
        adjacency.setdefault(a, set()).add(b)

    start = next((s for s in _SEED_CANDIDATES if s in adjacency), None)
    if start is None:
        return edges  # fall back to the whole graph rather than nothing

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
