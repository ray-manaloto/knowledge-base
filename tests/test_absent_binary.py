# Copyright (c) 2026 Raymond Manaloto
"""`kb_setup.absent_binary` — deny a probe whose command word is not installed.

Every test here fakes `shutil.which` rather than trusting the host, and the
reason is this module's own subject: a test that passes because `timeout`
happens to be absent on the developer's mac is a test that could only pass, and
it would go green on a Linux CI box for the opposite reason while asserting
nothing. Both directions are driven explicitly.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable

import pytest
from kb_setup import absent_binary, hook_guard


@pytest.fixture
def absent(monkeypatch: pytest.MonkeyPatch) -> Callable[..., str | None]:
    """Make every trap name unresolvable, and everything else resolvable."""

    def which(name: str, *_args: object, **_kwargs: object) -> str | None:
        return None if name in absent_binary.TRAPS else f"/usr/bin/{name}"

    monkeypatch.setattr(absent_binary.shutil, "which", which)
    return which


@pytest.fixture
def present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make EVERY name resolvable — the host where the guard must stay inert."""

    def which(name: str, *_args: object, **_kwargs: object) -> str:
        return f"/usr/bin/{name}"

    monkeypatch.setattr(absent_binary.shutil, "which", which)


@pytest.mark.parametrize(
    "command",
    [
        "timeout 30 codex exec --help",
        "timeout --preserve-status 5 mise run lint",
        "/usr/bin/timeout 5 ls",
        "gtimeout 10 curl https://example.com",
        "ls && timeout 5 sleep 9",
        "env timeout 5 ls",
        "FOO=1 timeout 5 ls",
        "nproc",
        "tac /tmp/log",
    ],
)
def test_denies_an_absent_command_word(absent, command: str) -> None:
    reason = absent_binary.decide(command)
    assert reason is not None, f"missed: {command}"
    assert "does not exist on this host" in reason
    assert "PROBE reason" in reason


def test_the_remedy_names_a_real_replacement(absent) -> None:
    """A deny whose message leaves you stuck is a guard people route around.

    `a-remedy-must-clear-its-own-message.md`: the remedy has to be runnable.
    `perl` is the one named fallback that is a binary rather than a harness
    feature, so it is the one this can assert about the host.
    """
    reason = absent_binary.decide("timeout 30 ls")
    assert reason is not None
    assert "/usr/bin/perl" in reason
    assert "mise" in reason


@pytest.mark.parametrize(
    "command",
    [
        # The control arm for this very guard. Denying it would make the rule
        # unfollowable — you could not check whether the binary is there.
        "command -v timeout",
        "which timeout",
        "type timeout",
        "command -v gtimeout || echo ABSENT",
        # The name as an ARGUMENT, never as a command. This is the shape every
        # confirmed false positive in this repo's other guards had.
        "grep -rn timeout .claude/rules/",
        'git commit -m "note that timeout is absent on macOS"',
        "echo timeout",
        "rg 'timeout 30' docs/",
        # A flag or key that merely spells it.
        "mise run lint --timeout 60",
        "uv run pytest tests/ -k timeout",
        # Empty / whitespace.
        "",
        "   ",
    ],
)
def test_allows_what_is_not_an_absent_command_word(absent, command: str) -> None:
    assert absent_binary.decide(command) is None, f"false positive: {command}"


def test_inert_when_the_binary_is_present(present) -> None:
    """The guard is host-conditional, and this is the arm proving it.

    On Linux `timeout` resolves and the command is legitimate. A guard that
    denied it anyway would be enforcing a fact about one laptop.
    """
    assert absent_binary.decide("timeout 30 ls") is None
    assert absent_binary.decide("nproc") is None


def test_unparsable_input_is_allowed(absent) -> None:
    """An unbalanced quote returns None rather than degrading to a regex.

    Stated as a test because the sibling guard degrades the OTHER way, and the
    difference is deliberate: a regex for a bare word would fire inside prose.
    """
    assert absent_binary.decide('timeout 5 echo "unterminated') is None


def test_the_hook_actually_denies_it() -> None:
    """`decide` could be perfect and inert — this drives the real hook payload.

    `a-validator-nothing-calls-is-not-a-gate.md`. Runs against the LIVE host: on
    a machine where `timeout` exists this asserts nothing about denial, so it
    asserts the one thing true either way — that the wiring returns a verdict of
    the right shape rather than raising.
    """
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "timeout 5 ls"}})
    result = hook_guard.check_hook_call(payload)
    value = getattr(result, "value", None)
    if shutil.which("timeout") is None:
        assert value is not None
        assert "does not exist on this host" in value
    else:
        assert value is None


def test_the_gate_redirect_still_wins_over_this_one(absent) -> None:
    """Order is the contract: a hand-run gate reports the gate remedy.

    `_absent_binary` runs last of the four, so a command tripping both must come
    back with `kb-check`, which is about what the author meant to do.

    The chain is two SEGMENTS, and that is not incidental. `timeout 5 uv run
    ruff check .` — the shape this test was first written with — trips only THIS
    guard: `timeout` is not one of `check_first`'s transparent prefixes, so the
    gate sits behind a command word that guard does not recognise and it returns
    None. Which is the right verdict for that command anyway: a chain whose first
    word is missing does not run at all, so telling its author about `kb-check`
    would be answering the question they will have second.
    """
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "uv run ruff check . && timeout 5 ls"}}
    )
    value = getattr(hook_guard.check_hook_call(payload), "value", None)
    assert value is not None
    assert "kb-check" in value, "the older, more specific remedy must win"


def test_an_introspector_behind_a_transparent_prefix_is_not_denied() -> None:
    """The cold lane's P2 on `c27bddf60480` — the guard denied its own control arm.

    `command` sits in BOTH this module's `_INTROSPECTORS` and `check_first`'s
    `_TRANSPARENT_PREFIXES`. So for `env command -v timeout`, `tokens[0]` is
    `env` (not an introspector), `command_word` strips `env`, `command` and `-v`,
    and the resolved word is `timeout` — which this guard then denied. The denied
    command is precisely the probe the guard's own message tells you to run, and
    a guard that refuses its own remedy is worse than no guard.

    The negative arm matters as much: widening the check to "any token anywhere"
    would let `timeout 5 which foo` through, because `which` appears in it. Only
    the tokens `command_word` actually STRIPPED may exempt a segment.
    """
    for wrapped in (
        "env command -v timeout",
        "time command -v timeout",
        "nohup command -v timeout",
    ):
        assert absent_binary.decide(wrapped) is None, f"{wrapped} is an introspection probe"

    assert absent_binary.decide("command -v timeout") is None, "the unwrapped control arm"
    assert absent_binary.decide("env which timeout") is None, "`which` behind `env`"

    denied = absent_binary.decide("timeout 5 which foo")
    assert denied is not None, (
        "an introspector LATER in the line must not exempt the absent binary "
        "that actually runs — this is the false negative the narrow fix avoids"
    )
    assert "timeout" in denied
