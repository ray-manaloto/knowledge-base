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


def python_paths(paths: list[str]) -> list[str]:
    """The `.py` members of `paths`, in the order given.

    A directory is passed through untouched — ruff, ty and pytest all walk one
    themselves, and expanding it here would mean reimplementing three different
    exclusion rules and getting at least one of them wrong.
    """
    return [p for p in paths if p.endswith(".py") or Path(p).is_dir()]


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

    De-duplicated while KEEPING ORDER, because pytest given the same file twice
    collects it twice and the summary then double-counts — a count nobody can
    reconcile against the file list they typed.
    """
    found: list[str] = []
    for path in paths:
        for candidate in (path if _is_test(path) else None, sibling_test(repo_root, path)):
            if candidate is not None and candidate not in found:
                found.append(candidate)
    return found


def _is_test(path: str) -> bool:
    parts = Path(path).parts
    return TESTS_DIR in parts and Path(path).name.startswith(_TEST_PREFIX)


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
    sources = python_paths(paths)
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


def main(repo_root: Path, args: list[str]) -> int:
    """Non-zero if any tool failed, or if nothing could be checked at all.

    "Nothing to check" is a FAILURE and not a quiet 0. A check that was handed
    an argument it did not understand and exits green is the same false-green
    this module exists to remove, one layer up — `kb-check -- src/x.rs` must not
    read as "x.rs is clean".
    """
    paths = [a for a in args if not a.startswith("-")]
    if not paths:
        print("kb-check: pass one or more paths, e.g. `mise run kb-check -- <file.py>`")
        return 2

    outcomes = run(repo_root, paths)
    print(render(outcomes))
    ran = [o for o in outcomes if not o.skipped]
    if not ran:
        return 2
    return 1 if any(not o.passed for o in ran) else 0
