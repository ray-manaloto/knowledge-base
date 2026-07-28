"""Tests for `kb_setup.review` — the local cross-family review receipt.

Both directions of every gate, per `probes-need-a-control-arm.md`: a receipt
check that has only ever been run against a good receipt is decoration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import review

_SHA = "9521853abcdef0123456789abcdef0123456789a"
_OTHER = "0000000abcdef0123456789abcdef0123456789b"


def _write(tmp_path: Path, **overrides: object) -> Path:
    """Write a valid receipt with ``overrides`` applied; return the repo root."""
    payload: dict[str, object] = {
        "sha": _SHA,
        "written_at": "2026-07-28T02:14:09+00:00",
        "fixed_point": "main",
        "fixed_point_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "lanes_ran": ["standards", "spec", "cold:codex", "silent-failure"],
        "lanes_skipped": [],
        "findings": 3,
        "blocking": 0,
    }
    payload.update(overrides)
    path = review.receipt_path(tmp_path, _SHA)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    # Every lane claimed as RUN needs its report on disk, so the default fixture
    # is a receipt whose evidence actually exists.
    ran = payload.get("lanes_ran")
    for entry in ran if isinstance(ran, list) else []:
        _write_report(tmp_path, str(entry).partition(":")[0])
    return tmp_path


def _write_report(tmp_path: Path, lane: str, body: str = "NO FINDINGS") -> Path:
    """Write ``lane``'s report for the fixture SHA."""
    rp = review.report_path(tmp_path, _SHA, lane)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(body, encoding="utf-8")
    return rp


def test_valid_receipt_passes(tmp_path: Path) -> None:
    """The PASS arm: a well-formed receipt for this SHA is accepted."""
    ok, summary = review.receipt_state(_write(tmp_path), _SHA)
    assert ok
    assert "cold:codex" in summary


def test_write_receipt_roundtrips(tmp_path: Path) -> None:
    """`write_receipt` produces something `receipt_state` accepts."""
    for lane in ("standards", "spec"):
        _write_report(tmp_path, lane)
    review.write_receipt(
        tmp_path,
        review.Receipt(
            sha=_SHA,
            fixed_point="main",
            fixed_point_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            lanes_ran=("standards", "spec"),
            lanes_skipped=(
                "cold:not-applicable-docs-only",
                "silent-failure:not-applicable-docs-only",
            ),
            findings=0,
            blocking=0,
        ),
    )
    ok, summary = review.receipt_state(tmp_path, _SHA)
    assert ok
    assert "not-applicable-docs-only" in summary


def test_missing_receipt_fails(tmp_path: Path) -> None:
    """No receipt at all is the common case and must refuse."""
    ok, summary = review.receipt_state(tmp_path, _SHA)
    assert not ok
    assert "no review receipt" in summary


def test_amended_commit_invalidates_receipt(tmp_path: Path) -> None:
    """A receipt for one SHA must not authorise a different HEAD.

    This is the realistic break: amend or rebase after reviewing, and the
    reviewed bytes no longer exist.
    """
    ok, _ = review.receipt_state(_write(tmp_path), _OTHER)
    assert not ok


def test_copied_receipt_fails(tmp_path: Path) -> None:
    """A receipt filed under this SHA that RECORDS another is a copied file."""
    ok, summary = review.receipt_state(_write(tmp_path, sha=_OTHER), _SHA)
    assert not ok
    assert "different SHA" in summary


def test_unparsable_receipt_fails_closed(tmp_path: Path) -> None:
    """Garbage must never read as approval — a parse error is not a "no"."""
    path = review.receipt_path(tmp_path, _SHA)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json at all", encoding="utf-8")
    ok, summary = review.receipt_state(tmp_path, _SHA)
    assert not ok
    assert "unreadable" in summary


def test_non_object_receipt_fails_closed(tmp_path: Path) -> None:
    """Valid JSON that is not an object is still not a receipt."""
    path = review.receipt_path(tmp_path, _SHA)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    ok, _ = review.receipt_state(tmp_path, _SHA)
    assert not ok


def test_blocking_findings_fail(tmp_path: Path) -> None:
    """A blocking finding stops the ship."""
    ok, summary = review.receipt_state(_write(tmp_path, blocking=2), _SHA)
    assert not ok
    assert "2 blocking" in summary


def test_missing_blocking_count_fails_closed(tmp_path: Path) -> None:
    """An absent or non-integer blocking count is ambiguity, not consent."""
    ok, _ = review.receipt_state(_write(tmp_path, blocking="none"), _SHA)
    assert not ok


