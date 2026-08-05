"""Tests for `kb_setup.review` — the local cross-family review receipt.

Both directions of every gate, per `probes-need-a-control-arm.md`: a receipt
check that has only ever been run against a good receipt is decoration.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from kb_setup import review

_SHA = "9521853abcdef0123456789abcdef0123456789a"
_OTHER = "0000000abcdef0123456789abcdef0123456789b"

#: A report body that DECLARES which commit it is about (#56). The default for
#: every PASS-arm fixture here, because that is what a real lane report now has
#: to carry — a fixture that omits it would be testing a shape the gate rejects.
_BOUND_BODY = f"NO FINDINGS — reviewed {_SHA}"


#: Sentinel meaning "DELETE this key", not "set it to something falsy".
#:
#: `_write` could only ever `update()`, so every test named "missing <field>"
#: actually passed a REPLACEMENT — `blocking="none"`, `fixed_point="  "`. Those
#: are worth testing and they are not the same state: a hand-edited or truncated
#: receipt can simply lack the key, and `data.get(k)` then returns None down a
#: path no test reached. Genuine absence was untested on a validator whose entire
#: contract is failing closed on it. (#59)
_ABSENT = object()


def _write(tmp_path: Path, **overrides: object) -> Path:
    """Write a valid receipt with ``overrides`` applied; return the repo root.

    An override of :data:`_ABSENT` DELETES the key rather than setting it.
    """
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
    for key, value in overrides.items():
        if value is _ABSENT:
            del payload[key]
    path = review.receipt_path(tmp_path, _SHA)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    # Every lane claimed as RUN needs its report on disk, so the default fixture
    # is a receipt whose evidence actually exists.
    ran = payload.get("lanes_ran")
    for entry in ran if isinstance(ran, list) else []:
        _write_report(tmp_path, str(entry).partition(":")[0])
    return tmp_path


def _write_report(tmp_path: Path, lane: str, body: str = _BOUND_BODY) -> Path:
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
    """A NON-INTEGER blocking count is ambiguity, not consent."""
    ok, _ = review.receipt_state(_write(tmp_path, blocking="none"), _SHA)
    assert not ok


@pytest.mark.parametrize("field", ["blocking", "fixed_point", "fixed_point_sha", "sha"])
def test_a_genuinely_absent_field_fails_closed(tmp_path: Path, field: str) -> None:
    """A key that is DELETED, not merely falsy, must still refuse.

    Every test named "missing <field>" replaced the value instead of removing
    the key, so `data.get(k)` returning None was never exercised on a validator
    whose whole contract is failing closed on unreadable input. The two states
    are genuinely different and both reachable: `write_receipt` is a non-atomic
    `write_text`, and a hand-edited receipt is exactly the reader
    `_check_blocking`'s negative-count guard already exists for. (#59)

    Parametrized across all four gating fields rather than the one that
    prompted it — the defect is the fixture's inability to express absence, so
    fixing it for one field and not the rest would leave the same gap.
    """
    ok, summary = review.receipt_state(_write(tmp_path, **{field: _ABSENT}), _SHA)
    assert not ok
    assert summary


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


def test_require_base_rejects_a_partial_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A receipt against a narrower base must not gate the whole branch.

    The LIKELY mistake, not an adversarial one: on a second review round the
    instinct is "review what changed since last time", which produces a truthful
    receipt covering one commit of twelve.

    `base_sha` is STUBBED, and that is the whole point of this version. Left to a
    bare `tmp_path` — which is not a git repo — it returned "", so
    `_base_coverage_gap` short-circuited on "could not resolve" and the assertion
    survived on an `or` disjunct: the test exercised the identical path as its
    sibling below and **could not fail**. Mutation-proven by the silent-failure
    lane: deleting `if got != want:` left it green at 102 passed, rc=0, while
    deleting the empty-range check on the same harness went red — so the harness
    discriminates and only this test did not. The `3c38ceb` commit message's
    "8/8 proved in the FAIL direction" was false for exactly this gate.
    """
    monkeypatch.setattr(review, "base_sha", lambda *_a, **_kw: "c" * 40)
    ok, summary = review.receipt_state(
        _write(tmp_path, fixed_point_sha="b" * 40),
        _SHA,
        require_base="main",
    )
    assert not ok
    assert "partial range" in summary
    assert "could not resolve" not in summary, "must reach the comparison, not short-circuit"


