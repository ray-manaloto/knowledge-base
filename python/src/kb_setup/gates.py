"""Run this repo's gates and record what actually happened — `mise run kb-gates`.

WHAT THIS REPLACES. `/clear-prep` step 5 tells you to redirect a gate to a file
and record `rc=$?`, so in-session the check IS performable — the premise that no
record exists was wrong, and #146's body was corrected to say so. What is true is
that **nothing enforces the step ran, and the file lives in `/tmp`**. By the time
anyone audits a handoff, the number in it is prose an agent retyped and the
artifact it came from is gone. Across 28 committed handoffs, 26 carry a gate
claim and none can be checked *now*. This is an EXPIRED artifact, not an absent
one, and the fix is a record that outlives the session rather than a new
instruction to be diligent.

WHY THE RECORD IS MACHINE-LOCAL. It lands under `.agent/kb/gates/`, the same
durability class as the `kb-review` receipt it sits beside: it survives the
session (the actual failure) and dies with the clone. Gate results are facts
about one machine at one commit — committing them would assert something about
every other machine that never ran them.

AN UNREACHED GATE IS RECORDED, NOT OMITTED. The ship path runs with
``stop_on_failure=True``, so its record is partial by construction. A partial
record whose unreached gates were simply missing would read as a complete pass,
which is this repo's oldest lesson — "could not check" is never rendered as green
— arriving in the artifact instead of in the logic. They appear with ``rc: null``.

THE RUNNER IS THE ONE `ship` ALREADY USED. :func:`_invoke` keeps `pr._stream`'s
INVOCATION exactly: one child, `mise run <task>`, inheriting this process's
stdio. No capture, no shell, no wrapper. That is #146's criterion 8, and it is
not stylistic — this repo has already paid for a substitution that swapped an
exec for a subprocess and silently gave away signal propagation, so the call that
was working is moved rather than rewritten, and a test pins the argv and kwargs.
Its failure *return values* do differ, deliberately; :func:`_invoke` says why.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kb_setup import atomic, resolve, review

#: Where a run's record lands. Listed in `agent-artifact-conventions.md`, which
#: forbids directories that are not.
GATES_DIR = Path(".agent") / "kb" / "gates"

#: Matches `pr`'s former `_GATE_TIMEOUT`. A gate that has not finished in half an
#: hour is wedged, and `long-running-command-hangs.md` says never wait blind.
_GATE_TIMEOUT = 1800

#: Bound on the two cheap git reads (`rev-parse`, `status`). Short on purpose:
#: these are metadata about the run, and a wedged one must not become the reason
#: the gates never happened.
_GIT_TIMEOUT = 30

#: rc for a gate that could not be STARTED or did not finish, kept distinct from
#: a gate that ran and failed. Both are non-zero — neither passes — but a record
#: whose whole job is being checkable later must not spell "mise is not on PATH"
#: the same way it spells "lint found something". The values follow the shell's
#: own conventions so they read without a legend.
_RC_TIMEOUT = 124
_RC_COULD_NOT_RUN = 127

_SHA_ABBREV = 12

#: The local gates every PR must pass before it is pushed — moved here from `pr`
#: (where it was `GATES`) so the ship path and `kb-gates` cannot drift into two
#: lists. `eval` is tiers 1+2 — reachability probes plus the guard fixture table,
#: offline and fast only, so it costs nothing here. Its two opt-in halves run on
#: demand: `-- --live` for the lane doctor (one API call per installed lane) and
#: `-- --slow` for the golden retrieval set (~3 min, advisory — it reports
#: recall@k, it does not gate).
#:
#: NOT EVERY OFFLINE CASE IS BINDING, and this comment used to imply otherwise by
#: scoping "advisory" to the `--slow` half alone. `tier1.mise-redaction-legible`
#: is offline, runs on every ship, and is `gated=False`: it reports and never
#: reddens, because its only remedy is a user-level mise config `do-not.md` #11
#: forbids editing. So a green `eval` gate here means "nothing GATED failed", not
#: "every case passed" — read the case table, not the rc. `evals.render` prints
#: the true failed/unarmed counts precisely so that distinction survives.
#:
#: Carried across the move verbatim rather than condensed. The first draft of the
#: move dropped the `--live`/`--slow` sentences, which is how a comment that took
#: two review rounds to get right decays into a summary of itself.
GATE_TASKS = ("lint", "test", "brain-audit", "eval")


@dataclass(frozen=True)
class GateResult:
    """One gate's outcome — the four things #146 names, plus ``dirty``.

    ``rc``/``sha``/``finished_at`` are all None together, and only together: that
    is the "not run" state, reachable only when an earlier gate failed under
    ``stop_on_failure``. A None ``rc`` is never a pass.

    ``dirty`` is the FIFTH field and is not in the ticket's list. It is here
    because without it the other four can combine into a false statement: "lint
    exited 0 at <sha>" is not true of that commit if the tree carried uncommitted
    changes when lint ran, and the whole point of the record is that a claim has
    something TRUE to be checked against. Recording the commit without recording
    whether the tree WAS that commit re-creates the defect one layer down. None
    when the gate did not run, or when git could not be read — "unknown", which is
    the third state and not the same as clean.
    """

    task: str
    rc: int | None
    sha: str | None
    finished_at: str | None
    dirty: bool | None = None

    @property
    def ran(self) -> bool:
        """Whether this gate produced a result — i.e. ran to COMPLETION.

        Not "was invoked at all", which is what this said and could not deliver.
        When a run is interrupted, the gate that was in flight has no result and
        is padded exactly like one that was never reached, so `rc=None` covers
        both "never started" and "started and did not finish". Those are genuinely
        indistinguishable from here — the interrupt can land inside `_invoke` or
        between gates — so the honest move is to claim the weaker thing rather
        than have the record assert a stronger one that is sometimes false.
        (Cold lane round 2, paired impl+test finding.)
        """
        return self.rc is not None

    @property
    def passed(self) -> bool:
        """Whether this gate completed AND exited 0. No result is never a pass."""
        return self.rc == 0

    @property
    def bound_to_a_commit(self) -> bool:
        """Whether a COMPLETED gate's result can be tied to a commit.

        A gate that ran while `git rev-parse` was transiently failing has a
        result and no commit to attach it to. That is not drift and not a
        failure; it is a row nobody can check later, which for this artifact is
        the one thing worth saying out loud. (Cold lane round 2.)
        """
        return not self.ran or bool(self.sha)


def head_sha(repo_root: Path) -> str:
    """HEAD's full SHA, or "" if git cannot be read.

    A named seam rather than a direct call: the tests pin it, and pinning
    `review.head_sha` itself would silently pin it for `review`'s own callers too.
    """
    return review.head_sha(repo_root)


def tree_dirty(repo_root: Path) -> bool | None:
    """Whether the working tree differs from HEAD; None if git could not be asked.

    Three states, not two, for the reason that recurs everywhere in this repo:
    "could not check" must never render as the clean answer. `git status
    --porcelain` is silent on both a clean tree and a failed invocation, so the
    rc is read rather than the output alone.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT,
        )
    except OSError, subprocess.SubprocessError, UnicodeDecodeError:
        # UnicodeDecodeError is neither of the other two — `text=True` decodes
        # inside `subprocess.run`, so a path git emits verbatim that is not UTF-8
        # raised straight past a handler whose whole job is to return "unknown"
        # instead of raising. (Cold lane round 2, P3.)
        return None
    if proc.returncode != 0:
        return None
    # `or ""` because `stdout` is None whenever capture was not in effect. That is
    # not hypothetical here: it is what an AttributeError out of a function whose
    # whole contract is to return a three-state answer looked like, and a crash is
    # not one of the three states.
    return bool((proc.stdout or "").strip())


