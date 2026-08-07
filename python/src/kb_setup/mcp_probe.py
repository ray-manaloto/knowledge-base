# Copyright (c) 2026 Raymond Manaloto
"""Speak MCP over stdio to a server command and report what it actually advertises.

WHY THIS EXISTS. `mise run kb-serve` is the documented way every consumer reaches
this graph — `CLAUDE.md`, `research-doc-sources.md` and `mise-tasks-only.md` all
point at it — and it could not serve at all. `mise run` reads a task's stdio BY
LINE rather than connecting it, so the stdio MCP server hit EOF on its first read
and exited: rc=0, empty stderr, indistinguishable from a clean shutdown. The
mise builtin `raw = true` ("directly connect task to stdin/stdout/stderr") fixes
it, and this module is what proves the fix is live.

THE POINT IS THAT NOTHING ELSE COULD HAVE CAUGHT IT. Every check this repo had
asks whether the TASK is defined, not whether the SERVER answers — and a task
that exits 0 passes all of them. Asserting `raw = true` in `mise.toml` would be
two files agreeing with each other (`currency`'s `extra_probes` lesson: a config
that says a thing is not the thing working). The only honest arm is a real
JSON-RPC handshake, which is what :func:`probe` performs.

MEASURED, so the numbers below are re-derivable rather than inherited
(2026-08-02, graphify 0.9.31, mise 2026.8.0):

=======================================  ==============  ===================
arm                                      first reply     verdict
=======================================  ==============  ===================
``mise run kb-serve`` (before the fix)   none, exit 10.4s  cannot serve
``graphify-mcp graph-prose.json`` 3.4MB  0.6s              10 tools
``graphify-mcp graph.json`` 393MB        9.8s              10 tools
``mise run --raw kb-serve``              10.8s             10 tools
=======================================  ==============  ===================

The 3.4MB-vs-393MB pair prices the graph load at ~9.2s, which is why the broken
arm's 10.4s exit read as a slow start rather than a dead server. Any timeout
here must clear that load with room to spare — see :data:`DEFAULT_TIMEOUT_S`.

READING A FAILURE. :class:`Advertised` never collapses "answered no" into "never
asked" (`probes-need-a-control-arm.md`): `initialized` False with a `detail`
saying the process exited is a dead server, while an empty `tools` tuple on an
`initialized` True server is a server that answered and advertised nothing.
Those demand opposite fixes, so they are never merged into one boolean.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from queue import Empty, Queue
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path
    from typing import IO

#: Long enough to clear the ~9.2s aggregate-graph load measured above with a wide
#: margin, because a timeout that merely *usually* clears it turns a slow host
#: into a reported defect. Not unbounded: `long-running-command-hangs.md` — a
#: wedged server must fail, not hang.
DEFAULT_TIMEOUT_S = 120.0

#: The protocol version this probe negotiates. Pinned rather than "latest" so a
#: server-side bump shows up as a handshake failure we investigate, not as a
#: silent renegotiation.
PROTOCOL_VERSION = "2024-11-05"

_INITIALIZE_ID = 1
_TOOLS_ID = 2
_RESOURCES_ID = 3

#: How long `_exit_detail` waits for an already-EOF'd child to be REAPED before
#: giving up on naming its exit code. EOF on stdout precedes reaping, so a bare
#: `poll()` there legitimately returns None on a loaded host — and `rc=None` is
#: the LESS informative message, in the one function whose stated job is to say
#: `rc=0` out loud. Short, because the child has already closed stdout: this
#: waits on bookkeeping, not on work.
_REAP_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class Advertised:
    """What a server answered — with "never asked" kept distinct from "said no"."""

    initialized: bool
    tools: tuple[str, ...]
    resources: tuple[str, ...]
    tool_schema_bytes: int
    elapsed_s: float
    detail: str

    @property
    def line(self) -> str:
        """One-line report carrying both the counts and the timing."""
        if not self.initialized:
            return f"NO HANDSHAKE after {self.elapsed_s:.1f}s — {self.detail}"
        return (
            f"{len(self.tools)} tools ({self.tool_schema_bytes:,} B of schema), "
            f"{len(self.resources)} resources, first reply {self.elapsed_s:.1f}s"
        )


def _pump(stream: IO[str], sink: Queue[str | None]) -> None:
    """Relay a server's stdout lines into a queue, then post a sentinel on EOF.

    A reader thread rather than a bare ``readline``: the whole failure this
    module exists to detect is a server that never writes, and a blocking read
    on a live pipe cannot be given a deadline. The ``None`` sentinel is what
    distinguishes "the process ended" from "nothing yet".
    """
    for line in stream:
        sink.put(line)
    sink.put(None)


class _Session:
    """One stdio JSON-RPC conversation with a server subprocess."""

    def __init__(self, proc: subprocess.Popen[str], deadline: float) -> None:
        if proc.stdin is None or proc.stdout is None:
            raise ValueError("server subprocess must be started with piped stdin and stdout")
        self._proc = proc
        self._stdin: IO[str] = proc.stdin
        self._deadline = deadline
        self._lines: Queue[str | None] = Queue()
        self._eof = False
        threading.Thread(target=_pump, args=(proc.stdout, self._lines), daemon=True).start()

    def send(self, payload: dict[str, object]) -> bool:
        """Write one JSON-RPC frame. False if the server's stdin is already gone."""
        try:
            self._stdin.write(json.dumps(payload) + "\n")
            self._stdin.flush()
        except BrokenPipeError, ValueError:
            return False
        return True

    def await_id(self, want: int) -> tuple[dict[str, object] | None, str]:
        """Read until the reply with ``want`` arrives, the deadline passes, or EOF.

        Returns the message and an empty detail on success; ``None`` plus a
        detail naming WHICH of the three happened on failure. Non-matching and
        unparsable lines are skipped: a server is free to interleave
        notifications, and a stray non-JSON line is not an answer to this id.
        """
        while True:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                return None, f"timed out waiting for reply id={want}"
            if self._eof:
                return None, self._exit_detail(want)
            try:
                line = self._lines.get(timeout=min(remaining, 1.0))
            except Empty:
                continue
            if line is None:
                self._eof = True
                return None, self._exit_detail(want)
            try:
                message = json.loads(line)
            except TypeError, ValueError:
                continue
            if isinstance(message, dict) and message.get("id") == want:
                return message, ""

    def _exit_detail(self, want: int) -> str:
        """Why an EOF happened, in the terms a reader needs to act on.

        rc=0 is called out explicitly: that is exactly what the broken
        `mise run kb-serve` produced, and "exited cleanly" is the reading that
        made the defect invisible for as long as it existed.
        """
        rc = self._proc.poll()
        if rc is None:
            # We are here because stdout hit EOF, which happens BEFORE the child
            # is reaped — so `poll()` returning None is a race, not a running
            # server. Under load it fires often enough to have failed this
            # module's own test, and the failure mode is the bad direction:
            # `rc=None` instead of the `rc=0` sentence below. Bounded, because a
            # child that has closed stdout and still will not be reaped is a
            # wedge and must fail rather than hang.
            with contextlib.suppress(subprocess.TimeoutExpired):
                rc = self._proc.wait(timeout=_REAP_TIMEOUT_S)
        if rc == 0:
            return (
                f"server closed stdout and exited rc=0 before answering id={want} "
                f"— a clean exit is NOT a served request"
            )
        return f"server exited rc={rc} before answering id={want}"


