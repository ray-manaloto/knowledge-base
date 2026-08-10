# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.check` — the dev-loop gate (`mise run kb-check`).

The defect this module exists to remove is a FALSE GREEN: a gate piped into
`tail` returns the pipe's exit code, so a failing check reports success. Every
arm here is therefore about a route to `0`, because that is this module's own
failure class — if it can report clean when something is wrong, it has
reproduced the bug it replaces one layer up.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import check
from kb_setup.result import Err, Ok, Rc, exit_code

if TYPE_CHECKING:
    import pytest


def _touch(path: Path, body: str = "x = 1\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _stub_rcs(monkeypatch: pytest.MonkeyPatch, rcs: dict[str, int]) -> list[tuple[str, ...]]:
    """Make each tool return a chosen rc, and record every argv built.

    The argv is recorded because WHICH paths reach WHICH tool is half of what
    this module decides; a stub that only supplied exit codes would let the path
    routing be deleted with every arm still green.
    """
    seen: list[tuple[str, ...]] = []

    def _fake(_root: Path, argv: tuple[str, ...]) -> int:
        seen.append(argv)
        for name, rc in rcs.items():
            if name in argv:
                return rc
        return 0

    monkeypatch.setattr(check, "_run", _fake)
    return seen


def test_a_failing_tool_makes_the_whole_run_non_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE arm. The entire point is that a failure cannot report success."""
    _touch(tmp_path / "a.py")
    _stub_rcs(monkeypatch, {"ty": 1})

    assert check.main(tmp_path, ["a.py"]) == 1


def test_all_tools_pass_is_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTROL ARM: the run can actually reach 0, so the arm above discriminates."""
    _touch(tmp_path / "a.py")
    _stub_rcs(monkeypatch, {})

    assert check.main(tmp_path, ["a.py"]) == 0


def test_every_tool_runs_even_after_one_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One pass must report everything wrong with the file, not the first thing.

    Stopping at the first failure turns one fast check into three slow ones —
    fix an import order, re-run, and only then discover `ty` had an opinion.
    """
    _touch(tmp_path / "a.py")
    seen = _stub_rcs(monkeypatch, {"ruff": 1})

    check.run(tmp_path, ["a.py"])

    assert [argv[2] for argv in seen] == ["ruff", "ruff", "ty"]


def test_a_skipped_tool_is_never_rendered_as_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SKIP, ok and FAIL are three states, and collapsing two of them is the bug.

    With no test path given, pytest is not run — and "did not run" must not
    appear as `rc=0 ok`. That collapse is the same shape as a piped gate: a
    question that was never asked, displayed as an answer.
    """
    _touch(tmp_path / "a.py")
    _stub_rcs(monkeypatch, {})

    rendered = check.render(check.run(tmp_path, ["a.py"]))

    assert "pytest   SKIP" in rendered
    assert "pytest   rc=" not in rendered


def test_nothing_checkable_is_a_failure_not_a_quiet_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`kb-check -- src/x.rs` must not read as "x.rs is clean".

    An argument the tool did not understand is the cheapest possible false
    green, and the one most likely to be believed — the command looked like it
    worked.
    """
    _touch(tmp_path / "x.rs", "fn main() {}\n")
    _stub_rcs(monkeypatch, {})

    assert check.main(tmp_path, ["x.rs"]) == 2


def test_a_directory_with_no_python_in_it_is_a_failure_not_a_clean_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The BLOCKING finding: three tools warn-and-exit-0, rendering as `rc=0 ok`.

    ruff, `ruff format --check` and ty all answer "no Python files found" with a
    **warning and exit 0** — they were handed nothing, and they report success
    rather than skip. So forwarding a directory containing no `.py` files put
    three `rc=0 ok` rows in the summary and returned 0 for a directory nobody
    checked anything in.

    That is the module's own thesis inverted: *"nothing to check" is a FAILURE,
    not a quiet 0* — and it failed for the case a dev-loop user actually hits: a
    typo'd path, the wrong directory, an empty scratch dir. (Cold lane, round 1.)

    THE `chdir` IS THE TEST, and without it this could not fail — round 2 proved
    that by reverting `check.py` alone and watching this stay green. The pre-fix
    `python_paths` stat'd against the PROCESS CWD, which under pytest is the real
    repo root; there is no `empty/` there, so the buggy code returned `[]` and
    `main` reached 2 through the pre-existing "nothing ran" branch — the right
    number for the wrong reason, which is indistinguishable from a pass.

    The bug only reproduces when the process CWD is the root being checked, i.e.
    the realistic `mise run` case. So the fixture has to BE that case. A test
    whose assertion is satisfied by pre-existing behaviour rather than by the fix
    is exactly what no mutation sweep can see, because the sweep mutates
    production code and this test was never reading it.

    The stub returns 0 for everything ON PURPOSE — it reproduces the real tools'
    behaviour, so the assertion cannot be satisfied by a tool happening to fail.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty" / "README.md").write_text("no python here\n", encoding="utf-8")
    _stub_rcs(monkeypatch, {})

    assert check.main(tmp_path, ["empty"]) == 2


def test_a_directory_that_does_hold_python_still_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: the emptiness check must not stop real directories working.

    Without this, "no directory is ever checkable" passes the test above and
    breaks the task's most useful invocation.
    """
    (tmp_path / "pkg").mkdir()
    _touch(tmp_path / "pkg" / "mod.py")
    _stub_rcs(monkeypatch, {})

    assert check.main(tmp_path, ["pkg"]) == 0


def test_a_directory_whose_only_python_is_tool_excluded_is_not_checkable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The FIRST fix closed only the instance it was handed.

    `rglob("*.py")` does not apply ruff/ty exclusions, so a directory whose only
    Python sits under `.venv` (or `graphify-out`, `node_modules`) answered True,
    ruff then reported "No Python files found" and exited **0**, and the summary
    printed three `rc=0 ok` rows — the identical false green the round-1
    BLOCKING finding named, one layer narrower. A finding is a SAMPLE of a
    class.

    Ruff is stubbed to return what it really returns for that input — empty
    output — so the assertion is about OUR handling of that answer, not about
    ruff's behaviour, which is measured separately and recorded in the
    docstring.
    """
    (tmp_path / "proj" / ".venv" / "lib").mkdir(parents=True)
    _touch(tmp_path / "proj" / ".venv" / "lib" / "mod.py")
    monkeypatch.setattr(check, "_ruff_would_check", lambda _root, _paths: "")

    assert check.holds_python(tmp_path, ["proj"]) is False


def test_a_directory_ruff_would_really_check_is_checkable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: asking ruff must not make every directory unanswerable.

    Without this, `_ruff_would_check` returning "" unconditionally passes the
    test above and breaks the task's most useful invocation — the same
    over-correction the previous round's control arm caught.
    """
    (tmp_path / "pkg").mkdir()
    _touch(tmp_path / "pkg" / "mod.py")
    monkeypatch.setattr(check, "_ruff_would_check", lambda _root, _paths: "pkg/mod.py")

    assert check.holds_python(tmp_path, ["pkg"]) is True


def test_ruff_failing_to_answer_is_not_a_clean_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FAIL-CLOSED: an unanswerable question must not read as "nothing wrong".

    If ruff cannot be run at all, `_ruff_would_check` returns "" and `main`
    exits 2. The tempting alternative — assume there is Python and let the tools
    decide — hands the verdict to three tools that were never launched.
    """

    def _boom(_argv: tuple[str, ...], **_kw: object) -> None:
        raise OSError("ruff is gone")

    (tmp_path / "pkg").mkdir()
    _touch(tmp_path / "pkg" / "mod.py")
    monkeypatch.setattr(check.subprocess, "run", _boom)

    assert check.holds_python(tmp_path, ["pkg"]) is False


def test_a_named_python_file_skips_the_ruff_question_entirely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `.py` argument must not pay a subprocess to be believed.

    Also the arm on fail-closed NOT over-reaching: with ruff unrunnable, a named
    `.py` file is still checkable, because the tools' non-zero for an absent
    file is the correct answer and must still be reached.
    """

    def _boom(_argv: tuple[str, ...], **_kw: object) -> None:
        raise AssertionError("ruff must not be consulted for a named .py path")

    monkeypatch.setattr(check.subprocess, "run", _boom)

    assert check.holds_python(tmp_path, ["a.py"]) is True


def test_a_named_python_file_reaches_the_tools_even_if_absent(tmp_path: Path) -> None:
    """A `.py` path is trusted WITHOUT a stat, and that is deliberate.

    The tools exit non-zero for a file that is not there, and that non-zero is
    the correct answer — `kb-check -- typo.py` must report FAIL, not SKIP.
    Statting first would convert a real failure into "nothing to check".
    """
    assert check.holds_python(tmp_path, ["nonexistent.py"]) is True


def test_no_paths_at_all_is_also_a_failure(tmp_path: Path) -> None:
    assert check.main(tmp_path, []) == 2
    assert check.main(tmp_path, ["--verbose"]) == 2


def test_a_source_file_pulls_in_its_sibling_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Editing a module should run the tests that cover it, without being asked."""
    _touch(tmp_path / "python" / "src" / "kb_setup" / "widget.py")
    _touch(tmp_path / "tests" / "test_widget.py")
    seen = _stub_rcs(monkeypatch, {})

    check.run(tmp_path, ["python/src/kb_setup/widget.py"])

    assert any("pytest" in argv and "tests/test_widget.py" in argv for argv in seen)


def test_a_sibling_that_does_not_exist_is_not_invented(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM on the convention: it fires on existence, not on the name.

    Handing pytest a path that is not there makes it exit non-zero for a reason
    that has nothing to do with the code — a red that means "your guess was
    wrong" while reading as "your tests failed".
    """
    _touch(tmp_path / "python" / "src" / "kb_setup" / "lonely.py")
    _stub_rcs(monkeypatch, {})

    outcomes = {o.tool: o for o in check.run(tmp_path, ["python/src/kb_setup/lonely.py"])}

    assert outcomes["pytest"].skipped


def test_a_test_file_is_not_given_to_pytest_twice(tmp_path: Path) -> None:
    """A path that IS a test needs no sibling, and the target list stays tidy.

    NOT a correctness fix, and the docstring here used to say it was — "pytest
    collects a file once per mention, so the summary would report twice the
    tests". Measured against the real pytest: an exact duplicate collects
    **14**, identical to the file alone, and `tests/test_check.py tests/`
    collects **2101**, identical to the directory alone. pytest deduplicates by
    node id, containment included.

    Kept because `render` echoes the target list and a repeated path invites a
    reader to reconcile a duplicate that means nothing.
    """
    _touch(tmp_path / "tests" / "test_widget.py")

    assert check.test_paths(tmp_path, ["tests/test_widget.py", "tests/test_widget.py"]) == [
        "tests/test_widget.py"
    ]


def test_the_tests_directory_reaches_pytest(tmp_path: Path) -> None:
    """`kb-check -- tests/` must RUN the tests, not report SKIP.

    It reported `pytest SKIP  no applicable path was given` while ruff, format
    and ty all ran over the same argument — this module's own failure class one
    layer down, on the most obvious way to invoke it. Found by dogfooding the
    tool on this repo, not by any test, which is why this one exists.
    """
    assert check.test_paths(tmp_path, ["tests"]) == ["tests"]
    assert check.test_paths(tmp_path, ["tests/"]) == ["tests/"]


def test_a_non_test_directory_does_not_reach_pytest(tmp_path: Path) -> None:
    """CONTROL ARM: the directory arm keys on `tests`, not on being a directory.

    Without this, "any directory goes to pytest" would pass the test above and
    hand `python/src/` to pytest on every run — collecting nothing, slowly, and
    reporting an exit code about the wrong question.
    """
    assert check.test_paths(tmp_path, ["python/src/kb_setup"]) == []


def test_a_directory_is_passed_through_untouched(tmp_path: Path) -> None:
    """The three tools each walk a directory with their OWN exclusion rules.

    Expanding it here would mean reimplementing all three and getting at least
    one wrong — a file ruff excludes and this module does not would be reported
    against rules its own config says do not apply.
    """
    (tmp_path / "python").mkdir()

    assert check.python_paths(tmp_path, ["python", "a.py", "notes.md"]) == ["python", "a.py"]


def test_a_relative_directory_resolves_against_the_repo_not_the_cwd(tmp_path: Path) -> None:
    """`python_paths` and `holds_python` must agree about what exists.

    They briefly did not: one stat'd `Path(p)` against the process CWD, the
    other resolved against `repo_root`. A directory genuinely holding `.py`
    files was then present to one and absent to the other, and every tool came
    back SKIP for a good argument. Invisible under `mise run`, which starts at
    the repo root — which is exactly why it needs a test rather than a habit.
    """
    (tmp_path / "pkg").mkdir()
    _touch(tmp_path / "pkg" / "mod.py")

    assert check.python_paths(tmp_path, ["pkg"]) == ["pkg"]
    assert check.holds_python(tmp_path, ["pkg"]) is True


def test_a_tool_that_cannot_start_is_distinguishable_from_one_that_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tool that could not START is not a tool that disagreed with the code.

    Both are non-zero, so no pass/fail decision changes — but a run reporting
    `rc=127` says fix your environment, and `rc=1` says fix your file.
    """

    def _boom(_argv: tuple[str, ...], **_kw: object) -> None:
        raise OSError("no such tool")

    monkeypatch.setattr(check.subprocess, "run", _boom)
    _touch(tmp_path / "a.py")

    outcomes = {o.tool: o for o in check.run(tmp_path, ["a.py"])}

    assert outcomes["ruff"].rc == check.RC_COULD_NOT_RUN
    assert not outcomes["ruff"].passed


def test_format_is_checked_never_applied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """This reports; it does not rewrite the file you are mid-thought in.

    `mise run fmt` is the verb that writes. A dev-loop helper that silently
    reformats is the same surprise as `hk fix` running where `hk check` was
    meant.
    """
    _touch(tmp_path / "a.py")
    seen = _stub_rcs(monkeypatch, {})

    check.run(tmp_path, ["a.py"])

    formatter = next(argv for argv in seen if "format" in argv)
    assert "--check" in formatter


# --------------------------------------------------------------------------
# The `check()` boundary (§2 R5) — what the bare integers could NOT express
# --------------------------------------------------------------------------
#
# `main` returns an int and is covered above; those assertions are the
# regression arm proving the Result refactor changed no observable exit code.
# The arms below test the thing that is genuinely NEW: the two states that were
# both `return 2` are now different types, and the state that was `return 1` is
# now an `Ok`. None of the pre-existing tests can fail if that distinction is
# lost, because an int cannot carry it.


def test_findings_are_ok_not_err(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE point of the change: a run that FOUND something still RAN.

    Before, this was `return 1` — indistinguishable in type from a failure to
    run. If someone "simplifies" this back to an `Err`, this is the only test
    that notices; `main` still returns 1 either way.
    """
    _touch(tmp_path / "a.py")
    _stub_rcs(monkeypatch, {"ty": 1})

    result = check.check(tmp_path, ["a.py"])

    assert isinstance(result, Ok)
    assert result.rc is Rc.FINDINGS
    # Mirror the filter `check()` itself applies. `passed` is also False for a
    # SKIPPED tool (here: pytest, because `a.py` has no sibling test), so
    # filtering on `passed` alone would assert something this module never
    # claims — a skip is not a failure.
    failed = [o.tool for o in result.value if not o.skipped and not o.passed]
    assert failed == ["ty"]


def test_a_clean_run_is_ok_with_rc_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTROL ARM for the test above — `Ok` is reachable with BOTH rcs."""
    _touch(tmp_path / "a.py")
    _stub_rcs(monkeypatch, {})

    result = check.check(tmp_path, ["a.py"])

    assert isinstance(result, Ok)
    assert result.rc is Rc.OK


def test_no_paths_is_err(tmp_path: Path) -> None:
    """A malformed request cannot run, so it is an `Err`."""
    result = check.check(tmp_path, [])

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert "pass one or more paths" in result.message


def test_nothing_checked_is_err_and_says_so(tmp_path: Path) -> None:
    """The false-green this module exists to remove, now carried in the TYPE.

    `kb-check -- x.rs` checked nothing. It was `return 2`, the same integer a
    malformed request returned; it is now an `Err` whose message states the
    reason, which is what makes it greppable per R9.
    """
    _touch(tmp_path / "x.rs", "fn main() {}\n")

    result = check.check(tmp_path, ["x.rs"])

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert "nothing was checked" in result.message


def test_the_two_former_rc_2_cases_are_now_distinguishable(tmp_path: Path) -> None:
    """Both were `return 2`. They are still exit code 2 — and now tell apart.

    This is the whole justification for the refactor stated as one assertion:
    same observable exit code, different in-process value.
    """
    _touch(tmp_path / "x.rs", "fn main() {}\n")

    malformed = check.check(tmp_path, [])
    nothing_ran = check.check(tmp_path, ["x.rs"])

    assert exit_code(malformed) == exit_code(nothing_ran) == 2
    assert malformed != nothing_ran
