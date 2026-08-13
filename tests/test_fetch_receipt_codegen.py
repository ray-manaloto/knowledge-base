# Copyright (c) 2026 Raymond Manaloto
"""Deterministic fetch-receipt codegen and workflow surface controls."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_model_exactly_matches_cold_codegen() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "schemas.check_fetch_receipt_codegen"],
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0


def test_codegen_is_byte_stable() -> None:
    output = ROOT / "python/src/kb_setup/generated/fetch_receipt.py"
    before = hashlib.sha256(output.read_bytes()).digest()
    subprocess.run(
        [sys.executable, "schemas/generate_fetch_receipt.py"],
        cwd=ROOT,
        check=True,
    )
    assert hashlib.sha256(output.read_bytes()).digest() == before


def test_paired_skills_are_exact_and_route_only_through_mise() -> None:
    agents = ROOT / ".agents/skills/artifact-download/SKILL.md"
    claude = ROOT / ".claude/skills/artifact-download/SKILL.md"
    assert agents.read_bytes() == claude.read_bytes()
    text = agents.read_text(encoding="utf-8")
    assert "mise run kb-artifact-download" in text
    assert "no provider adapter" in text
    assert "hf-xet" not in text.lower()
