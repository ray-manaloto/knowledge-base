"""kb_setup.currency._proc — the shared `subprocess.run → degrade, don't raise` shape.

Six currency probes funnel through here, so every failure mode is exercised in
BOTH directions: a broken probe must read as an *error string* (never a crash,
never a silent empty that a caller mistakes for real data), and the control arm
proves a healthy probe still returns its parsed payload with no error.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

from kb_setup.currency import _proc


def _run(
    rc: int = 0, *, stdout: str = "", stderr: str = ""
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def _fake(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], rc, stdout=stdout, stderr=stderr)

    return _fake


# ------------------------------------------------------------- run_capture ----


def test_run_capture_returns_the_process_on_success(monkeypatch) -> None:
    monkeypatch.setattr(_proc.subprocess, "run", _run(0, stdout="hi"))
    proc, err = _proc.run_capture(["true"], timeout=1)
    assert err == ""
    assert proc is not None
    assert proc.stdout == "hi"


def test_run_capture_degrades_a_spawn_failure_to_an_error(monkeypatch) -> None:
    def _boom(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        raise OSError("no such binary")

    monkeypatch.setattr(_proc.subprocess, "run", _boom)
    proc, err = _proc.run_capture(["nope"], timeout=1)
    assert proc is None
    assert "no such binary" in err


def test_run_capture_degrades_a_timeout_to_an_error(monkeypatch) -> None:
    def _slow(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="slow", timeout=1)

    monkeypatch.setattr(_proc.subprocess, "run", _slow)
    proc, err = _proc.run_capture(["slow"], timeout=1)
    assert proc is None
    assert err  # a non-empty reason, not a crash


# ---------------------------------------------------------------- run_json ----


def test_run_json_parses_an_object(monkeypatch) -> None:
    monkeypatch.setattr(_proc.subprocess, "run", _run(0, stdout='{"a": 1}'))
    payload, err = _proc.run_json(["x"], timeout=1, label="x")
    assert err == ""
    assert payload == {"a": 1}


def test_run_json_parses_an_array_in_list_shape(monkeypatch) -> None:
    monkeypatch.setattr(_proc.subprocess, "run", _run(0, stdout="[1, 2]"))
    payload, err = _proc.run_json(["x"], list_shape=True, timeout=1, label="x")
    assert err == ""
    assert payload == [1, 2]


def test_run_json_empty_stdout_is_an_error_not_a_clean_empty(monkeypatch) -> None:
    """Exit 0 with NO output is unreadable, not 'nothing found'.

    Every probe emits a JSON body on success (`mise outdated` prints `{}` when
    clean), so blank stdout is anomalous — coercing it to {}/[] with no error
    would be a false 'nothing found' (the absence-of-evidence trap). The control
    arm below proves a genuine empty container (`{}`) still reads as clean.
    """
    monkeypatch.setattr(_proc.subprocess, "run", _run(0, stdout=""))
    payload, err = _proc.run_json(["x"], timeout=1, label="mise outdated")
    assert payload == {}
    assert "empty output" in err

    monkeypatch.setattr(_proc.subprocess, "run", _run(0, stdout="   \n"))
    payload_l, err_l = _proc.run_json(["x"], list_shape=True, timeout=1, label="x")
    assert payload_l == []
    assert "empty output" in err_l


def test_run_json_explicit_empty_container_reads_as_clean(monkeypatch) -> None:
    """Control arm: an explicit `{}` / `[]` body is a real empty result, no error."""
    monkeypatch.setattr(_proc.subprocess, "run", _run(0, stdout="{}"))
    assert _proc.run_json(["x"], timeout=1, label="x") == ({}, "")
    monkeypatch.setattr(_proc.subprocess, "run", _run(0, stdout="[]"))
    assert _proc.run_json(["x"], list_shape=True, timeout=1, label="x") == ([], "")


def test_run_json_reports_a_nonzero_exit(monkeypatch) -> None:
    monkeypatch.setattr(_proc.subprocess, "run", _run(2, stderr="boom"))
    payload, err = _proc.run_json(["gh", "api", "x"], timeout=1, label="gh api x")
    assert payload == {}
    assert "gh api x exited 2" in err
    assert "boom" in err


def test_run_json_reports_non_json(monkeypatch) -> None:
    monkeypatch.setattr(_proc.subprocess, "run", _run(0, stdout="not json"))
    payload, err = _proc.run_json(["x"], timeout=1, label="mise outdated")
    assert payload == {}
    assert "non-JSON" in err


def test_run_json_wrong_shape_reads_as_empty_plus_error(monkeypatch) -> None:
    """A JSON array where an object was expected must NOT masquerade as data.

    This is the absence-of-evidence guard: silently coercing it to {} with no
    error would let a wrong-shaped upstream response read as 'no findings'.
    """
    monkeypatch.setattr(_proc.subprocess, "run", _run(0, stdout="[1, 2]"))
    payload, err = _proc.run_json(["x"], timeout=1, label="x")
    assert payload == {}
    assert "non-dict" in err

    monkeypatch.setattr(_proc.subprocess, "run", _run(0, stdout='{"a": 1}'))
    payload_l, err_l = _proc.run_json(["x"], list_shape=True, timeout=1, label="x")
    assert payload_l == []
    assert "non-list" in err_l


def test_run_json_degrades_a_spawn_failure(monkeypatch) -> None:
    def _boom(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        raise OSError("gh missing")

    monkeypatch.setattr(_proc.subprocess, "run", _boom)
    payload, err = _proc.run_json(["gh"], timeout=1, label="gh api x")
    assert payload == {}
    assert "gh api x failed" in err
    assert "gh missing" in err
