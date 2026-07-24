"""kb_setup.currency.decide — the six-gate bar that authorizes an unattended bump.

This is the safety-critical surface: `auto_apply=True` means a version change
proceeds without a human reading it. So every gate is tested in both directions,
and the fail-closed behaviour (unreadable upstream, unparsable version) is
tested explicitly — an engine that treats "I could not check" as "go ahead" is
the failure mode that matters here.
"""

from kb_setup.currency.decide import GATES, decide
from kb_setup.currency.issues import Observation
from kb_setup.currency.sync import DRIFT, OK, Finding, SyncStatus
from kb_setup.currency.upstream import UpstreamStatus, Version


def _sync(*, pinned="0.9.25", findings=()) -> SyncStatus:
    return SyncStatus(
        tool="graphify",
        pinned=pinned,
        resolved=pinned,
        findings=findings or (Finding("pin", OK, "pinned"),),
    )


def _clean_upstream(latest="0.9.26", notes="Routine fixes.") -> UpstreamStatus:
    return UpstreamStatus(pypi_latest=latest, github_tag=f"v{latest}", notes=notes)


# ------------------------------------------------------- the happy path ----


def test_all_six_gates_passing_authorizes_auto_apply() -> None:
    verdict = decide(sync=_sync(), upstream=_clean_upstream(), moved=())
    assert verdict.auto_apply
    assert verdict.ambiguities == ()
    assert set(verdict.gates_passed) == set(GATES)


def test_no_upgrade_available_is_not_an_auto_apply() -> None:
    verdict = decide(sync=_sync(), upstream=UpstreamStatus(pypi_latest="0.9.25"), moved=())
    assert not verdict.has_upgrade
    assert not verdict.auto_apply


# ------------------------------------------------------------ each gate ----


def test_minor_bump_stops_for_review() -> None:
    """Pre-1.0 projects use MINOR as the breaking channel, so 0.9.x -> 0.10.0 stops."""
    verdict = decide(sync=_sync(), upstream=_clean_upstream("0.10.0"), moved=())
    assert not verdict.auto_apply
    assert any(a.gate == GATES[0] for a in verdict.ambiguities)


def test_major_bump_stops_for_review() -> None:
    verdict = decide(sync=_sync(), upstream=_clean_upstream("1.0.0"), moved=())
    assert not verdict.auto_apply


def test_pypi_version_with_no_github_release_stops() -> None:
    """The live v1.0.0-tagged-but-not-on-PyPI trap, in its mirror form."""
    upstream = UpstreamStatus(pypi_latest="0.9.26", github_tag="", error="404")
    verdict = decide(sync=_sync(), upstream=upstream, moved=())
    assert not verdict.auto_apply
    assert any(a.gate == GATES[1] for a in verdict.ambiguities)


def test_breaking_marker_in_release_notes_stops() -> None:
    upstream = _clean_upstream(notes="Fixes.\n\n**BREAKING CHANGE**: graph schema v2.")
    verdict = decide(sync=_sync(), upstream=upstream, moved=())
    assert not verdict.auto_apply
    assert any(a.gate == GATES[2] for a in verdict.ambiguities)


def test_deprecation_marker_also_stops() -> None:
    upstream = _clean_upstream(notes="The `--force` flag is deprecated.")
    assert not decide(sync=_sync(), upstream=upstream, moved=()).auto_apply


def test_extras_drift_stops_the_bump() -> None:
    status = _sync(findings=(Finding("extras", DRIFT, "pin declares no extras"),))
    verdict = decide(sync=status, upstream=_clean_upstream(), moved=())
    assert not verdict.auto_apply
    assert any(a.gate == GATES[3] for a in verdict.ambiguities)


def test_moved_tracked_issue_stops_the_bump() -> None:
    moved = (Observation(key="issue:#2101", state="closed", updated_at="now"),)
    verdict = decide(sync=_sync(), upstream=_clean_upstream(), moved=moved)
    assert not verdict.auto_apply
    assert any(a.gate == GATES[4] for a in verdict.ambiguities)


def test_existing_drift_stops_the_bump() -> None:
    """Bumping on top of an unknown state makes the result unattributable."""
    status = _sync(findings=(Finding("resolution", DRIFT, "PATH reaches 0.9.23"),))
    verdict = decide(sync=status, upstream=_clean_upstream(), moved=())
    assert not verdict.auto_apply
    assert any(a.gate == GATES[5] for a in verdict.ambiguities)


# ---------------------------------------------------------- fail closed ----


def test_unreachable_upstream_never_authorizes_anything() -> None:
    upstream = UpstreamStatus(reachable=False, error="pypi lookup failed")
    verdict = decide(sync=_sync(), upstream=upstream, moved=())
    assert not verdict.auto_apply
    assert verdict.needs_interview


def test_unparsable_version_is_ambiguity_not_consent() -> None:
    verdict = decide(sync=_sync(), upstream=_clean_upstream("2026.07.nightly"), moved=())
    assert not verdict.auto_apply


def test_findings_are_reported_even_with_no_upgrade_pending() -> None:
    """Drift is worth surfacing whether or not a bump is waiting."""
    status = _sync(findings=(Finding("build-stamp", DRIFT, "rebuild pending"),))
    verdict = decide(sync=status, upstream=UpstreamStatus(pypi_latest="0.9.25"), moved=())
    assert verdict.needs_interview


# ------------------------------------------------------ version parsing ----


def _v(raw: str) -> Version:
    parsed = Version.parse(raw)
    assert parsed is not None, f"{raw!r} should parse"
    return parsed


def test_patch_bump_detection_both_directions() -> None:
    base = _v("0.9.25")
    assert _v("0.9.26").is_patch_bump_from(base)
    assert not _v("0.10.0").is_patch_bump_from(base)
    assert not _v("1.0.0").is_patch_bump_from(base)
    # A downgrade is not a bump.
    assert not _v("0.9.24").is_patch_bump_from(base)


def test_version_parse_rejects_non_numeric() -> None:
    assert Version.parse("nightly") is None
    assert Version.parse("") is None
    # Control arm: the same parser must accept the real thing.
    assert _v("v0.9.25").parts == (0, 9, 25)