def undeclared(repo_root: Path, tasks: tuple[str, ...]) -> tuple[str, ...]:
    """Gate names in ``tasks`` that THIS repo's `mise.toml` does not declare.

    Criterion 5, and it fails CLOSED: `resolve.declared_tasks` returns an empty
    set for a missing or malformed `mise.toml`, so every gate reads as undeclared
    rather than the check quietly passing on no evidence. Aliases count as
    declarations — that is `declared_tasks`' contract, not a special case here.

    Deliberately not `mise tasks ls`, which merges the user's GLOBAL config: a
    gate list naming one of those extras would pass on this machine and fail on
    every other. Same reasoning, and the same function, as `kb-handoff-check`.
    """
    declared = resolve.declared_tasks(repo_root)
    return tuple(t for t in tasks if t not in declared)


def _invoke(repo_root: Path, task: str) -> int:
    """Run one gate with output streaming to the terminal; return its exit code.

    The INVOCATION is `pr._stream`'s, unchanged — same argv, same kwargs, stdio
    inherited — because criterion 8 asks for "exactly as today" and the honest
    way to deliver that is to move the call rather than rewrite it into something
    that looks equivalent.

    What deliberately differs is the failure rc. `_stream` returned 1 for "could
    not start", which the record could not tell from a gate that ran and failed.
    Since the record's entire job is being checkable later, the two get distinct
    values. Both are non-zero, so no caller's pass/fail decision changes.
    """
    try:
        return subprocess.run(
            ["mise", "run", task], cwd=repo_root, check=False, timeout=_GATE_TIMEOUT
        ).returncode
    except subprocess.TimeoutExpired:
        # Total wall-clock, NOT an idle timer — `subprocess.run`'s timeout has no
        # notion of output. The message said "no output for", which would have
        # sent a reader hunting a silent gate rather than a slow one.
        print(f"  {task}: did not finish within {_GATE_TIMEOUT}s")
        return _RC_TIMEOUT
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  {task}: {exc}")
        return _RC_COULD_NOT_RUN


