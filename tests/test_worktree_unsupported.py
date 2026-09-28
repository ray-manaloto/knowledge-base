# Copyright (c) 2026 Raymond Manaloto
"""Fail-closed behavior when macOS clonefile is unavailable."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import worktree

if TYPE_CHECKING:
    import pytest


def test_missing_clonefile_backend_refuses_without_creating_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"source bytes")
    destination = tmp_path / "destination"
    if sys.platform != "darwin":
        assert worktree._LIBC is None
    monkeypatch.setattr(worktree, "_LIBC", None)

    failure = worktree._clonefile(source, destination)

    assert "ENOTSUP" in failure
    assert not destination.exists()
    assert source.read_bytes() == b"source bytes"
