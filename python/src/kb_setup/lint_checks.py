"""Repo lint checks implemented in python (zero-bash-logic).

The KB has NO bash scripts and no inline shell logic in hk.pkl / mise.toml: every
non-trivial check lives here and is invoked as `uv run kb-setup <cmd>`. This module
holds the checks the hk config calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

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


def no_lint_skip(repo_root: Path) -> int:
    """Fail (rc=1) if any inline lint suppression exists in source. Zero-skip policy."""
    hits = find_inline_suppressions(repo_root)
    if not hits:
        return 0
    print(
        "Inline lint suppressions are forbidden (use pyproject per-file-ignores):", file=sys.stderr
    )
    for path, lineno, marker in hits:
        print(f"  {path}:{lineno}: {marker!r}", file=sys.stderr)
    return 1
