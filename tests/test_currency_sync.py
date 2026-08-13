# Copyright (c) 2026 Raymond Manaloto
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
import subprocess
import time
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
    # The declared artifact must exist: a stamp now fingerprints it, and a
    # DECLARED-but-absent artifact is legitimately drift ("nothing was built").
    artifact = tmp_path / "graphify-out" / "graph.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        '{"nodes": [], "built_at_commit": "aaaaaaaa1111bbbb2222cccc3333dddd4444eeee"}',
        encoding="utf-8",
    )
    return tmp_path


def _spec(tmp_path) -> config.ToolSpec:
    return config.load(tmp_path)[0]


def _write_manifest(root, ref: str, commit: str = "abc123") -> None:
    path = root / "sources" / "graphify.manifest"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"url = https://example/x\nref = {ref}\ncommit = {commit}\n", encoding="utf-8")


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


def test_reads_exact_python_project_pin_and_extras(tmp_path) -> None:
    root = _repo(tmp_path)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "probe"\nversion = "0"\ndependencies = ["graphifyy[all]==0.9.41"]\n',
        encoding="utf-8",
    )
    (root / "currency.toml").write_text(
        '[tool.graphify]\npython_package = "graphifyy"\nextras = ["all"]\n',
        encoding="utf-8",
    )
    version, extras = sync.pinned_version(root, _spec(root))
    assert version == "0.9.41"
    assert extras == ("all",)


def test_python_package_owner_requires_an_exact_project_pin(tmp_path) -> None:
    root = _repo(tmp_path)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "probe"\nversion = "0"\ndependencies = ["graphifyy[all]>=0.9.41"]\n',
        encoding="utf-8",
    )
    (root / "currency.toml").write_text(
        '[tool.graphify]\npython_package = "graphifyy"\nextras = ["all"]\n',
        encoding="utf-8",
    )
    assert _finding(sync.check_sync(root, _spec(root)), "pin").status == sync.DRIFT


def test_missing_pin_is_drift_not_a_crash(tmp_path) -> None:
    root = _repo(tmp_path, pin='hk = "1.52.0"')
    status = sync.check_sync(root, _spec(root))
    assert not status.ok
    assert _finding(status, "pin").status == sync.DRIFT


# ----------------------------------------------------------- resolution ----


def test_mise_shim_resolution_is_in_sync_by_construction(tmp_path, monkeypatch) -> None:
    """A mise shim applies the pin at call time, so it cannot be stale.

    Regression guard: this path once reported DRIFT because `.resolve()` followed
    the shim symlink to the `mise` binary itself.
    """
    shim = tmp_path / "mise" / "shims" / "graphify"
    shim.parent.mkdir(parents=True)
    shim.touch()
    monkeypatch.setattr(sync, "_mise_shim_dirs", lambda: (shim.parent,))
    monkeypatch.setattr(sync.shutil, "which", lambda _: str(shim))
    version, how = sync.resolve_from_path("graphify")
    assert how == "shim"
    assert version == ""


def test_a_pyenv_or_asdf_shim_is_not_a_mise_shim(tmp_path, monkeypatch) -> None:
    """pyenv, asdf and rbenv all use a directory literally called `shims`.

    A bare segment test handed them a free pass, and `_check_resolution` then
    reported the PIN as the resolved version — a value nothing ever read from the
    binary. Same false-green class this module was written to catch.
    """
    mise_shims = tmp_path / "mise" / "shims"
    mise_shims.mkdir(parents=True)
    monkeypatch.setattr(sync, "_mise_shim_dirs", lambda: (mise_shims,))
    for foreign in ("/Users/x/.pyenv/shims/graphify", "/Users/x/.asdf/shims/graphify"):
        monkeypatch.setattr(sync.shutil, "which", lambda _, _f=foreign: _f)
        _version, how = sync.resolve_from_path("graphify")
        assert how.startswith("outside-mise"), foreign


def test_the_last_installs_segment_wins(tmp_path, monkeypatch) -> None:
    """A path can contain an earlier directory called `installs`.

    `index()` took the first, reading the "version" from the wrong segment.
    """
    monkeypatch.setattr(
        sync.shutil,
        "which",
        lambda _: "/opt/installs/cache/share/mise/installs/pipx-graphifyy/0.9.25/bin/graphify",
    )
    assert sync.resolve_from_path("graphify") == ("0.9.25", "install-dir")


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


