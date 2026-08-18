# Copyright (c) 2026 Raymond Manaloto
"""Deny a blanket `git add`; require the paths be named.

Ray's ruling 2026-08-18 ("zero tolerance on repeating mistakes"), and the
measurement is this session: `git add -A` swept derived corpus evidence under
`graphify-out/graphify-semantic-corpus-chunks/` into a commit **three times in
one session**, after the first one had been caught, amended out, and written up.
Knowing the rule did not prevent the second or the third.

WHY THAT PATH MATTERS, and why an ignore rule is not the answer. `do-not.md` #5:
nothing under `graphify-out/` is committed except `memory/`. That tree is
DELIBERATELY absent from `.gitignore`, and the comment there says why — it is
retained provider evidence for a run that cost real tokens, and whether it should
be tracked is the open question in #317. Ignoring it would settle that question
silently; committing it settles it just as silently in the other direction. The
untracked-and-visible state is the intended one, and a blanket `git add` is the
one command that destroys it without anybody deciding anything.

WHY A DENY AND NOT A WARNING. This repo has the comparison on its own directives:
the warning-only graph-first rule was complied with 0 times out of 19 in one
session, while the DENY that replaced it took its own violations 62 -> 0. A
directive that costs nothing to ignore is ignored — including by the author of
the directive, an hour after writing it.

WHAT THIS IS NOT. A redirect guard, not a sandbox: `$(…)`, `sh -c` and aliases
get through by design, exactly as `hook_guard` documents for its own family.
Precision over recall — the measured defects in this repo's guards have all been
false positives, never evasion.

SCOPE, kept narrow on purpose:

* Only `git add` with `-A`, `--all`, `--no-ignore-removal`, or a bare `.` / `:/`
  pathspec. `git add <named path>` is the whole point and is never touched.
* `git add -u` is ALLOWED. It stages modifications to already-tracked files and
  cannot introduce an untracked path, which is the entire failure mode here.
* `git commit -a` is deliberately absent for the same reason: it commits tracked
  modifications only.
"""

from __future__ import annotations

import posixpath
import re
import shlex

#: Flags that make `git add` sweep untracked files.
_BLANKET_FLAGS = frozenset({"-A", "--all", "--no-ignore-removal"})

#: Pathspecs that mean "everything from here" and so do the same thing.
_BLANKET_PATHSPECS = frozenset({".", "./", ":/", "*"})

_REASON = (
    "Do not stage with a blanket `git add`. Name the paths: "
    "`git add <path> [<path>...]`, or `git add -u` for tracked modifications "
    "only. This repo keeps `graphify-out/graphify-semantic-corpus-chunks/` "
    "UNTRACKED and deliberately out of .gitignore — it is provider evidence "
    "that cost real tokens, and whether to track it is open in #317, so a "
    "blanket add settles that question silently. Measured 2026-08-18: `git add "
    "-A` swept it into a commit THREE times in one session, the first two "
    "already caught and written up. Enforced by kb_setup.stage_explicitly; "
    "Ray's ruling, zero tolerance on repeating mistakes."
)


def decide(command: str) -> str | None:
    """Return a deny-reason if `command` stages blindly, else None.

    Public and pure on `hook_guard.decide`'s precedent: the function that denies
    a command is the one a fixture table can grade.
    """
    if not command or not command.strip():
        return None
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        # Unparsable input degrades to ALLOW rather than to a refusal nobody can
        # act on. `check_first` degrades to its older regex instead, because it
        # HAS one; there is no looser predecessor here, and a guard that refuses
        # everything it cannot parse is a guard people route around.
        return None

    segments: list[list[str]] = [[]]
    for token in tokens:
        if token and all(char in lexer.punctuation_chars for char in token):
            segments.append([])
        else:
            segments[-1].append(token)

    return _REASON if any(_is_blanket_add(segment) for segment in segments) else None


def _is_blanket_add(words: list[str]) -> bool:
    """True when this ONE segment is a `git add` that sweeps untracked files."""
    # `words[1:]` rather than a length comparison: `git` alone is not an add, and
    # the slice short-circuits before `words[0]` is touched on an empty segment.
    if not words[1:] or posixpath.basename(words[0]) != "git":
        return False
    # Skip git's own options (`-C <dir>`, `--no-pager`) to reach the subcommand.
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in {"-C", "-c", "--git-dir", "--work-tree"} else 1
    if index >= len(words) or words[index] != "add":
        return False
    arguments = words[index + 1 :]
    # `-u` WINS OVER ANY PATHSPEC. `git add -u .` updates tracked modifications
    # under the current directory and cannot introduce an untracked path, so it
    # is the safe form this guard's own message recommends — denying it was a
    # false positive of exactly the class the docstring forbids, found by the
    # cold lane on PR #339. Checked before the pathspec test, not after, because
    # the pathspec is what would otherwise convict it.
    if any(argument in {"-u", "--update"} for argument in arguments):
        return False
    if any(argument in _BLANKET_FLAGS for argument in arguments):
        return True
    # A bundled short-flag cluster: `-Av`, `-vA`. Split so `-A` is not missed
    # merely because it travelled with company.
    for argument in arguments:
        if re.fullmatch(r"-[A-Za-z]{2,}", argument) and "A" in argument[1:]:
            return True
    return any(argument in _BLANKET_PATHSPECS for argument in arguments)
