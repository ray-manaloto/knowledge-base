# Copyright (c) 2026 Raymond Manaloto
"""The reviewed pin -> mise lock/install -> skill refresh protocol."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from kb_setup import graphify_env, tool_sync
from kb_setup.currency import config, skill, sync
from kb_setup.currency.config import ToolSpec
from kb_setup.currency.skill import SkillResult

_SPEC = ToolSpec(
    name="graphify",
    mise_key="pipx:graphifyy",
    binary="graphify",
    skill_dir=".claude/skills/graphify",
    skill_install=("true",),
)
_SDK_PROBE = (
    "from pathlib import Path; from graphify.detect import detect; "
    "r=detect(Path('.graphify-sdk-probe-missing')); assert r['total_files'] == 0"
)


def _ok(argv: list[str], _root: Path) -> subprocess.CompletedProcess[str]:
    stdout = "graphify 0.9.39\n" if argv[-1] == "--version" else ""
    return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")


def _wire(monkeypatch: pytest.MonkeyPatch, calls: list[list[str]]) -> None:
    monkeypatch.setattr(config, "load", lambda _root: (_SPEC,))
    monkeypatch.setattr(sync, "pinned_version", lambda _root, _spec: ("0.9.39", ("all",)))
    monkeypatch.setattr(
        tool_sync,
        "_run",
        lambda argv, root: (calls.append(argv), _ok(argv, root))[1],
    )
    monkeypatch.setattr(graphify_env, "graphify_python", lambda _root: "/pinned/python")
    monkeypatch.setattr(skill, "refresh", lambda _root, _spec: SkillResult(ran=True))


def test_sync_uses_mise_for_lock_and_install_then_refreshes(tmp_path, monkeypatch) -> None:
    """The task must not stop after editing a pin or laundering a version stamp."""
    calls: list[list[str]] = []
    _wire(monkeypatch, calls)

    assert tool_sync.main(tmp_path, ["graphify"]) == 0
    assert calls == [
        ["mise", "lock", "pipx:graphifyy"],
        ["mise", "install", "pipx:graphifyy"],
        ["mise", "exec", "--", "graphify", "--version"],
        [
            "/pinned/python",
            "-c",
            _SDK_PROBE,
        ],
    ]


def test_a_failed_lock_prevents_install_and_refresh(tmp_path, monkeypatch) -> None:
    """A stale lock is a failure, not permission to install around it."""
    calls: list[list[str]] = []
    monkeypatch.setattr(config, "load", lambda _root: (_SPEC,))
    monkeypatch.setattr(sync, "pinned_version", lambda _root, _spec: ("0.9.39", ("all",)))

    def fail(argv: list[str], _root: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 7, stdout="", stderr="lock failed")

    monkeypatch.setattr(tool_sync, "_run", fail)
    monkeypatch.setattr(
        skill,
        "refresh",
        lambda _root, _spec: pytest.fail("refresh ran after the lock failed"),
    )

    assert tool_sync.main(tmp_path, ["graphify"]) == 7
    assert calls == [["mise", "lock", "pipx:graphifyy"]]


def test_a_post_install_version_mismatch_is_not_success(tmp_path, monkeypatch) -> None:
    """The executable is the proof; agreeing config files cannot make it green."""
    calls: list[list[str]] = []
    _wire(monkeypatch, calls)
    monkeypatch.setattr(tool_sync, "_observed_via_mise", lambda _root, _spec: "0.9.36")

    assert tool_sync.main(tmp_path, ["graphify"]) == 1


def test_sync_uses_a_declared_nonstandard_version_flag(tmp_path, monkeypatch) -> None:
    """FFmpeg's real ``-version`` flag is part of its executable proof."""
    calls: list[list[str]] = []
    ffmpeg = ToolSpec(
        name="ffmpeg",
        mise_key="conda:ffmpeg",
        binary="ffmpeg",
        version_args=("-version",),
        version_pattern=r"^ffmpeg version (\d+\.\d+)",
    )
    monkeypatch.setattr(config, "load", lambda _root: (ffmpeg,))
    monkeypatch.setattr(sync, "pinned_version", lambda _root, _spec: ("9.0", ()))

    def run(argv: list[str], _root: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        stdout = "ffmpeg version 9.0 Copyright\n" if argv[-1] == "-version" else ""
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(tool_sync, "_run", run)
    assert tool_sync.main(tmp_path, ["ffmpeg"]) == 0
    assert ["mise", "exec", "--", "ffmpeg", "-version"] in calls