def iter_run(
    repo_root: Path, tasks: tuple[str, ...], *, stop_on_failure: bool
) -> Iterator[GateResult]:
    """Yield one result per REQUESTED gate, AS EACH FINISHES.

    A generator rather than a list-returner so a caller can hold the results it
    already has when the run does not finish. `run_and_record` relies on that: a
    Ctrl-C partway through — the likeliest interruption, since a real run takes
    minutes — used to propagate out of a list-building loop and take every
    completed gate's evidence with it, leaving no record at all. Losing four
    minutes of gate results to an interrupt is the exact failure this module
    exists to prevent, arriving through the door nobody watched. (Cold lane, P2.)

    ``stop_on_failure`` is off for `kb-gates`, where the point is to learn every
    gate's state in one pass, and on for the ship path, where there is nothing to
    gain by spending minutes on gates whose result cannot change the refusal.
    Gates past the stop are yielded as "not run" rather than dropped.

    HEAD is read PER GATE, not once for the run. The gates take minutes and
    nothing stops an amend landing in the middle of them; a single sha stamped
    across every row would make the later rows quietly untrue, which is the exact
    failure this module exists to remove. :func:`render` flags the divergence.
    """
    stopped = False
    for task in tasks:
        if stopped:
            yield GateResult(task, None, None, None)
            continue
        # `or None`, not the raw "". An empty sha is git failing transiently, not
        # a commit — and `render`'s drift check filters falsy values, so the raw
        # form produced a PASSING row bound to nothing, silently. None makes it
        # the same three-state shape as `dirty`, and `bound_to_a_commit` reports
        # it. (Cold lane round 2, P2.)
        sha = head_sha(repo_root) or None
        dirty = tree_dirty(repo_root)
        # `flush=True` on both, and it is not cosmetic. Python block-buffers stdout
        # when it is a file rather than a tty, while the gate's own child writes
        # to the same fd unbuffered — so redirecting a run to a log put every
        # "==> gate:" header at the END, after all four gates' output, in an order
        # that reads as though nothing ran until the last second. Inherited from
        # `pr._stream`'s caller, seen in this task's first real run, and exactly
        # the live-output legibility criterion 8 exists to protect.
        print(f"==> gate: {task}", flush=True)
        rc = _invoke(repo_root, task)
        finished_at = datetime.now(UTC).isoformat()
        print(f"{'PASS' if rc == 0 else 'FAIL'}  gate {task} rc={rc}", flush=True)
        yield GateResult(task, rc, sha, finished_at, dirty)
        if rc != 0 and stop_on_failure:
            stopped = True


def run(repo_root: Path, tasks: tuple[str, ...], *, stop_on_failure: bool) -> list[GateResult]:
    """Run ``tasks`` in order; return one result per REQUESTED gate.

    Writes nothing — :func:`record` does that, and either is usable without the
    other (criterion 2). The eager form over :func:`iter_run`, for every caller
    that has nothing to do with a partial run.
    """
    return list(iter_run(repo_root, tasks, stop_on_failure=stop_on_failure))