def test_absent_binary_on_an_applicable_host_is_drift(tmp_path, monkeypatch) -> None:
    """`applies_here()` has already answered "should this exist here?".

    Past that point a missing binary is a fact about the install, not something
    we could not check. Calling it SKIP made a fresh clone — or a failed
    `mise install` — render as "graphify 0.9.25: in sync" with no binary at all.
    Platform-inapplicable hosts are handled earlier and still SKIP.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    status = sync.check_sync(root, _spec(root))
    assert _finding(status, "resolution").status == sync.DRIFT
    assert not status.ok


def test_a_run_of_nothing_but_skips_is_not_in_sync(tmp_path) -> None:
    """A foreign platform rendered as `graphify : in sync` — green, and unchecked."""
    root = _repo(tmp_path)
    (root / "currency.toml").write_text(
        '[tool.graphify]\nmise_key = "pipx:graphifyy"\nos = ["plan9"]\n', encoding="utf-8"
    )
    status = sync.check_sync(root, _spec(root))
    assert not status.verified
    assert "not verifiable here" in status.summary()
    assert "in sync" not in status.summary()


def test_undeclared_extras_in_the_pin_are_drift(tmp_path, monkeypatch) -> None:
    """The pin installing extras nobody declared is a real supply-surface change."""
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    (root / "currency.toml").write_text(
        '[tool.graphify]\nmise_key = "pipx:graphifyy"\nbinary = "graphify"\n', encoding="utf-8"
    )
    assert _finding(sync.check_sync(root, _spec(root)), "extras").status == sync.DRIFT


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


def _git(root, *a: str) -> str:
    """One git command in the `sources/graphify` clone, as stripped stdout."""
    clone = root / "sources" / "graphify"
    return subprocess.run(
        ["git", "-C", str(clone), *a], capture_output=True, text=True, check=True, timeout=30
    ).stdout.strip()


def _clone_at(root, ref: str, *, annotated: bool = False) -> str:
    """A real git clone under `sources/graphify` with `ref` tagged. Returns the SHA.

    A real repository, not a stub, because the check under test resolves the tag
    with `git rev-list` against the tree `kb-build` will actually check out. A
    fake would only confirm the fake.

    `annotated=True` makes it a TAG OBJECT rather than a lightweight ref, which
    is the only way to reach the two-identity comparison in
    `_check_manifest_commit`: a lightweight tag resolves to one SHA under both
    resolvers, so a fixture built with one cannot tell a widened check from a
    narrow one. The SHA returned is the PEELED commit either way; ask
    `_git(root, "rev-parse", ref)` for the tag object.
    """
    clone = root / "sources" / "graphify"
    clone.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(clone)], check=True, timeout=30)
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    # Without this an annotated tag blocks on a pinentry prompt on any machine
    # with `tag.gpgsign = true` set globally — a fixture that passes here and
    # hangs on someone else's laptop, which is `conftest`'s recorded lesson.
    _git(root, "config", "tag.gpgsign", "false")
    (clone / "f.txt").write_text("x\n", encoding="utf-8")
    _git(root, "add", "--", "f.txt")
    _git(root, "commit", "-q", "-m", "c")
    _git(root, "tag", *(["-a", "-m", f"release {ref}"] if annotated else []), ref)
    return _git(root, "rev-parse", "HEAD")


def test_manifest_matching_the_pin_is_ok(tmp_path, monkeypatch) -> None:
    """The `v` prefix is the tag convention; the pin has no prefix."""
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    sha = _clone_at(root, "v0.9.25")
    _write_manifest(root, "v0.9.25", commit=sha)
    assert _finding(sync.check_sync(root, _spec(root)), "manifest").status == sync.OK


def test_manifest_whose_commit_is_not_the_tag_is_drift(tmp_path, monkeypatch) -> None:
    """A matching `ref` is NOT the invariant — `kb-build` checks out `commit`.

    THE DEFECT THIS EXISTS FOR (cold lane, round 2): the check compared only
    `ref`, so a manifest reading `ref = v1.54.0` beside the PREVIOUS release's
    commit reported OK while the build extracted the old code. Same false-green
    the check exists to prevent, through a narrower mutation — and it was found
    the day this check was first armed for hk and fnox.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    _clone_at(root, "v0.9.25")
    _write_manifest(root, "v0.9.25", commit="0" * 40)
    finding = _finding(sync.check_sync(root, _spec(root)), "manifest")
    assert finding.status == sync.DRIFT, (
        f"a stale commit under a correct ref reported {finding.status}: {finding.detail}"
    )


