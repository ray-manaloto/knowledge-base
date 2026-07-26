"""Derive the prose-only graph — the same graph with the code-AST mass dropped.

WHY THIS EXISTS (knowledge-base#12, P0). `graphify query` walks the graph and
truncates its output at a token budget (default 2000) BEFORE the caller sees a
line. This corpus is 128,333 nodes of which 126,228 are AST nodes extracted from
the source repos, so a question about the *documents* competes for that budget
against ~60x its own mass in code symbols — and loses. Measured 2026-07-25 on
the golden set: on the full graph a missed target is not ranked low, it is
**absent from the entire returned list**. The code mass does not out-rank prose,
it crowds prose out of the budget.

So the fix is applied to the corpus, not to the output: a second artifact holding
only the prose layer, which `graphify query --graph` can be pointed at.

WHY NOT THE OTHER TWO SHAPES (both considered and rejected, 2026-07-25):

* A wrapper that raises `--budget` and filters the printed `NODE` lines grades a
  list the truncation already happened to. Post-filtering cannot recover a node
  the budget dropped.
* Upstreaming a `--source`/`--kind` filter to graphify is the right long-term
  home and the wrong schedule — it is a pinned third-party tool, so nothing here
  could move until a release plus a pin bump.

THE DROP RULE IS `_origin`, NOT `file_type`. These read as synonyms and are not.
Measured breakdown of this corpus:

===========================  ==========  =================================
`_origin` / `file_type`      count       what it is
===========================  ==========  =================================
``ast`` / ``code``           98,554      code symbols
``ast`` / ``rationale``      26,361      docstrings lifted out of code
``ast`` / ``concept``         1,313      package.json dependency names
(none) / ``concept``          1,815      prose
(none) / ``rationale``          271      prose
(none) / ``code``                10      **prose**, about code
(none) / ``document``             8      prose
(none) / ``image``                1      prose
===========================  ==========  =================================

Dropping ``file_type == "code"`` as well would delete those last 10 — nodes the
doc-extraction wave produced *about* code, one of them from
``fable-orchestrator.md``, which is a golden-set target. `_origin` is
provenance and is the thing that actually means "this came out of the AST
extractor"; `file_type` is a label the extractor also applies to prose.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

#: The derived artifact's name, alongside `graph.json` in `graphify-out/`.
PROSE_GRAPH_NAME = "graph-prose.json"

#: `_origin` value the AST extractor stamps on every node and link it produces.
AST_ORIGIN = "ast"

type Node = dict[str, object]
type Link = dict[str, object]
type Hyperedge = dict[str, object]


@dataclass(frozen=True)
class ProseStats:
    """What the derivation kept and what it dropped — counts, never a summary."""

    nodes_in: int
    nodes_out: int
    links_in: int
    links_out: int
    hyperedges_in: int
    hyperedges_out: int

    @property
    def line(self) -> str:
        """One-line report, both sides of every count."""
        return (
            f"{self.nodes_out:,}/{self.nodes_in:,} nodes, "
            f"{self.links_out:,}/{self.links_in:,} links, "
            f"{self.hyperedges_out:,}/{self.hyperedges_in:,} hyperedges kept"
        )


def is_ast(node: Node) -> bool:
    """True for a node the AST extractor produced. See the module docstring."""
    return node.get("_origin") == AST_ORIGIN


def prose_graph_path(repo_root: Path) -> Path:
    """Where the derived prose graph lives for this repo."""
    return repo_root / "graphify-out" / PROSE_GRAPH_NAME


def _surviving_hyperedges(edges: Sequence[Hyperedge], keep: set[str]) -> list[Hyperedge]:
    """Hyperedges every one of whose members survived.

    All-or-nothing rather than member-pruning: a hyperedge asserts that a
    specific set of nodes participate in one relation, so a version of it with
    members silently removed states something the extractor never claimed.
    """
    return [e for e in edges if all(m in keep for m in _members(e))]


def _members(edge: Hyperedge) -> list[str]:
    """A hyperedge's member node ids, or [] if it declares none."""
    nodes = edge.get("nodes")
    return [str(n) for n in nodes] if isinstance(nodes, list) else []


def derive(graph_path: Path, out_path: Path) -> ProseStats:
    """Write ``out_path``: ``graph_path`` minus every AST-origin node.

    Links are kept only when BOTH endpoints survive — a dangling endpoint is a
    reference to a node that is not in the file, which is a corrupt graph rather
    than a smaller one.

    Raises:
        ValueError: if nothing survives. An empty graph resolves, answers
            nothing, and would report recall 0 for every query — i.e. it would
            look exactly like the retrieval failure this artifact exists to fix.
    """
    with graph_path.open(encoding="utf-8") as fh:
        graph = json.load(fh)

    nodes: list[Node] = graph.get("nodes", [])
    links: list[Link] = graph.get("links", [])
    meta: dict[str, object] = graph.get("graph", {})
    hyperedges: list[Hyperedge] = graph.get("hyperedges", meta.get("hyperedges", []))

    kept_nodes = [n for n in nodes if not is_ast(n)]
    keep = {str(n["id"]) for n in kept_nodes if "id" in n}
    kept_links = [
        link
        for link in links
        if str(link.get("source")) in keep and str(link.get("target")) in keep
    ]
    kept_edges = _surviving_hyperedges(hyperedges, keep)

    if not kept_nodes:
        raise ValueError(
            f"{graph_path} has no non-AST nodes — the derived prose graph would be "
            f"empty, which resolves and knows nothing. Refusing to write {out_path}."
        )

    out = dict(graph)
    out["nodes"] = kept_nodes
    out["links"] = kept_links
    # graphify writes the hyperedge list in BOTH places (they are the same object
    # on read), so both have to carry the filtered list or a consumer reading the
    # other one sees hyperedges pointing at nodes this file does not contain.
    out["graph"] = dict(meta, hyperedges=kept_edges)
    if "hyperedges" in graph:
        out["hyperedges"] = kept_edges

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    return ProseStats(
        nodes_in=len(nodes),
        nodes_out=len(kept_nodes),
        links_in=len(links),
        links_out=len(kept_links),
        hyperedges_in=len(hyperedges),
        hyperedges_out=len(kept_edges),
    )


def derive_for(repo_root: Path) -> ProseStats:
    """Derive this repo's prose graph from its built graph, and report the counts."""
    graph = repo_root / "graphify-out" / "graph.json"
    if not graph.is_file():
        raise SystemExit(f"no graph at {graph} — run `mise run kb-build` first")
    out = prose_graph_path(repo_root)
    stats = derive(graph, out)
    print(f"[kb-prose] {out.name}: {stats.line}")
    return stats
