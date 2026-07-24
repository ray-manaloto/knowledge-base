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
