# Copyright (c) 2026 Raymond Manaloto
"""The shared Graphify subprocess boundary must not launder warnings."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from kb_setup import graph


def test_run_refuses_stderr_at_zero_and_retains_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    warning = b"WARNING: degraded build\n"
    monkeypatch.setattr(
        graph.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["graphify"], 0, stdout=b"progress\n", stderr=warning
        ),
    )

    with pytest.raises(SystemExit) as exc:
        graph._run(["graphify", "merge-graphs"], tmp_path)

    captured = capfd.readouterr()
    assert captured.out.endswith("progress\n")
    assert captured.err == warning.decode()
    assert f"stderr_bytes={len(warning)}" in str(exc.value)
    assert hashlib.sha256(warning).hexdigest() in str(exc.value)


def test_run_accepts_clean_stdout_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        graph.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["graphify"], 0, stdout=b"complete\n", stderr=b""
        ),
    )

    graph._run(["graphify", "merge-graphs"], tmp_path)

    captured = capfd.readouterr()
    assert captured.out.endswith("complete\n")
    assert captured.err == ""


def test_run_retains_nonzero_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        graph.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["graphify"], 9, stdout=b"", stderr=b"failed\n"
        ),
    )

    with pytest.raises(subprocess.CalledProcessError, match="exit status 9"):
        graph._run(["graphify", "merge-graphs"], tmp_path)

    assert capfd.readouterr().err == "failed\n"


def test_strict_version_rejects_warning_beside_valid_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(graph, "graphify_exe", lambda _root: "/graphify")
    monkeypatch.setattr(
        graph.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["/graphify", "--version"],
            0,
            stdout=b"graphify 0.9.41\n",
            stderr=b"WARNING: version environment degraded\n",
        ),
    )

    assert graph._strict_graphify_version(tmp_path) == ""


def test_strict_version_accepts_clean_version_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(graph, "graphify_exe", lambda _root: "/graphify")
    monkeypatch.setattr(
        graph.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["/graphify", "--version"], 0, stdout=b"graphify 0.9.41\n", stderr=b""
        ),
    )

    assert graph._strict_graphify_version(tmp_path) == "0.9.41"
