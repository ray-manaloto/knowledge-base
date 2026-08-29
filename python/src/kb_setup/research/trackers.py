# Copyright (c) 2026 Raymond Manaloto
"""Search GitHub issue and pull-request trackers with armed null results."""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import msgspec

from kb_setup import events
from kb_setup.generated.research_record import AdapterRecord, Arm, Hit, Kind, Null, Tier
from kb_setup.result import Err, External, Ok, Rc, Result, exit_code, external_from_returncode

_GH_TIMEOUT = 120
_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_ONLY_DOTS = re.compile(r"^\.+$")
_ARM_RESULT = re.compile(r"^total_count=([0-9]+)$")
_MAX_TERM_LENGTH = 200
_MAX_TITLE_LENGTH = 512
_MAX_SNIPPET_LENGTH = 600

type _GhRunner = Callable[[tuple[str, ...]], tuple[int, str, str]]


class _RepoResponse(msgspec.Struct):
    """The channel facts read from ``gh api repos/OWNER/REPO``."""

    has_issues: bool
    has_discussions: bool


class _SearchItem(msgspec.Struct):
    """The GitHub search fields used to construct one bounded hit."""

    html_url: str
    title: str
    body: str | None
    updated_at: str
    pull_request: dict[str, object] | None = None


class _SearchResponse(msgspec.Struct):
    """One page and its full GitHub search result count."""

    total_count: int
    items: list[_SearchItem]


def _run_gh(argv: tuple[str, ...]) -> tuple[int, str, str]:
    """Run one bounded ``gh`` call and keep both child streams captured."""
    try:
        process = subprocess.run(
            ["gh", *argv],
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=_GH_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", f"gh: {exc}"
    return process.returncode, process.stdout or "", process.stderr or ""


def _request[T](
    argv: tuple[str, ...], response_type: type[T], run: _GhRunner
) -> T | External | Err:
    """Run one GitHub request, preserving the subprocess's non-zero status.

    A zero-status payload that is not the expected JSON (an HTML error page, a
    truncated body) is NOT a gh failure and NOT a record: it fails closed as
    ``Err(rc=Rc.NOT_RUN)`` — the question was never answered — mirroring
    ``kb_setup.pr.checks_state`` on an unparsable payload.
    """
    returncode, stdout, stderr = run(argv)
    if returncode != 0:
        message = stderr.strip() or f"gh exited {returncode} with no stderr"
        return external_from_returncode(returncode, message)
    try:
        return msgspec.json.decode(stdout, type=response_type)
    except (msgspec.DecodeError, msgspec.ValidationError) as exc:
        return Err(
            f"gh returned an unparsable payload for `{_display_command(argv)}`: {exc}",
            rc=Rc.NOT_RUN,
        )


def _search_argv(repo: str, kind: Kind, term: str | None) -> tuple[str, ...]:
    """Build the single allowed GitHub tracker-search command shape."""
    query = f"repo:{repo} is:{kind.value}"
    if term is not None:
        query = f"{query} {term}"
    return ("api", "-X", "GET", "search/issues", "-f", f"q={query}")


def _display_command(argv: tuple[str, ...]) -> str:
    """Render the exact secret-free child argv for the contract record."""
    return " ".join(("gh", *argv))


def _hit(item: _SearchItem) -> Hit:
    """Convert one untrusted GitHub item into a bounded contract hit."""
    raw_title = item.title
    title = raw_title[:_MAX_TITLE_LENGTH]
    snippet_source = item.body or raw_title
    snippet = (snippet_source.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " "))[
        :_MAX_SNIPPET_LENGTH
    ]
    kind = Kind.pr if item.pull_request is not None else Kind.issue
    return Hit(
        url=item.html_url,
        title=title,
        snippet=snippet,
        date=item.updated_at,
        kind=kind,
    )


def _bad_request(repo: str, term: str) -> Err | None:
    """Return the bounded request error, or ``None`` when input is admissible."""
    if not term.strip():
        return Err("a search term is required", rc=Rc.BAD_REQUEST)
    if ":" in term:
        return Err("the search term must not contain ':'", rc=Rc.BAD_REQUEST)
    if len(term) > _MAX_TERM_LENGTH:
        return Err(
            f"the search term must be at most {_MAX_TERM_LENGTH} characters",
            rc=Rc.BAD_REQUEST,
        )
    if _REPO.fullmatch(repo) is None:
        return Err(
            "repository must be OWNER/REPO with 1..100 safe characters per segment",
            rc=Rc.BAD_REQUEST,
        )
    owner, name = repo.split("/", maxsplit=1)
    if _ONLY_DOTS.fullmatch(owner) or _ONLY_DOTS.fullmatch(name):
        return Err("repository segments must not consist only of dots", rc=Rc.BAD_REQUEST)
    return None


