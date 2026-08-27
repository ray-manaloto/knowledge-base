# Copyright (c) 2026 Raymond Manaloto
"""Deny a probe whose command word cannot actually be RUN on this host.

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

RE-ARMED 2026-08-26 — the first version of this guard was silently defeated by
its own fix target. A `mise` reshim wrote a shim FILE for `timeout`/`nproc`/`tac`
(and `git`, and 833 others) on this machine, so `shutil.which` started resolving
them — but no version was ever set for the tool behind those shims, so actually
running one prints `mise ERROR No version is set for shim: <name>` and exits
**1**. `shutil.which(name) is None` went from "true whenever the trap applies"
to "true for gtimeout only", because it answers "does a file exist at this
name", not "would running this name work" — and those stopped being the same
question the moment a shim could exist without a version behind it. The
signature that used to separate *the probe never ran* from *the thing under
test failed* (rc 127 vs. anything else) was exactly what went missing, on the
exact guard built to preserve that distinction.

TWO CANDIDATE FIXES, AND WHY ONE WAS REJECTED. The natural first instinct is to
ask mise directly — `mise which <name>` is documented for precisely this
("Shows the path that a tool's bin points to... figure out what version of a
tool is currently active"). It was probed and **rejected**: `mise which git`
reports `git is a mise bin however it is not currently active` — the same
"inactive" verdict `mise which timeout` gives — and yet running `git --version`
through the very same shim SUCCEEDS (it falls back to a real git found later on
PATH; not every mise-shimmed tool has that fallback, and mise's CLI does not
expose which ones do). Trusting `mise which`'s verdict would have produced a
false DENY on a binary that actually works, on the strength of an error string
whose meaning depends on shim internals this guard has no visibility into. Per
`probes-need-a-control-arm.md`'s cross-check rule: two probes disagreed (`mise
which` vs. actually running it), and the actual run is ground truth by
definition — it does not report on execution, it IS the execution. So this
guard now asks the ONLY question that cannot be wrong about itself: it actually
invokes the resolved binary (`<path> --version`, stdin closed, output
discarded, wall-clock bounded) and reads whether that succeeded. See
`_probe_runs` for the mechanics.

WHY THE COST IS ACCEPTABLE WITHOUT A CACHE. This runs inside a PreToolUse hook
on every Bash call — `.claude/settings.json` wires `uv run --project python
kb-setup hookguard` to `Bash|Grep`, a FRESH interpreter per call, so an
in-process cache (`functools.lru_cache` and the like) would not survive between
hook invocations and a file-based cache would trade a measured ~100ms for
staleness risk on a signal that should track the live host. Neither is needed
because the added subprocess is not on the path every call pays: it only runs
when a command word is BOTH one of the four curated `TRAPS` names AND already
resolved by `shutil.which` — the same narrowing the pre-existing `which` call
already relied on ("the lookup is the expensive part and the table is the
cheap filter... Ordering it the other way would stat the PATH for every command
word in every Bash call this hook sees"). Typing `timeout`/`gtimeout`/`nproc`/
`tac` as a command word is rare by construction — it is the exact event this
guard exists to catch — so the ~100ms measured for one `subprocess.run(...,
timeout=2)` call (see the module's commit message / PR for the number) is paid
on an already-rare path, not smeared across the session.

STILL HOST-CONDITIONAL BY CONSTRUCTION, one layer deeper than before. The old
version went inert the moment `shutil.which` resolved a name; this version goes
inert the moment the resolved binary ACTUALLY RUNS `--version` successfully —
whether that is because coreutils was installed properly, because mise's shim
fallback found a real binary, or because the OS ships the tool natively. No
future code change is needed for the guard to recognise a fixed host: fixing
the mise config (the owner's call, out of scope for this change — see
`.claude/rules/do-not.md` #11) makes the probe succeed and the guard silently
inert, exactly as the file-existence check used to.

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
repo's guards has been a false positive, never an evasion. The new probe adds
one more way to miss, on purpose: a `TimeoutExpired` (never observed for any
`TRAPS` entry on a working OR broken host — see `_probe_runs`) is treated as
"assume it runs" rather than denied, because a guard denying on a signal it
cannot explain would be inventing a false positive rather than reporting one.
"""

from __future__ import annotations

