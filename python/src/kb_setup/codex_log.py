# Copyright (c) 2026 Raymond Manaloto
"""Make Codex's nonfatal malformed-role warning a lane failure."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def malformed_agent_roles(text: str) -> list[str]:
    """Return complete warning lines without discarding the role's name."""
    return [
        line for line in text.splitlines() if "Ignoring malformed agent role definition" in line
    ]


def main(argv: list[str]) -> int:
    """Check an existing log; unreadable logs cannot certify a clean lane."""
    parser = argparse.ArgumentParser(prog="kb-setup codex-log-check")
    parser.add_argument("log", type=Path)
    args = parser.parse_args(argv)
    try:
        hits = malformed_agent_roles(args.log.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"codex-log-check: NOT CHECKED: {exc}", file=sys.stderr)
        return 1
    for line in hits:
        print(line, file=sys.stderr)
    return int(bool(hits))
