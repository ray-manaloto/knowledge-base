# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.hk_test` — the gate over hk's step-defined tests.

The interesting assertions are the FAIL directions. This gate exists because
`hk test` exits 0 when it runs nothing, so the test that matters most is the one
proving a zero-test run is refused rather than passed.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from kb_setup import hk_test
from kb_setup.result import Err, Ok, Rc


def _tap(passed: int, failed: int = 0) -> str:
    lines = [f"ok - step :: case {i} (5ms)" for i in range(passed)]
    lines += [f"not ok - step :: bad {i} (5ms)" for i in range(failed)]
    return "\n".join(lines) + "\n"


class _Pipe:
    """A closeable stand-in for one of `Popen`'s pipe streams."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _Proc:
    """A stand-in for `Popen`.

    `communicate` is where a hang surfaces, so a `TimeoutExpired` handed here is
    raised from THERE rather than from construction — which is the difference
    between exercising the timeout branch and exercising the could-not-start one.
    """

    def __init__(
        self,
        stdout: str,
        returncode: int = 0,
        stderr: str = "",
        raises: BaseException | None = None,
    ) -> None:
        self.out_text = stdout
        self.err_text = stderr
        #: Real closeable stand-ins, because `run` no longer uses `Popen` as a
        #: context manager and closes these itself. A fake whose `stdout` was a
        #: plain string passed while the `with` did the closing, and broke the
        #: moment the code took that job over — so these track `closed` and the
        #: test below asserts it.
        self.stdout = _Pipe()
        self.stderr = _Pipe()
        self.returncode = returncode
        self._raises = raises
        #: Deliberately invalid. Nothing in these tests may reach a real process
        #: group — `os.killpg` is monkeypatched, and this is the second layer.
        self.pid = -1
        self.killed = False
        #: The bounds the gate actually passed. Recorded rather than ignored so a
        #: test can assert the timeout was applied at all — a fake that silently
        #: accepted and dropped it would let an unbounded call pass every test.
        self.communicate_timeout: float | None = None
        self.wait_timeout: float | None = None

    # No `__enter__`/`__exit__`: `run` deliberately does NOT use `Popen` as a
    # context manager, because `__exit__` calls `wait()` unbounded. Leaving them
    # here would let a regression back to `with` keep passing these tests.

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        self.communicate_timeout = timeout
        if self._raises is not None:
            raise self._raises
        return self.out_text, self.err_text

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeout = timeout
        return self.returncode


class _Spawn:
    """What the fixture records: the argv AND the kwargs of each spawn."""

    def __init__(self) -> None:
        self.argv: list[tuple[str, ...]] = []
        self.kwargs: list[dict[str, object]] = []


@pytest.fixture
def fake_run(monkeypatch: pytest.MonkeyPatch):
    """Replace the ONE subprocess call so the gate's own logic is what is tested.

    `os.killpg` is replaced too, and not as an afterthought: the gate now kills a
    process GROUP on timeout, and a test that let that call through would be one
    bad pid away from killing the test runner.
    """

    def _install(proc: object) -> _Spawn:
        seen = _Spawn()

        def _fake(argv: Sequence[str], **kwargs: object) -> object:
            seen.argv.append(tuple(argv))
            seen.kwargs.append(kwargs)
            if isinstance(proc, BaseException):
                raise proc
            return proc

        monkeypatch.setattr(subprocess, "Popen", _fake)
        monkeypatch.setattr(hk_test.os, "killpg", lambda *_a: None)
        monkeypatch.setattr(hk_test.os, "getpgid", lambda _pid: 4242)
        return seen

    return _install


def test_all_passing_is_ok(tmp_path: Path, fake_run) -> None:
    fake_run(_Proc(_tap(46)))
    result = hk_test.run(tmp_path)
    assert isinstance(result, Ok)
    assert result.value == 46


def test_zero_tests_is_refused_not_passed(tmp_path: Path, fake_run) -> None:
    """THE point of this module: hk exits 0 having run nothing; we must not.

    Measured on hk 1.56.0 — `hk test --name definitely-no-such-test` returns
    rc=0 with no output. A bare `run = "hk test"` gate would report green.
    """
    fake_run(_Proc("", returncode=0))
    result = hk_test.run(tmp_path)
    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN


def test_below_floor_is_refused_even_though_every_test_passed(tmp_path: Path, fake_run) -> None:
    """A partially-collapsed config is the realistic break, not an empty one.

    One builtin swapped for a custom Step drops its tests without emptying the
    suite, so the count falls but stays non-zero and hk still exits 0.
    """
    fake_run(_Proc(_tap(hk_test._MIN_TESTS - 1), returncode=0))
    result = hk_test.run(tmp_path)
    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN


def test_exactly_at_the_floor_passes(tmp_path: Path, fake_run) -> None:
    """The boundary is inclusive — pins which side of `<` the floor sits on."""
    fake_run(_Proc(_tap(hk_test._MIN_TESTS), returncode=0))
    assert isinstance(hk_test.run(tmp_path), Ok)


def test_a_failing_test_is_findings_not_not_run(tmp_path: Path, fake_run) -> None:
    """A real failure and a never-ran must not collapse to one code."""
    fake_run(_Proc(_tap(45, failed=1), returncode=1))
    result = hk_test.run(tmp_path)
    assert isinstance(result, Err)
    assert result.rc is Rc.FINDINGS


def test_floor_is_checked_before_the_exit_code(tmp_path: Path, fake_run) -> None:
    """Ordering is the whole design: rc=0 must not rescue a zero-test run.

    If the exit code were read first, this case returns Ok and the gate is a
    no-op. Asserting NOT_RUN here is what pins the order.
    """
    fake_run(_Proc("", returncode=0))
    result = hk_test.run(tmp_path)
    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN


def test_it_invokes_through_mise_exec_not_a_bare_hk(tmp_path: Path, fake_run) -> None:
    """The stale-PATH skew is live on this machine; a bare `hk` runs the OLD one."""
    seen = fake_run(_Proc(_tap(46)))
    hk_test.run(tmp_path)
    assert seen.argv == [("mise", "exec", "--", "hk", "test")]


def test_timeout_is_not_run_not_findings(tmp_path: Path, fake_run) -> None:
    fake_run(_Proc("", raises=subprocess.TimeoutExpired(cmd="hk", timeout=1)))
    result = hk_test.run(tmp_path)
    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN


def test_timeout_prints_the_partial_output_it_captured(
    tmp_path: Path, fake_run, capsys: pytest.CaptureFixture[str]
) -> None:
    """A hang is the one failure with nothing else to go on — do not discard it.

    Every other failure branch prints what hk said. The timeout branch used to
    drop `TimeoutExpired.stdout`/`.stderr` on the floor, so the run that most
    needed a diagnostic was the only one that produced none. (Cold lane, batch 1.)
    """
    exc = subprocess.TimeoutExpired(cmd="hk", timeout=1)
    exc.stdout = b"ok - step :: case 0 (5ms)\n"
    exc.stderr = b"hk: still waiting on gitleaks\n"
    fake_run(_Proc("", raises=exc))

    result = hk_test.run(tmp_path)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    printed = capsys.readouterr().out
    assert "ok - step :: case 0" in printed
    assert "still waiting on gitleaks" in printed


def test_timeout_kills_the_whole_process_group(
    tmp_path: Path, fake_run, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hk spawns the linters, so the wedged process is usually a GRANDCHILD.

    Killing hk alone leaves it running and holding the pipes, which is the defect
    this asserts against: the signal must go to the group.
    """
    fake_run(_Proc("", raises=subprocess.TimeoutExpired(cmd="hk", timeout=1)))
    # AFTER `fake_run`, which installs its own no-op `killpg`. Patching first
    # would be silently overwritten and this test would assert nothing — the
    # fixture-ordering shape of a test that cannot fail.
    killed: list[int] = []
    monkeypatch.setattr(hk_test.os, "killpg", lambda pgid, _sig: killed.append(pgid))

    hk_test.run(tmp_path)

    assert killed == [4242]