def test_require_base_accepts_a_matching_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM — the same path with a base that DOES match must pass."""
    monkeypatch.setattr(review, "base_sha", lambda *_a, **_kw: "b" * 40)
    ok, _ = review.receipt_state(
        _write(tmp_path, fixed_point_sha="b" * 40), _SHA, require_base="main"
    )
    assert ok


def test_require_base_resolves_against_the_validated_sha_not_live_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The merge-base must be taken from the commit being validated.

    This is what lets `land` use the check at all: it validates the PR head oid,
    which is usually not local HEAD, so a HEAD-relative merge-base would refuse
    every merge. Adding `require_base` to `land` WITHOUT this would have shipped
    a gate that always fires — the naive one-line version of the fix.
    """
    seen: dict[str, object] = {}

    def fake_base_sha(_root: Path, fixed_point: str, *, head: str = "HEAD") -> str:
        seen["fixed_point"] = fixed_point
        seen["head"] = head
        return "b" * 40

    monkeypatch.setattr(review, "base_sha", fake_base_sha)
    review.receipt_state(_write(tmp_path, fixed_point_sha="b" * 40), _SHA, require_base="main")
    assert seen["head"] == _SHA, "resolved against live HEAD instead of the validated commit"
    assert seen["fixed_point"] == "main"


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


def test_a_report_that_never_names_the_commit_is_refused(tmp_path: Path) -> None:
    """A filename is not a binding: the report must say what it read (#56).

    The receipt is minted against fresh HEAD and there is deliberately no
    `--sha`, so the only thing tying "the commit the lanes reviewed" to "the
    commit the receipt is for" was the report's FILENAME — which the
    orchestrator chooses, not the lane. It records where a file was put, not
    what was read.

    Not hypothetical: of the two real lane reports on disk when this landed, one
    named its SHA and one did not.
    """
    root = _write(tmp_path)
    _write_report(tmp_path, "cold", "NO FINDINGS")  # plausible, and says nothing
    ok, summary = review.receipt_state(root, _SHA)
    assert not ok
    assert "cold" in summary
    assert "never names" in summary


def test_the_abbreviated_sha_binds_too(tmp_path: Path) -> None:
    """CONTROL ARM: the 12-char form this module prints everywhere must count.

    Every message here renders `sha[:12]`, so that is the form a lane naturally
    quotes back. Accepting only the full 40 would refuse honest reports and push
    authors toward pasting a SHA they never looked at.
    """
    root = _write(tmp_path)
    _write_report(tmp_path, "cold", f"Reviewed {_SHA[:12]} — NO FINDINGS")
    ok, _ = review.receipt_state(root, _SHA)
    assert ok


def test_a_seven_char_prefix_does_not_bind(tmp_path: Path) -> None:
    """CONTROL ARM 2: git's short form is too short to be evidence.

    A 7-hex run turns up in ordinary prose — and in other SHAs — often enough to
    match by accident, so accepting it would let the check pass without having
    verified anything. Refusing it is what makes the passing case mean something.
    """
    root = _write(tmp_path)
    _write_report(tmp_path, "cold", f"Reviewed {_SHA[:7]} — NO FINDINGS")
    ok, summary = review.receipt_state(root, _SHA)
    assert not ok
    assert "never names" in summary


def test_a_report_naming_another_commit_is_refused(tmp_path: Path) -> None:
    """The case the whole check exists for: evidence about some other commit.

    This is the shape a copied report has — `lanes.md` forbids copying the
    round-2 report to a new name, and until now nothing enforced it.
    """
    root = _write(tmp_path)
    _write_report(tmp_path, "cold", f"NO FINDINGS — reviewed {_OTHER}")
    ok, summary = review.receipt_state(root, _SHA)
    assert not ok
    assert "never names" in summary


def test_an_honest_fix_round_report_still_passes(tmp_path: Path) -> None:
    """The documented fix-round path must stay open (why #56 was not filed's fix).

    `SKILL.md` step 4 prescribes writing a SHORT report at the fixed SHA that
    states plainly that no lane re-ran and names the gates as the verification.
    Capturing HEAD at lane dispatch (the issue's proposal) would have made that
    impossible, since committing the fix is what moves HEAD. Asking the report to
    name its commit closes the same gap and leaves this path open — and now makes
    it VISIBLE rather than conventional.
    """
    root = _write(tmp_path)
    _write_report(
        tmp_path,
        "cold",
        f"Round 2 reviewed {_OTHER}; see review-{_OTHER}-cold.md for the findings.\n"
        f"No lane re-ran against {_SHA}. Verification for the fix is the local gates: "
        f"lint rc=0, pytest rc=0.\n",
    )
    ok, _ = review.receipt_state(root, _SHA)
    assert ok