def test_no_lane_ran_fails(tmp_path: Path) -> None:
    """Every lane skipped, each with a reason, is still not a review.

    Each skip is individually well-formed, so this is the case that would slip
    through a per-entry check: the defect is only visible across the whole set.
    """
    ok, summary = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=[],
            lanes_skipped=[f"{lane}:not-applicable-docs-only" for lane in review.LANES],
        ),
        _SHA,
    )
    assert not ok
    assert "no lane" in summary


@pytest.mark.parametrize("skipped", [["cold"], ["cold:"], [123]])
def test_unexplained_skip_fails(tmp_path: Path, skipped: list[object]) -> None:
    """A skip with no reason is a GAP, not a skip.

    "did not run" and "does not apply here" are different states; collapsing
    them is how a gap gets reported as coverage.
    """
    ok, summary = review.receipt_state(_write(tmp_path, lanes_skipped=skipped), _SHA)
    assert not ok
    assert "not excused" in summary


def test_no_spec_available_does_not_excuse_a_non_spec_lane(tmp_path: Path) -> None:
    """A skip reason must excuse THAT lane, not merely be a known string.

    `no-spec-available` belongs to the spec lane alone — a cold or
    silent-failure lane does not review against a spec, so "there is no spec"
    cannot explain why it did not run. Matching the reason without looking at
    the lane let `cold:no-spec-available` buy a pass for a lane that never ran:
    the third instance of one hole, after `--lanes placeholder` and
    `cold:not-yet-run`. The comment beside the constant already said "spec lane,
    and only when there genuinely is no spec"; nothing enforced it.
    """
    ok, summary = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=["standards", "spec", "silent-failure"],
            lanes_skipped=["cold:no-spec-available"],
        ),
        _SHA,
    )
    assert not ok
    assert "not excused" in summary
    assert "cold:no-spec-available" in summary


def test_no_spec_available_still_excuses_the_spec_lane(tmp_path: Path) -> None:
    """CONTROL ARM — the same reason on its OWN lane must still be accepted.

    Without this arm the test above would also pass if the reason had simply
    been deleted from the accepted set, which would be a different (and wrong)
    fix.
    """
    ok, _ = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=["standards", "cold:codex", "silent-failure"],
            lanes_skipped=["spec:no-spec-available"],
        ),
        _SHA,
    )
    assert ok


@pytest.mark.parametrize("container", [None, 0, "", "cold:not-applicable-x"])
def test_malformed_lanes_skipped_container_is_refused_not_crashed(
    tmp_path: Path, container: object
) -> None:
    """A bad CONTAINER must produce a verdict, exactly as a bad ELEMENT does.

    `"lanes_skipped": null` crashed with `TypeError: 'NoneType' object is not
    iterable` — `_check_lanes` normalised the key with `or []` while
    `_unexplained_skips` re-read it raw, so one key was read through two idioms
    and only one of them was safe. `land_main` died *after* printing
    `==> checks: ok`, which is a crash wearing a green light's clothes.

    The existing parametrize covers bad elements (`["cold"]`, `[123]`) and could
    not see this: the container was never the variable.
    """
    ok, summary = review.receipt_state(_write(tmp_path, lanes_skipped=container), _SHA)
    assert not ok
    assert "malformed lane list" in summary


@pytest.mark.parametrize(
    "reason",
    [
        "not-applicable-",  # the prefix with no why after it — an empty claim
        "no-spec-availablex",  # a typo that `startswith` accepted
        "not-applicable",  # the prefix without its trailing hyphen
    ],
)
def test_near_miss_skip_reasons_are_rejected(tmp_path: Path, reason: str) -> None:
    """A justification must be the real one, not merely start like it.

    `str.startswith` let a bare `not-applicable-` (no why) and a misspelled
    `no-spec-availablex` through. `not-applicable-` stays a PREFIX because the
    why is free text; everything else is matched exactly.
    """
    ok, summary = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=["standards", "spec", "silent-failure"],
            lanes_skipped=[f"cold:{reason}"],
        ),
        _SHA,
    )
    assert not ok
    assert "not excused" in summary


def test_a_real_not_applicable_reason_still_passes(tmp_path: Path) -> None:
    """CONTROL ARM for the near-misses — `not-applicable-<why>` must be accepted."""
    ok, _ = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=["standards", "spec", "silent-failure"],
            lanes_skipped=["cold:not-applicable-docs-only"],
        ),
        _SHA,
    )
    assert ok


def test_a_lane_cannot_be_both_run_and_skipped(tmp_path: Path) -> None:
    """Claiming both is a contradiction, and it used to satisfy the gate twice.

    `accounted` is a SET, so one lane in both lists collapsed to one entry and
    read as covered while saying two opposite things about it.
    """
    ok, summary = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=["standards", "spec", "cold:codex", "silent-failure"],
            lanes_skipped=["cold:not-applicable-docs-only"],
        ),
        _SHA,
    )
    assert not ok
    assert "BOTH run and skipped" in summary
    assert "cold" in summary


