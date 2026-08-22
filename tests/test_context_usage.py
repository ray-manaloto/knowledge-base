# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.context_usage`.

The defect these guard is a trigger that could never fire, so the tests are
weighted toward the directions that fail SILENTLY: a subagent being allowed
through, an unmeasurable session rendering as "fine", and a budget number being
mistaken for occupancy.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from kb_setup import context_usage, session_select


def _turn(
    inp: int, cache_read: int = 0, cache_create: int = 0, model: str = "claude-opus-5"
) -> dict:
    return {
        "type": "assistant",
        "message": {
            "model": model,
            "usage": {
                "input_tokens": inp,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_create,
            },
        },
    }


def _transcript(tmp_path, records, name="s.jsonl") -> Path:
    d = tmp_path / "proj"
    d.mkdir(exist_ok=True)
    p = d / name
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# The main-thread gate — the direction Ray named explicitly.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("retired", ["CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_FORK_SUBAGENT"])
def test_the_two_retired_names_are_not_treated_as_markers(retired):
    """The refutation, pinned by name so putting either back goes red.

    Both were read as "this is a subagent" and neither is. Per the vendor docs
    this repo has ingested, `CLAUDE_CODE_CHILD_SESSION` marks ANY subprocess
    Claude Code spawns — every Bash tool call, main thread included
    (`env-vars.md:208`) — and `CLAUDE_CODE_FORK_SUBAGENT` is an operator-set flag
    that ENABLES forking (`changelog.md:2211`). Measured on the main thread
    2026-08-22: both present, so the old detector refused 100% of the time.

    This is the test the module never had. The retired one asserted the POSITIVE
    case only — that a declared marker is detected — which stays true of a marker
    that means nothing, so it could not have caught this.
    """
    assert retired not in context_usage.CHILD_MARKERS
    assert context_usage.child_marker({retired: "1"}) is None


def test_a_declared_marker_would_still_be_detected(monkeypatch):
    """The seam still works, so the retirement is not a silent amputation.

    `CHILD_MARKERS` is empty because nothing belongs in it, not because the
    mechanism was removed. Armed with a stand-in rather than a real variable
    name — using a real one here would re-assert the claim just refuted.
    """
    monkeypatch.setattr(context_usage, "CHILD_MARKERS", ("A_REAL_DISCRIMINATOR",))
    assert context_usage.child_marker({"A_REAL_DISCRIMINATOR": "1"}) == "A_REAL_DISCRIMINATOR"
    assert context_usage.child_marker({"SOMETHING_ELSE": "1"}) is None


def test_an_empty_marker_is_absent_not_present(monkeypatch):
    """An exported-but-empty var is how a shell says 'unset'.

    Treating it as present would silence the MAIN session in exactly the
    environments that export placeholders — a failure that looks like the
    original defect and would be blamed on it.
    """
    monkeypatch.setattr(context_usage, "CHILD_MARKERS", ("A_REAL_DISCRIMINATOR",))
    assert context_usage.child_marker({"A_REAL_DISCRIMINATOR": ""}) is None
    assert context_usage.child_marker({"A_REAL_DISCRIMINATOR": "   "}) is None


def test_main_measures_on_the_main_thread_despite_the_retired_vars(tmp_path, monkeypatch):
    """The bug, armed end-to-end: this env IS the main thread's real env.

    Before 2026-08-22 this returned 3 and measured nothing, which is what made
    `/clear-prep`'s context trigger inert on every session that ever ran it.
    """
    monkeypatch.setenv("CLAUDE_CODE_CHILD_SESSION", "1")
    monkeypatch.setenv("CLAUDE_CODE_FORK_SUBAGENT", "1")
    called: list[int] = []
    monkeypatch.setattr(context_usage, "measure", lambda *_a, **_k: called.append(1))
    assert context_usage.main([], tmp_path) == 127
    assert called, "the main thread must MEASURE, not decline"


