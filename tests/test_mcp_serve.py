# Copyright (c) 2026 Raymond Manaloto
"""`mise run kb-serve` must actually answer MCP — not merely exit 0.

The defect these pin down (2026-08-02) was invisible for exactly the reason it
was expensive: `mise run` reads a task's stdio BY LINE rather than connecting it,
so this repo's stdio MCP server hit EOF on its first read and exited **rc=0 with
empty stderr**. Every check the repo had asks whether the task is *defined*; a
task that exits 0 passes all of them. `kb-serve` is the path `CLAUDE.md`,
`research-doc-sources.md` and `mise-tasks-only.md` all send consumers down, and
it served nothing at all.

So the load-bearing test here is not "the task is declared `raw = true`". That
would be two files agreeing with each other — `currency`'s `extra_probes` lesson
in miniature: a config asserting a thing is not the thing working. The only arm
that can fail for the real reason is a live JSON-RPC handshake.

AND THE PROBE IS ARMED BEFORE IT IS BELIEVED. `test_probe_*` run first against
fake servers whose behaviour is known, because an integration test proving
"kb-serve answers" is worthless if the probe reports success for a corpse. The
rc=0 arm is the one that matters: it reproduces the exact real failure, so a
probe that cannot tell it from a healthy server would have certified the bug.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import cast

import pytest
from kb_setup import evals, mcp_probe
from kb_setup.evals import CpuBound
from test_cpu_bounded import _Throttle

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The live arm is bounded by the server group's CPU WORK, not wall clock (#748,
#: after #838). Its 120 s wall bound failed at load 47-57 while the same test
#: passed alone in 28.9-35.0 s, so the bound measured the host. A server that
#: wedges (no CPU progress for a minute) or burns past this budget still fails.
#: The budget is set against measured cost; see the evidence report.
LIVE_CPU_BUDGET_S = 180.0

#: A responsive stdio MCP server. Deliberately minimal and deliberately NOT
#: graphify: it exists to prove the probe can read a success, so it must not be
#: able to fail for any of graphify's reasons.
_FAKE_SERVER = """
import json, sys
TOOLS = [{"name": "alpha", "inputSchema": {"type": "object"}},
         {"name": "beta", "inputSchema": {"type": "object"}}]
RESOURCES = [{"uri": "fake://one"}]
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    mid = msg.get("id")
    if mid is None:
        continue
    if msg["method"] == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {},
                  "serverInfo": {"name": "fake", "version": "1"}}
    elif msg["method"] == "tools/list":
        result = {"tools": TOOLS}
    elif msg["method"] == "resources/list":
        result = {"resources": RESOURCES}
    else:
        result = {}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\\n")
    sys.stdout.flush()
"""

#: The REAL failure, reproduced: exit 0 without reading or writing anything. This
#: is byte-for-byte what `mise run kb-serve` did before `raw = true` — which is
#: why it is the control arm and not a hypothetical.
_FAKE_CLEAN_EXIT = "import sys; sys.exit(0)\n"

#: A server that accepts input and never answers. Distinct from the above on
#: purpose: "exited" and "wedged" need opposite responses, so the probe must not
#: collapse them, and it must not hang on this one.
_FAKE_SILENT = """
import sys, time
for line in sys.stdin:
    pass
