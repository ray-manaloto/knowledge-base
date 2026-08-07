"""Run mutation arms from a declarative spec — the harness as a module (#160).

A mutation arm breaks one line of PRODUCTION code and asserts a NAMED test goes
red. `.claude/rules/probes-need-a-control-arm.md` rule 2 requires them; seven
successive rounds have written one by hand in the session scratchpad, and the
same defects keep coming back with them. This module is the fix: the runner
lives here with its tests, and a round contributes only **data**.

## Why a module, when a report already argued against one

The #145 report closed with the reasoning that this "is not a recurring
workflow… turning it into a task would make it look like a gate it is not". The
first half was refuted by events — it recurred six more times. The second half
is answered by scope rather than by architecture: ``mise run kb-arms`` is wired
into no gate, appears in neither ``kb-gates`` nor ``kb-ship`` nor ``kb-land``,
and mutates the working tree by design, exactly as ``kb-distill`` is a task that
states outright it is never a gate.

## The three protections, and the failure each one prevents

1. **Bytecode invalidation.** CPython validates a cached ``.pyc`` against
   ``(source mtime in whole seconds, source size)``. Most single-token
   mutations change a file's length by 0 or ±1, so two adjacent arms collide
   *often*, not rarely, and pytest imports the PREVIOUS arm's bytecode. Every
   suite run here purges ``__pycache__`` first **and** sets
   ``PYTHONDONTWRITEBYTECODE=1``. Three harnesses have paid this cost; the one
   in #144 reported a false ``SURVIVED`` for an arm that died on every hand run.

   The failure direction is why it is worth a module. A false ``SURVIVED``
   makes you look. The identical mechanism produces a false ``DEATH`` — an arm
   credited with killing a test the mutation never reached — which makes a
   whole run worthless **while reading green**.

2. **A probe that did not run is never scored as a death.** Four distinct
   states are reported apart from DIED/SURVIVED: the pattern is absent (a
   refactor moved the line), the pattern matches more than once (three
   "survivors" in one round were a ``str.replace`` hitting the wrong
   occurrence), the replacement is byte-identical to the original (a no-op edit
   proves nothing), and the suite went red **without the named test among the
   failures** (red for an unrelated reason is a false death). That last one is
   why ``test`` is REQUIRED on every non-control arm: the runner that dropped it
   scored rc-only deaths, and the check regressed silently between harnesses.

3. **A declared control that must hold.** Three separate green rows are
   mandatory, not conventional: the unmutated suite before any arm, at least one
   arm whose edit is a deliberate no-op comment and which must SURVIVE, and the
   restored suite after the last arm. Without the middle one a harness broken in
   any uniform way — a bad path, an unresolvable interpreter, zsh word-splitting
   — reads as total success, which has happened here.

   Control arms run FIRST and a broken control ABORTS: every row after a lying
   harness is noise, and printing them invites someone to read them.

## Arms are data, never code

The spec is TOML, so a round's arms cannot regrow logic (which is what happened
seven times) and so ``taplo`` already lints them. TOML literal strings
(``'''…'''``) perform **no** escape processing, so a code fragment carrying
backslashes, quotes or regex syntax survives byte-exact — the property the whole
mechanism rests on, since an arm is matched by literal containment.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

#: Directory names never descended when purging bytecode. `.venv` and `sources`
#: are not ours to write, and walking them is the slow part of a purge that runs
#: once per arm.
_PRUNED: frozenset[str] = frozenset(
    {".venv", ".git", "sources", "graphify-out", "raw", "node_modules"}
)

#: `-rf` is not decoration. The named-test check reads the failure summary, and
#: without it a `-q` run can report a red suite while naming nothing, which would
#: turn every death into `BROKEN_WRONG_TEST`. `-x` is deliberately ABSENT for the
#: same reason: stopping at the first failure hides whether the named test failed.
_PYTEST_FLAGS: tuple[str, ...] = ("-q", "--no-header", "-rf", "-p", "no:cacheprovider")

#: Said in one place because `load_spec` and the runner both refuse this, and two
#: wordings for one refusal is how a reader concludes they are two rules.
_ESCAPES = "`file` resolves outside the repo: {f} - an arm may only mutate this project"


class Verdict(Enum):
    """What one arm's run established. Only `is_pass` verdicts count as evidence."""

    DIED = "DIED"
    SURVIVED = "SURVIVED"
    CONTROL_HELD = "CONTROL HELD"
    CONTROL_BROKEN = "CONTROL BROKEN"
    BROKEN_ABSENT = "PROBE BROKEN - pattern not found"
    BROKEN_AMBIGUOUS = "PROBE BROKEN - pattern is not unique"
    BROKEN_NO_OP = "PROBE BROKEN - mutation was a no-op edit"
    BROKEN_WRONG_TEST = "PROBE BROKEN - red suite did not name the test"
    BROKEN_ESCAPES_REPO = "PROBE BROKEN - target is outside the repo"
    WOULD_APPLY = "would apply"

    @property
    def is_pass(self) -> bool:
        """True when this row is usable evidence rather than a broken probe."""
        return self in {Verdict.DIED, Verdict.CONTROL_HELD, Verdict.WOULD_APPLY}

    @property
    def is_broken_probe(self) -> bool:
        """True when the arm never measured anything — distinct from a survivor."""
        return self.name.startswith("BROKEN_")


