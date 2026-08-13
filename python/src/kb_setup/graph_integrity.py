# Copyright (c) 2026 Raymond Manaloto
"""Dependency anchors and Graphify limit semantics for the shared corpus.

Canonical dependencies are navigation anchors, not graph-theory ``god_nodes``.
Graphify's god-node analysis ranks high-degree real entities and deliberately
excludes concept nodes.  Injecting dependencies into that ranking would game a
useful structural measurement.  This module therefore writes a separate typed
artifact whose ordering is based on corpus coverage, evidence receipts, and
cross-dependency project reach -- never degree.

The same audit keeps four unrelated limits distinct.  A query's displayed
subgraph is bounded by ``graphify query --budget``; none of Graphify's three
``GRAPHIFY_MAX_*`` environment variables raises that display budget.
"""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import events, insights

if TYPE_CHECKING:
    from collections.abc import Mapping

_GRAPH = "graphify-out/graph.json"
_CURRENCY = "currency.toml"
_ANCHOR_ARTIFACT = "graphify-out/dependency-anchors.json"
_DEFAULT_QUERY_BUDGET = 2_000
_DEFAULT_GRAPH_BYTES = 512 * 1024 * 1024
_DEFAULT_CONTEXTS = 8
_BUDGET_ARG_COUNT = 2


@dataclass(frozen=True)
class QueryLimits:
    """Effective values and, critically, the separate surface each controls."""

    query_output_tokens: int
    semantic_llm_output_tokens: int | None
    graph_load_bytes: int
    mcp_project_contexts: int


@dataclass(frozen=True)
class AnchorSourceCoverage:
    """Coverage for one declaratively required source subtree."""

    prefix: str
    graph_nodes: int
    receipts: int


@dataclass(frozen=True)
class CanonicalDependency:
    """A typed dependency anchor derived from committed config and the graph."""

    type: str
    name: str
    repo: str
    manifest: str
    source_prefixes: tuple[str, ...]
    source_coverage: tuple[AnchorSourceCoverage, ...]
    graph_nodes: int
    source_receipts: int
    project_reach: tuple[str, ...]
    typed_edges: int
    god_node_eligible: bool = False

    @property
    def rank_key(self) -> tuple[int, int, int, str]:
        """Coverage, receipts, then reach; degree is intentionally unavailable."""
        return (self.graph_nodes, self.source_receipts, len(self.project_reach), self.name)


@dataclass(frozen=True)
class AnchorAudit:
    """Exact dependency-anchor coverage over one graph snapshot."""

    anchors: tuple[CanonicalDependency, ...]
    cross_dependency_edges: int

    @property
    def missing(self) -> tuple[str, ...]:
        """Configured dependencies with no nodes in the graph."""
        return tuple(anchor.name for anchor in self.anchors if anchor.graph_nodes == 0)

    @property
    def missing_sources(self) -> tuple[str, ...]:
        """Declared offline/code source subtrees with no nodes in the graph."""
        return tuple(
            f"{anchor.name}:{source.prefix}"
            for anchor in self.anchors
            for source in anchor.source_coverage
            if source.graph_nodes == 0
        )

    @property
    def red(self) -> bool:
        """No anchor may be absent, and a shared graph must connect dependencies."""
        return bool(self.missing_sources) or self.cross_dependency_edges == 0


def _positive_int(raw: str | None, default: int | None) -> int | None:
    """Graphify's positive-int convention: blank, invalid, and <=0 use default."""
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _graph_bytes(raw: str | None) -> int:
    """Mirror Graphify 0.9.39's bytes/MB/GB graph-load-cap grammar."""
    if raw is None or not raw.strip():
        return _DEFAULT_GRAPH_BYTES
    text = raw.strip().upper()
    multiplier = 1
    if text.endswith("GB"):
        multiplier = 1024**3
        text = text[:-2].strip()
    elif text.endswith("MB"):
        multiplier = 1024**2
        text = text[:-2].strip()
    parsed = _positive_int(text, None)
    return parsed * multiplier if parsed is not None else _DEFAULT_GRAPH_BYTES


def classify_limits(
    *, query_budget: int = _DEFAULT_QUERY_BUDGET, env: Mapping[str, str] | None = None
) -> QueryLimits:
    """Classify the four independent caps without claiming one changes another."""
    source = os.environ if env is None else env
    budget = query_budget if query_budget > 0 else _DEFAULT_QUERY_BUDGET
    semantic = _positive_int(source.get("GRAPHIFY_MAX_OUTPUT_TOKENS"), None)
    raw_contexts = source.get("GRAPHIFY_MAX_CONTEXTS")
    try:
        contexts = max(1, int(raw_contexts)) if raw_contexts and raw_contexts.strip() else 8
    except ValueError:
        contexts = _DEFAULT_CONTEXTS
    return QueryLimits(
        query_output_tokens=budget,
        semantic_llm_output_tokens=semantic,
        graph_load_bytes=_graph_bytes(source.get("GRAPHIFY_MAX_GRAPH_BYTES")),
        mcp_project_contexts=contexts,
    )


