# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.memory_serve` — the `kb-memory` MCP server (U-R9, #681).

The load-bearing tests here are the two LIVE ones. This repo has already been
bitten by the difference between a server that is *configured* and one that
*answers*: `mise run kb-serve` served NOTHING for months while every config file
on disk said otherwise, exiting rc=0 with empty stderr because mise read its
stdio by line instead of connecting it (#105). And #668 added the sibling
lesson — REGISTERED IS NOT REACHABLE — where a correctly-configured server was
denied before it was ever contacted.

So `test_kb_memory_server_advertises_recall` and
`test_a_real_tools_call_returns_ranked_json` speak real JSON-RPC to a real
subprocess. Nothing else in this file can catch the failure they exist for: a
unit test of `build_server` proves the object is shaped right, never that a
client can reach it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from kb_setup import mcp_probe, memory_serve

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_TIMEOUT_S = 120


def _memory(path: Path, name: str, *, question: str, answer: str, outcome: str = "useful") -> Path:
    """A memory file in the shape `graphify save-result` writes."""
    target = path / f"{name}.md"
    target.write_text(
        "---\n"
        'type: "query"\n'
        'date: "2026-08-01T00:00:00+00:00"\n'
        f'question: "{question}"\n'
        f'outcome: "{outcome}"\n'
        "---\n\n"
        f"# Q: {question}\n\n"
        f"## Answer\n\n{answer}\n\n"
        f"## Outcome\n\n- Signal: {outcome}\n",
        encoding="utf-8",
    )
    return target


# --- argument translation -------------------------------------------------


def test_recall_argv_passes_json_and_the_question() -> None:
    assert memory_serve.recall_argv({"question": "how does kb-build work"}) == [
        "how does kb-build work",
        "--json",
    ]


def test_recall_argv_forwards_every_optional_flag() -> None:
    argv = memory_serve.recall_argv(
        {"question": "q", "top": 3, "outcome": "corrected", "since": "2026-08-01"}
    )
    assert argv == ["q", "--json", "--top", "3", "--outcome", "corrected", "--since", "2026-08-01"]


def test_recall_argv_omits_a_flag_whose_value_is_none() -> None:
    """An MCP client may send an explicit null for an unset optional.

    Forwarding `--top None` would reach `check_recall` as a malformed integer
    and refuse the whole call, turning "the caller left this out" into "the
    caller got it wrong".
    """
    argv = memory_serve.recall_argv({"question": "q", "top": None, "outcome": None, "since": None})
    assert argv == ["q", "--json"]


def test_recall_argv_survives_no_arguments_at_all() -> None:
    """`params.arguments` is optional in MCP; None must not crash the handler."""
    assert memory_serve.recall_argv(None) == ["", "--json"]


# --- the tool handler, which must never raise -----------------------------


def test_run_recall_tool_returns_the_json_report(tmp_path: Path) -> None:
    _memory(
        tmp_path,
        "target",
        question="How does the heredoc tokeniser handle quote awareness?",
        answer="The guard's shlex-based tokeniser tracks quoting state.",
    )
    text, is_error = memory_serve.run_recall_tool({"question": "heredoc tokeniser"}, tmp_path)
    assert is_error is False
    payload = json.loads(text)
    assert payload["hits"], "a term present verbatim in the fixture found nothing"
    assert payload["hits"][0]["path"] == "target.md"
    assert payload["matched"] >= 1


def test_run_recall_tool_reports_a_bad_request_as_text_not_an_exception(tmp_path: Path) -> None:
    """A raising tool becomes a transport error the caller cannot read."""
    _memory(tmp_path, "x", question="q", answer="a")
    text, is_error = memory_serve.run_recall_tool(
        {"question": "q", "top": "not-a-number"}, tmp_path
    )
    assert is_error is True
    assert "refused" in text
    assert "rc=" in text, "the refusal must carry its exit code, not just prose"


def test_an_empty_store_is_not_flagged_as_an_error(tmp_path: Path) -> None:
    """NOT_RUN says nothing was searched — a different answer from a bad request.

    Collapsing the two is the "never asked" / "answered no" confusion
    `probes-need-a-control-arm.md` rule 4 exists to stop, and here it would tell
    a caller its question was malformed when the store was merely empty.
    """
    text, is_error = memory_serve.run_recall_tool({"question": "anything"}, tmp_path)
    assert is_error is False, "an empty store is an answer, not a failure of the call"
    assert "nothing searched" in text


def test_an_unreadable_memory_dir_still_returns_rather_than_raising(tmp_path: Path) -> None:
    text, is_error = memory_serve.run_recall_tool({"question": "q"}, tmp_path / "does-not-exist")
    assert isinstance(text, str)
    assert is_error is False


# --- server construction --------------------------------------------------


def test_build_server_advertises_exactly_the_recall_tool(tmp_path: Path) -> None:
    server = memory_serve.build_server(tmp_path)
    assert server.name == memory_serve.SERVER_NAME


def test_build_server_refuses_an_mcp_1x_shaped_server(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The 1.x decorator API is NOT implemented, and says so instead of half-working.

    graphify's own `_build_server` carries both branches because it ships
    everywhere; this repo pins mcp 2.x, and untested compatibility code for a
    version we do not run reads as coverage while providing none.
    """
    import mcp.server

    class _OneX:
        def list_tools(self) -> None: ...

    monkeypatch.setattr(mcp.server, "Server", _OneX)
    with pytest.raises(RuntimeError, match=r"mcp looks like 1\.x"):
        memory_serve.build_server(tmp_path)


def test_memory_dir_defaults_to_the_committed_store() -> None:
    assert memory_serve._memory_dir(REPO_ROOT, []) == REPO_ROOT / "graphify-out" / "memory"


def test_memory_dir_honours_an_explicit_flag(tmp_path: Path) -> None:
    explicit = str(tmp_path / "elsewhere")
    assert memory_serve._memory_dir(REPO_ROOT, ["--memory-dir", explicit]) == Path(explicit)


def test_memory_dir_ignores_a_dangling_flag() -> None:
    """`--memory-dir` with nothing after it falls back rather than IndexError-ing."""
    assert (
        memory_serve._memory_dir(REPO_ROOT, ["--memory-dir"])
        == REPO_ROOT / "graphify-out" / "memory"
    )


# --- LIVE: the two that catch "configured but not serving" ----------------


def test_kb_memory_server_advertises_recall() -> None:
    """A real MCP handshake against a real subprocess.

    Realistic mutation: break the `on_list_tools` wiring in `build_server` and
    this fails. A unit test on the returned `Server` object cannot — it inspects
    the object rather than asking it over a pipe, which is exactly the gap that
    let `mise run kb-serve` advertise nothing for months (#105).
    """
    result = mcp_probe.probe(
        ["uv", "run", "kb-setup", "serve-memory"], cwd=REPO_ROOT, timeout=LIVE_TIMEOUT_S
    )
    assert result.initialized is True, result.detail
    assert sorted(result.tools) == ["recall"], result.detail
    assert result.tool_schema_bytes > 0, result.detail


def test_a_real_tools_call_returns_ranked_json(tmp_path: Path) -> None:
    """REGISTERED IS NOT REACHABLE (#668) — so call the tool, do not just list it.

    Drives `initialize` -> `tools/call` over stdio against an isolated fixture
    store, and asserts the ranked JSON comes back through the transport rather
    than only out of `run_recall_tool` in-process.
    """
    _memory(
        tmp_path,
        "target",
        question="What broke the mise install lock during the renovate hang?",
        answer="The renovate npm-backend postinstall recursed into its own mise install.",
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "kb_setup.cli", "serve-memory", "--memory-dir", str(tmp_path)],
        cwd=REPO_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        # NOT optional, and not cargo-culted from `mcp_probe.probe`. The teardown
        # below is `mcp_probe._shutdown`, which signals the child's process GROUP
        # (`_signal_tree` -> `os.killpg`). Without its own session the child
        # shares pytest's group, so teardown SIGNALS THE TEST RUNNER: measured
        # here as pytest dying at exit 144 after 14 green tests, which reads like
        # a crash in the code under test and is not one. A private helper carries
        # its spawn contract with it.
        start_new_session=True,
    )
    try:
        import time

        session = mcp_probe._Session(proc, time.monotonic() + LIVE_TIMEOUT_S)
        session.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            }
        )
        init, detail = session.await_id(1)
        assert init is not None, detail
        session.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        session.send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "recall",
                    "arguments": {"question": "renovate hang mise install lock"},
                },
            }
        )
        reply, detail = session.await_id(2)
        assert reply is not None, detail
        assert "error" not in reply, reply
        result = reply["result"]
        assert isinstance(result, dict), reply
        content = result["content"]
        assert isinstance(content, list), result
        payload = json.loads(content[0]["text"])
        assert payload["hits"][0]["path"] == "target.md", payload
    finally:
        mcp_probe._shutdown(proc)
