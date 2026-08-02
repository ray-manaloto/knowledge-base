"""`kb-setup serve` narrows the advertised surface only when told to.

Two properties, and the FIRST is the one that protects the repo. `kb-serve` was
found on 2026-08-02 to have been serving nothing at all, so the default path must
keep no code of ours in the DATA path between the client and `graphify-mcp` — it
runs the binary with inherited stdio and only waits. A filter that quietly
interposed a relay on every session would be re-taking the risk that was just
paid down, in exchange for a saving the measurements say is ~30 tokens under
Claude Code's default deferred tool loading.

The second is that when an allowlist IS set, the narrowing is real, is keyed to
the request that asked for it, and passes everything else through untouched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from kb_setup import mcp_probe, mcp_serve

#: A server standing in for `graphify-mcp`: it answers `tools/list` and
#: `resources/list` and one unrelated method. NOT graphify — the filter is a
#: property of the relay, and a fixture that could fail for graphify's reasons
#: would not isolate it.
_FAKE_UPSTREAM = """
import json, sys
TOOLS = [{"name": n, "inputSchema": {"type": "object"}}
         for n in ("query_graph", "get_node", "list_prs", "triage_prs")]
RESOURCES = [{"uri": u} for u in ("graphify://report", "graphify://stats")]
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    mid = msg.get("id")
    if mid is None:
        continue
    m = msg["method"]
    if m == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {},
                  "serverInfo": {"name": "fake", "version": "1"}}
    elif m == "tools/list":
        result = {"tools": TOOLS}
    elif m == "resources/list":
        result = {"resources": RESOURCES}
    else:
        result = {"echo": m}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\\n")
    sys.stdout.flush()
