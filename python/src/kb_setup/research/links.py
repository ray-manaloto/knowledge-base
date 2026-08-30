# Copyright (c) 2026 Raymond Manaloto
"""Check that cited links resolve, via the pinned `lychee` 0.24.2 binary.

Mirrors `kb_setup.research.trackers`'s shape (subprocess transport + explicit
`now`, `validate()` doing a round-trip plus cross-field checks, `main()`
parsing `--out` positionally-flexible) with one deliberate difference: trackers
never needs to treat a non-zero subprocess exit as a valid answer, while lychee
does — rc=2 means "broken links found", a finding, not a failure. So the
branch here is on whether stdout PARSES as the expected JSON shape, never on
the raw exit code (lychee documents no exit codes at all; 0/1/2/3 are this
project's own observations, not a documented-complete set). See #578.

URLs are never passed to lychee as positional arguments — lychee treats a
positional URL as a page to fetch and scrape for links inside it, not as a
link to check, and a positional URL that itself 404s panics lychee (rc=1,
empty stdout). Instead every call writes the URLs to a temp file, one per
line, and passes that file as lychee's sole positional input.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import msgspec

from kb_setup import events
from kb_setup.generated.research_record import AdapterRecord, LinkResult, Links, Tier
from kb_setup.result import Err, External, Ok, Rc, Result, exit_code

_LYCHEE_TIMEOUT = 120
_MAX_URLS = 60
_MAX_URL_LENGTH = 2048
_MAX_STATUS_TEXT_LENGTH = 200
_MAX_QUESTION_LENGTH = 512
_LINKS_CONFIG = "links-check.toml"

#: The lychee output maps that represent one checked link. `redirect_map` is
#: deliberately excluded — it duplicates an entry already in `success_map` or
#: `error_map` and carries an incompatible shape (`{origin, redirects: [...]}`,
#: no `url`/`status`/`span`/`duration`). Including it double-counts a URL and
#: breaks the `checked == len(results)` control arm on a normal run.
_INCLUDED_MAPS = (
    "success_map",
    "error_map",
    "timeout_map",
    "excluded_map",
    "suggestion_map",
)

type _LinkRunner = Callable[[tuple[str, ...]], tuple[int, str, str]]


class _LycheeStatus(msgspec.Struct):
    """One lychee result's status: an HTTP outcome or an exclusion reason."""

    text: str
    code: int | None = None
    details: str | None = None


class _LycheeSpan(msgspec.Struct):
    """Where in the input file a checked link was found."""

    line: int
    column: int


class _LycheeDuration(msgspec.Struct):
    """lychee's own `{secs, nanos}` duration shape for one checked link."""

    secs: int
    nanos: int


class _LycheeEntry(msgspec.Struct):
    """One link result as lychee reports it inside any of the five maps."""

    url: str
    status: _LycheeStatus
    span: _LycheeSpan
    duration: _LycheeDuration


class _LycheeOutput(msgspec.Struct):
    """The lychee JSON fields this adapter reads; everything else is ignored.

    lychee publishes no schema for its own output, so every field here is
    read from untrusted, unbounded JSON. `redirect_map` is deliberately
    omitted (see `_INCLUDED_MAPS`); every other undeclared field (`total`,
    `redirects`, top-level `duration`, `cached`, ...) is silently dropped by
    plain `msgspec.Struct` decoding, which does not forbid unknown fields.
    """

    unique: int
    success_map: dict[str, list[_LycheeEntry]]
    error_map: dict[str, list[_LycheeEntry]]
    timeout_map: dict[str, list[_LycheeEntry]]
    excluded_map: dict[str, list[_LycheeEntry]]
    suggestion_map: dict[str, list[_LycheeEntry]]


