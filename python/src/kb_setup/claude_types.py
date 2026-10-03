# Copyright (c) 2026 Raymond Manaloto
"""One Claude-types pin reader and hygiene-normalized refresh for both repos."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

import httpx2

from kb_setup import atomic

_HYGIENE = (
    ("trailing-whitespace", ("--fix",)),
    ("end-of-file-fixer", ("--fix",)),
    ("mixed-line-ending", ("--fix",)),
    ("fix-smart-quotes", ()),
)
_ROW = re.compile(r"(?ms)^\[\[schema\]\]\s*\n(?:(?!^\[).)*")
_SHA = re.compile(r'(?m)^(sha256\s*=\s*")[^"]+("[^\n]*)$')


@dataclass(frozen=True)
class ClaudeTypesPin:
    """Only the shared claude-code row; other tools belong to their consumer."""

    version: str
    source: str
    sha256: str
    file: str


def load_pin(root: Path) -> ClaudeTypesPin:
    """Fail closed if the manifest or its unique Claude row is absent."""
    data = tomllib.loads((root / "schemas/sources.toml").read_text(encoding="utf-8"))
    rows = [row for row in data.get("schema", []) if row.get("tool") == "claude-code"]
    if len(rows) != 1:
        raise ValueError("schemas/sources.toml requires exactly one claude-code row")
    row = rows[0]
    pin = ClaudeTypesPin(**{key: row[key] for key in ("version", "source", "sha256", "file")})
    if not all(isinstance(v, str) and v for v in (pin.version, pin.source, pin.sha256, pin.file)):
        raise ValueError("claude-code pin fields must be nonempty strings")
    if not (root / pin.file).resolve().is_relative_to(root.resolve()):
        raise ValueError("claude-code file must stay inside the repository")
    expected = f"https://raw.githubusercontent.com/anthropics/claude-code/v{pin.version}/mods/types/claude-code.d.ts"
    if pin.source != expected:
        raise ValueError("claude-code source does not name the pinned upstream tag")
    return pin


def check(root: Path) -> list[str]:
    """Require bytes and a real sha; missing metadata is never a presence-only pass."""
    try:
        pin = load_pin(root)
        raw = (root / pin.file).read_bytes()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"claude-types NOT CHECKED: {exc}"]
    if not raw:
        return ["claude-code declarations are empty"]
    if hashlib.sha256(raw).hexdigest() != pin.sha256:
        return ["claude-code vendored declarations sha256 mismatch; run claude-types-refresh"]
    return []


def _normalize(raw: bytes, root: Path) -> bytes:
    """Use hk's real hygiene fixers before publishing or hashing the bytes."""
    with tempfile.TemporaryDirectory(prefix="claude-types-") as tmp:
        scratch = Path(tmp) / "claude-code.d.ts"
        scratch.write_bytes(raw)
        for fixer, flags in _HYGIENE:
            result = subprocess.run(
                ["hk", "util", fixer, *flags, str(scratch)],
                cwd=root,
                capture_output=True,
                check=False,
                timeout=120,
            )
            if result.returncode not in (0, 1):
                detail = result.stderr.decode(errors="replace")
                raise RuntimeError(f"hk util {fixer} rc={result.returncode}: {detail}")
        return scratch.read_bytes()


def render_sha(source: str, sha256: str) -> str:
    """Replace only the bound row's hash, preserving every other byte and line."""
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        row = match.group()
        if re.search(r'(?m)^tool\s*=\s*"claude-code"\s*$', row) is None:
            return row
        updated, changes = _SHA.subn(lambda sha: sha[1] + sha256 + sha[2], row)
        count += changes
        return updated

    rendered = _ROW.sub(replace, source)
    if count != 1:
        raise ValueError("claude-code row must contain exactly one sha256 value")
    return rendered


def refresh(root: Path) -> ClaudeTypesPin:
    """Fetch the pinned file, normalize it, and update its hash without row reflow."""
    pin = load_pin(root)
    with httpx2.Client(timeout=30.0) as client:
        response = client.get(pin.source)
        response.raise_for_status()
        raw = _normalize(response.content, root)
    if not raw:
        raise ValueError("pinned upstream Claude declarations were empty")
    manifest = root / "schemas/sources.toml"
    updated = render_sha(manifest.read_text(encoding="utf-8"), hashlib.sha256(raw).hexdigest())
    destination = root / pin.file
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_text(destination, raw.decode())
    atomic.write_text(manifest, updated)
    return load_pin(root)


def main(root: Path, argv: list[str], *, do_refresh: bool = False) -> int:
    """Expose the shared check and refresh commands without consumer imports."""
    argparse.ArgumentParser(
        prog="claude-types-refresh" if do_refresh else "claude-types-check"
    ).parse_args(argv)
    if do_refresh:
        refresh(root)
    findings = check(root)
    for finding in findings:
        print(finding)
    return int(bool(findings))
