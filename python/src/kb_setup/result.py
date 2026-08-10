# Copyright (c) 2026 Raymond Manaloto
"""`Result` + `Rc` — the typed error surface for `kb_setup` (§2 R5).

WHAT R5 ASKED FOR, and what the screening found. Ray, 2026-08-08: *"the python
library should be treated as an sdk with proper error codes via enums (not bare
ints, not ad-hoc rcs)"*. The screening behind this module is
`docs/research/reports/2026-08-09-r5-typed-error-surface.md`; the two facts that
shaped the code are worth carrying here rather than only there:

1. **The vocabulary already existed, undeclared.** `0` / `1` / `2` were returned
   from **175** sites across `kb_setup` with a consistent meaning that was
   written down only in prose (`CLAUDE.md`: *"rc 2 on a malformed request"*).
   `Rc` names it; it does not invent it.
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
    what this repo's 175 existing sites already meant. Note `uv` uses the same
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
    """Could not run: the request was malformed, or nothing was actually checked.

    The second half matters as much as the first — `kb-check -- src/x.rs` must
    not read as "x.rs is clean". A gate that never asked the question is not a
    pass (`.claude/rules/probes-need-a-control-arm.md`).
    """


@dataclass(frozen=True, slots=True)
class Ok[T]:
    """The command ran. `rc` says whether it found anything.

    `rc` defaults to `OK` so the common case stays `Ok(value)`; a findings-
    bearing run is explicit: `Ok(report, rc=Rc.FINDINGS)`.
    """

    value: T
    rc: Rc = Rc.OK

    def __post_init__(self) -> None:
        """Reject an `Ok` that claims the command could not run."""
        if self.rc is Rc.BAD_REQUEST:
            msg = (
                "Ok(rc=Rc.BAD_REQUEST) is not representable: BAD_REQUEST means "
                "the command could not run, which is an Err. Use "
                "Err(message) instead."
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


def exit_code[T](result: Result[T]) -> int:
    """The single `Result` -> process-exit-code conversion.

    Deliberately the only one, mirroring `impl From<ExitStatus> for ExitCode`
    (`ruff` lib.rs:47, `uv` commands/mod.rs:243). Every command funnels through
    here, so "what does rc 2 mean" has exactly one answer to read.
    """
    if isinstance(result, External):
        return result.code
    return int(result.rc)
