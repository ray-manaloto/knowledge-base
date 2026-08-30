# Copyright (c) 2026 Raymond Manaloto
"""Search code across GitHub via grep.app's unauthenticated Streamable-HTTP MCP.

**Transport choice is httpx2, not `mcp2cli`** (fable-advisor consult, this
round). The feasibility spike
(`docs/research/reports/2026-08-29-codesearch-feasibility.md`) proved the
endpoint needs no session negotiation — one stateless POST answers one
`tools/call` — so `mcp2cli`'s subprocess/session machinery buys nothing here
and would replace `packages.py`'s proven `httpx2.MockTransport` test seam
with an unmockable subprocess.

`Hit.date` on every hit this adapter emits is the query's OBSERVATION time
(the record's own `ran_at`), never the code's commit/modification date —
grep.app returns no per-hit date. Do not read it as recency.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import msgspec
from msgspec import UNSET, UnsetType

from kb_setup import events
from kb_setup.generated.research_record import AdapterRecord, Arm, Hit, Kind, Null, Tier
from kb_setup.result import Err, External, Ok, Rc, Result, exit_code

_ENDPOINT = "https://mcp.grep.app"
_HTTP_TIMEOUT = 30.0
_HTTP_OK = 200
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

_MAX_QUERY_LENGTH = 512
_MAX_REPO_LENGTH = 200
_MAX_LANGUAGE_LENGTH = 100
_MAX_COMMAND_LENGTH = 1024
_MAX_TITLE_LENGTH = 512
_MAX_SNIPPET_LENGTH = 600
_MAX_URL_LENGTH = 2048
_MAX_ARM_RESULT_LENGTH = 600
_GITHUB_PREFIX = "https://github.com/"

_NO_RESULTS_TEXT = "No results found for your query."
#: The exact query/language pair the feasibility spike proved returns real
#: content, reused as the null-corroboration control arm (PREMISES P1).
_CONTROL_QUERY = "useState("
_CONTROL_LANGUAGE = "TypeScript"
_EXPECTED_POSITIONAL_ARGS = 1

#: grep.app never returns more than one hit per query (verified live, 7/7
#: samples — PREMISES G1). Only the text at position 0 is ever parsed as a
#: hit header, anchored with `\A` rather than `re.MULTILINE`: nothing after
#: it is ever re-scanned for a second `Repository:`/`Path:`/`URL:` triple, so
#: attacker-controlled snippet content that fakes one is just inert snippet
#: text (truncated like everything else), never a second hit. `License:` is
#: present in all 7 live samples but modeled as optional here — untested-but
#: -safe permissiveness, not an observed variant.
_HIT_RE = re.compile(
    r"\ARepository: (?P<repo>[^\n]+)\n"
    r"Path: (?P<path>[^\n]+)\n"
    r"URL: (?P<url>[^\n]+)\n"
    r"(?:License: [^\n]+\n)?"
    r"\n"
    r"Snippets:\n"
    r"(?P<snippet>.*)",
    re.DOTALL,
)

type _Transport = httpx2.BaseTransport | None


class _McpContent(msgspec.Struct):
    """One content block of a grep.app `tools/call` result."""

    type: str
    text: str


class _McpToolResult(msgspec.Struct, rename="camel"):
    """The `result` object of a grep.app `tools/call` JSON-RPC response."""

    content: list[_McpContent]
    is_error: bool = False


class _McpResponse(msgspec.Struct):
    """The one JSON-RPC response shape this adapter reads.

    `jsonrpc`/`id` are deliberately NOT fields: `msgspec.Struct` decoding
    drops unknown fields, and both are present in real responses (verified
    live, 7/7 samples — PREMISES G2; the feasibility spike's real-hit
    transcript that looked like it omitted them was merely truncated).
    `error` is typed `msgspec.Raw` rather than `str` because a real JSON-RPC
    2.0 error is an OBJECT (`{code, message, data}`), not a bare string; `Raw`
    decodes either shape without raising (verified live, PREMISES G6), and
    its bytes are rendered for the error message in `_mcp_text`.
    """

    result: _McpToolResult | UnsetType = UNSET
    error: msgspec.Raw | UnsetType = UNSET


def _inputs(
    query: str,
    repo: str | None,
    language: str | None,
) -> tuple[str, str | None, str | None] | Err:
    """Normalize admissible codesearch identity or return a typed bad request."""
    normalized_query = query.strip()
    if not normalized_query:
        return Err("a query is required", rc=Rc.BAD_REQUEST)
    if len(normalized_query) > _MAX_QUERY_LENGTH:
        return Err(f"the query must be at most {_MAX_QUERY_LENGTH} characters", rc=Rc.BAD_REQUEST)

    normalized_repo = repo.strip() if repo else None
    if normalized_repo and len(normalized_repo) > _MAX_REPO_LENGTH:
        return Err(f"repo must be at most {_MAX_REPO_LENGTH} characters", rc=Rc.BAD_REQUEST)

    normalized_language = language.strip() if language else None
    if normalized_language and len(normalized_language) > _MAX_LANGUAGE_LENGTH:
        return Err(
            f"language must be at most {_MAX_LANGUAGE_LENGTH} characters",
            rc=Rc.BAD_REQUEST,
        )

    return normalized_query, normalized_repo or None, normalized_language or None


def _display_command(query: str, *, repo: str | None, language: str | None) -> str:
    """Render the secret-free request, truncating the RENDERED string (M3).

    Bounding `query` to 512 chars does not bound the rendered command — a
    512-char query of backslashes renders past `AdapterRecord.command`'s
    1024-char maximum via `!r`. Truncate the result, not just the input.
    """
    parts = [f"POST {_ENDPOINT} searchGitHub query={query!r}"]
    if repo:
        parts.append(f"repo={repo!r}")
    if language:
        parts.append(f"language={language!r}")
    return " ".join(parts)[:_MAX_COMMAND_LENGTH]


def _ran_at(now: datetime | None) -> str:
    """Render an aware instant in the contract's exact UTC `Z` form."""
    instant = datetime.now(UTC) if now is None else now
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return instant.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _post(
    client: httpx2.Client,
    query: str,
    *,
    repo: str | None,
    language: str | None,
    command: str,
) -> httpx2.Response | Err:
    """Issue one bounded `tools/call` POST, mapping transport failures to NOT_RUN."""
    arguments: dict[str, object] = {"query": query}
    if repo:
        arguments["repo"] = repo
    if language:
        # The upstream tool schema declares `language` as an ARRAY (PREMISES
        # M1); a bare scalar is rejected by its `additionalProperties: false`.
        arguments["language"] = [language]
    try:
        return client.post(
            _ENDPOINT,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "searchGitHub", "arguments": arguments},
            },
            headers=_HEADERS,
        )
    except httpx2.TransportError as exc:
        return Err(f"grep.app request failed for `{command}`: {exc}", rc=Rc.NOT_RUN)


