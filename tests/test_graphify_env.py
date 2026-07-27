"""Tests for `kb_setup.graphify_env` — the PATH-independent resolver and clean_env.

`graphify_exe` is the durable half of #40. The launcher can verify a PATH and
still not deliver it (tmux hands a pane the CLIENT's PATH), so corpus correctness
must not depend on PATH ordering at all. `graphify_exe` asks mise, which answers
from the repo's config and therefore follows the pin by construction.

`clean_env` is what every graphify subprocess runs under, and it strips for two
unrelated reasons — backend triggers by name, mise's secret-bearing `__MISE_*`
blob by prefix.

Every check is armed in both directions: a resolver that can only return the
mise answer would hide a mise-less machine, one that can only fall back would
silently reintroduce the PATH dependency this exists to remove, and an
"is it absent from clean_env?" assertion passes trivially on any host where mise
never set the variable — so each strip arm SETS the variable first.
"""

from __future__ import annotations

import os
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


# --- clean_env: two independent strips ---------------------------------------
#
# Every arm below sets the variable in the fixture environment and asserts it is
# PRESENT in os.environ before asserting it is absent from clean_env(). Without
# that first half the test passes on a host where mise never ran — a check that
# can only pass (`probes-need-a-control-arm.md`).


def test_the_mise_secret_blob_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE point of the second strip: `__MISE_DIFF` must not reach a subprocess.

    It carries the *values* of the credentials `_STRIP_BACKEND_ENV` removes by
    *name*, gzip+base64'd past any secret scanner. Asserted on presence/absence of
    the KEY only — never decode the blob to inspect it; doing that is what put
    live credentials into a session transcript.
    """
    monkeypatch.setenv("__MISE_DIFF", "sentinel-not-a-real-blob")
    monkeypatch.setenv("__MISE_SESSION", "sentinel-session")
    assert "__MISE_DIFF" in os.environ  # arm: the fixture really set it
    assert "__MISE_SESSION" in os.environ

    env = graphify_env.clean_env()

    assert "__MISE_DIFF" not in env
    assert "__MISE_SESSION" not in env


def test_the_strip_is_a_prefix_not_a_spelling(monkeypatch: pytest.MonkeyPatch) -> None:
    """A name list would cover today's two blobs and fail open on a third.

    This arm is the difference between the rule as written and the rule the
    handoff proposed: an unknown future `__MISE_*` must be stripped too, without
    anyone editing this module.
    """
    monkeypatch.setenv("__MISE_FUTURE_BLOB", "sentinel-unknown-to-us")
    assert "__MISE_FUTURE_BLOB" in os.environ

    assert "__MISE_FUTURE_BLOB" not in graphify_env.clean_env()


def test_public_mise_config_survives(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTROL ARM: the prefix must be `__MISE_`, not `MISE_`.

    A strip that also ate single-underscore `MISE_*` would pass every arm above
    and break real configuration — `kb_setup.currency.sync` reads `MISE_DATA_DIR`.
    Proves the rule discriminates rather than deleting anything mise-shaped.
    """
    monkeypatch.setenv("MISE_DATA_DIR", "sentinel-data-dir")
    monkeypatch.setenv("MISE_ENV_CACHE", "1")

    env = graphify_env.clean_env()

    assert env["MISE_DATA_DIR"] == "sentinel-data-dir"
    assert env["MISE_ENV_CACHE"] == "1"


def test_backend_triggers_are_still_stripped_and_claude_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTROL ARM for the FIRST strip, which the new prefix must not disturb.

    `ANTHROPIC_API_KEY` surviving is the other half: a clean_env that dropped
    everything would pass "the secret is gone" while silently killing the one
    backend this repo is allowed to use (`do-not.md` #4).
    """
    monkeypatch.setenv("GEMINI_API_KEY", "sentinel-forbidden")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sentinel-forbidden")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sentinel-kept")
    assert "GEMINI_API_KEY" in os.environ

    env = graphify_env.clean_env()

    assert "GEMINI_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert env["ANTHROPIC_API_KEY"] == "sentinel-kept"


def test_extra_still_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTROL ARM: `extra` is applied AFTER the strips, so callers can override."""
    monkeypatch.setenv("__MISE_DIFF", "sentinel-not-a-real-blob")

    env = graphify_env.clean_env({"GRAPHIFY_TEST": "on", "__MISE_DIFF": "explicit"})

    assert env["GRAPHIFY_TEST"] == "on"
    assert env["__MISE_DIFF"] == "explicit"
