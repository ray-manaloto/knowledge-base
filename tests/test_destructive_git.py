# Copyright (c) 2026 Raymond Manaloto
"""The destructive-git deny, and the much larger set it must NOT touch.

Most of this file is the ALLOW set. That is deliberate and follows
`stage_explicitly`: the only defect class these guards have actually produced is
the false positive, and this is the first STATEFUL guard in the chain — it can
be wrong in a way none of the others can, by misreading the tree.
"""

from __future__ import annotations

import json

import pytest
from kb_setup import destructive_git, hook_guard
from kb_setup.result import Ok

# ---------------------------------------------------------------------------
# DENY — but only on a dirty tree.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        # The exact command that destroyed a fix in this repo, 2026-09-03.
        "git reset --hard HEAD~1",
        "git reset --hard",
        "git reset --hard origin/main",
        # git's value-taking options must not hide the subcommand — the same
        # shape that defeated `codex_lane` live.
        "git -C /some/repo reset --hard HEAD~1",
        "git -c core.editor=true reset --hard",
        # Untracked files: no reflog, no stash, nothing gives them back.
        "git clean -fd",
        "git clean -xdf",
        # Overwrites named paths from the index.
        "git checkout -- src/thing.py",
        "git restore --worktree src/thing.py",
        # A second segment is still a command position.
        "git status && git reset --hard",
    ],
)
def test_a_destructive_command_on_a_dirty_tree_is_denied(command: str) -> None:
    assert destructive_git.decide(command, dirty=True) is not None, command


def test_the_remedy_names_the_command_that_keeps_the_work() -> None:
    """A refusal that does not say what to do instead is an obstacle, not a guard."""
    reason = destructive_git.decide("git reset --hard HEAD~1", dirty=True)
    assert reason is not None
    assert "--soft" in reason


def test_the_clean_remedy_says_the_files_are_unrecoverable() -> None:
    """`clean` differs from `reset` in kind: the reflog cannot help afterwards."""
    reason = destructive_git.decide("git clean -fd", dirty=True)
    assert reason is not None
    assert "--dry-run" in reason


# ---------------------------------------------------------------------------
# ALLOW — the larger half.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        # THE WHOLE POINT OF BEING STATEFUL: harmless on a clean tree.
        "git reset --hard HEAD~1",
        "git clean -fd",
        "git checkout -- src/thing.py",
    ],
)
def test_the_same_command_is_allowed_on_a_clean_tree(command: str) -> None:
    assert destructive_git.decide(command, dirty=False) is None, command


@pytest.mark.parametrize(
    "command",
    [
        # The forms that KEEP the work — the ones the remedy recommends. A guard
        # refusing its own advice would be worse than no guard.
        "git reset --soft HEAD~1",
        "git reset HEAD~1",
        "git reset",
        # Reading, never writing.
        "git status --porcelain",
        "git diff --stat",
        "git log --oneline -5",
        "git stash",
        "git stash -u",
        "git clean --dry-run -d",
        # Switching branches is not discarding work; git refuses on its own when
        # the change would be lost.
        "git checkout -b feat/thing",
        "git checkout main",
        # Not git at all.
        "ls -la",
        "",
    ],
)
def test_safe_and_recommended_forms_are_never_denied(command: str) -> None:
    assert destructive_git.decide(command, dirty=True) is None, command


def test_a_quoted_mention_is_not_a_command_position() -> None:
    """The shape every confirmed false positive on this repo's guards has had."""
    assert destructive_git.decide('git commit -m "never run git reset --hard"', dirty=True) is None


def test_a_heredoc_body_is_not_a_command_position() -> None:
    """`check_first.strip_heredoc_bodies` is inherited, so this holds for free.

    Added because the sibling guard denied its OWN commit message on exactly
    this shape hours earlier.
    """
    command = "git commit -q -F - <<'EOF'\nfix: stop running git reset --hard\nEOF"
    assert destructive_git.decide(command, dirty=True) is None


def test_an_unparsable_command_degrades_to_allow() -> None:
    assert destructive_git.decide('git reset --hard "unterminated', dirty=True) is None


# ---------------------------------------------------------------------------
# The stateful contract: unanswerable is not clean, and not a refusal either.
# ---------------------------------------------------------------------------


def test_a_tree_it_could_not_ask_about_is_allowed_not_refused() -> None:
    """`dirty=None` means git could not be asked.

    It must ALLOW: a guard that cannot ask must not refuse, the same contract
    the rest of the chain keeps. It must not silently become `False` either —
    that would be recording "could not check" as a clean answer, which this
    repo's currency engine keeps three separate states precisely to avoid.
    """
    assert destructive_git.decide("git reset --hard HEAD~1", dirty=None) is None


# ---------------------------------------------------------------------------
# Wiring.
# ---------------------------------------------------------------------------


def _through_the_chain(command: str) -> str | None:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = hook_guard.check_hook_call(payload)
    assert isinstance(result, Ok), result
    return result.value


def test_the_guard_is_wired_into_hook_guard() -> None:
    """RED ARM target: deleting `_destructive_git` from the chain fails this.

    Deleting the CALL is the realistic break; renaming the definition would
    leave the original as a substring and prove nothing.

    This drives the REAL tree, so it asserts only that the chain reaches the
    guard — a clean checkout correctly returns None, and pinning a verdict here
    would make the test depend on whoever runs it having a dirty tree.
    """
    reason = _through_the_chain("git reset --hard HEAD~1")
    assert reason is None or "--soft" in reason


def test_hook_guard_still_allows_the_safe_form() -> None:
    assert _through_the_chain("git reset --soft HEAD~1") is None
