# Copyright (c) 2026 Raymond Manaloto
"""Deny a git command that discards UNCOMMITTED work, when there is work to lose.

**The measurement is this session, and the author is me.** While verifying the
`codex_lane` guard I made an empty probe commit, then undid it with
`git reset --hard HEAD~1`. The probe commit was empty; the working tree was not.
`--hard` discards uncommitted changes, and it took the bypass fix I had written
minutes earlier — `git status` came back clean and the work was simply gone. It
survived only because the edit was still recoverable from the session's context.
`--soft`, or a plain `git reset`, would have done what I meant.

Ray ruled it in the same round: guard it, narrowly, **here first and port to
dotfiles later** — matching the standing precedent that a mechanism is proven in
this repo before the sibling adopts it.

**STATEFUL, WHICH IS NEW.** Every other guard in `hook_guard`'s chain decides
from the command string alone. This one asks git whether the tree is dirty,
because `git reset --hard` on a clean tree is ordinary and useful — undoing a
commit you just made, resetting to a remote. Denying that would be the
false-positive class these guards actually suffer from. So the deny fires only
when there is something to destroy.

That statefulness is the cost: it shells out to `git status --porcelain` on
matching commands only, and **fails OPEN** on any error. A guard that cannot ask
must not refuse — the same contract as the rest of the chain.

**WHAT IT DOES NOT COVER.** A redirect guard, not a sandbox: `$(…)`, `sh -c`,
`eval` and aliases get through by design (#675 is the class). And it says nothing
about committed history — `reset --hard` to an *older* commit on a clean tree is
allowed, because nothing uncommitted is lost and the reflog still holds the rest.
"""

from __future__ import annotations

import subprocess

from kb_setup import check_first

#: git's own value-taking options that may precede the subcommand. Same problem
#: `codex_lane` hit live: `git -C /some/dir reset --hard` must still be seen.
_GIT_VALUE_FLAGS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"})

#: `(subcommand, the flag that makes it destructive)`. Each entry destroys
#: UNCOMMITTED work specifically — that is the line, not "modifies the repo".
_DESTRUCTIVE = {
    "reset": frozenset({"--hard"}),
    "clean": frozenset({"-fd", "-fdx", "-xdf", "-df", "-f"}),
    "checkout": frozenset({"--", "-f", "--force"}),
    "restore": frozenset({"--worktree", "-W", "--staged"}),
}

_REMEDY = {
    "reset": (
        "`git reset --hard` DISCARDS every uncommitted change, and this tree is dirty.\n"
        "\n"
        "It is almost never what you want when undoing a commit:\n"
        "  git reset --soft HEAD~1     keep the changes, staged\n"
        "  git reset HEAD~1            keep the changes, unstaged\n"
        "\n"
        "Measured here 2026-09-03: `--hard` after an empty probe commit destroyed\n"
        "an uncommitted fix, and `git status` then read clean.\n"
        "\n"
        "If you truly mean to discard the tree, commit or stash first — then the\n"
        "reflog and the stash can both give it back."
    ),
    "clean": (
        "`git clean -fd` PERMANENTLY deletes untracked files, and this tree is dirty.\n"
        "Nothing in git can give them back — no reflog, no stash.\n"
        "\n"
        # LONG FLAGS ON PURPOSE, and the reason is worth the paragraph.
        #
        # This line first used git clean's SHORT dry-run form — `-n` and `-d`
        # joined into one token. The `typos` step read that joined token as a
        # misspelling of "and" and rewrote it, in BOTH this string and the test
        # asserting it. pytest stayed green while the remedy recommended a
        # command git rejects with `error: unknown switch 'a'`. Armed both ways
        # 2026-09-03: the joined short form exits 0 and lists what would go; the
        # rewritten one errors.
        #
        # It then corrupted THIS COMMENT the same way on the next format pass,
        # turning the sentence into "read as a misspelling of and" — the
        # explanation of the bug, rewritten by the bug. Hence no bare joined
        # token anywhere here: `--dry-run -d` and a separated `-n -d` are both
        # immune. Same class as #413, where typos rewrote short SHAs.
        "  git clean --dry-run -d      DRY RUN: list what would go\n"
        "  git stash -u                keep them, recoverably"
    ),
    "checkout": (
        "This `git checkout` form OVERWRITES uncommitted changes in the paths it\n"
        "names, and this tree is dirty.\n"
        "\n"
        "  git stash                   keep them first\n"
        "  git diff -- <path>          see what you are about to lose"
    ),
    "restore": (
        "`git restore` OVERWRITES uncommitted changes in the paths it names, and\n"
        "this tree is dirty.\n"
        "\n"
        "  git stash                   keep them first\n"
        "  git diff -- <path>          see what you are about to lose"
    ),
}


def _tree_is_dirty() -> bool | None:
    """True/False, or None when git could not be asked.

    None is NOT False: the caller must fail open on it rather than treat an
    unanswered question as a clean tree. This repo has the rule written down —
    "could not check" is never rendered as green.
    """
    try:
        done = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if done.returncode != 0:
        return None
    return bool(done.stdout.strip())


class _Ask:
    """Sentinel type for "caller did not say; go ask git"."""


#: The DEFAULT is a distinct sentinel, not `None`, and that distinction is
#: load-bearing. `None` already means something here — "git could not be asked" —
#: and the first version of this module used it for both. The result: a test
#: passing `dirty=None` to assert the fail-open path instead re-entered the ask
#: path, hit a genuinely dirty tree, and got a deny. The test was right and the
#: signature was ambiguous. Three states, three values: True, False, None.
_ASK = _Ask()


def decide(command: str, *, dirty: bool | _Ask | None = _ASK) -> str | None:
    """Return a remedy when `command` would discard uncommitted work, else None.

    `dirty` is injectable so a test can pin every state without touching a real
    repository — the guard's whole behaviour turns on it, and a test that had to
    dirty the working tree to exercise the deny would be a test nobody runs.

    `True` denies, `False` allows, `None` means git could not be asked and also
    allows, and the default sentinel means "go ask".
    """
    if not isinstance(command, str) or not command.strip():
        return None

    parsed = check_first.segments(command)
    if parsed is None:
        return None

    for tokens in parsed:
        words = check_first.command_word(tokens)
        if not words or words[0] != "git":
            continue

        rest = words[1:]
        # Skip git's own value-taking options to reach the subcommand.
        index = 0
        while index < len(rest) and rest[index].startswith("-"):
            index += 2 if rest[index] in _GIT_VALUE_FLAGS else 1
        if index >= len(rest):
            continue

        sub = rest[index]
        triggers = _DESTRUCTIVE.get(sub)
        if triggers is None:
            continue
        args = rest[index + 1 :]
        if not any(arg in triggers for arg in args):
            continue

        # Only NOW ask the expensive question, and only for a matching command.
        state = _tree_is_dirty() if isinstance(dirty, _Ask) else dirty
        if state is not True:
            # Clean tree, or git could not be asked. Both allow: a guard that
            # cannot ask must not refuse.
            continue
        return _REMEDY[sub]
    return None