def test_empty_comparison_range_is_rejected(tmp_path: Path) -> None:
    """A receipt whose base IS its own SHA reviewed nothing.

    `--fixed-point HEAD` resolves through `git merge-base HEAD HEAD` to HEAD
    itself (verified against real git), and `fixed_point_sha` was checked only
    for non-blankness — so one flag minted a full-coverage receipt for a
    zero-line diff.
    """
    ok, summary = review.receipt_state(_write(tmp_path, fixed_point_sha=_SHA), _SHA)
    assert not ok
    assert "EMPTY comparison range" in summary


@pytest.mark.parametrize("bad", [True, 42, None, ""])
def test_non_string_fixed_point_is_rejected(tmp_path: Path, bad: object) -> None:
    """A JSON `true` must not become the string "True" and pass as a base.

    The value was coerced with `str()` BEFORE the non-blank check, so every
    non-string except None/"" sailed through. Stringifying before validating
    turns "wrong type" into "some text".
    """
    ok, _ = review.receipt_state(_write(tmp_path, fixed_point=bad), _SHA)
    assert not ok


def test_report_path_strips_the_lane_variant(tmp_path: Path) -> None:
    """`cold:codex` must resolve to `…-cold.md`, matching what the gate reads.

    Spelled out literally rather than compared against `_lane_prefix`, so this
    cannot inherit the bug it is checking — the tautological-probe lesson from
    the `_safe_lane` hyphen defect, which is the same divergence one layer down.
    """
    assert review.report_path(tmp_path, _SHA, "cold:codex").name == f"review-{_SHA}-cold.md"
    assert review.report_path(tmp_path, _SHA, "cold").name == f"review-{_SHA}-cold.md"


def test_require_base_rejects_a_partial_range(tmp_path: Path) -> None:
    """A receipt against a narrower base must not gate the whole branch.

    The LIKELY mistake, not an adversarial one: on a second review round the
    instinct is "review what changed since last time", which produces a truthful
    receipt covering one commit of twelve. `ship` passes `require_base="main"`.
    """
    ok, summary = review.receipt_state(
        _write(tmp_path, fixed_point_sha="b" * 40),
        _SHA,
        require_base="main",
    )
    assert not ok
    assert "partial range" in summary or "could not resolve" in summary


def test_require_base_fails_closed_when_the_base_cannot_resolve(tmp_path: Path) -> None:
    """An unresolvable base is "could not check", never "clean"."""
    ok, summary = review.receipt_state(_write(tmp_path), _SHA, require_base="no-such-ref-anywhere")
    assert not ok
    assert "could not resolve" in summary


def test_require_base_is_opt_in(tmp_path: Path) -> None:
    """CONTROL ARM — without `require_base` the same receipt must still pass.

    Otherwise the two tests above would also pass if the receipt were rejected
    for some unrelated reason.
    """
    ok, _ = review.receipt_state(_write(tmp_path, fixed_point_sha="b" * 40), _SHA)
    assert ok


def test_unreadable_bytes_in_a_receipt_are_refused_not_crashed(tmp_path: Path) -> None:
    """`UnicodeDecodeError` is raised by `read_text` and is NOT an `OSError`.

    `write_receipt` is a non-atomic `write_text`, so a truncated or partly-binary
    receipt is realistic — and it escaped as a traceback out of the one function
    whose contract is to return a worded refusal.
    """
    path = review.receipt_path(tmp_path, _SHA)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'{"sha": "\xff\xfe not utf-8"}')
    ok, summary = review.receipt_state(tmp_path, _SHA)
    assert not ok
    assert "unreadable" in summary


def test_negative_blocking_count_is_rejected(tmp_path: Path) -> None:
    """`-1` is malformed, not "fewer than zero blockers".

    Only `> 0` was rejected, so a hand-edited receipt with a negative count read
    as clean. The CLI cannot write one — a hand-edited receipt is exactly the
    reader this check exists for, so the reader needs its own test.
    """
    ok, summary = review.receipt_state(_write(tmp_path, blocking=-1), _SHA)
    assert not ok
    assert "negative blocking count" in summary