def test_it_spawns_in_its_own_session_or_the_group_kill_cannot_work(
    tmp_path: Path, fake_run
) -> None:
    """`start_new_session` is what MAKES the group above addressable.

    Without it hk shares our group and `killpg` would signal the test runner, so
    this pins the spawn flag rather than trusting the kill test alone.
    """
    seen = fake_run(_Proc(_tap(46)))
    hk_test.run(tmp_path)
    assert seen.kwargs[0]["start_new_session"] is True


def test_undecodable_output_is_not_run_not_a_crash(tmp_path: Path, fake_run) -> None:
    """`text=True` decodes inside `communicate`, so a bad byte raises from there.

    `gates.py` already handles this for `git status`; a sibling gate that does not
    is one non-UTF-8 linter message away from crashing where the other reports.
    """
    fake_run(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"))
    result = hk_test.run(tmp_path)
    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN


def test_missing_binary_is_not_run(tmp_path: Path, fake_run) -> None:
    fake_run(OSError("no mise here"))
    result = hk_test.run(tmp_path)
    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN


def test_counts_ignore_prose_between_the_tap_lines() -> None:
    """Hk prints its own chatter; only ok/not-ok lines may be counted."""
    noisy = "hk running tests\n" + _tap(3, failed=1) + "done in 12ms\n"
    assert hk_test._counts(noisy) == (3, 1)


def test_not_ok_is_not_miscounted_as_ok() -> None:
    """`not ok - ` contains no `ok - ` prefix at position 0, but check anyway.

    A naive `"ok - " in line` would count every failure as a pass, which is the
    single most damaging parse bug this module could have.
    """
    assert hk_test._counts("not ok - step :: bad (1ms)\n") == (0, 1)


def test_the_pipes_are_closed_even_on_the_happy_path(tmp_path: Path, fake_run) -> None:
    """`run` dropped the `with`, so closing the FDs became ITS job.

    `Popen.__exit__` used to do this. It was removed because it also calls
    `wait()` with no timeout, which would reintroduce an unbounded wait on the
    way out of a path built to bound one (graphify-labs, PR #406). Taking over
    the close without taking over the cleanup would leak two FDs per gate run —
    a slow leak, which is the kind nothing notices.
    """
    proc = _Proc(_tap(46))
    fake_run(proc)

    hk_test.run(tmp_path)

    assert proc.stdout.closed
    assert proc.stderr.closed


def test_the_pipes_are_closed_on_the_timeout_path_too(tmp_path: Path, fake_run) -> None:
    """The control arm: the leak would otherwise survive on the branch that hangs."""
    proc = _Proc("", raises=subprocess.TimeoutExpired(cmd="hk", timeout=1))
    fake_run(proc)

    hk_test.run(tmp_path)

    assert proc.stdout.closed
    assert proc.stderr.closed
