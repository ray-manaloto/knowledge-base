"""kb_setup.currency.decide — the six-gate bar that authorizes an unattended bump.

This is the safety-critical surface: `auto_apply=True` means a version change
proceeds without a human reading it. So every gate is tested in both directions,
and the fail-closed behaviour (unreadable upstream, unparsable version) is
tested explicitly — an engine that treats "I could not check" as "go ahead" is
the failure mode that matters here.
"""

from kb_setup.currency.decide import GATES, decide
from kb_setup.currency.issues import Observation
from kb_setup.currency.sync import BLIND, DRIFT, OK, SKIP, Finding, SyncStatus
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
    return UpstreamStatus(latest=latest, github_tag=f"v{latest}", notes=notes)


# ------------------------------------------------------- the happy path ----


def test_all_six_gates_passing_authorizes_auto_apply() -> None:
    verdict = decide(sync=_sync(), upstream=_clean_upstream(), moved=())
    assert verdict.auto_apply
    assert verdict.ambiguities == ()
    assert set(verdict.gates_passed) == set(GATES)


def test_no_upgrade_available_is_not_an_auto_apply() -> None:
    verdict = decide(sync=_sync(), upstream=UpstreamStatus(latest="0.9.25"), moved=())
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
    upstream = UpstreamStatus(latest="0.9.26", github_tag="", error="404")
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
    verdict = decide(sync=status, upstream=UpstreamStatus(latest="0.9.25"), moved=())
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
    upstream = UpstreamStatus(latest="0.9.26", github_tag="v0.9.26", notes="")
    verdict = decide(sync=_sync(), upstream=upstream, moved=())
    assert not verdict.auto_apply
    assert any(a.gate == GATES[2] for a in verdict.ambiguities)


def test_whitespace_only_release_body_also_stops() -> None:
    upstream = UpstreamStatus(latest="0.9.26", github_tag="v0.9.26", notes="   \n\t ")
    assert not decide(sync=_sync(), upstream=upstream, moved=()).auto_apply


def test_a_real_release_body_with_no_markers_still_auto_applies() -> None:
    """Control arm: the gate must not have become unconditional."""
    upstream = UpstreamStatus(latest="0.9.26", github_tag="v0.9.26", notes="Routine fixes.")
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
    upstream = UpstreamStatus(latest="0.9.26", github_tag="v0.9.26", notes="None")
    verdict = decide(sync=_sync(), upstream=upstream, moved=())
    # "None" is still literally non-empty text, so the gate cannot catch it — the
    # fix belongs upstream in release_for_tag, asserted in test_currency_upstream.
    assert verdict.auto_apply, "guard belongs at the parse boundary, not here"


# ------------------------------------ SKIP is not consent for an unattended act ----


def _sync_blind_probe() -> SyncStatus:
    """Step 1 on a host that could not locate the install to probe its extras.

    Everything readable agreed; the one check that would have disagreed never
    ran. This is the realistic shape of the hole: the old `_REQUIRED_OK` list
    named only `resolution` and `build-stamp`, so an unreadable `extra-probes`
    sailed through and the bump auto-applied.
    """
    return SyncStatus(
        tool="graphify",
        pinned="0.9.25",
        resolved="0.9.25",
        findings=(
            Finding("pin", OK, "pinned"),
            Finding("resolution", OK, "reaches the pin"),
            Finding("extras", OK, "declared"),
            Finding("extra-probes", BLIND, "install path not resolvable here"),
            Finding("build-stamp", OK, "built by the pin"),
        ),
    )


def test_a_run_that_checked_almost_nothing_is_not_green() -> None:
    """Nothing-disagreed is not everything-agreed.

    A BLIND check is a check that never ran; counting it as consent for an
    UNATTENDED bump is the absence-of-evidence trap.
    """
    verdict = decide(sync=_sync_blind_probe(), upstream=_clean_upstream(), moved=())
    assert not verdict.auto_apply
    assert any(a.gate == GATES[5] for a in verdict.ambiguities)


