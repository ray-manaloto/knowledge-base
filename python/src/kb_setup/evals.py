"""Eval runner — tier-1 reachability probes and tier-2 fixtures, control arms enforced.

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

import itertools
import shutil
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
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
        name: Stable identifier, ``tier<N>.<what>``.
        description: What the case asserts, in one line.
        probe: The real check.
        control: The FAIL-direction arm. Runs the same logic against broken
            input and MUST return FAIL. Required for every gated case — see the
            module docstring. ``None`` is legal only for an advisory case.
        gated: Whether a FAIL makes the run red.
        live: Whether the case spends a real API call. Off by default; the
            offline set is what joins the ship gates.
        slow: Whether the case costs minutes rather than seconds. Off by
            default, and a SEPARATE axis from ``live``: a case can be free and
            still far too slow to sit on every ship (the golden retrieval set
            reloads a ~350 MB graph once per query). A slow gate is one people
            learn to skip, so it stays behind its own flag.
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
    slow: bool = False
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


# --- tier 2: guard fixture tables ---------------------------------------------


class Decision(StrEnum):
    """What a guard is expected to do with one command.

    An enum rather than a bool: a fixture table is read far more often than it
    is written, and ``("npx agnix", True)`` does not say which direction ``True``
    is. (It also keeps 30-odd rows out of ruff's boolean-positional rule without
    spelling ``deny=`` on every one.)
    """

    DENY = auto()
    ALLOW = auto()

    @property
    def inverted(self) -> Decision:
        """The other decision — the table-level control arm's whole mechanism."""
        return Decision.ALLOW if self is Decision.DENY else Decision.DENY


@dataclass(frozen=True)
class GuardFixture:
    """One ``(command, expected decision)`` row of a guard fixture table.

    Args:
        command: The Bash command string, exactly as a session would issue it.
        expected: :attr:`Decision.DENY` or :attr:`Decision.ALLOW`.
        why: One line saying what this row is defending. It is printed on a
            mismatch, so a future reader learns what broke rather than only
            which string moved.
    """

    command: str
    expected: Decision
    why: str


def run_guard_table(
    fixtures: Sequence[GuardFixture],
    decide: Callable[[str], str | None],
    *,
    invert: bool = False,
) -> Outcome:
    """Drive every row through ``decide`` and report the rows that disagreed.

    ``decide`` is the guard's decision function: a redirect reason for a denied
    command, ``None`` for an allowed one. Each repo passes its own.

    THE MUST-ALLOW HALF IS MANDATORY, and it is enforced here rather than left
    to authorial discipline: a single-direction table FAILS. False positives are
    the only defect class ever measured in these guards (dotfiles #265: 2 of the
    3 denials it had ever issued were false positives; bypasses all-time **0**),
    so a deny-only corpus grades the guard on the direction that has never
    failed — and, worse, an always-deny guard would pass it.

    THE CONTROL ARM IS TABLE-LEVEL (``invert=True``), not per-row. Inverting
    every expectation makes each row the other rows' control: an always-deny
    guard passes the deny rows and fails the allow rows, an always-allow guard
    does the inverse, so only a *discriminating* guard can pass the table while
    failing its inversion. Per-row cases were rejected — N controls to maintain,
    several of which could only be unrealistic mutations of the rule table.

    Args:
        fixtures: The repo's declared rows.
        decide: The guard's pure decision function.
        invert: Flip every expectation. This is the control arm, and it MUST
            come back FAIL for the case to count.
    """
    if not fixtures:
        return fail("guard fixture table is EMPTY — nothing was checked")

    denies = sum(1 for f in fixtures if f.expected is Decision.DENY)
    allows = len(fixtures) - denies
    if not denies or not allows:
        missing = "must-ALLOW" if not allows else "must-DENY"
        degenerate = "always-deny" if not allows else "always-allow"
        return fail(
            f"guard fixture table is single-direction ({denies} deny, {allows} "
            f"allow) — it has no {missing} half, so a degenerate {degenerate} "
            f"guard would pass it"
        )

    mismatches = []
    for fixture in fixtures:
        expected = fixture.expected.inverted if invert else fixture.expected
        reason = decide(fixture.command)
        actual = Decision.DENY if reason is not None else Decision.ALLOW
        if actual is expected:
            continue
        saw = f"DENIED ({reason.splitlines()[0][:60]})" if reason else "ALLOWED"
        mismatches.append(
            f"{fixture.command[:70]!r} expected {expected.name}, saw {saw} [{fixture.why}]"
        )

    scope = f"{len(fixtures)} row(s) ({denies} deny, {allows} allow)"
    if mismatches:
        return fail(
            f"{len(mismatches)}/{len(fixtures)} row(s) mismatched"
            f"{' (inverted table)' if invert else ''}: " + "; ".join(mismatches)
        )
    return ok(f"{scope} decided as declared{' (inverted table)' if invert else ''}")


