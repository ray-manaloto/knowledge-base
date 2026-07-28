"""Tests for kb_setup.pr — the ship/land PR workflow.

Every test drives the real functions with subprocess stubbed, and each
assertion has a control arm: a check that can only pass is not a check.
"""

from __future__ import annotations

import json

import pytest
from kb_setup import pr


class _Proc:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _stub_run(monkeypatch, handler) -> None:
    """Route kb_setup.pr's captured subprocess calls through `handler(cmd)`."""
    monkeypatch.setattr(pr.subprocess, "run", lambda cmd, **_kw: handler(cmd))


# --------------------------------------------------------------------------
# checks_state
# --------------------------------------------------------------------------


def test_checks_state_green_when_all_pass(monkeypatch):
    rows = [{"name": "CodeRabbit", "bucket": "pass"}, {"name": "lint", "bucket": "skipping"}]
    _stub_run(monkeypatch, lambda _cmd: _Proc(0, json.dumps(rows)))
    green, summary = pr.checks_state(7)
    assert green is True
    # CodeRabbit is advisory, so only `lint` is counted as binding — but the
    # advisory result is still REPORTED, never silently dropped.
    assert "1 binding check(s) green" in summary
    assert "CodeRabbit=pass" in summary


def test_checks_state_red_when_any_fails(monkeypatch):
    """CONTROL ARM for the test above — same shape, one failing bucket."""
    rows = [{"name": "CodeRabbit", "bucket": "pass"}, {"name": "lint", "bucket": "fail"}]
    _stub_run(monkeypatch, lambda _cmd: _Proc(1, json.dumps(rows)))
    green, summary = pr.checks_state(7)
    assert green is False
    assert "lint=fail" in summary


def test_checks_state_binding_pending_is_not_green(monkeypatch):
    """`pending` on a BINDING check means the answer is not in yet.

    Unchanged property, narrowed subject: this used to be asserted with
    CodeRabbit, which is now advisory (see the two tests below). The property
    itself never moved — only which checks it governs.
    """
    rows = [{"name": "lint", "bucket": "pending"}]
    _stub_run(monkeypatch, lambda _cmd: _Proc(0, json.dumps(rows)))
    green, _ = pr.checks_state(7)
    assert green is False


def test_checks_state_advisory_pending_does_not_block(monkeypatch):
    """CodeRabbit sitting in a quota queue must not block a merge.

    The motivating incident: a doc-only PR blocked on `pending` with nothing
    wrong. CodeRabbit returned `pass — Review rate limited` on 4 of 5 PRs here,
    so waiting on it is waiting on someone else's quota, not on a review.
    """
    rows = [{"name": "CodeRabbit", "bucket": "pending"}, {"name": "lint", "bucket": "pass"}]
    _stub_run(monkeypatch, lambda _cmd: _Proc(0, json.dumps(rows)))
    green, summary = pr.checks_state(7)
    assert green is True
    assert "advisory (not blocking): CodeRabbit=pending" in summary


def test_checks_state_advisory_failure_does_not_block(monkeypatch):
    """An advisory check is advisory in EVERY bucket, including `fail`.

    Control arm for the pair above: if only `pending` were tolerated, a
    rate-limit that surfaced as `fail` would still deadlock the merge.
    """
    rows = [{"name": "CodeRabbit", "bucket": "fail"}, {"name": "lint", "bucket": "pass"}]
    _stub_run(monkeypatch, lambda _cmd: _Proc(1, json.dumps(rows)))
    green, summary = pr.checks_state(7)
    assert green is True
    assert "CodeRabbit=fail" in summary


def test_checks_state_advisory_only_still_reports_binding_zero(monkeypatch):
    """A PR whose ONLY check is advisory is green, and says so honestly."""
    rows = [{"name": "CodeRabbit", "bucket": "pending"}]
    _stub_run(monkeypatch, lambda _cmd: _Proc(0, json.dumps(rows)))
    green, summary = pr.checks_state(7)
    assert green is True
    # NOT "0 binding check(s) green" — nothing was verified remotely, and that
    # is a different sentence from "verified clean".
    assert "no binding checks" in summary
    assert "green" not in summary.split("|")[0]


def test_checks_state_no_checks_is_green(monkeypatch):
    """This repo has no CI; 'no checks' must not deadlock the merge."""
    _stub_run(monkeypatch, lambda _cmd: _Proc(1, "[]"))
    green, summary = pr.checks_state(7)
    assert green is True
    assert "no checks" in summary


def test_checks_state_unparsable_is_not_green(monkeypatch):
    """A probe that could not ask the question must not answer 'yes'."""
    _stub_run(monkeypatch, lambda _cmd: _Proc(1, "gh: could not resolve to a PullRequest"))
    green, _ = pr.checks_state(7)
    assert green is False


# --------------------------------------------------------------------------
# land — the SHA pin is the safety property
# --------------------------------------------------------------------------


def test_land_pins_merge_to_verified_head_sha(monkeypatch, tmp_path):
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:3] == ["gh", "pr", "checks"]:
            return _Proc(0, json.dumps([{"name": "CodeRabbit", "bucket": "pass"}]))
        if cmd[:3] == ["gh", "pr", "view"]:
            return _Proc(0, "deadbeefcafe1234\n")
        return _Proc(0, "")

    _stub_run(monkeypatch, handler)
    assert pr.land_main(tmp_path, 42) == 0

    merge = next(c for c in seen if c[:3] == ["gh", "pr", "merge"])
    assert "--match-head-commit" in merge
    assert merge[merge.index("--match-head-commit") + 1] == "deadbeefcafe1234"
    assert "--squash" in merge