import itertools
import posixpath
import shutil
import subprocess
from typing import NamedTuple

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
#:
#: Deliberately silent on whether a name currently resolves or runs — that is
#: `decide`'s job, computed fresh every call. An entry that embedded a claim
#: like "returns 1 here" would go stale the moment the host changed (it did:
#: `command -v timeout` returned 1 before the 2026-08-26 reshim and returns 0
#: after), and a stale claim glued next to a freshly-computed one would
#: contradict it inside the SAME message.
#:
#: SAFETY NOTE for anyone adding a fifth entry: `_probe_runs` executes
#: `<name> --version`. That is safe only because every current entry is a
#: GNU-coreutils-style tool for which `--version` is standard and side-effect
#: free (GNU Coding Standards). A binary where `--version` is unsafe, undefined,
#: or blocking on stdin does not belong in this table without also reworking
#: `_probe_runs`'s invocation.
TRAPS: dict[str, str] = {
    "timeout": (
        "GNU coreutils' `timeout` is not part of the base macOS toolchain. "
        "Bound the run instead with, in order of preference: (1) the Bash "
        "tool's own `timeout` parameter, which is milliseconds and is the "
        "native mechanism; (2) a mise task's `timeout` key "
        "(`task_props.timeout`) for anything recurring — see "
        "`.claude/rules/long-running-command-hangs.md`; (3) "
        "`perl -e 'alarm shift @ARGV; exec @ARGV' <seconds> <cmd> …` as a "
        "one-off, `perl` being present at /usr/bin/perl."
    ),
    "gtimeout": (
        "GNU coreutils' `gtimeout` (the Homebrew spelling) is the same trap "
        "as `timeout` above, one substitution later. Use the Bash tool's "
        "`timeout` parameter, a mise task's `timeout` key, or "
        "`perl -e 'alarm shift @ARGV; exec @ARGV' <seconds> <cmd> …`."
    ),
    "nproc": (
        "GNU coreutils' `nproc` is not part of the base macOS toolchain. Use "
        "`sysctl -n hw.ncpu`, or `os.cpu_count()` from a `kb_setup` module."
    ),
    "tac": (
        "GNU coreutils' `tac` is not part of the base macOS toolchain. Use "
        "`tail -r`, or read the file in a `kb_setup` module and reverse it "
        "there."
    ),
}

#: Wall-clock bound on `_probe_runs`'s subprocess, in seconds. Protects the
#: HOOK, not the probe result: every `TRAPS` entry is a GNU-coreutils-style
#: tool whose `--version` returns in well under a second whether it succeeds
#: (a working binary) or fails (a broken mise shim errors immediately — see
#: `_probe_runs`'s docstring, this was measured, not assumed). A timeout here
#: means something this guard has no theory for, and it fails OPEN rather than
#: invent a deny reason it cannot explain.
_PROBE_TIMEOUT_S = 2.0


class _Probe(NamedTuple):
    """The outcome of actually invoking a resolved binary — see `_probe_runs`."""

    #: True if the invocation is evidence the binary works (rc 0, or the probe
    #: was inconclusive and this guard chose to fail open on it).
    ok: bool
    #: The process's real exit code, or None when it never produced one
    #: (timed out, or the exec itself raised).
    returncode: int | None
    #: One line for the deny message: the probe's first stderr line, an
    #: OSError's text, or "" when there is nothing more useful to add.
    detail: str


