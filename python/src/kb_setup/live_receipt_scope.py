# Copyright (c) 2026 Raymond Manaloto
"""Classify exact PR changed paths for the signed Graphify live-evidence gate.

The protected-main workflow supplies NUL-delimited paths from Git. Ambiguous
input requires evidence rather than exempting a change.
"""

from __future__ import annotations

import argparse
from pathlib import Path

MAX_INPUT_BYTES = 1_000_000
SENSITIVE_EXACT = {
    b"pyproject.toml",
    b"uv.lock",
    b"mise.toml",
    b"mise.lock",
    b"AGENTS.md",
    b"CLAUDE.md",
    b".claude/CLAUDE.md",
    b".claude/settings.json",
    b".mcp.json",
    b"sources/graphify.manifest",
    b"sources/graphify.dispositions.json",
    b"sources/planning-with-files.manifest",
    b".github/graphify/allowed-signers",
    b".github/workflows/graphify-integration.yml",
    b".github/workflows/graphify-live-receipt.yml",
    b"python/src/kb_setup/graph.py",
    b"python/src/kb_setup/manifest.py",
    b"python/src/kb_setup/chunks.py",
    b"python/src/kb_setup/cli.py",
    b"python/src/kb_setup/fetch.py",
    b"python/src/kb_setup/extract_census.py",
    b"python/src/kb_setup/live_receipt.py",
    b"python/src/kb_setup/live_receipt_produce.py",
    b"python/src/kb_setup/live_receipt_scope.py",
    b".claude/workflows/kb-extract.js",
}
SENSITIVE_PREFIXES = (
    # Shared helpers can affect extraction through the CLI's import graph.
    # Fail closed for new modules too; a static name list missed result.py.
    b"python/src/kb_setup/",
    # Agent instructions can select the ingestion task, CLI, model or profile.
    # Guard new skill/rule paths too, not just the currently named Graphify skill.
    b".agents/skills/",
    b".claude/skills/",
    b".claude/rules/",
    b".claude/agents/",
    b".claude/mods/",
    b".claude/workflows/",
    b".codex/",
)


def needs_live_receipt(changed_paths: bytes) -> bool:
    """Require evidence for extraction-capable changes or malformed path data."""
    if len(changed_paths) > MAX_INPUT_BYTES or (
        changed_paths and not changed_paths.endswith(b"\0")
    ):
        return True
    paths = [path for path in changed_paths.split(b"\0") if path]
    if not paths:
        return True  # A PR with no observable changed paths is ambiguous.
    return any(path in SENSITIVE_EXACT or path.startswith(SENSITIVE_PREFIXES) for path in paths)


def main() -> int:
    """Print one stable token for the protected workflow's shell decision."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-paths", required=True, type=Path)
    args = parser.parse_args()
    try:
        required = needs_live_receipt(args.changed_paths.read_bytes())
    except OSError:
        required = True
    print("REQUIRED" if required else "EXEMPT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
