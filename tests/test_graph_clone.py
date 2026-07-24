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

    def fake_run(cmd: list[str], **_kw: object) -> _P:
        calls.append(cmd)
        if "cat-file" in cmd:
            return _P(0 if has_commit else 1)
        return _P(0)

    monkeypatch.setattr(graph.subprocess, "run", fake_run)
    return calls


def _verbs(calls: list[list[str]]) -> list[str]:
    """The git subcommand of each recorded call (e.g. 'fetch', 'checkout')."""
    return [c[3] for c in calls if len(c) > 3 and c[0] == "git" and c[1] == "-C"]


def test_fetches_when_pinned_commit_is_absent(monkeypatch, tmp_path):
    """The regression case: pin advanced, clone stale -> must fetch before checkout."""
    calls = _record(monkeypatch, has_commit=False)
    graph._ensure_clone(_manifest(tmp_path))

    verbs = _verbs(calls)
    assert "fetch" in verbs, f"expected a fetch, saw {verbs}"
    assert verbs.index("fetch") < verbs.index("checkout"), "fetch must precede checkout"


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

    checkout = next(c for c in calls if len(c) > 3 and c[3] == "checkout")
    assert checkout[-1] == _PINNED