def test_an_undecodable_report_does_not_count_as_evidence(tmp_path: Path) -> None:
    """Unreadable evidence is not evidence — the same answer `_load_receipt` gives.

    `_report_gaps` (then named `_missing_reports`) read each report with
    `errors="replace"`, so a truncated
    or partly-binary file decoded into U+FFFD replacement characters, survived
    `.strip()`, and counted as proof that a lane ran. Three functions away,
    `_load_receipt` refuses undecodable receipt bytes outright — one module
    holding two answers to "what is readable", with the permissive one guarding
    the *evidence* and the strict one guarding the *claim*. (#58)

    The bytes below are a lone UTF-8 continuation byte: valid on disk, and
    `bytes.decode("utf-8")` raises on them. Written with `write_bytes` because
    there is no way to produce this through `write_text`.
    """
    root = _write(tmp_path)
    review.report_path(root, _SHA, "cold").write_bytes(b"\xff\xfe findings \x80\x81")
    ok, summary = review.receipt_state(root, _SHA)
    assert not ok
    assert "cold" in summary


def test_no_findings_report_is_valid_evidence(tmp_path: Path) -> None:
    """CONTROL ARM: a lane that ran and found nothing must still pass.

    Without this arm the evidence check would quietly require every lane to
    produce findings, which would reward inventing them. It is also the arm that
    proves the strict decoding above rejects UNDECODABLE bytes rather than
    merely rejecting anything it was handed.
    """
    root = _write(tmp_path)
    review.report_path(root, _SHA, "standards").write_text(_BOUND_BODY, encoding="utf-8")
    ok, _ = review.receipt_state(root, _SHA)
    assert ok


def test_a_non_ascii_report_is_still_valid_evidence(tmp_path: Path) -> None:
    """CONTROL ARM 2: strict decoding must not reject an ordinary UTF-8 report.

    A lane quoting a filename with an accent, an em-dash, or a CJK identifier
    writes perfectly valid UTF-8. Without this arm, "reject undecodable" and
    "reject non-ASCII" would be indistinguishable, and the fix for #58 would
    silently start refusing honest reports.
    """
    root = _write(tmp_path)
    review.report_path(root, _SHA, "cold").write_text(
        f"NO FINDINGS — reviewed {_SHA} — checked `café/日本語.py`", encoding="utf-8"
    )
    ok, _ = review.receipt_state(root, _SHA)
    assert ok


def test_blank_fixed_point_is_rejected(tmp_path: Path) -> None:
    """A receipt with a BLANK base says a review happened, but not of what.

    Renamed from `test_missing_fixed_point_is_rejected`: it passes `"  "`, which
    is present-but-blank, not missing. Genuine absence is covered by
    `test_a_genuinely_absent_field_fails_closed`, and naming this one "missing"
    is what disguised the gap for four rounds. (#59)
    """
    ok, summary = review.receipt_state(_write(tmp_path, fixed_point="  "), _SHA)
    assert not ok
    assert "fixed point" in summary


def test_empty_sha_fails(tmp_path: Path) -> None:
    """An unreadable HEAD must not pass; `head_sha` returns "" when git fails."""
    ok, summary = review.receipt_state(tmp_path, "")
    assert not ok
    assert "HEAD" in summary


# --- #66: the exempt-delta fallback -----------------------------------------
#
# A REAL git repo, not a monkeypatched `base_sha`. The whole mechanism is
# `git rev-list` and `git diff` behaviour — rename detection, the ancestry
# bound, an identical tree — and a stubbed git could only ever confirm the
# stub. The other tests in this file stub because they are about the receipt's
# JSON; these are about git, so they use git.


def test_exempt_delta_lets_an_ancestor_receipt_cover_head(
    tmp_path: Path, commit_file, receipt_for
) -> None:
    """#66's PASS arm: P7's own output committed after the review still ships.

    The realistic sequence — review, then `kb-remember` and `kb-goal-outcome`,
    then commit what they wrote. Before this, that commit was unshippable and
    three rounds running left the files uncommitted instead.
    """
    root = tmp_path
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    commit_file("graphify-out/memory/query_1.md", "# a lesson\n")
    head = commit_file("docs/goals/README.md", "| pair | achieved |\n")

    ok, summary = review.receipt_state(root, head, require_base="main")
    assert ok, summary
    # The fallback must ANNOUNCE itself — a gate that silently relaxes is worse
    # than one that refuses, because nobody can tell it happened.
    assert reviewed[:12] in summary
    assert "graphify-out/memory/query_1.md" in summary


def test_one_reviewed_path_in_the_delta_refuses(tmp_path: Path, commit_file, receipt_for) -> None:
    """FAIL arm: exempt files alongside code do not launder the code."""
    root = tmp_path
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    commit_file("graphify-out/memory/query_1.md", "# a lesson\n")
    head = commit_file("python/src/kb_setup/other.py", "def g(): ...\n")

    ok, summary = review.receipt_state(root, head, require_base="main")
    assert not ok
    assert "python/src/kb_setup/other.py" in summary
    # And it must not be reported as "you never reviewed" — the diagnosis is
    # which file moved, not the absence of a review.
    assert reviewed[:12] in summary


