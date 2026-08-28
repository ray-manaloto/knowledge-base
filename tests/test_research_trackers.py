# Copyright (c) 2026 Raymond Manaloto
"""Hermetic contract tests for the GitHub trackers research adapter."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import msgspec
import pytest
from kb_setup.generated.research_record import AdapterRecord, Arm, Hit, Kind, Null, Tier
from kb_setup.research import trackers
from kb_setup.result import Err, External, Ok, Rc

FIXTURES = Path(__file__).parent / "fixtures" / "research"
NOW = datetime(2026, 8, 28, 2, 7, 38, tzinfo=UTC)
REPO_JDX = "jdx/hk"
REPO_LYCHEE = "lycheeverse/lychee"

type Reply = str | tuple[int, str, str]
type Runner = Callable[[tuple[str, ...]], tuple[int, str, str]]


def _repo_argv(repo: str) -> tuple[str, ...]:
    return "api", f"repos/{repo}"


def _search_argv(repo: str, kind: str, term: str | None) -> tuple[str, ...]:
    query = f"repo:{repo} is:{kind}"
    if term is not None:
        query = f"{query} {term}"
    return "api", "-X", "GET", "search/issues", "-f", f"q={query}"


def _stub_gh(
    monkeypatch: pytest.MonkeyPatch, responses: dict[tuple[str, ...], Reply]
) -> list[tuple[str, ...]]:
    seen: list[tuple[str, ...]] = []

    def _fake(argv: tuple[str, ...]) -> tuple[int, str, str]:
        seen.append(argv)
        reply = responses[argv]
        if isinstance(reply, tuple):
            return reply
        return 0, (FIXTURES / reply).read_text(encoding="utf-8"), ""

    monkeypatch.setattr(trackers, "_run_gh", _fake)
    return seen


def _record(result: object) -> AdapterRecord:
    assert isinstance(result, Ok)
    assert isinstance(result.value, AdapterRecord)
    return result.value


def _search_with_stub(repo: str, term: str) -> AdapterRecord:
    return _record(trackers.search(repo, term, run=trackers._run_gh, now=NOW))


def test_jdx_search_reads_channels_first_and_searches_only_pull_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    term = "gitleaks"
    seen = _stub_gh(
        monkeypatch,
        {
            _repo_argv(REPO_JDX): "jdx-repo.json",
            _search_argv(REPO_JDX, "pr", term): "jdx-gitleaks-pr.json",
        },
    )

    record = _search_with_stub(REPO_JDX, term)

    assert seen == [_repo_argv(REPO_JDX), _search_argv(REPO_JDX, "pr", term)]
    assert record.has_issues is False
    assert record.has_discussions is True
    assert record.total_count == 9
    assert [hit.kind for hit in record.hits] == [Kind.pr]
    assert record.hits[0].snippet == "First line Second line"
    assert record.null_result is None
    trackers.validate(record)


def test_lychee_preserves_each_search_page_order_and_sums_total_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    term = "python bindings"
    issue = _search_argv(REPO_LYCHEE, "issue", term)
    pull_request = _search_argv(REPO_LYCHEE, "pr", term)
    seen = _stub_gh(
        monkeypatch,
        {
            _repo_argv(REPO_LYCHEE): "lychee-repo.json",
            issue: "lychee-python-bindings-issue.json",
            pull_request: "lychee-python-bindings-pr.json",
        },
    )

    record = _search_with_stub(REPO_LYCHEE, term)

    assert seen == [_repo_argv(REPO_LYCHEE), issue, pull_request]
    assert record.total_count == 3
    assert [hit.kind for hit in record.hits] == [Kind.issue, Kind.pr, Kind.pr]
    assert [hit.url.rsplit("/", maxsplit=1)[-1] for hit in record.hits] == ["2238", "2201", "2199"]
    assert record.hits[2].snippet == record.hits[2].title
    assert record.command == "gh " + " ".join(issue)
    trackers.validate(record)


def test_jdx_null_proves_channel_read_controls_search_and_arms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Realistic red: defaulting has_issues=True must finish, then fail here.

    The issue term and arm fixtures are deliberately present. Removing the
    repository-channel read therefore runs to completion but (a) searches the
    forbidden issue channel, (b) records has_issues=True, and (c) emits an issue
    arm. Each assertion below independently detects one part of that break.
    """
    term = "zzzqqqnotaterm"
    issue_term = _search_argv(REPO_JDX, "issue", term)
    issue_arm = _search_argv(REPO_JDX, "issue", None)
    pr_term = _search_argv(REPO_JDX, "pr", term)
    pr_arm = _search_argv(REPO_JDX, "pr", None)
    seen = _stub_gh(
        monkeypatch,
        {
            _repo_argv(REPO_JDX): "jdx-repo.json",
            issue_term: "jdx-null-issue.json",
            pr_term: "jdx-null-pr.json",
            issue_arm: "jdx-arm-issue.json",
            pr_arm: "jdx-arm-pr.json",
        },
    )

    record = _search_with_stub(REPO_JDX, term)

    assert seen[0] == _repo_argv(REPO_JDX)
    assert issue_term not in seen
    assert issue_arm not in seen
    assert record.has_issues is False
    assert record.null_result is not None
    assert [arm.kind for arm in record.null_result.arms] == [Kind.pr]
    assert record.null_result.arms[0].result == "total_count=1005"
    assert record.null_result.arms[0].discriminates is True
    trackers.validate(record)


