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

from kb_setup.currency import docs, run
from kb_setup.fetch import content_hash

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


def test_a_drifted_page_keeps_its_old_baseline_until_reviewed() -> None:
    """Reversed 2026-07-29, deliberately. This test used to assert the opposite.

    Its old rationale — "without this a drift would be reported again every run" —
    named the desired behaviour as the thing to avoid. Recording here consumed the
    signal on the very run that raised it, and docs drift is NOT a sync finding, so
    nothing durable carried it: all three watched Claude Code pages changed, the
    committed row read `claude-code 2.1.220, current: clean`, and the next run was
    silent. A page therefore stays flagged until `mark_reviewed` rolls it forward.
    """
    _, after = docs.verify((_URL,), _store(_NOW, "old"), fetcher=lambda _u: ("new", ""))
    assert after[_URL]["sha256"] == "old"


def test_the_drift_finding_is_still_raised_while_the_baseline_holds() -> None:
    """Control arm: keeping the baseline must not also swallow the report."""
    findings, _ = docs.verify((_URL,), _store(_NOW, "old"), fetcher=lambda _u: ("new", ""))
    assert findings[0].drifted
    assert "docs-reviewed" in findings[0].detail


def test_the_drift_finding_names_a_command_that_actually_runs(tmp_path: Path) -> None:
    """The remedy a message prescribes must be one the code accepts.

    `docs-reviewed` grew a required `--tool` (a dangling flag used to roll EVERY
    watched tool's baseline), and this message still read
    `kb-setup currency docs-reviewed` — so following the instruction verbatim
    exits 2. A self-contradiction introduced by the very fix that hardened the
    command, in the same commit range, one file away.

    Both halves are asserted rather than just grepping for `--tool`: the message
    must name the flag, AND the guard must really refuse the flagless form. A
    test on the string alone would stay green if the guard were later dropped,
    leaving the message over-specified instead of the code under-specified.
    """
    findings, _ = docs.verify((_URL,), _store(_NOW, "old"), fetcher=lambda _u: ("new", ""))
    assert "docs-reviewed --tool" in findings[0].detail

    (tmp_path / "mise.toml").write_text("[tools]\n", encoding="utf-8")
    (tmp_path / "currency.toml").write_text(
        f'[tool.claude-code]\nbinary = "claude"\nexpected = "2.1.220"\ndocs_watch = ["{_URL}"]\n',
        encoding="utf-8",
    )
    assert run.docs_reviewed(tmp_path, only="") == 2


def test_drift_is_reported_on_every_run_until_reviewed() -> None:
    """The property the reversal buys: the signal survives an unread console."""
    store = _store(_NOW, "old")
    for _ in range(3):
        findings, store = docs.verify((_URL,), store, fetcher=lambda _u: ("new", ""))
        assert findings[0].drifted


def test_an_unchanged_page_still_refreshes_its_checked_at() -> None:
    """Control arm: only a DRIFTED page withholds its update.

    An unchanged page must keep proving it was looked at, or the offline staleness
    check would start nagging about pages that are verified every run.
    """
    long_ago = datetime(2020, 1, 1, tzinfo=UTC)
    body = "unchanged page body"
    # The stored digest must be the REAL hash of the body, or the page reads as
    # drifted and this would silently test the branch above instead.
    before = _store(long_ago, content_hash(body))
    findings, after = docs.verify((_URL,), before, fetcher=lambda _u: (body, ""))
    assert not findings[0].drifted
    assert after[_URL]["checked_at"] != long_ago.isoformat()


def test_mark_reviewed_rolls_the_baseline_to_the_reviewed_content(tmp_path: Path) -> None:
    """The deliberate second step, after a human has actually re-read the page."""
    docs.save(tmp_path, _store(_NOW, "old"))
    findings = docs.mark_reviewed(tmp_path, (_URL,), fetcher=lambda _u: ("new", ""))
    assert findings[0].verified
    rolled = docs.load(tmp_path)[_URL]["sha256"]
    assert rolled != "old"
    # The message must NOT claim this proves what the human read — it cannot.
    assert "live now" in findings[0].detail
    assert rolled[:12] in findings[0].detail
    # And the drift is now genuinely resolved, not merely muted.
    again, _ = docs.verify((_URL,), docs.load(tmp_path), fetcher=lambda _u: ("new", ""))
    assert not again[0].drifted


def test_mark_reviewed_refuses_to_roll_a_page_it_could_not_fetch(tmp_path: Path) -> None:
    """Rolling to an unknown hash would silence the finding with nothing read."""
    docs.save(tmp_path, _store(_NOW, "old"))
    findings = docs.mark_reviewed(tmp_path, (_URL,), fetcher=lambda _u: ("", "HTTP 503"))
    assert not findings[0].verified
    assert docs.load(tmp_path)[_URL]["sha256"] == "old"


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