def test_a_rename_out_of_a_reviewed_path_refuses(
    tmp_path: Path, git, commit_file, receipt_for
) -> None:
    """`--no-renames` earns its place: moving code INTO an exempt dir is a delete.

    With rename detection on, `git diff --name-only` reports only the exempt
    destination, so the delta reads as exempt while a reviewed file left the
    tree. Off, the source path shows as a delete and fails the check.
    """
    root = tmp_path
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    (root / "graphify-out" / "memory").mkdir(parents=True, exist_ok=True)
    git("mv", "python/src/kb_setup/thing.py", "graphify-out/memory/thing.py")
    git("commit", "-q", "-m", "move")
    head = git("rev-parse", "HEAD")

    ok, summary = review.receipt_state(root, head, require_base="main")
    assert not ok
    assert "python/src/kb_setup/thing.py" in summary


def test_the_walk_does_not_reach_a_receipt_on_main(
    tmp_path: Path, git, commit_file, receipt_for
) -> None:
    """A receipt for a commit already on `main` reviewed a DIFFERENT branch.

    Bounding the ancestry walk to `main..sha` is what stops an old merged
    review vouching for new work whose delta happens to be exempt.
    """
    root = tmp_path
    git("checkout", "-q", "main")
    on_main = commit_file("docs/notes.md", "# notes\n")
    receipt_for(on_main)
    git("checkout", "-q", "work")
    git("merge", "-q", "main")
    head = commit_file("graphify-out/memory/query_1.md", "# a lesson\n")

    ok, summary = review.receipt_state(root, head, require_base="main")
    assert not ok
    assert "no commit below it on this branch has one either" in summary


def test_the_fallback_is_opt_in_with_require_base(tmp_path: Path, commit_file, receipt_for) -> None:
    """CONTROL ARM: without `require_base` the strict SHA identity still holds.

    The receipt writer's own read-back passes no base and must keep getting the
    unrelaxed answer, or this change would have quietly widened every caller.
    """
    root = tmp_path
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    head = commit_file("graphify-out/memory/query_1.md", "# a lesson\n")

    ok, summary = review.receipt_state(root, head)
    assert not ok
    assert "no review receipt" in summary