def test_an_unresolvable_commit_reports_skip_not_ok(tmp_path, monkeypatch) -> None:
    """CONTROL ARM: could-not-check must never render as green.

    Without a clone the tag cannot be resolved, and the honest answer is SKIP.
    Returning OK there would restore the exact hole above on every host that has
    not run `kb-build` yet — which is every fresh clone.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    _write_manifest(root, "v0.9.25", commit="a" * 40)
    finding = _finding(sync.check_sync(root, _spec(root)), "manifest")
    assert finding.status == sync.SKIP, (
        f"an unverifiable commit reported {finding.status}, not SKIP: {finding.detail}"
    )


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

    Crucially this mutates CONTENT while holding `built_at_commit` CONSTANT.
    `built_at_commit` is the git HEAD, so every rebuild at one commit writes the
    same value — and rebuilding repeatedly at one commit is the normal rhythm.
    Relying on it made this detector almost never able to fire while claiming it
    could; the fingerprint is what actually answers the question.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    artifact = root / "graphify-out" / "graph.json"
    head = '"built_at_commit": "aaaaaaaa1111bbbb2222cccc3333dddd4444eeee"'
    artifact.write_text("{" + head + "}", encoding="utf-8")
    sync.write_stamp(root, _spec(root), version="0.9.25")
    assert _finding(sync.check_sync(root, _spec(root)), "build-stamp").status == sync.OK

    time.sleep(0.01)
    artifact.write_text('{"nodes": [1, 2, 3], ' + head + "}", encoding="utf-8")
    finding = _finding(sync.check_sync(root, _spec(root)), "build-stamp")
    assert finding.status == sync.DRIFT
    assert "graphify-out/graph.json (changed)" in finding.detail


def test_artifact_commit_is_read_without_parsing_the_whole_graph(tmp_path) -> None:
    """Graphs run to hundreds of MB; the hook must never json.load one."""
    artifact = tmp_path / "graph.json"
    artifact.write_text(
        json.dumps({"nodes": [{"id": i} for i in range(5000)], "built_at_commit": "cafe1234"}),
        encoding="utf-8",
    )
    assert sync._artifact_commit(artifact) == "cafe1234"


# ------------------------------------------------------------- platform ----


def test_tool_declared_for_another_os_is_blind_never_fail(tmp_path, monkeypatch) -> None:
    """A macOS-only tool on a Linux runner is unverifiable, not broken.

    BLIND rather than SKIP: the tool IS configured here, so "this host cannot
    check it" is a check that never ran, not a check with nothing to do. It
    still must not make the run red — `status.ok` is the assertion that matters
    for CI — but it must never read as consent for an unattended bump.
    """
    root = _repo(tmp_path)
    (root / "currency.toml").write_text(
        '[tool.graphify]\nmise_key = "pipx:graphifyy"\nos = ["plan9"]\n', encoding="utf-8"
    )
    status = sync.check_sync(root, _spec(root))
    assert status.ok
    assert _finding(status, "platform").status == sync.BLIND


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


def test_unresolvable_install_is_blind_not_drift(tmp_path, monkeypatch) -> None:
    """Cannot-locate-the-install is not missing-extras. Never invent a finding.

    BLIND, not SKIP: probes ARE declared, so this is the check failing to run.
    That distinction is what stops an auto-apply here (`decide._gate_sync`).
    """
    monkeypatch.setattr(sync, "install_site_packages", lambda *_a, **_k: None)
    root = _repo_with_probes(tmp_path, '"faster_whisper"')
    status = sync.check_sync(root, _spec(root))
    assert _finding(status, "extra-probes").status == sync.BLIND
    assert "extra-probes" in {f.check for f in status.blind}
    # Deliberately NOT asserting `status.ok` here: `_check_resolution` reads the
    # real PATH, so on a host with a stale install ahead of the mise shims this
    # status legitimately carries an unrelated `resolution` drift. That the
    # BLIND status itself is not red is asserted by the platform test above,
    # which short-circuits before any PATH lookup.


def test_no_probes_declared_is_skip(tmp_path, monkeypatch) -> None:
    """Control arm for the split: nothing declared is SKIP, and is NOT blind.

    Without this, "blind" could quietly widen to mean "not OK" and permanently
    block every repo that declares no extras — a false stop replacing a false
    pass.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    status = sync.check_sync(root, _spec(root))
    assert _finding(status, "extra-probes").status == sync.SKIP
    assert not status.blind


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


def test_a_node_named_built_at_commit_cannot_impersonate_the_metadata_key(tmp_path) -> None:
    """This corpus ingests graphify's own source, which contains that identifier.

    A bare `rfind(b'"built_at_commit"')` matched a node NAMED `built_at_commit`
    just as readily as the real key, then partitioned on the next unrelated `:`
    and returned confident nonsense. Requiring a SHA-shaped VALUE fixes it.
    """
    real = "abcdef0123456789abcdef0123456789abcdef01"
    artifact = tmp_path / "decoy.json"
    filler = ",\n".join(f'    {{"id": "n{i}"}}' for i in range(200))
    artifact.write_text(
        f'{{\n  "built_at_commit": "{real}",\n  "nodes": [\n{filler},\n'
        '    {"name": "built_at_commit", "type": "attribute"}\n  ]\n}}\n',
        encoding="utf-8",
    )
    assert sync._artifact_commit(artifact) == real


def test_commit_is_found_whether_metadata_is_first_or_last(tmp_path) -> None:
    """Metadata-last is graphify's convention, not a guarantee."""
    sha = "abcdef0123456789abcdef0123456789abcdef01"
    filler = ",".join(f'"n{i}"' for i in range(600))
    last = tmp_path / "last.json"
    last.write_text(f'{{"nodes": [{filler}], "built_at_commit": "{sha}"}}', encoding="utf-8")
    first = tmp_path / "first.json"
    first.write_text(f'{{"built_at_commit": "{sha}", "nodes": [{filler}]}}', encoding="utf-8")
    assert sync._artifact_commit(last) == sha
    assert sync._artifact_commit(first) == sha


