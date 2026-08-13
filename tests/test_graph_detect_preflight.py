# Copyright (c) 2026 Raymond Manaloto
"""Complete, deterministic Graphify detection preflight."""

from __future__ import annotations

import io
import subprocess
import tarfile
from pathlib import Path

import msgspec
import pytest
from kb_setup import graph, graphify_health, graphify_sdk
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
        "detection_census",
        lambda _manifests: graph.DetectionCensusReceipt(
            state="incomplete",
            total_sources=2,
            sources=(
                graph.SourceCensusReceipt(
                    source="zeta",
                    kind="code",
                    status="incomplete",
                    stderr="bad zeta " + "x" * 900,
                ),
                graph.SourceCensusReceipt(
                    source="alpha",
                    kind="code",
                    status="incomplete",
                    stderr="bad alpha " + "x" * 900,
                ),
            ),
        ),
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
        "detection_census",
        lambda _manifests: graph.DetectionCensusReceipt(
            state="incomplete",
            total_sources=3,
            sources=(
                graph.SourceCensusReceipt(
                    source="timeout-source",
                    kind="code",
                    status="timed-out",
                    categories=("timeout",),
                    stderr="timeout",
                ),
                graph.SourceCensusReceipt(
                    source="exception-source",
                    kind="code",
                    status="error",
                    categories=("detector-error",),
                    stderr="walk exploded",
                ),
                graph.SourceCensusReceipt(
                    source="stderr-source",
                    kind="code",
                    status="incomplete",
                    categories=("stderr",),
                    stderr="permission denied",
                ),
            ),
        ),
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
        "detection_census",
        lambda _manifests: graph.DetectionCensusReceipt(
            state="incomplete",
            total_sources=1,
            sources=(
                graph.SourceCensusReceipt(
                    source="missing",
                    kind="code",
                    status="provenance-failed",
                    categories=("missing-clone",),
                ),
            ),
        ),
    )

    with pytest.raises(SystemExit, match="missing-clone"):
        graph._detect_preflight([manifest])


