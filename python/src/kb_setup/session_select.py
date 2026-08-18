# Copyright (c) 2026 Raymond Manaloto
"""Resolve WHICH session transcripts a run covers — `mise run kb-session-select`.

Ray's ask, verbatim: *"the session review workflow should be re-usable as a way
to review the current session or a set of sessions by date time range… where it
can take either a date-time range, or the current session, or a list of sessions
to review, and a flag if it is to prepare the handoff for /clear-prep."*

THE SEAM THIS SITS ON. The agent fan-out cannot be a mise task — a task is a
shell command and the fan-out needs a live model. But SELECTION can, and until
now it was done in the head of whichever session wrote the workflow's arguments:
a `transcriptDir` string plus a `since` date, typed by hand, unvalidated,
re-derived every round. That is the transcription-error surface
`kb-session-state` was built to remove, still open on the one input nobody
checked.

`Date.now()` and `new Date()` THROW inside a Workflow script, so the workflow
cannot compute a time window even in principle. All time arithmetic was always
going to happen outside it. This is that outside, made deterministic and
testable instead of remembered.

WHY started_at IS NOT mtime, which is the defect that makes this more than a
convenience wrapper. `session-review.js:159` told every lane to scope itself to
*"transcripts with mtime >= since"*. Measured on 2026-08-18 over the live
transcript dir: **238 files, 20 with a birth-to-mtime gap over 24 hours, worst
119.6 hours**. A session that began five days ago and was resumed for one turn
today carries today's mtime, so an mtime window pulls it in and tells every lane
it is part of this round. The direction matters and is stated rather than
inflated: since `mtime >= birthtime` always holds, an mtime filter OVER-includes
and MISDATES — it cannot silently drop a session that started inside the
window.

So `started_at` comes from `st_birthtime`, cross-checked against the transcript's
own first timestamped record, and every record SAYS which clock produced it. A
figure that travels without its condition survives review and is still wrong
where it is used.

WHAT THIS REFUSES TO DO. An empty resolution exits `Rc.NOT_RUN`, never `[]` with
rc 0 — a glob that matches nothing looks exactly like a round with no sessions,
which is the failure `session-review.js` already refuses for its `handoffs`
argument. An unknown `--sessions` id is a `Rc.BAD_REQUEST` naming the id, never a
partial list: silently returning the four that resolved is how a review comes to
cover less than it claims.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kb_setup import brain
from kb_setup.generated.session_select import (
    ResolvedBy,
    SessionRecord,
    SessionSelection,
    TimeSource,
    Window,
)
from kb_setup.result import Err, Ok, Rc, Result, exit_code

#: How far the filesystem birthtime and the transcript's own first timestamp may
#: disagree before the FILE is believed over the filesystem. Sixty seconds is
#: slack for the gap between a file being created and its first record being
#: written; beyond that the disagreement is real and the content wins, because
#: the content is what the session said about itself.
_CLOCK_SLACK_SECONDS = 60

#: How many lines to read looking for the first timestamped record. The header
#: records (`mode`, `permission-mode`) carry no timestamp — measured: the first
#: two lines of a real transcript have none — so this cannot be `1`. It also
#: cannot be unbounded: these files reach hundreds of megabytes and
#: `agent-report-persistence.md` forbids reading one into context. Twenty lines
#: is the bound, and a file whose first twenty lines carry no timestamp falls
#: back to birthtime rather than being read further.
_HEADER_LINES = 20

#: A session id is the transcript's filename stem, and it is a UUID. Validated
#: rather than trusted so that `--sessions ../../etc/passwd` is a BAD_REQUEST
#: about an id rather than a path traversal that happens to miss.
_SESSION_ID = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def transcript_dir(cwd: Path, env: dict[str, str] | None = None) -> Path:
    """Claude Code's transcript directory for ``cwd``.

    Delegates to `brain.transcripts_base` and `brain.encode_cwd` rather than
    re-deriving either. The encoding in particular is a Claude Code
    implementation detail this repo does not own, and two copies of a rule you
    do not own is two chances to be wrong about it.
    """
    return brain.transcripts_base(env) / brain.encode_cwd(cwd)


def _iso(stamp: float) -> str:
    return datetime.fromtimestamp(stamp, tz=UTC).isoformat().replace("+00:00", "Z")


def _first_record_timestamp(path: Path) -> float | None:
    """The transcript's own first timestamp, as an epoch, or None.

    Streams at most `_HEADER_LINES` lines. Never reads the file: they run to
    hundreds of megabytes and this module is invoked before the expensive part
    of a round, where a bad read would be paid on every session at once.
    """
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(_HEADER_LINES):
                line = handle.readline()
                if not line:
                    return None
                try:
                    stamp = json.loads(line).get("timestamp")
                except json.JSONDecodeError, AttributeError:
                    continue
                if isinstance(stamp, str):
                    try:
                        return datetime.fromisoformat(stamp).timestamp()
                    except ValueError:
                        continue
    except OSError:
        return None
    return None


def _record(path: Path) -> SessionRecord | None:
    """One transcript as a record, or None if it cannot be stat'd."""
    try:
        stat = path.stat()
    except OSError:
        return None
    # `st_birthtime` is macOS/BSD. On a filesystem without it, python reports
    # `st_ctime` under that name or omits it; falling back to the content
    # timestamp and then to mtime keeps this working rather than raising on a
    # platform this repo does not currently run but might.
    birth = getattr(stat, "st_birthtime", None)
    content = _first_record_timestamp(path)
    if birth is None:
        started, source = (
            (content, TimeSource.content) if content else (stat.st_mtime, TimeSource.birthtime)
        )
    elif content is not None and abs(content - birth) > _CLOCK_SLACK_SECONDS:
        started, source = content, TimeSource.content
    else:
        started, source = birth, TimeSource.birthtime
    return SessionRecord(
        path=str(path),
        session_id=path.stem,
        started_at=_iso(float(started)),
        last_written=_iso(stat.st_mtime),
        bytes=stat.st_size,
        time_source=source,
    )


