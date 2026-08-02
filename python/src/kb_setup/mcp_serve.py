"""Serve this repo's graph over MCP, optionally narrowing the advertised surface.

WHY THIS EXISTS. `graphify-mcp` advertises **10 tools + 6 resources
unconditionally** — 5,828 B of tool schema, measured against the live server on
2026-08-02 and identical in the pinned 0.9.31 and in 0.9.32. There is no way to
narrow that from either end:

* **Not from graphify.** No `--tools` flag, no `GRAPHIFY_MCP_TOOLS` env var, in
  0.9.31 or 0.9.32. Control arm: grepping the same file for the same shape finds
  `GRAPHIFY_MAX_CONTEXTS` and `GRAPHIFY_API_KEY`, so the probe discriminates.
* **Not from the client.** Claude Code's MCP settings expose only *server*-level
  toggles — `disabledMcpServers`, `enabledMcpServers`, `enabledMcpjsonServers`,
  `disabledMcpjsonServers`. Nothing selects individual tools. Control arm: the
  same doc mentions `mcp__` 7 times and `permissions` 6 times.

Custom code is therefore the last resort rather than the first reach
(`use-tool-builtins.md`), and this module records why, as that rule requires.

WHY IT IS OPT-IN, AND WHY THAT IS THE WHOLE DESIGN. With no allowlist set this
does not proxy at all: it runs `graphify-mcp` with **inherited stdio**, so the
child holds the real file descriptors and not one byte of the JSON-RPC stream
passes through this process. The default path therefore adds no failure surface
to the data path at all. That matters more than it sounds — this task was
discovered on 2026-08-02 to have been serving **nothing** (see
`kb_setup.mcp_probe`), and permanently interposing a relay in front of a server
that had just been repaired, for no default benefit, trades a real risk for a
hypothetical one.

Inherited stdio rather than `os.execvpe`, which would be a shade cleaner still
(no waiting parent at all), for one reason: `os.exec*` trips ruff's S606, and
this repo does not carry inline suppressions and does not widen the global ignore
list for a preference. The parent only waits; what the two forms have in common
is the part that matters, which is that the child's stdin and stdout ARE the
client's.

WHAT THE FILTER IS WORTH, WITH ITS CONDITION ATTACHED. Under Claude Code's
default `tool search`, MCP tools are deferred and only NAMES load at session
start — 118 B, so the standing cost of all ten is roughly 30 tokens and trimming
buys almost nothing. The saving is real for the consumers that load schemas
upfront, which Claude Code's own docs enumerate: `ENABLE_TOOL_SEARCH=false`, a
custom `ANTHROPIC_BASE_URL`, Amazon Bedrock, Google Cloud's Agent Platform, and
Microsoft Foundry. Those pay the full 5,828 B every session. The other argument
is codegraph's, and it is independent of tokens: a tool's mere presence steers
the model into picking it when it should not (`sources/codegraph/src/mcp/tools.ts`
:813, which pares its own default set to a single tool for exactly this reason).

FILTERING IS BY REQUEST ID, NOT BY GUESSING. A JSON-RPC response carries an `id`
and no method, so the proxy records the method of every client request it
forwards and rewrites only the responses whose id it is still waiting on. A
response cannot be identified from its own contents — a `result` holding a
`tools` key is not proof the client asked `tools/list`.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from kb_setup.graphify_env import clean_env, graphify_exe

#: Comma-separated tool names to advertise. UNSET or blank means "no filtering",
#: which is a different state from "advertise nothing" — see :func:`parse_allowlist`.
TOOLS_ENV = "KB_MCP_TOOLS"

#: The same, for `resources/list` URIs.
RESOURCES_ENV = "KB_MCP_RESOURCES"

#: The methods whose responses are rewritten, mapped to the `result` key holding
#: the array and the item field the allowlist matches on.
_FILTERED = {
    "tools/list": ("tools", "name"),
    "resources/list": ("resources", "uri"),
}

_MCP_BINARY = "graphify-mcp"


def parse_allowlist(raw: str | None) -> frozenset[str] | None:
    """Parse an allowlist env var. ``None`` means DO NOT FILTER.

    The distinction is load-bearing and is why this returns an optional set
    rather than a possibly-empty one: unset means "serve everything", while a
    value that is present but names nothing usable would otherwise silently
    become "serve nothing" — a server advertising zero tools looks exactly like
    the broken server this repo just finished diagnosing. A blank or
    all-separators value is therefore treated as unset, not as empty.
    """
    if raw is None:
        return None
    names = frozenset(part.strip() for part in raw.split(",") if part.strip())
    return names or None


def mcp_binary(repo_root: Path | None = None) -> str:
    """Locate `graphify-mcp`, following this repo's pin.

    Derived from :func:`graphify_exe`'s answer rather than resolved independently:
    the two binaries are installed side by side in one venv's `bin`, so taking
    the sibling of the pin-resolved `graphify` inherits its pin-following for
    free. Resolving `graphify-mcp` through PATH on its own would reintroduce
    exactly the frozen-install-dir hazard that function exists to avoid.
    """
    sibling = Path(graphify_exe(repo_root)).with_name(_MCP_BINARY)
    if sibling.is_file():
        return str(sibling)
    return shutil.which(_MCP_BINARY) or _MCP_BINARY


def _filter_response(message: dict[str, object], method: str, allow: frozenset[str]) -> None:
    """Narrow a `tools/list` or `resources/list` result in place.

    A response that carries an `error`, or whose `result` is not the shape the
    method promises, is left untouched: rewriting a payload we do not understand
    would turn a server-side error into a malformed frame, and the client is
    better placed to report the original.
    """
    key, field = _FILTERED[method]
    result = message.get("result")
    if not isinstance(result, dict):
        return
    items = result.get(key)
    if not isinstance(items, list):
        return
    # A rebuilt `result` rather than a mutated one: this dict came out of
    # `json.loads`, so its declared value type is whatever the parser inferred,
    # and assigning into it is not a checkable operation. Rebuilding keeps every
    # other key the server sent, byte-for-byte in value.
    narrowed: dict[str, object] = {str(k): v for k, v in result.items()}
    narrowed[key] = [i for i in items if isinstance(i, dict) and str(i.get(field, "")) in allow]
    message["result"] = narrowed


class _Relay:
    """Forwards frames between a client and a `graphify-mcp` child."""

    def __init__(self, child: subprocess.Popen[str], allow: dict[str, frozenset[str]]) -> None:
        self._child = child
        self._allow = allow
        #: request id -> method, for the requests whose responses get rewritten.
        #: Guarded because it is written by the client thread and read by the
        #: server thread.
        self._awaiting: dict[object, str] = {}
        self._lock = threading.Lock()

    def client_to_server(self) -> None:
        """Relay stdin to the child, remembering which requests to rewrite."""
        stdin = self._child.stdin
        if stdin is None:
            return
        try:
            for line in sys.stdin:
                self._note_request(line)
                stdin.write(line)
                stdin.flush()
        except BrokenPipeError, ValueError:
            pass
        finally:
            # EOF from the client is a shutdown, and it must be PASSED ON. The
            # defect this whole area exists to fix was a stdio server that saw an
            # EOF it should not have; swallowing a real one here would replace it
            # with a child that never exits.
            with contextlib.suppress(BrokenPipeError, ValueError):
                stdin.close()

    def _note_request(self, line: str) -> None:
        """Record `id -> method` when the client asks something we rewrite."""
        try:
            message = json.loads(line)
        except TypeError, ValueError:
            return
        if not isinstance(message, dict):
            return
        method = message.get("method")
        mid = message.get("id")
        if mid is not None and isinstance(method, str) and method in self._allow:
            with self._lock:
                self._awaiting[mid] = method

    def server_to_client(self) -> None:
        """Relay the child's stdout to stdout, rewriting the responses we own."""
        stdout = self._child.stdout
        if stdout is None:
            return
        for line in stdout:
            sys.stdout.write(self._rewrite(line))
            sys.stdout.flush()

    def _rewrite(self, line: str) -> str:
        """Return ``line``, filtered if it answers a request we are waiting on.

        Anything unrecognised is passed through BYTE-FOR-BYTE rather than
        re-serialised. A proxy that reformats every frame it merely inspects
        would make itself a suspect in any future protocol bug, and it has no
        business normalising another server's output.
        """
        try:
            message = json.loads(line)
        except TypeError, ValueError:
            return line
        if not isinstance(message, dict):
            return line
        mid = message.get("id")
        with self._lock:
            method = self._awaiting.pop(mid, None) if mid is not None else None
        if method is None:
            return line
        _filter_response(message, method, self._allow[method])
        return json.dumps(message) + "\n"