def guard_table_case(
    name: str,
    description: str,
    fixtures: Sequence[GuardFixture],
    decide: Callable[[str], str | None],
) -> Case:
    """A gated :class:`Case` for one guard's fixture table, control arm attached.

    The control is the same table with every expectation inverted, so the
    control-arm rule in :func:`run_cases` polices this table by construction
    instead of the table being exempted from principle 1 — which was the one
    thing that could not be allowed here, since this table is the single place
    false positives have actually been measured.
    """
    return Case(
        name=name,
        description=description,
        probe=lambda: run_guard_table(fixtures, decide),
        control=lambda: run_guard_table(fixtures, decide, invert=True),
    )


# --- tier 2: golden retrieval sets --------------------------------------------


class Phrasing(StrEnum):
    """How a golden query is worded — which is the whole experiment.

    ``NATURAL`` is how someone who has NOT read the target would ask.
    ``ECHO`` deliberately borrows the target's own label text. The pair is
    reported side by side because THE GAP BETWEEN THEM IS THE FINDING: measured
    2026-07-24, a label-echoing query surfaced prose nodes that its natural twin
    did not, so a set built only of echoes grades lexical overlap and reports a
    retrieval win that is not there.

    ``ABSENT`` is the negative direction: a query whose declared target is not
    in the corpus at all, so the target must NOT be among what comes back.
    Without it the set measures "returns something" rather than "returns the
    right thing".

    Read that precisely — an ABSENT row must come back with **no HITS**, not
    with no RESULTS. It still asks the graph a real question and the graph still
    answers; a row that returned nothing at all is a broken query path, and it
    fails (see :func:`retrieval_recall`). Exempting ABSENT rows from that check
    was proposed in review of PR #30 and rejected: a retriever that returns
    nothing would then satisfy every negative row trivially, which is the
    can-only-pass shape the negative direction exists to prevent.
    """

    NATURAL = auto()
    ECHO = auto()
    ABSENT = auto()


@dataclass(frozen=True)
class GoldenQuery:
    """One golden query: what was asked, what must come back, how far down we look.

    Args:
        topic: Pair identifier. The ``NATURAL`` and ``ECHO`` rows of one topic
            must declare the SAME targets and the same ``k`` — otherwise the
            two numbers are not comparable and their difference means nothing.
        phrasing: See :class:`Phrasing`.
        query: The question, verbatim as it is sent to the retriever.
        must_appear: The relevant units, as the retriever names them. Node
            **ids** are not usable here: this graph's ids are 300+ characters of
            repeated repo name and are not printed by ``graphify query``, while
            the source document is stable and IS printed. A prose chunk's
            identity is its source, so a hit means "some node from this
            document came back".
        k: How far down the returned list a hit counts. Per-query, because a
            broad question and a pointed one do not deserve the same window.
    """

    topic: str
    phrasing: Phrasing
    query: str
    must_appear: tuple[str, ...]
    k: int = 10

    @property
    def expects_absent(self) -> bool:
        """True for the negative direction, where a hit is the failure."""
        return self.phrasing is Phrasing.ABSENT


@dataclass(frozen=True)
class RetrievalRow:
    """One golden query's measurement — the raw counts, never a prose summary."""

    query: GoldenQuery
    rc: int
    returned: int
    hits: tuple[str, ...]

    @property
    def recall(self) -> float:
        """Fraction of declared targets that appeared in the top ``k``."""
        if not self.query.must_appear:
            return 0.0
        return len(self.hits) / len(self.query.must_appear)

    @property
    def summary(self) -> str:
        """``1/2`` — hits over declared targets, at this query's ``k``."""
        return f"{len(self.hits)}/{len(self.query.must_appear)}"


#: A retriever: given a golden query, return ``(rc, the units it returned, in
#: rank order)``. The caller supplies it — the live one shells out to graphify,
#: and the tests supply a fake, which is how the scorer itself gets a control arm.
Retrieve = Callable[[GoldenQuery], tuple[int, Sequence[str]]]