def test_the_ancestors_own_receipt_still_has_to_pass(
    tmp_path: Path, commit_file, receipt_for
) -> None:
    """The fallback picks WHICH receipt is read; it does not soften the reading.

    A blocking finding on the ancestor must still refuse, or an exempt commit
    on top would be a way to launder an unresolved blocker.
    """
    root = tmp_path
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    path = review.receipt_path(root, reviewed)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["blocking"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
    head = commit_file("graphify-out/memory/query_1.md", "# a lesson\n")

    ok, summary = review.receipt_state(root, head, require_base="main")
    assert not ok
    assert "blocking review finding" in summary


def test_an_unreadable_delta_fails_closed(
    tmp_path: Path, commit_file, receipt_for, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A git failure must not read as "the delta is empty, so it is exempt".

    This is why `_git_result` exists at all: `_git` collapses a failure into
    `""`, and `""` is also what an identical tree legitimately returns. Sharing
    one return for both would make a broken `git diff` the most permissive
    input the gate has.
    """
    root = tmp_path
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    head = commit_file("graphify-out/memory/query_1.md", "# a lesson\n")
    # CONTROL ARM: with git working, this exact call passes.
    assert review.receipt_state(root, head, require_base="main")[0]

    real = review._git_result

    def failing_diff(repo_root: Path, *args: str) -> tuple[bool, str]:
        return (False, "") if args and args[0] == "diff" else real(repo_root, *args)

    monkeypatch.setattr(review, "_git_result", failing_diff)
    ok, summary = review.receipt_state(root, head, require_base="main")
    assert not ok
    assert "could not be read" in summary


def test_exempt_paths_match_prefixes_and_exact_files() -> None:
    """The matcher, both arms — a directory entry is a prefix, a file is exact."""
    assert review._is_exempt("graphify-out/memory/query_1.md")
    assert review._is_exempt("docs/goals/README.md")
    # A file NAMED like the directory is not inside it.
    assert not review._is_exempt("graphify-out/memory")
    # A sibling that merely shares the prefix string is not exempt.
    assert not review._is_exempt("graphify-out/memory-of-a-thing.md")
    assert not review._is_exempt("docs/goals/README.md.bak")
    assert not review._is_exempt("docs/goals/2026-07-27-x-goal.md")


def test_many_reviewed_paths_are_summarised_not_dumped(
    tmp_path: Path, git, commit_file, receipt_for
) -> None:
    """The `(+N more)` branch of `_MAX_NAMED_PATHS`, which nothing reached before.

    Delete the bound and every test still passed — a limit verified only on
    inputs below it (`repo-smells.md`, "verified only in the PASS direction").
    """
    root = tmp_path
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    for i in range(9):
        commit_file(f"python/src/kb_setup/mod_{i}.py", f"X = {i}\n")
    head = git("rev-parse", "HEAD")

    ok, summary = review.receipt_state(root, head, require_base="main")
    assert not ok
    assert "(+4 more)" in summary, summary
    # The bound must STATE its remainder, never truncate silently.
    assert summary.count("python/src/kb_setup/mod_") == review._MAX_NAMED_PATHS


def test_an_accepted_fallback_is_summarised_too(
    tmp_path: Path, git, commit_file, receipt_for
) -> None:
    """CONTROL ARM on the permissive branch — it must bound its list as well.

    Only the refusal branch was bounded, leaving the branch that lets a commit
    SHIP able to print an unbounded wall of paths.
    """
    root = tmp_path
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    for i in range(9):
        commit_file(f"graphify-out/memory/query_{i}.md", f"# lesson {i}\n")
    head = git("rev-parse", "HEAD")

    ok, summary = review.receipt_state(root, head, require_base="main")
    assert ok, summary
    assert "(+4 more)" in summary, summary


def test_a_later_ancestor_can_cover_where_the_first_does_not(
    tmp_path: Path, git, commit_file, receipt_for
) -> None:
    """Trying EVERY reviewed ancestor, not just the first rev-list yields.

    The first draft took one candidate and justified it with "a farther ancestor
    is strictly harder to accept". False: add a file and delete it again, and the
    FARTHER delta is exempt-only while the nearer one is not. Fail-closed, so it
    cost an unwarranted refusal rather than a bad acceptance — which is why it
    survived a green suite. Two lanes found it independently.
    """
    root = tmp_path
    older = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(older)
    commit_file("scratch.py", "TEMP = 1\n")
    newer = git("rev-parse", "HEAD")
    receipt_for(newer)
    git("rm", "-q", "--", "scratch.py")
    git("commit", "-q", "-m", "drop scratch")
    head = commit_file("graphify-out/memory/query_1.md", "# a lesson\n")

    # The NEARER receipt (`newer`) cannot cover HEAD: scratch.py was deleted
    # since, and a delete is a reviewed-path change. The OLDER one can — that
    # file never existed in its tree.
    assert "scratch.py" in (review._delta_paths(root, newer, head) or [])
    assert review._delta_paths(root, older, head) == ["graphify-out/memory/query_1.md"]

    ok, summary = review.receipt_state(root, head, require_base="main")
    assert ok, summary
    assert older[:12] in summary


def test_a_refused_fallback_still_explains_itself_on_a_later_failure(
    tmp_path: Path, commit_file, receipt_for
) -> None:
    """The note must reach the FAILURE returns, not only the success one.

    An accepted fallback whose ancestor receipt then fails printed
    `receipt for <ancestor-sha> …` with nothing saying why a non-HEAD SHA was
    being judged — a refusal the reader cannot act on.
    """
    root = tmp_path
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    path = review.receipt_path(root, reviewed)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["blocking"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
    head = commit_file("graphify-out/memory/query_1.md", "# a lesson\n")

    ok, summary = review.receipt_state(root, head, require_base="main")
    assert not ok
    assert "blocking review finding" in summary
    assert "covered by the receipt for" in summary, summary


def test_a_later_ancestor_is_tried_when_the_nearer_receipt_is_invalid(
    tmp_path: Path, git, commit_file, receipt_for
) -> None:
    """A qualifying DELTA is not a valid RECEIPT — both candidates get judged.

    The first draft committed to the first ancestor whose delta was exempt-only
    and never looked further, so one ancestor with a blocking finding consumed
    the branch's only chance even though an older receipt covered the same tree.
    Fail-closed, and untested, which is why it survived a green suite — the same
    single-candidate bug this feature had already fixed one dimension over.
    """
    older = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(older)
    newer = commit_file("graphify-out/memory/query_0.md", "# earlier lesson\n")
    receipt_for(newer)
    blocked = review.receipt_path(tmp_path, newer)
    data = json.loads(blocked.read_text(encoding="utf-8"))
    data["blocking"] = 1
    blocked.write_text(json.dumps(data), encoding="utf-8")
    head = commit_file("graphify-out/memory/query_1.md", "# a lesson\n")

    # Both ancestors have exempt-only deltas to HEAD; only the older validates.
    ok, summary = review.receipt_state(tmp_path, head, require_base="main")
    assert ok, summary
    assert older[:12] in summary


def test_all_candidates_invalid_still_reports_the_receipt_failure(
    tmp_path: Path, commit_file, receipt_for
) -> None:
    """CONTROL ARM — when NO candidate validates, the refusal must still be specific.

    Without this the fix above could have been "skip invalid candidates
    silently", which turns a blocking finding into a bare "no receipt".
    """
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    path = review.receipt_path(tmp_path, reviewed)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["blocking"] = 2
    path.write_text(json.dumps(data), encoding="utf-8")
    head = commit_file("graphify-out/memory/query_1.md", "# a lesson\n")

    ok, summary = review.receipt_state(tmp_path, head, require_base="main")
    assert not ok
    assert "2 blocking review finding" in summary


def test_the_most_informative_refusal_is_the_one_reported(
    tmp_path: Path, git, commit_file, receipt_for
) -> None:
    """Of several refusing ancestors, report the one naming the FEWEST files.

    Candidates arrive in `git rev-list` order — reverse chronological, so the
    NEWEST reviewed ancestor comes first. Newest is usually also fewest-offending,
    which is why the first version of this test passed with the sort deleted: it
    could only ever have agreed with it. A revert separates the two orders, and it
    is the same non-monotonicity that forced trying every candidate at all — the
    two scratch files are added after the older receipt and deleted again before
    HEAD, so they are absent from the OLDER ancestor's delta and present as
    deletions in the newer one's.
    """
    older = commit_file("python/src/kb_setup/a.py", "A = 1\n")
    receipt_for(older)
    commit_file("python/src/kb_setup/scratch_one.py", "S = 1\n")
    newer = commit_file("python/src/kb_setup/scratch_two.py", "S = 2\n")
    receipt_for(newer)
    git(
        "rm", "-q", "--", "python/src/kb_setup/scratch_one.py", "python/src/kb_setup/scratch_two.py"
    )
    git("commit", "-q", "-m", "drop the scratch files")
    commit_file("python/src/kb_setup/last.py", "L = 1\n")
    head = commit_file("graphify-out/memory/query_1.md", "# a lesson\n")

    # The measurement the assertion rests on, stated rather than assumed: the
    # NEWER ancestor is blocked by three paths, the OLDER by one.
    assert (
        len(
            [
                p
                for p in review._delta_paths(tmp_path, newer, head) or []
                if not review._is_exempt(p)
            ]
        )
        == 3
    )
    assert [
        p for p in review._delta_paths(tmp_path, older, head) or [] if not review._is_exempt(p)
    ] == ["python/src/kb_setup/last.py"]

    ok, summary = review.receipt_state(tmp_path, head, require_base="main")
    assert not ok
    # `rev-list` offers `newer` first. Reporting it would name three files
    # including two irrelevant deletions; the one that actually blocks the ship
    # is `last.py`, and it is the older ancestor's refusal that says so.
    assert older[:12] in summary
    assert "last.py" in summary
    assert "scratch_one.py" not in summary


def test_a_control_character_in_a_path_is_escaped(
    tmp_path: Path, git, commit_file, receipt_for
) -> None:
    """Every character in a refusal comes from a filename in someone's commit.

    A newline splits one line of tool output into what looks like two; an ANSI
    escape can repaint the lines around it. `ship`/`land` print these strings, so
    the gate's own diagnosis is the one part of its output an attacker can shape.
    """
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    nasty = "python/src/kb_setup/we\x1b[2Kird\nname.py"
    (tmp_path / nasty).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / nasty).write_text("X = 1\n", encoding="utf-8")
    git("add", "--", nasty)
    git("commit", "-q", "-m", "odd name")
    head = git("rev-parse", "HEAD")

    ok, summary = review.receipt_state(tmp_path, head, require_base="main")
    assert not ok
    # The path is still identifiable...
    assert "ird" in summary
    # ...but neither control character survives into the terminal.
    assert "\x1b" not in summary
    assert "\n" not in summary
    assert "\\x1b" in summary


def test_an_ordinary_non_ascii_path_is_left_alone(
    tmp_path: Path, git, commit_file, receipt_for
) -> None:
    r"""CONTROL ARM — escaping must not mangle a legitimate filename.

    A `unicode_escape` round-trip would turn every accented or CJK path into
    `\\xNN` noise, costing legibility for every honest filename to defend against
    a rare one.
    """
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    head = commit_file("python/src/kb_setup/café_日本.py", "X = 1\n")

    ok, summary = review.receipt_state(tmp_path, head, require_base="main")
    assert not ok
    assert "café_日本.py" in summary
    assert "\\x" not in summary


def test_a_non_utf8_pathname_refuses_instead_of_crashing(
    tmp_path: Path, commit_file, receipt_for, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`text=True` decodes, and `UnicodeDecodeError` is not an `OSError`.

    So a pathname git holds as non-UTF-8 bytes escaped as a TRACEBACK out of the
    middle of `ship`/`land` — a crash where this module's whole contract is a
    worded refusal. Raised through the real call site rather than by planting an
    undecodable filename, because whether a given filesystem will accept one is
    itself platform-dependent, and a test that silently does not run on macOS is
    the kind of probe this repo keeps catching.
    """
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    head = commit_file("graphify-out/memory/query_1.md", "# a lesson\n")
    # CONTROL ARM: it passes with git answering normally.
    assert review.receipt_state(tmp_path, head, require_base="main")[0]

    real = review.subprocess.run

    # The kwargs are restated rather than forwarded: `**kwargs: object` fails ty
    # against `subprocess.run`'s overloads and `**kwargs: Any` fails ruff ANN401,
    # and there is no inline suppression in this repo. They are the exact set
    # `_git_result` passes, so the stub stays honest about what it stands in for.
    def decode_error_on_diff(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["git", "diff"]:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        return real(cmd, cwd=tmp_path, capture_output=True, text=True, check=False, timeout=30)

    monkeypatch.setattr(review.subprocess, "run", decode_error_on_diff)
    ok, summary = review.receipt_state(tmp_path, head, require_base="main")
    assert not ok
    assert "could not be read" in summary


def test_a_leading_space_in_a_pathname_survives_the_delta(
    tmp_path: Path, git, commit_file, receipt_for
) -> None:
    r"""`_git_result` must not strip the NUL-joined `-z` blob.

    `.strip()` ate a leading space from the FIRST path in the stream, so
    `" graphify-out/memory/x.md"` and `"graphify-out/memory/x.md"` became the
    same string — and in the shape that matters, an indented reviewed path could
    read as an exempt one. The file here is named with a leading space on
    purpose; `-z` exists so git hands over the bytes it has.
    """
    reviewed = commit_file("python/src/kb_setup/thing.py", "def f(): ...\n")
    receipt_for(reviewed)
    odd = " graphify-out/memory/leading-space.md"
    (tmp_path / odd).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / odd).write_text("# not exempt\n", encoding="utf-8")
    git("add", "--", odd)
    git("commit", "-q", "-m", "leading space")
    head = git("rev-parse", "HEAD")

    assert review._delta_paths(tmp_path, reviewed, head) == [odd]
    # And it must NOT be treated as exempt: the exempt entry has no leading space.
    ok, summary = review.receipt_state(tmp_path, head, require_base="main")
    assert not ok, summary


# ---------------------------- the one-lane policy skip (`by-policy-one-lane`) ----


def test_by_policy_excuses_the_three_lanes_the_policy_stands_down(tmp_path: Path) -> None:
    """The receipt shape the simplified one-lane review writes.

    Ray's decision (2026-07-29): the review runs the COLD lane only. The other
    three still have to be accounted for, because `LANES` is a closed set — so
    they need a reason that is TRUE. `not-applicable-*` would not be: it asserts
    the lane read this diff and had nothing to say, which is a judgement nobody
    made.
    """
    ok, _ = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=["cold:codex"],
            lanes_skipped=[
                "standards:by-policy-one-lane",
                "spec:by-policy-one-lane",
                "silent-failure:by-policy-one-lane",
            ],
        ),
        _SHA,
    )
    assert ok