class SpecError(ValueError):
    """A spec that cannot be trusted to discriminate. Raised before anything runs."""


@dataclass(frozen=True, slots=True)
class Arm:
    """One mutation: replace `old` with `new` in `file` and expect `test` to fail.

    `control=True` inverts the expectation — the edit must be a deliberate no-op
    and the suite must stay GREEN. A control carries no `test`, because there is
    no test it should break.
    """

    id: str
    file: str
    old: str
    new: str
    test: str | None = None
    meaning: str = ""
    control: bool = False


@dataclass(frozen=True, slots=True)
class Spec:
    """A suite selection plus the arms to run against it."""

    suites: tuple[str, ...]
    arms: tuple[Arm, ...]
    source: Path | None = None


@dataclass(frozen=True, slots=True)
class Row:
    """One arm's outcome. `rc` is None when the arm never reached the suite."""

    arm: Arm
    verdict: Verdict
    rc: int | None
    detail: str


@dataclass(frozen=True, slots=True)
class Report:
    """A whole run. `aborted` is set when a later row would have been meaningless.

    `dry` marks a `--dry-run`, where NO suite ran. It is a real field rather than
    a rendering flag because the first version passed `baseline_rc=0` and
    `restored_rc=0` for a dry run and printed two green rows that had never
    executed — a "could not check" rendered as green, in the tool built to refuse
    exactly that. `baseline_rc` is `None` on a dry report for the same reason.
    """

    baseline_rc: int | None
    rows: tuple[Row, ...] = ()
    restored_rc: int | None = None
    aborted: str | None = None
    dry: bool = False

    @property
    def ok(self) -> bool:
        """True only when every mandatory green row held and no arm failed to discriminate.

        Deliberately conjunctive: a run with no declared control, or an unread
        restored row, is NOT a pass — and a DRY report is never a pass, because
        validating the patterns is not running the arms.

        There is no separate `bool(self.rows)` clause. There was, and a mutation
        arm proved it INERT: `any(...)` over an empty tuple is already False, so
        the two guarded one property and each masked the other's mutation.
        Deleted rather than tested, on this repo's precedent — a guard whose
        removal no test can notice is worse than no guard, because a sweep scores
        it as covered. `test_a_report_with_no_rows_at_all_is_not_ok` still pins
        the behaviour, and now arms the clause that actually delivers it.
        """
        return (
            not self.dry
            and self.aborted is None
            and self.baseline_rc == 0
            and self.restored_rc == 0
            and any(row.arm.control for row in self.rows)
            and all(row.verdict.is_pass for row in self.rows)
        )

    def render(self) -> str:
        """Format the run as a table plus the summary a report can quote."""
        lines: list[str] = []
        if self.dry:
            lines.append("DRY RUN - patterns checked against the files; NO suite was run")
        else:
            lines.append(f"baseline (unmutated) rc={self.baseline_rc}")
            if self.baseline_rc != 0:
                lines.append("  BASELINE RED - no arm below could have discriminated")
        width = max((len(row.arm.id) for row in self.rows), default=1)
        for row in self.rows:
            rc = "--" if row.rc is None else str(row.rc)
            lines.append(f"  {row.arm.id:<{width}}  rc={rc:<3} {row.verdict.value}")
            if row.detail:
                lines.append(f"  {'':<{width}}    {row.detail}")
        if self.aborted is not None:
            lines.append(f"ABORTED: {self.aborted}")
        if not self.dry:
            if self.restored_rc is not None:
                state = "OK" if self.restored_rc == 0 else "TREE LEFT DIRTY"
                lines.append(f"restored rc={self.restored_rc}  {state}")
            real = [row for row in self.rows if not row.arm.control]
            died = [row for row in real if row.verdict is Verdict.DIED]
            controls = [row for row in self.rows if row.arm.control]
            held = [row for row in controls if row.verdict is Verdict.CONTROL_HELD]
            lines.append(
                f"{len(died)}/{len(real)} arms died; {len(held)}/{len(controls)} controls held"
            )
        lines.extend(
            f"  {row.verdict.value} - {row.arm.id}: {row.detail}"
            for row in self.rows
            if not row.verdict.is_pass
        )
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Planned:
    """The mutated text, or the reason this arm cannot be scored."""

    text: str | None
    verdict: Verdict | None = None
    detail: str = ""


