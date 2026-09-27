# Copyright (c) 2026 Raymond Manaloto
"""Full-build document batching preserves last-source-wins graph semantics."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from graphify.build import build, build_merge
from graphify.export import to_json
from kb_setup import _merge_docs, graph


def _node(node_id: str, source: str) -> dict:
    return {
        "id": node_id,
        "label": node_id,
        "type": "concept",
        "source_file": source,
        "_origin": "semantic",
    }


def _chunk(nodes: list[dict], *, date: str) -> dict:
    for node in nodes:
        node["captured_at"] = date
    return {"nodes": nodes, "edges": [], "hyperedges": []}


def test_collapse_keeps_only_latest_claims_and_unowned_edges() -> None:
    older = _chunk([_node("old", "doc.md"), _node("other", "other.md")], date="2026-08-01")
    older["edges"] = [
        {"source": "old", "target": "other", "source_file": "doc.md"},
        {"source": "old", "target": "other"},
    ]
    newer = _chunk([_node("new", "doc.md")], date="2026-08-02")

    effective, expected = _merge_docs._collapse_replay([older, newer])

    assert [n["id"] for n in effective[0]["nodes"]] == ["other"]
    assert effective[0]["edges"] == [older["edges"][1]]
    assert [n["id"] for n in effective[1]["nodes"]] == ["new"]
    assert expected == {"doc.md": {"new"}, "other.md": {"other"}}


def test_collapse_skips_zero_node_chunk_and_its_edges() -> None:
    live = _chunk([_node("live", "doc.md")], date="2026-08-01")
    empty = {"nodes": [], "edges": [{"source": "live", "target": "live"}], "hyperedges": []}

    effective, expected = _merge_docs._collapse_replay([live, empty])

    assert len(effective) == 1
    assert effective[0]["nodes"][0]["id"] == "live"
    assert effective[0]["edges"] == []
    assert expected == {"doc.md": {"live"}}


def test_batch_output_matches_sequential_supersession(tmp_path: Path) -> None:
    root = tmp_path
    old_path = root / "a-old.json"
    new_path = root / "z-new.json"
    older = _chunk([_node("old", "doc.md"), _node("other", "other.md")], date="2026-08-01")
    older["edges"] = [
        {
            "source": "other",
            "target": "code",
            "relation": "mentions",
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
            "source_file": "other.md",
            "source_location": "L1",
        }
    ]
    newer = _chunk([_node("new1", "doc.md"), _node("new2", "doc.md")], date="2026-08-02")
    newer["edges"] = [
        {
            "source": "new1",
            "target": "new2",
            "relation": "related_to",
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
            "source_file": "doc.md",
        }
    ]
    old_path.write_text(json.dumps(older), encoding="utf-8")
    new_path.write_text(json.dumps(newer), encoding="utf-8")
    sequential = root / "sequential.json"
    batched = root / "batched.json"
    base = build(
        [
            {
                "nodes": [
                    {
                        "id": "code",
                        "label": "code",
                        "type": "function",
                        "source_file": "code.py",
                        "_origin": "ast",
                    }
                ],
                "edges": [],
            }
        ],
        dedup=False,
    )
    assert to_json(base, {}, str(sequential))
    shutil.copyfile(sequential, batched)

    for path in (old_path, new_path):
        merged = build_merge(
            [json.loads(path.read_text())],
            graph_path=sequential,
            root=root,
            directed=False,
            dedup=False,
        )
        assert to_json(merged, _merge_docs._communities_from_graph(merged), str(sequential))
    assert (
        _merge_docs._batch_main(
            ["_merge_docs.py", "--batch", str(root), str(batched), str(old_path), str(new_path)]
        )
        == 0
    )

    def content(path: Path) -> dict:
        data = json.loads(path.read_text())
        return {key: data.get(key) for key in ("nodes", "links", "hyperedges")}

    assert content(batched) == content(sequential)


def test_full_build_dispatches_one_capture_ordered_batch(tmp_path: Path, monkeypatch) -> None:
    older = tmp_path / "z-old.json"
    newer = tmp_path / "a-new.json"
    older.write_text(json.dumps(_chunk([_node("old", "doc.md")], date="2026-08-01")))
    newer.write_text(json.dumps(_chunk([_node("new", "doc.md")], date="2026-08-02")))
    seen: list[list[str]] = []
    monkeypatch.setattr(graph, "_run", lambda argv, _cwd: seen.append(argv))

    graph._replay_doc_chunks(
        tmp_path, "python", tmp_path / "sources", tmp_path / "graph.json", [newer, older]
    )

    assert len(seen) == 1
    assert seen[0][2] == "--batch"
    assert [Path(p).name for p in seen[0][5:]] == ["z-old.json", "a-new.json"]


def test_full_build_with_no_chunks_does_not_invoke_merge(tmp_path: Path, monkeypatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(graph, "_run", lambda argv, _cwd: seen.append(argv))

    graph._replay_doc_chunks(tmp_path, "python", tmp_path / "sources", tmp_path / "graph.json", [])

    assert seen == []
