# Copyright (c) 2026 Raymond Manaloto
"""Controls for the real Colibri-to-Graphify canary scorer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import Mock, call

import pytest
from kb_setup import colibri_canary

if TYPE_CHECKING:
    from pathlib import Path


def _write_graph(path: Path, links: list[dict[str, str]]) -> None:
    labels = [
        "Knowledge Base",
        "Dotfiles",
        "Graphify",
        "Graph",
        "Currency Task",
        "Release Notes",
        "Verification Gate",
        "CLI",
        "Python SDK",
    ]
    path.write_text(
        json.dumps(
            {
                "nodes": [{"id": label.casefold(), "label": label} for label in labels],
                "links": links,
            }
        ),
        encoding="utf-8",
    )


def test_semantic_score_requires_source_relation_and_target(tmp_path: Path) -> None:
    graph = tmp_path / "graph.json"
    _write_graph(
        graph,
        [
            {"source": "dotfiles", "relation": "consumes", "target": "graphify"},
            {"source": "graphify", "relation": "extracts", "target": "graph"},
            {"source": "currency task", "relation": "reviews", "target": "release notes"},
            {"source": "verification gate", "relation": "compares", "target": "cli"},
        ],
    )

    score = colibri_canary._semantic_score(graph)

    assert score["passes"] is False
    assert "dotfiles:consumes:knowledge base" not in score["found_edge_signatures"]


def test_semantic_score_accepts_frozen_fixture_contract(tmp_path: Path) -> None:
    graph = tmp_path / "graph.json"
    _write_graph(
        graph,
        [
            {"source": "dotfiles", "relation": "consumes", "target": "knowledge base"},
            {"source": "graphify", "relation": "extracts", "target": "graph"},
            {"source": "currency task", "relation": "reviews", "target": "release notes"},
            {"source": "verification gate", "relation": "compares", "target": "cli"},
        ],
    )

    assert colibri_canary._semantic_score(graph)["passes"] is True


def test_request_rejects_non_loopback_before_network() -> None:
    with pytest.raises(ValueError, match="loopback"):
        colibri_canary._request("https://example.com/v1/models")


def test_explicit_source_accepts_only_pinned_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        colibri_canary,
        "_head_commit",
        Mock(return_value=colibri_canary._COLIBRI_COMMIT),
    )

    assert colibri_canary._source_checkout(tmp_path, tmp_path / "work") == tmp_path


def test_existing_source_refuses_wrong_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(colibri_canary, "_head_commit", Mock(return_value="wrong"))

    with pytest.raises(ValueError, match=colibri_canary._COLIBRI_COMMIT):
        colibri_canary._source_checkout(tmp_path, tmp_path / "work")


def test_missing_source_fetches_only_pinned_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = Mock()
    head_commit = Mock(return_value=colibri_canary._COLIBRI_COMMIT)
    monkeypatch.setattr(colibri_canary, "_run", run)
    monkeypatch.setattr(colibri_canary, "_head_commit", head_commit)

    source = colibri_canary._source_checkout(None, tmp_path)

    assert source == tmp_path / "colibri-source"
    assert run.call_args_list == [
        call(["git", "init"], cwd=source),
        call(
            ["git", "remote", "add", "origin", colibri_canary._COLIBRI_REPO],
            cwd=source,
        ),
        call(
            [
                "git",
                "fetch",
                "--depth",
                "1",
                "origin",
                colibri_canary._COLIBRI_COMMIT,
            ],
            cwd=source,
        ),
        call(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=source),
    ]
    head_commit.assert_called_once_with(source)


def test_glm52_uses_ready_container_without_conversion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    download = Mock(return_value=0)
    run = Mock()
    monkeypatch.setattr(colibri_canary.artifact_download, "download", download)
    monkeypatch.setattr(colibri_canary, "_run", run)
    config = colibri_canary._MODEL_CONFIGS["glm52"]

    model = colibri_canary._prepare_model(config, tmp_path / "source", tmp_path)

    assert model == tmp_path / "model"
    options = download.call_args.args[0]
    assert options.source == config.repo_id
    assert options.revision == config.revision
    assert options.provider_name == "hf-xet"
    assert options.dry_run is False
    run.assert_not_called()


def test_glm52_runtime_is_cpu_only_single_slot_without_mtp(tmp_path: Path) -> None:
    config = colibri_canary._MODEL_CONFIGS["glm52"]

    environment = colibri_canary._server_environment(config)
    command = colibri_canary._server_command(config, tmp_path, tmp_path / "model", 18081)

    assert environment["NOGPU"] == "1"
    assert environment["COLI_METAL"] == "0"
    assert environment["COLI_VULKAN"] == "0"
    assert environment["MTP"] == "0"
    assert environment["KV_SLOTS"] == "1"
    assert config.build_target == "glm"
    assert command[-2:] == ["--kv-slots", "1"]


def test_repeated_extraction_hash_requires_identical_graphs(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text('{"nodes": []}', encoding="utf-8")
    second.write_text('{"nodes": []}', encoding="utf-8")

    assert colibri_canary._sha256(first) == colibri_canary._sha256(second)
    second.write_text('{"nodes": [1]}', encoding="utf-8")
    assert colibri_canary._sha256(first) != colibri_canary._sha256(second)