_JSON_CONTENT_TYPE = "application/json"
_DATA_PREFIX = "data:"


def _sse_data_lines(chunk: str) -> list[str]:
    """Strip an optional single space after `data:` (the SSE spec makes it optional)."""
    return [
        line[len(_DATA_PREFIX) :].removeprefix(" ")
        for line in chunk.splitlines()
        if line.startswith(_DATA_PREFIX)
    ]


def _joined_sse_payload(response: httpx2.Response, command: str) -> str | Err:
    """Collect the LAST SSE event's `data:` line(s), or read a plain JSON body.

    Never confirmed live (7/7 samples were `text/event-stream`) but permitted
    by this adapter's own `Accept` header and the MCP Streamable HTTP spec —
    a defensive path, not a proven one.
    """
    content_type = response.headers.get("content-type", "")
    if content_type.split(";", 1)[0].strip() == _JSON_CONTENT_TYPE:
        return response.text

    # A real response terminates with its own blank line
    # ("event: message\ndata: {...}\n\n" — PREMISES G5), so a naive
    # `text.split("\n\n")[-1]` yields an empty trailing chunk on every real
    # call. Take the last chunk that actually carries a `data:` line instead.
    chunks = [chunk for chunk in response.text.split("\n\n") if chunk.strip()]
    for chunk in reversed(chunks):
        lines = _sse_data_lines(chunk)
        if lines:
            return "\n".join(lines)
    return Err(
        f"grep.app returned a non-SSE response for `{command}`: {response.text[:200]!r}",
        rc=Rc.NOT_RUN,
    )