def test_a_skip_with_nothing_configured_still_authorizes() -> None:
    """Control arm for the SKIP/BLIND split, in the direction that costs the most.

    Widening the gate to "any status that is not OK" would be the easy fix and
    the wrong one: `manifest` and `build-stamp` SKIP legitimately in a repo that
    declares neither, so it would block every such repo forever — a false stop
    replacing a false pass. Only BLIND may block.
    """
    status = SyncStatus(
        tool="graphify",
        pinned="0.9.25",
        resolved="0.9.25",
        findings=(
            Finding("pin", OK, "pinned"),
            Finding("resolution", OK, "reaches the pin"),
            Finding("extras", SKIP, "no extras declared for this tool"),
            Finding("extra-probes", SKIP, "no extra_probes declared for this tool"),
            Finding("manifest", SKIP, "this repo pins no source manifest for the tool"),
            Finding("build-stamp", OK, "built by the pin"),
        ),
    )
    assert decide(sync=status, upstream=_clean_upstream(), moved=()).auto_apply


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


# --------------------- gate 5 must distinguish "did not move" from "unread" ----


def _errored_observations() -> tuple[Observation, ...]:
    return tuple(
        Observation(key=f"issue:{n}", error="gh: HTTP 403 rate limit")
        for n in (2101, 2086, 1653, 1824)
    )


def test_unreadable_tracked_issues_do_not_pass_gate_five() -> None:
    """The gate whose entire job is to stop a bump was passing on unread issues.

    `differs_from` rightly refuses to call an errored observation movement — a
    rate limit must not manufacture movement on every item — so `moved` is empty
    for BOTH "provably did not move" and "could not be read". decide() saw only
    `moved`, so it could not tell them apart. An expired gh token, a rate limit,
    or one transferred issue was enough to auto-apply with all four tracked
    issues unread.
    """
    observations = _errored_observations()
    moved = tuple(o for o in observations if o.differs_from(None))
    assert moved == ()  # the input that made this invisible

    verdict = decide(
        sync=_sync(), upstream=_clean_upstream(), moved=moved, observations=observations
    )
    assert not verdict.auto_apply
    assert any(a.gate == GATES[4] for a in verdict.ambiguities)
    assert GATES[4] not in verdict.gates_passed


def test_readable_and_unmoved_issues_still_pass_gate_five() -> None:
    """Control arm: successfully-read, genuinely-unmoved issues must still pass."""
    observations = (Observation(key="issue:2101", state="open", updated_at="t1"),)
    verdict = decide(sync=_sync(), upstream=_clean_upstream(), moved=(), observations=observations)
    assert verdict.auto_apply
    assert GATES[4] in verdict.gates_passed


def test_unreachable_upstream_never_prints_the_word_current() -> None:
    """The landing row is committed; "current" would assert a fact never checked."""
    verdict = decide(
        sync=_sync(), upstream=UpstreamStatus(reachable=False, error="pypi down"), moved=()
    )
    assert "current" not in verdict.summary()
    assert "UNKNOWN" in verdict.summary()
    # Control arm: a genuinely-current run still says so.
    assert (
        "current"
        in decide(sync=_sync(), upstream=UpstreamStatus(latest="0.9.25"), moved=()).summary()
    )


# ---------------------------------------------- gate 5, the local half ----


_LOCAL = Observation(key="local:schema-gap", state="local", title="re-probe on each bump")


def test_a_local_watch_item_stops_a_pending_bump() -> None:
    """A `kind = "local"` item can never MOVE, so movement could never surface it.

    It observes as itself every run — same key, same `state="local"`, no
    timestamp — so `differs_from` is False forever and gate 5 was structurally
    unable to block on one, while `currency.toml`'s founding local item said in
    as many words "Re-probe on each bump". The claim and the machinery
    disagreed; this pins the resolution.
    """
    verdict = decide(sync=_sync(), upstream=_clean_upstream(), moved=(), observations=(_LOCAL,))
    assert not verdict.auto_apply
    assert any(a.gate == GATES[4] for a in verdict.ambiguities)


