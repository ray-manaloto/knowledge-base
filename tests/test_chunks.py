"""kb_setup.chunks — validate + assemble host-agent extraction chunks.

Control-armed both directions: a clean chunk passes AND a broken one (dangling
edge, duplicate id, missing field, bad confidence, cross-chunk id collision)
FAILS — a validator that can only pass is not a validator.
"""

import json

import pytest
from kb_setup import chunks


def _node(nid: str, **over: object) -> dict:
    n = {
        "id": nid,
        "label": nid.title(),
        "file_type": "concept",
        "source_file": "src.md",
        "source_url": "https://example.com/src",
        "captured_at": "2026-07-23",
        "author": None,
        "contributor": None,
        "rationale": "A test concept.",
    }
    n.update(over)
    return n


def _edge(src: str, tgt: str, **over: object) -> dict:
    e = {
        "source": src,
        "target": tgt,
        "relation": "relates_to",
        "confidence": "EXTRACTED",
        "confidence_score": 1,
        "source_file": "src.md",
        "weight": 1,
    }
    e.update(over)
    return e


def _chunk(nodes: list[dict], edges: list[dict]) -> dict:
    return {"nodes": nodes, "edges": edges, "hyperedges": [], "input_tokens": 0, "output_tokens": 0}


def test_validate_clean_chunk_has_no_issues() -> None:
    c = _chunk([_node("a"), _node("b")], [_edge("a", "b")])
    assert chunks.validate(c) == []


def test_validate_flags_dangling_edge() -> None:
    c = _chunk([_node("a")], [_edge("a", "ghost")])
    issues = chunks.validate(c)
    assert any("dangling target" in i for i in issues)


def test_validate_flags_duplicate_id() -> None:
    c = _chunk([_node("a"), _node("a")], [])
    assert any("duplicate node id" in i for i in chunks.validate(c))


def test_validate_flags_missing_node_field() -> None:
    bad = _node("a")
    del bad["source_url"]
    assert any("missing field" in i for i in chunks.validate(_chunk([bad], [])))


def test_validate_flags_bad_confidence() -> None:
    c = _chunk([_node("a"), _node("b")], [_edge("a", "b", confidence="MADE_UP")])
    assert any("confidence" in i for i in chunks.validate(c))


def test_assemble_writes_combined_chunk(tmp_path) -> None:
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c1 = tmp_path / "c1.json"
    c2 = tmp_path / "c2.json"
    c1.write_text(json.dumps(_chunk([_node("x_a"), _node("x_b")], [_edge("x_a", "x_b")])))
    c2.write_text(json.dumps(_chunk([_node("y_a")], [])))
    out = chunks.assemble(tmp_path, "mytopic", [c1, c2])
    assert out == tmp_path / "sources" / "extractions" / "mytopic-docs.json"
    got = json.loads(out.read_text())
    assert len(got["nodes"]) == 3
    assert len(got["edges"]) == 1
    assert got["hyperedges"] == []
    assert got["input_tokens"] == 0


def test_assemble_strips_docs_suffix_from_name(tmp_path) -> None:
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_chunk([_node("a")], [])))
    out = chunks.assemble(tmp_path, "topic-docs.json", [c])
    assert out.name == "topic-docs.json"


def test_assemble_raises_on_dangling_edge(tmp_path) -> None:
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_chunk([_node("a")], [_edge("a", "ghost")])))
    with pytest.raises(ValueError, match="dangling"):
        chunks.assemble(tmp_path, "bad", [c])
    assert not (tmp_path / "sources" / "extractions" / "bad-docs.json").exists()


def test_assemble_raises_on_cross_chunk_id_collision(tmp_path) -> None:
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c1 = tmp_path / "c1.json"
    c2 = tmp_path / "c2.json"
    c1.write_text(json.dumps(_chunk([_node("dup")], [])))
    c2.write_text(json.dumps(_chunk([_node("dup")], [])))
    with pytest.raises(ValueError, match="collision"):
        chunks.assemble(tmp_path, "clash", [c1, c2])


def test_validate_files_maps_path_to_issues(tmp_path) -> None:
    good = tmp_path / "good.json"
    bad = tmp_path / "bad.json"
    good.write_text(json.dumps(_chunk([_node("a")], [])))
    bad.write_text("{ not json")
    res = chunks.validate_files([good, bad])
    assert res[good] == []
    assert res[bad]
    assert "JSON" in res[bad][0]