def test_clean_preflight_proceeds_for_every_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifests = [_manifest(tmp_path, "beta"), _manifest(tmp_path, "alpha")]
    seen: list[str] = []

    def pass_detect(manifests: list[mf.Manifest]) -> graph.DetectionCensusReceipt:
        seen.extend(manifest.name for manifest in manifests)
        return graph.DetectionCensusReceipt(
            total_sources=2,
            sources=tuple(
                graph.SourceCensusReceipt(source=name, kind="code", status="complete")
                for name in sorted(seen)
            ),
        )

    monkeypatch.setattr(graph, "detection_census", pass_detect)

    graph._detect_preflight(manifests)

    assert sorted(seen) == ["alpha", "beta"]


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
    provenance = graph.SourceGitProvenance(
        declared_pin="a" * 40,
        resolved_commit="a" * 40,
        tree_digest="b" * 40,
    )
    monkeypatch.setattr(graph, "_verify_source_provenance", lambda _manifest: provenance)
    monkeypatch.setattr(
        graph,
        "_create_source_snapshot",
        lambda _manifest, verified, destination: (destination.mkdir(), verified)[1],
    )
    monkeypatch.setattr(
        graph,
        "_run_detection_census_receipts",
        lambda _jobs: [
            graph.SourceCensusReceipt(
                source="code",
                kind="code",
                status="incomplete",
                declared_pin="f" * 40,
                resolved_commit="f" * 40,
                tree_digest="f" * 40,
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
    assert {source.declared_pin for source in first.sources} == {"a" * 40}
    assert first.sources[0].resolved_commit == "a" * 40
    assert first.sources[0].tree_digest == "b" * 40
    assert msgspec.json.decode(msgspec.json.encode(first))["total_sources"] == 2


def test_census_rejects_missing_duplicate_and_unexpected_child_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifests = [_manifest(tmp_path, "a"), _manifest(tmp_path, "b")]
    provenance = graph.SourceGitProvenance(
        declared_pin="a" * 40,
        resolved_commit="b" * 40,
        tree_digest="c" * 40,
    )
    monkeypatch.setattr(graph, "_verify_source_provenance", lambda _manifest: provenance)
    monkeypatch.setattr(
        graph,
        "_create_source_snapshot",
        lambda _manifest, verified, destination: (destination.mkdir(), verified)[1],
    )
    monkeypatch.setattr(
        graph,
        "_run_detection_census_receipts",
        lambda _jobs: [
            graph.SourceCensusReceipt(source="b", kind="code", status="complete"),
            graph.SourceCensusReceipt(source="b", kind="code", status="complete"),
            graph.SourceCensusReceipt(source="ghost", kind="code", status="complete"),
        ],
    )

    receipt = graph.detection_census(manifests)

    assert receipt.state == "incomplete"
    assert receipt.total_sources == 2
    assert [source.source for source in receipt.sources] == ["a", "b"]
    assert [source.categories for source in receipt.sources] == [
        ("receipt-missing",),
        ("receipt-duplicate",),
    ]
    assert receipt.integrity_errors == ("unexpected-receipts:1:ghost",)


def test_census_rejects_duplicate_manifest_authority(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, "duplicate")

    with pytest.raises(ValueError, match="duplicate manifest source names: duplicate"):
        graph.detection_census([manifest, manifest])


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
    assert len(census.stderr) <= graph._CENSUS_MAX_STDERR_LENGTH


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

    assert evidence.file_type == "snapshot-tree:1"
    assert evidence.sha256 is not None
    assert len(evidence.sha256) == 64


def _real_manifest(tmp_path: Path, name: str = "source") -> mf.Manifest:
    manifest = _manifest(tmp_path, name, clone=False)
    manifest.clone_dir.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=manifest.clone_dir, check=True)
    (manifest.clone_dir / "source.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.py"], cwd=manifest.clone_dir, check=True)
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
        cwd=manifest.clone_dir,
        check=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=manifest.clone_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return mf.Manifest(
        name=manifest.name,
        path=manifest.path,
        url=manifest.url,
        ref=manifest.ref,
        commit=commit,
    )


def test_census_rejects_declared_aaaa_pin_for_real_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = _real_manifest(tmp_path)
    hostile = mf.Manifest(
        name=real.name,
        path=real.path,
        url=real.url,
        ref=real.ref,
        commit="a" * 40,
    )
    monkeypatch.setattr(
        graph,
        "_run_detection_census_receipts",
        lambda _jobs: pytest.fail("unverified source reached detector"),
    )

    receipt = graph.detection_census([hostile]).sources[0]

    assert receipt.status == "provenance-failed"
    assert receipt.categories == ("pin-unreachable",)
    assert receipt.declared_pin == "a" * 40
    assert receipt.resolved_commit == ""
    assert receipt.tree_digest == ""


def test_census_rejects_missing_and_unresolvable_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = _manifest(tmp_path, "missing", clone=False)
    broken = _manifest(tmp_path, "broken")
    monkeypatch.setattr(
        graph,
        "_run_detection_census_receipts",
        lambda _jobs: pytest.fail("unverified source reached detector"),
    )

    receipts = graph.detection_census([broken, missing]).sources

    assert [(receipt.source, receipt.categories) for receipt in receipts] == [
        ("broken", ("pin-unreachable",)),
        ("missing", ("missing-clone",)),
    ]
    assert all(receipt.status == "provenance-failed" for receipt in receipts)


def test_census_scans_pinned_a_when_worktree_moves_to_b_and_back_to_a(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = _real_manifest(tmp_path)
    original_bytes = (original.clone_dir / "source.py").read_bytes()
    (original.clone_dir / "source.py").write_text("value = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.py"], cwd=original.clone_dir, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "changed tree",
        ],
        cwd=original.clone_dir,
        check=True,
    )
    commit_b = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=original.clone_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert commit_b != original.commit
    (original.clone_dir / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    before = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=original.clone_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    snapshots: list[Path] = []

    def inspect_snapshot(jobs: list[tuple[str, Path, object]]) -> list[graph.SourceCensusReceipt]:
        name, snapshot, _policy = jobs[0]
        snapshots.append(snapshot)
        assert (snapshot / "source.py").read_bytes() == original_bytes
        assert not (snapshot / ".git").exists()
        subprocess.run(
            ["git", "checkout", "--quiet", "--detach", original.commit],
            cwd=original.clone_dir,
            check=True,
        )
        assert (snapshot / "source.py").read_bytes() == original_bytes
        return [graph.SourceCensusReceipt(source=name, kind="code", status="complete")]

    monkeypatch.setattr(graph, "_run_detection_census_receipts", inspect_snapshot)

    receipt = graph.detection_census([original]).sources[0]

    assert receipt.status == "complete"
    assert receipt.resolved_commit == original.commit
    assert receipt.tree_digest
    assert snapshots
    assert not snapshots[0].exists()
    assert (original.clone_dir / "untracked.txt").read_text(encoding="utf-8") == "dirty\n"
    after = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=original.clone_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert after == before
    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=original.clone_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head_after == original.commit
    assert "?? untracked.txt" in after


def test_census_accepts_annotated_tag_object_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _real_manifest(tmp_path)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "tag",
            "-a",
            "v-test",
            "-m",
            "tag",
        ],
        cwd=manifest.clone_dir,
        check=True,
    )
    tag_object = subprocess.run(
        ["git", "rev-parse", "v-test"],
        cwd=manifest.clone_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tagged = mf.Manifest(
        name=manifest.name,
        path=manifest.path,
        url=manifest.url,
        ref="v-test",
        commit=tag_object,
    )
    monkeypatch.setattr(
        graph,
        "_run_detection_census_receipts",
        lambda _jobs: [
            graph.SourceCensusReceipt(source=manifest.name, kind="code", status="complete")
        ],
    )

    receipt = graph.detection_census([tagged]).sources[0]

    assert receipt.status == "complete"
    assert receipt.declared_pin == tag_object
    assert receipt.resolved_commit == manifest.commit
    assert receipt.tree_digest


def test_census_reports_archive_failure_without_running_detector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _real_manifest(tmp_path)

    def fail_archive(_clone: Path, _commit: str, _archive: Path) -> None:
        raise subprocess.CalledProcessError(1, ["git", "archive"])

    monkeypatch.setattr(graph, "_write_git_archive", fail_archive)
    monkeypatch.setattr(
        graph,
        "_run_detection_census_receipts",
        lambda _jobs: pytest.fail("failed archive reached detector"),
    )

    receipt = graph.detection_census([manifest]).sources[0]

    assert receipt.status == "provenance-failed"
    assert receipt.categories == ("archive-failed",)
    assert receipt.resolved_commit == manifest.commit


@pytest.mark.parametrize("hostile", ["traversal", "symlink"])
def test_safe_archive_rejects_traversal_and_links(tmp_path: Path, hostile: str) -> None:
    archive_path = tmp_path / "hostile.tar"
    with tarfile.open(archive_path, "w") as archive:
        if hostile == "traversal":
            info = tarfile.TarInfo("../escape")
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
        else:
            info = tarfile.TarInfo("link")
            info.type = tarfile.SYMTYPE
            info.linkname = "../escape"
            archive.addfile(info)
    destination = tmp_path / "snapshot"
    destination.mkdir()

    with pytest.raises(graph.UnsafeArchiveError):
        graph._safe_extract_git_archive(archive_path, destination)

    assert not (tmp_path / "escape").exists()


def test_snapshot_preserves_source_and_gitignore_semantics(tmp_path: Path) -> None:
    manifest = _real_manifest(tmp_path)
    (manifest.clone_dir / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    ignored = manifest.clone_dir / "ignored"
    ignored.mkdir()
    (ignored / "secret.txt").write_text("tracked but ignored\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=manifest.clone_dir, check=True)
    subprocess.run(["git", "add", "-f", "ignored/secret.txt"], cwd=manifest.clone_dir, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "ignored fixture",
        ],
        cwd=manifest.clone_dir,
        check=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=manifest.clone_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest = mf.Manifest(
        name=manifest.name,
        path=manifest.path,
        url=manifest.url,
        ref=manifest.ref,
        commit=commit,
    )
    before = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=manifest.clone_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    provenance = graph._verify_source_provenance(manifest)
    snapshot = tmp_path / "snapshot"

    result = graph._create_source_snapshot(manifest, provenance, snapshot)
    detected, _receipt = graphify_sdk.observe_detect(snapshot, source_name=manifest.name)

    assert result.failure_category == ""
    assert not (snapshot / ".git").exists()
    assert any(Path(path).name == "ignored" for path in detected["ignored"])
    after = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=manifest.clone_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert after == before


def test_unexpected_100k_name_and_total_receipt_remain_bounded(tmp_path: Path) -> None:
    provenance = graph.SourceGitProvenance(
        declared_pin="a" * 40,
        resolved_commit="b" * 40,
        tree_digest="c" * 40,
    )
    _bound, errors = graph._bind_detection_receipts(
        [("expected", tmp_path, graphify_health.SourceCoveragePolicy())],
        [graph.SourceCensusReceipt(source="x" * 100_000, kind="code", status="complete")],
        {"expected": provenance},
    )

    assert len(errors) == 1
    assert len(errors[0]) < 200
    oversized = graph.DetectionCensusReceipt(
        integrity_errors=("x" * (graph._CENSUS_MAX_RECEIPT_BYTES + 1),)
    )
    with pytest.raises(ValueError, match="aggregate size bound"):
        graph._encode_detection_census(oversized)
