# Copyright (c) 2026 Raymond Manaloto
"""Classify an exact PR tree diff for the signed Graphify live-evidence gate.

The protected-main workflow supplies NUL-delimited paths and a zero-context
``mise.toml`` diff from Git. Ambiguous input requires evidence rather than
exempting a change.
"""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

MAX_INPUT_BYTES = 1_000_000
SENSITIVE_EXACT = {
    b"pyproject.toml",
    b"uv.lock",
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
    b"python/src/kb_setup/graphify",
    b".agents/skills/graphify/",
    b".claude/skills/graphify/",
)
#: `mise.toml` lines that can change what an extraction runs. `hk` (the git-hook
#: runner) and `postinstall` were dropped 2026-10-01 (#824, Ray's ruling): neither
#: is exercised by the eight live cases, and matching them made every hk bump
#: unmergeable while no evidence producer exists.
MISE_SENSITIVE = re.compile(
    rb"graphify|python|\buv\b|\bpkl\b|kb-build|kb-ingest|kb-native",
    re.IGNORECASE,
)


#: The `mise.lock` tool entries the eight signed live cases actually exercise
#: (`live_receipt.CASES`: graphify and planning-with-files extraction through the
#: claude-cli and openai-cli backends, NORMAL and DEEP), plus the interpreter and
#: resolver the extraction venv is built with. A change to any of these entries
#: still REQUIRES evidence. Every OTHER tool pin (hk, rumdl, antigravity-cli, gh,
#: typos, ...) is EXEMPT: it cannot change what an extraction produces, and
#: requiring evidence for it made every ordinary pin bump unmergeable (#824).
#: Listed by every spelling a backend can give the same tool, because the lock
#: key is the backend-qualified name. `node` is deliberately absent — it was the
#: original exemption and stays one.
EXTRACTION_LOCK_TOOLS = frozenset(
    {
        "python",
        "uv",
        # openai-cli backend
        "codex",
        "npm:@openai/codex",
        "aqua:openai/codex",
        "github:openai/codex",
        # claude-cli backend
        "claude",
        "claude-code",
        "npm:@anthropic-ai/claude-code",
        "github:anthropics/claude-code",
    }
)
#: Substrings that mark a lock entry as extraction-relevant whatever its backend
#: prefix (`pipx:graphifyy`, `pypi:planning-with-files`, ...).
EXTRACTION_LOCK_MARKERS = ("graphify", "planning-with-files")


def _extraction_relevant(tool: str) -> bool:
    lowered = tool.lower()
    return lowered in EXTRACTION_LOCK_TOOLS or any(m in lowered for m in EXTRACTION_LOCK_MARKERS)


def _only_exempt_lock_tools_changed(before: bytes, after: bytes) -> bool:
    """Accept a lock diff that touches only non-extraction tool entries (#824).

    Fail closed: an empty, oversized or unparsable lockfile, a `tools` table
    that is not a table, or ANY change outside `tools` (e.g. `conda-packages`)
    all return False, so evidence stays REQUIRED. An added or removed tool entry
    counts as a change to that tool.
    """
    if not before or not after or max(len(before), len(after)) > MAX_INPUT_BYTES:
        return False
    try:
        old = tomllib.loads(before.decode("utf-8"))
        new = tomllib.loads(after.decode("utf-8"))
    except UnicodeDecodeError:
        return False
    except tomllib.TOMLDecodeError:
        return False
    old_tools = old.pop("tools", None)
    new_tools = new.pop("tools", None)
    if not isinstance(old_tools, dict) or not isinstance(new_tools, dict) or old != new:
        return False
    changed = {
        tool
        for tool in old_tools.keys() | new_tools.keys()
        if old_tools.get(tool) != new_tools.get(tool)
    }
    return not any(_extraction_relevant(tool) for tool in changed)


def needs_live_receipt(
    changed_paths: bytes, mise_diff: bytes, *, base_lock: bytes = b"", head_lock: bytes = b""
) -> bool:
    """Require evidence for extraction-capable changes or malformed diff data."""
    if (
        len(changed_paths) > MAX_INPUT_BYTES
        or len(mise_diff) > MAX_INPUT_BYTES
        or (changed_paths and not changed_paths.endswith(b"\0"))
    ):
        return True
    paths = [path for path in changed_paths.split(b"\0") if path]
    if not paths:
        return True  # A PR with no observable changed paths is ambiguous.
    if any(path in SENSITIVE_EXACT or path.startswith(SENSITIVE_PREFIXES) for path in paths) or (
        b"mise.lock" in paths and not _only_exempt_lock_tools_changed(base_lock, head_lock)
    ):
        return True
    if b"mise.toml" in paths:
        if not mise_diff:
            return True
        for line in mise_diff.splitlines():
            if line.startswith((b"+++", b"---")):
                continue
            if line.startswith((b"+", b"-")) and MISE_SENSITIVE.search(line[1:]):
                return True
    return False


def main() -> int:
    """Print one stable token for the protected workflow's shell decision."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-paths", required=True, type=Path)
    parser.add_argument("--mise-diff", required=True, type=Path)
    parser.add_argument("--base-lock", required=True, type=Path)
    parser.add_argument("--head-lock", required=True, type=Path)
    args = parser.parse_args()
    try:
        required = needs_live_receipt(
            args.changed_paths.read_bytes(),
            args.mise_diff.read_bytes(),
            base_lock=args.base_lock.read_bytes(),
            head_lock=args.head_lock.read_bytes(),
        )
    except OSError:
        required = True
    print("REQUIRED" if required else "EXEMPT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
