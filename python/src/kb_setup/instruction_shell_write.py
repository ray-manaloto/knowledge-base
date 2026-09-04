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
2026-09-04 after the alternative was put to him. The reason is that most of the
bypass shapes do not carry their content: `tee f.md < big.md`, `sed -i`,
`perl -pi` and `find … -exec` all write bytes that do not exist until the command
runs. A heredoc does carry its content, and so does a `python -c` — but reading
the latter means evaluating a program, which is not something a PreToolUse guard
gets to do. So a budget check here would cover the shapes that are easiest to
measure rather than the ones that matter, while reading as if it covered the
surface. Refusing the shape and pointing at the `Edit`/`Write` tools — where
#698's real budget check already lives, over the real proposed content — is one
rule with no favoured shape.

A second reason, weaker but real: `check_first.segments` strips heredoc bodies
before tokenising, so even the one measurable shape would have needed the raw
command re-parsed a second way to recover its content.

🔴 SCOPE, stated so silence does not imply coverage. This guard sees:

  - a `>`, `>>`, `>|`, `&>` or `&>>` redirect whose target classifies as an
    instruction file — a numeric prefix (`2> f`) included, since shlex emits the
    digit as a separate token;
  - `tee` at a command position with such a file among its operands;
  - `sed` / `perl` at a command position with an in-place flag (`-i`,
    `--in-place`, `--in-place=SUFFIX`) and such a file among its operands, with
    `-f`/`-e` script arguments excluded because sed READS those;
  - `python -c` / `python3 -c` whose code contains BOTH an instruction path
    literal AND a write CALL;
  - any of the above after a `cd`, whose effect on the working directory is
    tracked across the command.

It does NOT see, and these are not denied:

  - `find … -exec sed -i …` and `xargs sed -i`, where the command word is
    `find`/`xargs` and the target is supplied by the search rather than written
    in the command. `inplace_edit._REMEDY` documents the identical blind spot
    for `.py` and is the sibling to read.
  - `$(…)` substitution, `sh -c`, `eval`, an alias — the same by-design hole
    every guard in this family has (`mise-tasks-only.md` § the guard is a
    redirect, not a sandbox).
  - a `python -c` that names no path literal, e.g. one building the path from
    variables — and, in the other direction, it CAN still fire on a path inside
    a printed string, because it text-matches a program it does not parse.
  - a `cd` whose argument is itself computed, or a `pushd`/subshell.

🔴 EVERY ITEM IN BOTH LISTS ABOVE WAS RUN, not reasoned about. Five of them are
there because the cold lane on `d3437a7059e1` ran them first and this module got
them wrong: a quoted `'>'` denied an ordinary `grep`; `&>`/`&>>`/`>|` were absent
from the redirect set; one `cd` in front of a redirect bypassed the guard
completely; a sed `-f` SCRIPT was reported as a write; and `--in-place=SUFFIX`
was missed by an equality check.

THE FALLBACK, stated more carefully than it was at first: hk's `md_size_budget`
step still sweeps every tracked instruction file — but it fails a commit only
when a file is actually OVER budget, so a bypass that stays within budget is
reported by nothing. What this guard buys is an earlier signal on the surface
#698 does not reach, not a second budget check.

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
from kb_setup.check_first import command_word, tokenise_marked

#: Redirect operators that WRITE. `<` is a read and never a write; `>|` is
#: bash's noclobber override, `&>`/`&>>` redirect both streams. All three of
#: those were missing until the cold lane on `d3437a7059e1` ran them (P1) —
#: `cat &> CLAUDE.md` is a real write and was reaching disk unremarked.
#: A numeric prefix needs no entry: shlex emits `2> f` as `2`, `>`, `f`.
_WRITE_REDIRECTS = frozenset({">", ">>", ">|", "&>", "&>>"})

#: Commands that write a file named on their own command line.
_TEE = frozenset({"tee"})
_IN_PLACE_TOOLS = frozenset({"sed", "perl"})
_PYTHON = frozenset({"python", "python3"})

#: `--in-place`, or `--in-place=SUFFIX` (GNU's single-token form, which an
#: equality check misses — cold lane P2).
_IN_PLACE_LONG = "--in-place"

#: Flags of `sed`/`perl` whose VALUE is a script or a script file, not a target.
#: Without this, `sed -i -f CLAUDE.md target.txt` reports CLAUDE.md as written
#: when it is being READ as the script (cold lane P2).
_SCRIPT_VALUE_FLAGS = frozenset({"-f", "-e", "--file", "--expression"})

#: A path literal inside a `python -c` program. Deliberately narrow: it must end
#: in `.md`, because that is the only extension any budget class matches, so a
#: broader pattern could only add false positives.
_PATH_LITERAL = re.compile(r"[\w./-]+\.md")

#: A write, as opposed to a read, inside that same program. Both conditions must
#: hold — a `python -c` that merely READS CLAUDE.md is a legitimate probe and
#: denying it would be exactly the false-positive direction every measured
#: defect in this guard family has come from.
#:
#: Every alternative requires the OPENING PAREN of a real call. Without it,
#: `print("write_text CLAUDE.md")` — prose that merely mentions the method —
#: was denied (cold lane P2). It is still a text match over a program this guard
#: does not parse, so a path inside a printed string can still trip it; see the
#: module SCOPE block.
_WRITE_INTENT = re.compile(r"""open\([^)]*['"][wax]|write_text\(|writelines\(|\.write\(""")


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
    # compared against a literal as a hardcoded credential, and a suppression is
    # not available here (`do-not.md` #9).
    for flag in tokens:
        if flag == "--":
            return False
        if flag.startswith(_IN_PLACE_LONG):
            return True
        if flag.startswith("-") and not flag.startswith("--") and "i" in flag[1:]:
            return True
    return False