def test_null_keeps_a_zero_issue_arm_beside_a_discriminating_pr_arm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = "example/project"
    term = "absent"
    issue_term = _search_argv(repo, "issue", term)
    pr_term = _search_argv(repo, "pr", term)
    issue_arm = _search_argv(repo, "issue", None)
    pr_arm = _search_argv(repo, "pr", None)
    _stub_gh(
        monkeypatch,
        {
            _repo_argv(repo): "synthetic-repo.json",
            issue_term: "synthetic-empty.json",
            pr_term: "synthetic-empty.json",
            issue_arm: "synthetic-empty.json",
            pr_arm: "synthetic-pr-arm.json",
        },
    )

    record = _search_with_stub(repo, term)

    assert record.null_result is not None
    assert [(arm.kind, arm.result, arm.discriminates) for arm in record.null_result.arms] == [
        (Kind.issue, "total_count=0", False),
        (Kind.pr, "total_count=7", True),
    ]
    trackers.validate(record)


def test_untrusted_title_and_fallback_snippet_are_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = "example/project"
    term = "long"
    _stub_gh(
        monkeypatch,
        {
            _repo_argv(repo): "untrusted-repo.json",
            _search_argv(repo, "pr", term): "untrusted-pr.json",
        },
    )

    hit = _search_with_stub(repo, term).hits[0]

    assert len(hit.title) == 512
    assert len(hit.snippet) == 600