def purge_bytecode(root: Path) -> int:
    """Delete every `__pycache__` under `root`, returning how many were removed.

    This is the mitigation, not a tidy-up. Without it a same-size mutation is
    served the previous arm's bytecode and the arm reports a verdict about code
    that never ran.

    It RAISES on a directory that survives its own removal. The first version
    paired `ignore_errors=True` with an unconditional `removed += 1`, so a purge
    that silently failed still reported the count of a purge that worked — the
    mitigation lying about itself, which is the one failure this module cannot
    absorb.
    """
    removed = 0
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _PRUNED]
        if "__pycache__" in dirnames:
            dirnames.remove("__pycache__")
            cache = Path(dirpath) / "__pycache__"
            shutil.rmtree(cache, ignore_errors=True)
            if cache.exists():
                raise RuntimeError(
                    f"could not purge {cache} - every later verdict would be suspect"
                )
            removed += 1
    return removed


def run_suite(
    repo_root: Path,
    suites: tuple[str, ...],
    *,
    purge: Callable[[Path], int] = purge_bytecode,
) -> tuple[int, str]:
    """Purge bytecode, then run `suites` under pytest; returns (rc, combined output).

    `purge` is injected so a test can DISABLE it and watch the same arm flip from
    DIED to SURVIVED — the control arm for protection 1, per
    `probes-need-a-control-arm.md`.
    """
    purge(repo_root)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *suites, *_PYTEST_FLAGS],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return proc.returncode, proc.stdout + proc.stderr


def plan_mutation(source: str, arm: Arm) -> Planned:
    """Decide whether `arm` can be applied to `source` at all.

    Every rejection here is a PROBE BROKEN verdict rather than a survivor,
    because an arm that never edited the code has no opinion about the tests.
    """
    hits = source.count(arm.old)
    if hits == 0:
        return Planned(
            None,
            Verdict.BROKEN_ABSENT,
            f"`old` does not occur in {arm.file} - a refactor moved it; re-derive the arm",
        )
    if hits > 1:
        return Planned(
            None,
            Verdict.BROKEN_AMBIGUOUS,
            f"`old` occurs {hits} times in {arm.file} - it would mutate the wrong occurrence",
        )
    mutated = source.replace(arm.old, arm.new, 1)
    if mutated == source:
        return Planned(
            None,
            Verdict.BROKEN_NO_OP,
            "`new` is byte-identical to `old` - the edit proves nothing",
        )
    return Planned(mutated)