#: A corpus-membership oracle: which of these target names exist in the graph at
#: all? Used only for fixture integrity — see :func:`retrieval_recall`.
Membership = Callable[[Sequence[str]], Mapping[str, bool]]


@dataclass(frozen=True)
class Arm:
    """One retrieval configuration the golden set is run against.

    An arm is a CORPUS plus the retriever that reads it, which is why the
    membership oracle lives here and not on the run: a target present in one
    arm's corpus and absent from another's is fixture rot in the second arm
    only, and a single shared oracle would report the first arm's answer for
    both.

    Two or more arms are run over the SAME queries and reported side by side,
    so the difference between them is attributable to the arm and nothing else.
    That is the whole design: the first arm is the baseline and each later one
    is a change whose effect is the delta (knowledge-base#12 — the prose-scoped
    corpus against the unscoped one).

    Args:
        name: How the arm is labelled in the report. Must be unique in a run.
        retrieve: Runs one query against this arm's corpus. See :data:`Retrieve`.
        present: Optional corpus-membership oracle for THIS arm's corpus.
    """

    name: str
    retrieve: Retrieve
    present: Membership | None = None


def corpus_has(
    graph_path: Path, needles: Sequence[str], *, chunk: int = 1 << 22
) -> dict[str, bool]:
    """Which of ``needles`` appear as a ``source_file`` value in the graph file?

    A streaming substring scan rather than ``json.load``: the graph is ~350 MB
    of pretty-printed JSON and parsing it costs gigabytes of resident memory for
    an answer this shape does not need. Measured at 0.3s over 128k nodes.

    Matches the KEYED form (``"source_file": "<needle>"``) in both the spaced
    and compact separator styles, so a bare mention of the filename inside some
    document's prose does NOT read as membership. That precision is load-bearing
    in one direction: a positive target that is merely *mentioned* would make
    fixture rot look like a retrieval failure.
    """
    keyed = {n: (f'"source_file": "{n}"', f'"source_file":"{n}"') for n in needles}
    found = dict.fromkeys(needles, False)
    overlap = max((len(v) for pair in keyed.values() for v in pair), default=0)
    tail = ""
    with graph_path.open(encoding="utf-8", errors="replace") as fh:
        while block := fh.read(chunk):
            buf = tail + block
            for needle, forms in keyed.items():
                if not found[needle] and any(form in buf for form in forms):
                    found[needle] = True
            if all(found.values()):
                break
            tail = buf[-overlap:] if overlap else ""
    return found


def score_retrieval(query: GoldenQuery, retrieve: Retrieve) -> RetrievalRow:
    """Run one golden query and count which declared targets came back in top-k."""
    rc, returned = retrieve(query)
    top = list(returned)[: query.k]
    hits = tuple(t for t in query.must_appear if t in top)
    return RetrievalRow(query=query, rc=rc, returned=len(returned), hits=hits)


def _golden_set_shape(queries: Sequence[GoldenQuery]) -> str:
    """Structural defects that make a golden set unable to measure. '' when sound.

    Enforced in the engine, exactly as ``run_guard_table`` refuses a
    single-direction table, and for the same reason: these are the shapes where
    a degenerate retriever passes.

    * No ABSENT query — a retriever that returns the whole corpus scores a
      perfect recall on every positive row.
    * A topic missing one of its phrasings — the pair IS the measurement; one
      number alone cannot show the lexical-overlap gap.
    * A pair whose halves declare different targets or a different ``k`` — then
      the two numbers are answers to different questions and their difference
      is noise.
    """
    if not queries:
        return "golden set is EMPTY — nothing was measured"
    if not any(q.expects_absent for q in queries):
        return (
            "golden set has NO negative direction (no ABSENT query) — it can only "
            "measure that something came back, so a retriever that returns the "
            "whole corpus would score perfectly"
        )
    pairs: dict[str, dict[Phrasing, GoldenQuery]] = {}
    for q in (q for q in queries if not q.expects_absent):
        pairs.setdefault(q.topic, {})[q.phrasing] = q
    for topic, halves in sorted(pairs.items()):
        missing = {Phrasing.NATURAL, Phrasing.ECHO} - set(halves)
        if missing:
            return (
                f"topic {topic!r} is missing its "
                f"{', '.join(sorted(p.name for p in missing))} half — the pair is "
                f"the measurement, since a lone number cannot show the gap"
            )
        natural, echo = halves[Phrasing.NATURAL], halves[Phrasing.ECHO]
        if natural.must_appear != echo.must_appear or natural.k != echo.k:
            return (
                f"topic {topic!r}: the two phrasings declare different targets or "
                f"a different k, so their recall figures are not comparable"
            )
    return ""