def _decode_mcp_response(joined: str, command: str) -> _McpResponse | Err:
    """Decode one joined SSE payload as the one JSON-RPC shape this adapter reads."""
    try:
        return msgspec.json.decode(joined, type=_McpResponse)
    except (msgspec.DecodeError, msgspec.ValidationError) as exc:
        return Err(f"grep.app returned an unparsable payload for `{command}`: {exc}", rc=Rc.NOT_RUN)


def _mcp_text(parsed: _McpResponse, command: str) -> str | Err:
    """Extract the concatenated text content, or fail on either error shape."""
    if not isinstance(parsed.error, UnsetType):
        # bytes(raw) for a bare-string error retains its JSON quotes
        # (`"boom"` -> `'"boom"'`), which is fine here: this is a rendered
        # message, not a value compared for equality (PREMISES G6).
        error_text = bytes(parsed.error).decode("utf-8", errors="replace")
        return Err(f"grep.app returned an error for `{command}`: {error_text}", rc=Rc.NOT_RUN)
    if isinstance(parsed.result, UnsetType):
        return Err(f"grep.app returned an error for `{command}`: no result", rc=Rc.NOT_RUN)
    text = "".join(entry.text for entry in parsed.result.content if entry.type == "text")
    if parsed.result.is_error:
        return Err(f"grep.app returned an error for `{command}`: {text}", rc=Rc.NOT_RUN)
    return text


def _search_once(
    client: httpx2.Client,
    query: str,
    *,
    repo: str | None,
    language: str | None,
) -> tuple[str, str] | Err:
    """Issue one `searchGitHub` call and return `(command, joined_text)`."""
    command = _display_command(query, repo=repo, language=language)
    response = _post(client, query, repo=repo, language=language, command=command)
    if isinstance(response, Err):
        return response
    if response.status_code != _HTTP_OK:
        return Err(
            f"grep.app returned HTTP {response.status_code} for `{command}`",
            rc=Rc.NOT_RUN,
        )
    joined = _joined_sse_payload(response, command)
    if isinstance(joined, Err):
        return joined
    parsed = _decode_mcp_response(joined, command)
    if isinstance(parsed, Err):
        return parsed
    text = _mcp_text(parsed, command)
    if isinstance(text, Err):
        return text
    return command, text


def _parse_hits(text: str, ran_at: str) -> list[Hit]:
    """Parse the single hit anchored at position 0, or return no hits.

    grep.app never returns more than one hit per query (verified live, 7/7
    samples — PREMISES G1). Only the text at position 0 is ever read as a
    hit header; anything after it — including a forged
    `Repository:`/`Path:`/`URL:` triple embedded in the snippet — is inert
    snippet text, never re-interpreted as a second hit.
    """
    match = _HIT_RE.match(text)
    if match is None:
        return []
    url = match.group("url").strip()
    if not url.startswith(_GITHUB_PREFIX) or len(url) > _MAX_URL_LENGTH:
        return []

    repo_name = match.group("repo").strip()
    path = match.group("path").strip()
    snippet = match.group("snippet").strip()

    return [
        Hit(
            url=url,
            title=f"{repo_name} — {path}"[:_MAX_TITLE_LENGTH],
            snippet=snippet[:_MAX_SNIPPET_LENGTH],
            date=ran_at,
            kind=Kind.codesearch,
        )
    ]


