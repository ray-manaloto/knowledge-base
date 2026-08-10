# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.result — the typed error surface (§2 R5).

Control-armed both directions on every guard. A type that only ever accepts is
not a type: each rejection test is paired with the nearest ACCEPTED case, so a
guard that stopped discriminating (e.g. someone widens the check to always
raise, or deletes it) fails a test either way rather than silently passing the
half that was written.

The interop tests are the load-bearing ones for adoption. `Rc` is an `IntEnum`
specifically so the 175 existing `return 0/1/2` sites can be renamed rather than
rewritten — if `Rc.OK == 0` ever stops holding, the migration is a rewrite and
this suite should say so before a call site does.
"""

import subprocess
import sys

import pytest
from kb_setup.result import Err, External, Ok, Rc, Result, exit_code

# --------------------------------------------------------------------------
# Rc — the vocabulary itself
# --------------------------------------------------------------------------


def test_rc_values_are_the_existing_convention() -> None:
    """0/1/2 are not free to change: 175 call sites and every mise task read them."""
    assert (Rc.OK, Rc.FINDINGS, Rc.BAD_REQUEST) == (0, 1, 2)


def test_rc_members_are_ints_everywhere_an_int_was() -> None:
    """`IntEnum`, not `Enum` — this is what makes adoption a rename."""
    assert isinstance(Rc.FINDINGS, int)
    assert Rc.FINDINGS == 1
    assert [Rc.OK, Rc.FINDINGS][1] == 1  # usable as an index
    assert f"rc={Rc.BAD_REQUEST:d}" == "rc=2"


def test_rc_compares_against_a_real_subprocess_returncode() -> None:
    """The real interop case: `subprocess.run(...).returncode` vs `Rc`.

    Not a mock. `subprocess` returns a plain `int`, and the whole design rests
    on that comparing equal to an `Rc` member without unwrapping.
    """
    ok = subprocess.run([sys.executable, "-c", "raise SystemExit(0)"], check=False)
    bad = subprocess.run([sys.executable, "-c", "raise SystemExit(2)"], check=False)
    assert ok.returncode == Rc.OK
    assert bad.returncode == Rc.BAD_REQUEST
    # ...and the arm: the probe can tell them apart.
    assert ok.returncode != Rc.BAD_REQUEST


# --------------------------------------------------------------------------
# Ok — accepts a findings-bearing run, rejects an impossible one
# --------------------------------------------------------------------------


def test_ok_defaults_to_rc_ok() -> None:
    assert Ok("report").rc is Rc.OK


def test_ok_accepts_findings() -> None:
    """ARM for the test below: a findings-bearing run is a SUCCESSFUL run.

    This is the distinction the bare integers could not carry, so it is the
    single most important behaviour in the module.
    """
    result = Ok("3 violations", rc=Rc.FINDINGS)
    assert result.rc is Rc.FINDINGS
    assert exit_code(result) == 1


def test_ok_rejects_bad_request() -> None:
    """FAIL direction: BAD_REQUEST means the command could not run — that is Err."""
    with pytest.raises(ValueError, match="not representable"):
        Ok("anything", rc=Rc.BAD_REQUEST)


def _assign(obj: object, name: str, value: object) -> None:
    """Assign through an `object`-typed seam so the guard is exercised at RUNTIME.

    A direct `result.value = ...` is a *static* error (ty: "read-only"), and the
    repo forbids inline suppressions (`do-not.md` #9 — `no_lint_skip` rejects
    them). Silencing it would also test the wrong thing: what matters is that
    the assignment raises when it actually runs, which a type error never
    reaches.
    """
    setattr(obj, name, value)


def test_ok_is_frozen() -> None:
    result = Ok("report")
    with pytest.raises(AttributeError):
        _assign(result, "value", "mutated")

    # ...and the arm: the seam CAN assign to something mutable, so the raise
    # above is the dataclass being frozen and not `_assign` always failing.
    class _Mutable:
        value: str = "before"

    target = _Mutable()
    _assign(target, "value", "after")
    assert target.value == "after"


# --------------------------------------------------------------------------
# Err — accepts a stated reason, rejects success and rejects silence
# --------------------------------------------------------------------------


def test_err_defaults_to_bad_request() -> None:
    assert Err("no paths given").rc is Rc.BAD_REQUEST


def test_err_accepts_a_non_default_failing_rc() -> None:
    """ARM for `test_err_rejects_rc_ok`: the guard rejects OK, not everything."""
    assert Err("upstream said no", rc=Rc.FINDINGS).rc is Rc.FINDINGS


def test_err_rejects_rc_ok() -> None:
    """FAIL direction: a failure cannot exit 0."""
    with pytest.raises(ValueError, match="cannot exit 0"):
        Err("something broke", rc=Rc.OK)


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
def test_err_rejects_an_unexplained_failure(blank: str) -> None:
    """FAIL direction: an Err with no reason recreates the defect R9 names."""
    with pytest.raises(ValueError, match="must state a reason"):
        Err(blank)


def test_err_accepts_a_stated_reason() -> None:
    """ARM for the blank-message tests above."""
    assert Err("  the reason  ").message.strip() == "the reason"


# --------------------------------------------------------------------------
# exit_code — the single conversion
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (Ok(None), 0),
        (Ok(None, rc=Rc.FINDINGS), 1),
        (Err("malformed"), 2),
    ],
)
def test_exit_code_maps_every_representable_state(result: Result[None], expected: int) -> None:
    assert exit_code(result) == expected


def test_exit_code_returns_a_plain_int() -> None:
    """`SystemExit` and `sys.exit` want an int; an IntEnum is one, but pin it.

    A caller that JSON-serialises the code (e.g. into `.agent/kb/gates/`) gets a
    number rather than an enum repr.
    """
    code = exit_code(Err("nope"))
    assert type(code) is int


# --------------------------------------------------------------------------
# External — a subprocess's own code, passed through (uv's `External(u8)`)
# --------------------------------------------------------------------------


def test_external_passes_the_code_through_unchanged() -> None:
    """THE point: the foreign code survives, instead of flattening to 0/1/2."""
    assert exit_code(External(17)) == 17


@pytest.mark.parametrize("code", [0, 1, 2, 127, 255])
def test_external_accepts_every_real_exit_code(code: int) -> None:
    """ARM for the rejection tests below — including the ones that COLLIDE.

    `External(1)` and `External(2)` are deliberately allowed even though they
    look like `Rc.FINDINGS`/`Rc.BAD_REQUEST`. That is what passthrough means: a
    tool that exits 2 for its own reasons must reach the caller as 2, not be
    reinterpreted as our "bad request".
    """
    assert exit_code(External(code)) == code


def test_external_rejects_a_signal_returncode() -> None:
    """FAIL direction, and the realistic one.

    `subprocess.run(...).returncode` is NEGATIVE when the child was killed by a
    signal (-9 for SIGKILL). Passing that straight through would exit with 247
    after two's-complement truncation — a plausible-looking code that means
    nothing. The guard forces a deliberate conversion.
    """
    with pytest.raises(ValueError, match="not a process exit code"):
        External(-9)


def test_external_rejects_a_code_that_would_wrap() -> None:
    """FAIL direction: >255 silently truncates to 8 bits, so 256 would BE 0."""
    with pytest.raises(ValueError, match="not a process exit code"):
        External(256)


def test_external_is_a_result_and_needs_no_rc() -> None:
    """It is a third variant, not an `Rc` member — `Rc` has no EXTERNAL.

    Pinned because the ask was literally "add Rc.EXTERNAL", and an `IntEnum`
    member cannot carry a payload. If someone later adds one, this says why not.
    """
    assert not hasattr(Rc, "EXTERNAL")
    assert not hasattr(External(3), "rc")


def test_a_real_subprocess_code_round_trips() -> None:
    """End to end, no mock: child exits 42, `External` carries 42 out."""
    done = subprocess.run([sys.executable, "-c", "raise SystemExit(42)"], check=False)
    assert exit_code(External(done.returncode)) == 42