def record(repo_root: Path, results: list[GateResult], *, sha: str) -> Path:
    """Write ``results`` to `.agent/kb/gates/gates-<sha>.json`; return the path.

    Runs nothing (criterion 2). ``sha`` keys the file and is the HEAD the run
    STARTED at; each row carries the HEAD its own gate ran against, so the two
    disagreeing is recorded rather than reconciled.

    Overwrites a previous record for the same commit, matching the receipt's
    semantics next door: the newest run at a commit is the current truth about
    that commit, and keeping the superseded one invites a reader to cite it.
    """
    path = repo_root / GATES_DIR / f"gates-{review.safe_sha(sha)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sha": sha,
        "recorded_at": datetime.now(UTC).isoformat(),
        "gates": [
            {
                "task": r.task,
                "rc": r.rc,
                "sha": r.sha,
                "finished_at": r.finished_at,
                "dirty": r.dirty,
            }
            for r in results
        ],
    }
    # Temp-then-rename, never a truncating in-place write. `record` OVERWRITES a
    # previous record for the same commit by design, so the destination usually
    # already holds a valid one — and `Path.write_text` truncates first, meaning
    # an interrupt or a full disk mid-write destroys the good record and leaves
    # unparsable bytes in its place. For an artifact whose only job is to be read
    # later that is corruption, not a lost write. (Cold lane, P2.)
    atomic.write_text(path, json.dumps(payload, indent=2) + "\n")
    return path


def render(results: list[GateResult], *, sha: str, path: Path) -> str:
    """The report: one line per gate, the counts, and where the record went."""
    lines = [f"gates at {sha[:_SHA_ABBREV]}"]
    for r in results:
        state = "not run" if not r.ran else ("PASS" if r.passed else f"FAIL rc={r.rc}")
        lines.append(f"  {r.task:<12} {state}")

    ran = [r for r in results if r.ran]
    failed = [r for r in ran if not r.passed]
    unrun = [r for r in results if not r.ran]
    summary = f"{len(ran) - len(failed)} passed, {len(failed)} failed"
    if unrun:
        # Named, not just counted. "3 passed, 1 failed" over a four-gate list that
        # was really six is the omission that makes a partial record read whole.
        summary += f", {len(unrun)} not run ({', '.join(r.task for r in unrun)})"
    lines.append(summary)

    drifted = sorted({r.sha for r in results if r.sha and r.sha != sha})
    if drifted:
        lines.append(
            f"  ! HEAD moved during the run — some gates ran against "
            f"{', '.join(s[:_SHA_ABBREV] for s in drifted)}, not {sha[:_SHA_ABBREV]}"
        )

    # Said out loud rather than left in the JSON. A run over a dirty tree is the
    # NORMAL case (you gate before you commit), so this is not a warning — it is
    # the sentence that stops the record being read as a fact about the commit.
    unclean = [r.task for r in results if r.dirty]
    unknown = [r.task for r in results if r.ran and r.dirty is None]
    if unclean:
        lines.append(
            f"  ! uncommitted changes were present — these describe the tree, "
            f"not {sha[:_SHA_ABBREV]} itself ({', '.join(unclean)})"
        )
    if unknown:
        lines.append(f"  ! could not tell whether the tree was clean ({', '.join(unknown)})")

    # A gate that COMPLETED while git was transiently unreadable has a result and
    # no commit to attach it to. It is not drift (the drift check filters falsy
    # shas by design), so without this it passed in silence. (Cold lane round 2.)
    unbound = [r.task for r in results if not r.bound_to_a_commit]
    if unbound:
        lines.append(
            f"  ! could not read HEAD for ({', '.join(unbound)}) — "
            f"their results are not bound to any commit"
        )
    lines.append(f"recorded: {path}")
    return "\n".join(lines)


@dataclass(frozen=True)
class GateRun:
    """One complete run: what happened, at which commit, and where it was written.

    These three travelled together into :func:`record` and :func:`render` and back
    out to two callers, which is a type asking to be born — and, more to the point,
    it is where the "``sha`` is never empty" invariant now lives. Enforcing that in
    only one of the two callers is precisely the defect this type was extracted to
    remove. (Standards + spec lanes, both independently.)
    """

    results: list[GateResult]
    sha: str
    path: Path

    @property
    def all_passed(self) -> bool:
        """Whether every REQUESTED gate ran and exited 0."""
        return all(r.passed for r in self.results)


