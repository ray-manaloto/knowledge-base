# Copyright (c) 2026 Raymond Manaloto
"""`Result` + `Rc` — the typed error surface for `kb_setup` (§2 R5).

WHAT R5 ASKED FOR, and what the screening found. Ray, 2026-08-08: *"the python
library should be treated as an sdk with proper error codes via enums (not bare
ints, not ad-hoc rcs)"*. The screening behind this module is
`docs/research/reports/2026-08-09-r5-typed-error-surface.md`; the two facts that
shaped the code are worth carrying here rather than only there:

1. **The vocabulary already existed, undeclared — and NOT consistent.** `0`/`1`/`2`
   were returned from most of `kb_setup`'s commands with meanings written down
   only in prose, and the prose contradicted itself: `.claude/rules/mise-tasks-only.md`
   documented "a glob matching nothing" as **1** for `skill_lint` and "a skill
   name matching nothing" as **2** for `kb-skill-score`, in the same file.
   `Rc` names the vocabulary and `NOT_RUN` reconciles that case; neither
   invents one. (No site count is given here on purpose — the sweep converting
   those sites is what makes any figure stale, and `check.py`'s docstring
   carried exactly that kind of rotting number until a cold lane caught it.)
2. **`Err` is for "the tool broke", not "the tool found something".** This is
   the distinction the integers could not carry, and the reason the change is
   worth making at all. Today `return 1` means both *found lint errors* and
   *failed*, and `return 2` means both *you asked wrong* and *nothing ran*. A
   findings-bearing run is a **successful** run: it is `Ok(..., rc=FINDINGS)`.

The shape is `ruff`'s, read from the pinned source at `0.16.2` — `pub fn run(…)
-> Result<ExitStatus>` (`crates/ruff/src/lib.rs:128`) returning
`Ok(ExitStatus::Failure)` for a clean run that found lint errors, with a single
`From<ExitStatus> for ExitCode` conversion at the boundary (lib.rs:47). `uv`
does the same. Ray ruled this reading over an exception hierarchy on
2026-08-09; the report records that my argument against it — *"nothing screened
uses it"* — was measured only over four **Python** SDKs and stated as though it
covered the field. Re-probed: **49** `-> Result<` signatures in `ruff`, **229**
in `uv`, control `0`.

WHERE THE BOUNDARY IS. `Result` is for values crossing out of a `kb_setup`
command into `cli.py` / a mise task. Inside a module, ordinary Python control
flow is unchanged — this is not a ban on `raise` everywhere, it is a contract
about what a *command* hands back.

WHAT STILL RAISES, deliberately. Constructing an impossible `Result` (an `Ok`
carrying `BAD_REQUEST`, an `Err` carrying `OK`) raises `ValueError`. That is a
programmer error, not an operational one — the Rust equivalent is `unreachable!`,
which panics rather than returning `Err`. "No exceptions across the boundary"
governs how a command reports that *the work* failed; it does not ask the type
to swallow its own misuse and hand back a plausible-looking value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

_MAX_EXIT_CODE = 255
"""POSIX truncates a wait status to 8 bits; anything wider silently wraps."""


class Rc(IntEnum):
    """Process exit codes, named. `IntEnum` because these ARE the integers.

    `IntEnum` rather than `Enum` is load-bearing in both directions: a member is
    an `int` everywhere the previous literals were, so `sys.exit(Rc.OK)` and a
    comparison against `subprocess.run(...).returncode` both keep working with
    no unwrapping — and adopting this is a rename at the call sites, not a
    rewrite.

    The three meanings are `ruff`'s (`Success` / `Failure` / `Error`), which is
    what most of this repo's existing sites already meant. Note `uv` uses the same
    three integers with the *inverse* emphasis (its `Failure` is bad user input,
    its `Error` is an unexpected failure) — which is the argument for naming
    them: two tools by one vendor, three shared integers, different meanings,
    and only the member name records which.
    """

    OK = 0
    """Ran to completion; nothing to report."""

    FINDINGS = 1
    """Ran to completion and FOUND something the caller must act on.

    Not a failure. A lint run that reports three violations did its job.
    """

    BAD_REQUEST = 2
    """Could not run: the request itself was malformed.

    Bad arguments, an unknown subcommand, a flag with no value. The caller can
    fix this by asking differently.
    """

    NOT_RUN = 127
    """The request was fine and the question was still never asked.

    A glob that matched nothing, a tool binary that would not start, an empty
    worklist. Distinct from `BAD_REQUEST` (you asked wrong) and from `FINDINGS`
    (we looked and found something) — **"we did not look" is a third state**,
    and collapsing it into either is how a gate reports clean without checking
    anything (`.claude/rules/probes-need-a-control-arm.md`).

    **127 is not invented here.** The repo already chose it for exactly this
    meaning, twice: `check.RC_COULD_NOT_RUN` and `gates._RC_COULD_NOT_RUN`, both
    `= 127`, both documented as *"distinct from any tool's own failure rc, so
    'broken' never reads as 'failed'"*. Both now alias this member, so the
    constant is defined once. It matches the shell's own `command not found`
    convention, and nothing in `kb_setup` branches on a specific non-zero code
    (every check is `!= 0`), so adopting it changed no consumer.

    **Why a fourth member existed to be added.** `.claude/rules/mise-tasks-only.md`
    documented this one case *both ways*: "a glob matching nothing exits **1**"
    for `skill_lint`, and "**rc 2** on a malformed request, e.g. a skill name
    matching nothing" for `kb-skill-score` — same failure, opposite codes, same
    file. `check.py` independently chose 2, and `distill` returns a string
    because it is advisory. Ray ruled the fourth member on 2026-08-09 rather
    than forcing that case into a code that misdescribes it.
    """


_RAN = frozenset({Rc.OK, Rc.FINDINGS})
"""The codes that mean the command actually ran. Everything else is an `Err`."""


@dataclass(frozen=True, slots=True)
class Ok[T]:
    """The command ran. `rc` says whether it found anything.

    `rc` defaults to `OK` so the common case stays `Ok(value)`; a findings-
    bearing run is explicit: `Ok(report, rc=Rc.FINDINGS)`.
    """

    value: T
    rc: Rc = Rc.OK

    def __post_init__(self) -> None:
        """Reject an `Ok` that claims the command did not run.

        Closed rather than a blacklist: only the two codes that mean "it ran"
        are admissible, so a member added later is rejected by default instead
        of silently becoming a valid `Ok`. `NOT_RUN` was exactly that member.
        """
        if self.rc not in _RAN:
            msg = (
                f"Ok(rc=Rc.{self.rc.name}) is not representable: it means the "
                f"command did not run, which is an Err. Use Err(message) — or "
                f"Err(message, rc=Rc.{self.rc.name}) to keep the code."
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Err:
    """The command could not run. Carries the operator-facing reason.

    `message` is the text a caller prints; it is required, because an `Err`
    whose reason is not stated recreates exactly the failure R9 names — a
    non-zero rc whose cause is somewhere nobody greps.
    """

    message: str
    rc: Rc = field(default=Rc.BAD_REQUEST)

    def __post_init__(self) -> None:
        """Reject an `Err` that claims success, or one with no stated reason."""
        if self.rc is Rc.OK:
            msg = "Err(rc=Rc.OK) is not representable: a failure cannot exit 0."
            raise ValueError(msg)
        if not self.message.strip():
            msg = (
                "Err(message=...) must state a reason; an unexplained "
                "failure is the defect R9 names."
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class External:
    """A subprocess's OWN exit code, passed through unchanged.

    This is `uv`'s `ExitStatus::External(u8)` (`crates/uv/src/commands/mod.rs:118`,
    pinned `0.12.3`), which maps straight to `ExitCode::from(code)` rather than
    to one of the three named cases. `kb_setup` shells out constantly —
    `graphify`, `hk`, `pytest`, `gh` — and today flattens every one of those rcs
    into `0`/`1`/`2`, which discards what the tool actually said.

    **Why this is not an `Rc` member.** Ray asked for `Rc.EXTERNAL` on
    2026-08-09; it is not representable as one. An `IntEnum` member is a single
    fixed integer, and the whole point of uv's variant is that it *carries* the
    code — `External(17)` and `External(3)` are different exit codes. Making it
    a member would mean either inventing a fixed integer (which is then not a
    passthrough) or attaching a payload to an enum member (which `IntEnum` has
    no room for). So it is a third `Result` variant with identical behaviour to
    uv's, and `Rc` stays the three-member vocabulary of codes *we* choose.

    **When to use it:** a command whose result IS one subprocess's verdict, and
    where the caller should see that tool's code. **When not to:** a command
    that aggregates several tools and forms its own opinion — `check.py` runs
    four and decides `FINDINGS`, which is `Ok`, not a passthrough.
    """

    code: int
    message: str = ""

    def __post_init__(self) -> None:
        """Reject a code no process could actually have exited with."""
        if not 0 <= self.code <= _MAX_EXIT_CODE:
            msg = (
                f"External(code={self.code}) is not a process exit code: "
                f"must be 0..{_MAX_EXIT_CODE}. A negative value is usually a "
                f"`subprocess` returncode carrying a SIGNAL (-N) — convert it "
                f"deliberately rather than passing it through."
            )
            raise ValueError(msg)


type Result[T] = Ok[T] | Err | External
"""What a `kb_setup` command hands back across the boundary."""


_SIGNAL_EXIT_BASE = 128
"""POSIX shells report a signal-killed child as `128 + N`. See below."""


def external_from_returncode(returncode: int, message: str = "") -> External:
    """Convert a `subprocess` returncode into an `External`, signals included.

    `External.__post_init__` refuses a negative code on purpose, and its
    docstring says why: a negative `subprocess` returncode is not an exit code
    at all, it is `-N` for "killed by signal N". Passing it through would wrap
    to nonsense (`-9` truncates to 247), and `abs()` would claim the child
    exited 9 when nothing did.

    So the conversion is stated once, here, rather than improvised at each
    call site: **signal N becomes `128 + N`**, which is what every POSIX shell
    reports for the same event and therefore what a caller reading the rc
    already expects. `SIGKILL` (9) is 137; `SIGTERM` (15) is 143.

    A signal number wide enough to overflow the byte is clamped rather than
    wrapped — losing precision loudly beats reporting a different signal.
    """
    if returncode < 0:
        code = min(_SIGNAL_EXIT_BASE - returncode, _MAX_EXIT_CODE)
        signal_note = f"killed by signal {-returncode}"
        return External(code=code, message=message or signal_note)
    return External(code=min(returncode, _MAX_EXIT_CODE), message=message)


def exit_code[T](result: Result[T]) -> int:
    """The single `Result` -> process-exit-code conversion.

    Deliberately the only one, mirroring `impl From<ExitStatus> for ExitCode`
    (`ruff` lib.rs:47, `uv` commands/mod.rs:243). Every command funnels through
    here, so "what does rc 2 mean" has exactly one answer to read.
    """
    if isinstance(result, External):
        return result.code
    return int(result.rc)
