# Copyright (c) 2026 Raymond Manaloto
"""Repo lint checks implemented in python (zero-bash-logic).

The KB has NO bash scripts and no inline shell logic in hk.pkl / mise.toml: every
non-trivial check lives here and is invoked as `uv run kb-setup <cmd>`. This module
holds the checks the hk config calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kb_setup.result import Ok, Rc, Result, exit_code

# Inline suppression markers that must NEVER appear in source — all suppressions
# live in the ONE pyproject.toml as ruff per-file-ignores, so they are visible and
# reviewable in one place rather than scattered through the code.
_SUPPRESSIONS = (
    "noqa",
    "type: ignore",
    "ty: ignore",
    "ty:ignore",
    "ruff:ignore",
    "ruff:file-ignore",
    "ruff:disable",
    "pylint: disable",
    "nosec",
)

_SCAN_DIRS = ("python/src", "tests")


def find_inline_suppressions(repo_root: Path) -> list[tuple[Path, int, str]]:
    """Return (path, lineno, marker) for every inline suppression in scanned .py.

    Skips THIS module — it necessarily contains every marker literally (in
    `_SUPPRESSIONS`), so scanning itself would be a guaranteed false positive.
    """
    self_file = Path(__file__).resolve()
    hits: list[tuple[Path, int, str]] = []
    for rel in _SCAN_DIRS:
        base = repo_root / rel
        if not base.is_dir():
            continue
        for py in sorted(base.rglob("*.py")):
            if py.resolve() == self_file:
                continue
            rel_path = py.relative_to(repo_root)
            for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                hits.extend(
                    (rel_path, lineno, marker) for marker in _SUPPRESSIONS if marker in line
                )
    return hits


def check_no_lint_skip(repo_root: Path) -> Result[list[tuple[Path, int, str]]]:
    """The boundary (§2 R5): the suppressions found, and whether that is a finding.

    Returns rather than raises, and prints nothing — `no_lint_skip` renders.
    Same split as `check.check`/`check.main`, which is `ruff`'s
    `pub fn run(..) -> Result<ExitStatus>` (`crates/ruff/src/lib.rs:128`).

    **Hits are `Ok`, not `Err`.** Finding suppressions is this gate doing its
    job — it ran, it looked, it found something. `Err` is reserved for "could
    not run", which for a filesystem walk over the repo has no case here.
    """
    hits = find_inline_suppressions(repo_root)
    return Ok(hits, rc=Rc.FINDINGS if hits else Rc.OK)


def no_lint_skip(repo_root: Path) -> int:
    """Fail if any inline lint suppression exists in source. Zero-skip policy.

    Kept returning `int`: `cli.py` and this module's existing exit-code
    assertions are the regression arm for the `Result` split, exactly as
    `check.main` is for `check.check`.
    """
    result = check_no_lint_skip(repo_root)
    if isinstance(result, Ok) and result.value:
        print(
            "Inline lint suppressions are forbidden (use pyproject per-file-ignores):",
            file=sys.stderr,
        )
        for path, lineno, marker in result.value:
            print(f"  {path}:{lineno}: {marker!r}", file=sys.stderr)
    return exit_code(result)
