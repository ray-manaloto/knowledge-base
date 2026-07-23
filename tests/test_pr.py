"""Tests for kb_setup.pr — the ship/land PR workflow.

Every test drives the real functions with subprocess stubbed, and each
assertion has a control arm: a check that can only pass is not a check
(dotfiles `.claude/rules/probes-need-a-control-arm.md`).
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
    assert "2 check(s) green" in summary


def test_checks_state_red_when_any_fails(monkeypatch):
    """CONTROL ARM for the test above — same shape, one failing bucket."""
    rows = [{"name": "CodeRabbit", "bucket": "pass"}, {"name": "lint", "bucket": "fail"}]
    _stub_run(monkeypatch, lambda _cmd: _Proc(1, json.dumps(rows)))
    green, summary = pr.checks_state(7)
    assert green is False
    assert "lint=fail" in summary


def test_checks_state_pending_is_not_green(monkeypatch):
    """`pending` means the answer is not in yet — it must never read as green."""
    rows = [{"name": "CodeRabbit", "bucket": "pending"}]
    _stub_run(monkeypatch, lambda _cmd: _Proc(0, json.dumps(rows)))
    green, _ = pr.checks_state(7)
    assert green is False


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


def test_ship_accepts_clean_feature_branch(monkeypatch, tmp_path):
    """CONTROL ARM for the two refusals above — the same path must succeed."""

    def handler(cmd: list[str]) -> _Proc:
        if cmd[:2] == ["git", "rev-parse"]:
            return _Proc(0, "feat/x")
        if cmd[:2] == ["git", "status"]:
            return _Proc(0, "")
        if cmd[:3] == ["gh", "pr", "view"]:
            return _Proc(0, "99")
        return _Proc(0, "")

    _stub_run(monkeypatch, handler)
    monkeypatch.setattr(pr, "run_gates", lambda _root: True)
    assert pr.ship_main(tmp_path) == 0


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