def test_main_still_declines_for_a_genuine_marker(tmp_path, monkeypatch):
    """rc=3 is retained, not deleted — it just has nothing to fire on today."""
    monkeypatch.setattr(context_usage, "CHILD_MARKERS", ("A_REAL_DISCRIMINATOR",))
    monkeypatch.setenv("A_REAL_DISCRIMINATOR", "1")
    called = []
    monkeypatch.setattr(context_usage, "measure", lambda *_a, **_k: called.append(1))
    assert context_usage.main([], tmp_path) == 3
    assert not called, "a subagent must not even measure — it has nothing to report on"


# --------------------------------------------------------------------------
# Occupancy: the three usage fields, summed — not the budget reminder.
# --------------------------------------------------------------------------


def test_occupancy_sums_all_three_usage_fields(tmp_path, monkeypatch):
    p = _transcript(tmp_path, [_turn(1_000, 2_000, 3_000)])
    monkeypatch.setattr(context_usage, "own_transcript", lambda *_a, **_k: p)
    usage = context_usage.measure(tmp_path)
    assert usage is not None
    assert usage.occupancy == 6_000, "cache_read and cache_creation ARE context the model held"


def test_occupancy_is_the_last_turn_not_the_sum_of_turns(tmp_path, monkeypatch):
    """Context is what one turn held, not what every turn cumulatively cost.

    Summing turns is the natural wrong implementation and would report an
    occupancy far above the window, which reads as a broken window rather than
    a broken measurement.
    """
    p = _transcript(tmp_path, [_turn(100_000), _turn(200_000), _turn(300_000)])
    monkeypatch.setattr(context_usage, "own_transcript", lambda *_a, **_k: p)
    usage = context_usage.measure(tmp_path)
    assert usage is not None
    assert usage.occupancy == 300_000
    assert usage.turns == 3


def test_a_transcript_with_no_usage_is_unmeasurable_not_zero(tmp_path, monkeypatch):
    p = _transcript(tmp_path, [{"type": "user", "message": {"content": "hi"}}])
    monkeypatch.setattr(context_usage, "own_transcript", lambda *_a, **_k: p)
    assert context_usage.measure(tmp_path) is None


def test_unparsable_lines_are_skipped_not_fatal(tmp_path, monkeypatch):
    d = tmp_path / "proj"
    d.mkdir()
    p = d / "s.jsonl"
    p.write_text("{not json\n" + json.dumps(_turn(5_000)) + "\n", encoding="utf-8")
    monkeypatch.setattr(context_usage, "own_transcript", lambda *_a, **_k: p)
    usage = context_usage.measure(tmp_path)
    assert usage is not None
    assert usage.occupancy == 5_000


# --------------------------------------------------------------------------
# Windows and rendering.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("claude-opus-5", 1_000_000),
        ("claude-fable-5", 1_000_000),
        ("claude-sonnet-5", 1_000_000),
        ("claude-haiku-4-5-20251001", 200_000),
    ],
)
def test_known_windows(model, expected):
    assert context_usage.window_for(model) == expected


def test_an_unknown_model_has_no_window_rather_than_a_guessed_one():
    assert context_usage.window_for("some-future-model") is None


def test_an_unknown_window_renders_127_not_a_percentage(tmp_path):
    usage = context_usage.Usage(
        transcript=tmp_path / "s.jsonl", model="mystery", occupancy=9, window=None, turns=1
    )
    report, code = context_usage.render(usage)
    assert code == 127
    assert "%" not in report.split("UNKNOWN")[-1].split("\n")[0]
    assert usage.pct is None
    assert not usage.over_threshold


def test_over_threshold_returns_10_and_says_what_to_do(tmp_path):
    usage = context_usage.Usage(
        transcript=tmp_path / "s.jsonl",
        model="claude-opus-5",
        occupancy=475_917,
        window=1_000_000,
        turns=380,
    )
    report, code = context_usage.render(usage)
    assert code == 10
    assert "47.6%" in report
    assert "/clear-prep" in report