def test_land_refuses_when_checks_red(monkeypatch, tmp_path):
    """CONTROL ARM: red checks must stop the merge before it is attempted."""
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:3] == ["gh", "pr", "checks"]:
            return _Proc(1, json.dumps([{"name": "lint", "bucket": "fail"}]))
        return _Proc(0, "")

    _stub_run(monkeypatch, handler)
    assert pr.land_main(tmp_path, 42) == 1
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in seen), "merge must not be attempted"


def test_land_refuses_when_head_sha_unreadable(monkeypatch, tmp_path):
    """Without a SHA there is nothing to pin to, so the merge must not happen."""
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:3] == ["gh", "pr", "checks"]:
            return _Proc(0, json.dumps([{"name": "x", "bucket": "pass"}]))
        if cmd[:3] == ["gh", "pr", "view"]:
            return _Proc(1, "")
        return _Proc(0, "")

    _stub_run(monkeypatch, handler)
    assert pr.land_main(tmp_path, 42) == 1
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in seen)


# --------------------------------------------------------------------------
# ship — preflight refuses before doing anything irreversible
# --------------------------------------------------------------------------


@pytest.mark.parametrize("branch", ["main", ""])
def test_ship_refuses_off_a_feature_branch(monkeypatch, tmp_path, branch):
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        return _Proc(0, branch)

    _stub_run(monkeypatch, handler)
    assert pr.ship_main(tmp_path) == 1
    assert not any(c[:2] == ["git", "push"] for c in seen)


def test_ship_refuses_dirty_tree(monkeypatch, tmp_path):
    def handler(cmd: list[str]) -> _Proc:
        if cmd[:2] == ["git", "rev-parse"]:
            return _Proc(0, "feat/x")
        if cmd[:2] == ["git", "status"]:
            return _Proc(0, " M mise.toml\n")
        return _Proc(0, "")

    _stub_run(monkeypatch, handler)
    assert pr.ship_main(tmp_path) == 1


def _clean_branch_handler(cmd: list[str]) -> _Proc:
    """A clean feature branch with an existing PR — the happy path for ship."""
    if cmd[:2] == ["git", "rev-parse"]:
        return _Proc(0, "feat/x")
    if cmd[:2] == ["git", "status"]:
        return _Proc(0, "")
    if cmd[:3] == ["gh", "pr", "view"]:
        return _Proc(0, "99")
    return _Proc(0, "")


def test_ship_refuses_without_a_review_receipt(monkeypatch, tmp_path):
    """An unreviewed commit must not leave the machine.

    CodeRabbit is advisory here, so the local `kb-review` receipt IS the review
    gate. Nothing else would stop an unreviewed push.
    """
    _stub_run(monkeypatch, _clean_branch_handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 1


def test_ship_accepts_clean_feature_branch(monkeypatch, tmp_path):
    """CONTROL ARM for the refusals above — the same path must succeed.

    The only difference from `test_ship_refuses_without_a_review_receipt` is
    the receipt, which is what makes that test a check rather than decoration.
    """
    from kb_setup import review

    for lane in ("standards", "spec"):
        rp = review.report_path(tmp_path, "feat/x", lane)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text("NO FINDINGS", encoding="utf-8")
    review.write_receipt(
        tmp_path,
        review.Receipt(
            sha="feat/x",  # what the stubbed `git rev-parse HEAD` returns
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
    _stub_run(monkeypatch, _clean_branch_handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 0


def test_ship_refuses_on_blocking_review_findings(monkeypatch, tmp_path):
    """A receipt that EXISTS but records blocking findings must still refuse."""
    from kb_setup import review

    review.write_receipt(
        tmp_path,
        review.Receipt(
            sha="feat/x",
            fixed_point="main",
            fixed_point_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            lanes_ran=("standards", "spec", "cold:codex", "silent-failure"),
            lanes_skipped=(),
            findings=4,
            blocking=1,
        ),
    )
    _stub_run(monkeypatch, _clean_branch_handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 1


def test_ship_does_not_push_when_gates_fail(monkeypatch, tmp_path):
    """A red gate must stop the push — that is the whole point of gating first."""
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:2] == ["git", "rev-parse"]:
            return _Proc(0, "feat/x")
        return _Proc(0, "")

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: False)
    assert pr.ship_main(tmp_path) == 1
    assert not any(c[:2] == ["git", "push"] for c in seen)


def test_ship_refuses_when_head_moves_during_the_gates(monkeypatch, tmp_path):
    """The pre-push re-check must actually guard the push.

    REALISTIC MUTATION, per `probes-need-a-control-arm.md`: the gates take
    minutes and HEAD can move under them (an amend to fix a gate is the normal
    way it happens). Without this test the second check is decoration — deleting
    it kept the whole suite green, which is how the standards lane found it.
    """
    from kb_setup import review

    for lane in ("standards", "spec"):
        rp = review.report_path(tmp_path, "feat/x", lane)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text("NO FINDINGS", encoding="utf-8")
    review.write_receipt(
        tmp_path,
        review.Receipt(
            sha="feat/x",
            fixed_point="main",
            fixed_point_sha="a" * 40,
            lanes_ran=("standards", "spec"),
            lanes_skipped=(
                "cold:not-applicable-docs-only",
                "silent-failure:not-applicable-docs-only",
            ),
            findings=0,
            blocking=0,
        ),
    )

    seen: list[list[str]] = []
    heads = iter(["feat/x", "moved-after-the-gates"])

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        return _clean_branch_handler(cmd)

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    # HEAD reads `feat/x` for the pre-gate check, then a different commit for
    # the pre-push one — exactly the window an amend opens.
    monkeypatch.setattr(review, "head_sha", lambda _root: next(heads))

    assert pr.ship_main(tmp_path) == 1
    assert not any(c[:2] == ["git", "push"] for c in seen), "must not push"