def test_a_pre_v3_stamp_admits_it_cannot_prove_the_generated_outputs(tmp_path, monkeypatch) -> None:
    """An old stamp must not inherit a guarantee it was never able to make.

    A pre-v3 stamp fingerprinted at most the primary graph, so it cannot testify
    that the wiki/graphml match — it must say so, not stay green.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    sync.write_stamp(root, _spec(root), version="0.9.25")
    path = root / "graphify-out" / ".currency-stamp.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["stamp_version"] = 2
    data.pop("artifact_fingerprints", None)
    data["artifact_fingerprint"] = "old-single"
    path.write_text(json.dumps(data), encoding="utf-8")

    finding = _finding(sync.check_sync(root, _spec(root)), "build-stamp")
    assert finding.status == sync.DRIFT
    assert "predates generated-output fingerprinting" in finding.detail


def test_declared_but_absent_artifact_is_drift(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo(tmp_path)
    sync.write_stamp(root, _spec(root), version="0.9.25")
    (root / "graphify-out" / "graph.json").unlink()
    finding = _finding(sync.check_sync(root, _spec(root)), "build-stamp")
    assert finding.status == sync.DRIFT
    assert "missing" in finding.detail


def test_build_clears_the_stamp_before_touching_the_artifact(tmp_path, monkeypatch) -> None:
    """An aborted build must fail closed, not leave a NEW artifact under an OLD stamp.

    `build()` overwrites graph.json at the seed step but stamps only at the end,
    so any failure in between left the previous stamp asserting it had built the
    new bytes — and `built_at_commit` is a repo commit, so a same-commit rebuild
    by a stale binary was undetectable.
    """
    from kb_setup import graph

    root = _repo(tmp_path)
    sync.write_stamp(root, _spec(root), version="0.9.25")
    stamp = root / "graphify-out" / ".currency-stamp.json"
    assert stamp.exists()

    graph._clear_stamp(root)
    assert not stamp.exists()

    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    finding = _finding(sync.check_sync(root, _spec(root)), "build-stamp")
    assert finding.status == sync.DRIFT
    assert "never been stamped" in finding.detail


def test_the_stamped_tool_is_chosen_by_name_not_by_sort_order(tmp_path) -> None:
    """currency.toml is explicitly multi-tool; "first spec with a stamp" picks the wrong one."""
    from kb_setup import graph

    root = _repo(tmp_path)
    (root / "currency.toml").write_text(
        '[tool.aardvark]\nmise_key = "x"\nstamp = "graphify-out/.a.json"\n\n'
        '[tool.graphify]\nmise_key = "pipx:graphifyy"\nbinary = "graphify"\n'
        'artifact = "graphify-out/graph.json"\nstamp = "graphify-out/.currency-stamp.json"\n',
        encoding="utf-8",
    )
    spec = graph._currency_spec(root)
    assert spec is not None
    assert spec.name == "graphify"


# ----------------------------------------- presence-only tool (ffmpeg) ----


def _ffmpeg_repo(tmp_path, *, present: bool) -> Path:
    (tmp_path / "mise.toml").write_text('[tools]\n"conda:ffmpeg" = "8.1.2"\n', encoding="utf-8")
    (tmp_path / "currency.toml").write_text(
        '[tool.ffmpeg]\nmise_key = "conda:ffmpeg"\nbinary = "ffmpeg"\n',
        encoding="utf-8",
    )
    return tmp_path


def test_a_present_ffmpeg_is_in_sync_with_no_manifest_or_stamp(tmp_path, monkeypatch) -> None:
    """A presence-only tool: pin resolves, binary reachable, everything else SKIP.

    ffmpeg has no manifest, artifact, stamp, or upstream — so the absence of
    those checks is correct, not a gap. This is the whole point of every ToolSpec
    field being optional.
    """
    root = _ffmpeg_repo(tmp_path, present=True)
    install = tmp_path / "installs" / "conda-ffmpeg" / "8.1.2" / ".mise-bins" / "ffmpeg"
    install.parent.mkdir(parents=True, exist_ok=True)
    install.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(sync.shutil, "which", lambda _b: str(install))

    status = sync.check_sync(root, config.load(root)[0])
    assert status.ok
    assert status.verified  # something actually ran; not an all-SKIP no-op
    assert _finding(status, "resolution").status == sync.OK
    assert {f.check for f in status.findings if f.status == sync.SKIP} == {
        "extras",
        "extra-probes",
        "manifest",
        "build-stamp",
    }


def test_an_absent_ffmpeg_is_drift_not_silence(tmp_path, monkeypatch) -> None:
    """The founding motivation: a missing ffmpeg breaks youtube ingest silently.

    Control arm for the test above — the same machinery must report DRIFT when
    the binary is gone, or the presence check is decoration.
    """
    root = _ffmpeg_repo(tmp_path, present=False)
    monkeypatch.setattr(sync.shutil, "which", lambda _b: None)
    status = sync.check_sync(root, config.load(root)[0])
    assert not status.ok
    assert _finding(status, "resolution").status == sync.DRIFT
    assert "not installed" in _finding(status, "resolution").detail


# --------------------------------------- generated-output fingerprinting ----


def _repo_with_generated(tmp_path) -> Path:
    """A graphify repo that also declares two derived outputs."""
    (tmp_path / "mise.toml").write_text(
        '[tools]\n"pipx:graphifyy" = { version = "0.9.25", extras = ["all"] }\n',
        encoding="utf-8",
    )
    (tmp_path / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'artifact = "graphify-out/graph.json"\n'
        'artifacts = ["graphify-out/GRAPH_REPORT.md", "graphify-out/wiki"]\n'
        'stamp = "graphify-out/.currency-stamp.json"\n',
        encoding="utf-8",
    )
    out = tmp_path / "graphify-out"
    (out).mkdir(parents=True, exist_ok=True)
    (out / "graph.json").write_text('{"nodes": []}', encoding="utf-8")
    (out / "GRAPH_REPORT.md").write_text("# report\n", encoding="utf-8")
    wiki = out / "wiki"
    wiki.mkdir()
    (wiki / "_index.md").write_text("index\n", encoding="utf-8")
    return tmp_path


def test_a_generated_output_that_changed_after_stamping_is_drift(tmp_path, monkeypatch) -> None:
    """The founding ask: 'in sync with the graph AND generated outputs'.

    A stamp that only fingerprinted graph.json would call a run clean while the
    committed GRAPH_REPORT.md was regenerated by a different graphify — the same
    silent-staleness the single-artifact stamp had for graph.json.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo_with_generated(tmp_path)
    sync.write_stamp(root, config.load(root)[0], version="0.9.25")
    assert _finding(sync.check_sync(root, config.load(root)[0]), "build-stamp").status == sync.OK

    time.sleep(0.01)
    (root / "graphify-out" / "GRAPH_REPORT.md").write_text("# regenerated\n", encoding="utf-8")
    finding = _finding(sync.check_sync(root, config.load(root)[0]), "build-stamp")
    assert finding.status == sync.DRIFT
    assert "GRAPH_REPORT.md (changed)" in finding.detail