@pytest.mark.parametrize(
    ("repo", "term", "message"),
    [
        ("not-a-repo", "x", "OWNER/REPO"),
        ("../..", "x", "dots"),
        (f"{'a' * 101}/repo", "x", "1..100"),
        ("owner/repo", "", "required"),
        ("owner/repo", "is:issue", "must not contain"),
        ("owner/repo", "x" * 201, "at most 200"),
    ],
)
def test_bad_requests_are_typed_without_running_gh(repo: str, term: str, message: str) -> None:
    def _unexpected(_argv: tuple[str, ...]) -> tuple[int, str, str]:
        pytest.fail("gh must not run for a bad request")

    result = trackers.search(repo, term, run=_unexpected, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert message in result.message


@pytest.mark.parametrize("payload", ["<html>rate limited</html>", '{"full_name":"owner/repo"}'])
def test_zero_status_unparsable_payload_fails_closed_as_not_run(payload: str) -> None:
    def _garbage(_argv: tuple[str, ...]) -> tuple[int, str, str]:
        return 0, payload, ""

    result = trackers.search("owner/repo", "term", run=_garbage, now=NOW)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "unparsable payload for `gh api repos/owner/repo`" in result.message


def test_nonzero_gh_status_is_external_and_blank_stderr_gets_a_reason() -> None:
    def _failed(_argv: tuple[str, ...]) -> tuple[int, str, str]:
        return 17, '{"message":"failure"}', "   "

    result = trackers.search("owner/repo", "term", run=_failed, now=NOW)

    assert isinstance(result, External)
    assert result.code == 17
    assert result.message == "gh exited 17 with no stderr"


def test_run_gh_uses_the_bounded_captured_subprocess_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="out", stderr="err")

    monkeypatch.setattr(subprocess, "run", _fake)

    result = trackers._run_gh(("api", "repos/owner/repo"))

    assert result == (0, "out", "err")
    assert captured == {
        "argv": ["gh", "api", "repos/owner/repo"],
        "capture_output": True,
        "text": True,
        "errors": "replace",
        "check": False,
        "timeout": 120,
    }


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("missing"),
        PermissionError("denied"),
        subprocess.TimeoutExpired(["gh"], 120),
    ],
    ids=["missing", "permission", "timeout"],
)
def test_run_gh_maps_start_and_timeout_failures_to_127(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    def _raise(_argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise error

    monkeypatch.setattr(subprocess, "run", _raise)

    returncode, stdout, stderr = trackers._run_gh(("api", "repos/owner/repo"))

    assert returncode == 127
    assert stdout == ""
    assert stderr.startswith("gh: ")


def _contract_record(
    *,
    hits: list[Hit] | None = None,
    null_result: Null | None = None,
    has_issues: bool = False,
) -> AdapterRecord:
    return AdapterRecord(
        adapter="trackers",
        tier=Tier.cheap,
        question="owner/repo term",
        command="gh api -X GET search/issues -f q=repo:owner/repo is:pr term",
        has_issues=has_issues,
        has_discussions=False,
        ran_at="2026-08-28T02:07:38Z",
        total_count=len(hits or []),
        hits=hits or [],
        null_result=null_result,
    )


def test_validate_round_trip_rejects_a_pattern_violation() -> None:
    record = _contract_record(
        hits=[
            Hit(
                url="NOT-A-URL",
                title="title",
                snippet="snippet",
                date="2026-08-28T02:07:38Z",
                kind=Kind.pr,
            )
        ]
    )

    with pytest.raises(msgspec.ValidationError, match="matching regex"):
        trackers.validate(record)


@pytest.mark.parametrize(
    "record",
    [
        _contract_record(),
        _contract_record(
            hits=[
                Hit(
                    url="https://example.test/1",
                    title="title",
                    snippet="snippet",
                    date="2026-08-28T02:07:38Z",
                    kind=Kind.pr,
                )
            ],
            null_result=Null(
                arms=[
                    Arm(
                        kind=Kind.pr,
                        command="gh api -X GET search/issues -f q=repo:owner/repo is:pr",
                        result="total_count=1",
                        discriminates=True,
                    )
                ]
            ),
        ),
    ],
)
def test_validate_requires_exactly_one_payload(record: AdapterRecord) -> None:
    with pytest.raises(msgspec.ValidationError, match="exactly one"):
        trackers.validate(record)


def test_validate_requires_one_unique_arm_per_searched_channel() -> None:
    record = _contract_record(
        has_issues=True,
        null_result=Null(
            arms=[
                Arm(
                    kind=Kind.pr,
                    command="gh api -X GET search/issues -f q=repo:owner/repo is:pr",
                    result="total_count=1",
                    discriminates=True,
                )
            ]
        ),
    )

    with pytest.raises(msgspec.ValidationError, match="one unique arm"):
        trackers.validate(record)


@pytest.mark.parametrize(
    "case",
    [("not-a-count", False), ("total_count=0", True), ("total_count=2", False)],
)
def test_validate_requires_arm_result_and_boolean_to_agree(case: tuple[str, bool]) -> None:
    result, discriminates = case
    record = _contract_record(
        null_result=Null(
            arms=[
                Arm(
                    kind=Kind.pr,
                    command="gh api -X GET search/issues -f q=repo:owner/repo is:pr",
                    result=result,
                    discriminates=discriminates,
                )
            ]
        )
    )

    with pytest.raises(msgspec.ValidationError):
        trackers.validate(record)


def _fix_now(monkeypatch: pytest.MonkeyPatch) -> None:
    original = trackers.search

    def _fixed(repo: str, term: str, *, run: Runner) -> trackers.Result[AdapterRecord]:
        return original(repo, term, run=run, now=NOW)

    monkeypatch.setattr(trackers, "search", _fixed)


def test_main_prints_one_indented_json_document_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    term = "gitleaks"
    _stub_gh(
        monkeypatch,
        {
            _repo_argv(REPO_JDX): "jdx-repo.json",
            _search_argv(REPO_JDX, "pr", term): "jdx-gitleaks-pr.json",
        },
    )
    _fix_now(monkeypatch)

    returncode = trackers.main([REPO_JDX, term], tmp_path)
    captured = capsys.readouterr()

    assert returncode == 0
    assert captured.err == ""
    assert captured.out.startswith('{\n  "adapter": "trackers"')
    decoded = msgspec.json.decode(captured.out, type=AdapterRecord)
    assert decoded.ran_at == "2026-08-28T02:07:38Z"


def test_main_bad_request_keeps_stdout_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    returncode = trackers.main(["not-a-repo", "x"], tmp_path)
    captured = capsys.readouterr()

    assert returncode == 2
    assert captured.out == ""
    assert captured.err.startswith("kb-research-trackers: repository must be OWNER/REPO")


def test_main_external_failure_keeps_child_stdout_off_process_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_gh(
        monkeypatch,
        {
            _repo_argv("owner/missing"): (
                1,
                '{"message":"Not Found","status":"404"}',
                "gh: Not Found (HTTP 404)\n",
            )
        },
    )

    returncode = trackers.main(["owner/missing", "x"], tmp_path)
    captured = capsys.readouterr()

    assert returncode == 1
    assert captured.out == ""
    assert captured.err == "kb-research-trackers: gh: Not Found (HTTP 404)\n"
