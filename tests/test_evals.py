"""Tests for the shared eval runner (kb_setup.evals).

The runner's whole reason for existing is that a case which can only pass is
decoration, so these tests are unusually literal about the FAIL direction: the
control-arm rule is itself control-armed here, in both directions.
"""

from __future__ import annotations

from pathlib import Path

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


def test_a_hit_inside_k_is_counted() -> None:
    """The direction that must work, or every 0 below means nothing."""
    outcome = evals.retrieval_recall(
        _golden(), _returns("noise.py", "wanted.md", "more.py"), stamp="test corpus"
    )
    assert outcome.verdict is evals.Verdict.PASS, outcome.detail
    assert "natural@3 1/1" in outcome.detail
    assert "test corpus" in outcome.detail


def test_a_hit_below_k_is_a_miss() -> None:
    """CONTROL ARM for the above: k is a real window, not decoration."""
    outcome = evals.retrieval_recall(
        _golden(k=2), _returns("a.py", "b.py", "wanted.md"), stamp="test corpus"
    )
    assert outcome.verdict is evals.Verdict.PASS, outcome.detail
    assert "natural@2 0/1" in outcome.detail


def test_the_pair_gap_is_reported() -> None:
    """The gap between the phrasings IS the finding, so it must be printed."""

    def retrieve(query: evals.GoldenQuery) -> tuple[int, list[str]]:
        return 0, (["wanted.md"] if query.phrasing is _ECH else ["noise.py"])

    outcome = evals.retrieval_recall(_golden(), retrieve, stamp="test corpus")
    assert "natural@3 0/1" in outcome.detail
    assert "echo@3 1/1" in outcome.detail
    assert "gap +1" in outcome.detail


def test_an_all_zero_run_says_it_cannot_show_discrimination() -> None:
    """Honesty about what a flat 0 does and does not establish."""
    outcome = evals.retrieval_recall(_golden(), _returns("noise.py"), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.PASS
    assert "nothing scored at all" in outcome.detail


def test_a_negative_query_that_comes_back_positive_fails() -> None:
    """The matcher lying is a harness defect, and never a retrieval win."""
    outcome = evals.retrieval_recall(_golden(), _returns("gone.md"), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "NEGATIVE direction" in outcome.detail


def test_a_golden_set_with_no_negative_direction_is_rejected() -> None:
    """The sibling of the single-direction guard table, and the same defect."""
    outcome = evals.retrieval_recall(
        _golden(absent=False), _returns("wanted.md"), stamp="test corpus"
    )
    assert outcome.verdict is evals.Verdict.FAIL
    assert "NO negative direction" in outcome.detail


def test_a_topic_missing_a_phrasing_is_rejected() -> None:
    """One number cannot show a gap, so a half-pair is not a measurement."""
    queries = (
        evals.GoldenQuery("topic", _NAT, "q", ("wanted.md",), 3),
        evals.GoldenQuery("gone", _ABS, "q", ("gone.md",), 3),
    )
    outcome = evals.retrieval_recall(queries, _returns("wanted.md"), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "missing its ECHO half" in outcome.detail


def test_a_pair_whose_halves_disagree_is_rejected() -> None:
    """Two answers to different questions cannot be subtracted.

    Both ways the halves can drift apart — different targets, different k — are
    checked, because either one silently turns the reported gap into noise.
    """
    different_targets = evals.retrieval_recall(
        _golden(echo_targets=("other.md",)), _returns("wanted.md"), stamp="test corpus"
    )
    assert different_targets.verdict is evals.Verdict.FAIL
    assert "not comparable" in different_targets.detail

    different_k = evals.retrieval_recall(
        _golden(echo_k=9), _returns("wanted.md"), stamp="test corpus"
    )
    assert different_k.verdict is evals.Verdict.FAIL
    assert "not comparable" in different_k.detail


def test_an_empty_golden_set_is_rejected() -> None:
    outcome = evals.retrieval_recall((), _returns("x"), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "EMPTY" in outcome.detail


def test_a_query_that_did_not_run_fails_rather_than_scoring_zero() -> None:
    """A broken query path reported as recall 0 would be a fabricated number."""
    outcome = evals.retrieval_recall(_golden(), lambda _q: (-2, []), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "rc=-2" in outcome.detail


def test_a_graph_that_returns_nothing_fails() -> None:
    """rc=0 with an empty list is a corpus that resolves and knows nothing."""
    outcome = evals.retrieval_recall(_golden(), _returns(), stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "returned NOTHING" in outcome.detail


def test_fixture_rot_is_caught_in_both_directions() -> None:
    """A renamed target reads as a retrieval failure forever without this."""
    queries = _golden()
    missing_positive = evals.retrieval_recall(
        queries,
        _returns("wanted.md"),
        stamp="test corpus",
        present=lambda names: {n: n != "wanted.md" for n in names},
    )
    assert missing_positive.verdict is evals.Verdict.FAIL
    assert "NOT in the corpus" in missing_positive.detail

    ingested_negative = evals.retrieval_recall(
        queries,
        _returns("wanted.md"),
        stamp="test corpus",
        present=lambda names: dict.fromkeys(names, True),
    )
    assert ingested_negative.verdict is evals.Verdict.FAIL
    assert "PRESENT but declared absent" in ingested_negative.detail


def test_a_sound_fixture_passes_the_integrity_check() -> None:
    """CONTROL ARM: without this, an always-FAIL integrity check passes above."""
    outcome = evals.retrieval_recall(
        _golden(),
        _returns("wanted.md"),
        stamp="test corpus",
        present=lambda names: {n: n != "gone.md" for n in names},
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

    outcome = evals.retrieval_recall(_golden(), retrieve, stamp="test corpus")
    assert outcome.verdict is evals.Verdict.FAIL
    assert "returned NOTHING" in outcome.detail
    assert "gone/ABSENT" in outcome.detail