def test_under_threshold_returns_0(tmp_path):
    usage = context_usage.Usage(
        transcript=tmp_path / "s.jsonl",
        model="claude-opus-5",
        occupancy=50_000,
        window=1_000_000,
        turns=10,
    )
    report, code = context_usage.render(usage)
    assert code == 0
    assert "5.0%" in report


def test_could_not_measure_never_renders_as_fine():
    report, code = context_usage.render(None)
    assert code == 127
    assert "NOT MEASURABLE" in report
    assert "not 'you have room'" in report


def test_threshold_is_exclusive_of_nothing_at_exactly_20_percent(tmp_path):
    """At exactly the threshold it must fire — `>=`, not `>`.

    A `>` here would make the documented "passes ~20%" true only strictly above,
    which is the off-by-one that lets a boundary case sit silent.
    """
    usage = context_usage.Usage(
        transcript=tmp_path / "s.jsonl",
        model="claude-opus-5",
        occupancy=200_000,
        window=1_000_000,
        turns=1,
    )
    assert usage.over_threshold
    assert context_usage.render(usage)[1] == 10


# --------------------------------------------------------------------------
# The regression this whole module exists for.
# --------------------------------------------------------------------------


def test_the_budget_reminder_is_never_read_as_occupancy(tmp_path, monkeypatch):
    """The original defect, pinned.

    A transcript carrying a huge `total_tokens` budget reminder AND a modest
    real occupancy must report the occupancy. Reading the reminder would report
    ~99.9% remaining and stay silent at 47.6% full, which is exactly what
    happened on 2026-08-21.
    """
    records = [
        _turn(475_917),
        {
            "type": "attachment",
            "attachment": {
                "type": "total_tokens_reminder",
                "text": "<total_tokens>14981005 tokens left</total_tokens>",
            },
        },
    ]
    p = _transcript(tmp_path, records)
    monkeypatch.setattr(context_usage, "own_transcript", lambda *_a, **_k: p)
    usage = context_usage.measure(tmp_path)
    assert usage is not None
    assert usage.occupancy == 475_917, "must be occupancy, never the budget countdown"
    assert usage.over_threshold
    assert context_usage.render(usage)[1] == 10


# --------------------------------------------------------------------------
# Which transcript is OURS — id first, mtime only as the fallback.
#
# The cold lane on `870c020c` found that newest-by-mtime answers a different
# question than "this session", and the two diverge the moment a second session
# runs against the repo. `clear-prep` treats `kb-context` as authoritative for
# its 20% trigger, so picking the wrong transcript reports a stranger's number.
# --------------------------------------------------------------------------


