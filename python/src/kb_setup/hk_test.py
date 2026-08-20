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

import contextlib
import os
import signal
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

#: How long to wait for the process group to actually die after SIGKILL. Short on
#: purpose: SIGKILL is not catchable, so anything still here after this is a
#: zombie whose parent is us, and blocking the gate on it helps nobody.
_KILL_GRACE = 5

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


def _kill_group(proc: subprocess.Popen[str]) -> None:
    """Kill hk AND everything it spawned, then reap it.

    `Popen.kill()` signals the direct child only. hk's whole job is spawning
    linters, so the process that is actually wedged is usually a grandchild —
    killing hk alone leaves it running and holding the pipes. `start_new_session`
    at spawn time is what makes the group addressable here.

    Both calls are best-effort: the group is already gone if hk exited between the
    timeout firing and this call, and a gate must not raise on the way to
    reporting NOT_RUN.
    """
    try:
        # `ProcessLookupError` needs no separate arm — it is an OSError subclass,
        # which is also the case that gets here most often (hk exited between the
        # timeout firing and this call).
        #
        # The pgid is `proc.pid` BY CONSTRUCTION, not by lookup: `start_new_session`
        # makes hk its own group leader, so the group id equals its pid for the
        # lifetime of the group. Asking `getpgid` instead would fail exactly when
        # the leader has already exited — and that is the case where the group
        # still holds the WEDGED GRANDCHILDREN this function exists to kill, so
        # the lookup failing would drop us to a `proc.kill()` that reaps a dead
        # leader and leaves the linters running. (graphify-labs, PR #406.)
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        # Also suppressed: the fallback races the same exit the OSError above
        # usually means. If hk died between `getpgid` failing and this line,
        # `kill()` can raise in turn — and a gate that raised while cleaning up
        # after a timeout would report a crash instead of the timeout, turning a
        # bounded failure into an unbounded-looking one. (graphify-labs, PR #406.)
        with contextlib.suppress(OSError):
            proc.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=_KILL_GRACE)


def _close_pipes(proc: subprocess.Popen[str]) -> None:
    """Release the pipe FDs the context manager would otherwise have closed.

    Dropping the `with` (see `run`) means nothing closes these for us, and a
    leaked FD per gate run is a slow leak rather than a loud one. Best-effort:
    a close that raises must not become the reason the gate reports nothing.
    """
    for stream in (proc.stdout, proc.stderr):
        if stream is not None:
            with contextlib.suppress(OSError):
                stream.close()


def _decode(stream: str | bytes | None) -> str:
    """Whatever a stream turned out to be, as text that cannot raise.

    `TimeoutExpired.stdout` is typed loosely and is `bytes` even when the call
    asked for text, because the decode happens after `communicate` returns and a
    timeout never gets there. Callers want the partial output either way.
    """
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode("utf-8", errors="replace")
    return stream


def run(repo_root: Path) -> Result[int]:
    """Run the step tests; Ok(passed) only if they ran AND all of them passed."""
    try:
        # `start_new_session` puts hk in its own process GROUP, which is what
        # makes the timeout below able to kill the linters hk spawned rather than
        # only hk itself. Without it a wedged linter survives the timeout holding
        # the pipes open, and the gate returns while the hang continues.
        # Deliberately NOT used as a context manager. `Popen.__exit__` closes the
        # pipes and then calls `wait()` with NO timeout, so a process that
        # outlived `_kill_group`'s grace period would hand the gate an unbounded
        # wait on the way OUT of the `with` — reintroducing the hang this path
        # exists to bound, one frame later and somewhere nobody would look for it.
        # Every wait here is bounded instead. (graphify-labs, PR #406.)
        proc = subprocess.Popen(
            _ARGV,
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=_TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            _kill_group(proc)
            # Print what hk managed to say before it wedged. Every other
            # failure branch here prints its captured output; discarding it
            # exactly when the run hung would withhold the diagnostic at the
            # one moment there is nothing else to go on.
            partial = (_decode(exc.stdout) + _decode(exc.stderr)).rstrip()
            if partial:
                print(partial)
            return Err(f"hk test did not finish within {_TIMEOUT}s", Rc.NOT_RUN)
        except BaseException:
            # Ctrl-C, and this is a REGRESSION `start_new_session` introduced two
            # commits ago rather than a pre-existing gap. A terminal delivers
            # SIGINT to its FOREGROUND process group only, and the new session is
            # precisely what takes hk out of that group — so the interrupt that
            # used to kill hk along with the gate now reaches only us, and
            # unwinding without this would leave hk and every linter it spawned
            # running orphaned. The bare `except` re-raises immediately; it
            # suppresses nothing. (graphify-labs, PR #406.)
            _kill_group(proc)
            raise
        finally:
            _close_pipes(proc)
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError is neither of the other two — `text=True` decodes
        # inside `communicate`, so a byte sequence a linter emits verbatim that is
        # not UTF-8 would raise straight past a handler whose whole job is to
        # return NOT_RUN instead of raising. `gates.py:282` already handles this
        # for `git status`; a sibling gate diverging from it is how one surface
        # ends up able to crash where the other reports. (Cold lane, batch 1.)
        return Err(f"hk test could not run: {exc}", Rc.NOT_RUN)

    output = stdout + stderr
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