def test_by_policy_can_never_excuse_the_cold_lane(tmp_path: Path) -> None:
    """The one thing this reason must NOT be able to say.

    The one-lane policy *is* "run cold", so `cold:by-policy-one-lane` is
    self-contradictory: it cites the policy as grounds for skipping the lane the
    policy exists to run. A lane-blind prefix in `_SKIP_ANY_LANE` would have
    accepted it — the fourth instance of the hole this module has closed three
    times — and the `records no lane that actually ran` backstop only fires when
    ALL four lanes are skipped, so it would not have caught this.
    """
    ok, summary = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=["standards", "spec", "silent-failure"],
            lanes_skipped=["cold:by-policy-one-lane"],
        ),
        _SHA,
    )
    assert not ok
    assert "not excused" in summary
    assert "cold:by-policy-one-lane" in summary


def test_by_policy_is_an_exact_token_not_a_prefix(tmp_path: Path) -> None:
    """A near-miss must not pass. `startswith` already cost this module one defect."""
    for bogus in ("standards:by-policy", "standards:by-policy-", "standards:by-policy-onelane"):
        ok, summary = review.receipt_state(
            _write(tmp_path, lanes_ran=["cold:codex"], lanes_skipped=[bogus]),
            _SHA,
        )
        assert not ok, f"{bogus!r} should not excuse a lane"
        assert "not excused" in summary


