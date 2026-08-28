# Copyright (c) 2026 Raymond Manaloto
"""Deterministic research-record codegen controls."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_model_exactly_matches_cold_codegen() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "schemas.check_research_record_codegen"],
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0


def test_codegen_is_byte_stable() -> None:
    output = ROOT / "python/src/kb_setup/generated/research_record.py"
    before = hashlib.sha256(output.read_bytes()).digest()
    subprocess.run(
        [sys.executable, "schemas/generate_research_record.py"],
        cwd=ROOT,
        check=True,
    )
    assert hashlib.sha256(output.read_bytes()).digest() == before
