# Copyright (c) 2026 Raymond Manaloto
"""`mise run kb-check -- <path>...` — the dev-loop gate, with REAL exit codes.

WHY THIS EXISTS, measured rather than assumed. `mise run check` is whole-repo
(`depends = ["lint", "test"]`) and `kb-gates` runs the four ship gates. Neither
answers the question an edit-run-edit loop actually asks — *are these two files
clean?* — so that question got answered in the shell instead, and the shell
answer is wrong: over the 2026-08-08 transcript, **35 gate invocations** were
piped into `head`/`tail`, which returns the PIPE's exit code and reports a
failed gate as a success.

The remedy `session_reflect`'s `piped-rc` used to print was itself shell logic
(`<cmd> > /tmp/out.log 2>&1; echo "rc=$?"`) in a repo whose first invariant is
zero-bash-logic — so the rule recommended the thing the repo forbids, and the
argument it generated was about which shell array to name. There is no array to
name here: `subprocess.run(...).returncode` is the exit code, and nothing sits
between it and the report.

WHAT IT DELIBERATELY IS NOT: a gate. It never records to
`.agent/kb/gates/`, because a per-file check is not evidence about a commit and
a record that could be mistaken for one would be worse than none. `kb-gates`
remains the only thing that writes that artifact.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from kb_setup.result import Err, Ok, Rc, Result, exit_code

RC_COULD_NOT_RUN = 127
"""Distinct from any tool's own failure rc, so "broken" never reads as "failed".

The same separation `gates._invoke` makes and for the same reason: a reader
deciding what to fix needs to know whether the tool disagreed with the code or
never started.
"""

TESTS_DIR = "tests"
_TEST_PREFIX = "test_"


@dataclass(frozen=True)
class Tool:
    """One checker, and the paths it has an opinion about."""

    name: str
    argv: tuple[str, ...]


STATIC_TOOLS: tuple[Tool, ...] = (
    Tool("ruff", ("uv", "run", "ruff", "check")),
    Tool("format", ("uv", "run", "ruff", "format", "--check")),
    Tool("ty", ("uv", "run", "ty", "check")),
)
"""Read-only checkers run over every `.py` path given.

`ruff format` is `--check` on purpose: this reports, it does not rewrite. A
dev-loop helper that silently reformats the file you are mid-thought in is the
same class of surprise as `hk fix` running where `hk check` was meant, which is
why `mise run lint` is the read-only one and `fmt` is the separate verb.
"""


@dataclass(frozen=True)
class Outcome:
    """What one tool did. `rc is None` is never a pass — nothing ran."""

    tool: str
    rc: int | None
    targets: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Ran AND exited 0. A `None` rc is not a pass — nothing was checked."""
        return self.rc == 0

    @property
    def skipped(self) -> bool:
        """No applicable path was given, so this tool was never asked anything."""
        return self.rc is None


def _resolve(repo_root: Path, path: str) -> Path:
    """`path` as the tools will see it — relative paths against `repo_root`.

    THE one resolution rule, and it exists because there were briefly two.
    `python_paths` stat'd against the process CWD while `holds_python` resolved
    against `repo_root`, so the pair disagreed whenever those differ: a
    directory genuinely holding `.py` files was judged present by one and absent
    by the other, and every tool came back SKIP for a perfectly good argument.
    Caught by the control arm on the fix for the round-1 BLOCKING finding —
    a fix introducing its own defect, which is why that arm was written.

    Invisible in normal use, because a mise task runs from the repo root and the
    two agree there. That is what makes it worth a named function rather than a
    second inline `Path(p)`.
    """
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def python_paths(repo_root: Path, paths: list[str]) -> list[str]:
    """The `.py` members of `paths`, in the order given.

    A directory is passed through untouched — ruff, ty and pytest all walk one
    themselves, and expanding it here would mean reimplementing three different
    exclusion rules and getting at least one of them wrong.

    The returned strings are the CALLER's spellings, not the resolved paths:
    they go straight into argv, and the tools run with `cwd=repo_root`, so
    rewriting them would only make the reported target list stop matching what
    was typed.
    """
    return [p for p in paths if p.endswith(".py") or _resolve(repo_root, p).is_dir()]