def test_all_four_lanes_skipped_by_policy_is_still_refused(tmp_path: Path) -> None:
    """Control arm on the `records no lane that actually ran` backstop.

    It must skip ALL FOUR. Skipping only two was caught by the earlier
    `lane(s) unaccounted for` check instead, so this test passed without ever
    reaching the backstop its own name claims to exercise — a tautological probe.
    (Cold lane.) `cold` is included here even though `by-policy-one-lane` cannot
    excuse it, because the accounting check runs BEFORE the excuse check and this
    test is about the backstop, not the scoping; the two are asserted apart below.
    """
    ok, summary = review.receipt_state(
        _write(
            tmp_path,
            lanes_ran=[],
            lanes_skipped=[f"{lane}:not-applicable-probe" for lane in review.LANES],
        ),
        _SHA,
    )
    assert not ok
    assert "records no lane that actually ran" in summary


def test_the_accepted_reason_help_names_the_new_reason() -> None:
    """The error message must tell the author what IS accepted.

    A gate that rejects without naming the alternative is how the previous
    reasons got invented by hand in the first place.
    """
    help_text = review._skip_reason_help()
    assert "by-policy-one-lane" in help_text
    assert "not-applicable-" in help_text


# ------------------------------------------------ strip_lane_variant (#148) ----


