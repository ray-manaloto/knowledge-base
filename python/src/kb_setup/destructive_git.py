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
from pathlib import Path

from kb_setup import check_first

#: git's own value-taking options that may precede the subcommand. Same problem
#: `codex_lane` hit live: `git -C /some/dir reset --hard` must still be seen.
_GIT_VALUE_FLAGS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"})

#: The subset of `_GIT_VALUE_FLAGS` that selects WHICH repository or worktree the
#: command acts on. These must be forwarded to the dirtiness probe; the others
#: (`-c`, `--exec-path`) change behaviour but not the target.
_GIT_TARGET_FLAGS = frozenset({"-C", "--git-dir", "--work-tree", "--namespace"})

#: `(subcommand, what makes it destructive)`. Each entry destroys UNCOMMITTED
#: work specifically — that is the line, not "modifies the repo".
#:
#: 🔴 THE FIRST VERSION ENUMERATED SPELLINGS AND THAT WAS THE WRONG SHAPE, found
#: by `codex review`. Three concrete misses, all ordinary usage:
#:   - `git restore <path>` is destructive with NO flag at all — `--worktree` is
#:     git's documented DEFAULT (`git restore --help`). The flag list required a
#:     flag, so the commonest destructive form sailed through.
#:   - `git clean --force -d` and `git clean -dfx` are valid and were missed,
#:     because only a handful of joined spellings were listed.
#:   - `git restore --staged <path>` was DENIED although it only unstages and
#:     leaves the worktree intact — a false positive on a safe command.
#:
#: So `clean` and `restore` are now decided by a predicate over the whole
#: argument list rather than by membership in a spelling set.
_DESTRUCTIVE_FLAGS = {
    "reset": frozenset({"--hard"}),
}

#: Branch-shaped `checkout` operands that do NOT overwrite the worktree. Anything
#: else given to `checkout` is a PATHSPEC, and a pathspec overwrites.
_CHECKOUT_BRANCH_FLAGS = frozenset({"-b", "-B", "--orphan", "--track", "-t", "--detach"})

#: `git checkout <tree-ish> <path>` — at this many operands it can only be a
#: path overwrite, never a branch switch.
_CHECKOUT_TREEISH_AND_PATH = 2


def _checkout_is_destructive(args: list[str]) -> bool:
    """`git checkout <path>` overwrites that path — no `--` and no force needed.

    🔴 The flag table required `--`, `-f` or `--force`. `codex review` disproved
    it the expensive way: in an isolated dirty repository it ran
    `decide("git checkout victim.txt")`, got ALLOW, then ran the real command and
    watched the modification disappear, leaving a clean porcelain status.

    Branch switching is not destructive — git refuses on its own when a switch
    would lose changes — so the discriminator is whether an operand is present
    that is not a branch-creating flag.
    """
    if any(a in {"-f", "--force", "--"} for a in args):
        return True
    if any(a in _CHECKOUT_BRANCH_FLAGS for a in args):
        return False
    operands = [a for a in args if not a.startswith("-")]
    if not operands:
        return False
    # `checkout <tree-ish> <path>` — two or more operands is always a path
    # overwrite.
    if len(operands) >= _CHECKOUT_TREEISH_AND_PATH:
        return True
    # ONE operand is ambiguous by syntax: `git checkout main` switches branch,
    # `git checkout victim.txt` overwrites a file. Treating every single operand
    # as destructive was tried and is the wrong trade — it denies the commonest
    # git command there is, on any dirty tree, and git ALREADY refuses a branch
    # switch that would lose changes. My own ALLOW test caught it.
    #
    # So ask the filesystem. A path that exists is a pathspec; anything else is
    # a ref. The collision — a branch and a file sharing a name — resolves
    # toward destructive, which is the right way for an ambiguity about
    # overwriting to fall.
    return Path(operands[0]).exists()


def _clean_is_destructive(args: list[str]) -> bool:
    """`git clean` deletes only with force; `-n`/`--dry-run` makes it safe."""
    if any(a in {"-n", "--dry-run"} for a in args):
        return False
    if "--force" in args:
        return True
    # Short clusters: -f, -fd, -dfx, -xdf … force is the `f` anywhere in a
    # single-dash cluster of short flags.
    return any(
        a.startswith("-") and not a.startswith("--") and "f" in a[1:] and a[1:].isalpha()
        for a in args
    )


def _restore_is_destructive(args: list[str]) -> bool:
    """`--worktree` is git's DEFAULT, so a bare `git restore <path>` overwrites.

    `--staged` ALONE only unstages and is safe; `--staged --worktree` together
    do touch the worktree and are not.
    """
    staged = any(a in {"-S", "--staged"} for a in args)
    worktree = any(a in {"-W", "--worktree"} for a in args)
    return not (staged and not worktree)


