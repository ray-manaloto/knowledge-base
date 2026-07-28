"""Tests for the shared eval runner (kb_setup.evals).

The runner's whole reason for existing is that a case which can only pass is
decoration, so these tests are unusually literal about the FAIL direction: the
control-arm rule is itself control-armed here, in both directions.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from kb_setup import evals

_ARMED = evals.fail("armed")


def _case(
    probe: evals.Outcome,
    control: evals.Outcome | None = _ARMED,
    *,
    gated: bool = True,
    live: bool = False,
    slow: bool = False,
) -> evals.Case:
    """Build a case from fixed outcomes.

    ``control`` defaults to a FAIL so the common case is properly armed; pass
    ``None`` to model a case whose author forgot the control arm.
    """
    return evals.Case(
        name="tier1.x",
        description="test case",
        probe=lambda: probe,
        control=(lambda: control) if control is not None else None,
        gated=gated,
        live=live,
        slow=slow,
    )


# --- the control-arm rule (design principle 1) --------------------------------


def test_a_gated_case_with_no_control_arm_is_refused() -> None:
    """The structural rule: an uncontrolled gated case is never counted.

    Its probe PASSES here — and the run is still red. That is the point: the
    probe's own answer is not evidence when nothing has shown it can say no.
    """
    report = evals.run_cases([_case(evals.ok("looks fine"), control=None)])
    assert report.results[0].outcome.verdict is evals.Verdict.UNARMED
    assert report.unarmed == 1
    assert report.red


def test_a_control_arm_that_passes_leaves_the_case_unarmed() -> None:
    """A control that does not FAIL has demonstrated nothing.

    This is the subtle half. A case can carry a control arm that is simply
    wrong — pointed at input that is not actually broken — and then the case
    looks armed while still being a coin with one face.
    """
    report = evals.run_cases([_case(evals.ok("fine"), control=evals.ok("also fine"))])
    assert report.results[0].outcome.verdict is evals.Verdict.UNARMED
    assert "not FAIL" in report.results[0].outcome.detail


def test_a_control_arm_that_skips_leaves_the_case_unarmed() -> None:
    """SKIP is not FAIL. "Could not run the control" is not "the control works"."""
    report = evals.run_cases([_case(evals.ok("fine"), control=evals.skip("no fixture"))])
    assert report.results[0].outcome.verdict is evals.Verdict.UNARMED


def test_a_control_arm_that_raises_leaves_the_case_unarmed() -> None:
    """A crashing control has not demonstrated the FAIL direction either."""

    def boom() -> evals.Outcome:
        raise RuntimeError("fixture blew up")

    case = evals.Case(name="tier1.x", description="d", probe=lambda: evals.ok("f"), control=boom)
    report = evals.run_cases([case])
    assert report.results[0].outcome.verdict is evals.Verdict.UNARMED
    assert "RuntimeError" in report.results[0].outcome.detail


def test_a_properly_armed_passing_case_is_green() -> None:
    """CONTROL ARM for all of the above: with a real control, PASS is counted.

    Without this, an always-UNARMED implementation would satisfy every test
    above — the tests would be measuring nothing.
    """
    report = evals.run_cases([_case(evals.ok("resolves"))])
    assert report.results[0].outcome.verdict is evals.Verdict.PASS
    assert report.passed == 1
    assert not report.red


def test_an_advisory_case_needs_no_control_arm() -> None:
    """Advisory cases cannot make the run red, so the rule does not apply."""
    report = evals.run_cases([_case(evals.fail("bad"), control=None, gated=False)])
    assert report.results[0].outcome.verdict is evals.Verdict.FAIL
    assert not report.red


def test_a_probe_that_raises_is_a_failure_not_a_crash() -> None:
    """One bad probe must not take the whole run down."""

    def boom() -> evals.Outcome:
        raise ValueError("probe blew up")

    case = evals.Case(
        name="tier1.x", description="d", probe=boom, control=lambda: evals.fail("armed")
    )
    report = evals.run_cases([case])
    assert report.results[0].outcome.verdict is evals.Verdict.FAIL
    assert "ValueError" in report.results[0].outcome.detail


# --- live gating --------------------------------------------------------------


def test_live_cases_are_skipped_by_default() -> None:
    """The offline set is what joins the ship gates; live costs API calls."""
    report = evals.run_cases([_case(evals.ok("f"), live=True)])
    assert report.results[0].outcome.verdict is evals.Verdict.SKIP
    assert not report.red


def test_live_cases_run_when_requested() -> None:
    """Control arm for the above: --live actually reaches the probe."""
    report = evals.run_cases([_case(evals.ok("f"), live=True)], live=True)
    assert report.results[0].outcome.verdict is evals.Verdict.PASS


# --- slow gating (a SEPARATE axis from live) ----------------------------------


def test_slow_cases_are_skipped_by_default() -> None:
    """Free is not the same as cheap: a 3-minute case cannot ride every ship."""
    report = evals.run_cases([_case(evals.ok("f"), slow=True)])
    assert report.results[0].outcome.verdict is evals.Verdict.SKIP
    assert "--slow" in report.results[0].outcome.detail
    assert not report.red


def test_slow_cases_run_when_requested() -> None:
    """Control arm for the above: --slow actually reaches the probe."""
    report = evals.run_cases([_case(evals.ok("f"), slow=True)], slow=True)
    assert report.results[0].outcome.verdict is evals.Verdict.PASS


def test_slow_and_live_are_independent_axes() -> None:
    """--live must not drag in the slow set, nor --slow the paid one.

    They are different costs — API spend versus wall clock — and collapsing
    them would mean one flag silently buys the other.
    """
    cases = [
        _case(evals.ok("f"), live=True),
        _case(evals.ok("f"), slow=True),
    ]
    live_only = evals.run_cases(cases, live=True)
    assert live_only.results[0].outcome.verdict is evals.Verdict.PASS
    assert live_only.results[1].outcome.verdict is evals.Verdict.SKIP
    slow_only = evals.run_cases(cases, slow=True)
    assert slow_only.results[0].outcome.verdict is evals.Verdict.SKIP
    assert slow_only.results[1].outcome.verdict is evals.Verdict.PASS


# --- an advisory case's control arm is optional, but never ignored -------------


def test_a_declared_control_arm_runs_even_on_an_advisory_case() -> None:
    """Advisory waives the REQUIREMENT, and must not become a loophole.

    A result reported without its control arm is an opinion, so a control that
    is declared gets run and said out loud.
    """
    calls: list[int] = []

    def control() -> evals.Outcome:
        calls.append(1)
        return evals.fail("armed")

    case = evals.Case(
        name="tier2.advisory",
        description="d",
        probe=lambda: evals.ok("measured"),
        control=control,
        gated=False,
    )
    report = evals.run_cases([case])
    assert calls == [1]
    assert "control arm failed as required" in report.results[0].control_detail


def test_an_advisory_control_arm_that_does_not_fail_is_reported_not_hidden() -> None:
    """It cannot redden an advisory run — but it must not be silent either."""
    case = evals.Case(
        name="tier2.advisory",
        description="d",
        probe=lambda: evals.ok("measured"),
        control=lambda: evals.ok("did not fail"),
        gated=False,
    )
    report = evals.run_cases([case])
    assert "NOT ARMED" in report.results[0].control_detail
    assert report.results[0].outcome.verdict is evals.Verdict.PASS
    assert not report.red


# --- the environment gate (precondition) --------------------------------------


def test_a_precondition_skip_short_circuits_the_case() -> None:
    """A case that does not apply here is a third state, checked FIRST."""
    case = evals.Case(
        name="tier1.x",
        description="d",
        probe=lambda: evals.fail("would have failed"),
        control=lambda: evals.fail("armed"),
        precondition=lambda: evals.skip("tool is host-only"),
    )
    report = evals.run_cases([case])
    assert report.results[0].outcome.verdict is evals.Verdict.SKIP
    assert "host-only" in report.results[0].outcome.detail
    assert not report.red


def test_a_precondition_is_checked_before_the_control_arm_rule() -> None:
    """THE reason this state exists, and the ordering is the whole fix.

    A case that cannot apply here also cannot have a working control arm — the
    control drives the same code path, so it skips too. If the control-arm rule
    ran first, such a case would be reported UNARMED and turn the run RED for a
    question that was never asked. This is a real failure, not a hypothetical:
    dotfiles' graphify canary is host-only and went rc=-2 inside its
    devcontainer, taking the whole smoke run with it.
    """
    case = evals.Case(
        name="tier1.x",
        description="d",
        probe=lambda: evals.ok("f"),
        control=lambda: evals.skip("control cannot run here either"),
        precondition=lambda: evals.skip("does not apply here"),
    )
    report = evals.run_cases([case])
    assert report.results[0].outcome.verdict is evals.Verdict.SKIP
    assert report.unarmed == 0
    assert not report.red


def test_a_precondition_returning_none_runs_the_case_normally() -> None:
    """CONTROL ARM: without this, an always-skip precondition passes above."""
    case = evals.Case(
        name="tier1.x",
        description="d",
        probe=lambda: evals.ok("ran"),
        control=lambda: evals.fail("armed"),
        precondition=lambda: None,
    )
    report = evals.run_cases([case])
    assert report.results[0].outcome.verdict is evals.Verdict.PASS


def test_a_precondition_that_raises_fails_the_case() -> None:
    """An environment gate we cannot evaluate must not silently let the case run."""

    def boom() -> evals.Outcome | None:
        raise RuntimeError("gate blew up")

    case = evals.Case(
        name="tier1.x",
        description="d",
        probe=lambda: evals.ok("f"),
        control=lambda: evals.fail("armed"),
        precondition=boom,
    )
    report = evals.run_cases([case])
    assert report.results[0].outcome.verdict is evals.Verdict.FAIL
    assert "RuntimeError" in report.results[0].outcome.detail


def test_the_live_filter_still_wins_over_the_precondition() -> None:
    """A live case is skipped without ever evaluating its environment gate.

    Otherwise `mise run eval` could pay a probe's cost for a case it is not
    going to run.
    """
    calls: list[int] = []

    def gate() -> evals.Outcome | None:
        calls.append(1)
        return None

    case = evals.Case(
        name="tier1.x",
        description="d",
        probe=lambda: evals.ok("f"),
        control=lambda: evals.fail("armed"),
        live=True,
        precondition=gate,
    )
    evals.run_cases([case])
    assert calls == []


# --- SKIP is never green ------------------------------------------------------


def test_an_all_skipped_run_reports_not_verifiable_and_exits_nonzero() -> None:
    """Collapsing "could not check" into "fine" is the defect this avoids.

    A run where nothing could be checked has produced no evidence, so reporting
    it as green would be the strongest possible version of the inert
    declaration: a gate that observed nothing and said OK.
    """
    rc, text = evals.run([_case(evals.ok("f"), live=True)])
    assert rc == 1
    assert "NOT VERIFIABLE HERE" in text
    assert "OK eval" not in text


def test_a_partially_skipped_run_is_still_green() -> None:
    """Control arm: a SKIP alongside a real PASS must not fail the run."""
    rc, text = evals.run([_case(evals.ok("f")), _case(evals.ok("f"), live=True)])
    assert rc == 0
    assert "OK eval" in text


def test_a_gated_failure_makes_the_run_red() -> None:
    rc, text = evals.run([_case(evals.fail("nope"))])
    assert rc == 1
    assert "FAIL eval" in text


# --- probe primitives ---------------------------------------------------------


def test_cli_present_discriminates() -> None:
    """Both arms, per the rule this module enforces on everyone else."""
    assert evals.cli_present("sh").verdict is evals.Verdict.PASS
    assert evals.cli_present("definitely-not-a-real-binary-xyz").verdict is evals.Verdict.FAIL


def test_run_command_reports_a_real_rc(tmp_path: Path) -> None:
    """Principle 8: surface the status seen, never a prose summary."""
    assert evals.run_command(["true"])[0] == 0
    assert evals.run_command(["false"])[0] == 1
    rc, detail = evals.run_command(["definitely-not-a-real-binary-xyz"])
    assert rc == -2
    assert detail


def test_run_command_reports_a_timeout_distinctly() -> None:
    """A timeout must not be indistinguishable from a non-zero exit."""
    rc, detail = evals.run_command(["sleep", "5"], timeout=1)
    assert rc == -1
    assert "timed out" in detail


# --- mise redaction legibility ------------------------------------------------
#
# The parse-and-judge half is driven through a stubbed `run_command` so the
# verdict does not depend on whatever secrets the host's mise config happens to
# hold. The real `mise env --redacted` round-trip is covered by this case's
# control arm in `test_eval_cases.py`, which writes a throwaway mise.toml.

#: A stand-in long enough to clear REDACTION_COLLISION_FLOOR by a wide margin.
_LONG = "a-genuinely-long-credential-value-36ch"


def _redaction_reader(
    monkeypatch: pytest.MonkeyPatch, rc: int, output: str, stderr: str = ""
) -> None:
    """Stub the SPLIT reader — the probe deliberately never sees combined output.

    ``stderr`` defaults to empty and is a real parameter, not decoration: the
    defect this shape replaced was a benign warning on stderr being concatenated
    into the JSON payload, so a test must be able to put something there and see
    the verdict NOT change.
    """
    monkeypatch.setattr(evals, "run_command_split", lambda *_a, **_k: (rc, output, stderr))


def _redaction_json(monkeypatch: pytest.MonkeyPatch, entries: dict[str, str]) -> None:
    _redaction_reader(monkeypatch, 0, json.dumps(entries))


def test_a_short_redacted_value_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """The observed damage: a redacted `1` rewrote every digit mise printed."""
    _redaction_json(monkeypatch, {"TELEMETRY_FLAG": "1", "REAL_TOKEN": _LONG})
    outcome = evals.mise_redaction_legible()
    assert outcome.verdict is evals.Verdict.FAIL
    assert "shortest=1" in outcome.detail


def test_a_failure_names_the_offending_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A length alone is not actionable; a NAME is, and a name is not a secret.

    This is also what lets the control arm prove its canary loaded rather than
    having tripped over some short host secret (silent-failure lane, F2).
    """
    _redaction_json(monkeypatch, {"TELEMETRY_FLAG": "1", "REAL_TOKEN": _LONG})
    detail = evals.mise_redaction_legible().detail
    assert "TELEMETRY_FLAG" in detail
    assert "REAL_TOKEN" not in detail, "only the SHORT ones are named"