def _result_list(message: dict[str, object] | None, key: str) -> list[dict[str, object]]:
    """The ``result[key]`` array from a JSON-RPC reply, or [] if it carries none."""
    if not isinstance(message, dict):
        return []
    result = message.get("result")
    if not isinstance(result, dict):
        return []
    items = result.get(key)
    if not isinstance(items, list):
        return []
    # Keys are re-stringified rather than trusted: this parses a foreign server's
    # JSON, so the shape is an assumption until it is enforced.
    return [{str(k): v for k, v in item.items()} for item in items if isinstance(item, dict)]


def probe(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Advertised:
    """Run ``cmd`` as a stdio MCP server and report the surface it advertises.

    The server is always terminated before returning, including on a timeout —
    an orphaned server holding a 393 MB graph is a worse outcome than the failure
    being diagnosed.

    Args:
        cmd: argv of the server, e.g. ``["mise", "run", "kb-serve"]``.
        cwd: working directory for the server, or the caller's.
        timeout: hard bound on the whole handshake.

    Returns:
        An :class:`Advertised` whose ``detail`` names the failure when there is
        one, and is empty when the handshake completed.
    """
    started = time.monotonic()
    deadline = started + timeout
    proc = subprocess.Popen(
        list(cmd),
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        # Its own process group, so :func:`_shutdown` can signal the whole tree.
        # REQUIRED, not incidental: without it the child shares OUR group, and
        # the `killpg` below would take down the caller — pytest included.
        start_new_session=True,
    )
    session = _Session(proc, deadline)
    try:
        return _handshake(session, started)
    finally:
        _shutdown(proc)


def _no_handshake(started: float, detail: str) -> Advertised:
    """The result shape for a server that never completed `initialize`.

    One constructor for all three ways that happens, so a new failure path cannot
    accidentally report zero tools on an `initialized=True` record — which would
    read as "answered, advertised nothing" and send a reader the wrong way.
    """
    return Advertised(
        initialized=False,
        tools=(),
        resources=(),
        tool_schema_bytes=0,
        elapsed_s=time.monotonic() - started,
        detail=detail,
    )


def _handshake(session: _Session, started: float) -> Advertised:
    """Drive initialize -> tools/list -> resources/list and score the result."""
    if not session.send(
        {
            "jsonrpc": "2.0",
            "id": _INITIALIZE_ID,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "kb-setup-mcp-probe", "version": "1"},
            },
        }
    ):
        return _no_handshake(started, "server stdin closed before initialize could be sent")

    init, detail = session.await_id(_INITIALIZE_ID)
    if init is None:
        return _no_handshake(started, detail)
    # A reply is not an agreement. `await_id` matches on the id alone, so a
    # server REFUSING to initialize answers with the very id we are waiting on —
    # and treating that as success would let this probe certify a server that
    # said no. That is the same class of mistake as reading rc=0 as "served".
    # (Cold lane, round 1.)
    if (refusal := _error_detail(init)) is not None:
        return _no_handshake(started, f"server refused initialize: {refusal}")
    # PROTOCOL_VERSION's docstring promises a server-side bump "shows up as a
    # handshake failure we investigate, not as a silent renegotiation", and until
    # now nothing checked — the promise lived only in the prose. A server may
    # legitimately negotiate down, so this does NOT fail the handshake; it names
    # the mismatch in `detail` so a probe result carries the version it actually
    # got. (Cold lane, round 2.)
    negotiated = _negotiated_version(init)
    version_note = (
        ""
        if negotiated in {PROTOCOL_VERSION, None}
        else f"protocolVersion negotiated to {negotiated!r}, not {PROTOCOL_VERSION!r}"
    )
    elapsed = time.monotonic() - started

    # The notification is unacknowledged by design, so its only failure mode is a
    # dead pipe — which the next await would report anyway.
    session.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    session.send({"jsonrpc": "2.0", "id": _TOOLS_ID, "method": "tools/list", "params": {}})
    tools_msg, tools_detail = session.await_id(_TOOLS_ID)
    session.send({"jsonrpc": "2.0", "id": _RESOURCES_ID, "method": "resources/list", "params": {}})
    resources_msg, resources_detail = session.await_id(_RESOURCES_ID)

    tools = _result_list(tools_msg, "tools")
    resources = _result_list(resources_msg, "resources")
    return Advertised(
        initialized=True,
        tools=tuple(str(t.get("name", "")) for t in tools),
        resources=tuple(str(r.get("uri", "")) for r in resources),
        tool_schema_bytes=len(json.dumps(tools, separators=(",", ":")).encode()),
        elapsed_s=elapsed,
        # BOTH lists report their own failure. An empty tuple means "answered,
        # advertised none"; a non-empty detail means the question was never
        # answered. The resources half used to discard its detail outright, so a
        # timeout there rendered as a server with zero resources — the exact
        # collapse this class's docstring promises never to make, contradicted by
        # the code under it. (Cold lane, round 1.)
        detail="; ".join(
            part
            for part in (
                version_note,
                _list_failures(
                    ("tools/list", tools_msg, tools_detail),
                    ("resources/list", resources_msg, resources_detail),
                ),
            )
            if part
        ),
    )


