# Copyright (c) 2026 Raymond Manaloto
"""Fail when checked-in session-selection models drift from their schema."""

from __future__ import annotations

import tempfile
from pathlib import Path

from schemas.generate_session_select import OUTPUT, ROOT, generate


def main() -> int:
    """Generate to a temporary path and compare exact bytes."""
    with tempfile.TemporaryDirectory(prefix=".session-select-codegen-", dir=ROOT) as directory:
        candidate = Path(directory) / OUTPUT.name
        generate(candidate)
        if candidate.read_bytes() != OUTPUT.read_bytes():
            print("session-select codegen drift: rerun schemas/generate_session_select.py")
            return 1
    print("session-select codegen PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