def test_long_redacted_values_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTROL ARM for the above: the same probe says yes to a safe set."""
    _redaction_json(monkeypatch, {"A": _LONG, "B": _LONG + "-more"})
    assert evals.mise_redaction_legible().verdict is evals.Verdict.PASS


def test_a_stderr_warning_does_not_change_the_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """The unit-level arm for the stderr-corruption defect.

    A benign warning alongside a perfectly good payload must be inert. The
    end-to-end arm against real `mise` is below; this one pins the contract at the
    layer where the bug lived, so it cannot come back via a different caller.
    """
    _redaction_reader(
        monkeypatch, 0, json.dumps({"A": _LONG}), stderr="mise WARN unknown field: settings.x"
    )
    assert evals.mise_redaction_legible().verdict is evals.Verdict.PASS


def test_an_empty_value_is_ignored_because_mise_filters_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A zero-length value masks NOTHING, so flagging it would be a false positive.

    `Redactor::new` drops empty patterns before building the automaton —
    `filter(|p| !p.is_empty())`, jdx/mise `src/redactions.rs:31` at tag
    v2026.7.15. This test exists because the first version treated 0 as the
    shortest-and-worst value, and this host's fnox set really does hold an empty
    `LANGSMITH_WORKSPACE_ID`, so the false positive was one config change away.

    Reading the source is what caught it; the docs do not say this.
    """
    _redaction_json(monkeypatch, {"EMPTY_ONE": "", "REAL_TOKEN": _LONG})
    outcome = evals.mise_redaction_legible()
    assert outcome.verdict is evals.Verdict.PASS
    assert "EMPTY_ONE" not in outcome.detail


