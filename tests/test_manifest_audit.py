# Copyright (c) 2026 Raymond Manaloto
"""Tests for kb_setup.manifest_audit — the registry/manifest consistency gate.

The four `_EXPECTED_*` registries in `graph.py` describe THIS repo's real
corpus, so every test here builds its OWN tiny registry via
`monkeypatch.setattr(manifest_audit, "_registries", ...)` rather than reading
the real one — that is also what makes this suite (spec REVISION 2 §C7) the
first thing that would ever catch a wrong `pinned_commit`: no registry is
JSON-decoded and no other test constructs these structs.

Every DRIFT-producing test is paired with its own control arm: the same
fixture, restored to agreement, must read OK. A check that has only ever been
seen to pass is not a check (`.claude/rules/probes-need-a-control-arm.md`).
"""

from __future__ import annotations

from pathlib import Path

from kb_setup import gates, graphify_health, manifest_audit
from kb_setup.manifest_audit import Outcome

_COMMIT_A = "a" * 40
_COMMIT_B = "b" * 40


def _write_manifest(sources_dir: Path, name: str, commit: str, *, build: str = "") -> None:
    sources_dir.mkdir(parents=True, exist_ok=True)
    body = f"url = https://example.invalid/{name}\nref = main\ncommit = {commit}\n"
    if build:
        body += f"build = {build}\n{build}_reason = fixture\n"
    (sources_dir / f"{name}.manifest").write_text(body, encoding="utf-8")


def _metadata_entry(*, source_name: str, relative_path: str, sha256: str, commit: str) -> object:
    return graphify_health.ExpectedMetadataOnly(
        source_name=source_name,
        relative_path=relative_path,
        content_sha256=sha256,
        pinned_commit=commit,
        skipped_disposition=graphify_health.EXPECTED_PACKAGE_MANIFEST_NO_NAME,
    )


