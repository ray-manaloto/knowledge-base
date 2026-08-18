# Copyright (c) 2026 Raymond Manaloto
"""Arms for the blanket-`git add` guard — both directions, and the false positives.

The DENY direction is easy; the ALLOW direction is where a redirect guard fails.
Every measured defect in this repo's guards has been a false positive, never an
evasion, so the allow table is the longer one on purpose.
"""

from __future__ import annotations

import pytest
from kb_setup import hook_guard, stage_explicitly
from kb_setup.result import Ok


def _verdict(payload: str) -> str | None:
    """The deny reason for one payload, narrowed positively on `Ok`."""
    result = hook_guard.check_hook_call(payload)
    return result.value if isinstance(result, Ok) else None


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("git add -A", id="the-shape-that-did-it-three-times"),
        pytest.param("git add --all", id="long-form"),
        pytest.param("git add .", id="bare-dot"),
        pytest.param("git add ./", id="dot-slash"),
        pytest.param("git add :/", id="repo-root-pathspec"),
        pytest.param("git add -A && git commit -m x", id="after-an-operator"),
        pytest.param("cd python && git add -A", id="not-at-the-start"),
        pytest.param("git add -Av", id="bundled-short-flags"),
        pytest.param("git add -vA", id="bundled-the-other-way"),
        pytest.param("git -C /repo add -A", id="a-git-option-before-the-subcommand"),
        pytest.param("/usr/bin/git add --all", id="an-absolute-path"),
        pytest.param("git status\ngit add -A", id="on-line-two-of-a-script"),
    ],
)
def test_a_blanket_add_is_denied(command: str) -> None:
    """The shape that swept derived corpus evidence into a commit three times."""
    reason = stage_explicitly.decide(command)

    assert reason is not None, f"guard missed: {command}"
    assert "Name the paths" in reason


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("git add docs/direction/2026-08-18.md", id="the-point-of-the-guard"),
        pytest.param("git add a.py b.py tests/test_a.py", id="several-named-paths"),
        pytest.param(
            "git add -u",
            id="tracked-modifications-only-CANNOT-introduce-an-untracked-path",
        ),
        pytest.param("git commit -am 'x'", id="commit--a-is-tracked-only-and-out-of-scope"),
        pytest.param("git add --patch python/src/kb_setup/pr.py", id="interactive-on-one-file"),
        pytest.param("git status --short", id="not-an-add-at-all"),
        pytest.param("git log --all", id="--all-on-a-DIFFERENT-subcommand"),
        pytest.param("git diff --all", id="--all-on-diff"),
        pytest.param("git stash list", id="ordinary-diagnostics"),
        pytest.param('git commit -m "stage everything with git add -A"', id="inside-a-message"),
        pytest.param("rg 'git add -A' .claude/", id="searching-for-the-string"),
        pytest.param("mise run kb-ship", id="the-task-that-stages-for-you"),
        pytest.param("", id="empty"),
        pytest.param("   ", id="blank"),
    ],
)
def test_legitimate_staging_is_allowed(command: str) -> None:
    """CONTROL ARM, and the longer half.

    `git add -u` is the one that matters: it stages modifications to already-
    tracked files and CANNOT introduce an untracked path, which is the entire
    failure mode this guard exists for. Denying it would make the guard refuse
    the safe alternative it recommends.
    """
    assert stage_explicitly.decide(command) is None, f"false positive: {command}"


def test_the_guard_is_wired_into_the_hook() -> None:
    """A decision function nothing calls is not a guard."""
    payload = (
        '{"tool_name": "Bash", "tool_input": {"command": "git add -A"}, '
        '"session_id": "s1", "cwd": "/tmp"}'
    )
    reason = _verdict(payload)

    assert reason is not None
    assert "Name the paths" in reason


def test_an_older_guard_still_reports_its_own_redirect() -> None:
    """ORDER ARM: this newest guard must not shadow the two before it.

    The command has to be one BOTH guards match, or the arm cannot fail — the
    mistake made on the kb-check guard's own order arm, which used a command
    only one side matched and so held whichever ran first.
    """
    assert stage_explicitly.decide("graphify label && git add -A") is not None, (
        "PRECONDITION: both guards must match, or this arm cannot detect shadowing"
    )
    payload = (
        '{"tool_name": "Bash", "tool_input": {"command": "graphify label && git add -A"}, '
        '"session_id": "s1", "cwd": "/tmp"}'
    )
    reason = _verdict(payload)

    assert reason is not None
    assert "kb-label" in reason
    assert "Name the paths" not in reason