def test_a_short_but_nonempty_value_beside_an_empty_one_still_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTROL ARM for the above: the empty exclusion must not swallow a real one.

    Written the obvious wrong way — `if size and size < floor` over a `min()` of
    all lengths — the reported `shortest` would be 0 and the name list empty.
    """
    _redaction_json(monkeypatch, {"EMPTY_ONE": "", "FLAG": "1", "REAL_TOKEN": _LONG})
    outcome = evals.mise_redaction_legible()
    assert outcome.verdict is evals.Verdict.FAIL
    assert "FLAG" in outcome.detail
    assert "EMPTY_ONE" not in outcome.detail
    # The reported `shortest` must be the shortest OFFENDING value, not the
    # shortest value overall. Reported `shortest=0` before this assertion existed
    # — an excluded value still setting the headline number, which is how a
    # correct exclusion produces an incorrect report.
    assert "shortest=1" in outcome.detail


def test_an_all_empty_redaction_set_passes_and_says_why(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Variables present, every value empty: nothing to mask, and it says so.

    Distinct from the no-variables PASS, because the two have different causes and
    a reader chasing a masked digit needs to know which one they are looking at.
    """
    _redaction_json(monkeypatch, {"EMPTY_ONE": "", "EMPTY_TWO": ""})
    outcome = evals.mise_redaction_legible()
    assert outcome.verdict is evals.Verdict.PASS
    assert "every value empty" in outcome.detail


def test_a_multiline_value_is_measured_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    """A PEM block is ONE value, not one per line.

    The first version read `--values` and split on newlines, so every line of a
    multiline secret was measured independently and a short line produced a false
    FAIL — while mise's own match is against the whole value. Found by the cold
    review lane; reading `--json` makes it structurally impossible.
    """
    pem = "-----BEGIN KEY-----\nab\ncd\n-----END KEY-----"
    _redaction_json(monkeypatch, {"PEM": pem})
    assert evals.mise_redaction_legible().verdict is evals.Verdict.PASS


def test_an_empty_redaction_set_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mise cannot mask what it does not hold — that is verified-good, not SKIP.

    Observed, not inferred: `{}` is an empty MAPPING. The `--values` version
    inferred it from an absence of output, which is also what an unrelated silent
    failure looks like.
    """
    _redaction_json(monkeypatch, {})
    outcome = evals.mise_redaction_legible()
    assert outcome.verdict is evals.Verdict.PASS
    assert "no redacted values" in outcome.detail


def test_an_unreadable_redaction_set_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """A set that could not be READ is a third state, never rendered as clean.

    Distinct from the empty-set PASS above on purpose: both would otherwise be
    "no short values found", which is how a probe that never ran gets counted
    as one that found nothing.
    """
    _redaction_reader(monkeypatch, -2, "no such file or directory: mise")
    outcome = evals.mise_redaction_legible()
    assert outcome.verdict is evals.Verdict.SKIP
    assert "exited -2" in outcome.detail


def test_unparsable_output_skips_rather_than_passing(monkeypatch: pytest.MonkeyPatch) -> None:
    """rc=0 with output that is not JSON is unread, not clean.

    This is the shape an unrelated stderr line mixing into stdout produces, which
    the `--values` reader silently counted as redacted values.
    """
    _redaction_reader(monkeypatch, 0, "warning: something\nnot json at all")
    assert evals.mise_redaction_legible().verdict is evals.Verdict.SKIP


def test_a_json_scalar_skips_rather_than_crashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid JSON of the wrong SHAPE is still unread. `null` parses fine."""
    _redaction_reader(monkeypatch, 0, "null")
    assert evals.mise_redaction_legible().verdict is evals.Verdict.SKIP


def test_run_command_split_keeps_a_diagnostic_out_of_the_payload() -> None:
    """A parser must never receive a diagnostic where a payload should be.

    The bug this pins: `mise_redaction_legible` claimed a JSON mapping "cannot be
    corrupted by an unrelated stderr line" while reading COMBINED output, so one
    benign `mise WARN` — an unknown config key is enough — broke the parse and
    turned the detector into a permanent SKIP, triggered from a file nowhere near
    the probe. Found and armed by the silent-failure review lane.

    Driven through a real subprocess rather than a stub, because the stub is what
    hid it: every parse test monkeypatches `run_command`, so the concatenation was
    never exercised by any of them.
    """
    argv = [
        "python3",
        "-c",
        'import sys; sys.stderr.write("WARN unrelated\\n"); print(\'{"A": "x"}\')',
    ]
    rc, out, err = evals.run_command_split(argv)
    assert rc == 0
    assert json.loads(out) == {"A": "x"}, "stdout alone must parse"
    assert "WARN" in err, "the warning is still available, just not in the payload"
    # CONTROL ARM: the combining wrapper is exactly what used to break it.
    _, combined = evals.run_command(argv)
    with pytest.raises(json.JSONDecodeError):
        json.loads(combined)


def test_the_probe_survives_a_stderr_warning_from_the_real_command(
    tmp_path: Path,
) -> None:
    """End to end, against real `mise`: a warning must not become "unreadable".

    The tempdir config declares an unknown settings key, which mise reports on
    stderr while still exiting 0 and still emitting valid JSON on stdout.
    """
    if shutil.which("mise") is None:
        pytest.skip("mise does not resolve on PATH")
    (tmp_path / "mise.toml").write_text(
        "[settings]\nnot_a_real_setting = true\n\n"
        '[env]\n_TEST_LONG = { value = "a-genuinely-long-credential-value", redact = true }\n'
    )
    outcome = evals.mise_redaction_legible(cwd=tmp_path)
    assert outcome.verdict is not evals.Verdict.SKIP, (
        f"a benign stderr warning degraded the probe to unreadable: {outcome.detail}"
    )


def test_the_probe_never_prints_the_redacted_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """The values ARE the secrets, so only names, counts and lengths may appear.

    Checked on ALL FOUR paths, and the two error paths are the point: the first
    version embedded 200 chars of raw combined output in its SKIP detail while
    PASS and FAIL were clean, so a `mise` that wrote partial values to stdout and
    then exited non-zero would have leaked them into the eval report. Found by the
    cold review lane, which is the only lane sharing no weights with the author.

    (The fixture is spelled as a joined literal because ruff's S105 reads a
    credential-shaped string assignment as a hardcoded password — correctly, and
    this repo takes no inline suppressions.)
    """
    leaked = "do-not-print-" + "this-value-anywhere"
    _redaction_json(monkeypatch, {"SHORT": "1", "LONG": leaked})
    assert leaked not in evals.mise_redaction_legible().detail  # FAIL path
    _redaction_json(monkeypatch, {"LONG": leaked})
    assert leaked not in evals.mise_redaction_legible().detail  # PASS path
    _redaction_reader(monkeypatch, 1, f'{{"LONG": "{leaked}"}}')
    assert leaked not in evals.mise_redaction_legible().detail  # rc != 0 path
    _redaction_reader(monkeypatch, 0, f"partial {leaked} then a parse error")
    assert leaked not in evals.mise_redaction_legible().detail  # unparsable path