def _projects(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """A real transcript directory for `tmp_path`, plus the env that finds it."""
    env = {"CLAUDE_CONFIG_DIR": str(tmp_path / "cfg")}
    directory = session_select.transcript_dir(tmp_path, env)
    directory.mkdir(parents=True, exist_ok=True)
    return env, directory


def _write(directory: Path, stem: str, mtime: float) -> Path:
    p = directory / f"{stem}.jsonl"
    p.write_text(json.dumps(_turn(1_000)) + "\n", encoding="utf-8")
    os.utime(p, (mtime, mtime))
    return p


def test_own_transcript_prefers_this_sessions_id_over_a_newer_stranger(tmp_path):
    """THE FINDING: a concurrent session wrote more recently than we did.

    Without the id, `kb-context` reports the other session's occupancy — and
    `clear-prep` acts on it. The stranger is deliberately the mtime winner, so
    an implementation that ignores the id cannot pass this by accident.
    """
    env, directory = _projects(tmp_path)
    mine = _write(directory, "aaaa1111-0000-4000-8000-000000000001", mtime=1_000)
    _write(directory, "bbbb2222-0000-4000-8000-000000000002", mtime=9_000)
    env["CLAUDE_CODE_SESSION_ID"] = mine.stem

    assert context_usage.own_transcript(tmp_path, env) == mine


def test_own_transcript_falls_back_to_mtime_with_no_session_id(tmp_path):
    """The control arm: without an id this is the behaviour that already shipped.

    It is also the arm that proves the test above is not just "returns whatever
    the id names" — same two files, same mtimes, only the id is absent.
    """
    env, directory = _projects(tmp_path)
    _write(directory, "aaaa1111-0000-4000-8000-000000000001", mtime=1_000)
    newest = _write(directory, "bbbb2222-0000-4000-8000-000000000002", mtime=9_000)

    assert context_usage.own_transcript(tmp_path, env) == newest


def test_own_transcript_refuses_a_stranger_when_the_id_names_no_file(tmp_path):
    """A known identity with an absent file is UNMEASURABLE, not someone else.

    This test asserted the opposite until `37684723`, on the reasoning that
    "failing to the pre-existing mtime rule is the safe direction". It is not:
    knowing who we are AND that our transcript is absent is positive evidence
    that the newest file belongs to another session, so the fallback handed
    `clear-prep` a stranger's occupancy as though it were ours.

    None surfaces as exit 127, which this module's caller already renders as
    explicitly NOT "you are fine" — a real answer, where the old behaviour
    manufactured a number. Raised independently by the cold lane and CodeRabbit.
    """
    env, directory = _projects(tmp_path)
    _write(directory, "bbbb2222-0000-4000-8000-000000000002", mtime=9_000)
    env["CLAUDE_CODE_SESSION_ID"] = "cccc3333-0000-4000-8000-000000000003"

    assert context_usage.own_transcript(tmp_path, env) is None


def test_own_transcript_still_uses_mtime_when_there_is_no_id_at_all(tmp_path):
    """THE ARM. Not knowing who we are is the one case mtime still serves.

    Without this the change above would read as "never fall back", which would
    break every hook shell and test that has no `CLAUDE_CODE_SESSION_ID`.
    """
    env, directory = _projects(tmp_path)
    newest = _write(directory, "bbbb2222-0000-4000-8000-000000000002", mtime=9_000)
    env.pop("CLAUDE_CODE_SESSION_ID", None)

    assert context_usage.own_transcript(tmp_path, env) == newest


def test_a_bare_null_line_does_not_crash_the_measurement(tmp_path, monkeypatch):
    """`json.loads("null")` RAISES NOTHING — it returns None, and `.get` then dies.

    The except clause guards the parse; it cannot guard the parse's result. One
    odd line in a transcript took down the whole measurement.
    """
    p = tmp_path / "s.jsonl"
    p.write_text("null\n123\n" + json.dumps(_turn(5_000)) + "\n", encoding="utf-8")
    monkeypatch.setattr(context_usage, "own_transcript", lambda *_a, **_k: p)

    usage = context_usage.measure(tmp_path)

    assert usage is not None
    assert usage.occupancy == 5_000, "the real turn is still measured past the junk lines"


def test_a_non_numeric_usage_field_does_not_crash_the_measurement(tmp_path, monkeypatch):
    """THE SAME LESSON ONE STEP FURTHER IN, and the test above could not see it.

    `{"input_tokens": "unknown"}` is a dict, so every `isinstance` guard above
    passes it through — and `int()` then raised ValueError out of `_last_usage`,
    killing the measurement of every LATER well-formed turn over one odd line.
    The bare-null test cannot catch this: its junk lines die at `.get`, before
    the arithmetic.

    The malformed record is deliberately in the MIDDLE, so a fix that merely
    stopped the crash without continuing the scan would still fail this.
    """
    p = tmp_path / "s.jsonl"
    p.write_text(
        json.dumps(_turn(1_000))
        + "\n"
        + json.dumps({"message": {"usage": {"input_tokens": "unknown"}}})
        + "\n"
        + json.dumps(_turn(7_000))
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(context_usage, "own_transcript", lambda *_a, **_k: p)

    usage = context_usage.measure(tmp_path)

    assert usage is not None
    assert usage.occupancy == 7_000, "the LAST good turn, measured past the malformed one"