def _probe_runs(path: str) -> _Probe:
    """Actually invoke ``<path> --version`` and report whether it worked.

    This is the seam a test replaces (`monkeypatch.setattr(absent_binary,
    "_probe_runs", fake)`) — the same pattern `shutil.which` already uses one
    layer up — because the real subprocess call must never run inside a test
    that is asserting about a HOST STATE the test does not control (see the
    module docstring's "WHY THE COST IS ACCEPTABLE" and
    `tests/test_absent_binary.py`'s own opening docstring on the same point).

    Runs `<path> --version` with stdin closed (never wait on input — `tac`
    reads stdin with no file argument, and this must never be that invocation),
    stdout discarded, and stderr captured for the deny message. Chose to invoke
    the RESOLVED PATH rather than the bare name: `shutil.which` already did the
    PATH search a moment earlier, and invoking the exact file it found removes
    any chance the two disagree if PATH is mutated between the two calls
    (unlikely inside one hook invocation, but the resolved path is available
    for free and removes the question).

    `TimeoutExpired` is treated as evidence the binary DOES work (`ok=True`).
    This was never observed for any `TRAPS` entry — a working coreutils
    `--version` returns near-instantly, and the broken-mise-shim failure this
    guard exists to catch also fails near-instantly (measured: it errors, it
    does not hang) — so this branch exists as a bound on the hook's own
    worst case, not as a signal this guard has a theory about. Denying on an
    unexplained hang would be manufacturing a false positive, which is the
    one failure class this guard family has never had and is not going to
    introduce here.

    `OSError` (the path vanished, lost its execute bit, or an exec-format
    mismatch between `which`'s stat and the actual exec) is `ok=False`: unlike
    the timeout case, an OSError IS a clear answer to "would this probe run",
    just not the one `shutil.which` implied a moment ago.
    """
    try:
        result = subprocess.run(
            [path, "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=_PROBE_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _Probe(ok=True, returncode=None, detail="probe timed out")
    except OSError as exc:
        return _Probe(ok=False, returncode=None, detail=str(exc))
    if result.returncode == 0:
        return _Probe(ok=True, returncode=0, detail="")
    stderr = result.stderr.decode("utf-8", "replace").strip()
    first_line = stderr.splitlines()[0] if stderr else ""
    return _Probe(ok=False, returncode=result.returncode, detail=first_line)


def _deny_absent(name: str, remedy: str) -> str:
    """The message for a name `shutil.which` cannot resolve at all — rc 127."""
    return (
        f"`{name}` does not exist on this host, so this probe would fail "
        f"for a PROBE reason and not for the reason you are testing — the "
        f"shell would print `command not found` and exit **127**. "
        f"{remedy} (kb_setup.absent_binary; Ray's ruling 2026-08-18, "
        f"after the same trap reached a handoff's gotcha list and was "
        f"walked into again.)"
    )


def _deny_broken(name: str, remedy: str, path: str, probe: _Probe) -> str:
    """The message for a name that resolves but does not actually run.

    A DIFFERENT rc than `_deny_absent` — stated explicitly, because it is no
    longer 127 and a reader who has this guard's old shape memorised would
    otherwise expect the classic "command not found".
    """
    rc = probe.returncode if probe.returncode is not None else "?"
    detail = f" — `{probe.detail}`" if probe.detail else ""
    return (
        f"`{name}` resolves to `{path}` on this host, but running it does not "
        f"work: `{name} --version` exits **{rc}**{detail}. This is a newer, "
        f"more confusing failure shape than the classic `command not found` "
        f"(rc 127) the absent case gives — the name resolves to a real file, "
        f"but the file does not run — and this probe would still fail for a "
        f"PROBE reason and not for the reason you are testing. "
        f"{remedy} (kb_setup.absent_binary; re-armed 2026-08-26 after a mise "
        f"reshim gave this trap a file that resolves but will not run.)"
    )


def _is_introspection(tokens: list[str], prefix: list[str]) -> bool:
    """True if `tokens` only ASKS about the command word rather than running it.

    Split out of `_decide_for_segment` to keep that function's return count
    under the house limit — this is the same two checks it always was, just
    named so the caller reads as one guard clause instead of two.
    """
    # The introspector may sit BEHIND a transparent prefix. `command` is in
    # both `_INTROSPECTORS` here and `check_first._TRANSPARENT_PREFIXES`, so
    # `env command -v timeout` resolves to the command word `timeout` while
    # `tokens[0]` is `env` — and a check on `tokens[0]` alone denied the
    # control arm this guard's own message recommends. Testing every token
    # `command_word` STRIPPED (it returns a suffix, so the prefix is
    # everything before it) covers the wrapped forms without widening to the
    # whole token list, which would let `timeout 5 which foo` escape.
    # (Cold review of c27bddf60480, P2.)
    if any(posixpath.basename(t) in _INTROSPECTORS for t in (tokens[0], *prefix)):
        return True
    # `command` only introspects with -v/-V; bare `command X` RUNS X. Look at
    # the token after each `command` in the prefix rather than at the word
    # itself, so `command -v timeout` is exempt and `command timeout 5 ls`
    # is not.
    return any(
        posixpath.basename(t) == "command" and nxt in _INTROSPECTOR_FLAGS
        for t, nxt in itertools.pairwise(tokens)
    )


def _decide_for_segment(tokens: list[str]) -> str | None:
    """The per-segment body of `decide` — extracted so `decide` stays a loop.

    Kept as one function rather than several smaller ones because every branch
    below is a `continue`/`return` on the SAME `tokens`, and splitting it would
    mean passing that state across three call boundaries to save nothing.
    """
    words = check_first.command_word(tokens)
    if not words:
        return None
    prefix = tokens[: len(tokens) - len(words)]
    if _is_introspection(tokens, prefix):
        return None
    name = posixpath.basename(words[0])
    remedy = TRAPS.get(name)
    if remedy is None:
        return None
    # `which` next, and only for a name already in the table: the lookup is
    # the expensive part and the table is the cheap filter. Ordering it the
    # other way would stat the PATH for every command word in every Bash
    # call this hook sees.
    path = shutil.which(name)
    if path is None:
        return _deny_absent(name, remedy)
    # `_probe_runs` is the EVEN more expensive step — a real subprocess —
    # and it is narrowed one step further still: it only runs once `path`
    # is not None, i.e. only for the ~4 curated names AND only once one of
    # them has already resolved. See the module docstring's "WHY THE COST
    # IS ACCEPTABLE" for why that is rare enough not to need a cache.
    probe = _probe_runs(path)
    if not probe.ok:
        return _deny_broken(name, remedy, path, probe)
    return None


def decide(command: str) -> str | None:
    """Return a deny-reason if `command` runs a binary that will not RUN, else None.

    Public and pure, matching `hook_guard.decide` and `check_first.decide`: the
    function that denies a command is the one a fixture table can grade.

    "Will not run" now covers two host states, both handled by
    `_decide_for_segment`: a name `shutil.which` cannot resolve at all
    (`_deny_absent`, unchanged from the original guard), and a name that
    resolves to a file which fails when actually invoked (`_deny_broken`,
    added 2026-08-26 — see the module docstring for why a file-existence check
    alone stopped being sufficient).

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
        reason = _decide_for_segment(tokens)
        if reason is not None:
            return reason
    return None
