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


#: Characters that END an unquoted heredoc delimiter. Everything else is part of
#: it — including `-` and `.`, which a `\w+` capture silently truncates.
#:
#: **`<` is in this set, and that membership is what makes `<<<` safe.** A
#: HERESTRING (`cmd <<<word`) takes one word on the SAME line rather than a
#: delimited body, so reading its operand as a delimiter would invent a heredoc
#: no later line can close and discard the rest of the command. `_scan_line`
#: carried an explicit `<<<` branch for this until an arm proved the branch
#: INERT: `_read_delimiter` stops immediately on the third `<`, returns None, and
#: the unreadable-delimiter path resumes scanning — the same outcome by a
#: shorter route. The branch was removed and the invariant written here instead,
#: because two mechanisms for one behaviour means a test can only ever arm one
#: of them. `test_a_herestring_consumes_nothing` covers this, and the
#: `herestring-via-delimiter-stop` arm removes `<` from this set to prove it.
_DELIMITER_STOP = frozenset(" \t;&|<>()'\"")


def _read_delimiter(line: str, i: int) -> str | None:
    r"""Read the heredoc delimiter starting at ``i``, or ``None`` to refuse one.

    Quoted (`<<'END-MSG'`, `<<"END-MSG"`, and the ANSI-C / locale forms
    `<<$'END-MSG'` and `<<$"END-MSG"`) reads to the closing quote; unquoted reads
    to the first character that cannot be part of a word.

    **REFUSING IS THE SAFE ANSWER, and every refusal below is deliberate.** A
    delimiter this function invents is one no later line can match, so the
    heredoc never closes and every command after it is discarded as body — the
    guard goes silent. Returning ``None`` instead makes `_scan_line` keep
    scanning, which at worst reads a body line as code and reports a command
    that was only ever text. A false report is answerable; a silent guard is not.

    Three refusals, all found by a cold lane running the shapes rather than
    reading them, and two of them REGRESSIONS this function introduced against
    the regex it replaced:

    - a trailing backslash CONTINUES the line, so the delimiter is not on it.
      `cat <<\\` + `EOF` recorded `\\` and swallowed the rest.
    - `$` outside the `$'…'` / `$"…"` forms means expansion, whose result we
      cannot know. `<<$VAR` is a delimiter only bash can resolve.
    - an unterminated quote has no closing quote to read to.
    """
    n = len(line)
    if i >= n:
        return None
    # `$'…'` (ANSI-C) and `$"…"` (locale): the `$` is quoting syntax, not part
    # of the delimiter. Stepping over it is what makes `<<$'END-MSG'` close.
    if line[i] == "$" and i + 1 < n and line[i + 1] in "'\"":
        i += 1
    if line[i] in "'\"":
        quote = line[i]
        end = line.find(quote, i + 1)
        return None if end == -1 else (line[i + 1 : end] or None)
    out: list[str] = []
    while i < n and line[i] not in _DELIMITER_STOP:
        if line[i] == "\\":
            if i + 1 >= n:
                return None  # continuation, not a delimiter
            out.append(line[i + 1])
            i += 2
            continue
        out.append(line[i])
        i += 1
    delimiter = "".join(out)
    if not delimiter or "$" in delimiter:
        return None
    return delimiter


def _delimiter_start(line: str, i: int) -> int:
    """Index where the delimiter begins, given `<<` starts at ``i``.

    Steps over the `-` of the `<<-` (tab-stripping) form and any whitespace
    between the operator and the word.
    """
    n = len(line)
    j = i + 2
    if j < n and line[j] == "-":
        j += 1
    while j < n and line[j] in " \t":
        j += 1
    return j


def _advance_in_quote(line: str, i: int, stack: list[str | None]) -> int:
    r"""Step one position inside a quoted word, mutating ``stack`` in place.

    Inside single quotes a backslash is literal — `'a\\'` is a complete token —
    while inside double quotes it escapes the next character, including the
    closing quote. Collapsing the two is how a scanner loses track of where a
    string ends.

    A `$(` inside DOUBLE quotes opens a FRESH quoting context: bash re-enters
    command-substitution parsing, so the inner `"` in `"$(printf "%s" x)"` opens
    a new string rather than closing the outer one. A single flat quote variable
    read that inner quote as a CLOSE, left the scanner outside any string, and
    then took a following quoted `<<EOF` for a real opener — blinding all three
    guards. Single quotes take no substitution, so this is scoped to `"`.
    """
    if line[i] == "\\" and stack[-1] == '"' and i + 1 < len(line):
        return i + 2
    if stack[-1] == '"' and line.startswith("$(", i):
        stack.append(None)
        return i + 2
    if line[i] == stack[-1]:
        stack[-1] = None
    return i + 1


