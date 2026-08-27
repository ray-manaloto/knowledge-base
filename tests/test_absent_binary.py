# Copyright (c) 2026 Raymond Manaloto
"""`kb_setup.absent_binary` — deny a probe whose command word cannot RUN.

THIS PARAGRAPH USED TO CLAIM "every test here fakes `shutil.which` AND
`_probe_runs`". That sentence was false, and being false is why the same class
of regression hit this file THREE times before anyone read it closely enough
to notice it was a promise nobody was keeping. Written now as a fact about the
file, checked against the actual fixture list below rather than restated from
memory the next time this file changes:

WHY THIS KEEPS HAPPENING. `timeout`/`nproc`/`tac`/`gtimeout` genuinely being
present or absent on THIS machine is not a fixed fact, it is `mise.toml`'s
current pin state — and that state has changed under this file three times in
one day: (2026-08-18) `timeout` genuinely absent; (2026-08-26, a mise reshim)
`timeout`/`nproc`/`tac` resolve to a shim with no version set, so they exist
as files but cannot run; (2026-08-26, `7eb281a8`) `conda:coreutils` pinned in
`mise.toml`, so `timeout`/`nproc`/`tac` now genuinely run. `gtimeout` alone has
stayed absent throughout. A test that asserts a DENY (or an allow) for any of
these four names against the LIVE host is making a claim about `mise.toml`,
whether it says so or not, and that claim expires the next time this repo's
tool pins change — which has already happened three times.

WHICH TESTS FAKE BOTH LAYERS (the default, and what to do unless you have a
specific reason not to): everything using the `absent`, `present`, or
`resolves_but_broken` fixtures — the majority of this file. Each controls
`shutil.which` and, where the code path reaches it, `_probe_runs`, so its
verdict follows from the FIXTURE, never from what happens to be pinned today.

WHICH TESTS DO NOT, AND WHY EACH ONE IS SAFE ANYWAY — the complete list, so a
future addition can be checked against it rather than assumed:

* `test_the_hook_actually_denies_it` — compares the hook's verdict to
  `absent_binary.decide()` called directly, rather than asserting an expected
  DENY or allow. It is checking that the wiring reaches this module, not what
  this module currently decides, so it passes under any host state.
* `test_probe_runs_reports_success_for_a_real_working_binary` — a unit test of
  `_probe_runs` ITSELF against `/usr/bin/perl`, which is Apple's vendored
  system perl, not a mise-managed tool. No `mise.toml` change can affect it.
* `test_probe_runs_reports_failure_for_a_path_that_cannot_exec` — the path is
  fabricated to never exist on any host; there is no config state that could
  make it start resolving.

Every one of the three above is deliberate and documented at its own
definition — read the local docstring before assuming a fourth exception is
safe by analogy. If you are about to write a NEW test that asserts what
`timeout`/`nproc`/`tac`/`gtimeout` do against the live host, it is very likely
wrong; use a fixture instead.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from kb_setup import absent_binary, hook_guard


@pytest.fixture
def absent(monkeypatch: pytest.MonkeyPatch) -> Callable[..., str | None]:
    """Make every trap name unresolvable, and everything else resolvable.

    `_probe_runs` is left unpatched here on purpose: with every trap name
    unresolvable, `decide` never reaches it (`shutil.which` returns None
    first), so a test using this fixture that DID reach the probe would be
    proof the "which first, cheap filter" ordering broke — see
    `test_the_probe_never_runs_for_a_name_that_never_resolves`.
    """

    def which(name: str, *_args: object, **_kwargs: object) -> str | None:
        return None if name in absent_binary.TRAPS else f"/usr/bin/{name}"

    monkeypatch.setattr(absent_binary.shutil, "which", which)
    return which


@pytest.fixture
def present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make EVERY name resolve AND actually run — the host where the guard is inert.

    Two layers now, both faked: `shutil.which` resolving a name used to be the
    whole story, and stopped being it on 2026-08-26 (see the module docstring's
    "RE-ARMED" section). A fixture that only faked `which` would prove the OLD
    predicate goes inert, not the current one.
    """

    def which(name: str, *_args: object, **_kwargs: object) -> str:
        return f"/usr/bin/{name}"

    def probe_runs(_path: str) -> absent_binary._Probe:
        return absent_binary._Probe(ok=True, returncode=0, detail="")

    monkeypatch.setattr(absent_binary.shutil, "which", which)
    monkeypatch.setattr(absent_binary, "_probe_runs", probe_runs)