def _split_git(rest: list[str]) -> tuple[str | None, list[str], list[str]]:
    """`(subcommand, its args, the target-selection options)`.

    Walks git's own value-taking options to reach the subcommand, KEEPING the
    ones that choose a repository so the dirtiness probe can ask the right one.
    Split out of `decide` to keep that function under the complexity gate rather
    than raising the gate — the same trade `use-tool-builtins.md` asks for.
    """
    index = 0
    selectors: list[str] = []
    while index < len(rest) and rest[index].startswith("-"):
        token = rest[index]
        # 🔴 EQUALS FORM. `--git-dir=/repo/.git` and `--work-tree=/repo` are
        # valid and were skipped as unknown flags, so the dirtiness probe went on
        # asking cwd. `codex review` proved it from a clean scratch repo: a reset
        # targeting another DIRTY repository through equals-form selectors was
        # ALLOWED, while the same selectors handed to `git status --porcelain`
        # reported `M base` in the real target.
        head = token.split("=", 1)[0]
        if "=" in token and head in _GIT_TARGET_FLAGS:
            selectors.append(token)
            index += 1
        elif token in _GIT_VALUE_FLAGS:
            if token in _GIT_TARGET_FLAGS and index + 1 < len(rest):
                selectors += [token, rest[index + 1]]
            index += 2
        else:
            index += 1
    if index >= len(rest):
        return None, [], selectors
    return rest[index], rest[index + 1 :], selectors


def _is_destructive(sub: str, args: list[str]) -> bool:
    """Does this subcommand, with these args, destroy uncommitted work?"""
    if sub == "clean":
        return _clean_is_destructive(args)
    if sub == "restore":
        return _restore_is_destructive(args)
    if sub == "checkout":
        return _checkout_is_destructive(args)
    if sub in _DESTRUCTIVE_FLAGS:
        return any(arg in _DESTRUCTIVE_FLAGS[sub] for arg in args)
    return False


def _targets_ignored_files(sub: str, args: list[str]) -> bool:
    """Does this command reach IGNORED files, which plain `status` cannot see?

    Only `git clean -x`/`-X` does. Without this the dirtiness probe reports a
    clean tree over a directory full of ignored data and the guard allows its
    permanent deletion.
    """
    if sub != "clean":
        return False
    return any(
        a in {"-x", "-X"}
        or (a.startswith("-") and not a.startswith("--") and ("x" in a[1:] or "X" in a[1:]))
        for a in args
    )


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


def _tree_is_dirty(selectors: list[str] | None = None, *, ignored: bool = False) -> bool | None:
    """True/False, or None when git could not be asked.

    None is NOT False: the caller must fail open on it rather than treat an
    unanswered question as a clean tree. This repo has the rule written down —
    "could not check" is never rendered as green.

    🔴 `selectors` CARRIES THE TARGET-SELECTION OPTIONS THROUGH, and the first
    version did not. It parsed PAST `-C`, `--git-dir` and `--work-tree` to reach
    the subcommand, then ran `git status` in the hook process's OWN directory —
    so `git -C /other/repo reset --hard` was judged against this checkout. Wrong
    in both directions: a clean cwd would allow a destructive command in a dirty
    repo, and a dirty cwd denies a safe one elsewhere. Found by `codex review`,
    then confirmed by running it — with this tree dirty, `git -C /tmp reset
    --hard` was DENIED without /tmp ever being consulted.

    🔴 `ignored=True` ADDS `--ignored`, and without it `git clean -x` slipped
    through. `codex review` built a scratch repo holding only an IGNORED
    `cache.secret`: `git status --porcelain` exited 0 with EMPTY output — a clean
    tree by this probe — while `git clean -ndfx` reported `Would remove
    cache.secret`. So the guard allowed permanent deletion of data it could not
    see. `-x`/`-X` are exactly the flags that make ignored files the target, so
    the probe has to be told to look at them.
    """
    status = ["status", "--porcelain"]
    if ignored:
        status.append("--ignored")
    try:
        done = subprocess.run(
            ["git", *(selectors or []), *status],
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

        sub, args, selectors = _split_git(words[1:])
        if sub is None or not _is_destructive(sub, args):
            continue

        # Only NOW ask the expensive question, and only for a matching command —
        # of the repository the command TARGETS, not cwd, and including ignored
        # files when the command is one that deletes them.
        state = (
            _tree_is_dirty(selectors, ignored=_targets_ignored_files(sub, args))
            if isinstance(dirty, _Ask)
            else dirty
        )
        if state is not True:
            # Clean tree, or git could not be asked. Both allow: a guard that
            # cannot ask must not refuse.
            continue
        return _REMEDY[sub]
    return None
