# Copyright (c) 2026 Raymond Manaloto
"""The final Graphify label pass must retain and reject warning output."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import graphify_ops

if TYPE_CHECKING:
    import pytest


def test_label_refuses_stderr_at_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    exe = tmp_path / "graphify"
    exe.touch()
    warning = b"WARNING: label degraded\n"
    monkeypatch.setattr(graphify_ops, "graphify_exe", lambda _root: str(exe))
    monkeypatch.setattr(graphify_ops, "assert_pinned_graphify", lambda _root: None)
    monkeypatch.setattr(graphify_ops.stamps, "snapshot_views", lambda _root: {})
    monkeypatch.setattr(
        graphify_ops.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [str(exe)], 0, stdout=b"labelled\n", stderr=warning
        ),
    )

    assert graphify_ops.label(tmp_path) == 3

    captured = capfd.readouterr()
    assert captured.out.endswith("labelled\n")
    assert warning.decode() in captured.err
    assert f"stderr_bytes={len(warning)}" in captured.err
    assert hashlib.sha256(warning).hexdigest() in captured.err
