# Copyright (c) 2026 Raymond Manaloto
"""Drift gate for every generated msgspec model.

Replaces four generate_*.py/check_*_codegen.py wrapper pairs (#569) with
datamodel-code-generator's own `--all-jobs --check`, run through the same
locked resolution the wrappers used to hand-assert with a `--version` check:
`--project . --locked --group codegen` refuses to run against anything but the
pinned, locked `datamodel-code-generator`, which is what makes that trio the
version guard now — see the `[tool.datamodel-codegen]` comment in
pyproject.toml.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_CODEGEN = (
    "uv",
    "run",
    "--project",
    str(ROOT),
    "--locked",
    "--group",
    "codegen",
    "datamodel-codegen",
)


def test_all_jobs_check_is_clean() -> None:
    """Every checked-in generated model matches what `--all-jobs` would produce."""
    result = subprocess.run(
        [*_CODEGEN, "--all-jobs", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
