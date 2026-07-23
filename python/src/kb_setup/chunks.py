"""Host-agent extraction chunks — validate + assemble into a committed doc chunk.

A *chunk* is the JSON a host-agent extraction produces for one source:
`{"nodes": [...], "edges": [...], "hyperedges": [], "input_tokens", "output_tokens"}`.
`kb-build` replays each committed `sources/extractions/*.json` chunk into the graph
(free, no LLM), so the chunk — not the raw fetched body — is the durable artifact.

This module is the reusable seam that USED to be an inline one-off: per-source
extraction chunks (written by the `kb-extract` Workflow fan-out) are validated
against the schema `_merge_docs.py` expects, then union-assembled into one
committed `sources/extractions/<name>-docs.json`. Driven by the mise tasks
`kb-assemble` / `kb-validate-chunks`; logic here so nothing hand-rolls it.
"""

from __future__ import annotations

import json
from pathlib import Path

# The exact node/edge shape graphify's doc merge (`_merge_docs.py` -> build_merge)
# consumes. Kept in sync with the committed chunks under sources/extractions/.
_NODE_REQUIRED = ("id", "label", "file_type", "source_file", "source_url", "captured_at")
_EDGE_REQUIRED = ("source", "target", "relation", "confidence", "confidence_score", "weight")
_CONFIDENCE = ("EXTRACTED", "INFERRED")


def _node_issues(nodes: list, label: str) -> tuple[list[str], set[str]]:
    """Per-node schema/uniqueness problems; also returns the set of valid ids."""
    issues: list[str] = []
    ids: set[str] = set()
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            issues.append(f"{label}: node[{i}] is not an object")
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid:
            issues.append(f"{label}: node[{i}] has no valid string id")
            continue
        if nid in ids:
            issues.append(f"{label}: duplicate node id {nid!r}")
        ids.add(nid)
        missing = [k for k in _NODE_REQUIRED if k not in n]
        if missing:
            issues.append(f"{label}: node {nid!r} missing field(s) {missing}")
    return issues, ids


def _edge_issues(edges: list, ids: set[str], label: str) -> list[str]:
    """Per-edge problems: missing fields, dangling endpoints, bad confidence."""
    issues: list[str] = []
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            issues.append(f"{label}: edge[{i}] is not an object")
            continue
        missing = [k for k in _EDGE_REQUIRED if k not in e]
        if missing:
            issues.append(f"{label}: edge[{i}] missing field(s) {missing}")
            continue
        if e["source"] not in ids:
            issues.append(f"{label}: edge[{i}] dangling source {e['source']!r}")
        if e["target"] not in ids:
            issues.append(f"{label}: edge[{i}] dangling target {e['target']!r}")
        if e["confidence"] not in _CONFIDENCE:
            issues.append(f"{label}: edge[{i}] confidence {e['confidence']!r} not in {_CONFIDENCE}")
    return issues


def validate(chunk: dict, *, label: str = "chunk") -> list[str]:
    """Return a list of schema/integrity problems in one chunk (empty == clean).

    Checks: nodes/edges are lists; every node carries the required fields and a
    non-empty string id; ids are unique WITHIN the chunk; every edge references a
    node present in the chunk (no dangling endpoints) and carries required fields;
    confidence is EXTRACTED|INFERRED. Never raises — the caller decides.
    """
    nodes = chunk.get("nodes")
    edges = chunk.get("edges")
    if not isinstance(nodes, list):
        return [f"{label}: 'nodes' is not a list"]
    if not isinstance(edges, list):
        return [f"{label}: 'edges' is not a list"]
    issues, ids = _node_issues(nodes, label)
    issues.extend(_edge_issues(edges, ids, label))
    return issues


def validate_files(paths: list[Path]) -> dict[Path, list[str]]:
    """Validate each chunk file; return {path: issues} (issues empty == clean)."""
    out: dict[Path, list[str]] = {}
    for p in paths:
        try:
            chunk = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            out[p] = [f"{p.name}: unreadable/invalid JSON: {e}"]
            continue
        out[p] = validate(chunk, label=p.name)
    return out


def _out_path(repo_root: Path, name: str) -> Path:
    stem = name.removesuffix(".json").removesuffix("-docs")
    return repo_root / "sources" / "extractions" / f"{stem}-docs.json"


def assemble(repo_root: Path, name: str, chunk_paths: list[Path]) -> Path:
    """Validate + union-merge per-source chunks into one committed doc chunk.

    Each input chunk is validated on its own; then ids are checked for collisions
    ACROSS the set (extraction prefixes ids per source, so a collision is a bug);
    nodes/edges are concatenated (no cross-source dedup — the aggregate graph spans
    many sources, so `_merge_docs.py` merges with dedup=False by design). Writes
    `sources/extractions/<name>-docs.json` and returns its path. Raises ValueError
    on any validation/collision problem — fail loud, never write a broken chunk.
    """
    nodes: list = []
    edges: list = []
    seen: dict[str, str] = {}
    problems: list[str] = []

    for p in chunk_paths:
        try:
            chunk = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            problems.append(f"{p.name}: unreadable/invalid JSON: {e}")
            continue
        problems.extend(validate(chunk, label=p.name))
        for n in chunk.get("nodes", []):
            nid = n.get("id") if isinstance(n, dict) else None
            if isinstance(nid, str) and nid:
                if nid in seen and seen[nid] != p.name:
                    problems.append(f"id collision {nid!r} ({p.name} vs {seen[nid]})")
                seen[nid] = p.name
            nodes.append(n)
        edges.extend(chunk.get("edges", []))

    if problems:
        raise ValueError(
            f"assemble '{name}': {len(problems)} problem(s):\n  " + "\n  ".join(problems)
        )

    out = _out_path(repo_root, name)
    out.parent.mkdir(parents=True, exist_ok=True)
    combined = {
        "nodes": nodes,
        "edges": edges,
        "hyperedges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }
    out.write_text(json.dumps(combined, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
