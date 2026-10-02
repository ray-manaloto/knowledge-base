# Copyright (c) 2026 Raymond Manaloto
"""`evals.run_command_cpu_bounded`: bound the WORK, not the clock (#838).

The eval canary failed its 180 s wall bound on a host at load ~100 while the
query was fine. The replacement has to keep failing the two things a bound is
for, a runaway and a wedge, and stop failing a command that is merely starved.
Each property has its own arm below. The starvation arm is the one #838 needs:
it reproduces the failure with SIGSTOP/SIGCONT duty-cycling, which takes CPU
away from the command without burning any on the shared host.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Self

import pytest
from kb_setup import eval_cases, evals


def _py(code: str, marker: str = "") -> list[str]:
    return [sys.executable, "-c", code, marker]


def _spin(seconds: float) -> str:
    """A command doing ``seconds`` of CPU work, then printing ``done``."""
    return f"import time\nwhile time.process_time() < {seconds}:\n    pass\nprint('done')\n"


class _Throttle:
    """Give every process whose argv holds ``marker`` a ``duty`` share of time.

    SIGSTOP/SIGCONT on each matching pid, the same starvation a saturated run
    queue imposes, but deterministic, and it spends no CPU of its own.
    """

    def __init__(self, marker: str, duty: float, period: float = 0.5) -> None:
        self.marker, self.duty, self.period = marker, duty, period
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _pids(self) -> set[int]:
        out = subprocess.run(
            ["pgrep", "-f", self.marker], capture_output=True, text=True, check=False
        ).stdout
        return {int(pid) for pid in out.split()} - {os.getpid()}

    def _signal(self, pids: set[int], sig: signal.Signals) -> None:
        for pid in pids:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                continue

    def _run(self) -> None:
        while not self.stop.is_set():
            pids = self._pids()
            self._signal(pids, signal.SIGSTOP)
            time.sleep(self.period * (1 - self.duty))
            self._signal(pids, signal.SIGCONT)
            time.sleep(self.period * self.duty)

    def __enter__(self) -> Self:
        self.thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop.set()
        self.thread.join()
        self._signal(self._pids(), signal.SIGCONT)


def test_ps_seconds_parses_every_ps_time_shape() -> None:
    assert evals._ps_seconds("0:31.70") == pytest.approx(31.7)
    assert evals._ps_seconds("953:56.84") == pytest.approx(953 * 60 + 56.84)
    assert evals._ps_seconds("1:02:03.50") == pytest.approx(3723.5)
    assert evals._ps_seconds("2-01:00:00") == pytest.approx(2 * 86400 + 3600)


def test_a_group_with_no_live_process_is_could_not_ask_not_zero() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    proc.wait()
    assert evals.group_cpu_seconds(proc.pid) is None


def test_a_healthy_command_returns_its_output() -> None:
    rc, out = evals.run_command_cpu_bounded(
        _py(_spin(0.2)), bound=evals.CpuBound(30, stall_window=5)
    )
    assert (rc, out.strip()) == (0, "done")


def test_a_wedged_command_is_killed_as_stalled() -> None:
    """NEGATIVE ARM: 0% CPU is a hang, and still fails fast."""
    start = time.monotonic()
    rc, out = evals.run_command_cpu_bounded(
        _py("import time; time.sleep(60)"),
        bound=evals.CpuBound(30, stall_window=1, min_progress=0.2),
    )
    assert rc == -1
    assert "stalled" in out
    assert time.monotonic() - start < 10


def test_a_runaway_command_is_killed_on_its_cpu_budget() -> None:
    """NEGATIVE ARM: real slowness, more CPU than budgeted, still fails."""
    rc, out = evals.run_command_cpu_bounded(
        _py("while True: pass"), bound=evals.CpuBound(1.5, stall_window=1, min_progress=0.1)
    )
    assert rc == -1
    assert "exceeded CPU budget" in out


def test_a_descendants_cpu_counts_against_the_budget() -> None:
    """The budget covers the GROUP, not just the spawned pid.

    A per-pid sample (or `RLIMIT_CPU`) sees an idle parent and calls it
    stalled or under budget.
    """
    code = "import subprocess, sys\nsubprocess.run([sys.executable, '-c', 'while True: pass'])\n"
    rc, out = evals.run_command_cpu_bounded(
        _py(code), bound=evals.CpuBound(1.5, stall_window=1, min_progress=0.1)
    )
    assert rc == -1
    assert "exceeded CPU budget" in out, out


def test_an_exit_just_after_a_sample_is_not_a_stall(monkeypatch: pytest.MonkeyPatch) -> None:
    """Round-2 P1: an exit racing a slow `ps` must not become a false verdict.

    The command finishes just after a tick; a slowed `ps` then lists its
    ZOMBIE, which macOS shows at 0 CPU. Reading that as "no progress" called a
    successful run stalled, and the follow-up `killpg` raised EPERM. Every run
    must return the command's own rc and output.
    """
    real = evals.group_cpu_seconds

    def slow_ps(pgid: int) -> float | None:
        time.sleep(0.5)
        return real(pgid)

    monkeypatch.setattr(evals, "group_cpu_seconds", slow_ps)
    for _ in range(5):
        rc, out = evals.run_command_cpu_bounded(
            _py(_spin(0.6)), bound=evals.CpuBound(30, stall_window=0.5, min_progress=0.05)
        )
        assert (rc, out.strip()) == (0, "done"), out


def test_a_descendant_holding_the_pipe_cannot_wait_forever() -> None:
    """Round-2 P2-1: an escaped (setsid) descendant must not hang the reap."""
    code = (
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(8)'],"
        " start_new_session=True)\n"
        "print('parent done', flush=True)\n"
    )
    start = time.monotonic()
    rc, out = evals.run_command_cpu_bounded(
        _py(code), bound=evals.CpuBound(30, stall_window=1, min_progress=0.05)
    )
    assert time.monotonic() - start < 6
    assert rc == -1
    assert "kept its output open" in out


def test_a_starved_command_completes_where_a_wall_bound_fails() -> None:
    """#838 reproduced. 1.5 CPU-s of work, starved by the throttle, needs ~5 s of wall.

    The wall-clock bound the canary used fails it. The CPU bound lets it finish,
    because it keeps making progress.
    """
    marker = f"kb838-{uuid.uuid4().hex}"
    work = _py(_spin(1.5), marker)
    with _Throttle(marker, duty=0.25):
        wall_rc, _, wall_err = evals.run_command_split(work, timeout=3)
    assert wall_rc == -1, "control: the wall bound must fail the starved command"
    assert "timed out" in wall_err

    with _Throttle(marker, duty=0.25):
        rc, out = evals.run_command_cpu_bounded(
            work, bound=evals.CpuBound(30, stall_window=1, min_progress=0.05)
        )
    assert (rc, out.strip()) == (0, "done"), out


def test_the_graph_canary_is_cpu_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The case wiring: `tier1.graph-answers` must use the CPU bound."""
    graph = tmp_path / "graphify-out" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text("{}")
    case = next(c for c in eval_cases.cases(tmp_path) if c.name == "tier1.graph-answers")
    seen: list[dict[str, object]] = []

    def fake(_argv: object, **kwargs: object) -> tuple[int, str]:
        seen.append(kwargs)
        return 0, "NODE x"

    def wall(*_: object, **__: object) -> tuple[int, str]:
        pytest.fail("the canary took the wall-clock path")

    monkeypatch.setattr(evals, "run_command_cpu_bounded", fake)
    monkeypatch.setattr(evals, "run_command", wall)
    assert case.probe().verdict is evals.Verdict.PASS
    assert seen == [{"cwd": tmp_path, "bound": evals.CpuBound(eval_cases.CANARY_CPU_BUDGET)}]