def _negotiated_version(init: dict[str, object]) -> str | None:
    """The `protocolVersion` the server agreed to, or ``None`` if it named none."""
    result = init.get("result")
    if not isinstance(result, dict):
        return None
    version = result.get("protocolVersion")
    return str(version) if isinstance(version, str) else None


def _error_detail(message: dict[str, object]) -> str | None:
    """The message text when a reply is a JSON-RPC error, else ``None``.

    A reply carrying neither `result` nor `error` violates the protocol; it is
    reported as a refusal rather than accepted, because a probe cannot describe a
    surface a server never sent.
    """
    error = message.get("error")
    if isinstance(error, dict):
        code = error.get("code", "?")
        return f"[{code}] {error.get('message', 'no message')}"
    if "result" not in message:
        return "reply carried neither result nor error"
    return None


def _list_failures(*asked: tuple[str, dict[str, object] | None, str]) -> str:
    """Join the details of the list requests that did not produce a real answer.

    TWO ways to not answer, and the second one was missed. A message that never
    arrived is ``None``; a message that arrived carrying a JSON-RPC **error** is a
    dict, so it read as "answered" and `_result_list` then found no array and
    returned `[]` — reporting `tools=()` with an empty detail, indistinguishable
    from a server that really advertises nothing. That is the same collapse this
    module's docstring disclaims, arriving through a second door after the first
    was closed. (Cold lane, round 2.)
    """
    out = []
    for method, message, detail in asked:
        if message is None:
            out.append(f"{method}: {detail}")
        elif (error := _error_detail(message)) is not None:
            out.append(f"{method}: server returned an error: {error}")
    return "; ".join(out)


def _shutdown(proc: subprocess.Popen[str]) -> None:
    """Close stdin and end the server TREE, escalating to kill if it will not go.

    The GROUP, not the process. The command this probe is pointed at in anger is
    `mise run kb-serve`, so the `Popen` is *mise* and `graphify-mcp` is a
    grandchild — signalling only the top-level pid left a server holding a 393 MB
    graph alive and reparented to init. That is not hypothetical: this session
    had to `pkill -f graphify-mcp` by hand before the leak was diagnosed.
    (Cold lane, round 2.)
    """
    with contextlib.suppress(BrokenPipeError, ValueError):
        if proc.stdin is not None:
            proc.stdin.close()
    _signal_tree(proc, signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _signal_tree(proc, signal.SIGKILL)
        proc.wait(timeout=10)


def _signal_tree(proc: subprocess.Popen[str], sig: int) -> None:
    """Signal the child's whole process group, falling back to the child alone.

    The fallback matters on a host where the group lookup fails: reaching the
    direct child is strictly better than reaching nothing, and a failure to clean
    up must not raise out of a `finally`.
    """
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except OSError, ProcessLookupError:
        with contextlib.suppress(OSError, ProcessLookupError):
            proc.send_signal(sig)