def _configured_dependencies(repo_root: Path) -> dict[str, tuple[str, str, tuple[str, ...]]]:
    """Currency tools carrying a source manifest, keyed by graph repo tag."""
    data = tomllib.loads((repo_root / _CURRENCY).read_text(encoding="utf-8"))
    configured: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    prefix_owner: dict[str, str] = {}
    for name, raw in data.get("tool", {}).items():
        manifest = raw.get("manifest") if isinstance(raw, dict) else None
        if not isinstance(manifest, str):
            continue
        repo = Path(manifest).stem
        raw_prefixes = raw.get("anchor_source_prefixes", [])
        extras = (
            tuple(str(prefix) for prefix in raw_prefixes) if isinstance(raw_prefixes, list) else ()
        )
        prefixes = (f"{repo}/", *extras)
        for prefix in prefixes:
            for previous_prefix, previous in prefix_owner.items():
                overlaps = prefix.startswith(previous_prefix) or previous_prefix.startswith(prefix)
                if overlaps and previous != repo:
                    msg = (
                        f"anchor source prefixes {prefix!r} and {previous_prefix!r} "
                        f"overlap across {repo!r} and {previous!r}"
                    )
                    raise ValueError(msg)
            prefix_owner[prefix] = repo
        configured[repo] = (str(name), manifest, prefixes)
    return configured


def _node_anchor(
    node: Mapping[str, str],
    configured: Mapping[str, tuple[str, str, tuple[str, ...]]],
) -> str | None:
    """Resolve one node to at most one anchor, refusing attribution collisions."""
    matches: set[str] = set()
    repo = node.get("repo")
    if repo is not None and repo in configured:
        matches.add(repo)
    source_file = node.get("source_file", "")
    for candidate, (_name, _manifest, prefixes) in configured.items():
        if any(source_file.startswith(prefix) for prefix in prefixes):
            matches.add(candidate)
    if len(matches) > 1:
        node_id = node.get("id", "<unknown>")
        msg = f"graph node {node_id!r} maps to multiple anchors: {sorted(matches)}"
        raise ValueError(msg)
    return next(iter(matches), None)


def audit_anchors(repo_root: Path) -> AnchorAudit:
    """Stream the graph once and compute exact anchor coverage and reach."""
    configured = _configured_dependencies(repo_root)
    graph = repo_root / _GRAPH
    node_repo: dict[str, str] = {}
    nodes = dict.fromkeys(configured, 0)
    receipts = {repo: set() for repo in configured}
    primary_nodes = dict.fromkeys(configured, 0)
    primary_receipts = {repo: set() for repo in configured}
    prefix_nodes = {
        (repo, prefix): 0
        for repo, (_name, _manifest, prefixes) in configured.items()
        for prefix in prefixes[1:]
    }
    prefix_receipts = {key: set() for key in prefix_nodes}
    reach = {repo: set() for repo in configured}
    typed_edges = dict.fromkeys(configured, 0)
    cross_edges = 0

    with graph.open(encoding="utf-8") as fh:
        insights.seek_top_level_array(fh, '"nodes": [')
        for node in insights.iter_top_level_objects(fh, '"links": ['):
            node_id, repo = node.get("id"), _node_anchor(node, configured)
            if node_id is None or repo is None:
                continue
            node_repo[node_id] = repo
            nodes[repo] += 1
            if source_file := node.get("source_file"):
                receipts[repo].add(source_file)
                if node.get("repo") == repo or source_file.startswith(configured[repo][2][0]):
                    primary_nodes[repo] += 1
                    primary_receipts[repo].add(source_file)
                for prefix in configured[repo][2][1:]:
                    if source_file.startswith(prefix):
                        prefix_nodes[(repo, prefix)] += 1
                        prefix_receipts[(repo, prefix)].add(source_file)
        for link in insights.iter_top_level_objects(fh, ('"hyperedges"', '"built_at_commit"')):
            source_repo = node_repo.get(link.get("source", ""))
            target_repo = node_repo.get(link.get("target", ""))
            if source_repo is None or target_repo is None or source_repo == target_repo:
                continue
            cross_edges += 1
            typed_edges[source_repo] += 1
            typed_edges[target_repo] += 1
            reach[source_repo].add(target_repo)
            reach[target_repo].add(source_repo)

    anchors = [
        CanonicalDependency(
            type="canonical_dependency",
            name=name,
            repo=repo,
            manifest=manifest,
            source_prefixes=prefixes,
            source_coverage=(
                AnchorSourceCoverage(
                    prefix=f"repo:{repo}",
                    graph_nodes=primary_nodes[repo],
                    receipts=len(primary_receipts[repo]),
                ),
                *(
                    AnchorSourceCoverage(
                        prefix=prefix,
                        graph_nodes=prefix_nodes[(repo, prefix)],
                        receipts=len(prefix_receipts[(repo, prefix)]),
                    )
                    for prefix in prefixes[1:]
                ),
            ),
            graph_nodes=nodes[repo],
            source_receipts=len(receipts[repo]),
            project_reach=tuple(sorted(reach[repo])),
            typed_edges=typed_edges[repo],
        )
        for repo, (name, manifest, prefixes) in configured.items()
    ]
    anchors.sort(key=lambda anchor: anchor.rank_key, reverse=True)
    return AnchorAudit(anchors=tuple(anchors), cross_dependency_edges=cross_edges)