# --- doctor.sh shim -----------------------------------------------------------


def test_doctor_skips_loudly_when_the_script_is_absent(tmp_path: Path) -> None:
    """The plugin cache path is version-pinned and can vanish on GC.

    A silent skip here would be the inert declaration again: lane health
    "checked" by a check that never ran.
    """
    out = evals.doctor_health(tmp_path / "nope" / "doctor.sh")
    assert out.verdict is evals.Verdict.SKIP
    assert "doctor.sh not found" in out.detail
    assert "reinstall" in out.detail


def test_doctor_reports_a_failing_script_as_fail(tmp_path: Path) -> None:
    """CONTROL ARM: a doctor run that reports failures must be FAIL, not SKIP.

    Absent-script and failing-script are different states and the runner must
    not conflate them — one is "we could not look", the other is "we looked and
    a lane is broken".
    """
    script = tmp_path / "doctor.sh"
    script.write_text("#!/usr/bin/env bash\necho '0 ok, 0 warnings, 1 failures'\nexit 1\n")
    out = evals.doctor_health(script)
    assert out.verdict is evals.Verdict.FAIL
    assert "rc=1" in out.detail
    assert "1 failures" in out.detail


def test_doctor_reports_a_clean_script_as_pass(tmp_path: Path) -> None:
    """The positive arm, so the two above cannot pass on an always-FAIL shim."""
    script = tmp_path / "doctor.sh"
    script.write_text("#!/usr/bin/env bash\necho '3 ok, 1 warnings, 0 failures'\nexit 0\n")
    out = evals.doctor_health(script)
    assert out.verdict is evals.Verdict.PASS
    assert "rc=0" in out.detail


# --- declared-vs-installed reconciliation -------------------------------------


def test_all_lanes_resolving_passes(tmp_path: Path) -> None:
    out = evals.declared_lanes_reconcile(["sh"], fallback_doc=tmp_path / "x.md", fallback_tokens=())
    assert out.verdict is evals.Verdict.PASS


def test_an_absent_lane_passes_when_its_degradation_path_is_declared(tmp_path: Path) -> None:
    """This is the `grok` case, and it must stay PASSING.

    The doctrine's position is that availability is discovered at run time, not
    declared. So an absent lane is not itself the defect — an absent lane with
    no written fallback is.
    """
    doc = tmp_path / "routing.md"
    doc.write_text("grok is not installed; fall back to codex, then Claude Opus.\n")
    out = evals.declared_lanes_reconcile(
        ["definitely-not-a-real-binary-xyz"],
        fallback_doc=doc,
        fallback_tokens=("fall back",),
    )
    assert out.verdict is evals.Verdict.PASS
    assert "degradation path IS" in out.detail


def test_an_absent_lane_fails_when_no_degradation_path_is_declared(tmp_path: Path) -> None:
    """CONTROL ARM: the case above must be able to fail, or it proves nothing."""
    doc = tmp_path / "routing.md"
    doc.write_text("we route implementation to grok.\n")
    out = evals.declared_lanes_reconcile(
        ["definitely-not-a-real-binary-xyz"],
        fallback_doc=doc,
        fallback_tokens=("fall back",),
    )
    assert out.verdict is evals.Verdict.FAIL
    assert "fall back" in out.detail


def test_an_absent_lane_fails_when_the_fallback_doc_is_missing(tmp_path: Path) -> None:
    """A doc we cannot read must never resolve to "the fallback is declared"."""
    out = evals.declared_lanes_reconcile(
        ["definitely-not-a-real-binary-xyz"],
        fallback_doc=tmp_path / "gone.md",
        fallback_tokens=("fall back",),
    )
    assert out.verdict is evals.Verdict.FAIL
    assert "does not exist" in out.detail


# --- the graphify canary ------------------------------------------------------


def test_graphify_canary_skips_without_a_graph(tmp_path: Path) -> None:
    """graph.json is gitignored and derived — absence on a clone is expected."""
    out = evals.graphify_canary(tmp_path, "anything")
    assert out.verdict is evals.Verdict.SKIP
    assert "no graph at" in out.detail


def test_graphify_canary_separates_broken_from_empty(tmp_path: Path) -> None:
    """rc!=0 and "rc=0 but nothing" are different defects, reported differently.

    The second is the one that matters: a graph that resolves and answers
    nothing reads as health from the outside, which is this harness's whole
    subject.
    """
    graph = tmp_path / "graphify-out" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text("{}")

    empty = tmp_path / "empty-bin"
    empty.mkdir()
    (empty / "graphify").write_text("#!/usr/bin/env bash\nexit 0\n")
    (empty / "graphify").chmod(0o755)

    broken = tmp_path / "broken-bin"
    broken.mkdir()
    (broken / "graphify").write_text("#!/usr/bin/env bash\necho boom >&2\nexit 3\n")
    (broken / "graphify").chmod(0o755)

    import os

    old = os.environ["PATH"]
    try:
        os.environ["PATH"] = f"{empty}:{old}"
        out = evals.graphify_canary(tmp_path, "q")
        assert out.verdict is evals.Verdict.FAIL
        assert "answers nothing" in out.detail

        os.environ["PATH"] = f"{broken}:{old}"
        out = evals.graphify_canary(tmp_path, "q")
        assert out.verdict is evals.Verdict.FAIL
        assert "rc=3" in out.detail
    finally:
        os.environ["PATH"] = old


def test_graphify_canary_passes_on_a_real_answer(tmp_path: Path) -> None:
    """The positive arm: rc=0 with output is the only green."""
    graph = tmp_path / "graphify-out" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text("{}")
    good = tmp_path / "good-bin"
    good.mkdir()
    (good / "graphify").write_text("#!/usr/bin/env bash\necho 'node: X'\n")
    (good / "graphify").chmod(0o755)

    import os

    old = os.environ["PATH"]
    try:
        os.environ["PATH"] = f"{good}:{old}"
        out = evals.graphify_canary(tmp_path, "q")
        assert out.verdict is evals.Verdict.PASS
        assert "rc=0" in out.detail
    finally:
        os.environ["PATH"] = old


# --- rendering ----------------------------------------------------------------


def test_render_names_an_unarmed_case_as_refused() -> None:
    """The operator must be able to tell "refused to count" from "failed"."""
    report = evals.run_cases([_case(evals.ok("f"), control=None)])
    text = evals.render(report)
    assert "UNARMED" in text
    assert "REFUSED TO COUNT" in text


def test_the_green_summary_line_is_unchanged_when_nothing_failed() -> None:
    """The exact string other things quote as evidence. Pinned deliberately."""
    text = evals.render(evals.run_cases([_case(evals.ok("fine"))]))
    assert "OK eval: 1 passed, 0 skipped, 0 failed, 0 unarmed" in text


def test_an_advisory_failure_is_counted_in_the_summary_not_papered_over() -> None:
    """The run is rc=0 and one case FAILED. Both facts must survive rendering.

    Before this, the OK branch printed literal zeroes for failed/unarmed, which
    was true only while every case was gated. The first advisory case would have
    printed "0 failed" over a real failure — the "could not check rendered as
    green" collapse this module refuses everywhere else.
    """
    report = evals.run_cases([_case(evals.fail("advisory problem"), gated=False)])
    assert not report.red
    text = evals.render(report)
    assert "OK eval: 0 passed, 0 skipped, 1 failed, 0 unarmed" in text
    assert "ADVISORY" in text