def holds_python(repo_root: Path, paths: list[str]) -> bool:
    """Would the static tools actually be HANDED a `.py` file by `paths`?

    The three tools answer "no Python here" with a **warning and exit 0**, not
    with a failure — so forwarding a directory containing no `.py` files made
    `kb-check` print three `rc=0 ok` rows and return 0 for a directory nobody
    had checked anything in. That is this module's own thesis inverted one
    function above where it is stated: *"nothing to check" is a FAILURE, not a
    quiet 0*. It failed for the case a dev-loop user actually hits — a typo'd
    path, the wrong directory, an empty scratch dir. (Cold lane, round 1,
    BLOCKING.)

    THIS PARAGRAPH USED TO SAY the thesis "held for `x.rs`, because ruff exits
    non-zero on a named non-Python file". That is FALSE, and round 2 caught it:
    `python_paths(root, ["x.rs"])` is `[]`, so **ruff is never invoked for
    `x.rs` at all** — it reaches 2 through the pre-existing "nothing ran"
    branch, before and after this fix. The mechanism was invented to explain a
    correct outcome, which is the most durable kind of wrong comment: the
    behaviour it describes is right, so nobody re-checks the reason.

    A `.py` path is trusted WITHOUT a stat: a named file that does not exist
    must still reach the tools, because they exit non-zero for it and that
    non-zero is the correct answer.

    A DIRECTORY IS ANSWERED BY RUFF, NOT BY `rglob`, and that is the second
    round of this fix rather than its first shape. `rglob("*.py")` does not
    apply the tools' exclusions, so a directory whose only Python sits under
    `.venv` / `graphify-out` / `node_modules` came back True, ruff then said
    *"No Python files found"* and exited **0**, and the summary printed three
    `rc=0 ok` rows — the identical false green the first fix was written to
    remove, one layer narrower. A finding is a SAMPLE of a class, and the first
    fix closed only the instance it was handed.

    `ruff check --show-files` prints the files ruff WOULD check, so the question
    is asked of the tool instead of reimplementing three different exclusion
    rule sets — which `python_paths` above explicitly warns against doing.

    LIMITATION, stated rather than implied: ruff is a PROXY for all three tools.
    ty's exclusions may differ, so a directory ruff excludes entirely and ty
    would not is reported as nothing-to-check. That direction is the safe one
    (it refuses rather than falsely passing), and closing it would mean asking
    each tool separately for a case nobody has hit.
    """
    if any(p.endswith(".py") for p in paths):
        return True
    directories = [p for p in paths if _resolve(repo_root, p).is_dir()]
    return bool(directories) and bool(_ruff_would_check(repo_root, directories))


