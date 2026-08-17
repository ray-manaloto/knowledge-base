# Copyright (c) 2026 Raymond Manaloto
"""Complete, deterministic Graphify detection preflight."""

from __future__ import annotations

import shutil
import subprocess
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
    monkeypatch.setattr(graph, "_assert_disposable_clone_identity", lambda *_args: None)
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
    monkeypatch.setattr(graph, "_assert_disposable_clone_identity", lambda *_args: None)
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


def test_public_census_source_filter_admits_exactly_graphify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    graphify = _manifest(tmp_path, "graphify")
    unrelated = _manifest(tmp_path, "unrelated")
    admitted: list[str] = []

    monkeypatch.setattr(graph.mf, "load_all", lambda _path: (unrelated, graphify))

    def census(manifests: list[mf.Manifest]) -> graph.DetectionCensusReceipt:
        admitted.extend(manifest.name for manifest in manifests)
        return graph.DetectionCensusReceipt(
            total_sources=1,
            sources=(graph.SourceCensusReceipt(source="graphify", kind="code", status="complete"),),
        )

    monkeypatch.setattr(graph, "detection_census", census)

    assert graph.detection_census_main(tmp_path, ["--source", "graphify"]) == 0
    assert admitted == ["graphify"]
    assert '"total_sources":1' in capsys.readouterr().out


def test_public_census_source_filter_rejects_missing_and_duplicate_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graphify = _manifest(tmp_path, "graphify")
    monkeypatch.setattr(graph.mf, "load_all", lambda _path: (graphify,))

    with pytest.raises(ValueError, match="source manifest not found: missing"):
        graph.detection_census_main(tmp_path, ["--source", "missing"])
    with pytest.raises(ValueError, match="flag may be specified only once"):
        graph.detection_census_main(
            tmp_path,
            ["--source", "graphify", "--source", "graphify"],
        )


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
        assert (snapshot / ".git").is_dir()
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


def test_census_reports_snapshot_failure_without_running_detector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _real_manifest(tmp_path)

    def fail_snapshot(
        _manifest: mf.Manifest,
        provenance: graph.SourceGitProvenance,
        _destination: Path,
    ) -> graph.SourceGitProvenance:
        return msgspec.structs.replace(
            provenance,
            failure_category="snapshot-failed",
            detail="clone failed",
        )

    monkeypatch.setattr(graph, "_create_source_snapshot", fail_snapshot)
    monkeypatch.setattr(
        graph,
        "_run_detection_census_receipts",
        lambda _jobs: pytest.fail("failed snapshot reached detector"),
    )

    receipt = graph.detection_census([manifest]).sources[0]

    assert receipt.status == "provenance-failed"
    assert receipt.categories == ("snapshot-failed",)
    assert receipt.resolved_commit == manifest.commit


def test_census_rejects_graphify_write_and_cleans_disposable_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _real_manifest(tmp_path)
    clones: list[Path] = []

    def mutate_clone(jobs: list[tuple[str, Path, object]]) -> list[graph.SourceCensusReceipt]:
        name, clone, _policy = jobs[0]
        clones.append(clone)
        (clone / "graphify-write.tmp").write_text("unexpected\n", encoding="utf-8")
        return [graph.SourceCensusReceipt(source=name, kind="code", status="complete")]

    monkeypatch.setattr(graph, "_run_detection_census_receipts", mutate_clone)

    receipt = graph.detection_census([manifest]).sources[0]

    assert receipt.status == "provenance-failed"
    assert receipt.categories == ("snapshot-drift",)
    assert clones
    assert not clones[0].exists()
    assert not (manifest.clone_dir / "graphify-write.tmp").exists()


def test_disposable_clones_are_independent_and_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifests = [_real_manifest(tmp_path, "alpha"), _real_manifest(tmp_path, "beta")]
    clones: list[Path] = []

    def inspect(jobs: list[tuple[str, Path, object]]) -> list[graph.SourceCensusReceipt]:
        clones.extend(root for _name, root, _policy in jobs)
        assert len({root for _name, root, _policy in jobs}) == 2
        assert all((root / ".git").is_dir() for _name, root, _policy in jobs)
        assert all(
            not (root / ".git" / "objects" / "info" / "alternates").exists()
            for _name, root, _policy in jobs
        )
        return [
            graph.SourceCensusReceipt(source=name, kind="code", status="complete")
            for name, _root, _policy in jobs
        ]

    monkeypatch.setattr(graph, "_run_detection_census_receipts", inspect)

    receipt = graph.detection_census(manifests)

    assert receipt.state == "complete"
    assert clones
    assert all(not clone.exists() for clone in clones)


