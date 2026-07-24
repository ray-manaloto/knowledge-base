"""kb_setup.currency.sync — step 1, the in-sync check.

Network-free and subprocess-free by construction: every check here reads files
or `shutil.which`, which is exactly why the SessionStart hook can afford to run
it on every session.

Every check is exercised in BOTH directions. A step-1 check that has only ever
been seen to fail is worth as little as one that has only ever passed — and this
suite exists partly because the control arm caught a real bug the day it was
written: `.resolve()` followed the mise shim's symlink to the `mise` binary and
reported a correctly-pinned tool as "outside mise".
"""

import json
from pathlib import Path

import pytest
from kb_setup.currency import config, sync


def _repo(tmp_path, *, pin='"pipx:graphifyy" = { version = "0.9.25", extras = ["all"] }') -> Path:
    (tmp_path / "mise.toml").write_text(f"[tools]\n{pin}\n", encoding="utf-8")
    (tmp_path / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'extras = ["all"]\n'
        'manifest = "sources/graphify.manifest"\n'
        'artifact = "graphify-out/graph.json"\n'
        'stamp = "graphify-out/.currency-stamp.json"\n',
        encoding="utf-8",
    )
    return tmp_path


def _spec(tmp_path) -> config.ToolSpec:
    return config.load(tmp_path)[0]


def _write_manifest(root, ref: str) -> None:
    path = root / "sources" / "graphify.manifest"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"url = https://example/x\nref = {ref}\ncommit = abc123\n", encoding="utf-8")


def _finding(status: sync.SyncStatus, check: str) -> sync.Finding:
    return next(f for f in status.findings if f.check == check)


# ------------------------------------------------------------------ pin ----


def test_reads_table_form_pin_and_extras(tmp_path) -> None:
    root = _repo(tmp_path)
    version, extras = sync.pinned_version(root, _spec(root))
    assert version == "0.9.25"
    assert extras == ("all",)


def test_reads_bare_string_pin(tmp_path) -> None:
    """Both pin forms are live across these repos, so both must parse."""
    root = _repo(tmp_path, pin='"pipx:graphifyy" = "0.9.25"')
    version, extras = sync.pinned_version(root, _spec(root))
    assert version == "0.9.25"
    assert extras == ()


def test_missing_pin_is_drift_not_a_crash(tmp_path) -> None:
    root = _repo(tmp_path, pin='hk = "1.52.0"')
    status = sync.check_sync(root, _spec(root))
    assert not status.ok
    assert _finding(status, "pin").status == sync.DRIFT


# ----------------------------------------------------------- resolution ----


