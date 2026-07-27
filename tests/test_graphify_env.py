"""Tests for `kb_setup.graphify_env.graphify_exe` — the PATH-independent resolver.

This is the durable half of #40. The launcher can verify a PATH and still not
deliver it (tmux hands a pane the CLIENT's PATH), so corpus correctness must not
depend on PATH ordering at all. `graphify_exe` asks mise, which answers from the
repo's config and therefore follows the pin by construction.

Every check is armed in both directions: a resolver that can only return the
mise answer would hide a mise-less machine, and one that can only fall back
would silently reintroduce the PATH dependency this exists to remove.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import graphify_env

if TYPE_CHECKING:
    import pytest

_PINNED = "/mise/installs/pipx-graphifyy/0.9.26/bin/graphify"
_ON_PATH = "/somewhere/else/graphify"


def _fake_run(stdout: str) -> object:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_mise_answer_wins_over_path_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE point: what `mise which` says beats whatever sits first on PATH."""
    monkeypatch.setattr(graphify_env.subprocess, "run", lambda *_a, **_k: _fake_run(_PINNED))
    monkeypatch.setattr(graphify_env.shutil, "which", lambda _t: _ON_PATH)
    monkeypatch.setattr(Path, "is_file", lambda self: str(self) == _PINNED)

    assert graphify_env.graphify_exe(Path("/repo")) == _PINNED


def test_it_falls_back_to_path_when_mise_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTROL ARM: a machine without mise must still get a working binary.

    Without this arm the test above passes for a resolver that always returns the
    mise answer — including on hosts where asking mise is impossible.
    """

    def _boom(*_a: object, **_k: object) -> object:
        raise OSError("mise not installed")

    monkeypatch.setattr(graphify_env.subprocess, "run", _boom)
    monkeypatch.setattr(graphify_env.shutil, "which", lambda _t: _ON_PATH)

    assert graphify_env.graphify_exe(Path("/repo")) == _ON_PATH


def test_a_mise_answer_pointing_nowhere_is_not_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A path mise names but that does not exist is not an answer.

    Fail-closed on garbage rather than handing a non-existent argv[0] to
    subprocess, which would surface as a confusing FileNotFoundError far from
    here.
    """
    gone = "/gone/graphify"
    monkeypatch.setattr(graphify_env.subprocess, "run", lambda *_a, **_k: _fake_run(gone))
    monkeypatch.setattr(graphify_env.shutil, "which", lambda _t: _ON_PATH)
    monkeypatch.setattr(Path, "is_file", lambda _self: False)

    assert graphify_env.graphify_exe(Path("/repo")) == _ON_PATH


def test_empty_mise_output_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """`mise which` exiting 0 with nothing to say is also not an answer."""
    monkeypatch.setattr(graphify_env.subprocess, "run", lambda *_a, **_k: _fake_run("  \n"))
    monkeypatch.setattr(graphify_env.shutil, "which", lambda _t: _ON_PATH)

    assert graphify_env.graphify_exe(Path("/repo")) == _ON_PATH


def test_the_last_resort_is_a_bare_name_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing resolves: return the bare name so the failure names the tool."""
    monkeypatch.setattr(graphify_env.subprocess, "run", lambda *_a, **_k: _fake_run(""))
    monkeypatch.setattr(graphify_env.shutil, "which", lambda _t: None)

    assert graphify_env.graphify_exe(Path("/repo")) == "graphify"


def test_the_fallback_is_loud(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Falling back is allowed; falling back SILENTLY is not.

    The whole point of this resolver is that PATH order stops deciding. When it
    cannot deliver that, the caller is back to the old behaviour — and a build
    log that does not say so renders "could not check" as "fine", the exact
    collapse the currency engine refuses to make.
    """
    graphify_env._WARNED.clear()
    monkeypatch.setattr(graphify_env.subprocess, "run", lambda *_a, **_k: _fake_run(""))
    monkeypatch.setattr(graphify_env.shutil, "which", lambda _t: _ON_PATH)

    graphify_env.graphify_exe(Path("/repo"))

    err = capsys.readouterr().err
    assert "WARNING" in err
    assert "does NOT follow this repo's pin" in err


def test_the_warning_does_not_repeat(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """CONTROL ARM: loud once, not eight times.

    `kb-artifacts` resolves per output; a warning per call would bury the run.
    Armed against the test above — together they pin "warns" AND "warns once",
    neither of which alone is the requirement.
    """
    graphify_env._WARNED.clear()
    monkeypatch.setattr(graphify_env.subprocess, "run", lambda *_a, **_k: _fake_run(""))
    monkeypatch.setattr(graphify_env.shutil, "which", lambda _t: _ON_PATH)

    for _ in range(3):
        graphify_env.graphify_exe(Path("/repo"))

    assert capsys.readouterr().err.count("WARNING") == 1


def test_a_successful_resolve_is_quiet(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """CONTROL ARM: the happy path must not warn, or the warning means nothing."""
    graphify_env._WARNED.clear()
    monkeypatch.setattr(graphify_env.subprocess, "run", lambda *_a, **_k: _fake_run(_PINNED))
    monkeypatch.setattr(Path, "is_file", lambda self: str(self) == _PINNED)

    graphify_env.graphify_exe(Path("/repo"))

    assert capsys.readouterr().err == ""