def _scan_line(line: str, stack: list[str | None]) -> list[str]:
    """Return EVERY heredoc delimiter opened on ``line``, in order.

    ``stack`` is the quoting context, mutated in place so it carries to the next
    line: a shell string spans newlines, so `git commit -m 'first line` +
    `second line <<EOF'` is still inside one single-quoted token on line two.
    Its last element is the open quote (or ``None``); `$(` pushes a frame and a
    matching `)` pops one.

    A regex cannot do any of this. `<<` is only a redirection when the shell is
    not already reading a quoted word, and the implementation this replaced
    matched it anywhere, so `printf '<<EOF'` opened a heredoc that never closed.

    **A LIST, not one delimiter.** `cat <<A <<B` is valid bash and reads BOTH
    bodies, in order. Returning only the first was documented in this module as
    a conservative limit that "can only make the guard see MORE" — that claim
    was FALSE, and a cold lane disproved it by running the shape rather than
    reading the note: with A closed and B's body read as code, a `<<NEVER`
    inside B's body opened a heredoc nothing closes, and the guarded command
    after it vanished. The reassuring limit was itself a blinding path, which is
    the argument for never writing "this can only fail safely" without an arm.
    """
    found: list[str] = []
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if stack[-1] is not None:
            i = _advance_in_quote(line, i, stack)
            continue
        if ch == "\\":
            i += 2
            continue
        if line.startswith("$(", i):
            stack.append(None)
            i += 2
            continue
        if ch == ")" and len(stack) > 1:
            stack.pop()
            i += 1
            continue
        if ch in "'\"":
            stack[-1] = ch
            i += 1
            continue
        if ch == "<" and line.startswith("<<", i):
            i = _consume_opener(line, i, found)
            continue
        i += 1
    return found


def _consume_opener(line: str, i: int, found: list[str]) -> int:
    """Read one `<<` opener at ``i``, appending any delimiter; return the resume index.

    Split out of :func:`_scan_line` to keep that loop under the complexity limit
    once multiple openers per line had to be queued.

    Resumes AFTER the operator either way. An unreadable delimiter (see
    :func:`_read_delimiter`'s refusals) opens no body we can close, so scanning
    continues rather than swallowing the rest of the command.
    """
    j = _delimiter_start(line, i)
    delimiter = _read_delimiter(line, j)
    if delimiter is None:
        return j
    found.append(delimiter)
    return j + len(delimiter)


def strip_heredoc_bodies(command: str) -> str:
    r"""Remove heredoc BODIES, keeping the command line that opened them.

    A heredoc body is stdin DATA, never a command position — but `shlex` has no
    idea, so every word in it arrives as a bare token. That is a false positive
    waiting for any guard that looks for a command word.

    It did not wait: `git commit -F - <<'EOF' … codex resume --last … EOF` was
    DENIED by `codex_lane` while committing the very change that added `resume`
    to its guarded set. The `-m "…"` form is safe because the message is one
    quoted token; a heredoc body is not quoted, which is exactly the difference
    `segments`' own docstring relies on and did not extend this far.

    `check_first` and `absent_binary` share this tokeniser, so both carried the
    same latent hole — a heredoc mentioning `ruff check` or `nproc` would have
    tripped them identically. Fixed here rather than in one caller so it is
    fixed once.

    Cuts from the opener's line-end to the closing delimiter line, keeping the
    opening line itself (it holds the real command) and everything after the
    body. An unterminated heredoc drops the remainder, which is correct: there
    is no command after it, only data.

    **Both halves of the opener were wrong until 2026-09-03, and both failed in
    the direction that BLINDS the guard rather than the one that trips it.** The
    opener was `<<-?\s*['"]?(\w+)['"]?`, so:

    - `\w+` truncated the delimiter at the first `-` or `.`. `<<'END-MSG'`
      captured `END`, no later line ever equals `END`, and every command after
      the heredoc was dropped as body.
    - the match was quote-blind. `git commit -m 'see <<EOF note'` — a message
      about heredocs, which this repo writes routinely — opened a heredoc that
      never closed, with the same result.

    Both are now handled by :func:`_scan_line`, which tracks quote state instead
    of pattern-matching, and :func:`_read_delimiter`, which reads a whole word.

    KNOWN LIMIT, stated rather than left to be discovered: only the FIRST heredoc
    **`cmd <<A <<B` reads BOTH bodies, in order, and this tracks both.** An
    earlier version of this docstring called tracking only the first a
    conservative limit that "can only make the guard see MORE, never less". That
    was wrong, and a cold lane disproved it by running the shape: with only A
    tracked, B's body was read as code, a `<<NEVER` inside it opened a heredoc
    nothing closes, and the guarded command after B vanished from all three
    guards. See :func:`_scan_line`.
    """
    if "<<" not in command:
        return command
    out: list[str] = []
    pending: list[str] = []
    stack: list[str | None] = [None]
    for line in command.splitlines():
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        pending = _scan_line(line, stack)
    return "\n".join(out)


