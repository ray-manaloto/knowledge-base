"""Tests for kb_setup.pr — the ship/land PR workflow.

Every test drives the real functions with subprocess stubbed, and each
assertion has a control arm: a check that can only pass is not a check.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable

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


def _reviewed(tmp_path, oid: str) -> None:
    """Write a valid review receipt (and its lane reports) for ``oid``."""
    from kb_setup import review

    for lane in ("standards", "spec"):
        rp = review.report_path(tmp_path, oid, lane)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text("NO FINDINGS", encoding="utf-8")
    review.write_receipt(
        tmp_path,
        review.Receipt(
            sha=oid,
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


def _land_handler(seen: list[list[str]]) -> Callable[[list[str]], _Proc]:
    """A PR whose checks are green and whose head is a fixed SHA."""

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:3] == ["gh", "pr", "checks"]:
            return _Proc(0, json.dumps([{"name": "CodeRabbit", "bucket": "pass"}]))
        if cmd[:3] == ["gh", "pr", "view"]:
            return _Proc(0, "deadbeefcafe1234\n")
        return _Proc(0, "")

    return handler


def test_land_pins_merge_to_verified_head_sha(monkeypatch, tmp_path):
    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")
    _stub_run(monkeypatch, _land_handler(seen))
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


def _write_valid_receipt(tmp_path, sha: str = "feat/x") -> None:
    """Write a PASSING receipt, plus the reports it must be backed by.

    ``sha`` defaults to what the stubbed `git rev-parse HEAD` returns.

    Extracted because several tests need a receipt that is *not* the thing under
    test. A test aimed at a LATER gate has to get past this one, or it silently
    becomes a second test of this one — which is exactly what happened to
    `test_ship_does_not_push_when_gates_fail`.
    """
    from kb_setup import review

    for lane in ("standards", "spec"):
        rp = review.report_path(tmp_path, sha, lane)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text("NO FINDINGS", encoding="utf-8")
    review.write_receipt(
        tmp_path,
        review.Receipt(
            sha=sha,
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
    _write_valid_receipt(tmp_path)
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
    """A red gate must stop the push — that is the whole point of gating first.

    The receipt is written FIRST so this test actually reaches `run_gates`.
    Without it `ship_main` returned at the receipt check and never evaluated the
    gates at all: both assertions passed for the wrong reason, and deleting the
    gate check entirely left the test green. That is the repo's own "a gate
    verified only in the PASS direction" smell, sitting in the test that guards
    a gate. Found by the cold lane.

    `reached` is the control arm — without it this test cannot tell "refused
    because the gates were red" from "refused before the gates ran".
    """
    _write_valid_receipt(tmp_path)
    seen: list[list[str]] = []
    reached: list[str] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        return _clean_branch_handler(cmd)

    def red_gates(_root) -> bool:
        reached.append("run_gates")
        return False

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", red_gates)
    assert pr.ship_main(tmp_path) == 1
    assert reached == ["run_gates"], "never reached the gates — the receipt refused first"
    assert not any(c[:2] == ["git", "push"] for c in seen)


def test_ship_pushes_the_validated_sha_not_the_branch_name(monkeypatch, tmp_path):
    """The push must be pinned to the commit the receipt was just checked against.

    REALISTIC MUTATION, per `probes-need-a-control-arm.md`: `git push origin
    <branch>` resolves the branch at push time, so HEAD moving between the
    pre-push receipt read and the push itself sends a commit no lane ever read.
    The pre-push re-check cannot close that window — only the refspec can, by
    making the validated object and the pushed object the same one.

    Probed against real git before writing this: pushing `<sha>:refs/heads/<b>`
    after a further commit lands the SHA, while `push <b>` lands the newer HEAD.
    """
    _write_valid_receipt(tmp_path)
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        return _clean_branch_handler(cmd)

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 0

    pushes = [c for c in seen if c[:2] == ["git", "push"]]
    assert len(pushes) == 1
    # Spelled out literally rather than rebuilt from the code under test: a
    # fixture built by the function it checks inherits that function's bugs.
    assert pushes[0] == ["git", "push", "origin", "feat/x:refs/heads/feat/x"]
    assert "feat/x" in pushes[0][3], "the branch name alone would re-resolve at push time"
    # `-u` cannot set tracking from a raw-SHA refspec, so it is set separately.
    assert ["git", "branch", "--set-upstream-to", "origin/feat/x", "feat/x"] in seen


def test_ship_refuses_on_detached_head(monkeypatch, tmp_path):
    """A detached HEAD must not ship — and the old code got this for free.

    `git rev-parse --abbrev-ref HEAD` returns the literal string "HEAD" when
    detached (paused bisect, stopped rebase, `checkout <sha>`), which is neither
    "" nor "main" and so passed the other two refusals. `git push -u origin HEAD`
    then failed on its own — an ACCIDENTAL guard. Pinning the refspec removed the
    accident: `git push origin <sha>:refs/heads/HEAD` succeeds and creates a
    remote branch literally called `HEAD`. Probed against real git both ways.

    REALISTIC MUTATION: delete the `branch == "HEAD"` arm and this fails.

    The receipt is written for the literal SHA `"HEAD"` on purpose. Without it
    this test passed for the wrong reason — the receipt check refused first, so
    deleting the guard left it green. The mutation probe caught that, which is
    the second time in this branch a detached-HEAD-shaped test was decoration.
    """
    _write_valid_receipt(tmp_path, sha="HEAD")
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:2] == ["git", "rev-parse"]:
            return _Proc(0, "HEAD")
        if cmd[:3] == ["gh", "pr", "view"]:
            return _Proc(0, "99")
        return _Proc(0, "")

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 1
    assert not any(c[:2] == ["git", "push"] for c in seen), "must not push from a detached HEAD"


def test_open_or_update_pr_refuses_when_the_pr_state_cannot_be_read(monkeypatch, tmp_path):
    """`gh pr view` failing for any reason OTHER than "no PR" must not create one.

    Flagged by the standards lane in two consecutive rounds as the one new gate
    with no coverage in either direction. Its whole discriminator is gh's English
    error text, so this test is also the tripwire for gh rewording it.
    """
    _write_valid_receipt(tmp_path)
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:3] == ["gh", "pr", "view"]:
            return _Proc(1, "error: could not authenticate to github.com")
        return _clean_branch_handler(cmd)

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 1
    assert not any(c[:3] == ["gh", "pr", "create"] for c in seen), "must not open a second PR"


def test_open_or_update_pr_creates_when_there_is_genuinely_no_pr(monkeypatch, tmp_path):
    """CONTROL ARM for the refusal above — the "no PR" wording must still create.

    Without this arm, refusing unconditionally would also pass the test above.
    """
    _write_valid_receipt(tmp_path)
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:3] == ["gh", "pr", "view"]:
            return _Proc(1, "no pull requests found for branch feat/x")
        return _clean_branch_handler(cmd)

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 0
    assert any(c[:3] == ["gh", "pr", "create"] for c in seen)


def test_open_or_update_pr_refuses_an_unparsable_success(monkeypatch, tmp_path):
    """rc=0 whose output is not a number is an UNREAD answer, not "no PR".

    `_run` merges stdout and stderr, so a warning printed beside the number
    defeats `.isdigit()`. This used to fall through to `gh pr create` and open a
    second PR for a branch that already had one.
    """
    _write_valid_receipt(tmp_path)
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:3] == ["gh", "pr", "view"]:
            return _Proc(0, "warning: upgrade gh\n99")
        return _clean_branch_handler(cmd)

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 1
    assert not any(c[:3] == ["gh", "pr", "create"] for c in seen)


def test_await_terminal_does_not_claim_terminal_on_a_failed_watch(monkeypatch):
    """A non-zero `gh` exit must not be reported as "reached a terminal state".

    rc cannot discriminate a FAILING check (terminal, expected) from "could not
    ask" (auth expiry, no such PR), so the note declines to assert either — what
    it must not do is assert the one it cannot know.
    """
    _stub_run(monkeypatch, lambda _cmd: _Proc(1, "", "could not resolve to a PullRequest"))
    note = pr.await_terminal(7, timeout=1)
    assert "reached a terminal state" not in note
    assert "rc=1" in note


def test_await_terminal_reports_terminal_on_a_clean_watch(monkeypatch):
    """CONTROL ARM — rc=0 must still report the terminal state."""
    _stub_run(monkeypatch, lambda _cmd: _Proc(0, ""))
    assert pr.await_terminal(7, timeout=1) == "reached a terminal state"


def test_checks_state_rejects_non_object_rows(monkeypatch):
    """A scalar row must produce the module's worded refusal, not AttributeError."""
    _stub_run(monkeypatch, lambda _cmd: _Proc(0, json.dumps(["lint", 3])))
    green, summary = pr.checks_state(7)
    assert green is False
    assert "want a list of objects" in summary