def _fixture_integrity(queries: Sequence[GoldenQuery], present: Membership) -> str:
    """Do the declared targets exist (positives) / not exist (ABSENT)? '' when sound.

    Fixture rot is indistinguishable from a retrieval failure without this: a
    positive target that has been renamed out of the corpus reports recall 0
    forever and reads as "retrieval is broken", while an ABSENT target that has
    since been ingested makes the negative direction unfalsifiable.
    """
    names = sorted({t for q in queries for t in q.must_appear})
    seen = present(names)
    rotten = [
        f"{q.topic}/{q.phrasing.name}: {target!r} is "
        f"{'PRESENT but declared absent' if q.expects_absent else 'NOT in the corpus'}"
        for q in queries
        for target in q.must_appear
        if seen.get(target, False) is q.expects_absent
    ]
    if rotten:
        return "fixture rot — " + "; ".join(rotten)
    return ""


def _pair_lines(rows: Sequence[RetrievalRow]) -> list[str]:
    """The per-topic table: natural and echo side by side, then the negatives."""
    by_topic: dict[str, dict[Phrasing, RetrievalRow]] = {}
    for row in rows:
        by_topic.setdefault(row.query.topic, {})[row.query.phrasing] = row
    lines = []
    for topic, halves in sorted(by_topic.items()):
        natural, echo = halves.get(Phrasing.NATURAL), halves.get(Phrasing.ECHO)
        if natural is not None and echo is not None:
            k = natural.query.k
            gap = len(echo.hits) - len(natural.hits)
            lines.append(
                f"    {topic:<22} natural@{k} {natural.summary}   echo@{k} {echo.summary}   "
                f"gap {gap:+d}"
            )
        lines.extend(
            f"    {topic:<22} ABSENT@{row.query.k} {row.summary} returned (0 is required)"
            for row in halves.values()
            if row.query.expects_absent
        )
    return lines


@dataclass(frozen=True)
class _ArmResult:
    """One arm's scored rows plus the two headline counts the delta line reads."""

    arm: Arm
    rows: tuple[RetrievalRow, ...]

    @property
    def natural(self) -> list[RetrievalRow]:
        """The NATURAL half of every positive pair."""
        return [
            r
            for r in self.rows
            if not r.query.expects_absent and r.query.phrasing is Phrasing.NATURAL
        ]

    @property
    def echo(self) -> list[RetrievalRow]:
        """The ECHO half of every positive pair."""
        return [
            r for r in self.rows if not r.query.expects_absent and r.query.phrasing is Phrasing.ECHO
        ]

    @property
    def scored(self) -> tuple[int, int]:
        """How many pairs scored at all, ``(natural, echo)``."""
        return sum(1 for r in self.natural if r.hits), sum(1 for r in self.echo if r.hits)


def _arms_shape(arms: Sequence[Arm]) -> str:
    """Structural defects in the ARM list. '' when sound.

    The sibling of :func:`_golden_set_shape`, and the same reasoning: a run with
    no arm measures nothing, and two arms sharing a name produce a report whose
    rows cannot be attributed — which is worse than no comparison, because it
    still prints numbers.
    """
    if not arms:
        return "no retrieval arm was declared — there is nothing to measure with"
    names = [a.name for a in arms]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        return (
            f"two or more arms share a name ({', '.join(duplicates)}) — the report "
            f"rows could not be attributed to a corpus"
        )
    return ""


