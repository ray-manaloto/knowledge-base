"""Generate every graphify output artifact from the current graph.

Single source of truth: the `_ARTIFACTS` registry (data, not copy-paste). Each
entry reads graphify-out/graph.json and writes a distinct file, so the set is
regenerable on demand and none of it needs committing (only graph.json +
manifest.json are). Runs sequentially (safe — no shared-file races).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from kb_setup.graphify_env import clean_env, ensure_runtime_deps

# svg does a full matplotlib spring_layout: O(n^2)-ish (useless hairball at scale)
# AND it feeds node labels through matplotlib mathtext, so any label containing a
# bare `$` raises `ParseException: Expected end of text, found '$'` and fails the
# whole task. graphify already skips its own graph.html above 5000 nodes for the
# same reason; we mirror that for svg. Verified 2026-07-22: a 61,767-node graph
# with a `$`-bearing label crashed `graphify export svg` (rc=1).
_SVG_NODE_LIMIT = 5000

# name -> graphify command. All read graph.json; each writes its own file(s).
# neo4j/falkordb both emit cypher.txt (OpenCypher, usable by either) — one entry.
# svg needs scipy (ensured below) and is slow at scale (full spring_layout).
_ARTIFACTS: list[tuple[str, list[str], str]] = [
    ("report", ["graphify", "cluster-only", ".", "--no-label"], "GRAPH_REPORT.md + graph.html"),
    ("tree", ["graphify", "tree"], "GRAPH_TREE.html"),
    ("callflow", ["graphify", "export", "callflow-html"], "*-callflow.html"),
    ("graphml", ["graphify", "export", "graphml"], "graph.graphml (Gephi/yEd)"),
    ("cypher", ["graphify", "export", "neo4j"], "cypher.txt (Neo4j/FalkorDB)"),
    ("wiki", ["graphify", "export", "wiki"], "wiki/ (agent-crawlable)"),
    ("obsidian", ["graphify", "export", "obsidian"], "obsidian/ (one note per node)"),
    ("svg", ["graphify", "export", "svg"], "graph.svg (slow at scale; needs scipy)"),
]


def _node_count(graph: Path) -> int:
    """Node count from graph.json (0 if unreadable — callers gate on it)."""
    try:
        return len(json.loads(graph.read_text(encoding="utf-8")).get("nodes", []))
    except OSError, json.JSONDecodeError:
        return 0


def generate(repo_root: Path, only: list[str] | None = None) -> int:
    """Generate all artifacts (or the subset in `only`). Returns non-zero on any failure."""
    graph = repo_root / "graphify-out" / "graph.json"
    if not graph.is_file():
        raise SystemExit("graphify-out/graph.json missing — run `mise run kb-build` first")

    ensure_runtime_deps(repo_root)  # scipy for svg, etc.

    selected = [a for a in _ARTIFACTS if not only or a[0] in only]

    # Skip svg on a large graph — it is both doomed (mathtext `$` crash) and
    # useless (unreadable hairball). Explicit skip, NOT a silent drop: an
    # explicitly-requested `only=['svg']` still runs so the failure is visible.
    n_nodes = _node_count(graph)
    if not only and n_nodes > _SVG_NODE_LIMIT:
        before = len(selected)
        selected = [a for a in selected if a[0] != "svg"]
        if len(selected) < before:
            print(
                f"[kb-artifacts] skipping svg: {n_nodes} nodes > {_SVG_NODE_LIMIT} "
                "(full spring_layout is unreadable + crashes on `$` labels)"
            )

    print(f"[kb-artifacts] generating {len(selected)} artifact(s)")
    failures: list[str] = []
    for name, cmd, desc in selected:
        print(f"  → {name}: {desc}")
        # clean_env: no non-Claude backend key reaches graphify (Gemini-free).
        rc = subprocess.run(cmd, cwd=repo_root, env=clean_env(), check=False).returncode
        if rc != 0:
            print(f"    FAILED ({name}, rc={rc})")
            failures.append(name)

    if failures:
        print(f"[kb-artifacts] {len(failures)} failed: {', '.join(failures)}")
        return 1
    print("[kb-artifacts] all artifacts generated")
    return 0