def _operands(words: list[str], value_flags: frozenset[str] = frozenset()) -> list[str]:
    """The non-flag words after the command, `--` and value-taking flags honoured."""
    out = []
    seen_separator = False
    skip_next = False
    for word in words[1:]:
        if skip_next:
            skip_next = False
            continue
        if word == "--" and not seen_separator:
            seen_separator = True
            continue
        if not seen_separator and word.startswith("-"):
            if word in value_flags:
                skip_next = True
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
    defect recorded in `_segment_is_a_gate`; it is not repeated here. NOTE that
    the arms sweep showed this boundedness is currently MASKED downstream — see
    the S7 entry in `docs/research/reports/2026-09-04-711-shell-write-guard-arms.toml`.
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


def _next_cwd(cwd: str, words: list[str]) -> str:
    """Apply a `cd` to the running working directory.

    🔴 WITHOUT THIS THE GUARD IS BYPASSED BY ONE TOKEN. `cd .claude/rules &&
    cat > x.md` writes a rule file, and resolving `x.md` against the repo root
    classifies it as nothing at all. Cold lane P1, reproduced before believed.
    The inverse mattered too: a relative write after `cd /tmp` was being resolved
    back INTO the repo and wrongly denied.

    A bare `cd` goes to $HOME. It is represented as an absolute path so that
    everything after it resolves outside the repository and falls silent, which
    is the correct answer rather than a guess.
    """
    if not words or posixpath.basename(words[0]) != "cd":
        return cwd
    operands = _operands(words)
    target = operands[0] if operands else "~"
    if target.startswith(("/", "~")):
        return target
    return posixpath.normpath(posixpath.join(cwd, target))


def _resolve(cwd: str, target: str) -> str:
    """Where `target` lands, given the command's running cwd."""
    if target.startswith(("/", "~")):
        return target
    return posixpath.normpath(posixpath.join(cwd, target)) if cwd else target


def _segment_targets(words: list[str]) -> list[str]:
    """Files this ONE command writes by naming them as arguments."""
    words = _unwrap_runner(command_word(words))
    if not words:
        return []
    tool = posixpath.basename(words[0])
    if tool in _TEE:
        return _operands(words)
    if tool in _IN_PLACE_TOOLS and _has_in_place_flag(words[1:]):
        # The first bare operand of `sed -i 's/a/b/' f.md` is the SCRIPT.
        # Classification discards it — a sed expression does not resolve to a
        # budgeted path — so no arity special case is needed, only the
        # value-taking flags above, whose arguments genuinely are filenames.
        return _operands(words, _SCRIPT_VALUE_FLAGS)
    if tool in _PYTHON:
        return _python_c_targets(words)
    return []


def written_paths(command: str) -> list[str]:
    """Every path this command appears to WRITE. Never raises.

    Returns paths as they land relative to the command's own working directory;
    :func:`evaluate` resolves and classifies them. Keeping the two apart is what
    lets the shapes be tested without a repository.
    """
    marked = tokenise_marked(command)
    if marked is None:
        return []  # unparsable, or two lexers disagreed — fail open

    found: list[str] = []
    cwd = ""
    current: list[str] = []
    awaiting_target = False

    for value, is_op in marked:
        if is_op:
            if value in _WRITE_REDIRECTS:
                awaiting_target = True
                continue
            # Any other operator ends the command: settle it, and let a `cd`
            # in it move the working directory for everything that follows.
            found.extend(_resolve(cwd, t) for t in _segment_targets(current))
            cwd = _next_cwd(cwd, command_word(current))
            current = []
            awaiting_target = False
            continue
        if awaiting_target:
            found.append(_resolve(cwd, value))
            awaiting_target = False
            continue
        current.append(value)

    found.extend(_resolve(cwd, t) for t in _segment_targets(current))
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
    "This is a deny by SHAPE, not a budget check. Most shapes that write these "
    "files carry no content in the command at all (`tee f < g`, `sed -i`, "
    "`perl -pi`), so a size check here would cover whichever shapes are easiest "
    "to measure while reading as if it covered all of them.\n"
    "\n"
    "SCOPE, stated so silence does not imply coverage: `find ... -exec sed -i`, "
    "`xargs sed -i`, `sh -c`, `eval` and `$(...)` are NOT denied. For those, hk's "
    "`md_size_budget` step is the remaining check — note that it fails a commit "
    "only when the file is actually OVER budget, so a bypass that stays within "
    "budget is not reported anywhere. Ray's ruling 2026-09-04; enforced by "
    "kb_setup.instruction_shell_write."
)


def evaluate(root: Path, command: str) -> Verdict:
    """Decide on one Bash command. Never raises."""
    hits = []
    for raw in written_paths(command):
        if raw.startswith("~"):
            # $HOME, not this repository. `Path(root) / "~/CLAUDE.md"` lands
            # INSIDE the root and classifies as a nested entry point, so without
            # this a write to the user's own config would be denied here — and
            # `do-not.md` #11 says user config is not this repo's to police.
            continue
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
    # Checked here rather than relying on the matcher. `.claude/settings.json`
    # registers this on `Bash` alone, so today the check is redundant — but the
    # module is importable and the settings file is edited by hand, and a
    # payload from another tool that happens to carry a `command` field would
    # otherwise be judged as shell. Cold lane P2 on `d3437a7059e1`.
    tool = payload.get("tool_name")
    if tool is not None and tool != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return 0
    out = render(evaluate(root, command))
    if out:
        sys.stdout.write(out + "\n")
    return 0
