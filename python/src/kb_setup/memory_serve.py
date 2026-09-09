# Copyright (c) 2026 Raymond Manaloto
"""Serve this repo's work-memory over MCP as `kb-memory` — U-R9's transport half.

WHY A THIRD SERVER RATHER THAN A FORK PATCH OR A RELAY. #681 weighed three ways
to close the hosted `remember`/`recall` gap and chose this one; an advisor
consult (`.agent/kb/reports/agents/advisor-ur-architecture.md`) added a fourth
and then ruled it out. The short form, with what was actually measured:

* **Patch our graphify fork.** Viable — `sources/graphify/` IS the installed
  fork rev (`157a957e`, `v0.9.53-8-g157a957`), so there is no clone/install skew
  to develop around. It buys the documented "graphify circle": 8 pin sites, and
  a bump that is never one line.
* **Inject through `kb_setup.mcp_serve`'s relay.** IMPOSSIBLE AS BUILT, probed
  live rather than read (three arms, on #681): unfiltered -> 10 tools; allowlist
  `query_graph` -> exactly 1, a strict subset; allowlist a name graphify does
  not serve -> **0 tools, not a new one**. The middle arm is the control that
  makes the third an answer rather than a broken probe. The relay also only ever
  narrows an existing `tools/list`; it never answers a `tools/call`.
* **Compose in-process** — import graphify's `_build_server` and append. Blocked
  by the pinned **mcp 2.0.0**, which binds handlers in the `Server` CONSTRUCTOR
  rather than by decorator, so they cannot be re-bound afterwards. It also
  reaches for a `_private` name, against Ray's standing `sdk-over-cli` call.

WHY IT DOES NOT RE-INCUR #668. That outage was a registration-key COLLISION, not
a server count: `codex mcp add graphify --url` wrote a GLOBAL entry while this
repo's PROJECT entry used the same key as a stdio command, and codex refused to
boot — *"url is not supported for stdio in `mcp_servers.graphify`"*. Renaming
ours to `kb` fixed it. Three distinctly-named servers do not reproduce that.

WHAT THIS DOES NOT WIRE INTO, and it is the premise #681 got wrong. There is no
dependency on `[tasks.kb-serve]`'s `raw = true`. Both clients register the binary
directly — `.mcp.json` and `.codex/config.toml` each say `uv run kb-setup …` —
so mise's line-buffered stdio, which made that TASK serve nothing until #105, is
not on this path at all. The mise task is a convenience for humans.

STDOUT IS THE JSON-RPC CHANNEL, so nothing here may print. `recall.main` renders
to stdout by design and is therefore NOT what this calls: it goes to the library
seam (`check_recall` -> `run_recall` -> `render_json`) and hands the JSON back as
tool content. A stray `print` would corrupt a frame, which is also why
`kb-serve`'s task comment fought mise's redaction for the same reason.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from kb_setup import recall
from kb_setup.result import Err, External, Ok, Rc, exit_code

if TYPE_CHECKING:
    from collections.abc import Sequence

    from mcp import types
    from mcp.server import Server

#: The registration key on both clients, and the `mcp__<name>__<tool>` prefix.
#: Ray chose it 2026-09-09 over `memory` (generic enough that a future global
#: entry could claim the key — the #668 shape) and over `kb-recall` (names the
#: one tool it ships today, while U-R1/2/3/4 are meant to land here too).
SERVER_NAME = "kb-memory"

#: The one tool this server ships today. U-R9's CLI half is already proven
#: (`kb_setup.recall`, `mise run kb-recall`, #540); this is only its transport.
RECALL_TOOL = "recall"

_RECALL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "Natural-language question to rank the work-memory store against.",
        },
        "top": {
            "type": "integer",
            "default": 5,
            "description": "How many ranked memories to return.",
        },
        "outcome": {
            "type": "string",
            "enum": ["useful", "corrected", "dead_end", "all"],
            "default": "all",
            "description": (
                "Narrow to one recorded outcome. `corrected` ranks at least as "
                "high as `useful` at equal relevance."
            ),
        },
        "since": {
            "type": "string",
            "description": "Only memories dated on or after this YYYY-MM-DD.",
        },
    },
    "required": ["question"],
}

_RECALL_DESCRIPTION = (
    "Rank this repo's committed work-memory (graphify-out/memory/) against a question "
    "by BM25, weighted by recorded outcome and recency. Use it BEFORE researching "
    "something that may already have been answered and recorded here. Returns JSON: "
    "the ranked hits with their scores, dates, outcomes and excerpts, plus how many "
    "memories matched, were searched, and exist."
)


def recall_argv(arguments: dict[str, Any] | None) -> list[str]:
    """Translate MCP tool arguments into the argv `check_recall` already validates.

    Deliberately a TRANSLATION and not a second validator. `check_recall` owns
    every rule about `--top`/`--outcome`/`--since` and is tested against them;
    re-expressing those rules here would be two implementations to drift, and
    the one on this side would be the untested one. `--json` is always passed
    because a tool result is machine-read.
    """
    args = dict(arguments or {})
    # An explicit JSON `null` is NOT the same as an absent key, and `dict.get`'s
    # default only covers the absent case — so `str(args.get("question", ""))`
    # produced the literal string `"None"` and searched for it. Cold-review P2,
    # live-verified: `{"question": null}` returned a normal-looking ranked set
    # (60 matches in the 382-record store) that a caller cannot tell apart from a
    # real answer, while an omitted key and an empty string both correctly refuse
    # with `a question is required`. The optional flags below already guarded
    # `is not None`; this field did not, and it is the only required one.
    question = args.get("question")
    argv = ["" if question is None else str(question), "--json"]
    for flag in ("top", "outcome", "since"):
        if args.get(flag) is not None:
            argv += [f"--{flag}", str(args[flag])]
    return argv


def run_recall_tool(arguments: dict[str, Any] | None, memory_dir: Path) -> tuple[str, bool]:
    """Answer one `recall` call. Returns `(text, is_error)` and NEVER raises.

    An MCP tool that raises becomes a transport-level error the caller cannot
    read; a tool that returns its refusal as text is one the caller can act on.
    Both halves of `recall`'s `Result` are therefore rendered, and the rc is
    carried into the message rather than dropped — `NOT_RUN` (an empty store) is
    a different answer from `BAD_REQUEST` (a malformed question), and collapsing
    them is the "never asked" / "answered no" confusion
    `probes-need-a-control-arm.md` rule 4 is about.
    """
    validated = recall.check_recall(recall_argv(arguments))
    if isinstance(validated, Err | External):
        return (f"refused (rc={exit_code(validated)}): {validated.message}", True)

    result = recall.run_recall(validated.value, memory_dir)
    if isinstance(result, Err | External):
        rc = exit_code(result)
        # NOT_RUN is not a failure of the request — it says the store was empty,
        # so nothing was searched. Reported as text, flagged as an error only
        # when the caller actually asked something this server could not do.
        return (f"nothing searched (rc={rc}): {result.message}", rc != Rc.NOT_RUN)

    return (recall.render_json(result.value), False)


def build_server(memory_dir: Path) -> Server:
    """A configured stdio MCP `Server` exposing `recall`.

    ONLY the mcp 2.x construction path is implemented, and that is deliberate.
    graphify's own `_build_server` carries both (`serve.py:2083-2130`) because it
    ships to many environments; this repo pins one, and untested compatibility
    code for a version we do not run is worse than an honest refusal — it reads
    as coverage. `mcp` here is **2.0.0**, where handlers ride the constructor as
    `on_*` callbacks; 1.x bound them by decorator (`server.list_tools()(fn)`).
    If that ever inverts, this raises and names the fix rather than half-working.
    """
    from mcp import types
    from mcp.server import Server

    if hasattr(Server, "list_tools"):
        msg = (
            "mcp looks like 1.x (Server.list_tools exists), but this module targets the "
            "pinned 2.x constructor API. Add the decorator branch — graphify's "
            "`serve.py` _build_server carries both — or re-pin mcp."
        )
        raise RuntimeError(msg)

    tool = types.Tool(
        name=RECALL_TOOL,
        description=_RECALL_DESCRIPTION,
        input_schema=_RECALL_SCHEMA,
    )

    async def _on_list_tools(_ctx: object, _params: object) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[tool])

    async def _on_call_tool(
        _ctx: object, params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        if params.name != RECALL_TOOL:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"unknown tool: {params.name}")],
                is_error=True,
            )
        text, is_error = run_recall_tool(dict(params.arguments or {}), memory_dir)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=text)],
            is_error=is_error,
        )

    return Server(
        SERVER_NAME,
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
    )


def serve(repo_root: Path, argv: Sequence[str] = ()) -> int:
    """Run the `kb-memory` stdio server. Returns an rc; prints NOTHING to stdout."""
    import asyncio

    from mcp.server.stdio import stdio_server

    args = list(argv)
    memory_dir = _memory_dir(repo_root, args)

    server = build_server(memory_dir)

    async def _main() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_main())
    return exit_code(Ok(None))


def _memory_dir(repo_root: Path, argv: Sequence[str]) -> Path:
    """`--memory-dir <path>`, else this repo's committed store.

    The default matches `recall.main`'s exactly — one store, named in two places
    only because the CLI resolves it from a parsed flag and this resolves it from
    raw argv. A divergence here would serve a different corpus than `kb-recall`
    reports, which is the kind of drift nothing would notice.
    """
    args = list(argv)
    if "--memory-dir" in args:
        idx = args.index("--memory-dir")
        if idx + 1 < len(args):
            return Path(args[idx + 1])
    return repo_root / "graphify-out" / "memory"