def test_strip_lane_variant_removes_a_variant_from_a_lane_report_name():
    got = review.strip_lane_variant(".agent/kb/review/reports/review-abc123-cold:codex.md")
    assert got == ".agent/kb/review/reports/review-abc123-cold.md"


def test_strip_lane_variant_keeps_a_hyphenated_lane_intact():
    """`silent-failure` must survive: the variant separator is `:`, never the last `-`."""
    got = review.strip_lane_variant("review-abc123-silent-failure:codex.md")
    assert got == "review-abc123-silent-failure.md"


def test_strip_lane_variant_leaves_a_name_with_no_variant_alone():
    assert review.strip_lane_variant("review-abc123-cold.md") == "review-abc123-cold.md"


def test_strip_lane_variant_leaves_a_non_review_filename_alone():
    assert review.strip_lane_variant("docs/notes:draft.md") == "docs/notes:draft.md"


def test_strip_lane_variant_leaves_another_directory_alone():
    """THE REACHING CASE, which the test above could not reach.

    That one varies the basename PREFIX, so it only ever exercised the
    `startswith("review-")` guard. The claim the docstring actually made was
    about the DIRECTORY, and nothing tested it — so `docs/review-2026:q3.md`
    became `docs/review-2026.md`: a token outside this module's directory
    silently rewritten into a name that may exist, which is the false-green
    direction. Found by the standards lane running the function rather than
    reading it. (H1.)
    """
    assert review.strip_lane_variant("docs/review-2026:q3.md") == "docs/review-2026:q3.md"
    assert (
        review.strip_lane_variant("python/src/kb_setup/review-notes:draft.md")
        == "python/src/kb_setup/review-notes:draft.md"
    )


def test_strip_lane_variant_accepts_the_report_directory_and_a_bare_name():
    """The two forms handoffs really write. Control arm for the test above."""
    assert (
        review.strip_lane_variant(".agent/kb/review/reports/review-abc-cold:codex.md")
        == ".agent/kb/review/reports/review-abc-cold.md"
    )
    assert review.strip_lane_variant("review-abc-cold:codex.md") == "review-abc-cold.md"


def test_strip_lane_variant_preserves_an_elision():
    """`_safe_lane` is NOT applied here, and this is why.

    It keeps only alphanumerics, `-` and `_`, so composing it as the writer does
    would turn `review-abc1234…-cold` into `review-abc1234-cold` — destroying the
    elision and silently converting a pattern into a literal that matches
    nothing. A review lane proposed matching the writer exactly; running it is
    what showed the two sides are not symmetric. (J1.)
    """
    got = review.strip_lane_variant("review-abc1234…-cold:codex.md")
    assert got == "review-abc1234…-cold.md"


def test_strip_lane_variant_leaves_a_bare_non_review_name_alone():
    """The `review-` prefix is load-bearing ONLY for a bare filename — pin that.

    With a directory the scope check already refuses anything outside
    `REPORT_DIR`, so removing the prefix guard changes nothing there. It changes
    everything for a bare name: `notes:draft.md` has no directory to judge, and
    without the prefix it would be rewritten to `notes.md` — a token repaired
    into a name that may exist. Mutation arm B13 survived until this test
    existed, which is precisely what the arm is for.
    """
    assert review.strip_lane_variant("notes:draft.md") == "notes:draft.md"
