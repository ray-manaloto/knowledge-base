# Copyright (c) 2026 Raymond Manaloto
"""The Claude-types sha is a real pin, and refreshing cannot reflow its row."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from kb_setup import claude_types


def _fixture(root: Path) -> Path:
    target = root / ".claude/types/claude-code.d.ts"
    target.parent.mkdir(parents=True)
    target.write_text("declare module 'claude-code' {}\n")
    manifest = root / "schemas/sources.toml"
    manifest.parent.mkdir()
    manifest.write_text(
        "[[schema]]\n"
        'tool = "claude-code"\n'
        'file = ".claude/types/claude-code.d.ts"\n'
        'version = "2.1.287"\n'
        'source = "https://raw.githubusercontent.com/anthropics/claude-code/v2.1.287/mods/types/claude-code.d.ts"\n'
        'pin_source = "schemas/sources.toml (vendored; no mise [tools] pin)"\n'
        f'sha256 = "{hashlib.sha256(target.read_bytes()).hexdigest()}"\n'
    )
    return manifest


def test_pin_sha_check_and_missing_row_fail_closed(tmp_path: Path) -> None:
    assert claude_types.check(tmp_path)
    manifest = _fixture(tmp_path)
    assert claude_types.check(tmp_path) == []
    pin = claude_types.load_pin(tmp_path)
    (tmp_path / pin.file).write_text("hand edited\n")
    assert "sha256 mismatch" in claude_types.check(tmp_path)[0]
    manifest.write_text("schema = []\n")
    assert "exactly one claude-code row" in claude_types.check(tmp_path)[0]


def test_sha_render_preserves_every_other_line(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    original = manifest.read_text()
    rendered = claude_types.render_sha(original, "a" * 64)
    before = original.splitlines()
    after = rendered.splitlines()
    assert len(before) == len(after)
    assert [line for line in before if not line.startswith("sha256 =")] == [
        line for line in after if not line.startswith("sha256 =")
    ]
    assert (
        'tool = "claude-code"\nfile = ".claude/types/claude-code.d.ts"\nversion = "2.1.287"'
        in rendered
    )
    with pytest.raises(ValueError, match="exactly one sha256"):
        claude_types.render_sha(original.replace("sha256 =", "removed ="), "a" * 64)


def test_real_repository_pin_and_empty_mcp_merge() -> None:
    root = Path(__file__).resolve().parents[1]
    assert claude_types.check(root) == []
    mcp = (root / ".claude/types/claude-code-mcp.d.ts").read_text()
    assert "interface McpToolInputs {}" in mcp
    assert "context7" not in mcp
    assert "exa" not in mcp
    assert "Upstream version:" not in (root / ".claude/types/README.md").read_text()