def test_a_local_watch_item_does_not_interrupt_a_run_with_no_bump() -> None:
    """Control arm: an open local finding is not a reason to interrupt every run.

    Without this the gate would fire on every SessionStart forever, which is how
    a real signal becomes noise nobody reads.
    """
    verdict = decide(
        sync=_sync(),
        upstream=UpstreamStatus(latest="0.9.25"),
        moved=(),
        observations=(_LOCAL,),
    )
    assert not verdict.has_upgrade
    assert verdict.ambiguities == ()


def test_an_issue_observation_alone_does_not_trip_the_local_gate() -> None:
    """Control arm: only `state == "local"` counts, not any observation."""
    issue = Observation(key="issue:2101", state="open", updated_at="2026-07-22T00:00:00Z")
    verdict = decide(sync=_sync(), upstream=_clean_upstream(), moved=(), observations=(issue,))
    assert verdict.auto_apply


# ------------------------------------------ presence-only (untracked) ----


def test_an_untracked_tool_produces_no_upstream_ambiguity() -> None:
    """ffmpeg: source='none'. An absent upstream is a non-event, not a question.

    Adversarial: the whole hazard is that "I could not read upstream" gets read
    as consent OR as a blocking ambiguity. For a tool with no upstream to read,
    it must be NEITHER — the run is simply clean.
    """
    untracked = UpstreamStatus(source="none")
    verdict = decide(sync=_sync(), upstream=untracked, moved=())
    assert not verdict.auto_apply  # nothing to apply
    assert not verdict.tracked
    assert verdict.ambiguities == ()  # and nothing to ask
    assert not verdict.needs_interview


def test_an_untracked_tool_still_surfaces_a_real_sync_drift() -> None:
    """Control arm: 'no upstream' must not suppress a genuine step-1 finding."""
    status = _sync(findings=(Finding("resolution", DRIFT, "not on PATH"),))
    verdict = decide(sync=status, upstream=UpstreamStatus(source="none"), moved=())
    assert verdict.needs_interview
    assert any(a.gate == GATES[5] for a in verdict.ambiguities)


def test_untracked_summary_does_not_claim_an_unknown_latest() -> None:
    """'not version-tracked' is the honest phrasing; 'UNKNOWN' implies a failed look."""
    summary = decide(sync=_sync(), upstream=UpstreamStatus(source="none"), moved=()).summary()
    assert "UNKNOWN" not in summary
    assert "not version-tracked" in summary


def test_a_tracked_unreachable_upstream_is_still_an_ambiguity() -> None:
    """Control arm: the untracked exemption must not swallow a real outage.

    A tool that DOES declare an upstream (tracked) which could not be read must
    still fail closed — otherwise the exemption becomes a hole for every
    rate-limited run.
    """
    unreachable = UpstreamStatus(source="pypi", reachable=False, error="pypi down")
    verdict = decide(sync=_sync(), upstream=unreachable, moved=())
    assert not verdict.auto_apply
    assert verdict.needs_interview


# --------------------------------------------- feature review (step 3) ----


def test_a_clean_auto_apply_still_surfaces_features_without_blocking() -> None:
    """The whole point of gap 4: features reach the interview even on auto-apply.

    Adversarial: a feature note must NOT convert an authorized bump into a
    blocked one — `needs_interview` stays False — while `feature_review` still
    carries the capability for a human to skim.
    """
    upstream = UpstreamStatus(
        latest="0.9.26",
        github_tag="v0.9.26",
        notes="- feat: add a `--backend openai` flag\n- fix: a crash",
    )
    verdict = decide(sync=_sync(), upstream=upstream, moved=())
    assert verdict.auto_apply
    assert not verdict.needs_interview
    assert any("backend openai" in f for f in verdict.feature_review)


def test_a_routine_bump_carries_no_feature_review() -> None:
    """Control arm: no feature-shaped note ⇒ an empty review, not noise."""
    verdict = decide(sync=_sync(), upstream=_clean_upstream(notes="- fix: a typo"), moved=())
    assert verdict.auto_apply
    assert verdict.feature_review == ()
