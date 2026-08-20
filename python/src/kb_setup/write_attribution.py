# Copyright (c) 2026 Raymond Manaloto
"""Name what ran when a tracked file was written behind our back.

## The failure this exists for

`.codex/config.toml` is tracked, and something keeps rewriting its
`[shell_environment_policy.set]` block with a verbatim copy of
`.claude/settings.json`'s `env`. It happened on 2026-08-18 (#399) and again on
2026-08-20. Both times the response was the same and it did not work: guess at a
culprit, probe it, refute it, guess again. Between the two incidents **eleven**
candidate writers were refuted by reproduction — `agy`, `codex exec` with and
without `--ephemeral`, the codex-side session hooks, two marketplace plugins,
the installed graphify, and five more in #399. Not one of them was it.

Guessing does not converge because the search space is every process that ran.
So this module stops guessing and asks the only question with a bounded answer:
**what was running in the seconds around the file's mtime?** A session transcript
records every tool call with an ISO timestamp, and every hook firing with the
hook's name. The write happened while the session was live, so the writer — or
the thing that invoked it — is in that window.

## What it does NOT claim

It produces **candidates, not a verdict.** A tool call adjacent to the mtime is a
lead; the transcript cannot see a process that was spawned earlier and wrote
later, nor anything a background daemon did. Reporting it as attribution would be
`unprobed-reasoning-wears-the-measured-voice` — narrow the window, then go and
reproduce the top candidate the way the eleven refutations were done.

Two states are kept distinct for the same reason `currency.toml` keeps three: a
window with **no events** is not the same as a window **nothing examined**, and
this refuses rather than returning an empty list when the second is true.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kb_setup.result import Err, Ok, Rc, Result, exit_code

#: Seconds either side of the mtime to report. 60 is wide enough to catch the
#: tool call that spawned a writer and narrow enough that a busy session does not
#: return its whole transcript. Overridable, because narrowing it is how a run
#: goes from a list of leads to one.
DEFAULT_WINDOW = 60.0

#: Cap on reported rows. A cap is a BOUND, so the report always states how many
#: were dropped — a truncated list read as complete is how "covered everything"
#: gets claimed for a sample (`probes-need-a-control-arm.md` rule 3).
DEFAULT_LIMIT = 40


@dataclass(frozen=True)
class Event:
    """One timestamped thing a transcript recorded, with its distance from the mtime."""

    at: datetime
    delta: float
    kind: str
    detail: str
    session: str

    def render(self) -> str:
        """One report row: when, how far from the mtime, what, and whose session."""
        sign = "+" if self.delta >= 0 else "-"
        return (
            f"{self.at.isoformat()}  {sign}{abs(self.delta):6.1f}s  "
            f"{self.kind:<14} {self.detail}  [{self.session[:8]}]"
        )


@dataclass(frozen=True)
class Attribution:
    """The window, what was examined, and what was found in it."""

    target: Path
    mtime: datetime
    window: float
    events: tuple[Event, ...]
    transcripts_examined: int
    transcripts_skipped: int
    #: Candidates that could not be READ at all. Kept apart from `examined`
    #: because contributing no events and being unreadable are byte-identical in
    #: the result and opposite in meaning.
    transcripts_unreadable: int = 0


def _parse_ts(raw: object) -> datetime | None:
    """Parse a transcript timestamp, ALWAYS tz-aware, or None if unusable.

    The `tzinfo` line is the whole point. `fromisoformat` returns a NAIVE
    datetime for a string carrying no offset, and subtracting a naive from the
    tz-aware mtime raises `TypeError` — so one offsetless line anywhere in any
    scanned transcript crashed the entire run. Every fixture here carried an
    offset, so no test could see it; both PR bots on #406 found it independently
    and a control arm confirmed it.

    UTC is the right assumption rather than a shrug: Claude Code writes these
    timestamps in UTC (the records this module reads end in `Z`), so an
    offsetless one is a truncation of UTC, not a local time.
    """
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _describe(record: dict[str, object]) -> list[tuple[str, str]]:
    """Reduce one transcript record to its (kind, detail) rows; [] if it says nothing.

    Hooks are pulled out FIRST and by name. They are the highest-value rows here:
    a hook is a command the harness runs on its own schedule, which is exactly the
    shape of a writer nobody remembers invoking.

    **EVERY `tool_use` block, not just the first.** One assistant record carries
    all the tool calls issued in parallel, and this codebase issues parallel Bash
    calls constantly — so returning after the first dropped the rest and reported
    a quieter window than actually occurred. In a module whose whole output is
    "what was running here", under-reporting is the one failure that matters.
    (graphify-labs, PR #406.)
    """
    attachment = record.get("attachment")
    if isinstance(attachment, dict):
        hook = attachment.get("hookName")
        if isinstance(hook, str) and hook:
            return [("hook", hook)]

    rows: list[tuple[str, str]] = []
    message = record.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = str(block.get("name", "?"))
                params = block.get("input")
                detail = ""
                if isinstance(params, dict):
                    # `command` for Bash, `file_path` for the file tools. Anything
                    # else is summarised by its tool name alone rather than by
                    # dumping a payload nobody can scan.
                    raw = params.get("command") or params.get("file_path") or ""
                    detail = " ".join(str(raw).split())[:120]
                rows.append(("tool", f"{name}: {detail}" if detail else name))
    if rows:
        return rows

    kind = record.get("type")
    if isinstance(kind, str) and kind in {"system", "user"}:
        return [(kind, "")]
    return []


def events_in(path: Path, mtime: datetime, window: float) -> Iterator[Event]:
    """Every event in one transcript whose timestamp falls inside the window.

    Raises `OSError` if the file cannot be read. That is deliberate and it is the
    module's whole thesis applied to itself: swallowing the error here made an
    UNREADABLE transcript indistinguishable from an examined-and-empty one, so a
    permissions problem would have been reported as "nothing ran in this window".
    The caller counts these separately. (graphify-labs, PR #406.)
    """
    session = path.stem
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        at = _parse_ts(record.get("timestamp"))
        if at is None:
            continue
        delta = (at - mtime).total_seconds()
        if abs(delta) > window:
            continue
        for kind, detail in _describe(record):
            yield Event(at=at, delta=delta, kind=kind, detail=detail, session=session)


def _relevant(
    transcripts: Iterable[Path], mtime: datetime, window: float
) -> tuple[list[Path], int]:
    """Split transcripts into those that COULD contain the moment, and the rest.

    A transcript last written before the window opened cannot hold an event inside
    it, so skipping it is sound rather than a shortcut. The count of skips is
    returned instead of discarded: a prefilter that quietly ate the one relevant
    file would otherwise be indistinguishable from an empty window.
    """
    keep: list[Path] = []
    skipped = 0
    floor = mtime.timestamp() - window
    for path in transcripts:
        try:
            if path.stat().st_mtime < floor:
                skipped += 1
                continue
        except OSError:
            skipped += 1
            continue
        keep.append(path)
    return keep, skipped


def attribute(
    target: Path,
    transcripts: Sequence[Path],
    *,
    window: float = DEFAULT_WINDOW,
) -> Result[Attribution]:
    """Collect what ran around `target`'s mtime. Err when the question cannot be asked."""
    try:
        stamp = target.stat().st_mtime
    except OSError as exc:
        return Err(f"cannot read the mtime of {target}: {exc}", Rc.NOT_RUN)

    mtime = datetime.fromtimestamp(stamp, tz=UTC)
    if not transcripts:
        return Err(
            "no transcripts to search — this is NOT 'nothing ran', it is "
            "'nothing was examined'. Point --transcripts at the session directory.",
            Rc.NOT_RUN,
        )

    keep, skipped = _relevant(transcripts, mtime, window)
    if not keep:
        return Err(
            f"all {skipped} transcript(s) were last written before the window "
            f"opened, so none could contain {mtime.isoformat()}. Widen --window, "
            "or the write happened outside any recorded session.",
            Rc.NOT_RUN,
        )

    found: list[Event] = []
    unreadable = 0
    for path in keep:
        try:
            found.extend(events_in(path, mtime, window))
        except OSError:
            # Counted, never swallowed. An unreadable transcript contributes no
            # events, which is byte-identical to an examined-and-empty one — so
            # silently continuing would report a permissions problem as "nothing
            # ran here", the exact collapse this module exists to refuse.
            unreadable += 1
    found.sort(key=lambda event: abs(event.delta))

    if unreadable and unreadable == len(keep):
        return Err(
            f"all {unreadable} candidate transcript(s) could not be READ, so the "
            "window was never actually searched. This is NOT 'nothing ran'.",
            Rc.NOT_RUN,
        )

    return Ok(
        Attribution(
            target=target,
            mtime=mtime,
            window=window,
            events=tuple(found),
            transcripts_examined=len(keep) - unreadable,
            transcripts_skipped=skipped,
            transcripts_unreadable=unreadable,
        )
    )


def render(result: Attribution, *, limit: int = DEFAULT_LIMIT) -> str:
    """The human-facing report — nearest events first, with the bounds stated.

    Both bounds are printed rather than applied silently: the window, and how many
    rows were dropped by `limit`. A reader who cannot see the bound will read the
    list as the whole answer.
    """
    head = [
        f"write-attribution: {result.target}",
        f"  mtime   {result.mtime.isoformat()}",
        f"  window  +/-{result.window:g}s",
        (
            f"  scanned {result.transcripts_examined} transcript(s), "
            f"skipped {result.transcripts_skipped} written before the window"
        ),
        "",
    ]
    if result.transcripts_unreadable:
        head.insert(
            -1,
            f"  ⚠ {result.transcripts_unreadable} candidate transcript(s) could "
            "not be READ — those windows were not searched, and their silence "
            "here is not evidence.",
        )
    if not result.events:
        head.append(
            "  NO EVENTS in the window. The transcripts were read and contained "
            "nothing here — a finding, not a failure to look. It does NOT show "
            "the writer was never a tool call: an earlier call can leave a "
            "process that writes later. Narrow or widen --window and re-ask."
        )
        return "\n".join(head)

    shown = result.events[:limit]
    body = [f"  {event.render()}" for event in shown]
    dropped = len(result.events) - len(shown)
    if dropped:
        body.append(f"  ... {dropped} more not shown (--limit {limit})")
    body += [
        "",
        (
            "  These are CANDIDATES, not a verdict. A transcript cannot see a "
            "process spawned earlier that wrote later. Narrow --window, then "
            "reproduce."
        ),
    ]
    return "\n".join(head + body)


def _transcript_dir(root: Path) -> Path:
    """Where Claude Code keeps this project's transcripts.

    The slug is the absolute path with every separator replaced by `-`, which is
    the harness's own scheme and not something this module gets to choose.
    """
    slug = str(root.resolve()).replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug


def write_attribution_main(root: Path, args: Sequence[str] = ()) -> int:
    """CLI: `uv run kb-setup write-attribution <path> [--window N] [--limit N]`."""
    positional: list[str] = []
    window = DEFAULT_WINDOW
    limit = DEFAULT_LIMIT
    transcripts_dir: Path | None = None

    pending = list(args)
    # A malformed numeric flag must be a REFUSAL, not a traceback, and not a
    # silent fallback to the default. `--window abc` used to raise ValueError
    # straight out of `main` — a stack trace from a module whose entire subject is
    # reporting rather than raising. Swallowing it would be worse: the run would
    # then search a different window than the one the caller asked for and report
    # the result as if it answered their question. (graphify-labs, PR #406.)
    #: Flags that consume the next argument. Listed rather than inlined so the
    #: missing-value check below cannot fall out of step with the parsing.
    valued = {"--window", "--limit", "--transcripts"}
    while pending:
        item = pending.pop(0)
        if item in valued:
            # A flag at the END of argv had no `pending` to pop, so it fell
            # through to `positional` and became the TARGET PATH — silently
            # ignoring the caller's flag and searching the default window. The
            # first version of this parser guarded the value-is-not-a-number case
            # and not the value-is-missing one, which is the same defect wearing
            # the other half of the pair. (graphify-labs, PR #406, third pass.)
            if not pending:
                print(f"write-attribution: {item} needs a value")
                return int(Rc.NOT_RUN)
            raw = pending.pop(0)
            if item == "--transcripts":
                transcripts_dir = Path(raw)
                continue
            try:
                if item == "--window":
                    window = float(raw)
                else:
                    limit = int(raw)
            except ValueError:
                print(f"write-attribution: {item} needs a number, got {raw!r}")
                return int(Rc.NOT_RUN)
        else:
            positional.append(item)

    if not positional:
        print("usage: kb-setup write-attribution <path> [--window N] [--limit N]")
        return int(Rc.NOT_RUN)

    target = Path(positional[0])
    if not target.is_absolute():
        target = root / target

    directory = transcripts_dir or _transcript_dir(root)
    transcripts = sorted(directory.glob("*.jsonl")) if directory.is_dir() else []

    result = attribute(target, transcripts, window=window)
    if isinstance(result, Ok):
        print(render(result.value, limit=limit))
    else:
        print(f"write-attribution: {result.message}")
    return exit_code(result)