def _run_lychee(argv: tuple[str, ...]) -> tuple[int, str, str]:
    """Run one bounded `lychee` call and keep both child streams captured."""
    try:
        process = subprocess.run(
            ["lychee", *argv],
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=_LYCHEE_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", f"lychee: {exc}"
    return process.returncode, process.stdout or "", process.stderr or ""


def _display_command(argv: tuple[str, ...]) -> str:
    """Render the exact secret-free child argv for the contract record."""
    return " ".join(("lychee", *argv))


def _bad_request(urls: tuple[str, ...]) -> Err | None:
    """Return the bounded request error, or `None` when input is admissible."""
    if not urls:
        return Err("at least one URL is required", rc=Rc.BAD_REQUEST)
    if len(urls) > _MAX_URLS:
        return Err(f"at most {_MAX_URLS} URLs are allowed per invocation", rc=Rc.BAD_REQUEST)
    for url in urls:
        if not url.startswith(("http://", "https://")):
            return Err(f"URL must start with http:// or https://: {url!r}", rc=Rc.BAD_REQUEST)
        if len(url) > _MAX_URL_LENGTH:
            return Err(
                f"URL exceeds {_MAX_URL_LENGTH} characters: {url[:80]!r}...",
                rc=Rc.BAD_REQUEST,
            )
    return None


def _ran_at(now: datetime | None) -> str:
    """Render an aware instant in the contract's exact UTC `Z` form."""
    instant = datetime.now(UTC) if now is None else now
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return instant.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _question(urls: tuple[str, ...]) -> str:
    """Render a bounded, human-legible question from the checked URLs."""
    joined = ", ".join(urls)
    if len(joined) <= _MAX_QUESTION_LENGTH:
        return joined
    return joined[: _MAX_QUESTION_LENGTH - 3] + "..."


def _status_text(status: _LycheeStatus) -> str:
    """Fold an HTTP status code into the text when no exclusion detail exists.

    `status.code` (an integer, present on real HTTP-status checks) and
    `status.details` (a string, present only on exclusions) are mutually
    exclusive in practice, so this never doubles up.
    """
    text = status.text
    if status.code is not None and status.details is None:
        text = f"{text} ({status.code})"
    return text[:_MAX_STATUS_TEXT_LENGTH]


def _link_result(entry: _LycheeEntry, *, ok: bool) -> LinkResult:
    """Convert one untrusted lychee map entry into a bounded contract result."""
    return LinkResult(
        url=entry.url,
        ok=ok,
        status_text=_status_text(entry.status),
        status_details=entry.status.details,
        line=entry.span.line,
        column=entry.span.column,
        duration_ms=entry.duration.secs * 1000 + entry.duration.nanos / 1_000_000,
    )


def _flatten(output: _LycheeOutput) -> list[LinkResult]:
    """Flatten the five per-outcome maps into one bounded result list."""
    results: list[LinkResult] = []
    for map_name in _INCLUDED_MAPS:
        ok = map_name == "success_map"
        entries: dict[str, list[_LycheeEntry]] = getattr(output, map_name)
        for file_entries in entries.values():
            results.extend(_link_result(entry, ok=ok) for entry in file_entries)
    return results


def check(
    urls: tuple[str, ...],
    *,
    run: _LinkRunner = _run_lychee,
    now: datetime | None = None,
) -> Result[AdapterRecord]:
    """Check every URL resolves and return a control-armed `links` record."""
    invalid = _bad_request(urls)
    if invalid is not None:
        return invalid

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as handle:
        temp_path = Path(handle.name)
    temp_path.write_text("".join(f"{url}\n" for url in urls))
    try:
        argv = (
            "--format",
            "json",
            "--no-progress",
            "-v",
            "--config",
            _LINKS_CONFIG,
            str(temp_path),
        )
        _returncode, stdout, stderr = run(argv)
        try:
            output = msgspec.json.decode(stdout, type=_LycheeOutput)
        except (msgspec.DecodeError, msgspec.ValidationError) as exc:
            reason = stderr.strip() or str(exc)
            return Err(
                f"lychee returned an unparsable payload for `{_display_command(argv)}`: {reason}",
                rc=Rc.NOT_RUN,
            )
    finally:
        temp_path.unlink(missing_ok=True)

    results = _flatten(output)
    broken_count = sum(1 for result in results if not result.ok)
    links = Links(checked=output.unique, broken_count=broken_count, results=results)

    return Ok(
        AdapterRecord(
            adapter="links",
            tier=Tier.cheap,
            question=_question(urls),
            command=_display_command(argv),
            trackers=None,
            links=links,
            packages=None,
            ran_at=_ran_at(now),
            total_count=len(results),
            hits=[],
            null_result=None,
        )
    )


def validate(record: AdapterRecord) -> None:
    """Enforce generated-field and semantic cross-field contract invariants."""
    msgspec.json.decode(msgspec.json.encode(record), type=AdapterRecord)

    if record.adapter != "links":
        return
    if record.links is None:
        raise msgspec.ValidationError("a links record must carry a non-null links field")
    if record.trackers is not None:
        raise msgspec.ValidationError("a links record must not carry trackers")
    if record.hits:
        raise msgspec.ValidationError("a links record must have empty hits")
    if record.null_result is not None:
        raise msgspec.ValidationError("a links record must have null_result=None")

    links = record.links
    broken = sum(1 for result in links.results if not result.ok)
    if links.broken_count != broken:
        raise msgspec.ValidationError("broken_count must equal the count of failing results")
    if len(links.results) != links.checked:
        raise msgspec.ValidationError(
            "checked must equal the number of results — a URL was silently "
            "bucketed outside every per-link map"
        )
    for result in links.results:
        if result.ok and result.status_text == "Excluded":
            raise msgspec.ValidationError("an excluded link must not be marked ok")


def main(argv: list[str], repo_root: Path) -> int:
    """Print one validated adapter record, or write it to `--out PATH`.

    `--out` may appear anywhere after the positional URLs. Every remaining
    argument is one URL to check.
    """
    del repo_root
    urls: list[str] = []
    out_path: Path | None = None
    i = 0
    while i < len(argv):
        if argv[i] == "--out":
            if i + 1 >= len(argv):
                err = Err("--out requires a path", rc=Rc.BAD_REQUEST)
                events.fail(
                    "links.bad_out_flag",
                    f"kb-research-links: {err.message}",
                    adapter="links",
                    outcome="bad_request",
                )
                return exit_code(err)
            out_path = Path(argv[i + 1])
            i += 2
            continue
        urls.append(argv[i])
        i += 1

    started_at = time.perf_counter()
    result = check(tuple(urls), run=_run_lychee)
    duration_s = time.perf_counter() - started_at
    if not isinstance(result, Ok):
        if isinstance(result, External):
            outcome = "external"
        elif result.rc is Rc.BAD_REQUEST:
            outcome = "bad_request"
        elif result.rc is Rc.NOT_RUN:
            outcome = "not_run"
        else:
            outcome = "error"
        events.fail(
            "links.check_failed",
            f"kb-research-links: {result.message}",
            adapter="links",
            url_count=len(urls),
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
            "links.wrote",
            f"[aggregated-research] wrote {out_path}",
            adapter="links",
            url_count=len(urls),
            duration_s=duration_s,
            outcome="ok",
            path=out_path,
        )
    else:
        events.say(
            "links.result",
            text,
            adapter="links",
            url_count=len(urls),
            duration_s=duration_s,
            outcome="ok",
        )
    return exit_code(result)
