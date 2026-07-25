"""Eval runner — tier-1 reachability probes, with control arms enforced.

The SHARED runner both this repo and ``ray-manaloto/dotfiles`` use (the
``kb_setup.currency`` / ``kb_setup.md_budget`` precedent: one implementation,
never a second copy that drifts). Each repo declares its own cases and passes
them in; nothing repo-specific lives here.

WHY THIS EXISTS. dotfiles#354 is one defect class: a declaration made and never
observed. The orchestrator's trigger line was absent for weeks while the mode
line sat beside it looking like configuration. Tier 0 (``suites.toml``
contracts) answers "is it declared?". This module answers the next question —
**does it resolve?** A lane named in doctrine but whose CLI is absent, a graph
that answers nothing, a plugin script at a path that has been garbage-collected:
each is a declaration that reads as true and is not.

THE STRUCTURAL RULE (design principle 1). A case that can only pass is the
inert trigger one level up — the single most likely way an eval harness becomes
theatre. So the runner **refuses to count a gated case that has no recorded
failing fixture**. Every gated :class:`Case` carries a ``control``: a callable
that runs the same probe logic against deliberately-broken input and MUST come
back FAIL. If it is missing, or if it does not fail, the case is reported
``UNARMED`` and the run is red. This is ``probes-need-a-control-arm.md``
promoted from a habit an author might forget into a property the runner checks.

PRINCIPLE 8. Every probe surfaces the status it actually saw — an ``rc``, an
exit code, a count — never a prose summary of it. A gate that printed "PR create
failed" and dropped the HTTP status made a hard 500 indistinguishable from
flakiness, and it was retried three times before anyone looked.

SKIP IS LOUD AND IS NOT PASS. A probe that could not run reports SKIP with its
reason and is counted separately. A run of nothing-but-SKIPs is reported as
*not verifiable here*, never as green — the same discipline
``kb_setup.currency`` applies to DRIFT/SKIP/OK, and for the same reason:
collapsing "could not check" into "fine" is how every defect in that engine's
review happened.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum, auto
from pathlib import Path

#: Probes shell out to small, local commands. A probe that needs longer than
#: this is not a reachability probe.
DEFAULT_TIMEOUT = 60

#: The live lane checks each send one real API call, which is slow enough that
#: the offline default must never wait on them.
LIVE_TIMEOUT = 300


class Verdict(StrEnum):
    """The outcome of one case. ``UNARMED`` is a runner verdict, not a probe's.

    Values come from ``auto()`` (so they are the lowercased member names) rather
    than literal strings: a literal ``PASS = "PASS"`` trips ruff's
    hardcoded-password rule, and the display form belongs in the renderer, which
    uses ``.name``, not in the data.
    """

    PASS = auto()
    FAIL = auto()
    SKIP = auto()
    UNARMED = auto()


@dataclass(frozen=True)
class Outcome:
    """A verdict plus the status that produced it (principle 8)."""

    verdict: Verdict
    detail: str

    @property
    def ok(self) -> bool:
        """True only for PASS. SKIP is deliberately not ok — it is unverified."""
        return self.verdict is Verdict.PASS


def ok(detail: str) -> Outcome:
    """A passing outcome."""
    return Outcome(Verdict.PASS, detail)


def fail(detail: str) -> Outcome:
    """A failing outcome."""
    return Outcome(Verdict.FAIL, detail)


def skip(detail: str) -> Outcome:
    """Could not run. Reported loudly, counted separately, never green."""
    return Outcome(Verdict.SKIP, detail)


@dataclass(frozen=True)
class Case:
    """One eval case.

    Args:
        name: Stable identifier, ``tier1.<what>``.
        description: What the case asserts, in one line.
        probe: The real check.
        control: The FAIL-direction arm. Runs the same logic against broken
            input and MUST return FAIL. Required for every gated case — see the
            module docstring. ``None`` is legal only for an advisory case.
        gated: Whether a FAIL makes the run red.
        live: Whether the case spends a real API call. Off by default; the
            offline set is what joins the ship gates.
        precondition: Optional environment gate. Return a SKIP :class:`Outcome`
            when this case CANNOT APPLY here; return ``None`` to run normally.
            "Does not apply in this environment" is a third state, distinct
            from both "the probe failed" and "this case is live", and it must
            be checked BEFORE the control-arm rule — see :func:`run_cases`.
    """

    name: str
    description: str
    probe: Callable[[], Outcome]
    control: Callable[[], Outcome] | None = None
    gated: bool = True
    live: bool = False
    precondition: Callable[[], Outcome | None] | None = None


@dataclass
class Result:
    """One case's outcome after the runner has applied the control-arm rule."""

    case: Case
    outcome: Outcome
    control_detail: str = ""


