# Copyright (c) 2026 Raymond Manaloto
"""Deny a hand-chained lint/typecheck; redirect it to `mise run kb-check`.

Ray's ruling, 2026-08-17, and the argument is a measurement rather than a
preference. `mise run kb-check -- <paths>` exists precisely because nothing
answered *"are these two files clean?"* — `check` is whole-repo and `kb-gates`
runs the ship gates — and the vacuum was filled 35 times in one session by
pipelines that discard the gate's exit code. This round filled it **12 more
times** (`kb-session-reflect`, `gate-by-hand`), in a session that had already
used `kb-check` correctly and then drifted back mid-round.

WHY A DENY AND NOT A WARNING. This repo has the comparison, on its own
directives: the warning-only graph-first rule was complied with **0 times out of
19** in one session, while the DENY that replaced it took its own violations
**62 -> 0**. A directive that costs nothing to ignore is ignored.

WHAT THIS IS NOT. It is a REDIRECT guard, not a sandbox — `$(…)`, `sh -c` and
aliases all get through by design, exactly as `hook_guard` documents for its own
family. Precision over recall: the only measured defects in this repo's guards
have been false positives, never evasion, and a guard that misfires on
legitimate work is one people route around.

SCOPE, kept narrow on purpose:

* Only `ruff check`, `ruff format` and `ty check` — the three `kb-check` runs.
* **`pytest` is deliberately absent.** `mise-tasks-only.md` explicitly allows a
  single-test `uv run pytest tests/x.py::test_y`, and a guard contradicting the
  rule it enforces is worse than no guard.
* A command containing `mise run kb-` is allowed outright, because `kb-check`
  itself shells out to exactly these tools.
* `--version` / `--help` are introspection, not a gate — scoped to the SEGMENT
  they appear in, so another command's `--help` cannot excuse the gate beside it.

HOW IT DECIDES. The command is tokenised ONCE with `shlex` (quote-aware, with
newline moved out of `whitespace` and into `punctuation_chars`), split at shell
operators into segments, and each segment asked whether its COMMAND WORD is a
gated tool carrying a gating subcommand.

Tokenising rather than pattern-matching is what the cold review bought: a regex
sees `ruff check` inside `git commit -m "…ruff check…"` and denies it, and every
false positive found across both review rounds was that shape. After tokenising,
a quoted message is ONE token — including a MULTI-LINE one, which is why the
command is not split on newlines first. A command `shlex` cannot parse
(unbalanced quotes) falls back to the older regex, so a parse failure degrades
to the previous behaviour instead of opening a hole.

WHICH WAY IT MISSES. `_VALUE_FLAGS` lists only the `uv` options likely to sit in
front of a command word; an unlisted one makes the guard read that option's
VALUE as the command word and allow the line. That direction is chosen: this
guard is a redirect, and both review rounds found only false positives, never an
evasion. `$(…)`, `sh -c`, an alias and `{ ruff check; }` all get through for the
same reason.
"""

from __future__ import annotations

import posixpath
import re
import shlex

#: The gating subcommands each tool owns. A bare `ruff`/`ty` is NOT a gate:
#: `ruff --version` and `ruff rule E501` answer a question rather than gating.
_GATES: dict[str, frozenset[str]] = {
    "ruff": frozenset({"check", "format"}),
    "ty": frozenset({"check"}),
}

#: Wrappers that may precede the real command word without changing what it is.
_TRANSPARENT_PREFIXES = frozenset({"env", "command", "nohup", "time", "exec"})

#: Subcommands that ASK about a gate rather than running one. `ruff help check`
#: and `ty explain check` both mention a gating subcommand and neither gates.
_INTROSPECTION_SUBCOMMANDS = frozenset(
    {"help", "explain", "config", "rule", "linter", "docs", "version"}
)

#: `uv` options that take their value as a SEPARATE token, so the token after
#: them is not the command word. Only the ones plausible in front of a command
#: are listed; `uv run --help` shows ~40 more.
#:
#: An unlisted value-flag makes this guard MISS (its value is read as the
#: command word, which is not a gated tool), never produce a false positive.
#: That is the safe direction on purpose — this guard's only measured defects,
#: in both review rounds, have been false positives.
_VALUE_FLAGS = frozenset(
    {
        "--directory",
        "--project",
        "--python",
        "-p",
        "--with",
        "-w",
        "--with-editable",
        "--with-requirements",
        "--group",
        "--only-group",
        "--extra",
        "--package",
        "--index",
        "--env-file",
        "--config-file",
        "--cache-dir",
        "--color",
    }
)

#: `FOO=bar cmd …` — a leading assignment is not the command word.
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

#: Introspection that happens to be spelled with a gate's name. A version probe
#: is not a gate run, and denying it would be the false positive this guard is
#: most likely to produce. Matched per SEGMENT (see `_segment_is_a_gate`): a
#: `--help` belonging to some other command in the chain must not excuse the
#: gate beside it.
_INTROSPECTION_TOKENS = frozenset({"--version", "-V", "--help", "-h"})

#: The pre-tokenising fallback, kept ONLY for a command shlex cannot parse
#: (unbalanced quotes). Falling back to the older, looser check means a parse
#: failure degrades to the previous behaviour rather than opening a hole.
_HAND_GATE_FALLBACK = re.compile(
    r"(?:^|[;&|\n]\s*|\buv\s+run\s+)(?:\S*/)?(?:ruff\s+(?:check|format)|ty\s+check)\b"
)