def test_a_dead_advisory_control_arm_is_rendered_not_just_recorded() -> None:
    """`_advisory_detail` promised this was "surfaced"; nothing rendered it.

    The string went into `Result.control_detail`, whose only readers were two
    unit tests — so an advisory case with a broken control arm printed
    byte-comparably to a healthy pass, in the module whose own docstring forbids
    exactly that collapse. Found by the silent-failure review lane on the commit
    that added this repo's first advisory case and thereby made the path
    reachable at all.
    """
    case = evals.Case(
        name="tier1.demo-advisory",
        description="d",
        probe=lambda: evals.ok("looks fine"),
        control=lambda: evals.ok("did not fail"),
        gated=False,
    )
    text = evals.render(evals.run_cases([case]))
    assert "NOT ARMED" in text, "a dead control arm must not be invisible"
    assert "tier1.demo-advisory" in text.split("OK eval:")[1], "named in the summary too"


def test_a_live_advisory_control_arm_does_not_trip_the_not_armed_warning() -> None:
    """CONTROL ARM for the above: the loud line must not fire on a healthy case.

    Without this, `render` could unconditionally print NOT ARMED and the test
    above would still pass — a warning that is always on is not a warning.

    This replaces `..._says_nothing_extra`, which asserted the healthy case
    printed NOTHING and thereby PINNED the very collapse the next test measures.
    A test can lock in a defect while looking like a control arm.
    """
    case = evals.Case(
        name="tier1.demo-advisory",
        description="d",
        probe=lambda: evals.ok("looks fine"),
        control=lambda: evals.fail("armed"),
        gated=False,
    )
    text = evals.render(evals.run_cases([case]))
    assert "NOT ARMED" not in text
    assert "control arm failed as required" in text


def test_all_three_advisory_control_arm_states_render_distinctly() -> None:
    """A never-asked control arm must not read like one that was asked and said no.

    Round 1 of review: the control-arm string was recorded and no renderer read
    it, so a DEAD arm was invisible. Round 2: the fix read only the NOT-ARMED
    marker, so `control arm not required` — meaning no control arm exists at all —
    rendered BYTE-IDENTICALLY to `control arm failed as required`. The silent-
    failure lane measured that identity both times.

    So this asserts the three states are mutually distinct, which is stronger
    than asserting any one of them appears: it is the property that actually
    failed twice, and it cannot be satisfied by a renderer that prints a constant.
    """

    def case(control: Callable[[], evals.Outcome] | None) -> evals.Case:
        return evals.Case(
            name="tier1.demo-advisory",
            description="d",
            probe=lambda: evals.ok("looks fine"),
            control=control,
            gated=False,
        )

    absent = evals.render(evals.run_cases([case(None)]))
    armed = evals.render(evals.run_cases([case(lambda: evals.fail("broke as required"))]))
    dead = evals.render(evals.run_cases([case(lambda: evals.ok("did not fail"))]))

    assert absent != armed, "no control arm at all must not read like a verified one"
    assert armed != dead
    assert absent != dead
    assert "control arm not required" in absent
    assert "control arm failed as required" in armed
    assert "NOT ARMED" in dead


def test_a_gated_cases_control_detail_is_not_dumped_into_the_report() -> None:
    """The advisory scoping is deliberate, not an oversight — pinned so it stays.

    A GATED case cannot hide a dead control arm: the runner refuses to count it,
    the verdict becomes UNARMED and the run goes red. So there is nothing to
    surface, and surfacing it anyway buries the report — the guard-fixture control
    arm's detail is the whole inverted table, about 4 KB on a single line. That
    is what the first version of this fix did.
    """
    report = evals.run_cases([_case(evals.ok("fine"), control=evals.fail("a" * 500))])
    text = evals.render(report)
    assert report.results[0].control_detail, "the runner still RECORDS it"
    assert "a" * 500 not in text, "but a gated case's control detail is not printed"


def test_the_not_armed_marker_is_not_printed_twice() -> None:
    """The detail already carries the marker; prefixing it repeated the token.

    Observed verbatim as `NOT ARMED: advisory — NOT ARMED: control arm returned
    PASS…`. Loud-direction, so not a silent failure — but the line exists to be
    read, and a stutter is how a reader learns to stop reading it.
    """
    case = evals.Case(
        name="tier1.demo-advisory",
        description="d",
        probe=lambda: evals.ok("looks fine"),
        control=lambda: evals.ok("did not fail"),
        gated=False,
    )
    case_line = next(
        line for line in evals.render(evals.run_cases([case])).splitlines() if "advisory — " in line
    )
    assert case_line.count("NOT ARMED") == 1, case_line


def test_the_dead_arm_summary_does_not_claim_a_pass_that_may_not_exist() -> None:
    """The case's verdict can be SKIP or FAIL; the summary said "its PASS above"."""
    case = evals.Case(
        name="tier1.demo-advisory",
        description="d",
        probe=lambda: evals.skip("could not look"),
        control=lambda: evals.ok("did not fail"),
        gated=False,
    )
    text = evals.render(evals.run_cases([case]))
    assert "NOT ARMED" in text
    assert "its PASS above" not in text


def test_an_advisory_failure_is_caveated_even_on_a_red_run() -> None:
    """`report.failed` counts every FAIL; `report.red` counts only gated ones.

    So a red run's `FAIL eval: N failed` silently folds advisory failures into
    the gated count. The caveat used to live inside the green branch only.
    """
    report = evals.run_cases(
        [
            _case(evals.fail("a gated problem"), gated=True),
            _case(evals.fail("an advisory problem"), gated=False),
        ]
    )
    assert report.red
    text = evals.render(report)
    assert "FAIL eval:" in text
    assert "ADVISORY failure(s) included in the count above" in text


# --- tier 2: guard fixture tables ---------------------------------------------
#
# The engine's whole job is to catch a guard that cannot discriminate, so these
# tests drive it with the two degenerate guards explicitly. Both must produce a
# RED run — an always-deny guard passes the deny rows, an always-allow guard
# passes the allow rows, and each looks healthy from its own half of the table.

_DENY = evals.Decision.DENY
_ALLOW = evals.Decision.ALLOW

_TABLE = (
    evals.GuardFixture("gh pr create --fill", _DENY, "has a canonical task"),
    evals.GuardFixture("git status --short", _ALLOW, "an ordinary command"),
)


def _discriminating(command: str) -> str | None:
    return "use the task" if command.startswith("gh pr create") else None


def _always_deny(_command: str) -> str | None:
    return "denied"


def _always_allow(_command: str) -> str | None:
    return None


def test_a_discriminating_guard_passes_its_table() -> None:
    outcome = evals.run_guard_table(_TABLE, _discriminating)
    assert outcome.verdict is evals.Verdict.PASS
    assert "1 deny, 1 allow" in outcome.detail


def test_a_discriminating_guard_fails_the_inverted_table() -> None:
    """The control arm, stated directly: inverting the expectations must FAIL.

    This is what makes the table-level arm legitimate rather than an exemption
    from principle 1 — each row is the other rows' control.
    """
    outcome = evals.run_guard_table(_TABLE, _discriminating, invert=True)
    assert outcome.verdict is evals.Verdict.FAIL
    assert "inverted table" in outcome.detail


