"""Merge a committed doc-extraction chunk into graphify-out/graph.json.

Runs under graphify's BUNDLED interpreter (imports graphify), invoked by
graph.py via subprocess — NOT under the KB repo's uv python.

Usage: python _merge_docs.py <chunk.json> <source_root_abs> <graph.json>

MERGE-ONLY (#169, #175). This used to also re-cluster (Louvain), score
cohesion, find god nodes and surprising connections, and render GRAPH_REPORT.md
— once PER CHUNK, i.e. once per source in the doc-replay loop. Measured: 17 of
those 18 per-chunk passes were discarded and never read, because `build()`
replays every committed chunk in one run and only the LAST chunk's report
survived on disk. The real clustering/labelling now happens exactly once, in
`build()`, via `graphify_ops.label` — AFTER every chunk (this script, run once
per chunk) and the code layer have all landed. This script's only remaining
job is: merge one chunk in, hand `to_json` a communities mapping, write.
"""

import json
import sys
from pathlib import Path

from graphify.build import build_merge
from graphify.export import to_json


def _communities_from_graph(g: object) -> dict[int, list[str]]:
    """Reconstruct `{community_id: [node_id, ...]}` from each node's own attr.

    Mirrors graphify's own `graphify.serve._communities_from_graph` (verified
    in the installed 0.9.33 source, `serve.py`:69-76) rather than importing
    it: that function lives in the MCP-server module for an unrelated reason
    (answering a live query), and reaching into a leading-underscore symbol
    across modules for a six-line, dependency-free algorithm is more coupling
    than the reuse is worth.

    `to_json` (`export.py`:232) takes `communities: dict[int, list[str]]` as a
    REQUIRED positional argument — there is no "skip clustering" option in its
    signature — so a per-chunk merge that no longer runs Louvain still has to
    hand it something. Reading back what the graph already carries is that
    something: `build_merge` loads the EXISTING graph.json (which already has
    real community assignments from the last full `graphify_ops.label` pass)
    and only appends the new chunk's nodes, so every pre-existing node keeps
    its real community. A node with no `community` attribute at all — brand
    new this chunk, or from a graph that predates any label pass — contributes
    to none, exactly as graphify's own version does; it comes back as
    `community: null` in this write and gets a real assignment at the next
    label pass, rather than being coerced into a guessed bucket here.
    """
    communities: dict[int, list[str]] = {}
    for node_id, data in g.nodes(data=True):
        cid = data.get("community")
        if cid is not None:
            communities.setdefault(int(cid), []).append(node_id)
    return communities


def main() -> int:
    chunk_path, root, out = sys.argv[1], sys.argv[2], sys.argv[3]
    chunk = json.loads(Path(chunk_path).read_text(encoding="utf-8"))
    n = len(chunk.get("nodes", []))
    if n == 0:
        print(f"[merge] {chunk_path}: 0 nodes — skipped")
        return 0

    # dedup=False: the chunk is already single-repo-deduped at extraction, and the
    # target graph now spans MULTIPLE repos — graphify forbids cross-project dedup
    # (a `main` in repo A != repo B), the same reason the code layer merges via
    # `merge-graphs` without deduping. Cross-repo dedup here raises ValueError.
    #
    # build_merge attaches this chunk's own hyperedges (if any) to `G.graph`,
    # resolving their endpoints against the freshly-loaded+merged graph — that
    # is unchanged by this file's #169 restructure; only the analysis/report
    # calls that used to follow it were removed.
    G = build_merge(
        [chunk], graph_path=out, prune_sources=None, root=root, directed=False, dedup=False
    )
    communities = _communities_from_graph(G)

    if not to_json(G, communities, out):
        print("[merge] ERROR: to_json refused (shrink guard #479)")
        return 1

    print(
        f"[merge] {chunk_path}: +{n} doc nodes -> {G.number_of_nodes()} nodes, "
        f"{G.number_of_edges()} edges, {len(communities)} communities carried forward"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