time.sleep(60)
"""


def _script(tmp_path: Path, name: str, body: str) -> list[str]:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return [sys.executable, str(path)]


# --------------------------------------------------------------------------
# Arm the probe. Nothing below this block is evidence until these pass.
# --------------------------------------------------------------------------


def test_probe_reads_a_healthy_server(tmp_path):
    """POSITIVE ARM: a server that answers is reported as answering."""
    result = mcp_probe.probe(_script(tmp_path, "ok.py", _FAKE_SERVER), timeout=30)

    assert result.initialized is True
    assert result.detail == ""
    assert result.tools == ("alpha", "beta")
    assert result.resources == ("fake://one",)
    # Not just non-zero: the count must match what the fake actually serialized,
    # or the field could be measuring the wrong object and still look plausible.
    assert result.tool_schema_bytes == len(
        json.dumps(
            [
                {"name": "alpha", "inputSchema": {"type": "object"}},
                {"name": "beta", "inputSchema": {"type": "object"}},
            ],
            separators=(",", ":"),
        ).encode()
    )


def test_probe_catches_a_clean_exit(tmp_path):
    """NEGATIVE ARM — the real bug: rc=0 with no reply must NOT read as success.

    If this test can be made to pass by a probe that ignores the exit, the whole
    file is decoration: `mise run kb-serve` failed in precisely this shape.
    """
    result = mcp_probe.probe(_script(tmp_path, "dead.py", _FAKE_CLEAN_EXIT), timeout=30)

    assert result.initialized is False
    assert result.tools == ()
    # The detail must say rc=0 out loud. "Exited cleanly" is the reading that
    # made this defect survive, so the message has to contradict it.
    assert "rc=0" in result.detail
    assert "NOT a served request" in result.detail


def test_probe_bounds_a_silent_server(tmp_path):
    """A server that reads and never answers times out rather than hanging."""
    result = mcp_probe.probe(_script(tmp_path, "mute.py", _FAKE_SILENT), timeout=3)

    assert result.initialized is False
    assert "timed out" in result.detail
    # Distinct from the exit case: conflating them would send a reader to the
    # wrong half of the problem.
    assert "rc=" not in result.detail


# --------------------------------------------------------------------------
# The live arm.
# --------------------------------------------------------------------------


@pytest.mark.xdist_group("real_graph")  # #838 — see [tasks.test] in mise.toml
def test_kb_serve_actually_answers_mcp():
    """`mise run kb-serve` completes a real MCP handshake and advertises tools.

    Realistic mutation: delete `raw = true` from `[tasks.kb-serve]` and this
    fails with the rc=0 detail above. Deleting the line IS the regression — that
    is the state `main` was in — so no more contrived break is needed.
    """
    graph = REPO_ROOT / "graphify-out" / "graph.json"
    if not graph.is_file():
        pytest.skip(
            f"no graph at {graph} — `mise run kb-build` first. This arm needs the "
            f"real graph the task pins; it is NOT a pass."
        )

    result = _live_probe()

    assert result.initialized is True, result.detail
    # graphify 0.9.31/0.9.32 both advertise 10 tools + 6 resources. Asserted as a
    # floor, not an equality: a graphify bump that ADDS a tool is not a failure of
    # this task, while a drop to zero is exactly the silence being guarded.
    assert len(result.tools) >= 1, result.detail
    assert "query_graph" in result.tools
    assert result.tool_schema_bytes > 0


def _live_probe() -> mcp_probe.Advertised:
    """The live arm's one probe call, so its bound can be pinned without a graph."""
    return mcp_probe.probe(
        ["mise", "run", "kb-serve"], cwd=REPO_ROOT, bound=CpuBound(LIVE_CPU_BUDGET_S)
    )


def test_the_live_arm_is_bounded_by_cpu_not_wall_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """#748 wiring: the kb-serve arm must use the CPU bound, never `timeout`."""
    seen: dict[str, object] = {}

    def fake(cmd: object, **kwargs: object) -> mcp_probe.Advertised:
        seen.update(kwargs, cmd=cmd)
        return mcp_probe.Advertised(
            initialized=True,
            tools=("query_graph",),
            resources=(),
            tool_schema_bytes=1,
            elapsed_s=0.0,
            detail="",
        )

    monkeypatch.setattr(mcp_probe, "probe", fake)
    _live_probe()
    assert seen.get("bound") == CpuBound(LIVE_CPU_BUDGET_S)
    assert "timeout" not in seen


# --------------------------------------------------------------------------
# The CPU bound on the probe (#748). Fake servers, so no graph is needed.
# --------------------------------------------------------------------------

#: Reads `initialize`, then works for a fixed amount of CPU before answering.
#: Starved by the throttle, it is the kb-serve failure in miniature: slow on the
#: wall clock, healthy in fact.
_FAKE_SLOW_WORKER = """
import json, sys, time
line = sys.stdin.readline()
mid = json.loads(line)["id"]
while time.process_time() < 1.5:
    pass
reply = {"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": "2024-11-05"}}
sys.stdout.write(json.dumps(reply) + "\\n")
sys.stdout.flush()
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("id") is not None:
        result = {"tools": []} if msg["method"] == "tools/list" else {"resources": []}
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}) + "\\n")
        sys.stdout.flush()
"""

#: Never answers and never computes: a wedge.
_FAKE_WEDGED = "import sys, time\nsys.stdin.readline()\ntime.sleep(60)\n"

