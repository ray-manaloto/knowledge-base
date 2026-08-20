# Copyright (c) 2026 Raymond Manaloto
"""Run hk's step-defined tests as a gate, and refuse a run that tested nothing.

`hk test` executes the tests declared on each step. This repo's `hk.pkl` declares
none of its own, so every test here ships WITH a builtin — and they come in pairs
(`check bad file` beside `check good file`, `fix bad file` beside `fix good file`),
which is a control arm by construction: a linter that passes the good file and
FAILS the bad one has demonstrated it can produce both answers. A step verified
only on clean input has demonstrated nothing (`probes-need-a-control-arm.md`).

Why this is a module and not `run = "hk test"`
----------------------------------------------
Because a bare seam would inherit a hazard this repo refuses everywhere else.
Measured on hk 1.56.0:

    hk test --name definitely-no-such-test   ->  rc=0, no output

A filter that matches nothing is a SILENT PASS. Nothing about that is specific to
`--name`: the same rc=0 comes back if the config stops declaring testable steps at
all — a builtin swapped for a custom `Step`, a `Mapping` accidentally emptied, an
upstream release that stops shipping tests with its builtins. In every one of those
cases a bare `hk test` gate reports green having asked no question, which is the
exact DRIFT/SKIP/OK collapse `currency.toml` documents and `Rc.NOT_RUN` exists to
name.

So this module asserts a FLOOR: at least `_MIN_TESTS` tests must have actually run.
The floor is deliberately below the current count rather than equal to it — an
exact match would fail every time hk adds a test to a builtin, training people to
bump the number without reading why it moved, and a gate people edit reflexively is
not a gate. What it catches is the collapse, not the drift.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from kb_setup.result import Err, Ok, Rc, Result, exit_code

#: How the tests are invoked. `mise exec --` and NOT a bare `hk`, because the
#: stale-PATH skew on this machine is live and was reproduced again on 2026-08-19:
#: a bare `hk version` printed 1.55.0 while `mise exec -- hk version` printed
#: 1.56.0, with stale install dirs sitting ahead of the mise shims. A gate that
#: silently runs the PREVIOUS hk against the CURRENT config is worse than no gate.
_ARGV = ("mise", "exec", "--", "hk", "test")

#: Wall-clock bound. The full suite runs in well under a second; this exists only
#: so a wedged linter cannot hang the gate indefinitely.
_TIMEOUT = 300

#: The floor. 40 against 46 observed on hk 1.56.0 — enough headroom that a builtin
#: dropping one or two tests upstream does not fail the gate, tight enough that the
#: collapse cases above (0 tests, or a config that stopped declaring steps) do.
#: Raise it only alongside a recorded measurement of what the new count IS.
_MIN_TESTS = 40

_OK_PREFIX = "ok - "
_FAIL_PREFIX = "not ok - "


def _counts(output: str) -> tuple[int, int]:
    """Return (passed, failed) from hk test's TAP-style lines.

    `hk test --json` was probed and does NOT emit JSON — it emits the same
    `ok - <step> :: <name> (<ms>)` lines as the default mode, so there is no
    structured form to prefer here and parsing the text is the only option
    rather than a shortcut past one.
    """
    passed = failed = 0
    for raw in output.splitlines():
        line = raw.strip()
        if line.startswith(_FAIL_PREFIX):
            failed += 1
        elif line.startswith(_OK_PREFIX):
            passed += 1
    return passed, failed


def _report(passed: int, failed: int) -> None:
    print(f"hk-test: {passed} passed, {failed} failed (floor {_MIN_TESTS})")


def run(repo_root: Path) -> Result[int]:
    """Run the step tests; Ok(passed) only if they ran AND all of them passed."""
    try:
        proc = subprocess.run(
            _ARGV,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return Err(f"hk test did not finish within {_TIMEOUT}s", Rc.NOT_RUN)
    except (OSError, subprocess.SubprocessError) as exc:
        return Err(f"hk test could not run: {exc}", Rc.NOT_RUN)

    output = proc.stdout + proc.stderr
    passed, failed = _counts(output)
    total = passed + failed

    # Order matters: the floor is checked BEFORE the exit code, because the whole
    # point is that hk's own rc cannot distinguish "all tests passed" from "there
    # were no tests". Reading rc first would let the collapse case return Ok.
    if total < _MIN_TESTS:
        print(output.rstrip())
        return Err(
            f"hk test ran {total} test(s), below the floor of {_MIN_TESTS} — "
            "the config may have stopped declaring testable steps. This is NOT a "
            "pass: a gate that asked no question has not answered it.",
            Rc.NOT_RUN,
        )

    if failed or proc.returncode != 0:
        print(output.rstrip())
        _report(passed, failed)
        return Err(f"hk test reported {failed} failing test(s)", Rc.FINDINGS)

    _report(passed, failed)
    return Ok(passed)


def hk_test_main(repo_root: Path) -> int:
    """CLI entry point: `uv run kb-setup hk-test`."""
    return exit_code(run(repo_root))
