# Copyright (c) 2026 Raymond Manaloto
"""Contract tests for the public Graphify SDK boundary."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import networkx as nx
import pytest
from kb_setup import graphify_sdk
from kb_setup.graphify_health import IncompleteGraphifyOperationError, SourceCoveragePolicy


def test_graphify_0941_public_sdk_contract_is_current() -> None:
    assert graphify_sdk.contract_errors("0.9.41") == ()


def test_every_contract_symbol_is_public() -> None:
    assert all(
        all(not part.startswith("_") for part in symbol.dotted_name.split("."))
        for symbol in graphify_sdk._PUBLIC_SYMBOLS
    )


def test_signature_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    first = graphify_sdk._PUBLIC_SYMBOLS[0]
    mutant = replace(first, expected_signature="(silently_changed: 'bool') -> 'None'")
    monkeypatch.setattr(
        graphify_sdk,
        "_PUBLIC_SYMBOLS",
        (mutant, *graphify_sdk._PUBLIC_SYMBOLS[1:]),
    )

    with pytest.raises(RuntimeError, match="signature changed"):
        graphify_sdk.assert_public_sdk("0.9.41")


def test_sdk_version_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graphify_sdk, "running_sdk_version", lambda: "0.9.42")

    with pytest.raises(RuntimeError, match=r"version 0\.9\.42"):
        graphify_sdk.assert_public_sdk("0.9.41")


def test_contract_main_checks_the_repository_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from kb_setup import graphify_env

    calls: list[Path] = []
    monkeypatch.setattr(graphify_env, "assert_pinned_graphify", calls.append)
    monkeypatch.setattr(graphify_sdk, "running_sdk_version", lambda: "0.9.41")

    assert graphify_sdk.contract_main(tmp_path) == 0
    assert calls == [tmp_path]
    assert "Graphify CLI/SDK contract PASS: 0.9.41" in capsys.readouterr().out


def test_checked_detect_blocks_required_unclassified_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    required = tmp_path / "mise.toml"
    required.write_text("[tools]\n", encoding="utf-8")
    monkeypatch.setattr(
        graphify_sdk,
        "detect",
        lambda _root: {"total_files": 0, "unclassified": [str(required)]},
    )
    with pytest.raises(IncompleteGraphifyOperationError, match="required-source-unclassified"):
        graphify_sdk.detect_checked(
            tmp_path,
            coverage_policy=SourceCoveragePolicy(required_paths=("mise.toml",)),
        )


def test_checked_detect_allows_only_reviewed_root_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ignored = [tmp_path / ".gitignore", tmp_path / "LICENSE"]
    monkeypatch.setattr(
        graphify_sdk,
        "detect",
        lambda _root: {"total_files": 2, "unclassified": [str(path) for path in ignored]},
    )

    _result, receipt = graphify_sdk.detect_checked(
        tmp_path,
        source_name="10x-Team",
        coverage_policy=SourceCoveragePolicy(optional_unclassified_paths=(".gitignore", "LICENSE")),
    )

    assert receipt.source_name == "10x-Team"
    assert receipt.unclassified_paths == (".gitignore", "LICENSE")


def test_checked_detect_rejects_unknown_code_like_file_with_source_and_bounded_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unknown = [tmp_path / f"unknown-{index}.codeish" for index in range(30)]
    monkeypatch.setattr(
        graphify_sdk,
        "detect",
        lambda _root: {"total_files": 30, "unclassified": [str(path) for path in unknown]},
    )

    with pytest.raises(IncompleteGraphifyOperationError) as caught:
        graphify_sdk.detect_checked(
            tmp_path,
            source_name="hostile-source",
            coverage_policy=SourceCoveragePolicy(
                optional_unclassified_paths=(".gitignore", "LICENSE")
            ),
        )

    message = str(caught.value)
    assert "source=hostile-source" in message
    assert "unknown-0.codeish" in message
    assert "unknown-29.codeish" not in message
    assert len(message) < 1200


def test_checked_detect_timeout_fails_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    def hangs(_root: Path) -> dict[str, object]:
        time.sleep(1)
        return {"total_files": 0, "unclassified": []}

    monkeypatch.setattr(graphify_sdk, "detect", hangs)

    with pytest.raises(IncompleteGraphifyOperationError) as caught:
        graphify_sdk.detect_checked(tmp_path, source_name="slow-source", timeout_seconds=0.01)

    message = str(caught.value)
    assert "source=slow-source" in message
    assert "timeout" in message


def test_checked_extract_blocks_zero_node_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(graphify_sdk, "extract", lambda *_a, **_k: {"nodes": [], "edges": []})
    with pytest.raises(IncompleteGraphifyOperationError, match="zero-node-sources"):
        graphify_sdk.extract_checked([tmp_path / "source.py"], root=tmp_path)


def test_checked_build_blocks_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def warning_build(*_args: object, **_kwargs: object) -> nx.Graph:
        import warnings

        warnings.warn("coverage reduced", stacklevel=2)
        graph = nx.Graph()
        graph.add_node("one")
        return graph

    monkeypatch.setattr(graphify_sdk, "build", warning_build)
    with pytest.raises(IncompleteGraphifyOperationError, match="stderr"):
        graphify_sdk.build_checked([{"nodes": [{"id": "one"}]}], root=tmp_path)


def test_checked_reflect_blocks_missing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(graphify_sdk, "reflect", lambda *_a, **_k: (tmp_path / "gone", {}))
    with pytest.raises(IncompleteGraphifyOperationError, match="reflection-missing"):
        graphify_sdk.reflect_checked(
            tmp_path / "memory",
            tmp_path / "LESSONS.md",
            graph_path=tmp_path / "graph.json",
        )


def test_checked_artifact_blocks_missing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(graphify_sdk, "to_json", lambda *_a, **_k: True)
    with pytest.raises(IncompleteGraphifyOperationError, match="artifacts-partial"):
        graphify_sdk.artifact_checked(nx.Graph(), {}, tmp_path / "graph.json")