#: Never answers and spins: a runaway.
_FAKE_RUNAWAY = "import sys\nsys.stdin.readline()\nwhile True: pass\n"

#: Exits cleanly, after a delay, without answering. The zombie guard must
#: report the rc=0 exit, not a stall.
_FAKE_LATE_CLEAN_EXIT = "import sys, time\nsys.stdin.readline()\ntime.sleep(1.2)\n"


def test_a_wedged_server_fails_as_stalled_under_the_cpu_bound(tmp_path):
    started = time.monotonic()
    result = mcp_probe.probe(
        _script(tmp_path, "wedged.py", _FAKE_WEDGED),
        bound=CpuBound(30, stall_window=1, min_progress=0.2),
    )
    assert result.initialized is False
    assert "stalled" in result.detail, result.detail
    assert time.monotonic() - started < 15


def test_a_runaway_server_fails_on_its_cpu_budget(tmp_path):
    result = mcp_probe.probe(
        _script(tmp_path, "runaway.py", _FAKE_RUNAWAY),
        bound=CpuBound(1.5, stall_window=1, min_progress=0.1),
    )
    assert result.initialized is False
    assert "exceeded CPU budget" in result.detail, result.detail


def test_a_clean_exit_is_not_misread_as_a_stall(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """The #838 zombie guard, reached through the probe with a slow `ps`."""
    real = evals.group_cpu_seconds

    def slow_ps(pgid: int) -> float | None:
        time.sleep(0.5)
        return real(pgid)

    monkeypatch.setattr(evals, "group_cpu_seconds", slow_ps)
    result = mcp_probe.probe(
        _script(tmp_path, "late-exit.py", _FAKE_LATE_CLEAN_EXIT),
        bound=CpuBound(30, stall_window=0.5, min_progress=0.05),
    )
    assert result.initialized is False
    assert "rc=0" in result.detail, result.detail


def test_a_starved_server_answers_where_the_wall_bound_fails(tmp_path):
    """#748 reproduced in miniature, with SIGSTOP starvation, as in #838."""
    marker = f"kb748-{uuid.uuid4().hex}"
    argv = [*_script(tmp_path, "slow.py", _FAKE_SLOW_WORKER), marker]
    with _Throttle(marker, duty=0.25):
        walled = mcp_probe.probe(argv, timeout=3)
    assert walled.initialized is False, "control: the wall bound must fail the starved server"
    assert "timed out" in walled.detail

    with _Throttle(marker, duty=0.25):
        bounded = mcp_probe.probe(argv, bound=CpuBound(30, stall_window=1, min_progress=0.05))
    assert bounded.initialized is True, bounded.detail


# --------------------------------------------------------------------------
# Cold-lane round 1. Each of these FAILED before its fix.
# --------------------------------------------------------------------------

#: A server that answers `initialize` with a JSON-RPC ERROR. The reply carries
#: the id the probe is waiting on, which is exactly why matching on the id alone
#: accepted it as a successful handshake.
_FAKE_REFUSES_INIT = """
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    if msg.get("id") is None:
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"],
                                 "error": {"code": -32600, "message": "nope"}}) + "\\n")
    sys.stdout.flush()
"""

#: Answers `initialize` and `tools/list`, then goes silent. `resources/list`
#: never comes back — which used to render as a server advertising 0 resources.
_FAKE_DROPS_RESOURCES = """
import json, sys, time
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    mid = msg.get("id")
    if mid is None:
        continue
    if msg["method"] == "resources/list":
        time.sleep(60)
        continue
    result = ({"tools": [{"name": "only", "inputSchema": {"type": "object"}}]}
              if msg["method"] == "tools/list" else {"protocolVersion": "2024-11-05"})
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\\n")
    sys.stdout.flush()
"""


def test_an_error_reply_is_not_a_handshake(tmp_path):
    """A server REFUSING to initialize must not be certified as initialized.

    `await_id` matches on the id alone, and a refusal answers with that same id.
    Before the fix this returned `initialized=True` — so the live gate would have
    passed against a server that said no.
    """
    result = mcp_probe.probe(_script(tmp_path, "refuse.py", _FAKE_REFUSES_INIT), timeout=30)

    assert result.initialized is False
    assert "refused initialize" in result.detail
    assert "nope" in result.detail


def test_a_reply_with_neither_result_nor_error_is_refused(tmp_path):
    """A protocol-violating reply is a refusal, not an empty surface."""
    body = _FAKE_REFUSES_INIT.replace(
        '"error": {"code": -32600, "message": "nope"}', '"jsonrpc2": "bogus"'
    )
    result = mcp_probe.probe(_script(tmp_path, "weird.py", body), timeout=30)

    assert result.initialized is False
    assert "neither result nor error" in result.detail


def test_a_dropped_resources_list_is_not_zero_resources(tmp_path):
    """A resources/list that never answers must say so, not report 0 resources.

    The detail for that half used to be discarded outright, which is the exact
    "answered no" / "never asked" collapse `Advertised`'s docstring promises not
    to make.
    """
    result = mcp_probe.probe(_script(tmp_path, "drop.py", _FAKE_DROPS_RESOURCES), timeout=4)

    assert result.initialized is True
    # The half that worked still reports its answer.
    assert result.tools == ("only",)
    # The half that did not is NAMED, and named as the resources half.
    assert result.resources == ()
    assert "resources/list" in result.detail
    assert "tools/list" not in result.detail


# --------------------------------------------------------------------------
# Cold-lane round 2. Three of the four were prose asserting what code did not do.
# --------------------------------------------------------------------------

#: Negotiates a version this probe did not ask for.
_FAKE_OTHER_VERSION = _FAKE_SERVER.replace('"2024-11-05"', '"1999-01-01"')

#: Answers `initialize` fine, then returns a JSON-RPC ERROR for `tools/list`.
#: The reply IS a message, so "did it arrive" said yes and the surface read as
#: an honest zero.
_FAKE_ERRORS_ON_TOOLS = """
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    mid = msg.get("id")
    if mid is None:
        continue
    if msg["method"] == "tools/list":
        body = {"error": {"code": -32000, "message": "tools exploded"}}
    else:
        body = {"result": {"protocolVersion": "2024-11-05"}}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, **body}) + "\\n")
    sys.stdout.flush()
"""

#: A wrapper that spawns a grandchild and then waits. Models `mise run kb-serve`,
#: where the `Popen` is mise and the real server is one level further down.
_FAKE_WRAPPER = """
import subprocess, sys
child = subprocess.Popen([sys.executable, sys.argv[1]],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
sys.stderr.write(str(child.pid) + "\\n"); sys.stderr.flush()
child.wait()
"""

#: A grandchild that DOES NOT READ STDIN and simply sleeps.
#:
#: Both properties are the fixture's control arm, and the first version had
#: neither. It reused the stdin-reading fake server, so when the wrapper died the
#: grandchild hit EOF and exited ON ITS OWN — the test passed with the group
#: signalling removed, which makes it a tautology rather than a check
#: (`probes-need-a-control-arm.md` rule 8: could this setup have produced the
#: other result?). Reading no stdin means only a delivered signal can end it.
_FAKE_SLEEPER = "import time\ntime.sleep(120)\n"


def test_a_negotiated_version_mismatch_is_reported(tmp_path):
    """PROTOCOL_VERSION's docstring promised this; nothing checked it.

    Not a handshake failure — a server may legitimately negotiate down — but the
    result must carry the version it actually got.
    """
    result = mcp_probe.probe(_script(tmp_path, "ver.py", _FAKE_OTHER_VERSION), timeout=30)

    assert result.initialized is True
    assert "1999-01-01" in result.detail
    assert mcp_probe.PROTOCOL_VERSION in result.detail


def test_the_matching_version_adds_no_note(tmp_path):
    """CONTROL ARM: agreement must stay silent, or every result carries noise."""
    result = mcp_probe.probe(_script(tmp_path, "ok.py", _FAKE_SERVER), timeout=30)

    assert result.initialized is True
    assert result.detail == ""


def test_an_error_on_tools_list_is_not_an_empty_tool_set(tmp_path):
    """An error reply ARRIVED, so "did it arrive" said yes and the count read 0.

    The second door into the same collapse round 1 closed: `_list_failures` only
    looked for a missing message, and an error is a message.
    """
    result = mcp_probe.probe(_script(tmp_path, "err.py", _FAKE_ERRORS_ON_TOOLS), timeout=30)

    assert result.initialized is True
    assert result.tools == ()
    assert "tools/list" in result.detail
    assert "tools exploded" in result.detail


def test_shutdown_reaps_a_grandchild(tmp_path):
    """The server is a GRANDCHILD under `mise run`, and it must still be reaped.

    Signalling only the top-level pid left `graphify-mcp` — holding a 393 MB
    graph — alive and reparented. This session hit that for real.
    """
    server = tmp_path / "stubborn.py"
    server.write_text(_FAKE_SLEEPER, encoding="utf-8")
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(_FAKE_WRAPPER, encoding="utf-8")
    marker = tmp_path / "pid.txt"

    proc = subprocess.Popen(
        [sys.executable, str(wrapper), str(server)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=marker.open("w"),
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    # Let the wrapper report its grandchild's pid.
    for _ in range(100):
        if marker.read_text().strip():
            break
        time.sleep(0.05)
    grandchild = int(marker.read_text().strip())

    mcp_probe._shutdown(proc)

    # The grandchild must be gone. `kill(pid, 0)` raises once it is reaped; a
    # surviving SIGTERM-ignoring process would answer happily.
    for _ in range(100):
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    os.kill(grandchild, signal.SIGKILL)
    pytest.fail(f"grandchild {grandchild} survived _shutdown — it was orphaned, not reaped")


class _UnreapedProc:
    """A child that has hit EOF on stdout but is NOT yet reaped.

    `poll()` returns None until someone `wait()`s — which is exactly what the
    OS does in the window between stdout closing and the process being reaped.
    Reproducing that window deterministically is the whole point: the real
    failure only appears on a loaded host, so waiting for load is not a test.
    """

    def __init__(self, rc: int) -> None:
        self._rc = rc
        self.polls = 0
        self.waits = 0
        self.timeout_seen: float | None = None

    def poll(self) -> int | None:
        self.polls += 1
        return None

    def wait(self, timeout: float | None = None) -> int:
        self.waits += 1
        self.timeout_seen = timeout
        return self._rc


class _WedgedProc(_UnreapedProc):
    """A child that closed stdout and will never be reaped — must not hang."""

    def wait(self, timeout: float | None = None) -> int:
        self.waits += 1
        self.timeout_seen = timeout
        raise subprocess.TimeoutExpired(cmd="server", timeout=timeout or 0)


def _session_over(proc: object) -> mcp_probe._Session:
    """A `_Session` bound to a stub process, bypassing the pipe wiring.

    The `cast` is the point of the helper, not an escape from it: every stub
    above implements only the handful of `Popen` members `_Session` actually
    touches (`wait`, `poll`, `kill`, `stdout`), which is what makes these tests
    able to reproduce a wedged or unreaped child at all. ty 0.0.69 began
    flagging the bare assignment; a `cast` states the substitution in code
    rather than hiding it behind a suppression, which this repo forbids
    (`do-not.md` #9).
    """
    session = mcp_probe._Session.__new__(mcp_probe._Session)
    session._proc = cast("subprocess.Popen[str]", proc)
    return session


def test_an_unreaped_clean_exit_still_reports_rc_zero():
    """The race that failed this module's own test under load.

    EOF on stdout precedes reaping, so a bare `poll()` returns None and the
    `rc=0` sentence — the one this function exists to produce — is skipped in
    favour of the LESS informative `rc=None`.
    """
    proc = _UnreapedProc(0)
    detail = _session_over(proc)._exit_detail(1)
    assert "rc=0" in detail
    assert "rc=None" not in detail
    assert proc.waits == 1, "poll() returned None and nothing waited for the child"
    assert proc.timeout_seen == mcp_probe._REAP_TIMEOUT_S, "the wait must be BOUNDED"


def test_an_unreaped_nonzero_exit_reports_its_real_code():
    """The MIRROR: waiting must not launder a real non-zero rc into 0."""
    detail = _session_over(_UnreapedProc(3))._exit_detail(1)
    assert "rc=3" in detail
    assert "rc=0" not in detail


def test_a_child_that_never_reaps_is_bounded_not_hung():
    """A wedged child must fail with what we know, not block the probe forever."""
    proc = _WedgedProc(0)
    detail = _session_over(proc)._exit_detail(7)
    assert "rc=None" in detail
    assert "id=7" in detail
    assert proc.waits == 1
    assert proc.timeout_seen == mcp_probe._REAP_TIMEOUT_S
