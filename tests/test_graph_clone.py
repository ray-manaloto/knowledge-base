# Copyright (c) 2026 Raymond Manaloto
"""Tests for kb_setup.graph._ensure_clone — pin advance vs. an existing clone.

The bug these pin: `_ensure_clone` used to `git checkout <pinned sha>` in an
EXISTING clone without ever fetching. A clone predates any later pin advance,
so the newly-pinned commit simply is not in it and git dies with
"fatal: unable to read tree". Observed 2026-07-23 on
`kb-update -- claude-plugins-community` (pin 086db464, clone still at
07fb1efe) — which means update was broken for every source whose clone
already existed, i.e. every source after its first build.

Driving this through real git would need network and a live upstream, and the
live re-run afterwards was ambiguous (the object arrived, but no fetch was
observed). So the code path is asserted directly here instead: a check whose
result you cannot attribute is not a check.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from kb_setup import graph
from kb_setup import manifest as mf

_PINNED = "086db464d0e8f648627aaef2aa8bd4775d6d85a4"


def _manifest(tmp_path: Path) -> mf.Manifest:
    """A manifest whose clone_dir already looks like a real git clone."""
    src = tmp_path / "sources"
    (src / "demo" / ".git").mkdir(parents=True)
    return mf.Manifest(
        name="demo",
        path=src / "demo.manifest",
        url="https://example.invalid/o/demo",
        ref="main",
        commit=_PINNED,
    )


def _record(monkeypatch, *, has_commit: bool) -> list[list[str]]:
    """Stub subprocess.run; `has_commit` decides what `git cat-file -e` reports."""
    calls: list[list[str]] = []

    class _P:
        def __init__(self, rc: int) -> None:
            self.returncode = rc
            self.stdout = _PINNED + "\n"

    def fake_run(cmd: list[str], **_kw: object) -> _P:
        calls.append(cmd)
        if "cat-file" in cmd:
            return _P(0 if has_commit else 1)
        return _P(0)

    monkeypatch.setattr(graph.subprocess, "run", fake_run)
    return calls


def _verbs(calls: list[list[str]]) -> list[str]:
    """The git subcommand of each recorded call (e.g. 'fetch', 'checkout')."""
    known = ("cat-file", "fetch", "rev-parse", "checkout")
    return [next(verb for verb in known if verb in call) for call in calls if call[0] == "git"]


def test_fetches_when_pinned_commit_is_absent(monkeypatch, tmp_path):
    """The regression case: pin advanced, clone stale -> must fetch before checkout."""
    calls = _record(monkeypatch, has_commit=False)
    graph._ensure_clone(_manifest(tmp_path))

    verbs = _verbs(calls)
    assert "fetch" in verbs, f"expected a fetch, saw {verbs}"
    assert verbs.index("fetch") < verbs.index("checkout"), "fetch must precede checkout"
    fetch = next(call for call in calls if "fetch" in call)
    assert fetch[-1] == _PINNED
    assert "main" not in fetch[fetch.index("fetch") + 1 :]


def test_does_not_fetch_when_commit_already_present(monkeypatch, tmp_path):
    """CONTROL ARM: the common path must stay offline — no needless network."""
    calls = _record(monkeypatch, has_commit=True)
    graph._ensure_clone(_manifest(tmp_path))

    verbs = _verbs(calls)
    assert "fetch" not in verbs, f"must not fetch when the object is present, saw {verbs}"
    assert "checkout" in verbs


@pytest.mark.parametrize("has_commit", [True, False])
def test_always_checks_out_the_pinned_commit(monkeypatch, tmp_path, has_commit):
    """Whichever path is taken, the pinned SHA is what gets checked out."""
    calls = _record(monkeypatch, has_commit=has_commit)
    graph._ensure_clone(_manifest(tmp_path))

    checkout = next(c for c in calls if "checkout" in c)
    assert checkout[-1] == _PINNED
    assert "--detach" in checkout
    assert "advice.detachedHead=false" in checkout


def _git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _remote_with_unreachable_pin(tmp_path: Path) -> tuple[Path, Path, str]:
    work = tmp_path / "upstream-work"
    remote = tmp_path / "upstream.git"
    work.mkdir()
    _git("init", "-b", "main", cwd=work)
    _git("config", "user.name", "Graph Clone Test", cwd=work)
    _git("config", "user.email", "graph-clone@example.invalid", cwd=work)
    (work / "tracked.txt").write_text("main\n", encoding="utf-8")
    _git("add", "tracked.txt", cwd=work)
    _git("commit", "-m", "main", cwd=work)
    _git("clone", "--bare", str(work), str(remote), cwd=tmp_path)

    _git("switch", "-c", "historical", cwd=work)
    (work / "tracked.txt").write_text("historical pin\n", encoding="utf-8")
    _git("commit", "-am", "historical", cwd=work)
    pin = _git("rev-parse", "HEAD", cwd=work)
    _git("push", str(remote), "historical", cwd=work)
    return remote, work, pin


def _existing_single_branch_clone(tmp_path: Path, remote: Path) -> mf.Manifest:
    sources = tmp_path / "sources"
    sources.mkdir(exist_ok=True)
    clone = sources / "demo"
    _git("clone", "--single-branch", "--branch", "main", str(remote), str(clone), cwd=tmp_path)
    return mf.Manifest(
        name="demo",
        path=sources / "demo.manifest",
        url=str(remote),
        ref="main",
        commit="",
    )


def test_fetches_exact_pin_not_reachable_from_manifest_ref(tmp_path: Path) -> None:
    remote, _work, pin = _remote_with_unreachable_pin(tmp_path)
    manifest = _existing_single_branch_clone(tmp_path, remote)
    manifest = mf.Manifest(
        name=manifest.name,
        path=manifest.path,
        url=manifest.url,
        ref=manifest.ref,
        commit=pin,
    )

    graph._ensure_clone(manifest)

    assert _git("rev-parse", "HEAD", cwd=manifest.clone_dir) == pin


def test_unfetchable_exact_pin_fails(tmp_path: Path) -> None:
    remote, _work, _pin = _remote_with_unreachable_pin(tmp_path)
    manifest = _existing_single_branch_clone(tmp_path, remote)
    manifest = mf.Manifest(
        name=manifest.name,
        path=manifest.path,
        url=manifest.url,
        ref=manifest.ref,
        commit="a" * 40,
    )

    with pytest.raises(subprocess.CalledProcessError):
        graph._ensure_clone(manifest)


def test_annotated_tag_object_pin_peels_to_verified_commit_and_tree(tmp_path: Path) -> None:
    remote, work, _pin = _remote_with_unreachable_pin(tmp_path)
    _git("tag", "-a", "v-test", "-m", "annotated", cwd=work)
    _git("push", str(remote), "refs/tags/v-test", cwd=work)
    tag_object = _git("rev-parse", "v-test", cwd=work)
    peeled_commit = _git("rev-parse", "v-test^{commit}", cwd=work)
    manifest = _existing_single_branch_clone(tmp_path, remote)
    manifest = mf.Manifest(
        name=manifest.name,
        path=manifest.path,
        url=manifest.url,
        ref="v-test",
        commit=tag_object,
    )

    graph._ensure_clone(manifest)

    assert _git("cat-file", "-t", tag_object, cwd=manifest.clone_dir) == "tag"
    assert _git("rev-parse", "HEAD", cwd=manifest.clone_dir) == peeled_commit
