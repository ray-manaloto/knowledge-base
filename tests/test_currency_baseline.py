"""Tests for `kb_setup.currency.baseline` — the offline pin-vs-upstream check.

The gap this module closes: step 1 compared the INSTALL against the PIN, both of
which live on this machine, so it was silent while graphify sat pinned at 0.9.26
with 0.9.30 released. Install and pin agreed with each other, and the third
version in the picture was never in the comparison at all.

So the tests that matter are the ones proving it returns BOTH answers, and that
the three not-current states stay distinct: BEHIND (we know we are stale), NO
RECORD (nobody has ever checked), and STALE OBSERVATION (the cache agrees, but it
is too old to be evidence). Collapsing any of those into "clean" is the
false-green this engine refuses everywhere.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from kb_setup.currency import baseline

_NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def _cache(latest: str, *, observed: datetime | None = None) -> dict[str, dict[str, str]]:
    return {"graphify": {"latest": latest, "observed_at": (observed or _NOW).isoformat()}}


def test_a_pin_behind_the_cached_upstream_is_reported() -> None:
    """The measured case: 0.9.26 pinned, 0.9.30 released, every session silent."""
    found = baseline.behind("graphify", "0.9.26", _cache("0.9.30"), now=_NOW)
    assert found is not None
    assert found.check == "upstream-version"
    assert "0.9.26" in found.detail
    assert "0.9.30" in found.detail


def test_a_pin_matching_a_fresh_observation_is_silent() -> None:
    """CONTROL ARM: the check must be able to say nothing, or it is noise."""
    assert baseline.behind("graphify", "0.9.30", _cache("0.9.30"), now=_NOW) is None


def test_a_v_prefixed_cached_tag_is_not_read_as_being_behind() -> None:
    """Versions are compared parsed, not as strings — `v0.9.30` is not ahead of `0.9.30`.

    The same one-character trap that made claude-code report an upgrade to the
    release it was already running.
    """
    assert baseline.behind("graphify", "0.9.30", _cache("v0.9.30"), now=_NOW) is None


def test_a_pin_ahead_of_the_cache_is_silent() -> None:
    """A local pin newer than the last observation is not drift.

    This is the normal state right after a bump lands and before the next full
    run refreshes the cache; nagging here would fire on every successful upgrade.
    """
    assert baseline.behind("graphify", "0.9.31", _cache("0.9.30"), now=_NOW) is None


def test_no_recorded_observation_is_a_finding_not_a_pass() -> None:
    """Nobody has ever looked. That is unchecked, not current."""
    found = baseline.behind("graphify", "0.9.26", {}, now=_NOW)
    assert found is not None
    assert found.check == "upstream-cache"
    assert "has ever been recorded" in found.detail


def test_an_entry_with_no_latest_is_also_unchecked() -> None:
    """A malformed/empty entry must not borrow the credibility of a real one."""
    found = baseline.behind("graphify", "0.9.26", {"graphify": {"latest": ""}}, now=_NOW)
    assert found is not None
    assert found.check == "upstream-cache"


def test_agreement_with_a_stale_observation_is_not_evidence_of_being_current() -> None:
    """The third state. Matching a months-old cache says nothing about today."""
    old = _cache("0.9.30", observed=_NOW - timedelta(days=baseline.STALE_AFTER_DAYS + 1))
    found = baseline.behind("graphify", "0.9.30", old, now=_NOW)
    assert found is not None
    assert found.check == "upstream-cache"
    assert "stale observation" in found.detail


def test_being_behind_outranks_being_stale() -> None:
    """Two things are true; report the actionable one.

    A stale cache that ALSO shows us behind should say "you are behind", not
    "your cache is old" — the version gap is the finding, and burying it under a
    housekeeping note is how it gets skipped.
    """
    old = _cache("0.9.30", observed=_NOW - timedelta(days=baseline.STALE_AFTER_DAYS + 1))
    found = baseline.behind("graphify", "0.9.26", old, now=_NOW)
    assert found is not None
    assert found.check == "upstream-version"


def test_an_unparsable_observed_at_is_treated_as_stale() -> None:
    """Fail closed: an unreadable date is not a fresh one."""
    broken = {"graphify": {"latest": "0.9.30", "observed_at": "not-a-date"}}
    found = baseline.behind("graphify", "0.9.30", broken, now=_NOW)
    assert found is not None
    assert found.check == "upstream-cache"


def test_recording_refreshes_the_observation() -> None:
    store = baseline.record({}, "graphify", "0.9.30", now=_NOW)
    assert store["graphify"]["latest"] == "0.9.30"
    assert store["graphify"]["observed_at"] == _NOW.isoformat()


def test_recording_an_empty_latest_is_refused() -> None:
    """A failed lookup and a tool with no release channel both arrive as "".

    Writing that would cache a claim that upstream offers nothing — turning an
    outage into a permanent false green.
    """
    assert baseline.record({}, "ffmpeg", "", now=_NOW) == {}
    # And it must not clobber a good existing entry either.
    good = _cache("0.9.30")
    assert baseline.record(good, "graphify", "", now=_NOW) == good


def test_recording_does_not_mutate_the_input_store() -> None:
    """The caller threads the store through a loop; in-place edits would surprise."""
    before = _cache("0.9.30")
    snapshot = dict(before["graphify"])
    baseline.record(before, "graphify", "0.9.31", now=_NOW)
    assert before["graphify"] == snapshot


def test_the_store_round_trips(tmp_path) -> None:
    """Committed cache: written sorted so a diff shows content, not reordering."""
    store = _cache("0.9.30")
    baseline.save(tmp_path, store)
    assert baseline.load(tmp_path) == store


def test_an_unreadable_store_reads_as_empty_not_as_current(tmp_path) -> None:
    """Corrupt JSON must degrade to 'never recorded', never to silence."""
    path = tmp_path / baseline.BASELINE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert baseline.load(tmp_path) == {}
    # Control arm: which then reports as unchecked rather than clean.
    assert baseline.behind("graphify", "0.9.26", baseline.load(tmp_path), now=_NOW) is not None


def test_a_missing_store_is_not_an_error(tmp_path) -> None:
    assert baseline.load(tmp_path) == {}