def test_a_newly_declared_output_never_stamped_is_drift(tmp_path, monkeypatch) -> None:
    """Adding a path to `artifacts` after a build must not silently pass.

    An output nobody fingerprinted cannot be asserted to match the graph — the
    control arm for 'present + matching' being the ONLY green state.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo_with_generated(tmp_path)
    sync.write_stamp(root, config.load(root)[0], version="0.9.25")
    # A new derived output appears on disk but was not part of the stamp.
    (root / "graphify-out" / "graph.graphml").write_text("<graphml/>", encoding="utf-8")
    (root / "currency.toml").write_text(
        (root / "currency.toml")
        .read_text(encoding="utf-8")
        .replace(
            '"graphify-out/wiki"]',
            '"graphify-out/wiki", "graphify-out/graph.graphml"]',
        ),
        encoding="utf-8",
    )
    finding = _finding(sync.check_sync(root, config.load(root)[0]), "build-stamp")
    assert finding.status == sync.DRIFT
    assert "graph.graphml (never stamped)" in finding.detail


def test_restamp_refreshes_fingerprints_without_a_rebuild(tmp_path, monkeypatch) -> None:
    """`kb-artifacts` regenerates derived outputs, then re-stamps them clean.

    Without the re-stamp, every `kb-artifacts` run would leave step 1 reporting
    the outputs it just legitimately regenerated as 'changed'.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo_with_generated(tmp_path)
    spec = config.load(root)[0]
    sync.write_stamp(root, spec, version="0.9.25", source_ref="v0.9.25")

    time.sleep(0.01)
    (root / "graphify-out" / "GRAPH_REPORT.md").write_text("# regenerated\n", encoding="utf-8")
    assert _finding(sync.check_sync(root, spec), "build-stamp").status == sync.DRIFT

    path = sync.restamp_artifacts(root, spec)
    assert path is not None
    # The version the build recorded is preserved — a re-stamp is not a rebuild.
    assert sync.read_stamp(root, spec)["version"] == "0.9.25"
    assert sync.read_stamp(root, spec)["source_ref"] == "v0.9.25"
    assert _finding(sync.check_sync(root, spec), "build-stamp").status == sync.OK


