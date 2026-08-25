# Copyright (c) 2026 Raymond Manaloto
"""Tests for kb_setup.pr — the ship/land PR workflow.

Every test drives the real functions with subprocess stubbed, and each
assertion has a control arm: a check that can only pass is not a check.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable

import pytest
from conftest import handoff_lead
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
        rp.write_text(f"NO FINDINGS — reviewed {oid}", encoding="utf-8")
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


#: The stub's answer for `gh pr view <n> --json headRefName ...` — a plain,
#: well-formed branch name so `check-ref-format` (routed to the catch-all,
#: which answers rc 0 for anything unmatched) passes it without special-casing.
_LAND_LOCAL_BRANCH = "feat/local-ahead-stub"


def _land_handler(seen: list[list[str]]) -> Callable[[list[str]], _Proc]:
    """A PR whose checks are green, head is a fixed SHA, with NO matching local branch.

    `git rev-parse --verify --quiet` is stubbed to answer ABSENT (#493's state
    1: no local branch of that name here, nothing to compare) so every land
    test written before the local-ahead guard keeps merging without having to
    know about it. A test that wants a different local-ahead state layers its
    own handler over this one — `test_land_refuses_when_checks_red` and
    `test_land_refuses_when_head_sha_unreadable` already do exactly that for
    their own concerns.
    """

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:3] == ["gh", "pr", "checks"]:
            return _Proc(0, json.dumps([{"name": "CodeRabbit", "bucket": "pass"}]))
        if cmd[:3] == ["gh", "pr", "view"]:
            # `_land_handler` used to answer every `--json` field with the SAME
            # oid-shaped string, so `pr_head_branch` received the head OID as a
            # "branch name" — a different code path went untested wearing this
            # stub's clothes (#493 premise-verifier M5). Dispatch on the field.
            if "headRefName" in cmd:
                return _Proc(0, f"{_LAND_LOCAL_BRANCH}\n")
            # Matches `_reviewed`'s `fixed_point_sha`, so the branch-coverage
            # check `land` applies sees a receipt that covers the whole branch.
            # Without it `base_sha` returns "" and every land test refuses on
            # "could not resolve" — fail-closed working, but testing the wrong
            # thing.
            return _Proc(0, "deadbeefcafe1234\n")
        if cmd[:2] == ["git", "merge-base"]:
            return _Proc(0, "a" * 40)
        if cmd[:3] == ["git", "rev-parse", "--verify"]:
            # No such local branch — real git's own shape for "absent": rc 1,
            # empty output (`--quiet` suppresses the diagnostic).
            return _Proc(1, "")
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


def test_land_refuses_a_suffix_only_receipt(monkeypatch, tmp_path):
    """`land` must demand the whole branch was reviewed, not just its tip.

    `ship` refuses a `--fixed-point HEAD^` receipt; `land` did not, and `land` is
    what puts commits on `main`. Reaching it does not require defeating `ship` —
    `gh pr create` is not guard-denied here, and this gate is documented as the
    backstop for exactly that bypass, so the backstop did not cover its own
    stated case. Found by the cold lane and rated blocking; two other lanes found
    the same asymmetry and rated it lower.
    """
    from kb_setup import review

    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")  # written with fixed_point_sha "a"*40
    # The branch's real base is a DIFFERENT commit, so the receipt covers only a
    # suffix. Stubbed rather than left to a non-git tmp_path, or this would
    # short-circuit on "could not resolve" and pass without comparing anything.
    monkeypatch.setattr(review, "base_sha", lambda *_a, **_kw: "f" * 40)
    _stub_run(monkeypatch, _land_handler(seen))

    assert pr.land_main(tmp_path, 42) == 1
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in seen), "must not merge"


def test_land_accepts_a_full_branch_receipt(monkeypatch, tmp_path):
    """CONTROL ARM — the same path with a matching base must still merge.

    The `monkeypatch.setattr(review, "base_sha", …)` this used to carry was a
    NO-OP: `_land_handler` already answers `"a" * 40` to `git merge-base`, which
    is what `_reviewed` records as `fixed_point_sha`. So the line that looked
    like the arm's variable was setting it to the value it already had, and the
    contrast with `test_land_refuses_a_suffix_only_receipt` — whose stub really
    does change it, to `"f" * 40` — was invisible at the call site. Removed, and
    the source of the matching base named instead. (#59)
    """
    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")  # records fixed_point_sha "a" * 40
    _stub_run(monkeypatch, _land_handler(seen))  # answers merge-base "a" * 40 — they MATCH

    assert pr.land_main(tmp_path, 42) == 0
    assert any(c[:3] == ["gh", "pr", "merge"] for c in seen)


def test_the_coverage_gate_resolves_origin_main_not_local_main(monkeypatch, tmp_path):
    """The base must be resolved against the ref the PR is actually opened against.

    `gh pr create --base main` targets GitHub's `main`; the gate resolved the
    LOCAL one. Local `main` ahead along the branch's own ancestry moves the
    merge-base forward, so the review covered LESS than the PR's real diff while
    the receipt claimed the whole branch. (#54)

    Asserted on the `git merge-base` ARGUMENT rather than on an outcome, because
    both refs answer `"a" * 40` in these stubs — an outcome assertion could not
    tell them apart, which is the #59 shape. Spelled literally rather than
    interpolating `review.DEFAULT_BASE_REF`: a fixture built from the constant
    under test passes whatever that constant becomes.
    """
    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")
    _stub_run(monkeypatch, _land_handler(seen))
    assert pr.land_main(tmp_path, 42) == 0

    bases = [c for c in seen if c[:2] == ["git", "merge-base"]]
    assert bases, "the coverage gate must resolve a base at all"
    assert all("origin/main" in c for c in bases), f"resolved something else: {bases}"
    assert not any(c[3:4] == ["main"] for c in bases), "local `main` is the defect"


def test_an_unresolvable_base_refuses_rather_than_falling_back(monkeypatch, tmp_path):
    """CONTROL ARM for the choice above: no `origin/main` must REFUSE, not degrade.

    Falling back to local `main` would silently reinstate #54 on exactly the
    clones least able to notice. "Could not check" is never rendered as clean
    anywhere else in `kb_setup.review`, and this is the path where that rule
    costs something — so it is pinned. (Ray's explicit trade, 2026-07-30.)
    """
    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")
    inner = _land_handler(seen)

    def handler(cmd: list[str]) -> _Proc:
        if cmd[:2] == ["git", "merge-base"]:
            seen.append(cmd)
            return _Proc(128, "", "fatal: Not a valid object name origin/main")
        return inner(cmd)

    _stub_run(monkeypatch, handler)
    assert pr.land_main(tmp_path, 42) == 1
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in seen), "must not merge"


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
# land — refuses when the local branch is ahead of the PR head (#493)
#
# `land` merges the PR HEAD, never the local branch it came from. On
# 2026-08-25 that merged a PR 10 commits behind local, then `--delete-branch`
# removed the branch holding the newer, reviewed state in the same breath.
# `_local_ahead_gap` is the question nobody asked; these tests drive it both
# through `land_main` (stubbed subprocess, for the merge-blocking property) and
# directly (real git, for the ref-resolution property no stub can exhibit).
# --------------------------------------------------------------------------


def _ahead_handler(seen: list[list[str]], *, count: str) -> Callable[[list[str]], _Proc]:
    """`_land_handler`, but the local branch EXISTS and `rev-list --count` says ``count``."""
    inner = _land_handler(seen)

    def handler(cmd: list[str]) -> _Proc:
        if cmd[:3] == ["git", "rev-parse", "--verify"]:
            seen.append(cmd)
            return _Proc(0, "1111111111222222222233333333334444444444")
        if cmd[:3] == ["git", "rev-list", "--count"]:
            seen.append(cmd)
            return _Proc(0, count)
        return inner(cmd)

    return handler


def test_land_refuses_when_local_branch_is_strictly_ahead(monkeypatch, tmp_path):
    """The regression this guard exists for: local work the merge would discard."""
    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")
    _stub_run(monkeypatch, _ahead_handler(seen, count="3"))

    assert pr.land_main(tmp_path, 42) == 1
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in seen), "must not merge"
    assert any(c[:3] == ["git", "rev-list", "--count"] for c in seen), "must actually compare"


def test_land_merges_when_local_branch_equals_pr_head(monkeypatch, tmp_path):
    """CONTROL ARM — same local branch, zero commits ahead, must still merge."""
    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")
    _stub_run(monkeypatch, _ahead_handler(seen, count="0"))

    assert pr.land_main(tmp_path, 42) == 0
    assert any(c[:3] == ["gh", "pr", "merge"] for c in seen)


def test_land_merges_when_no_local_branch_exists(monkeypatch, tmp_path):
    """State 1 — nothing local to lose, so nothing to refuse.

    `_land_handler`'s default already answers this way (rc 1, empty, on
    `rev-parse --verify`); asserted explicitly per #493's required case list
    rather than left to inference from another test's pass, and checked that
    the guard actually ran rather than merging for an unrelated reason.
    """
    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")
    _stub_run(monkeypatch, _land_handler(seen))

    assert pr.land_main(tmp_path, 42) == 0
    assert any(c[:3] == ["gh", "pr", "merge"] for c in seen)
    assert any(c[:3] == ["git", "rev-parse", "--verify"] for c in seen), (
        "the guard must actually have asked whether a local branch exists"
    )


def test_land_refuses_when_the_ahead_comparison_is_unanswerable(monkeypatch, tmp_path):
    """State 2 — the branch exists, but `rev-list` itself cannot answer.

    An unresolvable range reports rc 128, never 0 — real git does not silently
    report "0 ahead" on a broken comparison (premise-verifier M3). This must
    refuse rather than merge on the strength of an answer it never got.
    """
    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")
    inner = _land_handler(seen)

    def handler(cmd: list[str]) -> _Proc:
        if cmd[:3] == ["git", "rev-parse", "--verify"]:
            seen.append(cmd)
            return _Proc(0, "1111111111222222222233333333334444444444")
        if cmd[:3] == ["git", "rev-list", "--count"]:
            seen.append(cmd)
            return _Proc(128, "fatal: bad revision 'deadbeefcafe1234..refs/heads/feat'")
        return inner(cmd)

    _stub_run(monkeypatch, handler)
    assert pr.land_main(tmp_path, 42) == 1
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in seen), "must not merge"


def test_land_refuses_when_head_branch_name_is_unreadable(monkeypatch, tmp_path):
    """State 2, entered by the other door: `gh pr view --json headRefName` fails."""
    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")
    inner = _land_handler(seen)

    def handler(cmd: list[str]) -> _Proc:
        if cmd[:3] == ["gh", "pr", "view"] and "headRefName" in cmd:
            seen.append(cmd)
            return _Proc(1, "")
        return inner(cmd)

    _stub_run(monkeypatch, handler)
    assert pr.land_main(tmp_path, 42) == 1
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in seen), "must not merge"


# --------------------------------------------------------------------------
# _local_ahead_gap — unit level, against REAL git (#493)
#
# `_stub_run` cannot exhibit the property below: it patches `pr.subprocess.run`,
# so no real git ever runs, and a tag-shadowing test written inside it could
# only assert the ARGV shape (that `refs/heads/` appears somewhere) — a
# spelling check, not a behaviour check, which would pass against a guard that
# builds the right command and then misreads the answer. The `git` fixture
# (`tests/conftest.py`) gives a real repo instead; `pr.pr_head_branch` is
# patched as a module attribute so no `gh` is needed while git stays real —
# which is exactly why `_local_ahead_gap` calls the module-level function
# rather than inlining the `gh` call.
# --------------------------------------------------------------------------


def test_local_ahead_gap_is_not_fooled_by_a_same_named_tag(monkeypatch, git, tmp_path):
    """THE test that proves this guard is real, not decorative (#493).

    A tag sharing the head branch's name shadows the BARE form in git's own ref
    disambiguation (`refs/tags/` resolves ahead of `refs/heads/`), so
    `<base>..<name>` reports 0 even though the branch is genuinely ahead. If
    `_local_ahead_gap` ever regresses to a bare name instead of
    `refs/heads/<name>`, this is what catches it.
    """
    base = git("rev-parse", "main")
    git("checkout", "-q", "-b", "feat", "main")
    (tmp_path / "one.txt").write_text("1\n", encoding="utf-8")
    git("add", "--", "one.txt")
    git("commit", "-q", "-m", "one")
    (tmp_path / "two.txt").write_text("2\n", encoding="utf-8")
    git("add", "--", "two.txt")
    git("commit", "-q", "-m", "two")
    git("tag", "feat", "main")  # shadows the bare name at the OLD tip

    monkeypatch.setattr(pr, "pr_head_branch", lambda _n: "feat")
    gap = pr._local_ahead_gap(tmp_path, 42, base)

    assert gap is not None, "the branch IS 2 commits ahead — a bare-name bug reads this as 0"
    assert "feat" in gap
    assert "2 commit" in gap


def test_local_ahead_gap_proceeds_when_the_tagged_branch_is_not_ahead(monkeypatch, git, tmp_path):
    """CONTROL ARM — same tag-shadowing setup, but the branch tip IS the PR head."""
    tip = git("rev-parse", "main")
    git("checkout", "-q", "-b", "feat", "main")
    git("tag", "feat", "main")

    monkeypatch.setattr(pr, "pr_head_branch", lambda _n: "feat")
    assert pr._local_ahead_gap(tmp_path, 42, tip) is None


@pytest.mark.parametrize("bad_name", ["bad..name", "has space", "", "   ", "x~1"])
def test_local_ahead_gap_refuses_a_malformed_head_branch_name(monkeypatch, git, tmp_path, bad_name):
    """A `headRefName` that is not a legal ref must REFUSE, not read as absent.

    `rev-parse --verify --quiet` answers rc 1 + empty output for a malformed
    name too — indistinguishable from "branch does not exist" unless the name
    is validated FIRST (premise-verifier M14). Not tested here:
    `-weird` — `git check-ref-format` accepts it (a ref MAY start a path
    component with `-`); it is an unusual but legal branch name, and a repo
    with no such branch correctly reports state 1, not a refusal.
    """
    monkeypatch.setattr(pr, "pr_head_branch", lambda _n: bad_name)
    head = git("rev-parse", "main")
    gap = pr._local_ahead_gap(tmp_path, 42, head)
    assert gap is not None


def test_local_ahead_gap_proceeds_when_no_local_branch_exists(monkeypatch, git, tmp_path):
    """State 1, driven through the real function against a real repo lacking it."""
    monkeypatch.setattr(pr, "pr_head_branch", lambda _n: "some/branch/never/created")
    head = git("rev-parse", "main")
    assert pr._local_ahead_gap(tmp_path, 42, head) is None


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


#: The branch name and the commit at its tip, kept DISTINCT on purpose.
#:
#: `_clean_branch_handler` used to answer `"feat/x"` to every `git rev-parse`,
#: so `head_sha()` (`rev-parse HEAD`) and `current_branch()`
#: (`rev-parse --abbrev-ref HEAD`) returned the same string. That made
#: `test_ship_pushes_the_validated_sha_not_the_branch_name` unable to tell the
#: two apart: the refspec it asserts, `feat/x:refs/heads/feat/x`, is what BOTH
#: the correct code and the regression it names would produce. The test's own
#: docstring says it guards against pushing the branch name, and it could not
#: have noticed. (#59)
_BRANCH = "feat/x"
_HEAD = "c" * 40


def _clean_branch_handler(cmd: list[str]) -> _Proc:
    """A clean feature branch with an existing PR — the happy path for ship.

    The two `rev-parse` forms answer DIFFERENTLY — see :data:`_HEAD`. Order
    matters: `--abbrev-ref` must be matched before the bare form, or the bare
    prefix swallows it and both collapse back to one answer.
    """
    if cmd[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
        return _Proc(0, _BRANCH)
    if cmd[:2] == ["git", "rev-parse"]:
        return _Proc(0, _HEAD)
    if cmd[:2] == ["git", "status"]:
        return _Proc(0, "")
    if cmd[:3] == ["gh", "pr", "view"]:
        return _Proc(0, json.dumps({"number": 99, "state": "OPEN"}))
    if cmd[:2] == ["git", "merge-base"]:
        return _Proc(0, "a" * 40)
    return _Proc(0, "")


def _write_valid_receipt(tmp_path, sha: str = _HEAD) -> None:
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
        rp.write_text(f"NO FINDINGS — reviewed {sha}", encoding="utf-8")
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
    """A receipt that EXISTS but records blocking findings must still refuse.

    **Every other reason to refuse is removed first**, which is the whole
    difference between this and the version that shipped: it wrote a receipt
    claiming four lanes and no report files at all, so `_report_gaps` (then
    named `_missing_reports`)
    refused it before `_check_blocking` was ever consulted. Deleting the
    blocking check outright would have left the test green — a probe passing for
    a reason other than the one it names. (#59)

    So the reports exist, the base matches, and `blocking=1` is the ONLY
    remaining defect. `test_ship_accepts_clean_feature_branch` is the control
    arm: identical path, `blocking=0`, must return 0.
    """
    from kb_setup import review

    for lane in ("standards", "spec", "cold", "silent-failure"):
        rp = review.report_path(tmp_path, _HEAD, lane)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(f"one blocking finding — reviewed {_HEAD}", encoding="utf-8")
    review.write_receipt(
        tmp_path,
        review.Receipt(
            sha=_HEAD,
            fixed_point="main",
            fixed_point_sha="a" * 40,
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
    assert pushes[0] == ["git", "push", "origin", f"{_HEAD}:refs/heads/{_BRANCH}"]
    # The SOURCE half must be the commit, not the branch name. This is the
    # assertion the test was missing: while the stub answered "feat/x" to every
    # `rev-parse`, the expected refspec was `feat/x:refs/heads/feat/x` — which
    # the named regression produces too, so the probe could only ever pass.
    assert pushes[0][3].startswith(f"{_HEAD}:"), "must push the validated SHA, not the branch"
    assert not pushes[0][3].startswith(f"{_BRANCH}:"), "a branch name re-resolves at push time"
    # `-u` cannot set tracking from a raw-SHA refspec, so it is set separately.
    assert ["git", "branch", "--set-upstream-to", f"origin/{_BRANCH}", _BRANCH] in seen


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

    # Everything OTHER than the branch name must be a working happy path, or
    # `ship_main` returns 1 for an unrelated reason and this test passes without
    # exercising the guard. It did exactly that twice: first the receipt check
    # refused before the guard was reached, then a bare `_Proc(0, "99")` for
    # `gh pr view` failed the JSON parse and a `git merge-base` of "" failed the
    # base-coverage check. Delegating to `_clean_branch_handler` keeps every
    # other arm honest; only `rev-parse` is overridden.
    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:2] == ["git", "rev-parse"]:
            return _Proc(0, "HEAD")
        return _clean_branch_handler(cmd)

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


def test_ship_does_not_report_success_on_a_merged_pr(monkeypatch, tmp_path):
    """`gh pr view <branch>` resolves a branch to its PR regardless of STATE.

    Measured live: `gh pr view docs/clear-prep-sync --json number,state` →
    `{"number":52,"state":"MERGED"}`, rc=0. Asking only for `.number` made ship
    print `OK — PR #52 updated, gates green` and exit 0 having opened nothing.
    Reachable today — `land` deletes the remote branch and leaves the local one,
    and every PR in this repo is MERGED.
    """
    _write_valid_receipt(tmp_path)
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:3] == ["gh", "pr", "view"]:
            return _Proc(0, json.dumps({"number": 52, "state": "MERGED"}))
        return _clean_branch_handler(cmd)

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 0
    assert any(c[:3] == ["gh", "pr", "create"] for c in seen), "a merged PR needs a NEW one"


def test_ship_reports_update_only_for_an_open_pr(monkeypatch, tmp_path):
    """CONTROL ARM for the test above — an OPEN PR must still short-circuit."""
    _write_valid_receipt(tmp_path)
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        return _clean_branch_handler(cmd)

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 0
    assert not any(c[:3] == ["gh", "pr", "create"] for c in seen)


def test_ship_refuses_when_the_branch_changes_during_the_gates(monkeypatch, tmp_path):
    """Both halves of the push refspec must come from the same instant.

    Pinning `sha` post-gate while reusing the pre-gate `branch` closed one half
    of the window and left the other: a checkout during the gates would push the
    NEW branch's (separately reviewed, so passing) SHA to the OLD branch's ref.
    """
    _write_valid_receipt(tmp_path)
    seen: list[list[str]] = []
    # Exactly two `current_branch` reads: the preflight, then the pre-push
    # re-check. The second is the one that must see the checkout.
    branches = iter(["feat/x", "feat/other"])

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return _Proc(0, next(branches, "feat/other"))
        return _clean_branch_handler(cmd)

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 1
    assert not any(c[:2] == ["git", "push"] for c in seen), "must not push to a stale branch ref"


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

    # ORDERING, not mere presence. The test asserted only that a `--watch` call
    # existed somewhere in `seen`, so it would have stayed green with the wait
    # moved AFTER the read — which is precisely the regression its name forbids
    # and the only one that matters, since a verdict read before the checks
    # settle is a verdict about nothing. (#59)
    watch_at = [i for i, c in enumerate(seen) if c[:3] == ["gh", "pr", "checks"] and "--watch" in c]
    read_at = [i for i, c in enumerate(seen) if c[:3] == ["gh", "pr", "checks"] and "--json" in c]
    assert watch_at, "land must give the checks a bounded chance to settle"
    assert read_at, "land must then read the settled state"
    assert watch_at[0] < read_at[0], "the watch must precede the read, not follow it"


def test_await_terminal_expiry_proceeds_rather_than_refusing(monkeypatch):
    """Past the bound the remaining delay is a rate limit, not a review.

    Unit-level: `await_terminal` itself must return a NOTE on timeout, never
    raise. `test_land_still_merges_when_the_watch_times_out` is the half that
    drives the same timeout through `land_main`.
    """

    def boom(*_a: object, **_kw: object) -> None:
        raise subprocess.TimeoutExpired(cmd="gh", timeout=180)

    monkeypatch.setattr(pr.subprocess, "run", boom)
    note = pr.await_terminal(7, timeout=180)
    assert "quota" in note
    assert "proceeding" in note


def test_land_still_merges_when_the_watch_times_out(monkeypatch, tmp_path):
    """Expiry must not block the merge — asserted THROUGH `land_main`.

    The test above proves `await_terminal` returns a note rather than raising,
    which is a claim about one function. The claim that actually matters is
    `land`'s: "expiry is a note and never a refusal". Nothing drove a timeout
    through `land_main`, so a *caller* that treated the note as a failure would
    have gone unnoticed by a suite green on both. (#59)

    **What this is armed against, stated precisely.** It does NOT catch the
    deletion of `await_terminal`'s `except subprocess.TimeoutExpired` arm —
    measured, and the reason is worth keeping: `TimeoutExpired` subclasses
    `SubprocessError`, so the generic arm below it catches the same exception and
    also returns a note, and `land` proceeds either way. Two arms reaching one
    outcome is not a gap here, it is the safety net working.

    It IS armed against the regression it exists for: adding a refusal on a
    non-terminal note. Probed — inserting `if "reached a terminal state" not in
    note: return 1` into `land_main` turns this red and leaves the unit test
    above green, which is exactly the split that made it worth writing. Waiting
    on quota is what blocked a doc-only PR in the first place.
    """
    seen: list[list[str]] = []
    _reviewed(tmp_path, "deadbeefcafe1234")
    inner = _land_handler(seen)

    def handler(cmd: list[str]) -> _Proc:
        if cmd[:3] == ["gh", "pr", "checks"] and "--watch" in cmd:
            seen.append(cmd)
            raise subprocess.TimeoutExpired(cmd="gh", timeout=1)
        return inner(cmd)

    _stub_run(monkeypatch, handler)
    assert pr.land_main(tmp_path, 42) == 0, "a timed-out watch must not refuse the merge"
    assert any(c[:3] == ["gh", "pr", "merge"] for c in seen), "the merge must still happen"


def test_land_refuses_an_unreviewed_pr_head(monkeypatch, tmp_path):
    """CONTROL ARM: the same green PR, with no receipt for its head.

    `ship` guards only what IT pushes; a commit pushed afterwards by any other
    route reached the merge reviewed by nothing.
    """
    seen: list[list[str]] = []
    _stub_run(monkeypatch, _land_handler(seen))
    assert pr.land_main(tmp_path, 42) == 1
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in seen), "merge must not be attempted"


# --------------------------------------------------------------------------
# #66 — ship/land accept an ancestor receipt whose delta is exempt
#
# A REAL git repo (the `git`/`commit_file`/`receipt_for` fixtures in
# `conftest.py`), not the subprocess stub used above. The property under test IS
# git behaviour (ancestry, `git diff`), and the round-1 spec lane's finding was
# precisely that the only evidence `ship_main`/`land_main` honour the fallback
# was inference from an unchanged file. Inference is what a stub would repeat.
# --------------------------------------------------------------------------


def test_ship_accepts_an_ancestor_receipt_for_a_closing_commit(
    monkeypatch, tmp_path, capsys, commit_file, receipt_for
):
    """`ship` must get PAST the receipt gate when the delta is P7's own output.

    Stopped at the gates deliberately: running `lint`/`test`/`brain-audit`/`eval`
    inside a unit test is minutes of the wrong thing. What matters is WHICH
    refusal comes back — the gates', not the review's.
    """
    receipt_for(commit_file("code.py", "X = 1\n"))
    commit_file("graphify-out/memory/query_1.md", "# a lesson\n")
    monkeypatch.setattr(pr, "run_gates", lambda _root: False)

    assert pr.ship_main(tmp_path) == 1
    out = capsys.readouterr().out
    assert "ship: gates failed" in out
    assert "not pushing an unreviewed commit" not in out
    assert "covered by the receipt for" in out


def test_ship_still_refuses_a_closing_commit_that_also_touches_code(
    monkeypatch, tmp_path, capsys, commit_files, receipt_for
):
    """CONTROL ARM — the same shape with one reviewed path added must refuse.

    Without this the test above would pass just as well against a gate that
    accepted any ancestor receipt at all.
    """
    receipt_for(commit_files({"code.py": "X = 1\n"}))
    # ONE commit carrying both an exempt artifact and a reviewed path — the shape
    # the fallback must refuse.
    commit_files({"graphify-out/memory/query_1.md": "# a lesson\n", "code.py": "X = 2\n"})
    monkeypatch.setattr(pr, "run_gates", lambda _root: False)

    assert pr.ship_main(tmp_path) == 1
    out = capsys.readouterr().out
    assert "not pushing an unreviewed commit" in out
    assert "code.py" in out


def test_land_accepts_an_ancestor_receipt_for_a_closing_commit(
    monkeypatch, tmp_path, capsys, commit_file, receipt_for
):
    """`land` gates on the PR head, so it needs the same fallback as `ship`."""
    receipt_for(commit_file("code.py", "X = 1\n"))
    head = commit_file("graphify-out/memory/query_1.md", "# a lesson\n")

    # `_stub_run` patches the subprocess MODULE attribute, which `kb_setup.review`
    # shares — so a blanket stub silently answers review's git calls too, and the
    # ancestry lookup this test exists for never runs. `git` is delegated to the
    # real binary; only `gh` is stubbed.
    real_run = subprocess.run

    def handler(cmd: list[str]) -> object:
        if cmd[:3] == ["gh", "pr", "checks"]:
            return _Proc(0, json.dumps([{"name": "lint", "bucket": "pass"}]))
        if cmd[:3] == ["gh", "pr", "view"]:
            return _Proc(0, f"{head}\n")
        if cmd[:2] in (["git", "pull"], ["git", "fetch"], ["git", "checkout"]):
            # The post-merge sync needs a remote and is not what this test is about.
            return _Proc(0, "")
        if cmd and cmd[0] == "git":
            return real_run(cmd, cwd=tmp_path, capture_output=True, text=True, check=False)
        return _Proc(0, "")

    _stub_run(monkeypatch, handler)
    assert pr.land_main(tmp_path, 42) == 0
    out = capsys.readouterr().out
    assert "covered by the receipt for" in out
    assert "land: refusing" not in out


# --------------------------------------------------------------------------
# ship — the handoff for THIS branch (#149)
# --------------------------------------------------------------------------
#
# The branch match is what makes this gate safe to have at all. Measured on
# 2026-08-03: the newest handoff on disk described the session that STARTED the
# work rather than the one shipping it, so checking it unconditionally would
# have blocked a healthy PR.


def _handoff(tmp_path, branch: str, body: str) -> None:
    """Write one handoff recording ``branch``, in `kb-session-state`'s format.

    `docs/present.md` is written too, and it is not scenery. `kb_setup.resolve`
    reads a path whose FIRST SEGMENT names no directory here as a citation about
    ANOTHER repo — UNVERIFIABLE, which is advisory and does not refuse. Without a
    real `docs/` in the fixture, every `docs/gone.md` below would come back
    advisory and the refusal tests would assert a refusal that cannot happen: a
    fixture unable to exhibit the harm it targets, which is how the mutation arm
    on #144 nearly shipped as a false pass.
    """
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "present.md").write_text("x\n", encoding="utf-8")
    plans = tmp_path / ".agent" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    (plans / "session-2026-01-01.md").write_text(handoff_lead(branch, body), encoding="utf-8")


def test_ship_refuses_a_broken_handoff_for_this_branch(monkeypatch, tmp_path, capsys):
    """Criterion 3. Every OTHER reason to refuse is removed first.

    Without the receipt and the green gates this would exit 1 for a reason the
    test is not about — the failure mode `test_ship_refuses_on_blocking_review_findings`
    already paid for once.
    """
    _write_valid_receipt(tmp_path)
    _handoff(tmp_path, _BRANCH, "see `docs/gone.md`\n")
    seen: list[list[str]] = []

    def handler(cmd: list[str]) -> _Proc:
        seen.append(cmd)
        return _clean_branch_handler(cmd)

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 1
    assert not any(c[:2] == ["git", "push"] for c in seen)
    assert "docs/gone.md" in capsys.readouterr().out


def test_ship_accepts_a_clean_handoff_for_this_branch(monkeypatch, tmp_path, capsys):
    """CONTROL ARM for the refusal above — same path, a handoff that holds."""
    _write_valid_receipt(tmp_path)
    _handoff(tmp_path, _BRANCH, "see `mise.toml`\n")
    (tmp_path / "mise.toml").write_text("[tasks.lint]\nrun = 'true'\n", encoding="utf-8")
    _stub_run(monkeypatch, _clean_branch_handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 0
    assert "session-2026-01-01.md" in capsys.readouterr().out


def test_ship_is_not_blocked_by_a_broken_handoff_for_another_branch(monkeypatch, tmp_path, capsys):
    """Criterion 5 — the regression guard for the measured 2026-08-03 case.

    The only handoff on disk is BROKEN and describes another branch. Shipping
    must proceed, and must SAY it skipped (criteria 2 and 4): a gate that had
    nothing to check is not a gate that checked and found nothing.
    """
    _write_valid_receipt(tmp_path)
    _handoff(tmp_path, "some/older-branch", "see `docs/gone.md`\n")
    _stub_run(monkeypatch, _clean_branch_handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 0
    out = capsys.readouterr().out
    assert "SKIP" in out
    assert _BRANCH in out
    # The skipped handoff's own defect must not be reported as this branch's.
    assert "docs/gone.md" not in out


def test_ship_reports_the_handoff_gate_when_there_is_no_handoff_at_all(
    monkeypatch, tmp_path, capsys
):
    """Criterion 2. Silence would be indistinguishable from a pass."""
    _write_valid_receipt(tmp_path)
    _stub_run(monkeypatch, _clean_branch_handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 0
    assert "SKIP" in capsys.readouterr().out


def test_the_handoff_gate_runs_before_the_gates(monkeypatch, tmp_path):
    """A broken handoff is a cheap refusal — it must not cost four gate runs.

    Same reasoning as the receipt check, which is deliberately ahead of the
    gates. Fixing a handoff writes no commit (`.agent/` is gitignored), so
    ordering it before the gates costs nothing and invalidates nothing.
    """
    _write_valid_receipt(tmp_path)
    _handoff(tmp_path, _BRANCH, "see `docs/gone.md`\n")
    ran: list[bool] = []
    _stub_run(monkeypatch, _clean_branch_handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: ran.append(True) or True)
    assert pr.ship_main(tmp_path) == 1
    assert ran == []


def test_repowise_health_is_advisory_but_still_reported(monkeypatch):
    """A FAILING health gate must not block, and must not vanish either.

    Ray's ruling, 2026-08-17, on PR #336. The argument is different from
    CodeRabbit's and the difference is the point: CodeRabbit is advisory because
    it is usually unavailable, Repowise because of what it measures — a delta on
    a composite score, attributed by AUTHORSHIP rather than by defect
    ("AI-authored files account for the larger share of this PR's regression").
    A gate whose failure names no defect cannot be actioned, only appeased.

    Both halves are asserted because relaxing a gate has exactly one dangerous
    failure mode: relaxing it into SILENCE. The verdict is still in the summary.
    """
    rows = [
        {"name": "Repowise / code health", "bucket": "fail"},
        {"name": "lint", "bucket": "pass"},
    ]
    _stub_run(monkeypatch, lambda _cmd: _Proc(1, json.dumps(rows)))
    green, summary = pr.checks_state(336)

    assert green is True, "an advisory health gate blocked a merge"
    assert "Repowise / code health=fail" in summary
    assert "1 binding check(s) green" in summary


def test_a_binding_check_still_blocks_alongside_an_advisory_failure(monkeypatch):
    """A real failing check must still refuse, alongside an advisory one.

    CONTROL ARM for the test above: without it, that test would pass just as well
    against a gate that counted NOTHING as binding.
    """
    rows = [
        {"name": "Repowise / code health", "bucket": "fail"},
        {"name": "lint", "bucket": "fail"},
    ]
    _stub_run(monkeypatch, lambda _cmd: _Proc(1, json.dumps(rows)))
    green, summary = pr.checks_state(336)

    assert green is False
    assert "lint=fail" in summary
