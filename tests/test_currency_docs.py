"""Tests for `kb_setup.currency.docs` — documentation-drift detection.

The point of this module is to notice when a page whose CONTENT is the interface
changes without a version moving. So the tests that matter are the ones proving
it can return BOTH answers: a checker that can only say "unchanged" would report
green forever, which is precisely the false-green the currency engine refuses
everywhere else.

The offline/network split is tested separately because conflating them is the
design error this module exists to avoid: `staleness` must never need a fetch,
and `verify` must never overwrite a good baseline with a failed one.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from kb_setup.currency import docs

_URL = "https://code.claude.com/docs/en/goal.md"
_NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


def _store(when: datetime, digest: str = "abc") -> dict[str, dict[str, str]]:
    return {_URL: {"sha256": digest, "checked_at": when.isoformat()}}


def test_a_page_never_verified_is_reported() -> None:
    """An absent baseline is a finding, not a pass — nobody has ever looked."""
    findings = docs.staleness((_URL,), {}, now=_NOW)
    assert len(findings) == 1
    assert "never verified" in findings[0].detail


def test_a_recently_verified_page_is_silent() -> None:
    """CONTROL ARM: staleness must be able to return nothing.

    Otherwise every session carries noise it learns to skip.
    """
    fresh = _store(_NOW - timedelta(days=1))
    assert docs.staleness((_URL,), fresh, now=_NOW) == []


def test_an_old_verification_is_reported_as_stale_not_as_drift() -> None:
    """Stale is not drift.

    We know nobody looked, NOT that the page changed. Claiming drift here would
    be inventing a finding.
    """
    old = _store(_NOW - timedelta(days=docs.STALE_AFTER_DAYS + 1))
    findings = docs.staleness((_URL,), old, now=_NOW)
    assert len(findings) == 1
    assert findings[0].check == "docs-staleness"
    assert not findings[0].drifted


def test_staleness_never_fetches() -> None:
    """The SessionStart path must stay offline. A fetcher that raises proves it.

    `staleness` takes no fetcher at all, so this is a structural assertion: if
    someone later wires a network call into it, this import-free call would start
    doing IO and the test would no longer describe reality — hence the explicit
    check that the signature has not grown one.
    """
    assert "fetcher" not in docs.staleness.__code__.co_varnames


def test_a_changed_page_is_drift() -> None:
    """THE point of the module."""
    findings, _ = docs.verify(
        (_URL,), _store(_NOW, "old-digest"), fetcher=lambda _u: ("new body", "")
    )
    assert findings[0].drifted
    assert findings[0].verified
    assert "kb-curator" in findings[0].detail


def test_an_unchanged_page_is_not_drift() -> None:
    """CONTROL ARM: same body twice must report unchanged, or 'drift' means nothing."""
    body = "stable body"
    first, store = docs.verify((_URL,), {}, fetcher=lambda _u: (body, ""))
    assert first[0].check == "docs-baseline"  # first run records, does not accuse
    second, _ = docs.verify((_URL,), store, fetcher=lambda _u: (body, ""))
    assert not second[0].drifted
    assert second[0].verified


def test_a_failed_fetch_is_not_checked_and_never_a_pass() -> None:
    """An unreachable page must not read as unchanged.

    Same rule the rest of the engine follows: "could not ask" and "asked and it
    agrees" are different.
    """
    findings, _ = docs.verify((_URL,), _store(_NOW), fetcher=lambda _u: ("", "HTTP 503"))
    assert not findings[0].verified
    assert not findings[0].drifted
    assert "NOT CHECKED" in findings[0].detail


def test_a_failed_fetch_leaves_the_baseline_intact() -> None:
    """An outage must never overwrite a good baseline with nothing.

    Otherwise a single 503 silently resets drift detection to zero.
    """
    before = _store(_NOW, "good-digest")
    _, after = docs.verify((_URL,), before, fetcher=lambda _u: ("", "boom"))
    assert after[_URL]["sha256"] == "good-digest"


def test_a_drifted_page_updates_the_baseline() -> None:
    """Recording is the point.

    The NEXT run compares against what we have now seen, so without this a drift
    would be reported again every run.
    """
    _, after = docs.verify((_URL,), _store(_NOW, "old"), fetcher=lambda _u: ("new", ""))
    assert after[_URL]["sha256"] != "old"


def test_non_https_is_refused() -> None:
    """The scheme is a property of the connection class, not of config text.

    A config value must not be able to steer a fetch at `file:` or another scheme.
    """
    body, err = docs._fetch("file:///etc/passwd")
    assert body == ""
    assert "refusing non-https" in err


def test_the_store_round_trips(tmp_path: Path) -> None:
    """Committed baseline: written sorted so a diff shows content, not reordering."""
    store = _store(_NOW)
    docs.save(tmp_path, store)
    assert docs.load(tmp_path) == store


def test_an_unreadable_store_reads_as_empty_not_as_verified(tmp_path: Path) -> None:
    """Corrupt JSON must degrade to 'never verified', never to silence."""
    path = tmp_path / docs.FINGERPRINT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert docs.load(tmp_path) == {}
    assert docs.staleness((_URL,), docs.load(tmp_path), now=_NOW)
