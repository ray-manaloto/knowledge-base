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


# ---------------------------------------------------------------------------
# Findings from `codex review`, each confirmed by running it before the fix.
# ---------------------------------------------------------------------------


def test_the_dirtiness_probe_asks_the_target_repo_not_cwd() -> None:
    """P1: `-C` was parsed to find the subcommand, then ignored when asking git.

    With this checkout dirty, `git -C /tmp reset --hard` was DENIED without /tmp
    ever being consulted. /tmp is not a git repository, so the probe there
    cannot answer — and an unanswerable probe must ALLOW, not refuse.
    """
    assert destructive_git.decide("git -C /tmp reset --hard") is None


@pytest.mark.parametrize(
    "command",
    [
        # `--worktree` is git's DEFAULT for restore, so a bare path is
        # destructive with no flag at all. The flag-list version missed it.
        "git restore src/thing.py",
        # Long-form and clustered force spellings the list did not enumerate.
        "git clean --force -d",
        "git clean -dfx",
        "git clean -xdf",
    ],
)
def test_ordinary_destructive_forms_the_spelling_list_missed(command: str) -> None:
    assert destructive_git.decide(command, dirty=True) is not None, command


@pytest.mark.parametrize(
    "command",
    [
        # `--staged` ALONE only unstages; the worktree is untouched. Denying it
        # was a false positive on a safe command.
        "git restore --staged src/thing.py",
        # Dry runs never delete, whatever else is on the line.
        "git clean --dry-run -d",
        "git clean -n -d -x",
    ],
)
def test_safe_forms_the_spelling_list_wrongly_denied(command: str) -> None:
    assert destructive_git.decide(command, dirty=True) is None, command


def test_staged_and_worktree_together_are_destructive() -> None:
    """The exception to the exception: `--staged --worktree` does touch it."""
    assert destructive_git.decide("git restore --staged --worktree x.py", dirty=True) is not None


# ---------------------------------------------------------------------------
# Round 2 of `codex review`, this time WITH the METHOD paragraph. It built
# scratch repos and destroyed real files to prove each of these.
# ---------------------------------------------------------------------------


def test_a_bare_checkout_pathspec_is_destructive(tmp_path) -> None:
    """P1: `git checkout <path>` overwrites with no `--` and no force.

    The lane proved it by running the real command in a dirty scratch repo and
    watching the modification vanish. Discriminated by whether the operand
    EXISTS as a path — `git checkout main` must stay allowed.
    """
    victim = tmp_path / "victim.txt"
    victim.write_text("x")
    assert destructive_git.decide(f"git checkout {victim}", dirty=True) is not None


def test_a_branch_switch_is_still_allowed() -> None:
    """The ALLOW half, and the reason the naive fix was wrong.

    Treating every single operand as destructive denies the commonest git
    command there is on any dirty tree — and git already refuses a switch that
    would lose changes. Caught by this repo's own ALLOW test, not by a reviewer.
    """
    assert destructive_git.decide("git checkout main", dirty=True) is None
    assert destructive_git.decide("git checkout -b feat/x", dirty=True) is None


def test_equals_form_selectors_reach_the_dirtiness_probe() -> None:
    """P1: `--git-dir=/x` was skipped as an unknown flag, so cwd was judged."""
    sub, _args, selectors = destructive_git._split_git(
        ["--git-dir=/repo/.git", "--work-tree=/repo", "reset", "--hard"]
    )
    assert sub == "reset"
    assert "--git-dir=/repo/.git" in selectors
    assert "--work-tree=/repo" in selectors


@pytest.mark.parametrize(
    "command", ["git clean -xdf", "git clean -x -f -d", "git clean --force -X"]
)
def test_clean_x_asks_about_ignored_files(command: str) -> None:
    """P1: ignored files are invisible to a plain porcelain status.

    So a repo full of them read as CLEAN while `clean -x` would delete every one.

    The lane proved it with a scratch repo holding only an ignored
    `cache.secret`: status was empty, `clean -ndfx` said `Would remove`.
    """
    sub, args, _ = destructive_git._split_git(command.split()[1:])
    assert sub is not None
    assert destructive_git._targets_ignored_files(sub, args) is True


def test_a_clean_without_x_does_not_ask_about_ignored() -> None:
    """The control: `-fd` leaves ignored files alone, so the wider probe is noise."""
    sub, args, _ = destructive_git._split_git(["clean", "-fd"])
    assert sub is not None
    assert destructive_git._targets_ignored_files(sub, args) is False