def run_and_record(
    repo_root: Path, tasks: tuple[str, ...], *, stop_on_failure: bool
) -> tuple[GateRun | None, str]:
    """Validate, run, record — the whole sequence; ``(None, why)`` if it refused.

    The `(value, summary)` shape is `review.receipt_state`'s, deliberately: the
    caller decides what a refusal COSTS (an exit code, a False) and this decides
    what is refusable.

    This does NOT collapse :func:`run` and :func:`record` — criterion 2 keeps them
    separate and each is still usable alone, which two tests pin. What it removes
    is the second copy of the SEQUENCE around them. `kb-gates` and the ship path
    had one each, and they had already drifted: `main` refused an unreadable HEAD
    and `pr.run_gates` did not, so the ship path would write `gates-.json` with
    `"sha": ""` — a file that reads as a gate record and names no commit, which is
    the exact artifact #146 exists to abolish. Both review lanes found it
    independently, and the standards lane named the duplication as its cause.
    """
    missing = undeclared(repo_root, tasks)
    if missing:
        return None, (
            f"gate(s) not declared in mise.toml: {', '.join(missing)} "
            f"({len(resolve.declared_tasks(repo_root))} tasks declared)"
        )

    # Read BEFORE the gates: it keys the record, and a record that cannot name its
    # commit is not the checkable artifact #146 asks for. Refusing here also means
    # the minutes are never spent producing something unciteable.
    sha = head_sha(repo_root)
    if not sha:
        return None, "could not read HEAD — a record that cannot name its commit is not one"

    # Accumulate as each gate finishes and record in a `finally`, so an interrupt
    # cannot take the completed gates' evidence with it. `BaseException` is the
    # point — `KeyboardInterrupt` is not an `Exception`, and Ctrl-C during a
    # multi-minute run is the likeliest way this loop ever ends early. The
    # unreached gates are PADDED as "not run" rather than left absent, or a
    # truncated list would read as a complete short run. (Cold lane, P2.)
    results: list[GateResult] = []
    try:
        # `results.extend(<generator>)`, NOT `results = list(<generator>)`. They
        # look interchangeable and are not: `list()` builds its own list and only
        # binds it on success, so an interrupt leaves `results` empty and the
        # `finally` records nothing — the exact bug this block exists to fix,
        # reintroduced by the tidier spelling. `extend` appends as it consumes, so
        # what has already been yielded is retained.
        #
        # That retention is the load-bearing part, so it is PINNED BY A TEST
        # (`test_an_interrupt_still_records_the_gates_that_finished`) rather than
        # assumed from the interpreter's behaviour.
        results.extend(iter_run(repo_root, tasks, stop_on_failure=stop_on_failure))
    finally:
        results.extend(GateResult(t, None, None, None) for t in tasks[len(results) :])
        path = record(repo_root, results, sha=sha)
    return GateRun(results, sha, path), render(results, sha=sha, path=path)


#: Every flag `kb-gates` accepts. An unrecognised one is REFUSED rather than
#: ignored. `--stop-on-failure` is the realistic case — it is what the criterion
#: this flag implements is CALLED, so it is the spelling a reader guesses — and it
#: would otherwise be dropped from the task list by the `startswith("-")` filter
#: AND fail the `--stop` test, so the run would silently take the opposite
#: position of the one flag this command has and exit 0 or 1 as though that had
#: been asked for. The module already reserves 2 for a request it cannot honour;
#: a flag it does not know is one. (Spec lane.)
_FLAGS = frozenset({"--stop"})


def main(args: list[str], repo_root: Path) -> int:
    """`kb-gates [<task>...] [--stop]` — 1 if any gate failed, 2 on a bad request.

    2 is reserved for a request that could not be honoured — an unknown flag, a
    gate this repo does not declare, or a HEAD that cannot be read — the same
    split `kb-handoff-check` and `kb-skill-score` draw. It matters here because 1
    is a claim about the gates, and refusing to run them is not that claim.
    """
    unknown_flags = [a for a in args if a.startswith("-") and a not in _FLAGS]
    if unknown_flags:
        print(
            f"kb-gates: unknown flag(s) {', '.join(unknown_flags)} "
            f"(accepted: {', '.join(sorted(_FLAGS))})",
            file=sys.stderr,
        )
        return 2

    tasks = tuple(a for a in args if not a.startswith("-")) or GATE_TASKS
    gate_run, summary = run_and_record(repo_root, tasks, stop_on_failure="--stop" in args)
    if gate_run is None:
        print(f"kb-gates: {summary}", file=sys.stderr)
        return 2

    print(summary)
    # A gate that never ran counts as not passed. Under the default flag none can
    # be unrun, but `--stop` makes it reachable, and a `--stop` run that exited 0
    # having skipped half the list would be the false green in person.
    return 0 if gate_run.all_passed else 1