def contained_path(repo_root: Path, rel: str) -> Path | None:
    """Resolve `rel` under `repo_root`, or None when it escapes the repo.

    `repo_root / rel` is NOT containment. `Path.__truediv__` discards the left
    operand when the right is absolute, so `Path("/repo") / "/etc/hosts"` is
    `/etc/hosts` — and this module WRITES to that path. `..` traversal and a
    symlink pointing out of the tree are the other two constructions; all three
    were built and executed against the first version by the cold lane, which
    watched it mutate and restore a file with nothing to do with this repo.

    `.resolve()` on BOTH sides is what closes the symlink case. A lexical
    comparison would pass a symlink straight through — that exact substitution
    was defended in a docstring here once and walked through the next round.
    `do-not.md` #11 is the invariant: nothing outside this project is ours.
    """
    candidate = (repo_root / rel).resolve()
    root = repo_root.resolve()
    return candidate if candidate == root or candidate.is_relative_to(root) else None


def _read_target(repo_root: Path, arm: Arm) -> tuple[Path, str] | Row:
    """Resolve and read an arm's target, or return the Row saying why it cannot be scored.

    `UnicodeDecodeError` is caught beside `OSError` because it is a `ValueError`
    subclass, so an `except OSError` misses it entirely and a binary target
    crashed the whole run with a traceback instead of taking a verdict.

    The return type is a UNION rather than a three-tuple of optionals. The
    tuple version forced both callers to carry a `source is None and refusal is
    None` fallback that no input could reach — dead defensive code, and the kind
    an arm can never kill, so a sweep would score it as covered forever. An
    annotation admitting a state the function cannot produce is what makes a
    caller write a branch for it (cold lane round 2, P3).
    """
    path = contained_path(repo_root, arm.file)
    if path is None:
        return Row(arm, Verdict.BROKEN_ESCAPES_REPO, None, _ESCAPES.format(f=arm.file))
    try:
        return path, path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Row(arm, Verdict.BROKEN_ABSENT, None, f"cannot read {arm.file}: {exc}")


def check(spec: Spec, repo_root: Path) -> tuple[Row, ...]:
    """Validate every arm against the files WITHOUT running the suite (`--dry-run`).

    The cheap rung of the cost ladder: a stale pattern is the failure that has
    cost this repo the most re-runs, and it is answerable without pytest.
    """
    rows: list[Row] = []
    for arm in spec.arms:
        got = _read_target(repo_root, arm)
        if isinstance(got, Row):
            rows.append(got)
            continue
        planned = plan_mutation(got[1], arm)
        if planned.text is None and planned.verdict is not None:
            rows.append(Row(arm, planned.verdict, None, planned.detail))
        else:
            rows.append(Row(arm, Verdict.WOULD_APPLY, None, ""))
    return tuple(rows)


def _restore(path: Path, original: str) -> None:
    """Put the file back and PROVE it went back; a dirty tree must never be silent."""
    path.write_text(original, encoding="utf-8")
    if path.read_text(encoding="utf-8") != original:
        raise RuntimeError(f"failed to restore {path} - the working tree is dirty")


def _score(arm: Arm, rc: int, out: str) -> Row:
    """Turn one suite result into a verdict for `arm`."""
    if arm.control:
        if rc == 0:
            return Row(arm, Verdict.CONTROL_HELD, rc, "suite stayed green under a no-op edit")
        return Row(
            arm,
            Verdict.CONTROL_BROKEN,
            rc,
            "suite went RED under a no-op edit - the harness itself is broken",
        )
    if rc == 0:
        return Row(arm, Verdict.SURVIVED, rc, arm.meaning or "no test fails under this mutation")
    if arm.test is not None and arm.test not in out:
        return Row(
            arm,
            Verdict.BROKEN_WRONG_TEST,
            rc,
            f"suite went RED but {arm.test} was not among the failures - "
            f"this arm did not measure what it claims",
        )
    named = arm.test or "the suite"
    return Row(arm, Verdict.DIED, rc, f"{named} failed")