def _write_artifact(repo_root: Path, audit: AnchorAudit) -> Path:
    """Atomically replace the derived typed-anchor artifact."""
    target = repo_root / _ANCHOR_ARTIFACT
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".json.tmp")
    payload = {
        "schema": 1,
        "anchor_type": "canonical_dependency",
        "ranking": ["graph_nodes", "source_receipts", "project_reach"],
        "god_node_eligible": False,
        "cross_dependency_edges": audit.cross_dependency_edges,
        "status": "RED" if audit.red else "GREEN",
        "anchors": [asdict(anchor) for anchor in audit.anchors],
    }
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(target)
    return target


def report(repo_root: Path, args: list[str] | None = None) -> int:
    """Write typed anchors, print limit semantics, and fail closed on a RED graph."""
    argv = list(args or [])
    budget = _DEFAULT_QUERY_BUDGET
    if argv:
        if len(argv) != _BUDGET_ARG_COUNT or argv[0] != "--query-budget" or not argv[1].isdigit():
            events.fail(
                "graph_integrity.bad_args",
                "[kb-graph-integrity] usage: [--query-budget N]",
            )
            return 2
        budget = int(argv[1])

    graph = repo_root / _GRAPH
    currency = repo_root / _CURRENCY
    if not graph.is_file() or not currency.is_file():
        events.fail(
            "graph_integrity.missing_input",
            f"[kb-graph-integrity] requires {_GRAPH} and {_CURRENCY}",
        )
        return 2

    limits = classify_limits(query_budget=budget)
    events.say(
        "graph_integrity.limits",
        "## Graphify limits\n"
        f"  query display: {limits.query_output_tokens:,} tokens (`graphify query --budget`)\n"
        f"  semantic LLM response: {limits.semantic_llm_output_tokens or 'backend default'} "
        "(`GRAPHIFY_MAX_OUTPUT_TOKENS`)\n"
        f"  graph load: {limits.graph_load_bytes:,} bytes (`GRAPHIFY_MAX_GRAPH_BYTES`)\n"
        f"  MCP project LRU: {limits.mcp_project_contexts} (`GRAPHIFY_MAX_CONTEXTS`)\n"
        "  note: the three environment variables do not raise the query display budget.",
    )

    audit = audit_anchors(repo_root)
    target = _write_artifact(repo_root, audit)
    status = "RED" if audit.red else "GREEN"
    events.say(
        "graph_integrity.anchor_header",
        f"\n## Canonical dependency anchors — {status}\n"
        f"  {len(audit.anchors)} typed anchors; "
        f"{audit.cross_dependency_edges:,} cross-dependency edges\n"
        "  rank = graph coverage, evidence receipts, project reach; degree excluded\n"
        "  god_node_eligible = false",
        status=status,
        cross_dependency_edges=audit.cross_dependency_edges,
    )
    for anchor in audit.anchors:
        events.say(
            "graph_integrity.anchor",
            f"  {anchor.name}: {anchor.graph_nodes:,} nodes; "
            f"{anchor.source_receipts:,} receipts; reach="
            f"{','.join(anchor.project_reach) if anchor.project_reach else 'NONE'}",
            name=anchor.name,
            nodes=anchor.graph_nodes,
            receipts=anchor.source_receipts,
            reach=list(anchor.project_reach),
        )
    if audit.missing:
        events.fail(
            "graph_integrity.missing_anchors",
            f"  RED: no graph coverage for {', '.join(audit.missing)}",
            missing=list(audit.missing),
        )
    if audit.missing_sources:
        events.fail(
            "graph_integrity.missing_sources",
            f"  RED: required source subtrees have no graph coverage: "
            f"{', '.join(audit.missing_sources)}",
            missing_sources=list(audit.missing_sources),
        )
    if audit.cross_dependency_edges == 0:
        events.fail(
            "graph_integrity.no_cross_links",
            "  RED: canonical dependencies are isolated. Follow-up contract: add "
            "source-cited semantic relations, rebuild, and require at least one "
            "typed cross-dependency edge; never synthesize an edge or promote an "
            "anchor into god_nodes.",
        )
    events.say("graph_integrity.artifact", f"  artifact: {target.relative_to(repo_root)}")
    return 1 if audit.red else 0