def test_shim_resolution_is_in_sync_by_construction(tmp_path, monkeypatch) -> None:
    """A mise shim applies the pin at call time, so it cannot be stale.

    Regression guard: this path once reported DRIFT because `.resolve()` followed
    the shim symlink to the `mise` binary itself.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: "/Users/x/.local/share/mise/shims/graphify")
    version, how = sync.resolve_from_path("graphify")
    assert how == "shim"
    assert version == ""


def test_stale_install_dir_ahead_of_shims_is_drift(tmp_path, monkeypatch) -> None:
    """The live bug this whole module was written for."""
    monkeypatch.setattr(
        sync.shutil,
        "which",
        lambda _: "/Users/x/.local/share/mise/installs/pipx-graphifyy/0.9.23/bin/graphify",
    )
    root = _repo(tmp_path)
    _write_manifest(root, "v0.9.25")
    status = sync.check_sync(root, _spec(root))
    resolution = _finding(status, "resolution")
    assert resolution.status == sync.DRIFT
    assert "0.9.23" in resolution.detail


def test_matching_install_dir_is_ok(tmp_path, monkeypatch) -> None:
    """Control arm for the test above: same code path, opposite verdict."""
    monkeypatch.setattr(
        sync.shutil,
        "which",
        lambda _: "/Users/x/.local/share/mise/installs/pipx-graphifyy/0.9.25/bin/graphify",
    )
    root = _repo(tmp_path)
    status = sync.check_sync(root, _spec(root))
    assert _finding(status, "resolution").status == sync.OK


def test_binary_outside_mise_is_drift(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sync.shutil, "which", lambda _: "/opt/homebrew/bin/graphify")
    root = _repo(tmp_path)
    assert _finding(sync.check_sync(root, _spec(root)), "resolution").status == sync.DRIFT


def test_absent_binary_is_skip_not_drift(tmp_path, monkeypatch) -> None:
    """Not-installed-here is not installed-wrong — CI must not fail on it."""
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    assert _finding(sync.check_sync(root, _spec(root)), "resolution").status == sync.SKIP


# --------------------------------------------------------------- extras ----


def test_extras_mismatch_is_drift(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path, pin='"pipx:graphifyy" = { version = "0.9.25" }')
    assert _finding(sync.check_sync(root, _spec(root)), "extras").status == sync.DRIFT


def test_extras_match_is_ok(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    assert _finding(sync.check_sync(root, _spec(root)), "extras").status == sync.OK


# ------------------------------------------------------------- manifest ----


def test_manifest_tracking_a_different_release_is_drift(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    _write_manifest(root, "v0.9.23")
    assert _finding(sync.check_sync(root, _spec(root)), "manifest").status == sync.DRIFT


def test_manifest_matching_the_pin_is_ok(tmp_path, monkeypatch) -> None:
    """The `v` prefix is the tag convention; the pin has no prefix."""
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    _write_manifest(root, "v0.9.25")
    assert _finding(sync.check_sync(root, _spec(root)), "manifest").status == sync.OK


# ---------------------------------------------------------------- stamp ----


def test_unstamped_artifacts_report_rebuild_pending(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    finding = _finding(sync.check_sync(root, _spec(root)), "build-stamp")
    assert finding.status == sync.DRIFT
    assert "rebuild pending" in finding.detail


def test_stamp_written_by_the_build_task_reads_back_ok(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    sync.write_stamp(root, _spec(root), version="0.9.25", source_ref="v0.9.25")
    assert _finding(sync.check_sync(root, _spec(root)), "build-stamp").status == sync.OK


def test_stamp_from_an_older_version_is_drift(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    sync.write_stamp(root, _spec(root), version="0.9.23")
    finding = _finding(sync.check_sync(root, _spec(root)), "build-stamp")
    assert finding.status == sync.DRIFT
    assert "0.9.23" in finding.detail


def test_rebuild_outside_the_build_task_reports_version_unknown(tmp_path, monkeypatch) -> None:
    """The stamp's whole value is that it can detect its own staleness.

    A hand-run `graphify update` rewrites graph.json without touching the stamp,
    so the stamp would otherwise keep asserting a version that no longer built
    the artifacts. Comparing `built_at_commit` catches exactly that.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    artifact = root / "graphify-out" / "graph.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"nodes": [], "built_at_commit": "aaaa1111"}), encoding="utf-8")
    sync.write_stamp(root, _spec(root), version="0.9.25")

    # Simulate a rebuild that bypassed the build task.
    artifact.write_text(json.dumps({"nodes": [], "built_at_commit": "bbbb2222"}), encoding="utf-8")
    finding = _finding(sync.check_sync(root, _spec(root)), "build-stamp")
    assert finding.status == sync.DRIFT
    assert "version unknown" in finding.detail


def test_artifact_commit_is_read_without_parsing_the_whole_graph(tmp_path) -> None:
    """Graphs run to hundreds of MB; the hook must never json.load one."""
    artifact = tmp_path / "graph.json"
    artifact.write_text(
        json.dumps({"nodes": [{"id": i} for i in range(5000)], "built_at_commit": "cafe1234"}),
        encoding="utf-8",
    )
    assert sync._artifact_commit(artifact) == "cafe1234"


# ------------------------------------------------------------- platform ----


def test_tool_declared_for_another_os_is_skip_never_fail(tmp_path, monkeypatch) -> None:
    """A macOS-only tool on a Linux runner is unverifiable, not broken."""
    root = _repo(tmp_path)
    (root / "currency.toml").write_text(
        '[tool.graphify]\nmise_key = "pipx:graphifyy"\nos = ["plan9"]\n', encoding="utf-8"
    )
    status = sync.check_sync(root, _spec(root))
    assert status.ok
    assert _finding(status, "platform").status == sync.SKIP


def test_applies_here_is_true_when_no_os_restriction(tmp_path) -> None:
    """Control arm: the same machinery must say yes for an unrestricted tool."""
    root = _repo(tmp_path)
    assert _spec(root).applies_here()


def test_missing_config_is_empty_not_an_error(tmp_path) -> None:
    assert config.load(tmp_path) == ()


def test_config_without_mise_key_is_rejected(tmp_path) -> None:
    (tmp_path / "currency.toml").write_text('[tool.graphify]\nbinary = "graphify"\n')
    with pytest.raises(ValueError, match="mise_key"):
        config.load(tmp_path)


# --------------------------------------------------- build-task stamping ----


def test_build_stamp_records_the_version_that_ran_not_the_pin(tmp_path, monkeypatch) -> None:
    """The stamp must never fall back to the pin when the binary is unreadable.

    Falling back would record the version we HOPED ran, converting an unreadable
    binary into a false "in sync" — precisely the laundering this stamp exists to
    prevent. An unknown version is written as unknown and reported as drift.
    """
    from kb_setup import graph

    root = _repo(tmp_path)
    monkeypatch.setattr(sync, "observed_version", lambda _: "")
    graph._stamp_build(root)

    stamp = sync.read_stamp(root, _spec(root))
    assert stamp["version"] == ""
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    finding = _finding(sync.check_sync(root, _spec(root)), "build-stamp")
    assert finding.status == sync.DRIFT
    assert "unknown version" in finding.detail