def records(directory: Path) -> list[SessionRecord]:
    """Every transcript in ``directory``, NEWEST FIRST by ``started_at``.

    Sorted by start, not by mtime. Sorting by mtime is the same defect as
    filtering by it: the 119.6-hour case puts a five-day-old resumed session at
    the top of a "most recent" list.
    """
    if not directory.is_dir():
        return []
    found = [r for p in sorted(directory.glob("*.jsonl")) if (r := _record(p)) is not None]
    return sorted(found, key=lambda r: r.started_at, reverse=True)


@dataclass(frozen=True)
class Spec:
    """One resolved request. Exactly one selector is set."""

    current: bool = False
    sessions: tuple[str, ...] = ()
    last: int | None = None
    since: str | None = None
    until: str | None = None


def _current(repo_root: Path, found: list[SessionRecord]) -> Result[SessionSelection]:
    """Resolve `--current` by two independent routes, and report the disagreement.

    PRIMARY: `.agent/state/graph-first/<id>.queried`, which `kb_setup.graph_first`
    writes from the `session_id` the PreToolUse hook receives. Verified live on
    2026-08-18: this session's id was on disk there and named exactly one
    transcript. It is the primary route because it is written by the caller's own
    hook traffic — the caller is running this command, so it has just tripped the
    hook.

    FALLBACK: the newest transcript by `started_at`, used when no state file
    exists (a session that never tripped the hook, or `.agent/` swept by
    `git clean -xdf`).

    The two are CROSS-CHECKED rather than ranked silently. Under two interleaved
    sessions the newest `.queried` can belong to whichever probed last, which is
    not necessarily this one. When the routes disagree the primary still wins —
    hook traffic is a stronger signal than file age — but the disagreement is
    reported as a `caveat`, because a resolution nobody can audit is the shape
    this whole module exists to replace.
    """
    if not found:
        return Err("no transcripts found; --current cannot resolve", rc=Rc.NOT_RUN)
    state = repo_root / ".agent" / "state" / "graph-first"
    marks = (
        sorted(state.glob("*.queried"), key=lambda p: p.stat().st_mtime, reverse=True)
        if state.is_dir()
        else []
    )
    by_id = {r.session_id: r for r in found}
    newest = found[0]
    for mark in marks:
        record = by_id.get(mark.stem)
        if record is None:
            continue
        caveat = (
            None
            if record.session_id == newest.session_id
            else (
                f"the graph-first state names {record.session_id} while the newest "
                f"transcript is {newest.session_id} — two sessions are probably "
                f"interleaving; the hook-traffic route was preferred"
            )
        )
        return Ok(_selection("--current", ResolvedBy.graph_first_state, [record], caveat=caveat))
    return Ok(
        _selection(
            "--current",
            ResolvedBy.newest_birthtime,
            [newest],
            caveat=(
                "no graph-first state file matched a transcript; "
                "fell back to the newest session start"
            ),
        )
    )


