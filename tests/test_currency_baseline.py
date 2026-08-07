# Copyright (c) 2026 Raymond Manaloto
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
    # The store is typed `object`-valued on purpose (it is untrusted JSON), so the
    # test asserts on the round-tripped shape rather than subscripting through it.
    assert store == {"graphify": {"latest": "0.9.30", "observed_at": _NOW.isoformat()}}


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


# ----------------------- a crash is not a verdict (cold-lane findings) ----
#
# `load` guarded JSON *syntax* only, so a structurally-valid-but-wrong cache
# parsed cleanly and then raised out of `behind()`. This runs in the SessionStart
# hook, where an AttributeError surfaces as a broken session rather than as
# "could not check".


def test_a_non_dict_entry_is_unchecked_not_a_crash() -> None:
    """`{"graphify": "oops"}` is valid JSON and used to raise AttributeError."""
    found = baseline.behind("graphify", "0.9.26", {"graphify": "oops"}, now=_NOW)
    assert found is not None
    assert found.check == "upstream-cache"
    # And MALFORMED is reported as itself, not as "nobody has ever run the loop".
    assert "MALFORMED" in found.detail


def test_malformed_and_never_recorded_are_different_messages() -> None:
    """Two blocked comparisons, two causes. Collapsing them loses the fix.

    One says run the loop; the other says the committed cache is corrupt.
    """
    absent = baseline.behind("graphify", "0.9.26", {}, now=_NOW)
    corrupt = baseline.behind("graphify", "0.9.26", {"graphify": []}, now=_NOW)
    assert absent is not None
    assert corrupt is not None
    assert absent.detail != corrupt.detail
    assert "has ever been recorded" in absent.detail
    assert "MALFORMED" in corrupt.detail


def test_a_non_string_version_is_unchecked_not_a_crash() -> None:
    """`{"latest": 123}` used to raise on `.strip()` inside Version.parse."""
    found = baseline.behind("graphify", "0.9.26", {"graphify": {"latest": 123}}, now=_NOW)
    assert found is not None
    assert found.check == "upstream-cache"
    assert "MALFORMED" in found.detail


def test_a_non_string_observed_at_does_not_crash() -> None:
    """The date field gets the same treatment as the version field."""
    store = {"graphify": {"latest": "0.9.30", "observed_at": 12345}}
    found = baseline.behind("graphify", "0.9.26", store, now=_NOW)
    assert found is not None
    assert found.check == "upstream-version"


def test_an_unparsable_version_reports_unknown_not_a_direction() -> None:
    """A string `!=` cannot know WHICH side is newer.

    The old fallback rendered `pinned at 0.9.26 but upstream had nightly` — a
    definite claim about ordering, from a comparison that never happened.
    """
    store = _cache("nightly")
    found = baseline.behind("graphify", "0.9.26", store, now=_NOW)
    assert found is not None
    assert found.check == "upstream-cache"
    assert "cannot compare" in found.detail
    assert "UNKNOWN" in found.detail


def test_an_unparsable_pin_is_also_unknown_not_behind() -> None:
    """Symmetric: the unreadable side can be either one."""
    found = baseline.behind("graphify", "not-a-version", _cache("0.9.30"), now=_NOW)
    assert found is not None
    assert found.check == "upstream-cache"
    assert "cannot compare" in found.detail


def test_a_comparable_pair_still_reports_a_real_direction() -> None:
    """Control arm: the unknown-path must not have swallowed the real finding."""
    found = baseline.behind("graphify", "0.9.26", _cache("0.9.30"), now=_NOW)
    assert found is not None
    assert found.check == "upstream-version"


def test_a_falsy_non_string_latest_is_malformed_not_never_recorded() -> None:
    """The round-1 fix's own gap: a FALSY non-string was never reachable.

    `0`, `false` and `[]` are falsy, and were caught by a truthiness test that ran
    BEFORE the type narrowing — so the MALFORMED branch was unreachable for exactly
    the corrupt-cache class it was added to name.
    `test_malformed_and_never_recorded_are_different_messages` only ever exercised
    a TRUTHY malformed value (a string), which is why it stayed green.
    """
    for junk in (0, False, [], {}):
        found = baseline.behind("graphify", "0.9.26", {"graphify": {"latest": junk}}, now=_NOW)
        assert found is not None, junk
        assert "MALFORMED" in found.detail, junk
        assert "has ever been recorded" not in found.detail, junk


def test_an_absent_or_empty_latest_is_still_never_recorded() -> None:
    """CONTROL ARM: the reorder must not invent corruption.

    Putting the type check first must not turn "nobody ran the loop" into "the
    cache is corrupt". An absent key, an explicit null, and an
    empty string all mean nothing was ever written — not corruption.
    """
    for entry in ({}, {"latest": None}, {"latest": ""}):
        found = baseline.behind("graphify", "0.9.26", {"graphify": entry}, now=_NOW)
        assert found is not None, entry
        assert "has ever been recorded" in found.detail, entry
        assert "MALFORMED" not in found.detail, entry