@pytest.fixture
def resolves_but_broken(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every trap name resolves, but actually running it fails — the 2026-08-26 shape.

    Reproduces the exact regression without depending on this machine's mise
    state: a name `shutil.which` finds, whose invocation nonetheless exits
    non-zero with a mise-shaped error on stderr.
    """

    def which(name: str, *_args: object, **_kwargs: object) -> str | None:
        return f"/Users/dev/.local/share/mise/shims/{name}" if name in absent_binary.TRAPS else None

    def probe_runs(path: str) -> absent_binary._Probe:
        name = path.rsplit("/", 1)[-1]
        return absent_binary._Probe(
            ok=False,
            returncode=1,
            detail=f"mise ERROR No version is set for shim: {name}",
        )

    monkeypatch.setattr(absent_binary.shutil, "which", which)
    monkeypatch.setattr(absent_binary, "_probe_runs", probe_runs)


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

    On Linux `timeout` resolves AND runs, and the command is legitimate. A
    guard that denied it anyway would be enforcing a fact about one laptop.
    Both layers are faked (`present` patches `shutil.which` AND `_probe_runs`)
    — patching only `which` would prove the PRE-2026-08-26 predicate goes
    inert, which is exactly the version of this test that missed the
    regression the first time.
    """
    assert absent_binary.decide("timeout 30 ls") is None
    assert absent_binary.decide("nproc") is None


def test_denies_a_binary_that_resolves_but_will_not_run(resolves_but_broken) -> None:
    """The re-arm's whole point: a resolvable name is not a runnable one.

    Reproduces the 2026-08-26 regression (`shutil.which` finds a mise shim,
    running it exits 1 with 'No version is set for shim') without depending on
    THIS machine's mise state — see `resolves_but_broken`. Before the re-arm,
    `decide` returned None here because it only ever checked `which`.
    """
    reason = absent_binary.decide("timeout 5 ls")
    assert reason is not None, "a resolvable-but-broken binary must still be denied"
    assert "PROBE reason" in reason
    assert "resolves to" in reason
    assert "does not exist on this host" not in reason, (
        "this is the BROKEN-shim message, not the absent one -- conflating them "
        "would tell the reader `command -v` returns 1 when it returns 0"
    )
    assert "**1**" in reason, "the rc must be stated, and it is no longer 127"
    assert "No version is set for shim" in reason, "the real failure detail belongs in the message"


def test_the_probe_never_runs_for_a_name_that_never_resolves(
    absent, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ordering guard: `_probe_runs` is the expensive step and must stay LAST.

    `absent` already proves this indirectly (it never patches `_probe_runs`,
    so a call into the real `subprocess.run` would either hang the test suite
    or raise). This test makes the guarantee explicit and immediate: patch
    `_probe_runs` to blow up, and confirm every absent-command-word case still
    resolves cleanly because `decide` never calls it once `which` says None.
    """

    def explode(_path: str) -> absent_binary._Probe:
        raise AssertionError("_probe_runs must not run once `which` already returned None")

    monkeypatch.setattr(absent_binary, "_probe_runs", explode)
    for command in (
        "timeout 30 ls",
        "gtimeout 10 curl https://example.com",
        "nproc",
        "tac /tmp/log",
    ):
        assert absent_binary.decide(command) is not None


def test_unparsable_input_is_allowed(absent) -> None:
    """An unbalanced quote returns None rather than degrading to a regex.

    Stated as a test because the sibling guard degrades the OTHER way, and the
    difference is deliberate: a regex for a bare word would fire inside prose.
    """
    assert absent_binary.decide('timeout 5 echo "unterminated') is None


def test_the_hook_actually_denies_it() -> None:
    """`decide` could be perfect and inert — this drives the real hook payload.

    `a-validator-nothing-calls-is-not-a-gate.md`. Runs against the LIVE host,
    and compares the hook's verdict to `absent_binary.decide` called directly
    rather than to `shutil.which("timeout") is None` — that used to be the
    whole predicate and stopped being it on 2026-08-26, when `timeout` started
    resolving to a broken mise shim on this very machine (`which` is not None,
    yet the right verdict is still a deny). Comparing to `decide` itself keeps
    this test correct on ANY host state — absent, broken, or genuinely fixed —
    while still proving the thing it exists to prove: that the hook's wiring
    actually reaches this module rather than silently swallowing the call.
    """
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "timeout 5 ls"}})
    result = hook_guard.check_hook_call(payload)
    value = getattr(result, "value", None)
    expected = absent_binary.decide("timeout 5 ls")
    assert value == expected


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


def test_an_introspector_behind_a_transparent_prefix_is_not_denied(resolves_but_broken) -> None:
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

    Uses `resolves_but_broken` rather than trusting the live host for the final
    assertion. This test originally ran unmocked against the real machine, which
    was reliable exactly until it was not — TWICE: once when a mise reshim broke
    `timeout` silently (the whole reason this module changed on 2026-08-26), and
    again a few hours later when coreutils turned out to be genuinely installed
    here and due to be ACTIVATED via `mise.toml`, which would make `timeout` run
    and turn the final `is not None` false out from under this test. What this
    assertion is actually about — an introspector LATER in the line must not
    exempt an otherwise-denied command word — has nothing to do with whether
    `timeout` happens to work on this laptop today, so the fixture controls that
    and leaves the parser behaviour, which is the actual subject, live.
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
        "an introspector LATER in the line must not exempt a command word "
        "that is otherwise denied — this is the false negative the narrow "
        "fix avoids, independent of whether `timeout` works on this host"
    )
    assert "timeout" in denied


def test_bare_command_runs_its_argument_and_is_not_an_introspection_probe(
    resolves_but_broken,
) -> None:
    """Round 2's P2, and a hole opened by round 1's own fix.

    Round 1 exempted a segment whose stripped prefix contained an introspector,
    with `command` listed unqualified. But `command` is an execution WRAPPER —
    `command timeout 5 ls` RUNS `timeout` — and only `command -v` / `-V` asks
    about a name. So the fix that stopped a false positive opened a false
    NEGATIVE: the absent binary ran and died with rc 127, which is the exact
    transcript-poisoning this guard exists to prevent.

    Both directions are armed here, because closing one and leaving the other is
    what produced this finding in the first place.

    THIRD round this exact class has hit this file. This test ran unmocked
    against the live host until `conda:coreutils` was pinned in `mise.toml`
    (`7eb281a8`) and made `timeout` genuinely resolve and run here, which
    turned `denied is not None` false out from under it — `mise run test`
    caught it (`git log` on this file confirms the earlier fixes for the
    same reason: the mise-reshim regression this module was re-armed for,
    then `test_an_introspector_behind_a_transparent_prefix_is_not_denied`).
    `resolves_but_broken` makes the assertion about the PARSER — an
    execution wrapper still counts as running the wrapped name — rather
    than about whether `timeout` happens to work on this laptop.
    """
    for runs_it in ("command timeout 5 ls", "env command timeout 5 ls"):
        denied = absent_binary.decide(runs_it)
        assert denied is not None, f"{runs_it} EXECUTES timeout; it is not an introspection probe"
        assert "timeout" in denied

    for asks_about_it in ("command -v timeout", "command -V timeout", "env command -v timeout"):
        assert absent_binary.decide(asks_about_it) is None, (
            f"{asks_about_it} is the control arm this guard's own message recommends"
        )


def test_probe_runs_reports_success_for_a_real_working_binary() -> None:
    """`_probe_runs` itself, armed positive, against a REAL binary.

    Deliberately UNMOCKED, and deliberately kept that way: this function is a
    unit test of `_probe_runs`, not of `decide()`'s DENY/allow verdict, and
    faking the subprocess call here would only prove that `subprocess.run`
    returns whatever a mock is told to return — it would stop testing that
    `_probe_runs` correctly reads a REAL process's rc and stdout, which is the
    entire reason this function exists over trusting `shutil.which` alone (see
    the module docstring's "RE-ARMED" section).

    `/usr/bin/perl` is the right binary to depend on here, and for a DIFFERENT
    reason than the three regressions above: it is Apple's vendored system
    perl, not a mise-managed tool, so it carries none of the risk that bit this
    file three times — `mise.toml` gaining, losing, or activating a pin cannot
    make `/usr/bin/perl` start or stop working. This repo already leans on that
    same fact elsewhere (`TRAPS["timeout"]`'s remedy text, and
    `test_the_remedy_names_a_real_replacement` above), so this is not a new
    assumption, just the same one applied to a different call site.
    """
    probe = absent_binary._probe_runs("/usr/bin/perl")
    assert probe.ok is True
    assert probe.returncode == 0


def test_probe_runs_reports_failure_for_a_path_that_cannot_exec() -> None:
    """The OSError arm: `which` resolved a moment ago, exec fails now.

    Takes no fixture, but is NOT the same class of risk as the three fixed
    above: the path is fabricated to never exist on ANY host, so there is no
    future mise pin, activation, or config change that could make it start
    resolving — unlike `timeout`/`nproc`/`tac`, whose absence was itself the
    variable. This is a `FileNotFoundError` by construction, not by the luck
    of what happens to be installed here today.

    Simulated with a path that was never resolvable, which is the same OSError
    shape (`FileNotFoundError`, a subclass of `OSError`) Python raises for a
    permission-denied or exec-format-mismatch path too — `_probe_runs` does not
    distinguish those cases and none of them means "this would work".
    """
    probe = absent_binary._probe_runs("/nonexistent/kb-setup-absent-binary-probe-fixture")
    assert probe.ok is False
    assert probe.returncode is None
    assert probe.detail, "the OSError text belongs in the deny message"


def test_probe_runs_fails_open_on_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one branch this guard cannot explain, and chooses not to deny on.

    Never observed for a real `TRAPS` entry (see the module docstring), so this
    is controlled directly rather than chased on a real host — the module's own
    `subprocess` is patched, one layer below `_probe_runs`, the same pattern
    `absent_binary.shutil` above uses.
    """
    import subprocess
    from typing import Never

    def raises_timeout(*_args: object, **_kwargs: object) -> Never:
        raise subprocess.TimeoutExpired(cmd=["timeout", "--version"], timeout=2.0)

    monkeypatch.setattr(absent_binary.subprocess, "run", raises_timeout)
    probe = absent_binary._probe_runs("/usr/bin/timeout")
    assert probe.ok is True, "fail OPEN: an inconclusive probe must not brick the call"
    assert probe.returncode is None
