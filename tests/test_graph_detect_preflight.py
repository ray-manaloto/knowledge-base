# Copyright (c) 2026 Raymond Manaloto
"""Complete, deterministic Graphify detection preflight."""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import graph
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
