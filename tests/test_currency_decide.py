"""kb_setup.currency.decide — the six-gate bar that authorizes an unattended bump.

This is the safety-critical surface: `auto_apply=True` means a version change
proceeds without a human reading it. So every gate is tested in both directions,
and the fail-closed behaviour (unreadable upstream, unparsable version) is
tested explicitly — an engine that treats "I could not check" as "go ahead" is
the failure mode that matters here.
"""

from kb_setup.currency.decide import GATES, decide
from kb_setup.currency.issues import Observation
from kb_setup.currency.sync import DRIFT, OK, SKIP, Finding, SyncStatus
from kb_setup.currency.upstream import UpstreamStatus, Version


def _sync(*, pinned="0.9.25", findings=()) -> SyncStatus:
    # The default fixture is a POSITIVELY verified step 1: gate 6 now requires
    # resolution and build-stamp to have actually passed, not merely not-failed.
    return SyncStatus(
        tool="graphify",
        pinned=pinned,
        resolved=pinned,
        findings=findings
        or (
            Finding("pin", OK, "pinned"),
            Finding("resolution", OK, "reaches the pin"),
            Finding("build-stamp", OK, "built by the pin"),
        ),
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


def test_empty_release_body_is_not_a_clean_bill_of_health() -> None:
    """A missing document cannot testify that nothing is wrong.

    This is the absence-of-evidence trap: an empty release body cannot be
    scanned, so a passing marker gate would mean "nothing was read", not
    "nothing to worry about". Found by adversarially probing decide() rather
    than by a test — the original gate happily auto-applied here.
    """
    upstream = UpstreamStatus(pypi_latest="0.9.26", github_tag="v0.9.26", notes="")
    verdict = decide(sync=_sync(), upstream=upstream, moved=())
    assert not verdict.auto_apply
    assert any(a.gate == GATES[2] for a in verdict.ambiguities)


def test_whitespace_only_release_body_also_stops() -> None:
    upstream = UpstreamStatus(pypi_latest="0.9.26", github_tag="v0.9.26", notes="   \n\t ")
    assert not decide(sync=_sync(), upstream=upstream, moved=()).auto_apply


def test_a_real_release_body_with_no_markers_still_auto_applies() -> None:
    """Control arm: the gate must not have become unconditional."""
    upstream = UpstreamStatus(pypi_latest="0.9.26", github_tag="v0.9.26", notes="Routine fixes.")
    assert decide(sync=_sync(), upstream=upstream, moved=()).auto_apply


def test_same_version_written_differently_is_not_a_bump() -> None:
    """`1.2` and `1.2.0` are the SAME version — bumping to it is a no-op.

    The raw-tuple comparison `(1, 2, 0) > (1, 2)` used to call this a patch bump,
    so the two comparison paths disagreed and an unattended no-op upgrade could
    be authorized. `is_patch_bump_from` now delegates to `__gt__`.
    """
    assert not _v("1.2.0").is_patch_bump_from(_v("1.2"))
    assert not _v("1.2").is_patch_bump_from(_v("1.2.0"))
    # Control arm: a genuine patch bump is still recognised.
    assert _v("1.2.1").is_patch_bump_from(_v("1.2"))


def test_json_null_release_body_does_not_defeat_the_empty_notes_gate() -> None:
    """GitHub sends `"body": null`, not a missing key, for a release with no notes.

    `.get("body", "")` therefore never fires its default and `str(None)` yields
    the 4-character string "None" — non-empty, marker-free, and so it walked
    straight through the empty-notes gate. The whole protection was bypassed by
    the single most likely way a release ends up without notes.
    """
    upstream = UpstreamStatus(pypi_latest="0.9.26", github_tag="v0.9.26", notes="None")
    verdict = decide(sync=_sync(), upstream=upstream, moved=())
    # "None" is still literally non-empty text, so the gate cannot catch it — the
    # fix belongs upstream in release_for_tag, asserted in test_currency_upstream.
    assert verdict.auto_apply, "guard belongs at the parse boundary, not here"


# ------------------------------------ SKIP is not consent for an unattended act ----


def _sync_all_skipped() -> SyncStatus:
    """What step 1 looks like on a host where the tool is not installed at all."""
    return SyncStatus(
        tool="graphify",
        pinned="0.9.25",
        resolved="",
        findings=(
            Finding("pin", OK, "pinned"),
            Finding("resolution", SKIP, "not on PATH here"),
            Finding("extras", OK, "declared"),
            Finding("build-stamp", SKIP, "no stamp"),
        ),
    )


def test_a_run_that_checked_almost_nothing_is_not_green() -> None:
    """Nothing-disagreed is not everything-agreed.

    On a host without the tool, four of six checks SKIP. SKIP staying non-red is
    right for the hook; counting it as consent for an UNATTENDED bump is the
    absence-of-evidence trap.
    """
    verdict = decide(sync=_sync_all_skipped(), upstream=_clean_upstream(), moved=())
    assert not verdict.auto_apply
    assert any(a.gate == GATES[5] for a in verdict.ambiguities)


def test_positively_verified_step_one_still_authorizes() -> None:
    """Control arm: the gate must not have become unconditional."""
    status = SyncStatus(
        tool="graphify",
        pinned="0.9.25",
        resolved="0.9.25",
        findings=(
            Finding("pin", OK, "pinned"),
            Finding("resolution", OK, "reaches the pin"),
            Finding("build-stamp", OK, "built by the pin"),
        ),
    )
    assert decide(sync=status, upstream=_clean_upstream(), moved=()).auto_apply