def _null_record(
    client: httpx2.Client,
    identity: tuple[str, str | None, str | None],
    command: str,
    now: datetime | None,
) -> Result[AdapterRecord]:
    """Corroborate a "no results" text with the fixed known-good control QUERY.

    `identity` is the caller's own `(query, repo, language)`. The control
    keeps `repo`/`language` — the dimension that could actually have caused
    the null — and swaps in only the query, the one dimension proven live to
    return real content. Using a fixed, unrelated language here would
    discriminate the wrong thing: a caller's typo'd `--repo` or obscure
    `--language` would always read as "confirmed empty" even though the
    control never tested that filter. When the caller passed no language at
    all, fall back to `_CONTROL_LANGUAGE` (unchanged from prior behavior) so
    the control still has a known-good pairing with `_CONTROL_QUERY`; there
    is no equivalent default for `repo`.
    """
    query, repo, language = identity
    control_language = language if language is not None else _CONTROL_LANGUAGE
    control = _search_once(client, _CONTROL_QUERY, repo=repo, language=control_language)
    if isinstance(control, Err):
        return control
    control_command, control_text = control
    discriminates = control_text != _NO_RESULTS_TEXT
    arm_result = (control_text if discriminates else _NO_RESULTS_TEXT)[:_MAX_ARM_RESULT_LENGTH]

    return Ok(
        AdapterRecord(
            adapter="codesearch",
            tier=Tier.cheap,
            question=query,
            command=command,
            trackers=None,
            links=None,
            packages=None,
            ran_at=_ran_at(now),
            total_count=0,
            hits=[],
            null_result=Null(
                arms=[
                    Arm(
                        kind=Kind.codesearch,
                        command=control_command,
                        result=arm_result,
                        discriminates=discriminates,
                    )
                ]
            ),
        )
    )


def search(
    query: str,
    *,
    repo: str | None = None,
    language: str | None = None,
    transport: _Transport = None,
    now: datetime | None = None,
) -> Result[AdapterRecord]:
    """Search GitHub code via grep.app and return a control-armed record."""
    inputs = _inputs(query, repo, language)
    if isinstance(inputs, Err):
        return inputs
    normalized_query, normalized_repo, normalized_language = inputs

    with httpx2.Client(transport=transport, timeout=_HTTP_TIMEOUT) as client:
        primary = _search_once(
            client,
            normalized_query,
            repo=normalized_repo,
            language=normalized_language,
        )
        if isinstance(primary, Err):
            return primary
        command, text = primary
        ran_at = _ran_at(now)

        if text.strip() == _NO_RESULTS_TEXT:
            return _null_record(
                client,
                (normalized_query, normalized_repo, normalized_language),
                command,
                now,
            )

        hits = _parse_hits(text, ran_at)
        if not hits:
            # A silent upstream prose-format change must surface as a
            # failure, never as a plausible-looking empty success.
            return Err(
                f"grep.app returned unparsable codesearch content for `{command}`",
                rc=Rc.NOT_RUN,
            )

        return Ok(
            AdapterRecord(
                adapter="codesearch",
                tier=Tier.cheap,
                question=normalized_query,
                command=command,
                trackers=None,
                links=None,
                packages=None,
                ran_at=ran_at,
                total_count=len(hits),
                hits=hits,
                null_result=None,
            )
        )


def _validate_presence(record: AdapterRecord) -> None:
    """Require exactly one codesearch outcome: hits or corroborated null."""
    has_hits = bool(record.hits)
    has_null = record.null_result is not None
    if has_hits == has_null:
        raise msgspec.ValidationError("exactly one of hits or null_result must be present")


def _validate_null(record: AdapterRecord) -> None:
    """Pin a codesearch null to one codesearch-kind control arm."""
    if record.null_result is None:
        return
    arms = record.null_result.arms
    if len(arms) != 1 or arms[0].kind is not Kind.codesearch:
        raise msgspec.ValidationError(
            "a codesearch null_result must have exactly one codesearch arm"
        )