def segments(command: str) -> list[list[str]] | None:
    """Tokenise the command and split it at shell operators, None if unparsable.

    PUBLIC on `hook_guard.decide`'s precedent, and for the same reason: a second
    guard (`kb_setup.absent_binary`) needs exactly this tokenising, and a copy of
    it would drift from the one the review rounds actually hardened. One
    tokeniser, two guards.

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
    lexer = shlex.shlex(strip_heredoc_bodies(command), posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return None

    split: list[list[str]] = [[]]
    for token in tokens:
        # punctuation_chars=True emits operators as tokens of their own, made
        # up entirely of shell punctuation.
        if token and all(char in lexer.punctuation_chars for char in token):
            split.append([])
        else:
            split[-1].append(token)
    return split


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


def command_word(tokens: list[str]) -> list[str]:
    """Strip everything in front of the real command, and return from it on.

    PUBLIC for the same reason as `segments` above — `kb_setup.absent_binary`
    asks the identical question ("what is this segment actually running?") and
    must not answer it with a second implementation.

    Every branch either consumes a token or breaks, and that is a load-bearing
    property: `_consume_flags` stops AT `--` without consuming it, so before the
    separator had its own branch, `env -- ruff check .` handed it back unchanged
    and this loop never progressed again — a hang on EVERY Bash call shaped
    `<wrapper> -- …`, inside a hook that runs on all of them. (CodeRabbit on
    PR #337, confirmed live: the hook stalled to its 20 s timeout and the call
    then ran unguarded.)
    """
    words = list(tokens)
    saw_a_prefix = False
    while words:
        if _ASSIGNMENT.match(words[0]) or words[0] in _TRANSPARENT_PREFIXES:
            words.pop(0)
            saw_a_prefix = True
        elif saw_a_prefix and words[0] == "--":
            # `env -- ruff check .` — the separator ends the wrapper's own
            # options; what follows is the command. Checked BEFORE the flag
            # branch below, because `_consume_flags` cannot consume it.
            #
            # BREAK rather than continue: `--` means everything after it is the
            # command, so a command that itself starts with `-` must not be
            # mistaken for another wrapper option. Looping on kept `saw_a_prefix`
            # true and would have eaten it. (Cold lane NIT, review-2b7bd6ca.)
            words.pop(0)
            break
        elif saw_a_prefix and words[0].startswith("-"):
            # `env -i ruff check .` — the wrapper's own options.
            words = _consume_flags(words)
        else:
            break
    return words


def _segment_is_a_gate(tokens: list[str]) -> bool:
    """True when this ONE segment invokes a tool `kb-check` owns."""
    words = command_word(tokens)
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
    segs = segments(command)
    if segs is None:
        return _REASON if _HAND_GATE_FALLBACK.search(command) else None
    for tokens in segs:
        if not _segment_is_a_gate(tokens):
            continue
        if _INTROSPECTION_TOKENS.intersection(tokens):
            continue
        return _REASON
    return None
