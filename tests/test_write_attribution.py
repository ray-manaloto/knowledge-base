# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.write_attribution` — what ran when a file was written.

The assertions that matter are the REFUSALS. This module's whole reason to exist
is that guessing at a writer does not converge, so the one thing it must never do
is hand back an empty list that reads like "nothing ran" when the truth is
"nothing was examined". Two tests below are dedicated to keeping those apart.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import write_attribution as wa
from kb_setup.result import Err, Ok, Rc

if TYPE_CHECKING:
    # Annotation-only: nothing here uses pytest at runtime (no fixtures are
    # defined in this file), and `from __future__ import annotations` above makes
    # the deferred reference resolve.
    import pytest

_MTIME = datetime(2026, 8, 20, 6, 3, 34, tzinfo=UTC)


def _at(offset: float) -> str:
    return (_MTIME + timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")


def _target(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text("x = 1\n", encoding="utf-8")
    os.utime(path, (_MTIME.timestamp(), _MTIME.timestamp()))
    return path


def _transcript(tmp_path: Path, name: str, records: list[dict[str, object]]) -> Path:
    path = tmp_path / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    # A transcript must look written at/after the window or the prefilter drops it.
    later = _MTIME.timestamp() + 300
    os.utime(path, (later, later))
    return path


def _tool(offset: float, name: str, command: str) -> dict[str, object]:
    return {
        "timestamp": _at(offset),
        "message": {"content": [{"type": "tool_use", "name": name, "input": {"command": command}}]},
    }


def _hook(offset: float, name: str) -> dict[str, object]:
    return {"timestamp": _at(offset), "attachment": {"hookName": name}}


def test_events_inside_the_window_are_found_and_sorted_by_nearness(tmp_path: Path) -> None:
    """Nearest-first is the whole ergonomics: the top row is where you look."""
    target = _target(tmp_path)
    transcript = _transcript(
        tmp_path,
        "sess",
        [
            _tool(-40, "Bash", "git status"),
            _hook(2, "SessionStart:startup"),
            _tool(-5, "Bash", "mise run kb-currency-check"),
        ],
    )

    result = wa.attribute(target, [transcript], window=60)

    assert isinstance(result, Ok)
    details = [event.detail for event in result.value.events]
    assert details[0] == "SessionStart:startup"
    assert "kb-currency-check" in details[1]
    assert "git status" in details[2]


def test_events_outside_the_window_are_excluded(tmp_path: Path) -> None:
    """The control arm for the test above — the window must actually bound."""
    target = _target(tmp_path)
    transcript = _transcript(tmp_path, "sess", [_tool(-500, "Bash", "far away")])

    result = wa.attribute(target, [transcript], window=60)

    assert isinstance(result, Ok)
    assert result.value.events == ()


def test_no_transcripts_is_refused_not_reported_as_no_events(tmp_path: Path) -> None:
    """'Nothing was examined' must never render as 'nothing ran'.

    This is the DRIFT/SKIP/OK collapse in its most damaging form here: an empty
    result would close the investigation that the module exists to open.
    """
    result = wa.attribute(_target(tmp_path), [], window=60)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "nothing was examined" in result.message


def test_every_transcript_prefiltered_away_is_refused(tmp_path: Path) -> None:
    """The prefilter is a BOUND, so eating the last candidate must be loud.

    A transcript written before the window cannot contain it — sound as a skip,
    and catastrophic as a silent one, because the caller cannot tell it from a
    window that was searched and found empty.
    """
    target = _target(tmp_path)
    stale = _transcript(tmp_path, "old", [_tool(0, "Bash", "in the window")])
    older = _MTIME.timestamp() - 5000
    os.utime(stale, (older, older))

    result = wa.attribute(target, [stale], window=60)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "1 transcript" in result.message


def test_a_searched_but_empty_window_is_ok_and_says_so(tmp_path: Path) -> None:
    """The other side of the pair: examined, and genuinely nothing there.

    Distinguishing this from the two refusals above is the entire design, so it
    is asserted on the rendered text a human actually reads, not just on the Ok.
    """
    target = _target(tmp_path)
    transcript = _transcript(tmp_path, "sess", [_tool(-999, "Bash", "elsewhere")])

    result = wa.attribute(target, [transcript], window=60)

    assert isinstance(result, Ok)
    rendered = wa.render(result.value)
    assert "NO EVENTS" in rendered
    assert "not a failure to look" in rendered


def test_hooks_are_labelled_as_hooks_not_swallowed_as_system_records(tmp_path: Path) -> None:
    """A hook is the highest-value row — a command nobody remembers invoking."""
    target = _target(tmp_path)
    transcript = _transcript(tmp_path, "sess", [_hook(1, "SessionStart:startup")])

    result = wa.attribute(target, [transcript], window=60)

    assert isinstance(result, Ok)
    assert result.value.events[0].kind == "hook"


def test_a_missing_target_is_not_run_rather_than_a_crash(tmp_path: Path) -> None:
    result = wa.attribute(tmp_path / "nope.toml", [tmp_path / "x.jsonl"], window=60)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN


def test_render_states_the_cap_when_it_truncates(tmp_path: Path) -> None:
    """A cap is a bound; a truncated list read as complete is the failure."""
    target = _target(tmp_path)
    transcript = _transcript(
        tmp_path, "sess", [_tool(i * 0.1, "Bash", f"cmd {i}") for i in range(10)]
    )

    result = wa.attribute(target, [transcript], window=60)

    assert isinstance(result, Ok)
    rendered = wa.render(result.value, limit=3)
    assert "7 more not shown" in rendered


def test_malformed_lines_do_not_stop_the_scan(tmp_path: Path) -> None:
    """A transcript is append-only and can end mid-write; one bad line is not the end."""
    target = _target(tmp_path)
    path = tmp_path / "sess.jsonl"
    path.write_text(
        "{not json\n" + json.dumps(_tool(1, "Bash", "survived")) + "\n",
        encoding="utf-8",
    )
    later = _MTIME.timestamp() + 300
    os.utime(path, (later, later))

    result = wa.attribute(target, [path], window=60)

    assert isinstance(result, Ok)
    assert "survived" in result.value.events[0].detail


# ── the naive-timestamp crash (PR #406 bots, control-armed) ────────────────


def test_an_offsetless_timestamp_does_not_crash_the_scan(tmp_path: Path) -> None:
    """One offsetless line must not kill the whole run.

    `fromisoformat` returns a NAIVE datetime for a string with no offset, and
    `naive - aware` raises TypeError — so a single such line anywhere in any
    scanned transcript aborted the entire scan with an unhandled exception.

    Every fixture above carries an offset, which is exactly why no test here
    could see it. Both PR bots on #406 found it independently; a control arm
    confirmed `TypeError: can't subtract offset-naive and offset-aware`.
    """
    target = _target(tmp_path)
    offsetless: dict[str, object] = {
        "timestamp": "2026-08-20T06:03:34",
        "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "x"}}]},
    }
    transcript = _transcript(tmp_path, "sess", [offsetless])

    result = wa.attribute(target, [transcript], window=60)

    assert isinstance(result, Ok)
    assert len(result.value.events) == 1
    assert result.value.events[0].delta == 0.0


def test_an_offsetless_timestamp_is_read_as_utc_not_local() -> None:
    """The control arm on the ASSUMPTION, not just on the absence of a crash.

    Defaulting to the local zone would also stop the crash while silently
    shifting every offsetless event by the host's UTC offset — a bug that
    survives the test above and shows up as rows in the wrong place.
    """
    assert wa._parse_ts("2026-08-20T06:03:34") == datetime(2026, 8, 20, 6, 3, 34, tzinfo=UTC)
    assert wa._parse_ts("2026-08-20T06:03:34Z") == wa._parse_ts("2026-08-20T06:03:34")


# ── PR #406 second bot pass (graphify-labs) ────────────────────────────────


def test_every_parallel_tool_call_in_one_record_is_reported(tmp_path: Path) -> None:
    """One assistant record holds ALL the tool calls issued in parallel.

    `_describe` used to `return` on the first `tool_use` block, so a record with
    three parallel Bash calls contributed one row and the window read quieter
    than it was. For a module whose entire output is "what was running here",
    under-reporting is the failure that matters most. (graphify-labs, PR #406.)
    """
    target = _target(tmp_path)
    record: dict[str, object] = {
        "timestamp": _at(1),
        "message": {
            "content": [
                {"type": "text", "text": "ignored"},
                {"type": "tool_use", "name": "Bash", "input": {"command": "first"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "second"}},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/third"}},
            ]
        },
    }
    transcript = _transcript(tmp_path, "sess", [record])

    result = wa.attribute(target, [transcript], window=60)

    assert isinstance(result, Ok)
    details = [event.detail for event in result.value.events]
    assert len(details) == 3
    assert any("first" in d for d in details)
    assert any("second" in d for d in details)
    assert any("/third" in d for d in details)


def test_a_malformed_numeric_flag_is_refused_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A malformed numeric flag is refused, not raised.

    `--window abc` used to raise ValueError straight out of `main` — a stack
    trace from a module whose whole subject is reporting instead of raising.

    Asserting NOT_RUN rather than 0 is the point: silently keeping the default
    window would search a different window than the caller asked for and report
    the result as if it had answered their question.
    """
    target = _target(tmp_path)
    _transcript(tmp_path, "sess", [_tool(1, "Bash", "in window")])

    rc = wa.write_attribution_main(
        tmp_path, [str(target), "--window", "abc", "--transcripts", str(tmp_path)]
    )

    printed = capsys.readouterr().out
    # Asserted on the MESSAGE, not on the rc alone. The first version checked
    # only `rc == NOT_RUN` and SURVIVED its own mutation arm: swallowing the
    # ValueError also reaches NOT_RUN, by a different route entirely. A test that
    # passes for the wrong reason is invisible to every sweep over production
    # code, which is the class this whole arms spec exists to catch.
    assert "needs a number" in printed
    assert "'abc'" in printed
    assert rc == int(Rc.NOT_RUN)


def test_a_wellformed_numeric_flag_is_parsed_not_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The control arm — the guard above must not reject valid input.

    Asserted on the OUTPUT, not on a bare `rc != NOT_RUN`. The first draft of
    this test was `assert rc != int(Rc.NOT_RUN) or True`, which passes for every
    possible input — a test incapable of failing, written while fixing a finding
    about exactly that class of defect.
    """
    target = _target(tmp_path)
    _transcript(tmp_path, "sess", [_tool(1, "Bash", "in window")])

    rc = wa.write_attribution_main(
        tmp_path, [str(target), "--window", "5", "--transcripts", str(tmp_path)]
    )

    printed = capsys.readouterr().out
    assert "needs a number" not in printed
    assert "window  +/-5s" in printed
    assert rc == int(Rc.OK)


def test_a_flag_at_the_end_of_argv_is_refused_not_swallowed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A valued flag with nothing after it became the TARGET PATH.

    `[target, "--window"]` left `pending` empty, so `--window` fell through to
    `positional` — the caller's flag silently ignored and the DEFAULT window
    searched, then reported as if it had answered their question. That is the
    exact failure the not-a-number guard was written to prevent, and the first
    version of that guard covered only half the pair.
    """
    target = _target(tmp_path)
    _transcript(tmp_path, "sess", [_tool(1, "Bash", "in window")])

    rc = wa.write_attribution_main(
        tmp_path, [str(target), "--transcripts", str(tmp_path), "--window"]
    )

    printed = capsys.readouterr().out
    assert "--window needs a value" in printed
    assert rc == int(Rc.NOT_RUN)


def test_the_transcripts_flag_is_covered_by_the_same_guard(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The sibling half: `--transcripts` consumes a value too.

    Named separately because the first fix handled `--window`/`--limit` as a set
    and left `--transcripts` on its own `elif` — so a guard added for the pair
    would have missed the third one. A finding is a SAMPLE of a class.
    """
    target = _target(tmp_path)

    rc = wa.write_attribution_main(tmp_path, [str(target), "--transcripts"])

    printed = capsys.readouterr().out
    assert "--transcripts needs a value" in printed
    assert rc == int(Rc.NOT_RUN)
