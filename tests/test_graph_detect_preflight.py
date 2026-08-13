# Copyright (c) 2026 Raymond Manaloto
"""Complete, deterministic Graphify detection preflight."""

from __future__ import annotations

import subprocess
from pathlib import Path

import msgspec
import pytest
from kb_setup import graph, graphify_health
from kb_setup import manifest as mf


def _manifest(tmp_path: Path, name: str, *, clone: bool = True) -> mf.Manifest:
    manifest = mf.Manifest(
        name=name,
        path=tmp_path / "sources" / f"{name}.manifest",
        url=f"https://example.invalid/{name}",
        ref="main",
        commit="a" * 40,
    )
    if clone:
        (manifest.clone_dir / ".git").mkdir(parents=True)
    return manifest


def test_preflight_reports_all_sources_sorted_and_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifests = [_manifest(tmp_path, "zeta"), _manifest(tmp_path, "alpha")]

    monkeypatch.setattr(
        graph,
        "_run_detection_census",
        lambda _jobs: [
            ("zeta", "IncompleteGraphifyOperationError: bad zeta " + "x" * 900),
            ("alpha", "IncompleteGraphifyOperationError: bad alpha " + "x" * 900),
        ],
    )

    with pytest.raises(SystemExit) as caught:
        graph._detect_preflight(manifests)

    message = str(caught.value)
    assert message.index("alpha:") < message.index("zeta:")
    assert "failed for 2 source(s)" in message
    assert "categories={incomplete: 2}" in message
    assert len(message) < 900


def test_preflight_continues_after_timeout_exception_and_walk_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifests = [
        _manifest(tmp_path, "timeout-source"),
        _manifest(tmp_path, "exception-source"),
        _manifest(tmp_path, "stderr-source"),
    ]

    monkeypatch.setattr(
        graph,
        "_run_detection_census",
        lambda _jobs: [
            ("timeout-source", "IncompleteGraphifyOperationError: timeout"),
            ("exception-source", "OSError: walk exploded"),
            ("stderr-source", "IncompleteGraphifyOperationError: stderr: permission denied"),
        ],
    )

    with pytest.raises(SystemExit) as caught:
        graph._detect_preflight(manifests)

    message = str(caught.value)
    assert "timeout-source" in message
    assert "exception-source" in message
    assert "walk exploded" in message
    assert "stderr-source" in message
    assert "permission denied" in message
    assert "detector-error: 1" in message
    assert "stderr: 1" in message
    assert "timeout: 1" in message


def test_preflight_reports_missing_clone_without_calling_detector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _manifest(tmp_path, "missing", clone=False)
    monkeypatch.setattr(
        graph,
        "_run_detection_census",
        lambda *_args, **_kwargs: pytest.fail("missing clone reached detector"),
    )

    with pytest.raises(SystemExit, match="missing verified clone"):
        graph._detect_preflight([manifest])


def test_clean_preflight_proceeds_for_every_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifests = [_manifest(tmp_path, "beta"), _manifest(tmp_path, "alpha")]
    seen: list[str] = []

    def pass_detect(jobs: list[tuple[str, Path, object]]) -> list[tuple[str, str]]:
        seen.extend(name for name, _root, _policy in jobs)
        return []

    monkeypatch.setattr(graph, "_run_detection_census", pass_detect)

    graph._detect_preflight(manifests)

    assert seen == ["alpha", "beta"]


def test_parent_enforces_hard_child_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _manifest(tmp_path, "slow")
    policy = graph.graphify_health.SourceCoveragePolicy()
    monkeypatch.setattr(graph, "_DETECT_SOURCE_TIMEOUT_SECONDS", 0.001)

    failures = graph._run_detection_census([("slow", manifest.clone_dir, policy)])

    assert failures == [("slow", "TimeoutError: detect source timeout")]


def test_machine_census_receipt_covers_all_sources_and_is_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = _manifest(tmp_path, "docs")
    docs = mf.Manifest(
        name=docs.name,
        path=docs.path,
        url=docs.url,
        ref=docs.ref,
        commit=docs.commit,
        kind="docs",
    )
    code = _manifest(tmp_path, "code")
    monkeypatch.setattr(
        graph,
        "_run_detection_census_receipts",
        lambda _jobs: [
            graph.SourceCensusReceipt(
                source="code",
                kind="code",
                status="incomplete",
                categories=("unclassified-files",),
                unclassified_count=1,
                unclassified=(
                    graph.SourcePathEvidence(path="unknown.codeish", sha256="a" * 64, size=5),
                ),
            )
        ],
    )

    first = graph.detection_census([docs, code])
    second = graph.detection_census([code, docs])

    assert first == second
    assert first.total_sources == 2
    assert first.status_counts == (("incomplete", 1), ("skipped-docs", 1))
    assert [source.source for source in first.sources] == ["code", "docs"]
    assert {source.source_commit for source in first.sources} == {"a" * 40}
    assert msgspec.json.decode(msgspec.json.encode(first))["total_sources"] == 2


def test_census_output_refuses_tracked_or_out_of_repo_path(
    tmp_path: Path,
) -> None:
    receipt = graph.DetectionCensusReceipt(total_sources=0)

    with pytest.raises(ValueError, match=r"under \.agent"):
        graph.write_detection_census(tmp_path, Path("receipt.json"), receipt)
    with pytest.raises(ValueError, match=r"under \.agent"):
        graph.write_detection_census(tmp_path, Path("../escape.json"), receipt)


def test_source_census_hashes_paths_and_bounds_stderr(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    unknown = source / "unknown.codeish"
    unknown.write_text("code\n", encoding="utf-8")
    receipt = graphify_health.assess(
        graphify_health.GraphifyOperation.DETECT,
        graphify_health.GraphifyEvidence(
            observed=True,
            source_name="source",
            stderr="warning " * 1000,
            unclassified_files=1,
            unclassified_paths=("unknown.codeish",),
        ),
    )

    census = graph._source_census_receipt(
        source,
        "source",
        {"total_files": 1, "unclassified": [str(unknown)], "ignored": []},
        receipt,
    )

    assert census.unclassified_count == 1
    assert census.unclassified[0].sha256 == (
        "b57b236c9bcd2a61fcd627b69ae2d7a6eb5bc13f2dc25311348ee08df43bc0c4"
    )
    assert census.unclassified[0].size == 5
    assert len(census.stderr) == graph._CENSUS_MAX_STDERR_LENGTH


def test_machine_census_timeout_is_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _manifest(tmp_path, "slow")
    policy = graph.graphify_health.SourceCoveragePolicy()
    monkeypatch.setattr(graph, "_DETECT_SOURCE_TIMEOUT_SECONDS", 0.001)

    receipts = graph._run_detection_census_receipts([("slow", manifest.clone_dir, policy)])

    assert receipts == [
        graph.SourceCensusReceipt(
            source="slow",
            kind="code",
            status="timed-out",
            categories=("timeout",),
            stderr="detect source timeout",
        )
    ]


def test_ignored_directory_uses_git_tree_hash(tmp_path: Path) -> None:
    root = tmp_path / "source"
    ignored = root / "ignored"
    ignored.mkdir(parents=True)
    (ignored / "file.txt").write_text("retained\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "ignored/file.txt"], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=root,
        check=True,
    )

    evidence = graph._source_path_evidence(root, "ignored")

    assert evidence.file_type == "git-tree"
    assert evidence.sha256 is not None
    assert len(evidence.sha256) == 64