def _sha256(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _one_registry(*entries: object) -> tuple[tuple[str, tuple[object, ...]], ...]:
    return (
        ("unclassified", ()),
        ("metadata-only", tuple(entries)),
        ("partial-extraction", ()),
        ("unsupported-language", ()),
    )


# ---------------------------------------------------------------------------
# Tier 1 — registry <-> manifest pin agreement.
# ---------------------------------------------------------------------------


def test_tier1_ok_when_pinned_commit_matches_manifest(tmp_path: Path, monkeypatch) -> None:
    _write_manifest(tmp_path / "sources", "demo", _COMMIT_A)
    entry = _metadata_entry(
        source_name="demo", relative_path="Cargo.toml", sha256="x" * 64, commit=_COMMIT_A
    )
    monkeypatch.setattr(manifest_audit, "_registries", lambda: _one_registry(entry))

    report = manifest_audit.audit(tmp_path)

    assert report.tier1.outcome == Outcome.OK
    assert report.tier1.mismatches == ()


def test_tier1_drift_when_pinned_commit_is_stale(tmp_path: Path, monkeypatch) -> None:
    """The `b2d51b53` class: the manifest moved, the registration did not."""
    _write_manifest(tmp_path / "sources", "demo", _COMMIT_B)  # manifest bumped to B
    entry = _metadata_entry(
        source_name="demo", relative_path="Cargo.toml", sha256="x" * 64, commit=_COMMIT_A
    )  # entry still pinned at A
    monkeypatch.setattr(manifest_audit, "_registries", lambda: _one_registry(entry))

    report = manifest_audit.audit(tmp_path)

    assert report.tier1.outcome == Outcome.DRIFT
    assert any("demo:Cargo.toml" in m for m in report.tier1.mismatches)
    assert report.blocks


def test_tier1_flags_a_registered_source_with_no_manifest(tmp_path: Path, monkeypatch) -> None:
    """Defensive path (spec A1/§C8): not observed at HEAD, must not crash."""
    (tmp_path / "sources").mkdir()
    entry = _metadata_entry(
        source_name="ghost", relative_path="Cargo.toml", sha256="x" * 64, commit=_COMMIT_A
    )
    monkeypatch.setattr(manifest_audit, "_registries", lambda: _one_registry(entry))

    report = manifest_audit.audit(tmp_path)

    assert report.tier1.outcome == Outcome.DRIFT
    assert "ghost:Cargo.toml" in report.tier1.unmatched_sources


# ---------------------------------------------------------------------------
# Tier 2 — content freshness + coverage (requires a clone).
# ---------------------------------------------------------------------------


def test_tier2_skip_when_no_clone_present(tmp_path: Path, monkeypatch) -> None:
    _write_manifest(tmp_path / "sources", "demo", _COMMIT_A)
    entry = _metadata_entry(
        source_name="demo", relative_path="Cargo.toml", sha256="x" * 64, commit=_COMMIT_A
    )
    monkeypatch.setattr(manifest_audit, "_registries", lambda: _one_registry(entry))

    report = manifest_audit.audit(tmp_path)

    assert report.tier2.outcome == Outcome.SKIP
    assert "demo" in report.tier2.skipped_sources
    assert not report.blocks  # SKIP never blocks (spec REVISION 2 §C6)
    assert report.sidecar_outcome == Outcome.SKIP


def test_tier2_hash_mismatch_when_clone_content_changed(tmp_path: Path, monkeypatch) -> None:
    content = "[workspace]\nmembers = []\n"
    sources_dir = tmp_path / "sources"
    _write_manifest(sources_dir, "demo", _COMMIT_A)
    clone = sources_dir / "demo"
    clone.mkdir()
    (clone / "Cargo.toml").write_text(content, encoding="utf-8")
    entry = _metadata_entry(
        source_name="demo",
        relative_path="Cargo.toml",
        sha256=_sha256("something else entirely"),  # stale hash
        commit=_COMMIT_A,
    )
    monkeypatch.setattr(manifest_audit, "_registries", lambda: _one_registry(entry))

    report = manifest_audit.audit(tmp_path)

    assert report.tier2.outcome == Outcome.DRIFT
    assert any("content_sha256 stale" in m for m in report.tier2.hash_mismatches)
    assert report.blocks


def test_tier2_ok_control_arm_when_hash_matches(tmp_path: Path, monkeypatch) -> None:
    """Control arm for the previous test: same fixture, correct hash, must read OK."""
    content = "[workspace]\nmembers = []\n"
    sources_dir = tmp_path / "sources"
    _write_manifest(sources_dir, "demo", _COMMIT_A)
    clone = sources_dir / "demo"
    clone.mkdir()
    (clone / "Cargo.toml").write_text(content, encoding="utf-8")
    entry = _metadata_entry(
        source_name="demo",
        relative_path="Cargo.toml",
        sha256=_sha256(content),
        commit=_COMMIT_A,
    )
    monkeypatch.setattr(manifest_audit, "_registries", lambda: _one_registry(entry))

    report = manifest_audit.audit(tmp_path)

    assert report.tier2.outcome == Outcome.OK
    assert not report.blocks
    assert report.sidecar_outcome == Outcome.OK


def test_tier2_ok_when_some_clones_present_and_some_absent(tmp_path: Path, monkeypatch) -> None:
    """The MIXED shape a fresh checkout is actually in, not the all-absent one.

    `demo` is present and clean; `ghost` has no clone at all. `_tier2`'s outcome
    branch checks `elif verified_sources` before `else: SKIP` — this is the test
    that would catch a swap to `elif skipped_sources` (checking the WRONG
    condition first), which would report SKIP even though a real source was
    fully verified.
    """
    content = "[workspace]\nmembers = []\n"
    sources_dir = tmp_path / "sources"
    _write_manifest(sources_dir, "demo", _COMMIT_A)
    _write_manifest(sources_dir, "ghost", _COMMIT_A)  # never cloned
    clone = sources_dir / "demo"
    clone.mkdir()
    (clone / "Cargo.toml").write_text(content, encoding="utf-8")
    entry = _metadata_entry(
        source_name="demo",
        relative_path="Cargo.toml",
        sha256=_sha256(content),
        commit=_COMMIT_A,
    )
    monkeypatch.setattr(manifest_audit, "_registries", lambda: _one_registry(entry))

    report = manifest_audit.audit(tmp_path)

    assert report.tier2.outcome == Outcome.OK
    assert "demo" in report.tier2.verified_sources
    assert "ghost" in report.tier2.skipped_sources
    assert not report.blocks
    assert report.sidecar_outcome == Outcome.OK


def test_tier2_coverage_flags_an_unregistered_zero_node_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    """The `biome` case: a built source's zero-node Cargo.toml with no registration at all."""
    sources_dir = tmp_path / "sources"
    _write_manifest(sources_dir, "demo", _COMMIT_A)  # build defaults to "include"
    clone = sources_dir / "demo"
    clone.mkdir()
    (clone / "Cargo.toml").write_text("[workspace]\nmembers = []\n", encoding="utf-8")
    monkeypatch.setattr(manifest_audit, "_registries", _one_registry)  # nothing registered

    report = manifest_audit.audit(tmp_path)

    assert report.tier2.outcome == Outcome.DRIFT
    assert any("demo:Cargo.toml" in u for u in report.tier2.uncovered)
    assert report.blocks


def test_tier2_coverage_control_arm_when_source_is_build_skip(tmp_path: Path, monkeypatch) -> None:
    """Control arm: identical zero-node file, but the source is excluded from the build."""
    sources_dir = tmp_path / "sources"
    _write_manifest(sources_dir, "demo", _COMMIT_A, build="skip")
    clone = sources_dir / "demo"
    clone.mkdir()
    (clone / "Cargo.toml").write_text("[workspace]\nmembers = []\n", encoding="utf-8")
    monkeypatch.setattr(manifest_audit, "_registries", _one_registry)

    report = manifest_audit.audit(tmp_path)

    assert report.tier2.outcome == Outcome.OK
    assert not report.blocks


def test_tier2_coverage_excludes_a_parse_failure_from_both_classes(
    tmp_path: Path, monkeypatch
) -> None:
    """A TOML syntax error is neither registerable nor a coverage failure (spec §C2/M1)."""
    sources_dir = tmp_path / "sources"
    _write_manifest(sources_dir, "demo", _COMMIT_A)
    clone = sources_dir / "demo"
    clone.mkdir()
    (clone / "Cargo.toml").write_text("[package\nbroken", encoding="utf-8")
    monkeypatch.setattr(manifest_audit, "_registries", _one_registry)

    report = manifest_audit.audit(tmp_path)

    assert report.tier2.outcome == Outcome.OK
    assert report.tier2.uncovered == ()


def test_tier2_coverage_ignores_a_real_package(tmp_path: Path, monkeypatch) -> None:
    """Control arm for the parse-failure test: a real `[package]` must never be flagged."""
    sources_dir = tmp_path / "sources"
    _write_manifest(sources_dir, "demo", _COMMIT_A)
    clone = sources_dir / "demo"
    clone.mkdir()
    (clone / "Cargo.toml").write_text(
        '[package]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr(manifest_audit, "_registries", _one_registry)

    report = manifest_audit.audit(tmp_path)

    assert report.tier2.outcome == Outcome.OK
    assert report.tier2.uncovered == ()


# ---------------------------------------------------------------------------
# main() and the sidecar channel.
# ---------------------------------------------------------------------------


def test_main_rejects_arguments(tmp_path: Path) -> None:
    from kb_setup.result import Rc

    assert manifest_audit.main(tmp_path, ["--bogus"]) == int(Rc.BAD_REQUEST)


def test_main_writes_the_sidecar_gates_reads_back(tmp_path: Path, monkeypatch) -> None:
    """The channel C3 asked for: `main` writes what `gates.read_sidecar_outcome` reads."""
    import subprocess

    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "root"], cwd=tmp_path, check=True)

    _write_manifest(tmp_path / "sources", "demo", _COMMIT_A)
    entry = _metadata_entry(
        source_name="demo", relative_path="Cargo.toml", sha256="x" * 64, commit=_COMMIT_B
    )  # stale on purpose -> DRIFT
    monkeypatch.setattr(manifest_audit, "_registries", lambda: _one_registry(entry))

    rc = manifest_audit.main(tmp_path, [])

    from kb_setup.result import Rc

    assert rc == int(Rc.FINDINGS)
    sha = gates.head_sha(tmp_path)
    assert gates.read_sidecar_outcome(tmp_path, manifest_audit.TASK_NAME, sha) == "DRIFT"


def test_main_returns_ok_and_writes_skip_sidecar_on_a_missing_clone(
    tmp_path: Path, monkeypatch
) -> None:
    """The claim this whole gate exists to prove: SKIP must never block `main`.

    Same shape as `test_main_writes_the_sidecar_gates_reads_back`, but with no
    clone present at all — a fresh checkout. `main` must exit `Rc.OK` (never
    `Rc.FINDINGS`) and the sidecar must read `SKIP`, never laundered to `OK`.
    """
    import subprocess

    from kb_setup.result import Rc

    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "root"], cwd=tmp_path, check=True)

    _write_manifest(tmp_path / "sources", "demo", _COMMIT_A)  # no clone ever made
    entry = _metadata_entry(
        source_name="demo", relative_path="Cargo.toml", sha256="x" * 64, commit=_COMMIT_A
    )
    monkeypatch.setattr(manifest_audit, "_registries", lambda: _one_registry(entry))

    rc = manifest_audit.main(tmp_path, [])

    assert rc == int(Rc.OK)
    sha = gates.head_sha(tmp_path)
    assert gates.read_sidecar_outcome(tmp_path, manifest_audit.TASK_NAME, sha) == "SKIP"
