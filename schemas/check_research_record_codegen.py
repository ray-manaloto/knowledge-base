# Copyright (c) 2026 Raymond Manaloto
"""Fail when checked-in research-record models drift from their schema."""

from __future__ import annotations

import tempfile
from pathlib import Path

from schemas.generate_research_record import OUTPUT, ROOT, generate


def main() -> int:
    """Generate to a temporary path and compare exact bytes."""
    with tempfile.TemporaryDirectory(prefix=".research-record-codegen-", dir=ROOT) as directory:
        candidate = Path(directory) / OUTPUT.name
        generate(candidate)
        if candidate.read_bytes() != OUTPUT.read_bytes():
            print("research-record codegen drift: run `mise run kb-research-record-codegen`")
            return 1
    print("research-record codegen PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
