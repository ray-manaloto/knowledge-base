# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.context_usage`.

The defect these guard is a trigger that could never fire, so the tests are
weighted toward the directions that fail SILENTLY: a subagent being allowed
through, an unmeasurable session rendering as "fine", and a budget number being
mistaken for occupancy.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import context_usage


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


@pytest.mark.parametrize("marker", context_usage.CHILD_MARKERS)
def test_every_declared_child_marker_is_detected(marker):
    assert context_usage.child_marker({marker: "1"}) == marker


def test_main_thread_has_no_marker():
    assert context_usage.child_marker({"CLAUDE_CODE_SESSION_ID": "abc", "CLAUDECODE": "1"}) is None


def test_an_empty_marker_is_absent_not_present():
    """An exported-but-empty var is how a shell says 'unset'.

    Treating it as present would silence the MAIN session in exactly the
    environments that export placeholders — a failure that looks like the
    original defect and would be blamed on it.
    """
    assert context_usage.child_marker({"CLAUDE_CODE_CHILD_SESSION": ""}) is None
    assert context_usage.child_marker({"CLAUDE_CODE_CHILD_SESSION": "   "}) is None


def test_main_returns_3_and_measures_nothing_when_a_child_marker_is_set(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_CHILD_SESSION", "1")
    called = []
    monkeypatch.setattr(context_usage, "measure", lambda *_a, **_k: called.append(1))
    assert context_usage.main([], tmp_path) == 3
    assert not called, "a subagent must not even measure — it has nothing to report on"


def test_main_measures_when_no_marker_is_set(tmp_path, monkeypatch):
    for name in context_usage.CHILD_MARKERS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(context_usage, "measure", lambda *_a, **_k: None)
    assert context_usage.main([], tmp_path) == 127


# --------------------------------------------------------------------------
# Occupancy: the three usage fields, summed — not the budget reminder.
# --------------------------------------------------------------------------


def test_occupancy_sums_all_three_usage_fields(tmp_path, monkeypatch):
    p = _transcript(tmp_path, [_turn(1_000, 2_000, 3_000)])
    monkeypatch.setattr(context_usage, "newest_transcript", lambda *_a, **_k: p)
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
    monkeypatch.setattr(context_usage, "newest_transcript", lambda *_a, **_k: p)
    usage = context_usage.measure(tmp_path)
    assert usage is not None
    assert usage.occupancy == 300_000
    assert usage.turns == 3


def test_a_transcript_with_no_usage_is_unmeasurable_not_zero(tmp_path, monkeypatch):
    p = _transcript(tmp_path, [{"type": "user", "message": {"content": "hi"}}])
    monkeypatch.setattr(context_usage, "newest_transcript", lambda *_a, **_k: p)
    assert context_usage.measure(tmp_path) is None


def test_unparsable_lines_are_skipped_not_fatal(tmp_path, monkeypatch):
    d = tmp_path / "proj"
    d.mkdir()
    p = d / "s.jsonl"
    p.write_text("{not json\n" + json.dumps(_turn(5_000)) + "\n", encoding="utf-8")
    monkeypatch.setattr(context_usage, "newest_transcript", lambda *_a, **_k: p)
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
    monkeypatch.setattr(context_usage, "newest_transcript", lambda *_a, **_k: p)
    usage = context_usage.measure(tmp_path)
    assert usage is not None
    assert usage.occupancy == 475_917, "must be occupancy, never the budget countdown"
    assert usage.over_threshold
    assert context_usage.render(usage)[1] == 10