def test_ship_refuses_when_head_moves_during_the_gates(monkeypatch, tmp_path):
    """The pre-push re-check must actually guard the push.

    REALISTIC MUTATION, per `probes-need-a-control-arm.md`: the gates take
    minutes and HEAD can move under them (an amend to fix a gate is the normal
    way it happens). Without this test the second check is decoration — deleting
    it kept the whole suite green, which is how the standards lane found it.
    """
    from kb_setup import review

    _write_valid_receipt(tmp_path)

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


def test_land_waits_for_a_terminal_state_before_reading_checks(monkeypatch, tmp_path):
    """`--watch` must actually be used, not a hand-rolled poll (`gh-cli-watch.md`).

    "Never blocking" is not "never looking": a CodeRabbit verdict that lands
    ten seconds after the merge was never read, and reading it is free.
    """
    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")
    _stub_run(monkeypatch, _land_handler(seen))
    assert pr.land_main(tmp_path, 42) == 0
    watched = [c for c in seen if c[:3] == ["gh", "pr", "checks"] and "--watch" in c]
    assert watched, "land must give the checks a bounded chance to settle"


def test_await_terminal_expiry_proceeds_rather_than_refusing(monkeypatch):
    """Past the bound the remaining delay is a rate limit, not a review.

    This is the half of the spec that matters: waiting on quota is the thing
    that blocked a doc-only PR, so expiry must be a note and never a refusal.
    """

    def boom(*_a: object, **_kw: object) -> None:
        raise subprocess.TimeoutExpired(cmd="gh", timeout=180)

    monkeypatch.setattr(pr.subprocess, "run", boom)
    note = pr.await_terminal(7, timeout=180)
    assert "quota" in note
    assert "proceeding" in note


def test_land_refuses_an_unreviewed_pr_head(monkeypatch, tmp_path):
    """CONTROL ARM: the same green PR, with no receipt for its head.

    `ship` guards only what IT pushes; a commit pushed afterwards by any other
    route reached the merge reviewed by nothing.
    """
    seen: list[list[str]] = []
    _stub_run(monkeypatch, _land_handler(seen))
    assert pr.land_main(tmp_path, 42) == 1
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in seen), "merge must not be attempted"