def _run_arm(arm: Arm, repo_root: Path, suite: Callable[[], tuple[int, str]]) -> Row:
    """Apply one arm, run the suite, restore the file, and score the result."""
    got = _read_target(repo_root, arm)
    if isinstance(got, Row):
        return got
    path, original = got
    planned = plan_mutation(original, arm)
    if planned.text is None:
        if planned.verdict is None:
            raise RuntimeError(f"{arm.id}: plan_mutation returned neither text nor a verdict")
        return Row(arm, planned.verdict, None, planned.detail)
    path.write_text(planned.text, encoding="utf-8")
    try:
        rc, out = suite()
    finally:
        _restore(path, original)
    return _score(arm, rc, out)


def run(
    spec: Spec,
    repo_root: Path,
    *,
    suite: Callable[[], tuple[int, str]] | None = None,
    purge: Callable[[Path], int] = purge_bytecode,
) -> Report:
    """Run the whole spec: baseline, controls, mutations, restored.

    Controls run BEFORE mutations and a broken control aborts, because every row
    printed after a lying harness invites someone to believe it.
    """
    runner = suite if suite is not None else lambda: run_suite(repo_root, spec.suites, purge=purge)
    baseline_rc, _ = runner()
    if baseline_rc != 0:
        return Report(
            baseline_rc,
            aborted="baseline suite is RED - no arm could have discriminated",
        )
    rows: list[Row] = []
    ordered = [a for a in spec.arms if a.control] + [a for a in spec.arms if not a.control]
    for arm in ordered:
        row = _run_arm(arm, repo_root, runner)
        rows.append(row)
        if arm.control and row.verdict is not Verdict.CONTROL_HELD:
            return Report(
                baseline_rc,
                tuple(rows),
                aborted=f"control arm {arm.id!r} did not hold - later rows would be meaningless",
            )
    restored_rc, _ = runner()
    return Report(baseline_rc, tuple(rows), restored_rc)


#: Every key a `[[arm]]` table may carry. An unknown key is an error rather than
#: a shrug: a typo'd `cntrl = true` would silently demote a control to a
#: mutation arm, and the run would then read as a normal sweep.
_REQUIRED_ARM_KEYS: tuple[str, ...] = ("id", "file", "old", "new")
_ARM_KEYS: frozenset[str] = frozenset({*_REQUIRED_ARM_KEYS, "test", "meaning", "control"})


#: Why `test` is mandatory, stated where the refusal is raised: the runner that
#: dropped it scored deaths on the exit code alone, so a suite red for an
#: unrelated reason was credited to the mutation.
_TEST_REQUIRED = (
    "{where}: `test` is required - an arm scored on the exit code alone cannot tell "
    "a real death from a suite that went red for another reason"
)


def _resolve_test(raw: object, *, control: bool) -> tuple[str | None, bool]:
    """Narrow a `[[arm]]` table's `test` value; the flag is False when it is unusable."""
    if control:
        return None, True
    return (raw, True) if isinstance(raw, str) else (None, False)


