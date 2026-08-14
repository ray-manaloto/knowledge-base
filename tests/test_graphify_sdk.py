# Copyright (c) 2026 Raymond Manaloto
"""Contract tests for the public Graphify SDK boundary."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import networkx as nx
import pytest
from kb_setup import graphify_sdk
from kb_setup.currency import config as currency_config
from kb_setup.graphify_health import (
    ExpectedMetadataOnly,
    ExpectedUnclassifiedFile,
    GraphifyState,
    IncompleteGraphifyOperationError,
    SourceCoveragePolicy,
)


def test_graphify_0943_public_sdk_contract_is_current() -> None:
    assert graphify_sdk.contract_errors("0.9.43") == ()


def test_graphify_0943_watch_conclusions_are_structured_notes() -> None:
    repo = Path(__file__).parent.parent.absolute()
    graphify = {spec.name: spec for spec in currency_config.load(repo)}["graphify"]
    conclusions = {item.ref: item.note for item in graphify.watch if item.kind == "local"}

    assert "2026-08-14 for 0.9.43" in conclusions["label-communities-schema-gap"]
    assert "Remains RESOLVED" in conclusions["mcp-major-pin-is-what-makes-kb-serve-installable"]
    assert "remains UNKNOWN" in conclusions["data-only-json-produces-zero-nodes"]


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
        graphify_sdk.assert_public_sdk("0.9.43")


def test_sdk_version_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graphify_sdk, "running_sdk_version", lambda: "0.9.41")

    with pytest.raises(RuntimeError, match=r"version 0\.9\.41"):
        graphify_sdk.assert_public_sdk("0.9.43")


def test_contract_main_checks_the_repository_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from kb_setup import graphify_env

    calls: list[Path] = []
    monkeypatch.setattr(graphify_env, "assert_pinned_graphify", calls.append)
    monkeypatch.setattr(graphify_sdk, "running_sdk_version", lambda: "0.9.43")

    assert graphify_sdk.contract_main(tmp_path) == 0
    assert calls == [tmp_path]
    assert "Graphify CLI/SDK contract PASS: 0.9.43" in capsys.readouterr().out


def test_checked_detect_blocks_required_unclassified_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    required = tmp_path / "mise.toml"
    required.write_text("[tools]\n", encoding="utf-8")
    monkeypatch.setattr(
        graphify_sdk,
        "detect",
        lambda _root, **_kwargs: {"total_files": 0, "unclassified": [str(required)]},
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
        lambda _root, **_kwargs: {
            "total_files": 2,
            "unclassified": [str(path) for path in ignored],
        },
    )

    _result, receipt = graphify_sdk.detect_checked(
        tmp_path,
        source_name="10x-Team",
        coverage_policy=SourceCoveragePolicy(optional_unclassified_paths=(".gitignore", "LICENSE")),
    )

    assert receipt.source_name == "10x-Team"
    assert receipt.unclassified_paths == (".gitignore", "LICENSE")


def test_checked_detect_normalizes_absolute_results_for_relative_source_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".gitignore").write_text("build/\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)
    relative_root = Path(tmp_path.name)
    monkeypatch.setattr(
        graphify_sdk,
        "detect",
        lambda _root, **_kwargs: {
            "total_files": 1,
            "unclassified": [str(tmp_path / ".gitignore")],
        },
    )

    _result, receipt = graphify_sdk.detect_checked(
        relative_root,
        coverage_policy=graphify_sdk.source_detection_policy(relative_root, "source"),
    )

    assert receipt.unclassified_paths == (".gitignore",)


def test_checked_detect_rejects_unknown_code_like_file_with_source_and_bounded_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unknown = [tmp_path / f"unknown-{index}.codeish" for index in range(30)]
    monkeypatch.setattr(
        graphify_sdk,
        "detect",
        lambda _root, **_kwargs: {
            "total_files": 30,
            "unclassified": [str(path) for path in unknown],
        },
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


def test_observe_detect_retains_incomplete_receipt_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unknown = tmp_path / "unknown.codeish"
    unknown.write_text("code\n", encoding="utf-8")
    monkeypatch.setattr(
        graphify_sdk,
        "detect",
        lambda _root, **_kwargs: {"total_files": 1, "unclassified": [str(unknown)]},
    )

    result, receipt = graphify_sdk.observe_detect(tmp_path, source_name="source")

    assert result["unclassified"] == [str(unknown)]
    assert receipt.state is GraphifyState.INCOMPLETE
    assert receipt.unclassified_paths == ("unknown.codeish",)


def test_observe_detect_uses_ephemeral_cache_outside_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed_cache: list[Path] = []

    def inspect_cache(_root: Path, *, cache_root: Path) -> dict[str, object]:
        assert cache_root.is_dir()
        assert not cache_root.is_relative_to(tmp_path)
        observed_cache.append(cache_root)
        (cache_root / "probe").write_text("cache\n", encoding="utf-8")
        return {"total_files": 0, "unclassified": []}

    monkeypatch.setattr(graphify_sdk, "detect", inspect_cache)

    graphify_sdk.observe_detect(tmp_path)

    assert len(observed_cache) == 1
    assert not observed_cache[0].exists()
    assert list(tmp_path.iterdir()) == []


def test_checked_detect_timeout_fails_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    def hangs(_root: Path, **_kwargs: object) -> dict[str, object]:
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


def test_checked_extract_captures_printed_stderr_and_failed_source_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.py"
    source.write_text("broken\n", encoding="utf-8")

    def incomplete(*_args: object, **_kwargs: object) -> dict[str, object]:
        import sys

        print("parser warning", file=sys.stderr)
        return {"nodes": [{"id": "partial"}], "edges": [], "failed_sources": [str(source)]}

    monkeypatch.setattr(graphify_sdk, "extract", incomplete)

    with pytest.raises(IncompleteGraphifyOperationError) as caught:
        graphify_sdk.extract_checked(
            [source],
            root=tmp_path,
            cache_root=tmp_path.parent / "external-cache",
        )

    message = str(caught.value)
    assert "stderr" in message
    assert "source-coverage-partial" in message
    assert "zero-node-sources" in message


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


def test_checked_build_blocks_printed_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def warning_build(*_args: object, **_kwargs: object) -> nx.Graph:
        import sys

        print("build warning", file=sys.stderr)
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


def test_checked_artifact_blocks_printed_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def warning_export(*_args: object, **_kwargs: object) -> bool:
        import sys

        print("export warning", file=sys.stderr)
        (tmp_path / "graph.json").write_text("{}\n", encoding="utf-8")
        return True

    monkeypatch.setattr(graphify_sdk, "to_json", warning_export)
    with pytest.raises(IncompleteGraphifyOperationError, match="stderr"):
        graphify_sdk.artifact_checked(nx.Graph(), {}, tmp_path / "graph.json")


def test_checked_artifact_binds_source_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "graph.json"
    observed: list[str | None] = []

    def export(
        _graph: nx.Graph,
        _communities: dict[int, list[str]],
        output_path: str,
        *,
        force: bool,
        built_at_commit: str | None,
    ) -> bool:
        assert force
        observed.append(built_at_commit)
        Path(output_path).write_text(
            '{"nodes":[{"id":"n"}],"edges":[],"hyperedges":[]}\n',
            encoding="utf-8",
        )
        return True

    monkeypatch.setattr(graphify_sdk, "to_json", export)

    receipt = graphify_sdk.artifact_checked(
        nx.Graph(),
        {},
        output,
        built_at_commit="a" * 40,
    )

    assert receipt.state is GraphifyState.COMPLETE
    assert observed == ["a" * 40]


_SKIPPED = "data json (not a config/manifest)"
_WARNING = (
    "  warning: 1 source file(s) produced zero nodes and are absent from the graph: "
    "plugin.json. A re-run will retry them (empties are no longer cached); if it persists, "
    "please report the file(s) (#1666).\n"
)


def _metadata_inventory(
    path: Path, *, digest: str | None = None
) -> tuple[ExpectedMetadataOnly, ...]:
    import hashlib

    return (
        ExpectedMetadataOnly(
            source_name="reviewed-source",
            relative_path="plugin.json",
            content_sha256=digest or hashlib.sha256(path.read_bytes()).hexdigest(),
            skipped_disposition=_SKIPPED,
        ),
    )


def test_exact_reviewed_metadata_skip_approves_and_retains_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "plugin.json"
    path.write_text('{"name":"metadata"}\n', encoding="utf-8")
    monkeypatch.setattr(
        graphify_sdk,
        "extract_json",
        lambda _path: {"nodes": [], "edges": [], "skipped": _SKIPPED},
    )

    approved = graphify_sdk.approve_metadata_zero_node_warning(
        tmp_path, "reviewed-source", _WARNING, _metadata_inventory(path)
    )

    assert approved == ("approved-reviewed-metadata-zero-node",)


@pytest.mark.parametrize(
    "mutation", ["hash", "disposition", "missing-disposition", "error", "stderr", "source", "path"]
)
def test_metadata_skip_mutations_do_not_approve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    path = tmp_path / "plugin.json"
    path.write_text('{"name":"metadata"}\n', encoding="utf-8")
    disposition = "unexpected" if mutation == "disposition" else _SKIPPED
    extraction: dict[str, object] = {"nodes": [], "edges": [], "skipped": disposition}
    if mutation == "missing-disposition":
        extraction.pop("skipped")
    if mutation == "error":
        extraction["error"] = "parser failed"
    monkeypatch.setattr(
        graphify_sdk,
        "extract_json",
        lambda _path: extraction,
    )
    digest = "0" * 64 if mutation == "hash" else None
    inventory = _metadata_inventory(path, digest=digest)
    if mutation == "path":
        inventory = (
            ExpectedMetadataOnly(
                source_name="reviewed-source",
                relative_path="missing.json",
                content_sha256=inventory[0].content_sha256,
                skipped_disposition=_SKIPPED,
            ),
        )

    approved = graphify_sdk.approve_metadata_zero_node_warning(
        tmp_path,
        "other-source" if mutation == "source" else "reviewed-source",
        _WARNING + ("unexpected stderr\n" if mutation == "stderr" else ""),
        inventory,
    )

    assert approved == ()


def test_detection_policy_allows_only_safe_root_metadata(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("build/\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("license\n", encoding="utf-8")

    policy = graphify_sdk.source_detection_policy(tmp_path, "source")

    assert set(policy.optional_unclassified_paths) == {".gitignore", "LICENSE"}


def test_detection_policy_rejects_nested_basename_symlink_and_bad_ignore(
    tmp_path: Path,
) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "LICENSE").write_text("nested\n", encoding="utf-8")
    outside = tmp_path.parent / "outside-license"
    outside.write_text("outside\n", encoding="utf-8")
    (tmp_path / "LICENSE").symlink_to(outside)
    (tmp_path / ".claudeignore").write_text("valid/\n", encoding="utf-8")

    policy = graphify_sdk.source_detection_policy(tmp_path, "source")

    assert policy.optional_unclassified_paths == ()


def test_detection_policy_requires_exact_reviewed_source_path_and_hash(tmp_path: Path) -> None:
    import hashlib

    marker = tmp_path / ".github" / "BOILERPLATE_VERSION"
    marker.parent.mkdir()
    marker.write_text("v1\n", encoding="utf-8")
    expected = ExpectedUnclassifiedFile(
        source_name="Attacca",
        relative_path=".github/BOILERPLATE_VERSION",
        content_sha256=hashlib.sha256(marker.read_bytes()).hexdigest(),
        classification="reviewed-version-marker",
    )

    accepted = graphify_sdk.source_detection_policy(tmp_path, "Attacca", (expected,))
    wrong_source = graphify_sdk.source_detection_policy(tmp_path, "other", (expected,))
    marker.write_text("v2\n", encoding="utf-8")
    changed = graphify_sdk.source_detection_policy(tmp_path, "Attacca", (expected,))

    assert accepted.optional_unclassified_paths == (".github/BOILERPLATE_VERSION",)
    assert wrong_source.optional_unclassified_paths == ()
    assert changed.optional_unclassified_paths == ()


def test_claudeignore_requires_exact_source_root_hash_utf8_size_and_grammar(
    tmp_path: Path,
) -> None:
    import hashlib

    ignored = tmp_path / ".claudeignore"
    ignored.write_text("# reviewed\nnode_modules/\n*.log\n", encoding="utf-8")
    expected = ExpectedUnclassifiedFile(
        source_name="Attacca",
        relative_path=".claudeignore",
        content_sha256=hashlib.sha256(ignored.read_bytes()).hexdigest(),
        classification="reviewed-root-ignore-metadata",
    )

    accepted = graphify_sdk.source_detection_policy(tmp_path, "Attacca", (expected,))
    ignored.write_text("command $(unsafe)\n", encoding="utf-8")
    hostile = ExpectedUnclassifiedFile(
        source_name="Attacca",
        relative_path=".claudeignore",
        content_sha256=hashlib.sha256(ignored.read_bytes()).hexdigest(),
        classification="reviewed-root-ignore-metadata",
    )
    rejected = graphify_sdk.source_detection_policy(tmp_path, "Attacca", (hostile,))

    assert accepted.optional_unclassified_paths == (".claudeignore",)
    assert rejected.optional_unclassified_paths == ()
