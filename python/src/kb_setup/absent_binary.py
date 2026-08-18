# Copyright (c) 2026 Raymond Manaloto
"""Deny a probe whose command word does not exist on this host.

Ray's ruling, 2026-08-18, quoting the transcripts back at me:

    i see this a lot in the session transcripts. we must prevent this repeated
    error from happening again:
    "timeout isn't on macOS — that probe failed for a probe reason, not a codex
    reason. Re-probing properly."

WHAT THE DEFECT ACTUALLY IS, and why it is worse than a typo. A missing binary
does not fail quietly and it does not fail honestly: the shell prints
``command not found`` and returns **127**, and that lands in a transcript looking
exactly like the thing under test failing. The measured cost here was a
near-false *"codex unavailable"* — a conclusion about a paid external service,
drawn from a probe that never ran. This is `probes-need-a-control-arm.md` rule 4
("a redirect/timeout/parse-error is not a 'no'") in its most literal form: the
probe never asked the question.

WHY A DENY AND NOT A NOTE. It has already been a note. `.agent/plans/
session-2026-08-18-b.md` § "Things that will bite you" item 3 says exactly this,
in a handoff written by the session that got bitten, and the trap is still in the
transcripts. This repo has the comparison on its own directives: the warning-only
graph-first rule was complied with **0 times out of 19** in one session, while the
DENY that replaced it took its violations **62 -> 0**. A trap that costs nothing
to walk into is walked into.

HOST-CONDITIONAL BY CONSTRUCTION. Every name below is denied only when
`shutil.which` cannot resolve it *here, now*. On a Linux host — or on this one
once someone installs coreutils — `timeout` resolves and this guard is silently
inert. That is deliberate: the finding is "this binary is absent", not "GNU is
forbidden", and a guard hardcoding the former would be a lie the moment the
environment changed. It also means the guard cannot be verified by reading it;
its control arm is `command -v <name>`, which is the very probe it allows.

SCOPE, kept narrow on the house pattern:

* Only the COMMAND WORD of a segment, tokenised by `check_first.segments` /
  `check_first.command_word` — the same tokeniser both other Bash guards use, so
  ``grep timeout f``, ``git commit -m "…timeout…"`` and ``echo timeout`` are all
  arguments and none of them is denied.
* Only names in `TRAPS`, each of which ships a REMEDY. An unresolvable command
  word that is not in the table is ALLOWED: this is a redirect guard, not a
  sandbox, and denying every name `which` cannot find would fire on shell
  functions, aliases, `$VAR` command words and anything installed mid-session.
* A probe ABOUT the binary is never denied — ``command -v timeout``,
  ``which timeout``, ``type timeout``. Those are the control arm. Denying the
  control arm for a rule about control arms would be its own worked example.

WHICH WAY IT MISSES. `$(…)`, `sh -c`, `eval`, aliases and a name reached through
a variable all get through, exactly as `hook_guard` and `check_first` document
for their own families. Precision over recall: every measured defect in this
repo's guards has been a false positive, never an evasion.
"""

from __future__ import annotations

import itertools
import posixpath
import shutil

from kb_setup import check_first

#: Commands that ASK about a binary rather than run it, UNCONDITIONALLY — the
#: name alone settles it, with no flag to inspect. Checked against the segment's
#: first raw token and against every token `command_word` strips, because an
#: introspector can sit behind a transparent prefix (``env which timeout``).
#: These are the control arm this guard's own docstring tells you to run.
_INTROSPECTORS = frozenset({"which", "type", "hash", "whence", "whereis"})

#: `command` is NOT in the set above, and that is the whole point of this one.
#: It is an execution WRAPPER — `command timeout 5 ls` runs `timeout` — and only
#: `command -v` / `command -V` asks about a name instead of running it. Listing
#: it unqualified made `command timeout 5 ls` and `env command timeout 5 ls`
#: both return None, so the absent binary ran and died with rc 127, which is the
#: exact transcript-poisoning this guard exists to prevent (cold review round 2
#: of `e42d50e51d12`, P2 — a hole opened by round 1's own fix).
_INTROSPECTOR_FLAGS = frozenset({"-v", "-V"})