def validate(record: AdapterRecord) -> None:
    """Enforce generated-field and semantic cross-field contract invariants."""
    msgspec.json.decode(msgspec.json.encode(record), type=AdapterRecord)

    if record.adapter != "codesearch":
        return
    if record.trackers is not None:
        raise msgspec.ValidationError("a codesearch record must not carry trackers")
    if record.links is not None:
        raise msgspec.ValidationError("a codesearch record must not carry links")
    if record.packages is not None:
        raise msgspec.ValidationError("a codesearch record must not carry packages")
    if record.total_count != len(record.hits):
        raise msgspec.ValidationError("total_count must equal the number of hits")
    for hit in record.hits:
        if hit.kind is not Kind.codesearch:
            raise msgspec.ValidationError("every codesearch hit must have kind=codesearch")
        if not hit.url.startswith(_GITHUB_PREFIX):
            raise msgspec.ValidationError("every codesearch hit url must be a github.com URL")
        if hit.date != record.ran_at:
            raise msgspec.ValidationError("every codesearch hit date must equal ran_at")

    _validate_presence(record)
    _validate_null(record)


def _parse_argv(argv: list[str]) -> tuple[list[str], str | None, str | None, Path | None] | Err:
    """Split argv into positionals plus `--out`/`--repo`/`--language`, any order."""
    positionals: list[str] = []
    out_path: Path | None = None
    repo: str | None = None
    language: str | None = None
    flags = {"--out": "a path", "--repo": "a value", "--language": "a value"}
    i = 0
    while i < len(argv):
        flag = argv[i]
        if flag in flags:
            if i + 1 >= len(argv):
                return Err(f"{flag} requires {flags[flag]}", rc=Rc.BAD_REQUEST)
            value = argv[i + 1]
            if flag == "--out":
                out_path = Path(value)
            elif flag == "--repo":
                repo = value
            else:
                language = value
            i += 2
            continue
        positionals.append(flag)
        i += 1
    return positionals, repo, language, out_path


def _outcome(result: Err | External) -> str:
    """Map a failed `Result` onto the telemetry outcome vocabulary."""
    if isinstance(result, External):
        return "external"
    if result.rc is Rc.BAD_REQUEST:
        return "bad_request"
    if result.rc is Rc.NOT_RUN:
        return "not_run"
    return "error"


def main(argv: list[str], repo_root: Path) -> int:
    """Print one validated codesearch record, or write it to `--out PATH`."""
    del repo_root
    parsed = _parse_argv(argv)
    if isinstance(parsed, Err):
        events.fail(
            "codesearch.bad_argv",
            f"kb-research-codesearch: {parsed.message}",
            adapter="codesearch",
            outcome="bad_request",
        )
        return exit_code(parsed)
    positionals, repo, language, out_path = parsed

    event_query = positionals[0][:_MAX_QUERY_LENGTH] if positionals else ""
    event_repo = repo[:_MAX_REPO_LENGTH] if repo else ""
    event_language = language[:_MAX_LANGUAGE_LENGTH] if language else ""
    started_at = time.perf_counter()
    result: Result[AdapterRecord]
    if len(positionals) != _EXPECTED_POSITIONAL_ARGS:
        result = Err("expected <query>", rc=Rc.BAD_REQUEST)
    else:
        result = search(positionals[0], repo=repo, language=language)
    duration_s = time.perf_counter() - started_at
    if not isinstance(result, Ok):
        events.fail(
            "codesearch.search_failed",
            f"kb-research-codesearch: {result.message}",
            adapter="codesearch",
            query=event_query,
            repo=event_repo,
            language=event_language,
            duration_s=duration_s,
            outcome=_outcome(result),
        )
        return exit_code(result)

    record = result.value
    validate(record)
    text = msgspec.json.format(msgspec.json.encode(record).decode(), indent=2)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n")
        events.say(
            "codesearch.wrote",
            f"[aggregated-research] wrote {out_path}",
            adapter="codesearch",
            query=event_query,
            repo=event_repo,
            language=event_language,
            duration_s=duration_s,
            outcome="ok",
            path=out_path,
        )
    else:
        events.say(
            "codesearch.result",
            text,
            adapter="codesearch",
            query=event_query,
            repo=event_repo,
            language=event_language,
            duration_s=duration_s,
            outcome="ok",
        )
    return exit_code(result)
