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


class _Proc:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


@pytest.fixture
def fake_run(monkeypatch: pytest.MonkeyPatch):
    """Replace the ONE subprocess call so the gate's own logic is what is tested."""

    def _install(proc: object) -> list[tuple[str, ...]]:
        seen: list[tuple[str, ...]] = []

        def _fake(argv: Sequence[str], **_kwargs: object) -> object:
            seen.append(tuple(argv))
            if isinstance(proc, BaseException):
                raise proc
            return proc

        monkeypatch.setattr(subprocess, "run", _fake)
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
    assert seen == [("mise", "exec", "--", "hk", "test")]


def test_timeout_is_not_run_not_findings(tmp_path: Path, fake_run) -> None:
    fake_run(subprocess.TimeoutExpired(cmd="hk", timeout=1))
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