def _arm_defect(result: _ArmResult) -> str:
    """Everything that would make this arm's number a lie. '' when sound."""
    rows, name = result.rows, result.arm.name
    broken = [f"{r.query.topic}/{r.query.phrasing.name} rc={r.rc}" for r in rows if r.rc != 0]
    if broken:
        return f"[{name}] {len(broken)} query/queries did not run: {', '.join(broken)}"
    # EVERY row, ABSENT included — `returned` counts what came back, not what
    # matched. An ABSENT row that returned nothing has not demonstrated the
    # target is absent; it has demonstrated the query path is dead, and it would
    # let a retriever that returns nothing pass every negative row.
    silent = [f"{r.query.topic}/{r.query.phrasing.name}" for r in rows if r.returned == 0]
    if silent:
        return (
            f"[{name}] {len(silent)} query/queries returned NOTHING at all "
            f"({', '.join(silent)}) — that is a graph that resolves and knows nothing"
        )
    leaked = [r for r in rows if r.query.expects_absent and r.hits]
    if leaked:
        return (
            f"[{name}] the NEGATIVE direction came back positive: "
            + "; ".join(f"{r.query.topic} returned {', '.join(r.hits)}" for r in leaked)
            + " — the target is declared absent from the corpus, so this is the "
            "matcher or the fixture lying, not a retrieval win"
        )
    return ""


def _arm_lines(result: _ArmResult) -> list[str]:
    """One arm's report block: its header, its table, and its SUITE summary."""
    natural, echo, scored = result.natural, result.echo, result.scored
    return [
        f"  [{result.arm.name}]",
        *_pair_lines(result.rows),
        f"    SUITE: {len(natural)} pair(s) — natural scored on {scored[0]}, "
        f"echo on {scored[1]}; mean recall natural "
        f"{_mean(r.recall for r in natural):.2f} vs echo "
        f"{_mean(r.recall for r in echo):.2f}",
    ]


def _delta_line(baseline: _ArmResult, other: _ArmResult) -> str:
    """The before/after line: what changed between two arms, in both phrasings.

    Printed by the runner rather than compared by hand across two invocations. A
    comparison a later session cannot reproduce is the inherited-number trap
    (``probes-need-a-control-arm.md`` rule 6) — so the two figures are produced
    by ONE run, over one query set, and their difference is stated here.
    """
    base_n, base_e = baseline.scored
    other_n, other_e = other.scored
    total = len(baseline.natural)
    return (
        f"  DELTA {baseline.arm.name} -> {other.arm.name}: "
        f"natural {base_n} -> {other_n} of {total} pair(s) "
        f"(mean {_mean(r.recall for r in baseline.natural):.2f} -> "
        f"{_mean(r.recall for r in other.natural):.2f}), "
        f"echo {base_e} -> {other_e} "
        f"(mean {_mean(r.recall for r in baseline.echo):.2f} -> "
        f"{_mean(r.recall for r in other.echo):.2f})"
    )


#: Below this many arms, the consecutive comparison IS the cumulative one, so a
#: cumulative line would repeat the consecutive line verbatim.
_ARMS_WITH_ONE_DELTA = 2


def _delta_lines(results: Sequence[_ArmResult]) -> list[str]:
    """Every delta the report owes the reader, and no duplicates.

    With two arms there is one comparison and it is both consecutive and
    cumulative, so exactly one line is printed — unchanged from PR #30.

    With three or more, printing only baseline→arm would leave the newest arm's
    OWN contribution unstated: `unscoped -> prose+idf` folds P0 and P1 together,
    and a reader wanting P1 alone would have to subtract two printed numbers by
    hand. That is precisely the inherited-number trap :func:`_delta_line` exists
    to close (`probes-need-a-control-arm.md` rule 6) — a figure nobody re-derived,
    with its provenance lost the moment it is restated. So each arm is also
    compared to its PREDECESSOR, which is the change that arm actually made.
    """
    consecutive = [_delta_line(a, b) for a, b in itertools.pairwise(results)]
    if len(results) <= _ARMS_WITH_ONE_DELTA:
        return consecutive
    return [*consecutive, _delta_line(results[0], results[-1])]


def _floor_problem(floor: int, queries: Sequence[GoldenQuery]) -> str:
    """Is this floor capable of both verdicts? '' when it is.

    Both directions are rejected, because both produce a check that prints a
    number and decides nothing:

    * ``floor < 1`` — every run clears it, including one where retrieval returned
      nothing at all. The check that can only pass.
    * ``floor`` above the number of positive pairs — no run can ever clear it.
      The check that can only fail, which is the same defect wearing the
      opposite sign (`hk.pkl`'s ``no_grep_q_under_pipefail`` is the local
      instance of it).
    """
    pairs = len({q.topic for q in queries if not q.expects_absent})
    if floor < 1:
        return (
            f"a natural-recall floor of {floor} is a check that can only pass — "
            f"a run returning nothing at all would clear it"
        )
    if floor > pairs:
        return (
            f"a natural-recall floor of {floor} exceeds the {pairs} positive "
            f"pair(s) in the golden set, so no run can ever clear it"
        )
    return ""


