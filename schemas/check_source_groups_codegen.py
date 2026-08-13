# Copyright (c) 2026 Raymond Manaloto
"""Fail when the checked-in source-group models drift from their schema."""

from __future__ import annotations

import tempfile
from pathlib import Path

from schemas.generate_source_groups import OUTPUT, ROOT, generate


def main() -> int:
    """Generate to a temporary path and compare exact bytes."""
    # Keep the candidate beneath ROOT so ruff-format discovers this project's
    # line-length/config. A system-temp output would use ruff defaults and make
    # byte output depend on where the comparison happened.
    with tempfile.TemporaryDirectory(prefix=".source-groups-codegen-", dir=ROOT) as directory:
        candidate = Path(directory) / OUTPUT.name
        generate(candidate)
        if candidate.read_bytes() != OUTPUT.read_bytes():
            print("source-groups codegen drift: run `mise run kb-source-groups-codegen`")
            return 1
    print("source-groups codegen PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