def test_payload_timestamp_is_stamped_once(tmp_path: Path) -> None:
    """The bytes validated must be the bytes written.

    `as_payload()` called `datetime.now()` on every invocation, so `rejection()`
    checked a payload that differed from the one `write_receipt()` then wrote.
    Nothing gates on the timestamp, so no verdict changed — but this module's
    whole claim is that the writer and the reader see one artefact.

    Asserted against an EXPLICIT stamp, not `as_payload() == as_payload()`: two
    calls in the same second produce identical `timespec="seconds"` strings, so
    the equality form stayed green under the mutation. The probe was the defect.
    """
    stamp = "2020-01-01T00:00:00+00:00"
    receipt = review.Receipt(
        sha=_SHA,
        fixed_point="main",
        fixed_point_sha="a" * 40,
        lanes_ran=("standards", "spec"),
        lanes_skipped=(
            "cold:not-applicable-docs-only",
            "silent-failure:not-applicable-docs-only",
        ),
        findings=0,
        blocking=0,
        written_at=stamp,
    )
    assert receipt.as_payload()["written_at"] == stamp
    assert receipt.as_payload() == receipt.as_payload()


def test_explained_skip_passes(tmp_path: Path) -> None:
    """The control arm for the test above: a reasoned skip is accepted."""
    ok, _ = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=["standards", "spec", "silent-failure"],
            lanes_skipped=["cold:not-applicable-docs-only"],
        ),
        _SHA,
    )
    assert ok


def test_invented_lane_name_is_rejected(tmp_path: Path) -> None:
    """`--lanes placeholder` must not satisfy the gate.

    Found by the cold cross-family lane reviewing this module's own first
    draft: the check was `lanes_ran` non-empty, so any string passed. A gate
    the caller can talk past by naming a lane that does not exist is not a
    gate — which is the one thing this module claims to be.
    """
    ok, summary = review.receipt_state(_write(tmp_path, lanes_ran=["placeholder"]), _SHA)
    assert not ok
    assert "unknown lane" in summary


def test_lane_left_unaccounted_for_is_rejected(tmp_path: Path) -> None:
    """Naming only SOME lanes is the subtler half of the same bypass."""
    ok, summary = review.receipt_state(_write(tmp_path, lanes_ran=["standards"]), _SHA)
    assert not ok
    assert "unaccounted for" in summary
    assert "silent-failure" in summary


def test_lane_variant_suffix_is_accepted(tmp_path: Path) -> None:
    """CONTROL ARM: `cold:codex` names a known lane and must still pass.

    Without this, the fix above would reject every real receipt — the cold
    lane always records which family actually ran.
    """
    ok, _ = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=["standards", "spec", "cold:claude-fallback-SAME-FAMILY", "silent-failure"],
        ),
        _SHA,
    )
    assert ok


def test_not_yet_run_is_not_a_valid_skip(tmp_path: Path) -> None:
    """`cold:not-yet-run` is a GAP wearing a reason's clothes.

    The reference docs already said a lane that could not be spawned is
    `not-yet-run` and never `not-applicable` — and the first version of the gate
    then accepted any non-empty reason, so the doc and the code disagreed with
    the code being the permissive one.
    """
    ok, summary = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=["standards", "spec", "silent-failure"],
            lanes_skipped=["cold:not-yet-run"],
        ),
        _SHA,
    )
    assert not ok
    assert "not excused" in summary


def test_lane_claimed_without_a_report_is_rejected(tmp_path: Path) -> None:
    """The widest hole: a full-coverage receipt minted with no evidence at all.

    `--lanes standards,spec,cold:codex,silent-failure --blocking 0` used to pass
    in one command without any lane having run.
    """
    root = _write(tmp_path)
    review.report_path(root, _SHA, "cold").unlink()
    ok, summary = review.receipt_state(root, _SHA)
    assert not ok
    assert "no non-empty report" in summary
    assert "cold" in summary


def test_empty_report_does_not_count_as_evidence(tmp_path: Path) -> None:
    """A whitespace-only report file is a placeholder, not a review."""
    root = _write(tmp_path)
    review.report_path(root, _SHA, "spec").write_text("   \n", encoding="utf-8")
    ok, summary = review.receipt_state(root, _SHA)
    assert not ok
    assert "spec" in summary


def test_no_findings_report_is_valid_evidence(tmp_path: Path) -> None:
    """CONTROL ARM: a lane that ran and found nothing must still pass.

    Without this arm the evidence check would quietly require every lane to
    produce findings, which would reward inventing them.
    """
    root = _write(tmp_path)
    review.report_path(root, _SHA, "standards").write_text("NO FINDINGS", encoding="utf-8")
    ok, _ = review.receipt_state(root, _SHA)
    assert ok


def test_missing_fixed_point_is_rejected(tmp_path: Path) -> None:
    """A receipt with no base says a review happened, but not of what."""
    ok, summary = review.receipt_state(_write(tmp_path, fixed_point="  "), _SHA)
    assert not ok
    assert "fixed point" in summary


def test_empty_sha_fails(tmp_path: Path) -> None:
    """An unreadable HEAD must not pass; `head_sha` returns "" when git fails."""
    ok, summary = review.receipt_state(tmp_path, "")
    assert not ok
    assert "HEAD" in summary