def test_an_always_deny_guard_fails_the_table_on_its_allow_row() -> None:
    """False positives are the only defect class ever measured in these guards."""
    outcome = evals.run_guard_table(_TABLE, _always_deny)
    assert outcome.verdict is evals.Verdict.FAIL
    assert "git status --short" in outcome.detail
    assert "expected ALLOW, saw DENIED" in outcome.detail


def test_an_always_allow_guard_fails_the_table_on_its_deny_row() -> None:
    outcome = evals.run_guard_table(_TABLE, _always_allow)
    assert outcome.verdict is evals.Verdict.FAIL
    assert "gh pr create --fill" in outcome.detail
    assert "expected DENY, saw ALLOWED" in outcome.detail


def test_a_mismatch_reports_the_reason_it_actually_saw() -> None:
    """Principle 8: surface the status seen, never a prose summary of it."""
    outcome = evals.run_guard_table(_TABLE, _always_deny)
    assert "denied" in outcome.detail  # the guard's own reason, echoed back
    assert "an ordinary command" in outcome.detail  # the row's `why`


def test_a_deny_only_table_is_rejected() -> None:
    """The must-ALLOW half is enforced, not merely recommended.

    Without this the always-deny guard above would pass a deny-only corpus and
    the harness would certify the one direction that has never failed.
    """
    deny_only = tuple(f for f in _TABLE if f.expected is _DENY)
    outcome = evals.run_guard_table(deny_only, _always_deny)
    assert outcome.verdict is evals.Verdict.FAIL
    assert "single-direction" in outcome.detail
    assert "must-ALLOW" in outcome.detail


def test_an_allow_only_table_is_rejected() -> None:
    allow_only = tuple(f for f in _TABLE if f.expected is _ALLOW)
    outcome = evals.run_guard_table(allow_only, _always_allow)
    assert outcome.verdict is evals.Verdict.FAIL
    assert "single-direction" in outcome.detail
    assert "must-DENY" in outcome.detail


def test_an_empty_table_is_rejected() -> None:
    """An empty table is a probe that cannot fail — the shape principle 1 bans."""
    outcome = evals.run_guard_table((), _discriminating)
    assert outcome.verdict is evals.Verdict.FAIL
    assert "EMPTY" in outcome.detail


def test_guard_table_case_is_armed_and_green_on_a_real_guard() -> None:
    case = evals.guard_table_case("tier2.x", "d", _TABLE, _discriminating)
    report = evals.run_cases([case])
    assert not report.red, evals.render(report)
    assert report.passed == 1


def test_guard_table_case_goes_red_for_both_degenerate_guards() -> None:
    """The composite property, end to end through the runner.

    Neither degenerate guard may reach a green run, and neither may reach it by
    the back door of being marked UNARMED-but-ignored: `Report.red` is true for
    UNARMED too, so both paths are covered by the same assertion.
    """
    for guard in (_always_deny, _always_allow):
        report = evals.run_cases([evals.guard_table_case("tier2.x", "d", _TABLE, guard)])
        assert report.red, f"{guard.__name__} reached a green run"


# --- tier 2: golden retrieval sets --------------------------------------------
#
# The scorer's own control arm lives here, and it is the load-bearing one: a
# matcher that never counts a hit reports recall 0 for every query, which is
# indistinguishable from retrieval being broken. So these tests drive it with a
# retriever that DOES return the target, one that returns nothing, and one that
# returns a target the corpus does not contain.

_NAT = evals.Phrasing.NATURAL
_ECH = evals.Phrasing.ECHO
_ABS = evals.Phrasing.ABSENT


def _golden(
    *,
    natural_targets: tuple[str, ...] = ("wanted.md",),
    echo_targets: tuple[str, ...] | None = None,
    k: int = 3,
    echo_k: int | None = None,
    absent: bool = True,
) -> tuple[evals.GoldenQuery, ...]:
    """A minimal well-formed golden set, with each defect switchable on."""
    rows = [
        evals.GoldenQuery("topic", _NAT, "how does one do the thing?", natural_targets, k),
        evals.GoldenQuery(
            "topic",
            _ECH,
            "the thing, phrased as the label",
            echo_targets or natural_targets,
            echo_k or k,
        ),
    ]
    if absent:
        rows.append(evals.GoldenQuery("gone", _ABS, "something not held here", ("gone.md",), k))
    return tuple(rows)


def _returns(*sources: str) -> evals.Retrieve:
    """A retriever that always returns the same ranked list."""
    return lambda _query: (0, list(sources))


def _one(
    retrieve: evals.Retrieve, present: evals.Membership | None = None
) -> tuple[evals.Arm, ...]:
    """The single-arm case — what most of these tests exercise.

    Named rather than inlined so the multi-arm tests below stand out as the ones
    measuring the before/after, and the rest read as scorer tests that happen to
    need one corpus.
    """
    return (evals.Arm("only", retrieve, present=present),)


def test_a_hit_inside_k_is_counted() -> None:
    """The direction that must work, or every 0 below means nothing."""
    outcome = evals.retrieval_recall(
        _golden(), _one(_returns("noise.py", "wanted.md", "more.py")), stamp="test corpus"
    )
    assert outcome.verdict is evals.Verdict.PASS, outcome.detail
    assert "natural@3 1/1" in outcome.detail
    assert "test corpus" in outcome.detail


def test_a_hit_below_k_is_a_miss() -> None:
    """CONTROL ARM for the above: k is a real window, not decoration."""
    outcome = evals.retrieval_recall(
        _golden(k=2), _one(_returns("a.py", "b.py", "wanted.md")), stamp="test corpus"
    )
    assert outcome.verdict is evals.Verdict.PASS, outcome.detail
    assert "natural@2 0/1" in outcome.detail


def test_the_pair_gap_is_reported() -> None:
    """The gap between the phrasings IS the finding, so it must be printed."""

    def retrieve(query: evals.GoldenQuery) -> tuple[int, list[str]]:
        return 0, (["wanted.md"] if query.phrasing is _ECH else ["noise.py"])

    outcome = evals.retrieval_recall(_golden(), _one(retrieve), stamp="test corpus")
    assert "natural@3 0/1" in outcome.detail
    assert "echo@3 1/1" in outcome.detail
    assert "gap +1" in outcome.detail


