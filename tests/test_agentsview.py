# Copyright (c) 2026 Raymond Manaloto
"""`kb_setup.agentsview` — the refusals, not the happy path.

NO TEST HERE RUNS THE REAL BINARY. It indexes ~8,829 session files on this
machine, needs a daemon, and its answers change while the suite runs — so a
test that shelled out would be measuring the author's laptop, not the module.
Every case fakes `subprocess.run` and asserts on what the module DECIDES.

WHAT IS ACTUALLY WORTH TESTING. The module's reason for existing is a single
distinction: an empty answer that means *"asked, found nothing"* versus one that
means *"never successfully asked."* agentsview reads a mutable derived index, so
those two are byte-identical at the shell — and the second, reported as the
first, is a false evidentiary claim about a session. So the tests that matter
are the ones proving a broken sync can never be rendered as a clean zero.

The `--reveal` case is the other one: it unredacts detected secrets, and
`secret_guard` (#441) exists so a credential never reaches a transcript. A task
that could print one through a side door would be a hole in that guard.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from kb_setup import agentsview
from kb_setup.result import Rc


def _proc(rc: int, out: str = "", err: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["agentsview"], returncode=rc, stdout=out, stderr=err)


@pytest.fixture
def _binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agentsview.shutil, "which", lambda _: "/fake/agentsview")


def test_missing_binary_is_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """An absent tool is NOT_RUN, never an empty result set."""
    monkeypatch.setattr(agentsview.shutil, "which", lambda _: None)
    assert agentsview.main(["anything"], Path()) == Rc.NOT_RUN


@pytest.mark.usefixtures("_binary")
def test_failed_sync_refuses_rather_than_searching(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE central case. A non-zero sync must not fall through to a search.

    If it did, the search would answer from a stale or absent index and the
    caller would read "0 matches" as a fact about the sessions.
    """
    calls: list[list[str]] = []

    def fake(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        del timeout
        calls.append(args)
        return _proc(1, err="disk on fire")

    monkeypatch.setattr(agentsview, "_run", fake)
    assert agentsview.main(["pattern"], Path()) == Rc.NOT_RUN
    assert len(calls) == 1, "it must NOT have gone on to run the search"
    assert calls[0][1] == "sync"
    assert "refusing to search a stale or absent index" in capsys.readouterr().out


@pytest.mark.usefixtures("_binary")
def test_timed_out_sync_is_also_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A timeout is an interrupted index, which is a stale index."""
    monkeypatch.setattr(agentsview, "_run", lambda *_a, **_k: None)
    assert agentsview.main(["pattern"], Path()) == Rc.NOT_RUN


@pytest.mark.usefixtures("_binary")
def test_zero_matches_after_a_green_sync_is_ok_and_says_it_searched(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other side of the distinction: a REAL zero is rc 0 and self-describing."""

    def fake(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        del timeout
        return _proc(0, out='{"matches": []}') if "search" in args else _proc(0)

    monkeypatch.setattr(agentsview, "_run", fake)
    assert agentsview.main(["nothing-matches-this"], Path()) == Rc.OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["searched"] is True
    assert payload["synced"] is True
    assert payload["results"] == {"matches": []}


@pytest.mark.usefixtures("_binary")
def test_no_sync_reports_synced_false(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--no-sync` still answers, but must never claim the index was freshened."""
    monkeypatch.setattr(agentsview, "_run", lambda *_a, **_k: _proc(0, out="{}"))
    assert agentsview.main(["p", "--no-sync"], Path()) == Rc.OK
    assert json.loads(capsys.readouterr().out)["synced"] is False


@pytest.mark.usefixtures("_binary")
def test_non_json_output_is_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unparsable output is a failure to ask, not an empty answer."""

    def fake(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        del timeout
        return _proc(0, out="<html>login</html>") if "search" in args else _proc(0)

    monkeypatch.setattr(agentsview, "_run", fake)
    assert agentsview.main(["p"], Path()) == Rc.NOT_RUN


@pytest.mark.usefixtures("_binary")
def test_reveal_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--reveal` unredacts secrets; argparse exits 2 on a parser error."""
    monkeypatch.setattr(agentsview, "_run", lambda *_a, **_k: _proc(0, out="{}"))
    with pytest.raises(SystemExit) as exc:
        agentsview.main(["p", "--reveal"], Path())
    assert exc.value.code == Rc.BAD_REQUEST


def test_forced_env_pins_telemetry_and_update_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Telemetry off and update-check off must survive into the child process.

    Update-check specifically: on 2026-09-01 both `claude-code` and `mise` were
    found to have self-updated out from under their pins on this machine, so a
    pinned tool that phones home about versions is one release away from
    joining them.
    """
    monkeypatch.setenv("AGENTSVIEW_TELEMETRY_ENABLED", "1")
    env = agentsview._env()
    assert env["AGENTSVIEW_TELEMETRY_ENABLED"] == "0"
    assert env["AGENTSVIEW_DISABLE_UPDATE_CHECK"] == "1"


def test_no_daemon_is_not_forced() -> None:
    """A regression guard on a REFUTED design, not a style preference.

    `AGENTSVIEW_NO_DAEMON=1` was in `_FORCED_ENV` and made every search fail
    with *"daemon autostart is disabled"* — measured against the installed
    0.41.1, where only `usage daily` reads SQLite directly. Re-adding it would
    break the task while every other test here still passed, because they all
    fake the subprocess.
    """
    assert "AGENTSVIEW_NO_DAEMON" not in agentsview._FORCED_ENV