def _arm_from_table(index: int, table: object, errors: list[str]) -> Arm | None:
    """Build one `Arm` from a `[[arm]]` table, appending every problem to `errors`.

    Values arrive from `tomllib` as `object` and are narrowed here rather than
    annotated as `str`. An annotation that promises what the input has not been
    checked to hold is how callers stop checking it.
    """
    where = f"[[arm]] #{index}"
    if not isinstance(table, dict):
        errors.append(f"{where}: not a table")
        return None
    unknown = sorted(str(key) for key in table if key not in _ARM_KEYS)
    if unknown:
        errors.append(f"{where}: unknown key(s) {unknown}")

    required: dict[str, str] = {}
    for key in _REQUIRED_ARM_KEYS:
        value = table.get(key)
        if isinstance(value, str):
            required[key] = value
        else:
            errors.append(f"{where}: missing or non-string `{key}`")
    if len(required) != len(_REQUIRED_ARM_KEYS):
        return None
    arm_id = required["id"]

    control = table.get("control", False)
    if not isinstance(control, bool):
        errors.append(f"{where} ({arm_id}): `control` must be a boolean")
        return None

    test, test_ok = _resolve_test(table.get("test"), control=control)
    if not test_ok:
        errors.append(_TEST_REQUIRED.format(where=f"{where} ({arm_id})"))
        return None
    if control and table.get("test") is not None:
        errors.append(f"{where} ({arm_id}): a control arm must not name a `test` - it SURVIVES")

    meaning = table.get("meaning", "")
    if not isinstance(meaning, str):
        errors.append(f"{where} ({arm_id}): `meaning` must be a string")
        meaning = ""
    return Arm(
        id=arm_id,
        file=required["file"],
        old=required["old"],
        new=required["new"],
        test=test,
        meaning=meaning,
        control=control,
    )


def load_spec(path: Path, repo_root: Path) -> Spec:
    """Parse and VALIDATE a TOML arms spec; raises `SpecError` listing every problem.

    Validation is total rather than first-failure: a spec is authored in one
    sitting, and reporting one error per run is how a stale spec takes six runs
    to fix.

    `repo_root` is here so containment is decided BEFORE the baseline runs. The
    runner refuses an escaping arm too, and that is not a duplicate guard masking
    this one: `run()` also accepts hand-built `Spec` objects that never pass
    through here, so the two cover different entry points and each is armed
    separately.
    """
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise SpecError(f"{path}: {exc}") from exc

    errors: list[str] = []
    suites = raw.get("suites")
    if not isinstance(suites, list) or not suites or not all(isinstance(s, str) for s in suites):
        errors.append("`suites` must be a non-empty array of strings")
        suites = []
    tables = raw.get("arm")
    if not isinstance(tables, list) or not tables:
        errors.append("at least one `[[arm]]` table is required")
        tables = []

    arms = [arm for i, t in enumerate(tables, 1) if (arm := _arm_from_table(i, t, errors))]
    seen: set[str] = set()
    for arm in arms:
        if arm.id in seen:
            errors.append(f"duplicate arm id {arm.id!r} - ids name rows in the report")
        seen.add(arm.id)
    errors.extend(
        _ESCAPES.format(f=arm.file) for arm in arms if contained_path(repo_root, arm.file) is None
    )
    if arms and not any(arm.control for arm in arms):
        errors.append(
            "no `control = true` arm - a harness broken in any uniform way reads as "
            "total success without one"
        )
    if errors:
        raise SpecError(f"{path}: " + "; ".join(errors))
    return Spec(tuple(suites), tuple(arms), source=path)


def main(argv: list[str], repo_root: Path) -> int:
    """CLI entry: `kb-setup arms <spec.toml> [--dry-run]`."""
    args = [a for a in argv if a != "--dry-run"]
    dry = "--dry-run" in argv
    if len(args) != 1:
        print("usage: kb-setup arms <spec.toml> [--dry-run]")
        return 2
    try:
        spec = load_spec(Path(args[0]), repo_root)
    except SpecError as exc:
        print(f"SPEC REFUSED: {exc}")
        return 2

    if dry:
        rows = check(spec, repo_root)
        print(Report(baseline_rc=None, rows=rows, dry=True).render())
        broken = [row for row in rows if row.verdict.is_broken_probe]
        print(f"\ndry run: {len(rows) - len(broken)}/{len(rows)} arms would apply")
        return 1 if broken else 0

    report = run(spec, repo_root)
    print(report.render())
    return 0 if report.ok else 1