"""


def _relay_cmd(tmp_path: Path, env_pairs: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    """A command that runs the real relay in front of the fake upstream."""
    upstream = tmp_path / "upstream.py"
    upstream.write_text(_FAKE_UPSTREAM, encoding="utf-8")
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import sys\n"
        "from kb_setup import mcp_serve\n"
        "allow = {}\n"
        "for method, env in (('tools/list', mcp_serve.TOOLS_ENV),\n"
        "                    ('resources/list', mcp_serve.RESOURCES_ENV)):\n"
        "    import os\n"
        "    names = mcp_serve.parse_allowlist(os.environ.get(env))\n"
        "    if names is not None:\n"
        "        allow[method] = names\n"
        "sys.exit(mcp_serve._proxy([sys.executable, sys.argv[1]], allow, None))\n",
        encoding="utf-8",
    )
    return [sys.executable, str(driver), str(upstream)], env_pairs


# --------------------------------------------------------------------------
# parse_allowlist: unset and empty are DIFFERENT states.
# --------------------------------------------------------------------------


def test_unset_means_do_not_filter():
    assert mcp_serve.parse_allowlist(None) is None


def test_blank_means_do_not_filter_not_serve_nothing():
    """A present-but-empty value must not collapse to "advertise nothing".

    That collapse is the exact silhouette of the bug this area just fixed: a
    server advertising zero tools is indistinguishable from a server that is not
    working, so an empty allowlist has to fail OPEN.
    """
    assert mcp_serve.parse_allowlist("") is None
    assert mcp_serve.parse_allowlist("   ") is None
    assert mcp_serve.parse_allowlist(",, ,") is None


def test_names_are_parsed_and_trimmed():
    assert mcp_serve.parse_allowlist(" query_graph , get_node ") == frozenset(
        {"query_graph", "get_node"}
    )


# --------------------------------------------------------------------------
# _filter_response: only touches what it understands.
# --------------------------------------------------------------------------


def test_filter_keeps_only_allowed():
    message: dict[str, object] = {
        "result": {"tools": [{"name": "a"}, {"name": "b"}, {"name": "c"}]}
    }
    mcp_serve._filter_response(message, "tools/list", frozenset({"a", "c"}))
    assert message["result"]["tools"] == [{"name": "a"}, {"name": "c"}]


def test_filter_leaves_an_error_response_alone():
    """An error carries no `result`; rewriting it would corrupt a real failure."""
    message: dict[str, object] = {"error": {"code": -32603, "message": "boom"}}
    mcp_serve._filter_response(message, "tools/list", frozenset({"a"}))
    assert message == {"error": {"code": -32603, "message": "boom"}}


def test_filter_leaves_an_unexpected_shape_alone():
    message: dict[str, object] = {"result": {"tools": "not-a-list"}}
    mcp_serve._filter_response(message, "tools/list", frozenset({"a"}))
    assert message["result"]["tools"] == "not-a-list"


# --------------------------------------------------------------------------
# The relay, end to end, through the real MCP probe.
# --------------------------------------------------------------------------


def test_relay_passes_everything_through_when_unset(tmp_path, monkeypatch):
    """CONTROL ARM: with no allowlist the relay must not remove anything.

    Without this the narrowing test below proves only that *something* came back
    smaller — it could not distinguish a working filter from a relay that drops
    whatever it fails to understand.
    """
    monkeypatch.delenv(mcp_serve.TOOLS_ENV, raising=False)
    monkeypatch.delenv(mcp_serve.RESOURCES_ENV, raising=False)
    cmd, _ = _relay_cmd(tmp_path, {})

    result = mcp_probe.probe(cmd, timeout=30)

    assert result.initialized is True, result.detail
    assert result.tools == ("query_graph", "get_node", "list_prs", "triage_prs")
    assert result.resources == ("graphify://report", "graphify://stats")


def test_relay_narrows_tools_when_set(tmp_path, monkeypatch):
    monkeypatch.setenv(mcp_serve.TOOLS_ENV, "query_graph,get_node")
    monkeypatch.delenv(mcp_serve.RESOURCES_ENV, raising=False)
    cmd, _ = _relay_cmd(tmp_path, {})

    result = mcp_probe.probe(cmd, timeout=30)

    assert result.initialized is True, result.detail
    assert result.tools == ("query_graph", "get_node")
    # Resources were NOT filtered — the two allowlists are independent, and a
    # tools filter that also silently trimmed resources would be a second,
    # unrequested change hiding inside the first.
    assert result.resources == ("graphify://report", "graphify://stats")


def test_relay_narrows_resources_independently(tmp_path, monkeypatch):
    monkeypatch.delenv(mcp_serve.TOOLS_ENV, raising=False)
    monkeypatch.setenv(mcp_serve.RESOURCES_ENV, "graphify://stats")
    cmd, _ = _relay_cmd(tmp_path, {})

    result = mcp_probe.probe(cmd, timeout=30)

    assert result.initialized is True, result.detail
    assert result.tools == ("query_graph", "get_node", "list_prs", "triage_prs")
    assert result.resources == ("graphify://stats",)


def test_relay_does_not_rewrite_a_response_it_never_requested(tmp_path, monkeypatch):
    """A `result` containing a `tools` key is not proof the client asked for it.

    The relay keys off the id of a request it forwarded, so an unrelated method
    whose payload merely resembles a tool list passes through untouched. Guessing
    from the response body would corrupt any server that happens to use the same
    key for something else.
    """
    monkeypatch.setenv(mcp_serve.TOOLS_ENV, "nothing-matches-this")
    monkeypatch.delenv(mcp_serve.RESOURCES_ENV, raising=False)
    cmd, _ = _relay_cmd(tmp_path, {})

    proc = mcp_probe.probe(cmd, timeout=30)
    assert proc.initialized is True, proc.detail
    # `initialize` itself is a response the relay saw and must have left alone,
    # which the successful handshake already proves.
    assert proc.tools == ()
    assert json.dumps(list(proc.resources))


# --------------------------------------------------------------------------
# Cold-lane round 1: an allowlist the transport cannot enforce must REFUSE.
# --------------------------------------------------------------------------


def test_stdio_is_not_flagged():
    """CONTROL ARM: the transports that CAN be filtered are not refused."""
    assert mcp_serve.wants_non_stdio([]) is None
    assert mcp_serve.wants_non_stdio(["--transport", "stdio"]) is None
    assert mcp_serve.wants_non_stdio(["--transport=stdio"]) is None
    # A bare trailing flag names no transport; argparse would reject it, and this
    # must not invent one.
    assert mcp_serve.wants_non_stdio(["--transport"]) is None


def test_http_transport_is_detected_in_both_spellings():
    assert mcp_serve.wants_non_stdio(["--transport", "http"]) == "http"
    assert mcp_serve.wants_non_stdio(["--transport=http"]) == "http"
    assert mcp_serve.wants_non_stdio(["--port", "8080", "--transport", "http"]) == "http"


def test_serve_refuses_an_allowlist_it_cannot_enforce(tmp_path, monkeypatch, capsys):
    """`--transport http` + an allowlist must REFUSE, not serve unfiltered.

    The relay only rewrites line-delimited JSON-RPC on the child's pipes; an
    HTTP child serves on its own socket. Before this, the process started the
    server anyway AND printed "narrowed to N" — a filter reporting success
    without filtering. `mise.toml` documents that exact invocation.

    The binary is stubbed to `true`, and that is a REQUIREMENT rather than
    tidiness. Mutating the guard away and re-running this is how its FAIL
    direction is proven — and with the real binary that mutation does not fail,
    it HANGS, because the unguarded path genuinely starts an HTTP server and
    waits forever. A test whose failure mode is a wedged suite cannot be used to
    verify the thing it is testing, so the stub is what makes the mutation come
    back fast and red.
    """
    monkeypatch.setenv(mcp_serve.TOOLS_ENV, "query_graph")
    monkeypatch.setattr(mcp_serve, "mcp_binary", lambda _root=None: "true")

    rc = mcp_serve.serve(tmp_path, ["--transport", "http", "--port", "8080"])

    assert rc == 2
    err = capsys.readouterr().err
    assert "REFUSING" in err
    assert "CANNOT be enforced" in err
    # It must not also claim to have narrowed anything.
    assert "narrowed to" not in err