def test_build_stamp_records_a_stale_binary_honestly(tmp_path, monkeypatch) -> None:
    """Control arm: a readable binary is recorded verbatim, even when stale.

    A build that silently ran 0.9.23 under a 0.9.25 pin must stamp 0.9.23 — the
    stamp reports what happened, it does not assert what should have happened.
    """
    from kb_setup import graph

    root = _repo(tmp_path)
    monkeypatch.setattr(sync, "observed_version", lambda _: "0.9.23")
    graph._stamp_build(root)

    assert sync.read_stamp(root, _spec(root))["version"] == "0.9.23"
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    assert _finding(sync.check_sync(root, _spec(root)), "build-stamp").status == sync.DRIFT


# --------------------------------------------------------- extra probes ----


def _repo_with_probes(tmp_path, probes: str) -> Path:
    root = _repo(tmp_path)
    (root / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'extras = ["all"]\n'
        f"extra_probes = [{probes}]\n",
        encoding="utf-8",
    )
    return root


def test_missing_extra_package_is_drift(tmp_path, monkeypatch) -> None:
    """Two config files agreeing on `extras` says nothing about the INSTALL.

    This is the half of "extensions tools are in sync" that a config comparison
    cannot answer: the extra is declared everywhere and still delivered nothing.
    """
    site = tmp_path / "install" / "x" / "lib" / "python3.14" / "site-packages"
    (site / "faster_whisper").mkdir(parents=True)
    monkeypatch.setattr(sync, "install_site_packages", lambda *_a, **_k: site)

    root = _repo_with_probes(tmp_path, '"faster_whisper", "graspologic"')
    finding = _finding(sync.check_sync(root, _spec(root)), "extra-probes")
    assert finding.status == sync.DRIFT
    assert "graspologic" in finding.detail


def test_present_extra_packages_are_ok(tmp_path, monkeypatch) -> None:
    """Control arm: same code path, all probes satisfied."""
    site = tmp_path / "install" / "x" / "lib" / "python3.14" / "site-packages"
    (site / "faster_whisper").mkdir(parents=True)
    (site / "tree_sitter").mkdir(parents=True)
    monkeypatch.setattr(sync, "install_site_packages", lambda *_a, **_k: site)

    root = _repo_with_probes(tmp_path, '"faster_whisper", "tree_sitter"')
    assert _finding(sync.check_sync(root, _spec(root)), "extra-probes").status == sync.OK


def test_unresolvable_install_is_skip_not_drift(tmp_path, monkeypatch) -> None:
    """Cannot-locate-the-install is not missing-extras. Never invent a finding."""
    monkeypatch.setattr(sync, "install_site_packages", lambda *_a, **_k: None)
    root = _repo_with_probes(tmp_path, '"faster_whisper"')
    assert _finding(sync.check_sync(root, _spec(root)), "extra-probes").status == sync.SKIP


def test_no_probes_declared_is_skip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    assert _finding(sync.check_sync(root, _spec(root)), "extra-probes").status == sync.SKIP


def test_shallow_mode_never_shells_out(tmp_path, monkeypatch) -> None:
    """The hook path must stay subprocess-free — it runs every session."""

    def _explode(*_a: object, **_k: object) -> None:
        msg = "check_sync(deep=False) must not spawn a subprocess"
        raise AssertionError(msg)

    monkeypatch.setattr(sync.subprocess, "run", _explode)
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo_with_probes(tmp_path, '"faster_whisper"')
    sync.check_sync(root, _spec(root))  # must not raise


def test_deep_mode_prefers_the_pinned_install_over_path(tmp_path, monkeypatch) -> None:
    """PATH may reach a STALE install; the extras question is about the PIN.

    Probing whatever PATH reaches would answer the wrong question — and on this
    very host PATH reached 0.9.23 while the pin was 0.9.25.
    """
    pinned = tmp_path / "pinned"
    (pinned / "g" / "lib" / "python3.14" / "site-packages").mkdir(parents=True)
    monkeypatch.setattr(sync, "_pinned_install_root", lambda _: pinned)
    monkeypatch.setattr(
        sync, "_install_root_from_path", lambda _: tmp_path / "stale-should-not-be-used"
    )
    site = sync.install_site_packages("graphify", "pipx:graphifyy", deep=True)
    assert site is not None
    assert "pinned" in str(site)