@dataclass
class Report:
    """The outcome of one run."""

    results: list[Result] = field(default_factory=list)

    def _count(self, verdict: Verdict) -> int:
        return sum(1 for r in self.results if r.outcome.verdict is verdict)

    @property
    def passed(self) -> int:
        """Cases whose probe passed."""
        return self._count(Verdict.PASS)

    @property
    def failed(self) -> int:
        """Cases whose probe failed."""
        return self._count(Verdict.FAIL)

    @property
    def skipped(self) -> int:
        """Cases that could not run."""
        return self._count(Verdict.SKIP)

    @property
    def unarmed(self) -> int:
        """Gated cases the runner refused to count — a hard error."""
        return self._count(Verdict.UNARMED)

    @property
    def red(self) -> bool:
        """True when the run must fail the gate.

        An UNARMED case is red regardless of what its probe would have said:
        an uncontrolled gated case is indistinguishable from decoration, and
        counting it would be the exact defect this harness exists to catch.
        """
        if self.unarmed:
            return True
        return any(r.outcome.verdict is Verdict.FAIL and r.case.gated for r in self.results)

    @property
    def nothing_verifiable(self) -> bool:
        """Every case skipped — report that, never "green"."""
        return bool(self.results) and self.skipped == len(self.results)


# --- shelling out -------------------------------------------------------------


def run_command(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[int, str]:
    """Run ``argv``, returning ``(rc, combined output)``.

    Returns a synthetic negative rc rather than raising, so a probe always has
    a status to report (principle 8): ``-1`` timed out, ``-2`` the executable
    was not found. Callers surface these verbatim rather than translating them
    into prose.
    """
    try:
        proc = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return -1, f"timed out after {timeout}s"
    except (FileNotFoundError, PermissionError) as exc:
        return -2, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr)


# --- probe primitives ---------------------------------------------------------


def cli_present(name: str) -> Outcome:
    """Does ``name`` resolve on PATH?

    Resolution, not invocation: a lane's CLI existing is the cheap half, and
    whether it is authenticated is the live half (:func:`doctor_health`).
    """
    path = shutil.which(name)
    if path:
        return ok(f"{name} resolves at {path}")
    return fail(f"{name} does not resolve on PATH")


def declared_lanes_reconcile(
    declared: Sequence[str],
    *,
    fallback_doc: Path,
    fallback_tokens: Sequence[str],
) -> Outcome:
    """Every DECLARED lane either resolves, or its degradation path is written down.

    The doctrine's position is that "availability is discovered at run time, not
    declared", so this deliberately does NOT assert that every declared lane is
    installed. ``grok`` is named across the routing docs and is not installed;
    that is correct and must stay passing. What must NOT be true is a lane named
    with no recorded fallback — then the doctrine routes work to a lane that
    cannot run it and says nothing about what happens next.

    Args:
        declared: Lane CLI names the docs name.
        fallback_doc: The doc that must describe the degradation path.
        fallback_tokens: Tokens whose presence in that doc constitutes the
            degradation path being declared.
    """
    missing = [name for name in declared if shutil.which(name) is None]
    if not missing:
        return ok(f"all {len(declared)} declared lane(s) resolve: {', '.join(declared)}")
    if not fallback_doc.is_file():
        return fail(
            f"{len(missing)} declared lane(s) absent ({', '.join(missing)}) and "
            f"the fallback doc {fallback_doc.name} does not exist"
        )
    text = fallback_doc.read_text(errors="replace")
    absent = [tok for tok in fallback_tokens if tok not in text]
    if absent:
        return fail(
            f"lane(s) absent ({', '.join(missing)}) and {fallback_doc.name} does not "
            f"declare the degradation path — missing: {', '.join(absent)}"
        )
    return ok(
        f"lane(s) absent ({', '.join(missing)}) but the degradation path IS "
        f"declared in {fallback_doc.name}"
    )


