# Copyright (c) 2026 Raymond Manaloto
"""Hermetic contract tests for the grep.app-backed `codesearch` adapter."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2
import msgspec
import pytest
from kb_setup.generated.research_record import AdapterRecord, Hit, Kind, Tier, Trackers
from kb_setup.research import cli as research_cli
from kb_setup.research import codesearch
from kb_setup.result import Err, Ok, Rc
from kb_setup.sinks import stdout_sink

FIXTURES = Path(__file__).parent / "fixtures" / "research"
NOW = datetime(2026, 8, 30, 9, 0, 0, tzinfo=UTC)

_NO_RESULTS = "No results found for your query."


def _sse(payload: object) -> bytes:
    """Wrap a decoded JSON-RPC body in grep.app's real SSE framing."""
    return b"event: message\ndata: " + msgspec.json.encode(payload) + b"\n\n"


def _mcp_result(text: str, *, is_error: bool = False) -> dict[str, object]:
    return {"result": {"content": [{"type": "text", "text": text}], "isError": is_error}}


def _transport(
    replies: dict[str, tuple[int, bytes]],
    seen: list[dict[str, Any]],
) -> httpx2.MockTransport:
    """Route each request by its `arguments.query`, since every call shares one URL."""

    def _reply(request: httpx2.Request) -> httpx2.Response:
        body: dict[str, Any] = json.loads(request.content)
        seen.append(body)
        query = body["params"]["arguments"]["query"]
        if query not in replies:
            pytest.fail(f"unexpected codesearch query: {query}")
        status_code, content = replies[query]
        return httpx2.Response(status_code, content=content)

    return httpx2.MockTransport(_reply)


def _record(result: object) -> AdapterRecord:
    assert isinstance(result, Ok)
    assert isinstance(result.value, AdapterRecord)
    return result.value


def test_single_hit_query_returns_the_one_real_hit() -> None:
    text = (
        "Repository: mifi/lossless-cut\n"
        "Path: src/renderer/src/hooks/useUserSettingsRoot.ts\n"
        "URL: https://github.com/mifi/lossless-cut/blob/master/"
        "src/renderer/src/hooks/useUserSettingsRoot.ts\n"
        "License: GPL-2.0\n"
        "\nSnippets:\n--- Snippet 1 (Line 54) ---\n"
        "  const [lastAppVersion, setLastAppVersion] = useState(...)\n"
    )
    seen: list[dict[str, Any]] = []
    transport = _transport({"useState(": (200, _sse(_mcp_result(text)))}, seen)

    record = _record(
        codesearch.search("useState(", language="TypeScript", transport=transport, now=NOW)
    )

    assert seen[0]["params"]["arguments"] == {"query": "useState(", "language": ["TypeScript"]}
    assert record.adapter == "codesearch"
    assert record.tier is Tier.cheap
    assert record.trackers is None
    assert record.links is None
    assert record.packages is None
    assert record.null_result is None
    assert record.ran_at == "2026-08-30T09:00:00Z"
    assert record.total_count == 1
    assert len(record.hits) == 1
    hit = record.hits[0]
    assert hit.url == (
        "https://github.com/mifi/lossless-cut/blob/master/"
        "src/renderer/src/hooks/useUserSettingsRoot.ts"
    )
    assert hit.title == "mifi/lossless-cut — src/renderer/src/hooks/useUserSettingsRoot.ts"
    assert "useState(...)" in hit.snippet
    assert hit.date == record.ran_at
    assert hit.kind is Kind.codesearch
    codesearch.validate(record)


