# Copyright (c) 2026 Raymond Manaloto
"""Content-bound Graphify build receipt controls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import msgspec
import pytest
from kb_setup import graph


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0"\ndependencies = ["graphifyy[all]==0.9.41"]\n',
        encoding="utf-8",
    )
    out = tmp_path / "graphify-out"
    out.mkdir()
    return tmp_path


def _write_graph(root: Path) -> bytes:
    raw = b'{"nodes":[{"id":"n"}],"edges":[],"hyperedges":[]}\n'
    (root / "graphify-out" / "graph.json").write_bytes(raw)
    return raw


def test_build_receipt_binds_exact_graph_runtime_inputs_and_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    raw = _write_graph(root)
    inputs = {"sources/b.manifest": "sha256:b", "sources/a.manifest": "sha256:a"}
    monkeypatch.setattr(graph.time, "time_ns", lambda: 1_765_432_100_000_000_123)

    path = graph._write_build_receipt(
        root,
        runtime_version="0.9.41",
        inputs=inputs,
    )

    payload = json.loads(path.read_bytes())
    canonical_inputs = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    assert payload == {
        "schema_version": 1,
        "status": "complete",
        "runtime_version": "0.9.41",
        "graph_sha256": hashlib.sha256(raw).hexdigest(),
        "graph_bytes": len(raw),
        "node_count": 1,
        "edge_count": 0,
        "hyperedge_count": 0,
        "input_fingerprints_sha256": hashlib.sha256(canonical_inputs).hexdigest(),
        "recorded_at_ns": 1_765_432_100_000_000_123,
        "warnings": [],
    }


@pytest.mark.parametrize("runtime", ["", "0.9.40", "0.9.42"])
def test_build_receipt_rejects_unknown_or_drifted_runtime(tmp_path: Path, runtime: str) -> None:
    root = _repo(tmp_path)
    _write_graph(root)

    with pytest.raises(SystemExit, match="version drift"):
        graph._write_build_receipt(root, runtime_version=runtime, inputs={})

    assert not (root / "graphify-out" / "build-receipt.json").exists()


def test_build_receipt_rejects_missing_inputs_and_corrupt_graph(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write_graph(root)
    with pytest.raises(SystemExit, match="without corpus input fingerprints"):
        graph._write_build_receipt(root, runtime_version="0.9.41", inputs=None)

    (root / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="graph field 'nodes'"):
        graph._write_build_receipt(root, runtime_version="0.9.41", inputs={})

    assert not (root / "graphify-out" / "build-receipt.json").exists()


def test_clear_stamp_removes_build_receipt_without_currency_config(tmp_path: Path) -> None:
    receipt = tmp_path / "graphify-out" / "build-receipt.json"
    receipt.parent.mkdir()
    receipt.write_text("old", encoding="utf-8")

    graph._clear_stamp(tmp_path)

    assert not receipt.exists()


def test_watch_may_carry_only_an_exact_current_build_receipt(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write_graph(root)
    inputs = {"sources/a.manifest": "sha256:a"}
    graph._write_build_receipt(root, runtime_version="0.9.41", inputs=inputs)
    held = graph._HeldStamp(version="0.9.41", source_ref="abc", inputs=inputs)

    assert graph._current_build_receipt_matches(root, held)

    (root / "graphify-out" / "graph.json").write_bytes(b'{"nodes":[],"edges":[],"hyperedges":[]}\n')
    assert not graph._current_build_receipt_matches(root, held)

    _write_graph(root)
    changed_inputs = graph._HeldStamp(
        version="0.9.41",
        source_ref="abc",
        inputs={"sources/a.manifest": "sha256:changed"},
    )
    assert not graph._current_build_receipt_matches(root, changed_inputs)


def test_watch_rejects_forged_schema_size_and_counts(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write_graph(root)
    inputs = {"sources/a.manifest": "sha256:a"}
    receipt_path = graph._write_build_receipt(root, runtime_version="0.9.41", inputs=inputs)
    receipt = msgspec.json.decode(receipt_path.read_bytes(), type=graph.GraphifyBuildReceipt)
    held = graph._HeldStamp(version="0.9.41", source_ref="abc", inputs=inputs)

    forged = msgspec.structs.replace(
        receipt,
        schema_version=999,
        graph_bytes=1,
        node_count=0,
        edge_count=7,
        hyperedge_count=8,
    )
    receipt_path.write_bytes(msgspec.json.encode(forged))

    assert not graph._current_build_receipt_matches(root, held)


def test_build_refuses_before_manifest_read_when_inputs_are_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    read_manifest = False

    def _load_all(_path: Path) -> tuple[()]:
        nonlocal read_manifest
        read_manifest = True
        return ()

    monkeypatch.setattr(graph, "_input_fingerprints", lambda _root: None)
    monkeypatch.setattr(graph.mf, "load_all", _load_all)

    with pytest.raises(SystemExit, match="input fingerprints are unavailable"):
        graph.build(tmp_path)

    assert not read_manifest