def _selection(
    selector: str,
    route: ResolvedBy,
    chosen: list[SessionRecord],
    *,
    window: Window | None = None,
    caveat: str | None = None,
) -> SessionSelection:
    payload = SessionSelection(
        schema_version=1,
        selector=selector,
        window=window if window is not None else Window(since=None, until=None),
        resolved_by=route,
        sessions=chosen,
    )
    if caveat is not None:
        payload.caveat = caveat
    return payload


def _by_id(found: list[SessionRecord], spec: Spec, directory: Path) -> Result[SessionSelection]:
    """`--sessions` — every id resolves, or none of them do.

    NEVER a partial list. Returning the ids that did resolve is how a review
    silently covers less than it was asked to, which is the same shape as an
    empty selection returning `[]` with rc 0.
    """
    index = {r.session_id: r for r in found}
    missing = [s for s in spec.sessions if s not in index]
    if missing:
        return Err(
            f"no transcript for session id(s): {', '.join(missing)} (in {directory})",
            rc=Rc.BAD_REQUEST,
        )
    chosen = [index[s] for s in spec.sessions]
    return Ok(_selection(f"--sessions {' '.join(spec.sessions)}", ResolvedBy.explicit, chosen))


def _window(found: list[SessionRecord], spec: Spec, directory: Path) -> Result[SessionSelection]:
    """`--since [--until]` — a datetime range over ``started_at``, never mtime."""
    lower, upper = spec.since, spec.until
    chosen = [
        r
        for r in found
        if (lower is None or r.started_at >= lower) and (upper is None or r.started_at <= upper)
    ]
    if not chosen:
        # Says WHAT IT LOOKED AT. "no sessions" and "no sessions in this window,
        # out of 238 examined" are different answers, and only the second one
        # tells you the probe worked.
        return Err(
            f"no session started in [{lower or '-inf'}, {upper or '+inf'}] — "
            f"{len(found)} transcript(s) were examined in {directory}",
            rc=Rc.NOT_RUN,
        )
    label = f"--since {lower}" + (f" --until {upper}" if upper else "")
    return Ok(_selection(label, ResolvedBy.window, chosen, window=Window(since=lower, until=upper)))


def select(
    found: list[SessionRecord], spec: Spec, repo_root: Path, directory: Path
) -> Result[SessionSelection]:
    """Apply ``spec`` to ``found``. Pure apart from `--current`'s state read.

    One branch per selector, each delegating — the selectors genuinely do
    different things (a state read, an exact lookup, a slice, a range filter) and
    inlining all four put every refusal path in one function.
    """
    if spec.current:
        return _current(repo_root, found)
    if spec.sessions:
        return _by_id(found, spec, directory)
    if spec.last is not None:
        chosen = found[: spec.last]
        if not chosen:
            return Err(f"no transcripts in {directory}", rc=Rc.NOT_RUN)
        return Ok(_selection(f"--last {spec.last}", ResolvedBy.explicit, chosen))
    return _window(found, spec, directory)


def _normalise(stamp: str) -> str | None:
    """A user-supplied bound as a comparable ISO-8601 UTC string, or None.

    Accepts a bare date (`2026-08-18`) as midnight UTC, which is the form a
    caller will actually type, and a full datetime. Compared as STRINGS against
    `started_at`, which is safe only because both sides are normalised here to
    the same fixed-width UTC form — a comparison that would be a lurking bug if
    either side were free-form.
    """
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


#: The flags that take a value. A tuple rather than a branch chain so adding a
#: selector cannot silently fall through to "unknown argument".
_VALUE_FLAGS = ("--since", "--until", "--last")


def _value_for(flag: str, value: str, seen: dict[str, object]) -> Err | None:
    """Store one value flag, or return the refusal. None means accepted."""
    if flag == "--last":
        if not value.isdigit() or int(value) < 1:
            return Err(f"--last needs a positive integer, got {value!r}", rc=Rc.BAD_REQUEST)
        seen["last"] = int(value)
        return None
    bound = _normalise(value)
    if bound is None:
        return Err(f"{flag} is not an ISO-8601 date or datetime: {value!r}", rc=Rc.BAD_REQUEST)
    seen[flag.removeprefix("--")] = bound
    return None