def test_disposable_clone_owns_objects_from_shared_source(tmp_path: Path) -> None:
    upstream = _real_manifest(tmp_path, "upstream")
    shared = _manifest(tmp_path, "shared", clone=False)
    subprocess.run(
        ["git", "clone", "--quiet", "--shared", str(upstream.clone_dir), str(shared.clone_dir)],
        check=True,
    )
    shared = mf.Manifest(
        name=shared.name,
        path=shared.path,
        url=shared.url,
        ref=shared.ref,
        commit=upstream.commit,
    )
    provenance = graph._verify_source_provenance(shared)
    destination = tmp_path / "disposable"

    result = graph._create_source_snapshot(shared, provenance, destination)

    assert result.failure_category == ""
    assert not (destination / ".git" / "objects" / "info" / "alternates").exists()
    shutil.rmtree(shared.clone_dir)
    shutil.rmtree(upstream.clone_dir)
    subprocess.run(
        ["git", "-C", str(destination), "fsck", "--full", "--no-dangling"],
        check=True,
        capture_output=True,
    )
    assert (destination / "source.py").read_text(encoding="utf-8") == "value = 1\n"
    graph._assert_disposable_clone_identity(destination, provenance)


def test_timed_out_detection_cleans_disposable_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _real_manifest(tmp_path)
    clones: list[Path] = []

    def time_out(jobs: list[tuple[str, Path, object]]) -> list[graph.SourceCensusReceipt]:
        name, clone, _policy = jobs[0]
        clones.append(clone)
        return [
            graph.SourceCensusReceipt(
                source=name,
                kind="code",
                status="timed-out",
                categories=("timeout",),
                stderr="detect source timeout",
            )
        ]

    monkeypatch.setattr(graph, "_run_detection_census_receipts", time_out)

    receipt = graph.detection_census([manifest]).sources[0]

    assert receipt.status == "timed-out"
    assert clones
    assert not clones[0].exists()


def test_failed_disposable_clone_is_removed(tmp_path: Path) -> None:
    manifest = _real_manifest(tmp_path)
    provenance = graph._verify_source_provenance(manifest)
    destination = tmp_path / "already-present"
    destination.mkdir()
    (destination / "block-clone").write_text("occupied\n", encoding="utf-8")

    result = graph._create_source_snapshot(manifest, provenance, destination)

    assert result.failure_category == "snapshot-failed"
    assert not destination.exists()


def test_snapshot_preserves_source_and_gitignore_semantics(tmp_path: Path) -> None:
    manifest = _real_manifest(tmp_path)
    (manifest.clone_dir / ".gitattributes").write_text(
        "hidden.txt export-ignore\nsubst.txt export-subst\n", encoding="utf-8"
    )
    (manifest.clone_dir / "hidden.txt").write_text("must remain\n", encoding="utf-8")
    (manifest.clone_dir / "subst.txt").write_text("$Format:%H$\n", encoding="utf-8")
    executable = manifest.clone_dir / "tool"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    (manifest.clone_dir / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    ignored = manifest.clone_dir / "ignored"
    ignored.mkdir()
    # RENAMED from `secret.txt`, and the reason is worth keeping: graphify 0.9.45
    # skips a file whose NAME begins `secret.` regardless of gitignore, so the old
    # fixture tripped a secrets filter rather than the behaviour under test.
    # Invisible before 0.9.45 — the assertion then looked at the ignored DIRECTORY,
    # never the file — and the first reading of the new failure was "0.9.45
    # silently drops tracked+ignored files", which would have been a false and
    # alarming claim about the release. Isolated by holding the directory, the
    # `.gitignore` and the commit shape fixed and changing only the filename:
    # `secret.{txt,md}` vanish, `design.{txt,md}` are both detected.
    (ignored / "design.txt").write_text("tracked but ignored\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", ".gitignore", ".gitattributes", "hidden.txt", "subst.txt", "tool"],
        cwd=manifest.clone_dir,
        check=True,
    )
    subprocess.run(["git", "add", "-f", "ignored/design.txt"], cwd=manifest.clone_dir, check=True)
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
    assert (snapshot / ".git").is_dir()
    assert (snapshot / "hidden.txt").read_text(encoding="utf-8") == "must remain\n"
    assert (snapshot / "subst.txt").read_text(encoding="utf-8") == "$Format:%H$\n"
    assert (snapshot / "tool").stat().st_mode & 0o111
    # INVERTED at graphify 0.9.45 (#2759), and the inversion is the point. This
    # fixture force-adds `ignored/design.txt`, so it is git-TRACKED while also
    # matching `.gitignore`. Up to 0.9.43 detection dropped it and this line
    # asserted that. 0.9.45 keeps it, matching git's own behaviour of never
    # un-tracking such a file — so the corpus stops silently losing committed
    # content, which is precisely what this repo lost two `docs/superpowers`
    # documents to.
    #
    # The `ignored` bucket is NOT dead: an UNTRACKED path matching `.gitignore`
    # still classifies as ignored, measured at 0.9.45 against a three-repo control
    # (tracked+ignored → retained, untracked+ignored → ignored, no-.gitignore →
    # neither). That case is armed in `graphify_baseline.certify_controls`'s
    # `untracked-ignored-path`; here we pin the tracked half.
    assert not any(Path(path).name == "ignored" for path in detected.get("ignored", []))
    # Reaching detection at all is the property under test; WHICH bucket a `.txt`
    # lands in is graphify's classification policy and not this test's business.
    # Asserting a specific bucket would couple this to a policy that can change
    # without the retention behaviour changing.
    reached = {Path(path).name for group in detected["files"].values() for path in group} | {
        Path(path).name for path in detected.get("unclassified", [])
    }
    assert "design.txt" in reached
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