def _ran_at(now: datetime | None) -> str:
    """Render an aware instant in the contract's exact UTC ``Z`` form."""
    instant = datetime.now(UTC) if now is None else now
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return instant.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def search(
    repo: str,
    term: str,
    *,
    run: _GhRunner = _run_gh,
    now: datetime | None = None,
) -> Result[AdapterRecord]:
    """Search enabled tracker channels and return hits or a control-armed null."""
    invalid = _bad_request(repo, term)
    if invalid is not None:
        return invalid

    repo_argv = ("api", f"repos/{repo}")
    repo_response = _request(repo_argv, _RepoResponse, run)
    if isinstance(repo_response, External | Err):
        return repo_response

    kinds = [Kind.issue] if repo_response.has_issues else []
    kinds.append(Kind.pr)
    searches: list[tuple[Kind, tuple[str, ...], _SearchResponse]] = []
    hits: list[Hit] = []
    total_count = 0
    for kind in kinds:
        argv = _search_argv(repo, kind, term)
        response = _request(argv, _SearchResponse, run)
        if isinstance(response, External | Err):
            return response
        searches.append((kind, argv, response))
        total_count += response.total_count
        hits.extend(_hit(item) for item in response.items)

    null_result: Null | None = None
    if not hits:
        arms: list[Arm] = []
        for kind in kinds:
            arm_argv = _search_argv(repo, kind, None)
            arm_response = _request(arm_argv, _SearchResponse, run)
            if isinstance(arm_response, External | Err):
                return arm_response
            count = arm_response.total_count
            arms.append(
                Arm(
                    kind=kind,
                    command=_display_command(arm_argv),
                    result=f"total_count={count}",
                    discriminates=count > 0,
                )
            )
        null_result = Null(arms=arms)

    return Ok(
        AdapterRecord(
            adapter="trackers",
            tier=Tier.cheap,
            question=f"{repo} {term}",
            command=_display_command(searches[0][1]),
            has_issues=repo_response.has_issues,
            has_discussions=repo_response.has_discussions,
            ran_at=_ran_at(now),
            total_count=total_count,
            hits=hits,
            null_result=null_result,
        )
    )


def validate(record: AdapterRecord) -> None:
    """Enforce generated-field and semantic cross-field contract invariants."""
    msgspec.json.decode(msgspec.json.encode(record), type=AdapterRecord)

    has_hits = bool(record.hits)
    has_null = record.null_result is not None
    if has_hits == has_null:
        raise msgspec.ValidationError(
            "exactly one of non-empty hits or null_result must be present"
        )
    if record.null_result is None:
        return

    arm_kinds = [arm.kind for arm in record.null_result.arms]
    expected = {Kind.pr}
    if record.has_issues:
        expected.add(Kind.issue)
    if len(arm_kinds) != len(set(arm_kinds)) or set(arm_kinds) != expected:
        raise msgspec.ValidationError("null_result must have one unique arm per searched channel")

    for arm in record.null_result.arms:
        match = _ARM_RESULT.fullmatch(arm.result)
        if match is None:
            raise msgspec.ValidationError("arm result must be total_count=<integer>")
        if arm.discriminates != (int(match.group(1)) > 0):
            raise msgspec.ValidationError("arm discriminates must agree with its total_count")


def main(argv: list[str], repo_root: Path) -> int:
    """Print one validated adapter record, or write it to ``--out PATH``.

    ``--out`` may appear anywhere after the positional ``repo``; its value is
    stripped from the search term before the remaining words are joined.
    """
    del repo_root
    repo = argv[0] if argv else ""
    term_words: list[str] = []
    out_path: Path | None = None
    rest = argv[1:]
    i = 0
    while i < len(rest):
        if rest[i] == "--out":
            if i + 1 >= len(rest):
                err = Err("--out requires a path", rc=Rc.BAD_REQUEST)
                events.fail(
                    "trackers.bad_out_flag",
                    f"kb-research-trackers: {err.message}",
                    adapter="trackers",
                )
                return exit_code(err)
            out_path = Path(rest[i + 1])
            i += 2
            continue
        term_words.append(rest[i])
        i += 1
    term = " ".join(term_words)

    started_at = time.perf_counter()
    result = search(repo, term, run=_run_gh)
    duration_s = time.perf_counter() - started_at
    event_repo = repo[:200]
    event_term = term[:_MAX_TERM_LENGTH]
    if not isinstance(result, Ok):
        if isinstance(result, External):
            outcome = "external"
        elif result.rc is Rc.BAD_REQUEST:
            outcome = "bad_request"
        else:
            outcome = "error"
        events.fail(
            "trackers.search_failed",
            f"kb-research-trackers: {result.message}",
            adapter="trackers",
            repo=event_repo,
            term=event_term,
            duration_s=duration_s,
            outcome=outcome,
        )
        return exit_code(result)

    record = result.value
    validate(record)
    text = msgspec.json.format(msgspec.json.encode(record).decode(), indent=2)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n")
        events.say(
            "trackers.wrote",
            f"[aggregated-research] wrote {out_path}",
            adapter="trackers",
            repo=event_repo,
            term=event_term,
            duration_s=duration_s,
            outcome="ok",
            path=out_path,
        )
    else:
        events.say(
            "trackers.result",
            text,
            adapter="trackers",
            repo=event_repo,
            term=event_term,
            duration_s=duration_s,
            outcome="ok",
        )
    return exit_code(result)