def _segments(command: str) -> list[list[str]] | None:
    """Tokenise the command and split it at shell operators, None if unparsable.

    Quote-aware by construction, which is the whole point: `git commit -m "…ruff
    check…"` yields the message as ONE token, so the gate word is never at a
    command position. A regex cannot see that difference, and both of this
    guard's confirmed false positives came from it.

    A newline is taken OUT of `whitespace` and put INTO `punctuation_chars`, so
    it separates commands the way `;` does — while a newline inside a quoted
    string stays part of its token. Splitting the raw text on newlines first
    would be simpler and is wrong: it tears a multi-line commit message apart
    and hands `_segment_is_a_gate` its second line as a command. (Round 2
    finding 1; the round-1 fix introduced it.)
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return None

    segments: list[list[str]] = [[]]
    for token in tokens:
        # punctuation_chars=True emits operators as tokens of their own, made
        # up entirely of shell punctuation.
        if token and all(char in lexer.punctuation_chars for char in token):
            segments.append([])
        else:
            segments[-1].append(token)
    return segments


def _consume_flags(words: list[str], value_flags: frozenset[str] = frozenset()) -> list[str]:
    """Drop the leading options, so `words[0]` is the next command word.

    `value_flags` is passed rather than read from the module, because it is
    `uv`'s grammar and not everyone's: `-p` takes a value for `uv` and takes
    none for `time`, and a shared set silently ate `time -p ruff check`'s
    command word. Found by this round's own probe table, not by a reviewer.
    """
    index = 0
    while index < len(words) and words[index].startswith("-") and words[index] != "--":
        index += 2 if words[index] in value_flags else 1
    return words[index:]


def _command_word(tokens: list[str]) -> list[str]:
    """Strip everything in front of the real command, and return from it on."""
    words = list(tokens)
    saw_a_prefix = False
    while words:
        if _ASSIGNMENT.match(words[0]) or words[0] in _TRANSPARENT_PREFIXES:
            words.pop(0)
            saw_a_prefix = True
        elif saw_a_prefix and words[0].startswith("-"):
            # `env -i ruff check .` — the wrapper's own options.
            words = _consume_flags(words)
        else:
            break
    return words


def _segment_is_a_gate(tokens: list[str]) -> bool:
    """True when this ONE segment invokes a tool `kb-check` owns."""
    words = _command_word(tokens)
    if not words:
        return False

    if posixpath.basename(words[0]) == "uv":
        # `uv [OPTIONS] run [OPTIONS] <command> …` — options on BOTH sides of
        # `run`, which is why flags are consumed twice.
        words = _consume_flags(words[1:], _VALUE_FLAGS)
        if words[:1] != ["run"]:
            return False
        words = _consume_flags(words[1:], _VALUE_FLAGS)
        if not words:
            return False
        # Deliberately NOT a forward scan for the first ruff/ty token. That was
        # the round-1 fix and it promoted an ARGUMENT into the command position:
        # `uv run pytest -k ruff -k check` was denied, for a tool this guard
        # explicitly does not cover. (Round 2 finding 2.)

    tool = posixpath.basename(words[0])
    subcommands = _GATES.get(tool)
    if subcommands is None:
        return False
    arguments = words[1:]
    if arguments[:1] and arguments[0] in _INTROSPECTION_SUBCOMMANDS:
        return False
    # The subcommand need not be adjacent: `ruff --config ruff.toml check .`
    # is the same gate run.
    return any(word in subcommands for word in arguments)


_REASON = (
    "Do not hand-chain the gates. Use `mise run kb-check -- <paths>` — it runs "
    "ruff, format, ty AND those paths' own tests, and returns REAL exit codes "
    "with nothing in between to discard them. A hand-run chain has to be piped "
    "to be read, and a pipe returns the LAST command's status: this repo "
    "measured 35 gate invocations in one session whose failure would have been "
    "invisible. For the whole repo use `mise run lint` / `mise run test`, and "
    "for the ship gates `mise run kb-gates` (which records each result to "
    ".agent/kb/gates/). Enforced by kb_setup.check_first; Ray's ruling "
    "2026-08-17, after this directive was violated 12 times in one round."
)


def decide(command: str) -> str | None:
    """Return a deny-reason if `command` hand-runs a gate, else None.

    Public and pure, on `hook_guard.decide`'s precedent: the function that denies
    a command is the one a fixture table can grade, and a gate reaching through a
    private name is a gate that can be refactored out from under.
    """
    if not command or not command.strip():
        return None
    # A mise task legitimately shells out to these tools inside itself. Matched
    # ANYWHERE in the command rather than at the start, deliberately and for the
    # same reason `hook_guard` does it: this is a redirect, so a command that
    # already reaches for the right task is not the behaviour being corrected.
    if re.search(r"\bmise\s+run\s+kb-", command):
        return None
    segments = _segments(command)
    if segments is None:
        return _REASON if _HAND_GATE_FALLBACK.search(command) else None
    for tokens in segments:
        if not _segment_is_a_gate(tokens):
            continue
        if _INTROSPECTION_TOKENS.intersection(tokens):
            continue
        return _REASON
    return None