def _floor_verdict(floor: int, results: Sequence[_ArmResult]) -> tuple[str, str]:
    """``(the report line, the failure or '')`` for the recall floor.

    Asserted on the BEST arm rather than the last one, and that is the whole
    decision (locked with Ray 2026-07-27). What the floor guards is regression in
    the best retrieval path the KB actually has; the arm holding that path is not
    guaranteed to be the newest one, and this run is the proof — P2's `prose+rrf`
    scores BELOW `prose+idf`, so a floor on the last arm would have had zero
    headroom while the thing it exists to protect had one pair of it. Naming an
    arm instead would hard-code a string into the gate, so retiring or renaming
    that arm later would silently change what is being enforced.
    """
    best = max(results, key=lambda r: r.scored[0])
    scored, total = best.scored[0], len(best.natural)
    line = (
        f"  FLOOR: best arm [{best.arm.name}] scored {scored} of {total} natural "
        f"pair(s), floor is {floor}"
    )
    if scored < floor:
        return line, (
            f"natural-phrasing recall REGRESSED below the floor: the best arm "
            f"[{best.arm.name}] scored {scored} of {total} pair(s), floor is {floor}"
        )
    return line, ""


def _measure_arms(
    queries: Sequence[GoldenQuery], arms: Sequence[Arm]
) -> tuple[tuple[_ArmResult, ...], str]:
    """Score every arm. ``(results, '')`` when sound, ``((), problem)`` when not.

    The two checks run at deliberately different times, and the difference is not
    incidental:

    * **Fixture rot is checked before that arm is scored**, so a rotten first arm
      short-circuits before the expensive later ones run. Its targets are wrong,
      so nothing measured after it could be interpreted anyway.
    * **Arm defects are checked only once EVERY arm has been scored**, so the
      message can name all of them. Bailing on the first would report one broken
      arm and leave a second one to be discovered on the next 4-minute run.
    """
    results = []
    for arm in arms:
        if arm.present is not None:
            rot = _fixture_integrity(queries, arm.present)
            if rot:
                return (), f"[{arm.name}] {rot}"
        results.append(_ArmResult(arm, tuple(score_retrieval(q, arm.retrieve) for q in queries)))
    for defect in (_arm_defect(r) for r in results):
        if defect:
            return (), defect
    return tuple(results), ""


def retrieval_recall(
    queries: Sequence[GoldenQuery],
    arms: Sequence[Arm],
    *,
    stamp: str,
    floor: int | None = None,
) -> Outcome:
    """Measure recall@k over a golden set, once per arm.

    Beyond the optional ``floor``, this fails on everything that would make the
    number a lie — a broken query path, a graph that answers nothing, a rotten
    fixture, and the negative direction coming back positive. Those are harness
    defects, not retrieval quality, and they must never be reported as a recall
    figure. They are checked PER ARM: a second corpus that answers nothing must
    not hide behind the first one's numbers.

    Args:
        queries: The golden set. Its shape is checked (:func:`_golden_set_shape`).
        arms: The corpora to measure, in order, each one the previous plus a
            single change. Every arm is reported as a delta against its
            PREDECESSOR — which is the change that arm actually made — and with
            three or more arms a cumulative first-to-last line is printed as
            well. With two arms those coincide and exactly one line is emitted.
            See :class:`Arm` and :func:`_delta_lines`.
        stamp: The corpus stamp — build date and node count. Carried into the
            detail because a retrieval number without the corpus it was measured
            against is not a measurement (``probes-need-a-control-arm.md`` rule 6).
        floor: Minimum natural-phrasing pairs the BEST arm must score, or None to
            report without asserting. It stayed None from PR #30 through P1 for a
            reason worth keeping written down: the baseline this case exists to
            make citable is 0/119 relevant nodes (knowledge-base#12), and a floor
            set at or below a baseline of zero is the check that can only pass.
            A floor became meaningful only once P0-P2 had moved the number.
            See :func:`_floor_verdict` for why the best arm and not the last.
    """
    shape = _golden_set_shape(queries) or _arms_shape(arms)
    if not shape and floor is not None:
        shape = _floor_problem(floor, queries)
    if shape:
        return fail(shape)

    results, problem = _measure_arms(queries, arms)
    if problem:
        return fail(problem)

    floor_line, breach = ("", "")
    if floor is not None:
        floor_line, breach = _floor_verdict(floor, results)

    detail = "\n".join(
        [
            f"corpus: {stamp}",
            *(line for r in results for line in _arm_lines(r)),
            *_delta_lines(results),
            *([floor_line] if floor_line else []),
        ]
    )
    # AFTER the detail is assembled, so a breach is reported WITH the per-arm
    # table that produced it. A bare "recall regressed" line would leave the next
    # session re-running the 4-minute case just to see which topic moved.
    if breach:
        return fail(f"{breach}\n{detail}")
    if all(r.scored == (0, 0) for r in results):
        detail += (
            "\n  NOTE: nothing scored at all, so this run alone cannot show the "
            "matcher discriminates — that is proven by its unit tests, not here"
        )
    return ok(detail)


