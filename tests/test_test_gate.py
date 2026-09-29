# Copyright (c) 2026 Raymond Manaloto
"""The test task must fail before pytest if a fresh worktree is not prepared."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import test_gate
from kb_setup.result import Rc

if TYPE_CHECKING:
    import pytest


def test_unprepared_primary_checkout_never_starts_pytest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def never_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise AssertionError("pytest must not start")

    assert test_gate.main(tmp_path, runner=never_run, has_codegen=lambda: False) == Rc.NOT_RUN
    assert "run `mise run kb-build`" in capsys.readouterr().out


def test_unprepared_linked_worktree_gets_worktree_setup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".git").write_text("gitdir: /tmp/example")
    assert test_gate.main(tmp_path, has_codegen=lambda: False) == Rc.NOT_RUN
    assert "run `mise run kb-worktree-ready`" in capsys.readouterr().out


def test_prepared_worktree_uses_the_locked_interpreter(tmp_path: Path) -> None:
    for relative in (
        "sources/graphify/.git",
        "sources/skillopt/.git",
        "graphify-out/graph.json",
        "graphify-out/graph-prose.json",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.name != ".git":
            path.touch()
        else:
            path.mkdir()
    seen: list[object] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        seen.extend((command, kwargs))
        return subprocess.CompletedProcess(command, 7)

    assert test_gate.main(tmp_path, runner=run, has_codegen=lambda: True) == 7
    assert seen[0] == [sys.executable, "-m", "pytest", "tests/", "-x", "-q", "-n", "auto"]
    assert seen[1] == {"cwd": tmp_path, "check": False}


def test_targeted_test_path_does_not_collect_whole_suite(tmp_path: Path) -> None:
    for relative in (
        "sources/graphify/.git",
        "sources/skillopt/.git",
        "graphify-out/graph.json",
        "graphify-out/graph-prose.json",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.name == ".git":
            path.mkdir()
        else:
            path.touch()
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    rc = test_gate.main(
        tmp_path, ("tests/test_test_gate.py",), runner=run, has_codegen=lambda: True
    )
    assert rc == 0
    assert commands[0].count("tests/") == 0
    assert commands[0][-1] == "tests/test_test_gate.py"


def test_default_uv_sync_keeps_the_codegen_group() -> None:
    repo = Path(__file__).resolve().parents[1]
    project = tomllib.loads((repo / "pyproject.toml").read_text())
    tasks = tomllib.loads((repo / "mise.toml").read_text())
    assert set(project["tool"]["uv"]["default-groups"]) == {"dev", "codegen"}
    assert tasks["tasks"]["test"]["run"] == "uv run --locked kb-setup test"
