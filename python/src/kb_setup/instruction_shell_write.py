# Copyright (c) 2026 Raymond Manaloto
"""Deny a SHELL write to a budgeted instruction file (#711).

`instruction_edit_guard` (#698) registers eight `PreToolUse` handlers, every one
of them matching `Edit|Write`. So the whole Bash surface reached the same files
with no check at all, and the cold lane on `3047b2989777` rated that P1.

🔴 WHY THIS IS WORSE HERE THAN THE SAME GAP ELSEWHERE. The session harness
instructs agents to *"make file changes with sed, heredocs, or short scripts,
rather than using the dedicated Read, Edit, or Write tools."* The uncovered door
was therefore the DEFAULT one — a guard whose coverage is inversely correlated
with how the work is actually done is worth less than its green suggests. This
was measured, not inferred: `uv run python -c` wrote 401 lines into
`.claude/rules/` and landed, while identical content through the `Write` tool was
denied.

🔴 IT DENIES BY SHAPE, AND DELIBERATELY DOES NOT BUDGET. Ray ruled this on
2026-09-04 after the alternative was put to him. The reason is that of the six
bypass shapes, exactly ONE carries its content in the command: a heredoc.
`tee f.md < big.md`, `sed -i`, `perl -pi`, a `python -c` and `find … -exec` all
write bytes that do not exist until the command runs, so a budget check could
only ever cover a sixth of the surface while reading as if it covered the
surface. Refusing the shape and pointing at the `Edit`/`Write` tools — where
#698's real budget check already lives, over the real proposed content — is one
rule with no favoured shape.

A second reason, weaker but real: `check_first.segments` strips heredoc bodies
before tokenising, so even the one measurable shape would have needed the raw
command re-parsed a second way to recover its content.

🔴 SCOPE, stated so silence does not imply coverage. This guard sees:

  - a `>` / `>>` redirect whose target classifies as an instruction file;
  - `tee` at a command position with such a file among its operands;
  - `sed` / `perl` at a command position with an in-place flag and such a file
    among its operands;
  - `python -c` / `python3 -c` whose code contains BOTH an instruction path
    literal AND a write indicator.

It does NOT see, and these are not denied:

  - `find … -exec sed -i …` and `xargs sed -i`, where the command word is
    `find`/`xargs` and the target is supplied by the search rather than written
    in the command. `inplace_edit._REMEDY` documents the identical blind spot
    for `.py` and is the sibling to read.
  - `$(…)` substitution, `sh -c`, `eval`, an alias — the same by-design hole
    every guard in this family has (`mise-tasks-only.md` § the guard is a
    redirect, not a sandbox).
  - a `python -c` that names no path literal, e.g. one building the path from
    variables.

The FALLBACK IS UNCHANGED AND NOT A REGRESSION: hk's `md_size_budget` step still
sweeps every tracked instruction file and still fails the commit. What this buys
is an earlier signal on the surface #698 does not reach.

🔴 IT FAILS OPEN, matching `hook_guard`'s convention rather than
`instruction_edit_guard`'s. The inversion is deliberate and is the opposite
choice from its #698 sibling: that guard is asked "is this specific proposed
content over budget?" and a payload it cannot project is a real unknown worth
refusing. This one is asked "does this command write a protected file?", over
arbitrary shell — where an unparsable command is overwhelmingly an ordinary one,
and denying every command a tokeniser trips on would brick the Bash tool.
"""

from __future__ import annotations

import json
import posixpath
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from kb_setup import md_budget
from kb_setup.check_first import command_word, is_operator, tokenise

#: Redirect operators that TRUNCATE or APPEND. `<` is a read and never a write.
_WRITE_REDIRECTS = frozenset({">", ">>"})

#: Commands that write a file named on their own command line.
_TEE = frozenset({"tee"})
_IN_PLACE_TOOLS = frozenset({"sed", "perl"})
_PYTHON = frozenset({"python", "python3"})

#: `sed -i` (BSD form takes a suffix argument), `perl -pi`, `--in-place`.
_IN_PLACE_FLAGS = frozenset({"--in-place"})

#: A path literal inside a `python -c` program. Deliberately narrow: it must end
#: in `.md`, because that is the only extension any budget class matches, so a
#: broader pattern could only add false positives.
_PATH_LITERAL = re.compile(r"[\w./-]+\.md")

#: A write, as opposed to a read, inside that same program. Both conditions must
#: hold — a `python -c` that merely READS CLAUDE.md is a legitimate probe and
#: denying it would be exactly the false-positive direction every measured
#: defect in this guard family has come from.
_WRITE_INTENT = re.compile(r"""open\([^)]*['"][wax]|write_text|writelines|\.write\(""")


@dataclass(frozen=True)
class Verdict:
    """One decision about one Bash command."""

    deny: bool
    reason: str


SILENT = Verdict(deny=False, reason="")


def _has_in_place_flag(tokens: list[str]) -> bool:
    """True when these tokens request an in-place edit.

    Stops at `--`, so an operand that merely looks like a flag cannot flip it
    on — the same precaution `inplace_edit._is_in_place` takes, and for the same
    reason.
    """
    # Named `flag`, not `token`: ruff's S105 reads a variable called `token`
    # compared against a literal as a hardcoded credential, and a suppression
    # is not available here (`do-not.md` #9).
    for flag in tokens:
        if flag == "--":
            return False
        if flag in _IN_PLACE_FLAGS:
            return True
        if flag.startswith("-") and not flag.startswith("--") and "i" in flag[1:]:
            return True
    return False


