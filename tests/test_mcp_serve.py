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
import sys
from pathlib import Path

import pytest
from kb_setup import mcp_probe

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The aggregate graph takes ~9.2s to load (3.4 MB prose graph answers in 0.6s,
#: the 393 MB aggregate in 9.8s), so the live arm needs real headroom. Bounded
#: rather than absent — `long-running-command-hangs.md`.
LIVE_TIMEOUT_S = 120.0

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

    result = mcp_probe.probe(["mise", "run", "kb-serve"], cwd=REPO_ROOT, timeout=LIVE_TIMEOUT_S)

    assert result.initialized is True, result.detail
    # graphify 0.9.31/0.9.32 both advertise 10 tools + 6 resources. Asserted as a
    # floor, not an equality: a graphify bump that ADDS a tool is not a failure of
    # this task, while a drop to zero is exactly the silence being guarded.
    assert len(result.tools) >= 1, result.detail
    assert "query_graph" in result.tools
    assert result.tool_schema_bytes > 0