def graphify_canary(
    repo_root: Path,
    question: str,
    *,
    graph: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Outcome:
    """A graph that exists must also ANSWER. rc=0 and non-empty output.

    The two halves are separate failures and are reported separately: a
    non-zero rc is a broken query path, while rc=0 with empty output is a graph
    that resolves and knows nothing — which reads as health from the outside
    and is the shape this whole harness exists to catch.

    SKIPs loudly when there is no graph to query: ``graphify-out/graph.json``
    is gitignored and derived, so its absence on a fresh clone is expected and
    is not a defect.
    """
    graph_path = graph if graph is not None else repo_root / "graphify-out" / "graph.json"
    if not graph_path.is_file():
        return skip(f"no graph at {graph_path} — run the build task first")
    rc, out = run_command(["graphify", "query", question], cwd=repo_root, timeout=timeout)
    if rc != 0:
        return fail(f"graphify query rc={rc}: {out.strip()[:200]}")
    if not out.strip():
        return fail("graphify query rc=0 but returned NOTHING — resolves, answers nothing")
    return ok(f"graphify query rc=0, {len(out.strip())} bytes returned")


def doctor_health(script: Path, *, timeout: int = LIVE_TIMEOUT) -> Outcome:
    """Shell out to the fable-orchestrator plugin's own ``doctor.sh``.

    ``use-tool-builtins.md`` hard gate: doctor already does lane presence plus
    LIVE auth and model access per CLI, and ships a permission canary whose pass
    condition is a nonce the model can only produce by actually executing a
    command. That canary is the control-arm principle at framework level and is
    better than anything reimplemented here.

    THIS IS THE LIVE HALF, ENTIRELY. doctor takes no flags and has no offline
    mode: whenever a lane's CLI is present it fires a real API call. So it can
    never be part of the free, gated tier — the offline probes above are.

    It exits ``[ FAIL -eq 0 ]``, so warnings pass and only a live-check failure
    fails; an absent CLI is a warning by its design, which is the right reading
    (a lane that is not installed degrades, per :func:`declared_lanes_reconcile`).

    SKIPs LOUDLY when the script is absent. Its path is version-pinned inside
    the plugin cache and can vanish on plugin GC, so "not there" must never be
    silent — a silently-skipped lane check is the inert declaration again.
    """
    if not script.is_file():
        return skip(
            f"doctor.sh not found at {script} — the plugin cache is version-pinned "
            f"and can vanish on GC; reinstall the fable-orchestrator plugin to "
            f"restore lane health checks"
        )
    rc, out = run_command(["bash", str(script)], timeout=timeout)
    tail = " | ".join(line.strip() for line in out.strip().splitlines()[-3:])
    if rc != 0:
        return fail(f"doctor.sh rc={rc}: {tail}")
    return ok(f"doctor.sh rc=0: {tail}")


# --- the runner ---------------------------------------------------------------


def _control_verdict(case: Case) -> tuple[bool, str]:
    """Run a case's control arm. Returns ``(armed, detail)``.

    Armed means the control actually FAILED, i.e. the probe logic can produce
    the other answer. Anything else — no control, a control that passes, a
    control that skips, a control that raises — leaves the case uncontrolled.
    """
    if case.control is None:
        return False, "no control arm declared"
    try:
        result = case.control()
    except Exception as exc:  # a control that crashes has not demonstrated FAIL
        return False, f"control arm raised {type(exc).__name__}: {exc}"
    if result.verdict is Verdict.FAIL:
        return True, f"control arm failed as required ({result.detail})"
    return False, (
        f"control arm returned {result.verdict.name}, not FAIL — the probe "
        f"cannot be shown to discriminate ({result.detail})"
    )


def run_cases(cases: Sequence[Case], *, live: bool = False) -> Report:
    """Run every in-scope case, applying the control-arm rule first.

    Order of the three gates matters and is pinned by tests: live-filter, then
    ``precondition``, then the control-arm rule.

    Args:
        cases: The repo's declared cases.
        live: Include cases that spend real API calls. Off by default, because
            the offline set is what joins the ship gates.
    """
    report = Report()
    for case in cases:
        if case.live and not live:
            report.results.append(Result(case, skip("live case — pass --live to run it")))
            continue

        # The environment gate comes BEFORE the control-arm rule, and that
        # ordering is load-bearing. A case that cannot apply here also cannot
        # have a working control arm — the control drives the same code path, so
        # it would skip too, the runner would mark the case UNARMED, and the run
        # would go red for a case that was never asked. Checking the
        # precondition first keeps "does not apply here" from masquerading as
        # "this gate is decoration".
        #
        # Learned from a real failure: dotfiles' graphify canary is host-only,
        # and inside the devcontainer it failed with rc=-2 (no such file),
        # turning the whole devcontainer smoke red.
        if case.precondition is not None:
            try:
                gate = case.precondition()
            except Exception as exc:
                gate = fail(f"precondition raised {type(exc).__name__}: {exc}")
            if gate is not None:
                report.results.append(Result(case, gate))
                continue

        if case.gated:
            armed, detail = _control_verdict(case)
            if not armed:
                # Refuse to COUNT it: an uncontrolled gated case is decoration,
                # and the probe's own answer is not evidence of anything.
                report.results.append(
                    Result(case, Outcome(Verdict.UNARMED, detail), control_detail=detail)
                )
                continue
        else:
            detail = "advisory — control arm not required"

        try:
            outcome = case.probe()
        except Exception as exc:
            outcome = fail(f"probe raised {type(exc).__name__}: {exc}")
        report.results.append(Result(case, outcome, control_detail=detail))
    return report


def render(report: Report, *, live: bool = False) -> str:
    """Render the case table plus the summary line."""
    lines = [f"eval: {len(report.results)} case(s), live={'on' if live else 'off'}"]
    for r in report.results:
        flag = "gated" if r.case.gated else "advisory"
        lines.append(f"  {r.outcome.verdict.name:<8} {r.case.name} [{flag}]")
        lines.append(f"           {r.outcome.detail}")
        if r.outcome.verdict is Verdict.UNARMED:
            lines.append(
                "           REFUSED TO COUNT: a gated case with no working control "
                "arm cannot be distinguished from decoration"
            )
    lines.append("")
    if report.nothing_verifiable:
        lines.append(
            f"NOT VERIFIABLE HERE: all {len(report.results)} case(s) skipped — this is not a pass"
        )
    elif report.red:
        lines.append(
            f"FAIL eval: {report.failed} failed, {report.unarmed} unarmed, "
            f"{report.passed} passed, {report.skipped} skipped"
        )
    else:
        lines.append(
            f"OK eval: {report.passed} passed, {report.skipped} skipped, 0 failed, 0 unarmed"
        )
    return "\n".join(lines)


def run(cases: Sequence[Case], *, live: bool = False) -> tuple[int, str]:
    """Run the cases and return ``(exit_code, report)``."""
    report = run_cases(cases, live=live)
    text = render(report, live=live)
    if report.nothing_verifiable:
        # Nothing was checked. Not a pass, and not a silent one either.
        return 1, text
    return (1 if report.red else 0), text