def _ruff_would_check(repo_root: Path, paths: list[str]) -> str:
    """Ruff's own list of the files it would check under `paths`; "" if none.

    Captured rather than inherited — this one is a QUESTION, not a check, so its
    output is data for the caller rather than something the user should see.
    Every other invocation in this module inherits stdio on purpose.

    A failure to run returns "" (nothing to check), which makes `main` exit 2
    rather than 0. Fail-closed: an unanswerable question must not read as a
    clean verdict, which is the whole subject of this module.
    """
    try:
        completed = subprocess.run(
            ("uv", "run", "ruff", "check", "--show-files", *paths),
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError, subprocess.SubprocessError:
        return ""
    return completed.stdout.strip()


def sibling_test(repo_root: Path, path: str) -> str | None:
    """`tests/test_<stem>.py` for a source file, when that file EXISTS.

    Convention-based and therefore capable of being wrong, so it is reported in
    the output rather than applied silently — a check that quietly ran something
    you did not name is a check whose green you cannot interpret. Returns None
    for a path already under `tests/`, which needs no sibling: it IS one.
    """
    candidate = Path(path)
    if candidate.suffix != ".py" or TESTS_DIR in candidate.parts:
        return None
    if candidate.name.startswith(_TEST_PREFIX):
        return None
    guess = Path(TESTS_DIR) / f"{_TEST_PREFIX}{candidate.stem}.py"
    return str(guess) if (repo_root / guess).is_file() else None


def test_paths(repo_root: Path, paths: list[str]) -> list[str]:
    """Every path pytest should be pointed at: the given tests, plus siblings.

    De-duplicated while KEEPING ORDER — for the REPORTED target list, not for
    pytest's benefit. The first version of this docstring claimed pytest
    "collects it twice and the summary double-counts", and that is measured
    false: `tests/test_check.py tests/test_check.py` collects **14**, the same
    as the file alone, and `tests/test_check.py tests/` collects **2101**, the
    same as the directory alone. pytest deduplicates by node id, including the
    containment case.

    So the honest reason is narrower and worth keeping anyway: `render` prints
    the target list, and a row echoing a path twice invites a reader to
    reconcile a duplicate that means nothing. A tidy report, not a correctness
    fix — recorded as such, because a rationale that sounds like a correctness
    fix is one nobody re-checks.
    """
    found: list[str] = []
    for path in paths:
        for candidate in (path if _is_test(path) else None, sibling_test(repo_root, path)):
            if candidate is not None and candidate not in found:
                found.append(candidate)
    return found


def _is_test(path: str) -> bool:
    """A path pytest should be pointed at: a `test_*.py` file, OR a test DIRECTORY.

    The directory arm was missing and `mise run kb-check -- tests/` reported
    `pytest SKIP  no applicable path was given` — while ruff, format and ty all
    ran over the same argument. That is this module's own failure class one
    layer down: a question that WAS asked, displayed as one that was not, on the
    single most obvious way to invoke it. Found by dogfooding rather than by any
    test, which is why the test now exists.

    A directory is recognised by `tests` appearing in its parts and the path not
    naming a `.py` file — pytest walks it from there, applying its own
    collection rules rather than ours.
    """
    parts = Path(path).parts
    if TESTS_DIR not in parts:
        return False
    if Path(path).suffix == ".py":
        return Path(path).name.startswith(_TEST_PREFIX)
    return True


def _run(repo_root: Path, argv: tuple[str, ...]) -> int:
    """Run `argv` with stdio INHERITED, and return its real exit code.

    Inherited rather than captured so the tool's own diagnostics reach the
    terminal live and unmangled — which is the whole thing a `| tail -3` was
    approximating, and doing worse: `tail` both truncates the diagnostics and
    destroys the exit code, while this keeps all of both.
    """
    try:
        return subprocess.run(argv, cwd=repo_root, check=False).returncode
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  could not run {argv[0]}: {exc}")
        return RC_COULD_NOT_RUN


def run(repo_root: Path, paths: list[str]) -> list[Outcome]:
    """Check `paths` with every applicable tool, running all of them.

    Every tool runs even after one fails — the loop deliberately does not stop.
    A dev-loop check exists to tell you everything wrong with the file in one
    pass; stopping at ruff so you fix an import order, re-run, and only then
    learn ty has an opinion is how a fast check becomes three slow ones.
    """
    outcomes: list[Outcome] = []
    # Both conditions: something `.py`-SHAPED was named, AND something `.py` is
    # really there for the tools to read. The second is what stops three
    # warn-and-exit-0 tools from rendering as `rc=0 ok` over an empty directory.
    sources = python_paths(repo_root, paths) if holds_python(repo_root, paths) else []
    for tool in STATIC_TOOLS:
        rc = _run(repo_root, (*tool.argv, *sources)) if sources else None
        outcomes.append(Outcome(tool.name, rc, tuple(sources)))

    tests = test_paths(repo_root, paths)
    rc = _run(repo_root, ("uv", "run", "pytest", "-q", *tests)) if tests else None
    outcomes.append(Outcome("pytest", rc, tuple(tests)))
    return outcomes


def render(outcomes: list[Outcome]) -> str:
    """The summary. Every row states its rc, and a SKIP is never shown as a pass."""
    lines = ["", "kb-check:"]
    for outcome in outcomes:
        if outcome.skipped:
            lines.append(f"  {outcome.tool:8} SKIP  no applicable path was given")
            continue
        verdict = "ok" if outcome.passed else "FAIL"
        lines.append(
            f"  {outcome.tool:8} rc={outcome.rc:<4} {verdict}  {' '.join(outcome.targets)}"
        )
    ran = [o for o in outcomes if not o.skipped]
    if not ran:
        lines.append("  nothing was checked — pass at least one .py path or directory")
    return "\n".join(lines)


def check(repo_root: Path, args: list[str]) -> Result[list[Outcome]]:
    """The command boundary (§2 R5) — errors are RETURNED, never raised.

    Ray ruled the `Result` reading of R5 on 2026-08-09, and this is the first
    command converted to it. The shape is `ruff`'s `pub fn run(…) ->
    Result<ExitStatus>` (pinned `0.16.2`, `crates/ruff/src/lib.rs:128`), and the
    distinction it buys is the one this function most needed:

    - **A run that FOUND something is `Ok`**, carrying `Rc.FINDINGS`. A checker
      that reports three violations did its job.
    - **`Err` is reserved for "could not run"** — a malformed request, or a
      request that checked nothing.

    Before this, both were `return 1` / `return 2` with the meaning living only
    in a docstring, so a caller could not tell "your code is dirty" from "your
    invocation was wrong" without reading the source.

    "Nothing to check" stays a FAILURE and not a quiet 0, for the reason it
    always was: a check handed an argument it did not understand and exiting
    green is the same false-green this module exists to remove, one layer up —
    `kb-check -- src/x.rs` must not read as "x.rs is clean". It is now an `Err`,
    which says so in the type.

    Prints nothing: rendering belongs to the caller (`main`), which is also
    where §2.5's human-rendering sink will land.
    """
    paths = [a for a in args if not a.startswith("-")]
    if not paths:
        return Err("kb-check: pass one or more paths, e.g. `mise run kb-check -- <file.py>`")

    outcomes = run(repo_root, paths)
    ran = [o for o in outcomes if not o.skipped]
    if not ran:
        # `render` already carries the "nothing was checked" line, so the Err
        # message is the same text the previous `print` emitted — the exit code
        # and the operator-visible output are both unchanged by this refactor.
        return Err(render(outcomes))

    failed = any(not o.passed for o in ran)
    return Ok(outcomes, rc=Rc.FINDINGS if failed else Rc.OK)


def main(repo_root: Path, args: list[str]) -> int:
    """Thin conversion from `Result` to a process exit code, and the only print.

    Kept returning `int` deliberately: `cli.py` and every pre-existing
    `assert check.main(...)` in `tests/test_check.py` are the regression arm for
    the `Result` refactor — each observable code must be byte-identical to
    before.

    That sentence carried a COUNT ("the eight existing…") until the cold lane
    caught it at 7. The miscount came from reading `grep -n "main("` hit-lines,
    three of which are `_touch(… "fn main() {}")` — a **Rust** fixture string.
    It is now stated without a figure, which is the structural fix rather than
    the corrective one: a number here goes stale the next time anyone adds a
    test, and `md-size-budgets`/`probes-need-a-control-arm` both say a figure
    invalidated by the very commit that writes it should be a mechanism instead.
    """
    result = check(repo_root, args)
    match result:
        case Ok(outcomes, _):
            print(render(outcomes))
        case Err(message, _):
            print(message)
    return exit_code(result)
