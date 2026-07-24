"""The shared `subprocess.run → degrade, don't raise` shape the currency engine repeats.

Every currency probe (`gh api`, `mise outdated`, `mise where`, …) shares one
contract: an unreachable tool must read as an *error string*, never a crash, so
one down upstream never aborts the whole run. That contract was hand-inlined at
each call site — the same try/except/returncode/`json.loads` block, near
verbatim, drifting apart in its error wording and its wrong-shape handling (some
sites silently coerced a wrong-shaped payload to empty; others reported it). This
module makes the contract one implementation so it cannot drift again.

`manifest.resolve_tag` is deliberately NOT a caller: it runs with `check=True`
and RAISES `RuntimeError` on failure (its caller `apply()` catches that), the
opposite of the degrade-to-a-string contract here — folding it in would force
this helper to grow a third return shape, the very divergence it exists to remove.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal, overload


def run_capture(
    cmd: list[str], *, cwd: Path | None = None, timeout: float
) -> tuple[subprocess.CompletedProcess[str] | None, str]:
    """Run `cmd`, capturing text output, as (completed_process, error).

    A spawn failure (`OSError`) or timeout degrades to `(None, "<reason>")`
    instead of raising: a currency probe treats an unreachable tool as a status,
    not an exception, so the engine keeps running when one tool is missing.
    """
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=False, cwd=cwd, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    return proc, ""


@overload
def run_json(
    cmd: list[str],
    *,
    list_shape: Literal[False] = ...,
    cwd: Path | None = ...,
    timeout: float,
    label: str,
) -> tuple[dict[str, object], str]: ...


@overload
def run_json(
    cmd: list[str],
    *,
    list_shape: Literal[True],
    cwd: Path | None = ...,
    timeout: float,
    label: str,
) -> tuple[list[object], str]: ...


def run_json(
    cmd: list[str],
    *,
    list_shape: bool = False,
    cwd: Path | None = None,
    timeout: float,
    label: str,
) -> tuple[dict[str, object] | list[object], str]:
    """Run `cmd` and parse stdout as JSON of the expected shape, as (payload, error).

    On ANY failure — spawn, non-zero exit, non-JSON, or a JSON value of the wrong
    shape — returns the empty container of the expected shape plus a human error
    keyed by `label`. Never raises and never returns a half-parsed value: a list
    arriving where a dict was expected reads as empty+error, so it cannot be
    mistaken for real data (the absence-of-evidence trap this engine is built to
    avoid). `label` names the command in every message (e.g. "gh api repos/x/…").
    """
    empty: dict[str, object] | list[object] = [] if list_shape else {}
    proc, spawn_err = run_capture(cmd, cwd=cwd, timeout=timeout)
    if proc is None:
        return empty, f"{label} failed: {spawn_err}"
    if proc.returncode != 0:
        detail = proc.stderr.strip()[:200] or f"exit {proc.returncode}"
        return empty, f"{label} exited {proc.returncode}: {detail}"
    try:
        payload = json.loads(proc.stdout or ("[]" if list_shape else "{}"))
    except json.JSONDecodeError as e:
        return empty, f"{label} returned non-JSON: {e}"
    expected: type = list if list_shape else dict
    if not isinstance(payload, expected):
        return empty, f"{label} returned a non-{expected.__name__}"
    return payload, ""