def test_an_all_zero_run_says_it_cannot_show_discrimination() -> None:
    """Honesty about what a flat 0 does and does not establish."""
    outcome = evals.retrieval_recall(_golden(), _one(_returns("noise.py")), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.PASS
    assert "nothing scored at all" in outcome.detail


def test_a_negative_query_that_comes_back_positive_fails() -> None:
    """The matcher lying is a harness defect, and never a retrieval win."""
    outcome = evals.retrieval_recall(_golden(), _one(_returns("gone.md")), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "NEGATIVE direction" in outcome.detail


def test_a_golden_set_with_no_negative_direction_is_rejected() -> None:
    """The sibling of the single-direction guard table, and the same defect."""
    outcome = evals.retrieval_recall(
        _golden(absent=False), _one(_returns("wanted.md")), stamp="test corpus"
    )
    assert outcome.verdict is evals.Verdict.FAIL
    assert "NO negative direction" in outcome.detail


def test_a_topic_missing_a_phrasing_is_rejected() -> None:
    """One number cannot show a gap, so a half-pair is not a measurement."""
    queries = (
        evals.GoldenQuery("topic", _NAT, "q", ("wanted.md",), 3),
        evals.GoldenQuery("gone", _ABS, "q", ("gone.md",), 3),
    )
    outcome = evals.retrieval_recall(queries, _one(_returns("wanted.md")), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "missing its ECHO half" in outcome.detail


def test_a_pair_whose_halves_disagree_is_rejected() -> None:
    """Two answers to different questions cannot be subtracted.

    Both ways the halves can drift apart — different targets, different k — are
    checked, because either one silently turns the reported gap into noise.
    """
    different_targets = evals.retrieval_recall(
        _golden(echo_targets=("other.md",)), _one(_returns("wanted.md")), stamp="test corpus"
    )
    assert different_targets.verdict is evals.Verdict.FAIL
    assert "not comparable" in different_targets.detail

    different_k = evals.retrieval_recall(
        _golden(echo_k=9), _one(_returns("wanted.md")), stamp="test corpus"
    )
    assert different_k.verdict is evals.Verdict.FAIL
    assert "not comparable" in different_k.detail


def test_an_empty_golden_set_is_rejected() -> None:
    outcome = evals.retrieval_recall((), _one(_returns("x")), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "EMPTY" in outcome.detail


def test_a_query_that_did_not_run_fails_rather_than_scoring_zero() -> None:
    """A broken query path reported as recall 0 would be a fabricated number."""
    outcome = evals.retrieval_recall(_golden(), _one(lambda _q: (-2, [])), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "rc=-2" in outcome.detail


def test_a_graph_that_returns_nothing_fails() -> None:
    """rc=0 with an empty list is a corpus that resolves and knows nothing."""
    outcome = evals.retrieval_recall(_golden(), _one(_returns()), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "returned NOTHING" in outcome.detail


def test_fixture_rot_is_caught_in_both_directions() -> None:
    """A renamed target reads as a retrieval failure forever without this."""
    queries = _golden()
    missing_positive = evals.retrieval_recall(
        queries,
        _one(_returns("wanted.md"), present=lambda names: {n: n != "wanted.md" for n in names}),
        stamp="test corpus",
    )
    assert missing_positive.verdict is evals.Verdict.FAIL
    assert "NOT in the corpus" in missing_positive.detail

    ingested_negative = evals.retrieval_recall(
        queries,
        _one(_returns("wanted.md"), present=lambda names: dict.fromkeys(names, True)),
        stamp="test corpus",
    )
    assert ingested_negative.verdict is evals.Verdict.FAIL
    assert "PRESENT but declared absent" in ingested_negative.detail


def test_a_sound_fixture_passes_the_integrity_check() -> None:
    """CONTROL ARM: without this, an always-FAIL integrity check passes above."""
    outcome = evals.retrieval_recall(
        _golden(),
        _one(_returns("wanted.md"), present=lambda names: {n: n != "gone.md" for n in names}),
        stamp="test corpus",
    )
    assert outcome.verdict is evals.Verdict.PASS, outcome.detail


# --- corpus membership (the fixture-integrity oracle) -------------------------


def test_corpus_has_discriminates_present_from_absent(tmp_path: Path) -> None:
    graph = tmp_path / "graph.json"
    graph.write_text('{"nodes": [{"source_file": "here.md"}, {"source_file":"compact.md"}]}')
    found = evals.corpus_has(graph, ["here.md", "compact.md", "nowhere.md"])
    assert found == {"here.md": True, "compact.md": True, "nowhere.md": False}


def test_corpus_has_finds_a_needle_split_across_two_reads(tmp_path: Path) -> None:
    """The overlap is the whole reason this is not a naive per-chunk scan.

    Without it a target that straddles a read boundary reports ABSENT, which
    would surface as fixture rot on a graph that is perfectly fine — a false
    negative produced entirely by the probe's own buffering.
    """
    graph = tmp_path / "graph.json"
    graph.write_text("x" * 40 + '{"source_file": "straddle.md"}' + "y" * 40)
    assert evals.corpus_has(graph, ["straddle.md"], chunk=8) == {"straddle.md": True}


def test_corpus_has_ignores_a_bare_mention_that_is_not_a_source(tmp_path: Path) -> None:
    """Precision matters in one direction: a mention is not membership.

    A document whose PROSE names another file would otherwise make a rotten
    fixture look sound, and the recall 0 that follows would be read as a
    retrieval failure.
    """
    graph = tmp_path / "graph.json"
    graph.write_text('{"label": "see also cerebras.md", "source_file": "other.md"}')
    assert evals.corpus_has(graph, ["cerebras.md"]) == {"cerebras.md": False}


def test_an_absent_row_that_returned_nothing_still_fails() -> None:
    """An ABSENT row must come back with no HITS, never with no RESULTS.

    Exempting the negative rows from the emptiness check was proposed in review
    of PR #30 and rejected here in code: a retriever that returns nothing would
    then satisfy every negative row trivially — the can-only-pass shape the
    negative direction exists to prevent. This pins the distinction, since the
    two readings are one word apart in prose and opposite in effect.
    """

    def retrieve(query: evals.GoldenQuery) -> tuple[int, list[str]]:
        return (0, []) if query.expects_absent else (0, ["wanted.md"])

    outcome = evals.retrieval_recall(_golden(), _one(retrieve), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "returned NOTHING" in outcome.detail
    assert "gone/ABSENT" in outcome.detail


# --- multi-arm runs: the before/after IS the measurement ----------------------
#
# One run, one query set, N corpora. The tests below are about the property that
# makes that trustworthy: every arm is scored and CHECKED independently, so a
# second corpus cannot ride the first one's numbers.


def _sound(names: Sequence[str]) -> dict[str, bool]:
    """A membership oracle agreeing with `_golden()`: positives in, negative out."""
    return {n: n != "gone.md" for n in names}


def _arm(name: str, *sources: str) -> evals.Arm:
    """An arm whose retriever always returns the same ranked list."""
    return evals.Arm(name, _returns(*sources))


def test_two_arms_are_reported_side_by_side_with_a_delta() -> None:
    """The shape knowledge-base#12 needs: before, after, and the difference.

    Hand-comparing two separate runs is the inherited-number trap — a later
    session cannot reproduce a subtraction that was never written down. So the
    delta is produced by the run that measured both sides.
    """
    outcome = evals.retrieval_recall(
        _golden(),
        (_arm("full", "noise.py"), _arm("scoped", "wanted.md")),
        stamp="test corpus",
    )
    assert outcome.verdict is evals.Verdict.PASS, outcome.detail
    assert "[full]" in outcome.detail
    assert "[scoped]" in outcome.detail
    assert "DELTA full -> scoped: natural 0 -> 1 of 1 pair(s)" in outcome.detail


def test_a_single_arm_run_prints_no_delta() -> None:
    """CONTROL ARM: the delta line is a comparison, not decoration.

    An implementation that always printed one would satisfy the test above while
    subtracting an arm from itself.
    """
    outcome = evals.retrieval_recall(_golden(), _one(_returns("wanted.md")), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.PASS, outcome.detail
    assert "DELTA" not in outcome.detail


def test_a_defect_in_either_arm_fails_the_whole_run() -> None:
    """Both directions, because "checks the last arm" also passes one of them.

    A second corpus that leaks the absent target — or a first one that does —
    must be named. Whichever arm is silently unchecked, the number printed for
    it is a lie, and it is the arm under test that is most likely to be the new
    one.
    """
    second_leaks = evals.retrieval_recall(
        _golden(),
        (_arm("full", "wanted.md"), _arm("scoped", "gone.md")),
        stamp="test corpus",
    )
    assert second_leaks.verdict is evals.Verdict.FAIL
    assert "[scoped]" in second_leaks.detail

    first_leaks = evals.retrieval_recall(
        _golden(),
        (_arm("full", "gone.md"), _arm("scoped", "wanted.md")),
        stamp="test corpus",
    )
    assert first_leaks.verdict is evals.Verdict.FAIL
    assert "[full]" in first_leaks.detail


def test_a_silent_second_corpus_is_not_hidden_by_a_healthy_first() -> None:
    """A graph that resolves and knows nothing, in the arm nobody was watching."""
    outcome = evals.retrieval_recall(
        _golden(),
        (_arm("full", "wanted.md"), _arm("scoped")),
        stamp="test corpus",
    )
    assert outcome.verdict is evals.Verdict.FAIL
    assert "[scoped]" in outcome.detail
    assert "returned NOTHING" in outcome.detail


def test_each_arm_checks_fixture_rot_against_its_own_corpus() -> None:
    """A target present in one corpus and absent from the other is rot in one.

    With a single shared oracle the scoped arm would be checked against the
    unscoped graph, where every target trivially exists — so a positive target
    the scoping filter dropped would report recall 0 forever and read as a
    retrieval failure rather than the fixture defect it is.
    """
    outcome = evals.retrieval_recall(
        _golden(),
        (
            evals.Arm("full", _returns("wanted.md"), present=_sound),
            evals.Arm(
                "scoped", _returns("wanted.md"), present=lambda names: dict.fromkeys(names, False)
            ),
        ),
        stamp="test corpus",
    )
    assert outcome.verdict is evals.Verdict.FAIL
    assert "[scoped]" in outcome.detail
    assert "NOT in the corpus" in outcome.detail


def test_both_arms_sound_passes_the_per_arm_integrity_check() -> None:
    """CONTROL ARM for the above: an always-FAIL integrity check would pass it."""
    outcome = evals.retrieval_recall(
        _golden(),
        (
            evals.Arm("full", _returns("wanted.md"), present=_sound),
            evals.Arm("scoped", _returns("wanted.md"), present=_sound),
        ),
        stamp="test corpus",
    )
    assert outcome.verdict is evals.Verdict.PASS, outcome.detail


def test_a_run_with_no_arms_is_rejected() -> None:
    """Zero corpora is zero measurements, and must never print a table."""
    outcome = evals.retrieval_recall(_golden(), (), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "no retrieval arm" in outcome.detail


def test_two_arms_sharing_a_name_are_rejected() -> None:
    """Unattributable rows are worse than no comparison — they still print."""
    outcome = evals.retrieval_recall(
        _golden(),
        (_arm("same", "wanted.md"), _arm("same", "noise.py")),
        stamp="test corpus",
    )
    assert outcome.verdict is evals.Verdict.FAIL
    assert "share a name" in outcome.detail


# --- the recall floor (knowledge-base#12, P2) ---------------------------------


def _pairs(count: int) -> tuple[evals.GoldenQuery, ...]:
    """``count`` positive pairs, each with its own target, plus one negative.

    `_golden()` yields a single pair, which cannot express "the best arm cleared
    a floor of 2" — so the floor tests get a set they can actually breach.
    """
    return (
        *(
            evals.GoldenQuery(f"t{i}", phrasing, f"q{i}", (f"want{i}.md",), 3)
            for i in range(count)
            for phrasing in (_NAT, _ECH)
        ),
        evals.GoldenQuery("gone", _ABS, "q", ("gone.md",), 3),
    )


def _scores(name: str, topics: int) -> evals.Arm:
    """An arm that finds the target of the first ``topics`` pairs and nothing else.

    Always returns a non-empty list, so `_arm_defect`'s silent-corpus check does
    not fire and the floor is the only thing under test.
    """

    def retrieve(query: evals.GoldenQuery) -> tuple[int, list[str]]:
        if query.expects_absent:
            return 0, ["filler.md"]
        findable = {f"want{i}.md" for i in range(topics)}
        return 0, [*(t for t in query.must_appear if t in findable), "filler.md"]

    return evals.Arm(name, retrieve)


def test_the_floor_passes_when_the_best_arm_clears_it() -> None:
    """The direction that must work, or every FAIL below means nothing."""
    outcome = evals.retrieval_recall(_pairs(2), (_scores("only", 2),), stamp="c", floor=2)
    assert outcome.verdict is evals.Verdict.PASS, outcome.detail
    assert "FLOOR: best arm [only] scored 2 of 2 natural pair(s), floor is 2" in outcome.detail


def test_the_floor_fails_when_no_arm_clears_it() -> None:
    """CONTROL ARM for the above: the floor is a gate, not a printed number.

    Without this the test above would pass for an implementation that computed
    the line and never compared it.
    """
    outcome = evals.retrieval_recall(_pairs(2), (_scores("only", 1),), stamp="c", floor=2)
    assert outcome.verdict is evals.Verdict.FAIL
    assert "REGRESSED below the floor" in outcome.detail


def test_the_floor_reads_the_best_arm_not_the_last() -> None:
    """P2 is why: the newest arm is not the best one, and the floor guards the best.

    `prose+rrf` scores below `prose+idf` on the real corpus, so a floor read off
    the LAST arm would redden a run whose best retrieval path never regressed.
    The weaker arm is placed last here for exactly that reason — an
    implementation reading ``results[-1]`` fails this test.
    """
    outcome = evals.retrieval_recall(
        _pairs(2), (_scores("best", 2), _scores("newest", 0)), stamp="c", floor=2
    )
    assert outcome.verdict is evals.Verdict.PASS, outcome.detail
    assert "best arm [best]" in outcome.detail


def test_a_floor_breach_is_reported_with_the_table_that_produced_it() -> None:
    """A bare "recall regressed" costs the next session a 4-minute re-run."""
    outcome = evals.retrieval_recall(_pairs(2), (_scores("only", 0),), stamp="c", floor=1)
    assert outcome.verdict is evals.Verdict.FAIL
    assert "[only]" in outcome.detail
    assert "natural@3 0/1" in outcome.detail


def test_an_arm_defect_outranks_a_floor_breach() -> None:
    """A broken arm must never be reported as a recall regression.

    Both conditions hold here — the retriever returns nothing, so it breaches any
    floor AND is a dead query path. Reporting the floor would send the reader
    hunting for a topic that moved when the real answer is that nothing ran.
    """
    outcome = evals.retrieval_recall(_pairs(2), _one(_returns()), stamp="c", floor=1)
    assert outcome.verdict is evals.Verdict.FAIL
    assert "returned NOTHING at all" in outcome.detail
    assert "REGRESSED" not in outcome.detail


def test_no_floor_reports_without_asserting() -> None:
    """CONTROL ARM for the floor existing at all: None must not gate.

    This is the shape the case shipped with from PR #30 through P1, and it has to
    stay reachable — an engine that always applied a floor would have made the
    0/119 baseline unreportable.
    """
    outcome = evals.retrieval_recall(_pairs(2), (_scores("only", 0),), stamp="c")
    assert outcome.verdict is evals.Verdict.PASS, outcome.detail
    assert "FLOOR" not in outcome.detail


@pytest.mark.parametrize("floor", [0, -1])
def test_a_floor_below_one_is_rejected(floor: int) -> None:
    """The check that can only pass: a run returning nothing would clear it."""
    outcome = evals.retrieval_recall(_pairs(2), (_scores("only", 2),), stamp="c", floor=floor)
    assert outcome.verdict is evals.Verdict.FAIL
    assert "can only pass" in outcome.detail


def test_a_floor_above_the_pair_count_is_rejected() -> None:
    """The same defect wearing the opposite sign: a check that can only fail."""
    outcome = evals.retrieval_recall(_pairs(2), (_scores("only", 2),), stamp="c", floor=3)
    assert outcome.verdict is evals.Verdict.FAIL
    assert "no run can ever clear it" in outcome.detail