#: The absent-binary traps, each with the remedy that replaces it. A name earns
#: a row by having been walked into HERE, or by being the same shape as one that
#: was; a name with no remedy to offer does not belong in a redirect guard.
TRAPS: dict[str, str] = {
    "timeout": (
        "`timeout` is GNU coreutils and is NOT on macOS — `command -v timeout` "
        "returns 1 here. Your probe would die with `command not found` (rc 127) "
        "and read in the transcript as the thing under test failing; that is how "
        "this repo nearly concluded `codex` was unavailable when it was fine. "
        "Bound the run instead with, in order of preference: (1) the Bash tool's "
        "own `timeout` parameter, which is milliseconds and is the native "
        "mechanism; (2) a mise task's `timeout` key (`task_props.timeout`) for "
        "anything recurring — see `.claude/rules/long-running-command-hangs.md`; "
        "(3) `perl -e 'alarm shift @ARGV; exec @ARGV' <seconds> <cmd> …` as a "
        "one-off, `perl` being present at /usr/bin/perl."
    ),
    "gtimeout": (
        "`gtimeout` is coreutils-from-Homebrew and is not installed here either "
        "(`command -v gtimeout` returns 1) — so it is the same failed probe as "
        "`timeout`, one substitution later. Use the Bash tool's `timeout` "
        "parameter, a mise task's `timeout` key, or "
        "`perl -e 'alarm shift @ARGV; exec @ARGV' <seconds> <cmd> …`."
    ),
    "nproc": (
        "`nproc` is GNU coreutils and is absent on macOS. Use "
        "`sysctl -n hw.ncpu`, or `os.cpu_count()` from a `kb_setup` module."
    ),
    "tac": (
        "`tac` is GNU coreutils and is absent on macOS. Use `tail -r`, or read "
        "the file in a `kb_setup` module and reverse it there."
    ),
}


def decide(command: str) -> str | None:
    """Return a deny-reason if `command` runs a known-absent binary, else None.

    Public and pure, matching `hook_guard.decide` and `check_first.decide`: the
    function that denies a command is the one a fixture table can grade.

    Unparsable input (unbalanced quotes) returns None rather than falling back to
    a regex. `check_first` keeps a fallback because its own earlier version WAS
    that regex and degrading to it opens no hole; this guard has no earlier
    version, and a regex for a bare word like `timeout` would fire inside every
    sentence that mentions one.
    """
    if not command or not command.strip():
        return None
    segs = check_first.segments(command)
    if segs is None:
        return None
    for tokens in segs:
        if not tokens:
            continue
        words = check_first.command_word(tokens)
        if not words:
            continue
        # The introspector may sit BEHIND a transparent prefix. `command` is in
        # both `_INTROSPECTORS` here and `check_first._TRANSPARENT_PREFIXES`, so
        # `env command -v timeout` resolves to the command word `timeout` while
        # `tokens[0]` is `env` — and a check on `tokens[0]` alone denied the
        # control arm this guard's own message recommends. Testing every token
        # `command_word` STRIPPED (it returns a suffix, so the prefix is
        # everything before it) covers the wrapped forms without widening to the
        # whole token list, which would let `timeout 5 which foo` escape.
        # (Cold review of c27bddf60480, P2.)
        prefix = tokens[: len(tokens) - len(words)]
        if any(posixpath.basename(t) in _INTROSPECTORS for t in (tokens[0], *prefix)):
            continue
        # `command` only introspects with -v/-V; bare `command X` RUNS X. Look at
        # the token after each `command` in the prefix rather than at the word
        # itself, so `command -v timeout` is exempt and `command timeout 5 ls`
        # is not.
        if any(
            posixpath.basename(t) == "command" and nxt in _INTROSPECTOR_FLAGS
            for t, nxt in itertools.pairwise(tokens)
        ):
            continue
        name = posixpath.basename(words[0])
        remedy = TRAPS.get(name)
        # `which` LAST, and only for a name already in the table: the lookup is
        # the expensive part and the table is the cheap filter. Ordering it the
        # other way would stat the PATH for every command word in every Bash
        # call this hook sees.
        if remedy is not None and shutil.which(name) is None:
            return (
                f"`{name}` does not exist on this host, so this probe would fail "
                f"for a PROBE reason and not for the reason you are testing. "
                f"{remedy} (kb_setup.absent_binary; Ray's ruling 2026-08-18, "
                f"after the same trap reached a handoff's gotcha list and was "
                f"walked into again.)"
            )
    return None