def _mean(values: Iterable[float]) -> float:
    """Mean of an iterable of floats, 0.0 when empty."""
    seq = list(values)
    return sum(seq) / len(seq) if seq else 0.0


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


def _cost_skip(case: Case, *, live: bool, slow: bool) -> Outcome | None:
    """The opt-in cost filters. Two independent axes: API spend, and wall clock."""
    if case.live and not live:
        return skip("live case — pass --live to run it")
    if case.slow and not slow:
        return skip("slow case — pass --slow to run it")
    return None


def _environment_skip(case: Case) -> Outcome | None:
    """Evaluate the ``precondition``, turning a raising gate into a FAIL."""
    if case.precondition is None:
        return None
    try:
        return case.precondition()
    except Exception as exc:
        return fail(f"precondition raised {type(exc).__name__}: {exc}")


def _advisory_detail(case: Case) -> str:
    """What to record about an advisory case's control arm.

    An advisory case is not REQUIRED to carry one — but when it declares one,
    run it and say so. "Advisory" waives the requirement, and must not become
    the loophole that exempts a case from ever demonstrating it can say no; a
    result reported without its control arm is an opinion
    (``probes-need-a-control-arm.md`` rule 5). A control that fails to fail is
    surfaced here rather than reddening the run, since an advisory case cannot
    turn the run red by construction.
    """
    if case.control is None:
        return "advisory — control arm not required"
    armed, detail = _control_verdict(case)
    return f"advisory — {detail}" if armed else f"advisory — NOT ARMED: {detail}"


def run_cases(cases: Sequence[Case], *, live: bool = False, slow: bool = False) -> Report:
    """Run every in-scope case, applying the control-arm rule first.

    Order of the gates matters and is pinned by tests: the cost filters
    (``live``, then ``slow``), then ``precondition``, then the control-arm rule.

    Args:
        cases: The repo's declared cases.
        live: Include cases that spend real API calls. Off by default, because
            the offline set is what joins the ship gates.
        slow: Include cases that cost minutes. Off by default for the same
            reason and on a separate axis — free but slow is still too
            expensive to run on every ship.
    """
    report = Report()
    for case in cases:
        cost = _cost_skip(case, live=live, slow=slow)
        if cost is not None:
            report.results.append(Result(case, cost))
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
        gate = _environment_skip(case)
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
            detail = _advisory_detail(case)

        try:
            outcome = case.probe()
        except Exception as exc:
            outcome = fail(f"probe raised {type(exc).__name__}: {exc}")
        report.results.append(Result(case, outcome, control_detail=detail))
    return report


def render(report: Report, *, live: bool = False, slow: bool = False) -> str:
    """Render the case table plus the summary line."""
    lines = [
        f"eval: {len(report.results)} case(s), live={'on' if live else 'off'}, "
        f"slow={'on' if slow else 'off'}"
    ]
    for r in report.results:
        flag = "gated" if r.case.gated else "advisory"
        lines.append(f"  {r.outcome.verdict.name:<8} {r.case.name} [{flag}]")
        # A multi-line detail (the retrieval table) keeps its own alignment
        # under a common indent rather than breaking out of the case block.
        lines.extend(f"           {line}" for line in r.outcome.detail.splitlines() or [""])
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


def run(cases: Sequence[Case], *, live: bool = False, slow: bool = False) -> tuple[int, str]:
    """Run the cases and return ``(exit_code, report)``."""
    report = run_cases(cases, live=live, slow=slow)
    text = render(report, live=live, slow=slow)
    if report.nothing_verifiable:
        # Nothing was checked. Not a pass, and not a silent one either.
        return 1, text
    return (1 if report.red else 0), text