def _redirect_targets(tokens: list[str]) -> list[str]:
    """Every token that follows a truncating or appending redirect."""
    found = []
    for index, token in enumerate(tokens[:-1]):
        if token in _WRITE_REDIRECTS and not is_operator(tokens[index + 1]):
            found.append(tokens[index + 1])
    return found


def _operands(words: list[str]) -> list[str]:
    """The non-flag words after the command, `--` honoured."""
    out = []
    seen_separator = False
    for word in words[1:]:
        if word == "--" and not seen_separator:
            seen_separator = True
            continue
        if not seen_separator and word.startswith("-"):
            continue
        out.append(word)
    return out


def _unwrap_runner(words: list[str]) -> list[str]:
    """Step past `uv run` so the real command word is first.

    `command_word` strips env assignments and transparent prefixes (`env`,
    `nohup`, …) but not `uv run`, which is a subcommand rather than a wrapper —
    `check_first._segment_is_a_gate` carries the same special case for the same
    reason. Without it every `uv run python -c …` in this repo, which is how
    python is actually invoked here, reads as a command named `uv`.

    The scan for `run` is bounded to the flags before it and stops at the first
    non-flag word, so `uv run pytest -k run` cannot have its `-k` argument
    promoted into the command position. That promotion is precisely the round-1
    defect recorded in `_segment_is_a_gate`; it is not repeated here.
    """
    if not words or posixpath.basename(words[0]) != "uv":
        return words
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 1
    if index >= len(words) or words[index] != "run":
        return words
    index += 1
    while index < len(words) and words[index].startswith("-"):
        index += 1
    return words[index:] or words


def _python_c_targets(words: list[str]) -> list[str]:
    """Path literals in a `python -c` program that also shows write intent."""
    if "-c" not in words[1:]:
        return []
    program = " ".join(words[1:])
    if not _WRITE_INTENT.search(program):
        return []
    return _PATH_LITERAL.findall(program)


def written_paths(command: str) -> list[str]:
    """Every path this command appears to WRITE. Never raises.

    Returns raw strings as written on the command line; :func:`evaluate` is what
    resolves and classifies them. Keeping the two apart is what lets the shapes
    be tested without a repository.
    """
    tokens = tokenise(command)
    if tokens is None:
        return []  # unparsable — fail open, see the module docstring

    found = _redirect_targets(tokens)

    segment: list[str] = []
    segments = [segment]
    for token in tokens:
        if is_operator(token):
            segment = []
            segments.append(segment)
        else:
            segment.append(token)

    for raw in segments:
        words = _unwrap_runner(command_word(raw))
        if not words:
            continue
        tool = posixpath.basename(words[0])
        if tool in _TEE:
            found.extend(_operands(words))
        elif tool in _IN_PLACE_TOOLS and _has_in_place_flag(words[1:]):
            # The first operand of `sed -i 's/a/b/' f.md` is the SCRIPT, not a
            # file. Classification discards it — a sed expression does not
            # resolve to a budgeted path — so no special case is needed here,
            # and adding one would be a second place to get the arity wrong.
            found.extend(_operands(words))
        elif tool in _PYTHON:
            found.extend(_python_c_targets(words))
    return found


_REMEDY = (
    "Do not write an instruction file from the shell — use the Edit or Write "
    "tool.\n"
    "\n"
    "Those tools are where the instruction-budget guard actually runs (#698): it "
    "reads the PROPOSED content, re-runs the whole md_budget sweep against it, "
    "and tells you the headroom before the bytes reach disk. A shell write "
    "reaches the same file with none of that, and the harness's own advice to "
    "prefer sed/heredocs for edits makes that the default path rather than an "
    "unusual one.\n"
    "\n"
    "This is a deny by SHAPE, not a budget check: of the shell shapes that can "
    "write these files, only a heredoc carries its content in the command, so a "
    "size check here could cover one shape while reading as if it covered all "
    "of them.\n"
    "\n"
    "SCOPE, stated so silence does not imply coverage: `find ... -exec sed -i`, "
    "`xargs sed -i`, `sh -c`, `eval` and `$(...)` are NOT denied. hk's "
    "`md_size_budget` step remains the backstop for every one of them and still "
    "fails the commit. Ray's ruling 2026-09-04; enforced by "
    "kb_setup.instruction_shell_write."
)


def evaluate(root: Path, command: str) -> Verdict:
    """Decide on one Bash command. Never raises."""
    hits = []
    for raw in written_paths(command):
        try:
            rel = (root / raw).resolve().relative_to(root.resolve()).as_posix()
        except ValueError, OSError:
            continue  # outside this repo; not ours to guard
        if md_budget.classify(rel) is not None:
            hits.append(rel)
    if not hits:
        return SILENT
    named = ", ".join(sorted(set(hits)))
    return Verdict(deny=True, reason=f"{_REMEDY}\n\nThis command writes: {named}")


def render(verdict: Verdict) -> str | None:
    """The hook's JSON response, or None when there is nothing to say."""
    if not verdict.deny:
        return None
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": verdict.reason,
            }
        }
    )


def main(root: Path, stdin_text: str | None = None) -> int:
    """Entry point for `kb-setup instruction-shell-write`.

    Always returns 0. A hook that exits non-zero on its own confusion breaks
    every Bash call in the session, which is a far larger failure than the one
    this guard prevents.
    """
    raw = sys.stdin.read() if stdin_text is None else stdin_text
    try:
        payload = json.loads(raw)
    except ValueError, TypeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return 0
    out = render(evaluate(root, command))
    if out:
        sys.stdout.write(out + "\n")
    return 0