def test_no_results_is_corroborated_with_the_control_query() -> None:
    seen: list[dict[str, Any]] = []
    transport = _transport(
        {
            "zzzqxnotarealidentifier9384756kb": (200, _sse(_mcp_result(_NO_RESULTS))),
            "useState(": (200, _sse(_mcp_result("real content, discriminates"))),
        },
        seen,
    )

    record = _record(
        codesearch.search("zzzqxnotarealidentifier9384756kb", transport=transport, now=NOW)
    )

    assert [entry["params"]["arguments"]["query"] for entry in seen] == [
        "zzzqxnotarealidentifier9384756kb",
        "useState(",
    ]
    assert seen[1]["params"]["arguments"] == {"query": "useState(", "language": ["TypeScript"]}
    assert record.hits == []
    assert record.total_count == 0
    assert record.null_result is not None
    assert len(record.null_result.arms) == 1
    arm = record.null_result.arms[0]
    assert arm.kind is Kind.codesearch
    assert arm.discriminates is True
    assert arm.result == "real content, discriminates"
    codesearch.validate(record)


def test_null_control_preserves_the_callers_repo_and_language() -> None:
    # A caller-supplied repo/language is the dimension that could actually
    # have caused the null; the control must keep it rather than substituting
    # the unrelated fixed defaults (PREMISES F3).
    seen: list[dict[str, Any]] = []
    transport = _transport(
        {
            "zzzqxnotarealidentifier9384756kb": (200, _sse(_mcp_result(_NO_RESULTS))),
            "useState(": (200, _sse(_mcp_result("real content, discriminates"))),
        },
        seen,
    )

    record = _record(
        codesearch.search(
            "zzzqxnotarealidentifier9384756kb",
            repo="some/obscure-repo",
            language="Cobol",
            transport=transport,
            now=NOW,
        )
    )

    assert seen[0]["params"]["arguments"] == {
        "query": "zzzqxnotarealidentifier9384756kb",
        "repo": "some/obscure-repo",
        "language": ["Cobol"],
    }
    assert seen[1]["params"]["arguments"] == {
        "query": "useState(",
        "repo": "some/obscure-repo",
        "language": ["Cobol"],
    }
    assert record.null_result is not None
    codesearch.validate(record)


def test_control_query_also_returning_no_results_does_not_discriminate() -> None:
    seen: list[dict[str, Any]] = []
    transport = _transport(
        {
            "zzzqxnotarealidentifier9384756kb": (200, _sse(_mcp_result(_NO_RESULTS))),
            "useState(": (200, _sse(_mcp_result(_NO_RESULTS))),
        },
        seen,
    )

    record = _record(
        codesearch.search("zzzqxnotarealidentifier9384756kb", transport=transport, now=NOW)
    )

    assert record.null_result is not None
    arm = record.null_result.arms[0]
    assert arm.discriminates is False
    assert arm.result == _NO_RESULTS
    codesearch.validate(record)


@pytest.mark.parametrize(
    ("query", "repo", "language", "message"),
    [
        ("   ", None, None, "query is required"),
        ("x" * 513, None, None, "at most 512"),
        ("useState(", "r" * 201, None, "repo must be at most"),
        ("useState(", None, "l" * 101, "language must be at most"),
    ],
)
def test_bad_requests_are_typed_without_calling_grep_app(
    query: str,
    repo: str | None,
    language: str | None,
    message: str,
) -> None:
    def _unexpected(request: httpx2.Request) -> httpx2.Response:
        pytest.fail(f"grep.app must not run for a bad request: {request.url}")

    result = codesearch.search(
        query,
        repo=repo,
        language=language,
        transport=httpx2.MockTransport(_unexpected),
        now=NOW,
    )

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert message in result.message