def _tokenise(args: list[str]) -> Result[dict[str, object]]:
    """The flags as a dict — grammar only, no cross-flag rules.

    Split from `parse` because the two answer different questions: this asks "is
    each flag well formed", `parse` asks "is this COMBINATION a request anyone
    can honour". Together they were one function you had to read whole to answer
    either, which ruff called complexity and is really two jobs in one place.
    """
    seen: dict[str, object] = {
        "current": False,
        "sessions": [],
        "last": None,
        "since": None,
        "until": None,
    }
    rest = list(args)
    while rest:
        flag = rest.pop(0)
        if flag == "--current":
            seen["current"] = True
        elif flag == "--json":
            continue  # accepted and ignored: JSON is the only output there is
        elif flag == "--sessions":
            ids = []
            while rest and not rest[0].startswith("-"):
                ids.append(rest.pop(0))
            if not ids:
                return Err("--sessions needs at least one id", rc=Rc.BAD_REQUEST)
            seen["sessions"] = ids
        elif flag in _VALUE_FLAGS:
            if not rest:
                return Err(f"{flag} needs a value", rc=Rc.BAD_REQUEST)
            refusal = _value_for(flag, rest.pop(0), seen)
            if refusal is not None:
                return refusal
        else:
            return Err(f"unknown argument: {flag}", rc=Rc.BAD_REQUEST)
    return Ok(seen)


def parse(args: list[str]) -> Result[Spec]:
    """The CLI grammar. Exactly one selector, or a BAD_REQUEST naming the problem."""
    tokenised = _tokenise(args)
    if not isinstance(tokenised, Ok):
        return Err(getattr(tokenised, "message", "bad request"), rc=Rc.BAD_REQUEST)
    seen = tokenised.value
    raw_ids = seen["sessions"]
    sessions = [str(s) for s in raw_ids] if isinstance(raw_ids, list) else []
    since, until, last = seen["since"], seen["until"], seen["last"]

    bad = [s for s in sessions if not _SESSION_ID.match(s)]
    if bad:
        return Err(f"not a session id: {', '.join(bad)}", rc=Rc.BAD_REQUEST)
    if until is not None and since is None:
        return Err(
            "--until needs --since; an open lower bound is the whole history",
            rc=Rc.BAD_REQUEST,
        )
    chosen = sum([bool(seen["current"]), bool(sessions), last is not None, since is not None])
    if chosen == 0:
        return Err(
            "one selector is required: --current | --sessions <id>... | "
            "--last N | --since <ISO> [--until <ISO>]",
            rc=Rc.BAD_REQUEST,
        )
    if chosen > 1:
        # Two selectors is a request nobody can honour: they mean different sets,
        # and picking one silently is the "resolves to X" default that composes
        # into an answer nobody chose.
        return Err("selectors are mutually exclusive; give exactly one", rc=Rc.BAD_REQUEST)
    return Ok(
        Spec(
            current=bool(seen["current"]),
            sessions=tuple(sessions),
            last=last if isinstance(last, int) else None,
            since=since if isinstance(since, str) else None,
            until=until if isinstance(until, str) else None,
        )
    )


def resolve(
    args: list[str], repo_root: Path, env: dict[str, str] | None = None
) -> Result[SessionSelection]:
    """The boundary: parse, enumerate, select. Returns rather than prints."""
    parsed = parse(args)
    if not isinstance(parsed, Ok):
        return Err(parsed.message, rc=Rc.BAD_REQUEST)
    directory = transcript_dir(repo_root, env)
    if not directory.is_dir():
        # Naming the DERIVED path, not just "not found": the encoding turns a cwd
        # into a directory name, and a wrong cwd produces a plausible-looking
        # path that does not exist. Printing it is what makes that visible
        # instead of looking like an empty round.
        return Err(f"no transcript directory at {directory}", rc=Rc.BAD_REQUEST)
    return select(records(directory), parsed.value, repo_root, directory)


def main(args: list[str], repo_root: Path) -> int:
    """`kb-session-select <selector>` — the JSON on stdout is the only stdout."""
    result = resolve(args, repo_root)
    if not isinstance(result, Ok):
        print(f"kb-session-select: {result.message}", file=sys.stderr)
        return exit_code(result)
    import msgspec

    print(msgspec.json.format(msgspec.json.encode(result.value).decode(), indent=2))
    return exit_code(result)