def test_restamp_is_a_noop_when_no_build_stamp_exists(tmp_path, monkeypatch) -> None:
    """Control arm: a re-stamp must not INVENT a stamp the build never wrote.

    Otherwise `kb-artifacts` on a never-built repo would fabricate a currency
    stamp with an empty version — a false green for a graph that does not exist.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    root = _repo_with_generated(tmp_path)
    assert sync.restamp_artifacts(root, config.load(root)[0]) is None
    assert not (root / "graphify-out" / ".currency-stamp.json").exists()


# ------------------------------------------------- self-managed (mise) ----
#
# A tool that bootstraps the toolchain cannot honestly be pinned in `[tools]`:
# measured 2026-07-27, adding `ubi:jdx/mise` moved `which(mise)` from the ambient
# `~/.local/bin/mise` to the install dir, so the check would have compared the
# pinned copy against the pin and reported in sync forever while the binary that
# actually runs every task drifted. Hence `expected` + a version read from the
# binary, and hence these arms.


def _self_managed(tmp_path, **overrides: str) -> config.ToolSpec:
    (tmp_path / "currency.toml").write_text(
        "[tool.mise]\n"
        'binary = "mise"\n'
        f'expected = "{overrides.get("expected", "2026.7.15")}"\n'
        'version_pattern = "^v?(\\\\d+\\\\.\\\\d+\\\\.\\\\d+)"\n',
        encoding="utf-8",
    )
    return config.load(tmp_path)[0]


def test_a_tool_with_expected_is_self_managed(tmp_path) -> None:
    assert _self_managed(tmp_path).self_managed is True
    assert config.load(_repo(tmp_path))[0].self_managed is False


def test_a_self_managed_tool_needs_no_mise_key(tmp_path) -> None:
    """Requiring one would force a fake pin at a `[tools]` entry that must not exist."""
    assert _self_managed(tmp_path).mise_key == ""


def test_a_tool_declaring_none_of_the_three_kinds_is_rejected(tmp_path) -> None:
    """CONTROL ARM: the relaxation must not accept a spec that declares nothing.

    Three kinds now, not two — `source_only` joined mise-managed and self-managed
    when SkillOpt needed declaring (see `tests/test_currency_source_only.py`). The
    assertion widened with the contract rather than being deleted: what must hold
    is that a spec naming NO kind is still refused.
    """
    (tmp_path / "currency.toml").write_text('[tool.x]\nbinary = "x"\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"mise_key.*expected.*source_only"):
        config.load(tmp_path)


def test_the_running_version_matching_the_reviewed_one_is_ok(tmp_path, monkeypatch) -> None:
    spec = _self_managed(tmp_path)
    monkeypatch.setattr(sync.shutil, "which", lambda _b: "/usr/local/bin/mise")
    monkeypatch.setattr(sync, "observed_version", lambda _b, _p="": "2026.7.15")
    status = sync.check_sync(tmp_path, spec)
    assert status.ok
    assert status.verified
    assert _finding(status, "version").status == sync.OK


def test_a_self_updated_binary_is_drift(tmp_path, monkeypatch) -> None:
    """THE point of the entry: the host moved under us and nothing else would say so."""
    spec = _self_managed(tmp_path, expected="2026.7.0")
    monkeypatch.setattr(sync.shutil, "which", lambda _b: "/usr/local/bin/mise")
    monkeypatch.setattr(sync, "observed_version", lambda _b, _p="": "2026.7.15")
    status = sync.check_sync(tmp_path, spec)
    assert not status.ok
    detail = _finding(status, "version").detail
    assert "2026.7.15" in detail
    assert "2026.7.0" in detail
    # It must say what to DO — the config is not wrong, the host moved.
    assert "bump `expected`" in detail


def test_resolving_outside_mise_is_normal_for_a_self_managed_tool(tmp_path, monkeypatch) -> None:
    """CONTROL ARM against the mise-managed path, which calls this exact state DRIFT.

    `~/.local/bin/mise` is where mise correctly lives; reporting it as drift
    would make the entry permanently red and therefore ignored.
    """
    spec = _self_managed(tmp_path)
    monkeypatch.setattr(sync.shutil, "which", lambda _b: "/Users/x/.local/bin/mise")
    monkeypatch.setattr(sync, "observed_version", lambda _b, _p="": "2026.7.15")
    assert sync.check_sync(tmp_path, spec).ok


def test_an_unreadable_version_is_blind_not_drift(tmp_path, monkeypatch) -> None:
    """A broken `version_pattern` must not masquerade as a tool upgrade.

    Rendering it as DRIFT would send the reader to review release notes for a
    bump that never happened; BLIND says the probe failed, which is the truth.
    """
    spec = _self_managed(tmp_path)
    monkeypatch.setattr(sync.shutil, "which", lambda _b: "/usr/local/bin/mise")
    monkeypatch.setattr(sync, "observed_version", lambda _b, _p="": "")
    status = sync.check_sync(tmp_path, spec)
    assert status.ok  # BLIND is not red...
    assert not status.verified  # ...but it is emphatically not a pass either
    assert _finding(status, "version").status == sync.BLIND


def test_an_absent_self_managed_binary_is_drift(tmp_path, monkeypatch) -> None:
    spec = _self_managed(tmp_path)
    monkeypatch.setattr(sync.shutil, "which", lambda _b: None)
    assert not sync.check_sync(tmp_path, spec).ok


# ------------------------------------------------------ version parsing ----


def test_a_pattern_extracts_the_version_from_richer_output(monkeypatch) -> None:
    """`mise --version` prints `<version> <arch> (<date>)`, so last-field is the DATE.

    This silently produced `observed_version("mise") == "(2026-07-27)"` — a
    string no comparison could ever match.
    """
    monkeypatch.setattr(sync.shutil, "which", lambda _b: "/usr/local/bin/mise")
    monkeypatch.setattr(
        sync.subprocess,
        "run",
        lambda *_a, **_k: type(
            "R", (), {"returncode": 0, "stdout": "2026.7.15 macos-arm64 (2026-07-27)", "stderr": ""}
        )(),
    )
    assert sync.observed_version("mise", r"^v?(\d+\.\d+\.\d+)") == "2026.7.15"
    # CONTROL ARM: the heuristic this replaces, on the same input.
    assert sync.observed_version("mise") == "(2026-07-27)"


def test_a_non_matching_pattern_returns_empty_rather_than_falling_back(monkeypatch) -> None:
    """CONTROL ARM: silent fallback would hide a stale pattern behind a plausible value."""
    monkeypatch.setattr(sync.shutil, "which", lambda _b: "/usr/local/bin/mise")
    monkeypatch.setattr(
        sync.subprocess,
        "run",
        lambda *_a, **_k: type(
            "R", (), {"returncode": 0, "stdout": "graphify 0.9.26", "stderr": ""}
        )(),
    )
    assert sync.observed_version("mise", r"^NOPE(\d+)") == ""
    assert sync.observed_version("mise") == "0.9.26"


# --- A `manifest` on a self-managed row must actually be CHECKED (#242) --------
#
# It was not, until 2026-08-08: `check_sync` returned out of `_check_self_managed`
# before `_check_manifest` could run, so the key was declared, parsed, and never
# read. The hole was invisible in exactly the way that matters — a DEAD check
# reports nothing, which is indistinguishable from a check that passed.
#
# Found by a cold review lane; the arm that proved it was reverting
# `sources/mise.manifest` three releases and getting silence, while the identical
# mutation on mise-managed `hk` fired.


def _self_managed_with_manifest(tmp_path, *, ref: str) -> config.ToolSpec:
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "sources" / "mise.manifest").write_text(
        f"url = https://github.com/jdx/mise\nref = {ref}\ncommit = " + "0" * 40 + "\n",
        encoding="utf-8",
    )
    (tmp_path / "currency.toml").write_text(
        "[tool.mise]\n"
        'binary = "mise"\n'
        'expected = "2026.7.15"\n'
        'manifest = "sources/mise.manifest"\n'
        'version_pattern = "^v?(\\\\d+\\\\.\\\\d+\\\\.\\\\d+)"\n',
        encoding="utf-8",
    )
    return config.load(tmp_path)[0]


def test_a_self_managed_manifest_behind_the_running_version_is_drift(tmp_path, monkeypatch):
    """THE regression arm: this reported nothing at all before the fix."""
    spec = _self_managed_with_manifest(tmp_path, ref="v2026.7.0")
    monkeypatch.setattr(sync.shutil, "which", lambda _b: "/usr/local/bin/mise")
    monkeypatch.setattr(sync, "observed_version", lambda _b, _p="": "2026.7.15")
    status = sync.check_sync(tmp_path, spec)
    manifest = _finding(status, "manifest")
    assert manifest.status == sync.DRIFT
    assert "v2026.7.0" in manifest.detail
    # And it must not claim a manager that is not involved: mise does not install
    # mise. The wording follows the row shape.
    assert "mise installs" not in manifest.detail
    assert "the running version is" in manifest.detail


def test_a_self_managed_manifest_matching_the_running_version_is_not_drift(tmp_path, monkeypatch):
    """CONTROL ARM: the check must be able to return the other answer."""
    spec = _self_managed_with_manifest(tmp_path, ref="v2026.7.15")
    monkeypatch.setattr(sync.shutil, "which", lambda _b: "/usr/local/bin/mise")
    monkeypatch.setattr(sync, "observed_version", lambda _b, _p="": "2026.7.15")
    status = sync.check_sync(tmp_path, spec)
    assert _finding(status, "manifest").status != sync.DRIFT


def test_a_mise_managed_manifest_still_says_mise_installs(tmp_path) -> None:
    """CONTROL ARM on the WORDING split: the original path must be unchanged.

    Calls `_check_manifest` directly, because reaching it through `check_sync`
    on the mise-managed path needs a whole `[tools]` pin and install dir — this
    test is about one sentence, not about that plumbing.
    """
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "sources" / "hk.manifest").write_text(
        "url = https://github.com/jdx/hk\nref = v1.54.0\ncommit = " + "0" * 40 + "\n",
        encoding="utf-8",
    )
    (tmp_path / "currency.toml").write_text(
        '[tool.hk]\nmise_key = "hk"\nbinary = "hk"\nmanifest = "sources/hk.manifest"\n',
        encoding="utf-8",
    )
    spec = config.load(tmp_path)[0]
    assert spec.self_managed is False
    detail = sync._check_manifest(tmp_path, spec, "1.54.1").detail
    assert "mise installs" in detail
    assert "the running version is" not in detail


# --- #245/#246: a prefixed tag, and an ANNOTATED tag's two identities ---------


def test_a_tag_prefix_is_stripped_before_the_version_compare(tmp_path) -> None:
    """Codex tags `rust-v0.147.0`, not `v0.147.0`.

    Comparing that literally to an installed `0.147.0` reported drift on a
    manifest pinned exactly right (#245).
    """
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "sources" / "codex.manifest").write_text(
        "url = https://github.com/openai/codex\nref = rust-v0.147.0\ncommit = " + "0" * 40 + "\n",
        encoding="utf-8",
    )
    (tmp_path / "currency.toml").write_text(
        '[tool.codex]\nmise_key = "codex"\nbinary = "codex"\n'
        'tag_prefix = "rust-v"\nmanifest = "sources/codex.manifest"\n',
        encoding="utf-8",
    )
    spec = config.load(tmp_path)[0]
    assert spec.tag_prefix == "rust-v"
    # The REF compare passes; only the commit check can speak, and with no clone
    # it must SKIP rather than claim agreement.
    assert sync._check_manifest(tmp_path, spec, "0.147.0").status == sync.SKIP


def test_without_the_prefix_the_same_pin_would_drift(tmp_path) -> None:
    """CONTROL ARM: the prefix is what makes the row correct, not the widening."""
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "sources" / "codex.manifest").write_text(
        "url = https://github.com/openai/codex\nref = rust-v0.147.0\ncommit = " + "0" * 40 + "\n",
        encoding="utf-8",
    )
    (tmp_path / "currency.toml").write_text(
        '[tool.codex]\nmise_key = "codex"\nbinary = "codex"\nmanifest = "sources/codex.manifest"\n',
        encoding="utf-8",
    )
    spec = config.load(tmp_path)[0]
    assert spec.tag_prefix == ""
    assert sync._check_manifest(tmp_path, spec, "0.147.0").status == sync.DRIFT


def test_rev_parse_and_rev_list_are_distinct_resolvers() -> None:
    """The first attempt at #246 failed BECAUSE they were not.

    `rev-list` peels for both `<ref>` and `<ref>^{}`, so asking it twice compared
    peeled against peeled and still reported drift on a correct manifest. Only
    `rev-parse` returns the tag object that `ls-remote` recorded.

    A constants check, and on its own it was ALL the coverage #246 had: the two
    tests beside it used manifests with no clone, so they reached the
    `resolved is None` SKIP and never the widened compare. Dropping `tag_object`
    entirely left every one of them green (cold lane, 2026-08-08). The three
    tests below are the behavioural arm this one cannot be.
    """
    assert sync._RESOLVERS["rev-list"] == ("rev-list", "-n1")
    assert sync._RESOLVERS["rev-parse"] == ("rev-parse",)


def test_the_fixture_annotated_tag_really_has_two_identities(tmp_path) -> None:
    """CONTROL ARM ON THE FIXTURE, and it has to come first.

    The three tests below are only meaningful if the tag object and the peeled
    commit are actually DIFFERENT SHAs here. If git ever produced one SHA for
    both — or the `-a` were dropped from the helper — those tests would keep
    passing while testing nothing, which is precisely the defect they replace.
    """
    root = _repo(tmp_path)
    peeled = _clone_at(root, "v0.9.25", annotated=True)
    assert _git(root, "rev-parse", "v0.9.25") != peeled


def test_an_annotated_tags_tag_object_sha_is_accepted(tmp_path) -> None:
    """What `kb-manifest-add` actually records, via `git ls-remote`.

    This is the row that reported DRIFT on a manifest pinned exactly right, and
    it is the one a regression to a single `rev-list` resolver breaks.
    """
    root = _repo(tmp_path)
    _clone_at(root, "v0.9.25", annotated=True)
    _write_manifest(root, "v0.9.25", commit=_git(root, "rev-parse", "v0.9.25"))
    assert sync._check_manifest(root, _spec(root), "0.9.25").status == sync.OK


def test_an_annotated_tags_peeled_commit_is_also_accepted(tmp_path) -> None:
    """The OTHER identity: a checkout of either SHA produces the same tree.

    So both are true answers to "what does this ref name", and accepting both is
    a widening rather than a normalisation.
    """
    root = _repo(tmp_path)
    peeled = _clone_at(root, "v0.9.25", annotated=True)
    _write_manifest(root, "v0.9.25", commit=peeled)
    assert sync._check_manifest(root, _spec(root), "0.9.25").status == sync.OK


def test_a_wrong_sha_still_drifts_through_the_widened_compare(tmp_path) -> None:
    """CONTROL ARM: the check was WIDENED, not lost.

    Two accepted SHAs is a check; three is a check that cannot fail. A manifest
    naming neither identity must still report DRIFT.
    """
    root = _repo(tmp_path)
    _clone_at(root, "v0.9.25", annotated=True)
    _write_manifest(root, "v0.9.25", commit="0" * 40)
    assert sync._check_manifest(root, _spec(root), "0.9.25").status == sync.DRIFT


def test_a_lightweight_tag_costs_the_widening_no_precision(tmp_path) -> None:
    """CONTROL ARM on the OTHER tag kind: one SHA under both resolvers.

    Measured upstream on astral-sh/uv 0.12.3. If accepting two identities had
    weakened the lightweight path, a wrong SHA here would stop drifting.
    """
    root = _repo(tmp_path)
    peeled = _clone_at(root, "v0.9.25")
    assert _git(root, "rev-parse", "v0.9.25") == peeled
    _write_manifest(root, "v0.9.25", commit="0" * 40)
    assert sync._check_manifest(root, _spec(root), "0.9.25").status == sync.DRIFT


def test_the_unresolvable_skip_does_not_claim_the_clone_is_absent(tmp_path) -> None:
    """A SKIP whose stated reason is FALSE is how a real DRIFT gets read as fine.

    It said "its clone is absent" while `sources/mise/.git` was a directory —
    the ref simply did not resolve. Naming the wrong cause sends the reader to
    fix something that is not broken.
    """
    (tmp_path / "sources").mkdir(exist_ok=True)
    (tmp_path / "sources" / "hk.manifest").write_text(
        "url = https://github.com/jdx/hk\nref = v1.54.1\ncommit = " + "0" * 40 + "\n",
        encoding="utf-8",
    )
    (tmp_path / "currency.toml").write_text(
        '[tool.hk]\nmise_key = "hk"\nbinary = "hk"\nmanifest = "sources/hk.manifest"\n',
        encoding="utf-8",
    )
    spec = config.load(tmp_path)[0]
    detail = sync._check_manifest(tmp_path, spec, "1.54.1").detail
    assert "clone is absent" not in detail
    assert "could not resolve that ref" in detail