def _proxy(cmd: list[str], allow: dict[str, frozenset[str]], repo_root: Path) -> int:
    """Run `graphify-mcp` behind a filtering relay and return its exit code."""
    child = subprocess.Popen(
        cmd,
        cwd=repo_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        bufsize=1,
        env=clean_env(),
    )
    relay = _Relay(child, allow)
    # The client pump is the daemon: when the child dies, `server_to_client`
    # returns and this process should end even though stdin may never see EOF.
    pump = threading.Thread(target=relay.client_to_server, daemon=True)
    pump.start()
    relay.server_to_client()
    return child.wait()


def serve(repo_root: Path, argv: list[str]) -> int:
    """Start the MCP server for this repo's graph.

    With no allowlist configured this NEVER RETURNS — it replaces the current
    process with `graphify-mcp`, so nothing of this module remains between the
    client and the server.
    """
    graph = repo_root / "graphify-out" / "graph.json"
    cmd = [mcp_binary(repo_root), str(graph), *argv]

    allow = {
        method: names
        for method, env in (("tools/list", TOOLS_ENV), ("resources/list", RESOURCES_ENV))
        if (names := parse_allowlist(os.environ.get(env))) is not None
    }
    if not allow:
        # No pipes: the child inherits this process's stdin/stdout, so the client
        # is talking to `graphify-mcp` directly and nothing here can corrupt,
        # buffer, or drop a frame.
        return subprocess.run(cmd, cwd=repo_root, env=clean_env(), check=False).returncode
    for method, names in sorted(allow.items()):
        # stderr, never stdout — stdout IS the JSON-RPC channel, and a banner
        # written there is a malformed frame the client must try to parse.
        print(
            f"[kb-serve] {method} narrowed to {len(names)}: {', '.join(sorted(names))}",
            file=sys.stderr,
        )
    return _proxy(cmd, allow, repo_root)
