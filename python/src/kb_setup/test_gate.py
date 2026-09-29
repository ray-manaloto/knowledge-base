# Copyright (c) 2026 Raymond Manaloto
"""Run the canonical test gate only after its worktree inputs are available."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from kb_setup.result import Rc

_REQUIRED_PATHS = (
    "sources/graphify",
    "sources/skillopt",
    "graphify-out/graph.json",
)


def preflight(repo_root: Path, *, has_codegen: Callable[[], bool] | None = None) -> tuple[str, ...]:
    """Name missing inputs before an expensive suite can misreport a code defect."""
    missing = tuple(path for path in _REQUIRED_PATHS if not (repo_root / path).exists())
    probe = has_codegen or (lambda: importlib.util.find_spec("grpc_tools") is not None)
    if not probe():
        missing += ("locked codegen dependency group (grpcio-tools)",)
    return missing


def main(
    repo_root: Path,
    argv: Sequence[str] = (),
    *,
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
    has_codegen: Callable[[], bool] | None = None,
) -> int:
    """Run pytest in this exact interpreter, preserving its direct exit code."""
    missing = preflight(repo_root, has_codegen=has_codegen)
    if missing:
        print(f"test: NOT_RUN — missing {', '.join(missing)}; run `mise run kb-worktree-ready`")
        return int(Rc.NOT_RUN)
    command = [sys.executable, "-m", "pytest", "tests/", "-x", "-q", "-n", "auto", *argv]
    return runner(command, cwd=repo_root, check=False).returncode
