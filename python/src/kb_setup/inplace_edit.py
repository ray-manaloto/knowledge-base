# Copyright (c) 2026 Raymond Manaloto
"""Deny an in-place SHELL rewrite of a Python file — the type checker cannot see it.

WHAT THE DEFECT IS, and it was measured rather than reasoned about. On
2026-09-02 a three-armed experiment settled how ty's diagnostics actually reach
a session (#671). One throwaway file, one `Literal["one"] -> int` type error,
three ways of putting it there:

===========  ==========================================  ====================
arm          how the error got in                        diagnostic delivered
===========  ==========================================  ====================
A            the **Edit tool**                           YES, immediately
B            ``perl -pi -e 's/add_one(1)/.../'``         **NO**
C            error left on disk from B, then the Edit
             tool touched an UNRELATED line               YES — the same error
===========  ==========================================  ====================

Arm C is the proof. The defect was already on disk and unreported; an Edit-tool
edit to a *different line* surfaced it. So delivery is bound to the Edit tool,
not to the file's contents and not to a file watcher — even though ty implements
``did_change_watched_files``. Control arm: ``mise run kb-check`` reported
``ty rc=1 FAIL`` throughout, so the error was real and detectable the whole time.
Only the REPORTING was missing.

The consequence is a silent-failure channel of exactly the shape
``zero-skip-policy.md`` exists to close: an in-place shell rewrite leaves
possibly-broken code with nothing saying so, until a later ``mise run lint`` or
an unrelated Edit happens to surface it.

WHY A DENY. `fable-orchestrator:fable-advisor` proposed this guard on
2026-09-02 and it was the ONE mechanism it would build (it argued explicitly
*against* a broader grep/sed -> LSP deny). The caller refused to build it at the
time, because the advisor's justification cited ``discover-plugins.md:82`` for a
claim that line does not make, and wrote: *"must not be built until someone arms
the premise."* The premise is now armed by the experiment above. This module is
that build, and not a moment earlier — the ordering is the point.

WHAT THIS GUARD CANNOT COVER, stated because a guard that names two commands
implies the rest are safe. The same hole exists for **any** write that does not
go through the Edit tool: a heredoc (``cat > f.py <<'PY'``), ``tee f.py``,
``python -c`` opening the file, ``git checkout`` restoring it, an editor. Those
are not denied — several are ordinary and useful, and a deny broad enough to
catch them would fire on writes the repo depends on. The message says so rather
than letting silence imply coverage.

IT COVERS CODEX FOR FREE. ``.codex/hooks.json`` already wires ``uv run kb-setup
hookguard`` on ``PreToolUse`` matcher ``Bash``, and ``Bash`` is a canonical codex
tool name (``hooks/index.md`` Tool coverage). So adding this to
``hook_guard.decide`` reaches both clients from one decision function, the same
sharing ``skill_lint`` already relies on (``mise-tasks-only.md`` § Enforcement
layers). That matters here more than usual: codex has no LSP client at all
(#667), so a codex lane never had the diagnostics this guard protects — which is
why the codex side also gets an explicit ``ty check`` hook (``kb_setup.edit_check``).
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from kb_setup.check_first import command_word, segments

#: Commands that rewrite a file IN PLACE and are common enough to be worth
#: naming. Deliberately short: every entry here must be a command whose whole
#: purpose in the denied form is to edit a file the model could have edited with
#: the Edit tool. `awk` is absent — GNU `awk -i inplace` exists but is rare, and
#: an unused branch is a branch nobody arms.
_IN_PLACE_COMMANDS = frozenset({"sed", "perl"})

#: A short-flag cluster carrying `i`. `sed -i`, `sed -i.bak`, `perl -pi`,
#: `perl -i.orig -pe` all match; `sed -n`, `perl -e` do not. Anchored to a
#: SINGLE leading dash so `--include=…` can never match on its `i`.
_SHORT_FLAG_WITH_I = re.compile(r"^-[A-Za-z]*i")

#: The long spelling, which GNU sed accepts and which a cluster test misses.
_LONG_IN_PLACE = frozenset({"--in-place"})

#: Extensions ty actually type-checks. A `sed -i` over markdown or TOML is
#: nobody's business here — this guard is about the type checker's blind spot,
#: not about shell edits in general.
_CHECKED_SUFFIXES = frozenset({".py", ".pyi"})

_REMEDY = (
    "Do not rewrite a Python file in place from the shell — use the Edit tool.\n"
    "\n"
    "MEASURED (#671, three arms): an error introduced by `perl -pi` produced NO ty\n"
    "diagnostic, while the SAME error surfaced the moment an Edit-tool edit touched\n"
    "an unrelated line in that file. Diagnostic delivery is bound to the Edit tool,\n"
    "not to the file's contents — so a shell rewrite leaves possibly-broken code\n"
    "with nothing saying so until a later `mise run lint`.\n"
    "\n"
    "If you genuinely need a scripted rewrite, run `mise run kb-check -- <paths>`\n"
    "immediately afterwards; that reads a real exit code and does not depend on the\n"
    "language server.\n"
    "\n"
    "SCOPE, stated so silence does not imply coverage: this guard sees `sed`/`perl`\n"
    "at a COMMAND POSITION only. All of these have the same blind spot and are NOT\n"
    "denied — a heredoc (`cat > f.py`), `tee`, a `python -c` that writes a file,\n"
    "and — confirmed by the cold lane — `find … -exec sed -i` and `xargs sed -i`,\n"
    "where the command word is `find`/`xargs` and `sed` is an argument."
)


def _is_in_place(tokens: list[str]) -> bool:
    """True when this segment's flags request an in-place edit.

    Stops at `--`: everything after it is an operand, so a filename that happens
    to look like `-i` cannot flip this on.
    """
    for flag in tokens:
        if flag == "--":
            return False
        if flag in _LONG_IN_PLACE:
            return True
        if flag.startswith("--"):
            continue
        if _SHORT_FLAG_WITH_I.match(flag):
            return True
    return False


def _checked_targets(tokens: list[str]) -> list[str]:
    """The `.py`/`.pyi` operands in this segment, if any.

    Suffix-matched rather than existence-checked on purpose. A guard that stats
    the filesystem answers "does this path exist right now", which is a
    different question from "is this command about to rewrite a Python file" —
    and `probes-need-a-control-arm.md` rule 10 records what happens when a
    "resolves to X" default is chained onto another one.
    """
    return [t for t in tokens if PurePosixPath(t).suffix in _CHECKED_SUFFIXES]


def decide(command: str) -> str | None:
    """Return the remedy when `command` rewrites a Python file in place, else None.

    Fails OPEN on anything it cannot parse, matching every other guard in this
    hook: an unparsable command is not evidence of a violation.
    """
    parsed = segments(command)
    if parsed is None:
        return None
    for tokens in parsed:
        words = command_word(tokens)
        if not words:
            continue
        if PurePosixPath(words[0]).name not in _IN_PLACE_COMMANDS:
            continue
        if not _is_in_place(words[1:]):
            continue
        targets = _checked_targets(words[1:])
        if not targets:
            continue
        return f"{_REMEDY}\n\nDenied target(s): {', '.join(targets)}"
    return None
