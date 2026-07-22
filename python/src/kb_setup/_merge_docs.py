"""Merge a committed doc-extraction chunk into graphify-out/graph.json.

Runs under graphify's BUNDLED interpreter (imports graphify), invoked by
graph.py via subprocess — NOT under the KB repo's uv python.

Usage: python _merge_docs.py <chunk.json> <source_root_abs> <graph.json>
"""

import json
import sys
from pathlib import Path

from graphify.analyze import god_nodes, suggest_questions, surprising_connections
from graphify.build import build_merge
from graphify.cluster import cluster, score_all
from graphify.export import to_json


def main() -> int:
    chunk_path, root, out = sys.argv[1], sys.argv[2], sys.argv[3]
    chunk = json.loads(Path(chunk_path).read_text(encoding="utf-8"))
    n = len(chunk.get("nodes", []))
    if n == 0:
        print(f"[merge] {chunk_path}: 0 nodes — skipped")
        return 0

    G = build_merge([chunk], graph_path=out, prune_sources=None, root=root, directed=False)
    communities = cluster(G)
    cohesion = score_all(G, communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)

    if not to_json(G, communities, out):
        print("[merge] ERROR: to_json refused (shrink guard #479)")
        return 1

    try:  # best-effort report/analysis; graph.json is already written
        from graphify.report import generate

        labels = {cid: f"Community {cid}" for cid in communities}
        questions = suggest_questions(G, communities, labels)
        detect_file = Path(out).parent / ".graphify_detect.json"
        detection = (
            json.loads(detect_file.read_text(encoding="utf-8"))
            if detect_file.is_file()
            else {"files": {}, "total_files": 0, "total_words": 0}
        )
        tokens = {"input": 0, "output": 0}
        report = generate(
            G, communities, cohesion, labels, gods, surprises, detection, tokens,
            root, suggested_questions=questions,
        )
        (Path(out).parent / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    except Exception as e:  # noqa: BLE001 - report is optional
        print(f"[merge] note: report skipped ({type(e).__name__}: {e})")

    print(f"[merge] {chunk_path}: +{n} doc nodes -> {G.number_of_nodes()} nodes, "
          f"{G.number_of_edges()} edges, {len(communities)} communities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