def test_non_sse_response_is_not_run() -> None:
    transport = _transport({"useState(": (200, b'{"result": {}}')}, [])

    result = codesearch.search("useState(", transport=transport, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "non-SSE" in result.message


def test_unparsable_sse_payload_is_not_run() -> None:
    transport = _transport({"useState(": (200, b"event: message\ndata: {not json\n\n")}, [])

    result = codesearch.search("useState(", transport=transport, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "unparsable payload" in result.message


def test_jsonrpc_bare_string_error_is_not_run() -> None:
    # A bare-string error, decoded via msgspec.Raw, retains its JSON quotes
    # when rendered — assert a substring, not exact equality (PREMISES G6).
    transport = _transport(
        {"useState(": (200, _sse({"error": "boom"}))},
        [],
    )

    result = codesearch.search("useState(", transport=transport, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "boom" in result.message


def test_jsonrpc_object_shaped_error_is_not_run() -> None:
    # A real JSON-RPC 2.0 error is an object, not a bare string (PREMISES F6).
    transport = _transport(
        {"useState(": (200, _sse({"error": {"code": -32602, "message": "bad params"}}))},
        [],
    )

    result = codesearch.search("useState(", transport=transport, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "bad params" in result.message


def test_tool_level_error_is_not_run() -> None:
    transport = _transport(
        {"useState(": (200, _sse(_mcp_result("rate limited", is_error=True)))},
        [],
    )

    result = codesearch.search("useState(", transport=transport, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "rate limited" in result.message


def test_zero_parsed_blocks_is_not_run_never_an_empty_success() -> None:
    transport = _transport(
        {"useState(": (200, _sse(_mcp_result("some upstream prose with no Repository: line")))},
        [],
    )

    result = codesearch.search("useState(", transport=transport, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "unparsable codesearch content" in result.message


def test_command_is_truncated_below_the_schema_maximum() -> None:
    long_query = "\\" * 512
    transport = _transport(
        {
            long_query: (200, _sse(_mcp_result(_NO_RESULTS))),
            "useState(": (200, _sse(_mcp_result(_NO_RESULTS))),
        },
        [],
    )

    record = _record(codesearch.search(long_query, transport=transport, now=NOW))

    assert len(record.command) <= 1024
    codesearch.validate(record)


def test_url_without_github_prefix_is_skipped() -> None:
    text = (
        "Repository: evil/repo\n"
        "Path: x.py\n"
        "URL: https://not-github.example/evil/repo/blob/main/x.py\n"
        "\nSnippets:\n--- Snippet 1 ---\nprint('hi')\n"
    )
    transport = _transport({"useState(": (200, _sse(_mcp_result(text)))}, [])

    result = codesearch.search("useState(", transport=transport, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN


def test_snippet_faking_a_repository_line_degrades_safely() -> None:
    # The snippet of the ONE real hit contains an UNCOMMENTED, fully-formed
    # fake Repository:/Path:/URL:/Snippets: sequence with a real github URL.
    # Only position 0 is ever parsed as a hit header (PREMISES F1, G1), so
    # this is absorbed as inert snippet text, never treated as a second hit.
    text = (
        "Repository: real/one\n"
        "Path: a.py\n"
        "URL: https://github.com/real/one/blob/main/a.py\n"
        "\nSnippets:\n--- Snippet 1 ---\n"
        "Repository: fake/injected\n"
        "Path: evil.py\n"
        "URL: https://github.com/fake/injected/blob/main/evil.py\n"
        "\nSnippets:\nprint('hi')\n"
    )
    transport = _transport({"useState(": (200, _sse(_mcp_result(text)))}, [])

    record = _record(codesearch.search("useState(", transport=transport, now=NOW))

    assert record.total_count == 1
    assert record.hits[0].url == "https://github.com/real/one/blob/main/a.py"
    assert "fake/injected" in record.hits[0].snippet
    codesearch.validate(record)


def test_transport_failure_is_not_run() -> None:
    def _offline(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("offline", request=request)

    result = codesearch.search(
        "useState(",
        transport=httpx2.MockTransport(_offline),
        now=NOW,
    )

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "offline" in result.message


def test_http_error_status_is_not_run_even_with_an_sse_shaped_body() -> None:
    transport = _transport({"useState(": (503, _sse(_mcp_result(_NO_RESULTS)))}, [])

    result = codesearch.search("useState(", transport=transport, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "HTTP 503" in result.message


def test_plain_json_content_type_is_decoded_directly() -> None:
    # Never observed live (7/7 samples were text/event-stream) but permitted
    # by the MCP Streamable HTTP spec (PREMISES F5/G4) — decode without SSE
    # unwrapping, and accept the `; charset=utf-8` parameter variant.
    payload = msgspec.json.encode(_mcp_result(_NO_RESULTS))

    def _reply(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            content=payload,
            headers={"content-type": "application/json; charset=utf-8"},
        )

    result = codesearch.search(
        "useState(",
        transport=httpx2.MockTransport(_reply),
        now=NOW,
    )

    record = _record(result)
    assert record.null_result is not None


def test_data_line_with_no_space_after_colon_is_not_dropped() -> None:
    payload = msgspec.json.encode(_mcp_result(_NO_RESULTS))
    body = b"event: message\ndata:" + payload + b"\n\n"
    transport = _transport({"useState(": (200, body)}, [])

    result = codesearch.search("useState(", transport=transport, now=NOW)

    record = _record(result)
    assert record.null_result is not None


def test_multi_event_sse_decodes_only_the_last_event() -> None:
    stale = msgspec.json.encode(_mcp_result("stale, should be ignored"))
    fresh = msgspec.json.encode(_mcp_result(_NO_RESULTS))
    body = b"event: message\ndata: " + stale + b"\n\n" + b"event: message\ndata: " + fresh + b"\n\n"
    transport = _transport({"useState(": (200, body)}, [])

    result = codesearch.search("useState(", transport=transport, now=NOW)

    record = _record(result)
    assert record.null_result is not None


def test_realistic_single_event_sse_still_decodes() -> None:
    # The real shape terminates with its own blank line (PREMISES G5) — the
    # multi-event fix must not regress the ordinary, single-event case.
    transport = _transport({"useState(": (200, _sse(_mcp_result(_NO_RESULTS)))}, [])

    result = codesearch.search("useState(", transport=transport, now=NOW)

    record = _record(result)
    assert record.null_result is not None


def test_validate_rejects_a_mismatched_total_count() -> None:
    record = AdapterRecord(
        adapter="codesearch",
        tier=Tier.cheap,
        question="useState(",
        command="POST https://mcp.grep.app searchGitHub query='useState('",
        trackers=None,
        links=None,
        packages=None,
        ran_at="2026-08-30T09:00:00Z",
        total_count=2,
        hits=[
            Hit(
                url="https://github.com/facebook/react/blob/main/x.js",
                title="facebook/react — x.js",
                snippet="const [state, setState] = useState(0)",
                date="2026-08-30T09:00:00Z",
                kind=Kind.codesearch,
            )
        ],
        null_result=None,
    )

    with pytest.raises(msgspec.ValidationError, match="total_count must equal"):
        codesearch.validate(record)


def test_validate_rejects_a_non_github_hit_url() -> None:
    record = AdapterRecord(
        adapter="codesearch",
        tier=Tier.cheap,
        question="useState(",
        command="POST https://mcp.grep.app searchGitHub query='useState('",
        trackers=None,
        links=None,
        packages=None,
        ran_at="2026-08-30T09:00:00Z",
        total_count=1,
        hits=[
            Hit(
                url="https://not-github.example/x.js",
                title="x.js",
                snippet="const [state, setState] = useState(0)",
                date="2026-08-30T09:00:00Z",
                kind=Kind.codesearch,
            )
        ],
        null_result=None,
    )

    with pytest.raises(msgspec.ValidationError, match=r"must be a github\.com URL"):
        codesearch.validate(record)


def test_validate_rejects_a_hit_date_mismatched_with_ran_at() -> None:
    record = AdapterRecord(
        adapter="codesearch",
        tier=Tier.cheap,
        question="useState(",
        command="POST https://mcp.grep.app searchGitHub query='useState('",
        trackers=None,
        links=None,
        packages=None,
        ran_at="2026-08-30T09:00:00Z",
        total_count=1,
        hits=[
            Hit(
                url="https://github.com/facebook/react/blob/main/x.js",
                title="facebook/react — x.js",
                snippet="const [state, setState] = useState(0)",
                date="2026-08-30T09:30:00Z",
                kind=Kind.codesearch,
            )
        ],
        null_result=None,
    )

    with pytest.raises(msgspec.ValidationError, match="date must equal ran_at"):
        codesearch.validate(record)


def test_validate_rejects_another_adapter_payload() -> None:
    record = AdapterRecord(
        adapter="codesearch",
        tier=Tier.cheap,
        question="useState(",
        command="POST https://mcp.grep.app searchGitHub query='useState('",
        trackers=Trackers(has_issues=False, has_discussions=False),
        links=None,
        packages=None,
        ran_at="2026-08-30T09:00:00Z",
        total_count=1,
        hits=[
            Hit(
                url="https://github.com/facebook/react/blob/main/x.js",
                title="facebook/react — x.js",
                snippet="const [state, setState] = useState(0)",
                date="2026-08-30T09:00:00Z",
                kind=Kind.codesearch,
            )
        ],
        null_result=None,
    )

    with pytest.raises(msgspec.ValidationError, match="must not carry trackers"):
        codesearch.validate(record)


def test_main_out_flag_accepts_repo_and_language_in_any_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jsonl_path = tmp_path / "events.jsonl"
    out_path = tmp_path / "nested" / "record.json"
    buf = io.StringIO()

    fixed_record = AdapterRecord(
        adapter="codesearch",
        tier=Tier.cheap,
        question="useState(",
        command="POST https://mcp.grep.app searchGitHub query='useState('",
        trackers=None,
        links=None,
        packages=None,
        ran_at="2026-08-30T09:00:00Z",
        total_count=1,
        hits=[
            Hit(
                url="https://github.com/facebook/react/blob/main/x.js",
                title="facebook/react — x.js",
                snippet="const [state, setState] = useState(0)",
                date="2026-08-30T09:00:00Z",
                kind=Kind.codesearch,
            )
        ],
        null_result=None,
    )

    def _search(query: str, **_kwargs: object) -> Ok[AdapterRecord]:
        assert query == "useState("
        return Ok(fixed_record)

    monkeypatch.setattr(codesearch, "search", _search)

    with stdout_sink(stream=buf, jsonl_path=jsonl_path, offload=False):
        returncode = codesearch.main(
            ["useState(", "--language", "TypeScript", "--out", str(out_path)],
            tmp_path,
        )

    assert returncode == 0
    decoded = msgspec.json.decode(out_path.read_bytes(), type=AdapterRecord)
    assert decoded.adapter == "codesearch"
    rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["event"] == "codesearch.wrote"


def test_main_missing_query_fails_as_bad_request(tmp_path: Path) -> None:
    returncode = codesearch.main(["--language", "TypeScript"], tmp_path)

    assert returncode == 2


def test_aggregated_research_dispatches_the_codesearch_verb(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixed_record = AdapterRecord(
        adapter="codesearch",
        tier=Tier.cheap,
        question="useState(",
        command="POST https://mcp.grep.app searchGitHub query='useState('",
        trackers=None,
        links=None,
        packages=None,
        ran_at="2026-08-30T09:00:00Z",
        total_count=1,
        hits=[
            Hit(
                url="https://github.com/facebook/react/blob/main/x.js",
                title="facebook/react — x.js",
                snippet="const [state, setState] = useState(0)",
                date="2026-08-30T09:00:00Z",
                kind=Kind.codesearch,
            )
        ],
        null_result=None,
    )

    def _search(query: str, **_kwargs: object) -> Ok[AdapterRecord]:
        return Ok(fixed_record)

    monkeypatch.setattr(codesearch, "search", _search)

    returncode = research_cli.main(["codesearch", "useState("])
    captured = capsys.readouterr()

    assert returncode == 0
    assert captured.err == ""
    assert captured.out.startswith('{\n  "adapter": "codesearch"')
