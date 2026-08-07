"""Tests for `kb_setup.arms` — the mutation harness promoted to a module (#160).

Two of these ARE the acceptance criteria, and both are CONTROL-ARMED: they run
the same scenario with the protection removed and assert the opposite outcome. A
test that has only ever seen the protected path cannot tell you the protection
does anything.

- `test_a_stale_pyc_is_really_used_and_the_purge_prevents_it` measures the CPython
  rule itself — `(mtime, size)` — by writing a same-size edit and restoring the
  original mtime with `os.utime`, rather than racing the clock.
- `test_two_same_size_arms_die_and_survive_without_the_purge` runs the real
  `arms.run()` over a synthetic project seeded with an UNCHECKED_HASH `.pyc`,
  which CPython uses regardless of mtime. That makes the collision deterministic
  instead of timing-dependent, so the test cannot be flaky in the direction that
  reads as success.
"""

from __future__ import annotations

import os
import py_compile
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from kb_setup import arms

if TYPE_CHECKING:
    from collections.abc import Callable

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _victim(tmp_path: Path) -> Path:
    """A one-module project plus two tests that assert the module's two values."""
    module = tmp_path / "victim.py"
    module.write_text("VALUE = 1\nOTHER = 1\n", encoding="utf-8")
    (tmp_path / "test_victim.py").write_text(
        textwrap.dedent(
            """
            import victim


            def test_value_is_one():
                assert victim.VALUE == 1


            def test_other_is_one():
                assert victim.OTHER == 1
            """
        ),
        encoding="utf-8",
    )
    return module


_CONTROL = arms.Arm("A0", "victim.py", "VALUE = 1", "VALUE = 1  # c", control=True)
_OTHER = arms.Arm("A1", "victim.py", "OTHER = 1", "OTHER = 9", test="test_other_is_one")


def _spec(*arm: arms.Arm) -> arms.Spec:
    """A spec over the synthetic project, defaulting to the control arm alone."""
    return arms.Spec(suites=("test_victim.py",), arms=arm or (_CONTROL,))


def _fake_suite(results: list[tuple[int, str]]) -> Callable[[], tuple[int, str]]:
    """A suite runner returning canned results in order, so no real pytest runs."""
    calls = iter(results)

    def run() -> tuple[int, str]:
        return next(calls)

    return run


def _write_spec(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "spec.toml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# protection 1 — bytecode invalidation
# --------------------------------------------------------------------------- #


def test_a_stale_pyc_is_really_used_and_the_purge_prevents_it(tmp_path: Path) -> None:
    """The CPython (mtime, size) rule, both arms: stale bytecode wins until purged."""
    module = tmp_path / "victim.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")

    # This test needs bytecode to BE written, so it must not inherit the very
    # variable the harness sets. Running the suite under `kb-arms` exports
    # PYTHONDONTWRITEBYTECODE=1, the child inherited it, no `.pyc` was ever
    # written, and the test failed — a test whose result depended on which tool
    # invoked it. Found by running this module's own arms against itself.
    writes_bytecode = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}

    def read_value() -> str:
        proc = subprocess.run(
            [sys.executable, "-c", "import victim; print(victim.VALUE)"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
            env=writes_bytecode,
        )
        return proc.stdout.strip()

    assert read_value() == "1"
    assert (tmp_path / "__pycache__").is_dir(), "bytecode must exist for the arm to be meaningful"
    stat = module.stat()

    # A same-SIZE edit with the ORIGINAL mtime restored: exactly what two adjacent
    # single-token arms produce, made deterministic rather than left to the clock.
    module.write_text("VALUE = 2\n", encoding="utf-8")
    os.utime(module, (stat.st_atime, stat.st_mtime))

    assert read_value() == "1", "control arm: without a purge the STALE bytecode is used"

    assert arms.purge_bytecode(tmp_path) == 1
    assert read_value() == "2", "with the purge, an arm measures the code it actually wrote"


def test_two_same_size_arms_die_and_survive_without_the_purge(tmp_path: Path) -> None:
    """#160's criterion: same-size arms back to back, armed by removing the purge."""
    _victim(tmp_path)
    spec = _spec(
        _CONTROL,
        arms.Arm("A1", "victim.py", "VALUE = 1", "VALUE = 9", test="test_value_is_one"),
        arms.Arm("A2", "victim.py", "OTHER = 1", "OTHER = 9", test="test_other_is_one"),
    )
    for arm in spec.arms[1:]:
        assert len(arm.old) == len(arm.new), f"{arm.id} must be a same-size edit"

    def seed_stale_bytecode() -> None:
        """An UNCHECKED_HASH `.pyc` is used regardless of mtime — a deterministic stale one.

        It is seeded before BOTH runs on purpose. Seeding only the unprotected
        one would leave `run_suite`'s `purge(repo_root)` CALL unarmed: with
        `PYTHONDONTWRITEBYTECODE=1` no `.pyc` is ever written during a run, so
        deleting that call would change nothing and the mutation would survive —
        which is precisely the regression this module exists to stop.
        """
        py_compile.compile(
            str(tmp_path / "victim.py"),
            invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
            doraise=True,
        )

    seed_stale_bytecode()
    protected = arms.run(spec, tmp_path)
    assert protected.ok, protected.render()
    assert [row.verdict for row in protected.rows] == [
        arms.Verdict.CONTROL_HELD,
        arms.Verdict.DIED,
        arms.Verdict.DIED,
    ]

    # The arm: same stale bytecode, purging disabled. Both mutations must be missed.
    seed_stale_bytecode()
    unprotected = arms.run(spec, tmp_path, purge=lambda _root: 0)
    assert not unprotected.ok
    assert [row.verdict for row in unprotected.rows] == [
        arms.Verdict.CONTROL_HELD,
        arms.Verdict.SURVIVED,
        arms.Verdict.SURVIVED,
    ], "without the purge both same-size arms are served stale bytecode"


def test_a_suite_run_writes_no_bytecode_of_its_own(tmp_path: Path, monkeypatch) -> None:
    """The SECOND bytecode mitigation, armed by its effect rather than its spelling.

    `PYTHONDONTWRITEBYTECODE=1` survived the first sweep: the purge runs before
    every suite, so anything written during arm N is gone before arm N+1 and no
    verdict changes. That made it look inert. It is not — `purge_bytecode` can
    fail, and this is the second line. Asserting the variable is in the env would
    only be the code agreeing with itself, so this asserts the OBSERVABLE
    consequence: the purge runs BEFORE the suite, so a `.pyc` written during it
    would still be on disk afterwards.

    `delenv` is the load-bearing line, and the arm proves it. `run_suite` builds
    `{**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}`; when this suite is run BY
    the harness the parent already exports that variable, so deleting the
    explicit key changes nothing and the mutation survives — measured, rc=0 with
    the variable inherited against rc=1 without it. The harness was setting the
    condition it was trying to measure. Clearing it here makes the test give the
    same answer whoever invoked it.
    """
    monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)
    _victim(tmp_path)
    rc, _ = arms.run_suite(tmp_path, ("test_victim.py",))
    assert rc == 0
    assert not (tmp_path / "__pycache__").exists()


def test_a_purge_that_did_not_purge_raises_rather_than_counting(tmp_path: Path) -> None:
    """A mitigation that lies about itself is the one failure this module cannot absorb."""
    cache = tmp_path / "pkg" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "x.pyc").write_bytes(b"stale")
    assert arms.purge_bytecode(tmp_path) == 1

    cache.mkdir(parents=True)
    (cache / "x.pyc").write_bytes(b"stale")
    cache.parent.chmod(0o500)  # read+execute: the entry cannot be unlinked
    try:
        with pytest.raises(RuntimeError, match="could not purge"):
            arms.purge_bytecode(tmp_path)
    finally:
        cache.parent.chmod(0o700)


# --------------------------------------------------------------------------- #
# protection 2 — a probe that never ran is not a death
# --------------------------------------------------------------------------- #


def test_a_pattern_that_does_not_match_is_broken_not_a_death(tmp_path: Path) -> None:
    _victim(tmp_path)
    arm = arms.Arm("A1", "victim.py", "NOT PRESENT", "x", test="test_value_is_one")
    row = arms._run_arm(arm, tmp_path, _fake_suite([(1, "FAILED test_value_is_one")]))
    assert row.verdict is arms.Verdict.BROKEN_ABSENT
    assert not row.verdict.is_pass


def test_a_pattern_that_matches_more_than_once_is_broken_not_a_death(tmp_path: Path) -> None:
    """Three 'survivors' in one round were a `str.replace` hitting the wrong occurrence."""
    module = _victim(tmp_path)
    module.write_text("VALUE = 1\nOTHER = 1\nSPARE = 1\n", encoding="utf-8")
    arm = arms.Arm("A1", "victim.py", " = 1", " = 9", test="test_value_is_one")
    row = arms._run_arm(arm, tmp_path, _fake_suite([(1, "FAILED test_value_is_one")]))
    assert row.verdict is arms.Verdict.BROKEN_AMBIGUOUS
    assert "3 times" in row.detail


def test_a_no_op_mutation_is_broken_not_a_survivor(tmp_path: Path) -> None:
    _victim(tmp_path)
    arm = arms.Arm("A1", "victim.py", "VALUE = 1", "VALUE = 1", test="test_value_is_one")
    row = arms._run_arm(arm, tmp_path, _fake_suite([(0, "")]))
    assert row.verdict is arms.Verdict.BROKEN_NO_OP


def test_a_red_suite_that_does_not_name_the_test_is_not_a_death(tmp_path: Path) -> None:
    """The false-DEATH class: red for an unrelated reason must never be credited."""
    _victim(tmp_path)
    arm = arms.Arm("A1", "victim.py", "VALUE = 1", "VALUE = 9", test="test_value_is_one")
    unrelated = arms._run_arm(arm, tmp_path, _fake_suite([(2, "ERROR collecting test_other.py")]))
    assert unrelated.verdict is arms.Verdict.BROKEN_WRONG_TEST

    named = arms._run_arm(arm, tmp_path, _fake_suite([(1, "FAILED t.py::test_value_is_one")]))
    assert named.verdict is arms.Verdict.DIED, "control: the same rc DOES count when named"


def test_a_genuinely_unkilled_mutation_is_a_survivor_not_a_broken_probe(tmp_path: Path) -> None:
    """The one row that means 'your tests have a gap' must stay distinguishable."""
    _victim(tmp_path)
    arm = arms.Arm("A1", "victim.py", "VALUE = 1", "VALUE = 9", test="test_value_is_one")
    row = arms._run_arm(arm, tmp_path, _fake_suite([(0, "2 passed")]))
    assert row.verdict is arms.Verdict.SURVIVED
    assert not row.verdict.is_broken_probe


# --------------------------------------------------------------------------- #
# protection 3 — the mandatory green rows
# --------------------------------------------------------------------------- #


def test_a_red_baseline_aborts_before_any_arm_runs(tmp_path: Path) -> None:
    report = arms.run(_spec(), tmp_path, suite=_fake_suite([(1, "boom")]))
    assert report.rows == ()
    assert report.aborted is not None
    assert not report.ok


def test_a_control_arm_that_dies_aborts_the_run(tmp_path: Path) -> None:
    _victim(tmp_path)
    # Four canned results, though an unmutated run consumes two: a harness that
    # wrongly CONTINUED past the broken control must fail on the assertion below
    # rather than on a StopIteration, or the arm proving that reads as a crash.
    report = arms.run(
        _spec(_CONTROL, _OTHER),
        tmp_path,
        suite=_fake_suite([(0, ""), (1, "boom"), (0, ""), (0, "")]),
    )
    assert report.rows[0].verdict is arms.Verdict.CONTROL_BROKEN
    assert len(report.rows) == 1, "no arm may run after the harness is shown to be lying"
    assert not report.ok


def test_controls_run_before_mutations_whatever_their_spec_order(tmp_path: Path) -> None:
    _victim(tmp_path)
    report = arms.run(_spec(_OTHER, _CONTROL), tmp_path)
    assert [row.arm.id for row in report.rows] == ["A0", "A1"]


def test_a_run_whose_restored_row_is_red_is_not_ok(tmp_path: Path) -> None:
    _victim(tmp_path)
    report = arms.run(_spec(), tmp_path, suite=_fake_suite([(0, ""), (0, ""), (1, "dirty")]))
    assert report.restored_rc == 1
    assert not report.ok
    assert "TREE LEFT DIRTY" in report.render()


def test_a_report_with_no_control_row_is_not_ok() -> None:
    """`ok` is conjunctive on purpose: an all-green sweep with no control proves nothing."""
    row = arms.Row(_OTHER, arms.Verdict.DIED, 1, "test_other_is_one failed")
    assert not arms.Report(baseline_rc=0, rows=(row,), restored_rc=0).ok
    control = arms.Row(_CONTROL, arms.Verdict.CONTROL_HELD, 0, "green")
    assert arms.Report(baseline_rc=0, rows=(control, row), restored_rc=0).ok


def test_a_report_with_no_rows_at_all_is_not_ok() -> None:
    assert not arms.Report(baseline_rc=0, rows=(), restored_rc=0).ok


def test_a_dry_report_never_claims_a_baseline_or_a_restored_row(tmp_path: Path) -> None:
    """Found by running the thing: the first version printed two green rows that never ran."""
    _victim(tmp_path)
    rendered = arms.Report(baseline_rc=None, rows=arms.check(_spec(), tmp_path), dry=True).render()
    assert "DRY RUN" in rendered
    assert "baseline" not in rendered
    assert "restored" not in rendered
    assert "arms died" not in rendered


def test_a_dry_report_is_never_ok(tmp_path: Path) -> None:
    """Validating the patterns is not running the arms, so it can never be a pass."""
    _victim(tmp_path)
    assert not arms.Report(baseline_rc=None, rows=arms.check(_spec(), tmp_path), dry=True).ok


def test_the_file_is_restored_after_every_arm(tmp_path: Path) -> None:
    module = _victim(tmp_path)
    before = module.read_text(encoding="utf-8")
    arms.run(_spec(_CONTROL, _OTHER), tmp_path)
    assert module.read_text(encoding="utf-8") == before


def test_a_restore_that_did_not_take_raises_rather_than_returning(
    tmp_path: Path, monkeypatch
) -> None:
    """A SURVIVING mutant the cold lane found: deleting `_restore`'s verify changed nothing.

    Nothing in the suite exercised a write that raises no exception and still
    leaves the wrong bytes. The stub IS the failure being modelled — a write that
    silently does not take (a full or read-only-by-another-process filesystem, or
    a second writer between the write and the read) — not a stand-in for the code
    under test.
    """
    target = tmp_path / "victim.py"
    target.write_text("MUTATED\n", encoding="utf-8")
    monkeypatch.setattr(Path, "write_text", lambda *_a, **_k: 0)
    with pytest.raises(RuntimeError, match="failed to restore"):
        arms._restore(target, "ORIGINAL\n")


def test_a_restore_that_took_returns_quietly(tmp_path: Path) -> None:
    """The control for the row above: the same call on a working filesystem is silent."""
    target = tmp_path / "victim.py"
    target.write_text("MUTATED\n", encoding="utf-8")
    arms._restore(target, "ORIGINAL\n")
    assert target.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_the_file_is_restored_even_when_the_suite_raises(tmp_path: Path) -> None:
    module = _victim(tmp_path)
    before = module.read_text(encoding="utf-8")

    def explode() -> tuple[int, str]:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        arms._run_arm(_OTHER, tmp_path, explode)
    assert module.read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------- #
# containment — an arm may only mutate this project
# --------------------------------------------------------------------------- #


def test_an_absolute_file_escapes_the_repo_and_is_refused(tmp_path: Path) -> None:
    """`Path("/repo") / "/etc/hosts"` is `/etc/hosts`, and this module WRITES there."""
    outside = tmp_path.parent / "outside_the_repo.txt"
    outside.write_text("canary\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    arm = arms.Arm("A1", str(outside), "canary", "MUTATED", test="test_x")
    row = arms._run_arm(arm, repo, _fake_suite([(1, "FAILED test_x")]))
    assert row.verdict is arms.Verdict.BROKEN_ESCAPES_REPO
    assert outside.read_text(encoding="utf-8") == "canary\n", "it must not have been touched"


def test_a_traversal_out_of_the_repo_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "sibling.txt").write_text("canary\n", encoding="utf-8")
    arm = arms.Arm("A1", "../sibling.txt", "canary", "MUTATED", test="test_x")
    assert arms._run_arm(arm, repo, _fake_suite([(1, "")])).verdict is (
        arms.Verdict.BROKEN_ESCAPES_REPO
    )


def test_a_symlink_pointing_out_of_the_repo_is_refused(tmp_path: Path) -> None:
    """Lexical containment would pass this straight through; `.resolve()` is why it does not."""
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("canary\n", encoding="utf-8")
    (repo / "looks_local.py").symlink_to(outside)
    arm = arms.Arm("A1", "looks_local.py", "canary", "MUTATED", test="test_x")
    row = arms._run_arm(arm, repo, _fake_suite([(1, "")]))
    assert row.verdict is arms.Verdict.BROKEN_ESCAPES_REPO
    assert outside.read_text(encoding="utf-8") == "canary\n"


def test_an_ordinary_in_repo_file_still_resolves(tmp_path: Path) -> None:
    """The control: containment must not refuse the normal case it exists to allow."""
    _victim(tmp_path)
    assert arms.contained_path(tmp_path, "victim.py") == (tmp_path / "victim.py").resolve()
    assert arms._run_arm(_OTHER, tmp_path, _fake_suite([(1, "test_other_is_one")])).verdict is (
        arms.Verdict.DIED
    )


def test_dry_run_refuses_an_escaping_arm_too(tmp_path: Path) -> None:
    """`--dry-run` reads the target, so it needs the same boundary as the real run."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "outside.txt").write_text("canary\n", encoding="utf-8")
    spec = arms.Spec(("t.py",), (arms.Arm("A1", "../outside.txt", "canary", "X", test="t"),))
    assert arms.check(spec, repo)[0].verdict is arms.Verdict.BROKEN_ESCAPES_REPO


def test_a_spec_naming_a_file_outside_the_repo_is_refused_before_anything_runs(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    body = _VALID.replace('file = "victim.py"', 'file = "/etc/hosts"', 1)
    with pytest.raises(arms.SpecError, match="resolves outside the repo"):
        arms.load_spec(_write_spec(tmp_path, body), repo)


# --------------------------------------------------------------------------- #
# unreadable targets — a ValueError is not an OSError
# --------------------------------------------------------------------------- #


def test_a_non_utf8_target_takes_a_verdict_instead_of_raising(tmp_path: Path) -> None:
    """`UnicodeDecodeError` is a `ValueError`, so `except OSError` missed it entirely."""
    (tmp_path / "binary.py").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
    arm = arms.Arm("A1", "binary.py", "PNG", "JPG", test="test_x")
    row = arms._run_arm(arm, tmp_path, _fake_suite([(1, "")]))
    assert row.verdict is arms.Verdict.BROKEN_ABSENT
    assert "cannot read" in row.detail


def test_a_non_utf8_spec_is_refused_rather_than_raising(tmp_path: Path) -> None:
    path = tmp_path / "spec.toml"
    path.write_bytes(b'suites = ["t.py"]\n# \xff\xfe\n')
    with pytest.raises(arms.SpecError):
        arms.load_spec(path, tmp_path)


# --------------------------------------------------------------------------- #
# the spec loader
# --------------------------------------------------------------------------- #

_VALID = """
    suites = ["tests/test_victim.py"]

    [[arm]]
    id = "A0"
    control = true
    file = "victim.py"
    old = '''VALUE = 1'''
    new = '''VALUE = 1  # control'''

    [[arm]]
    id = "A1"
    file = "victim.py"
    old = '''OTHER = 1'''
    new = '''OTHER = 9'''
    test = "test_other_is_one"
    meaning = "the other value is unchecked"
"""


def test_a_valid_spec_loads(tmp_path: Path) -> None:
    spec = arms.load_spec(_write_spec(tmp_path, _VALID), tmp_path)
    assert spec.suites == ("tests/test_victim.py",)
    assert [arm.id for arm in spec.arms] == ["A0", "A1"]
    assert spec.arms[0].control is True
    assert spec.arms[0].test is None
    assert spec.arms[1].test == "test_other_is_one"
    assert spec.arms[1].meaning == "the other value is unchecked"


def test_a_literal_string_keeps_backslashes_and_quotes_untouched(tmp_path: Path) -> None:
    """The mechanism is literal containment, so escape processing would silently break it."""
    fragment = r"""    if re.match(r"^ {0,3}(?P<f>`{3,})", line) and x != "\\n":"""
    path = _write_spec(
        tmp_path,
        f"""
        suites = ["t.py"]

        [[arm]]
        id = "A0"
        control = true
        file = "victim.py"
        old = '''{fragment}'''
        new = '''{fragment}  # control'''
        """,
    )
    assert arms.load_spec(path, tmp_path).arms[0].old == fragment


def test_a_spec_with_no_control_arm_is_refused(tmp_path: Path) -> None:
    body = _VALID.replace("control = true", 'test = "test_value_is_one"', 1)
    with pytest.raises(arms.SpecError, match="no `control = true` arm"):
        arms.load_spec(_write_spec(tmp_path, body), tmp_path)


def test_a_mutation_arm_with_no_test_is_refused(tmp_path: Path) -> None:
    body = _VALID.replace('test = "test_other_is_one"', "", 1)
    with pytest.raises(arms.SpecError, match="`test` is required"):
        arms.load_spec(_write_spec(tmp_path, body), tmp_path)


def test_a_control_arm_naming_a_test_is_refused(tmp_path: Path) -> None:
    body = _VALID.replace("control = true", 'control = true\ntest = "test_value_is_one"', 1)
    with pytest.raises(arms.SpecError, match="must not name a `test`"):
        arms.load_spec(_write_spec(tmp_path, body), tmp_path)


def test_duplicate_arm_ids_are_refused(tmp_path: Path) -> None:
    body = _VALID.replace('id = "A1"', 'id = "A0"', 1)
    with pytest.raises(arms.SpecError, match="duplicate arm id"):
        arms.load_spec(_write_spec(tmp_path, body), tmp_path)


def test_a_mistyped_key_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    """A typo'd `cntrl` would silently demote a control arm to an ordinary one."""
    body = _VALID.replace("control = true", "cntrl = true", 1)
    with pytest.raises(arms.SpecError, match="unknown key"):
        arms.load_spec(_write_spec(tmp_path, body), tmp_path)


def test_every_problem_is_reported_in_one_pass(tmp_path: Path) -> None:
    """A spec is authored in one sitting; one error per run is how it takes six runs."""
    body = _VALID.replace("control = true", 'test = "test_value_is_one"', 1).replace(
        'test = "test_other_is_one"', "", 1
    )
    with pytest.raises(arms.SpecError) as excinfo:
        arms.load_spec(_write_spec(tmp_path, body), tmp_path)
    message = str(excinfo.value)
    assert "`test` is required" in message
    assert "no `control = true` arm" in message


def test_a_spec_whose_arms_all_fail_to_parse_reports_only_those_failures(tmp_path: Path) -> None:
    """The missing-control complaint is suppressed when NO arm parsed, deliberately.

    "You have no control arm" is a claim about a spec that has arms. Adding it to
    a spec where nothing parsed buries the errors that actually explain the
    refusal — this test exists because the first version of the sibling test
    above assumed the opposite and was wrong about the code, not the code about
    the spec.
    """
    body = _VALID.replace("control = true", "", 1).replace('test = "test_other_is_one"', "", 1)
    with pytest.raises(arms.SpecError) as excinfo:
        arms.load_spec(_write_spec(tmp_path, body), tmp_path)
    message = str(excinfo.value)
    assert message.count("`test` is required") == 2
    assert "no `control = true` arm" not in message


def test_an_arm_missing_a_required_key_is_refused_and_names_it(tmp_path: Path) -> None:
    """Found by a survivor: the first sweep's arm for this line mutated a branch no test reached."""
    body = _VALID.replace('file = "victim.py"', "", 1)
    with pytest.raises(arms.SpecError, match="missing or non-string `file`"):
        arms.load_spec(_write_spec(tmp_path, body), tmp_path)


def test_a_spec_with_no_arms_is_refused(tmp_path: Path) -> None:
    with pytest.raises(arms.SpecError, match=r"\[\[arm\]\]"):
        arms.load_spec(_write_spec(tmp_path, 'suites = ["t.py"]\n'), tmp_path)


def test_a_spec_with_no_suites_is_refused(tmp_path: Path) -> None:
    body = _VALID.replace('suites = ["tests/test_victim.py"]', "", 1)
    with pytest.raises(arms.SpecError, match="`suites`"):
        arms.load_spec(_write_spec(tmp_path, body), tmp_path)


def test_unparsable_toml_is_a_spec_error_not_a_traceback(tmp_path: Path) -> None:
    with pytest.raises(arms.SpecError):
        arms.load_spec(_write_spec(tmp_path, "suites = [\n"), tmp_path)


# --------------------------------------------------------------------------- #
# --dry-run and the CLI
# --------------------------------------------------------------------------- #


def test_dry_run_names_the_stale_arm_without_running_pytest(tmp_path: Path) -> None:
    _victim(tmp_path)
    stale = arms.Arm("A1", "victim.py", "MOVED = 1", "MOVED = 9", test="test_other_is_one")
    rows = arms.check(_spec(_CONTROL, stale), tmp_path)
    assert [row.verdict for row in rows] == [arms.Verdict.WOULD_APPLY, arms.Verdict.BROKEN_ABSENT]


def test_the_cli_refuses_a_bad_spec_with_rc_2(tmp_path: Path, capsys) -> None:
    path = _write_spec(tmp_path, 'suites = ["t.py"]\n')
    assert arms.main([str(path)], tmp_path) == 2
    assert "SPEC REFUSED" in capsys.readouterr().out


_CLI_SPEC = """
    suites = ["test_victim.py"]

    [[arm]]
    id = "A0"
    control = true
    file = "victim.py"
    old = '''VALUE = 1'''
    new = '''VALUE = 1  # control'''

    [[arm]]
    id = "A1"
    file = "victim.py"
    old = '''{old}'''
    new = '''OTHER = 9'''
    test = "test_other_is_one"
"""


def test_the_cli_dry_run_exits_1_on_a_stale_arm(tmp_path: Path, capsys) -> None:
    _victim(tmp_path)
    path = _write_spec(tmp_path, _CLI_SPEC.format(old="MOVED = 1"))
    assert arms.main([str(path), "--dry-run"], tmp_path) == 1
    assert "1/2 arms would apply" in capsys.readouterr().out


def test_the_cli_runs_a_spec_end_to_end(tmp_path: Path, capsys) -> None:
    _victim(tmp_path)
    path = _write_spec(tmp_path, _CLI_SPEC.format(old="OTHER = 1"))
    assert arms.main([str(path)], tmp_path) == 0
    out = capsys.readouterr().out
    assert "1/1 arms died" in out
    assert "1/1 controls held" in out


def test_the_cli_exits_1_when_an_arm_survives(tmp_path: Path, capsys) -> None:
    """The FAIL direction of the CLI itself: a survivor must not exit 0."""
    _victim(tmp_path)
    (tmp_path / "test_victim.py").write_text(
        "import victim\n\n\ndef test_other_is_one():\n    assert True\n",
        encoding="utf-8",
    )
    path = _write_spec(tmp_path, _CLI_SPEC.format(old="OTHER = 1"))
    assert arms.main([str(path)], tmp_path) == 1
    assert "SURVIVED" in capsys.readouterr().out


def test_the_cli_usage_error_exits_2(tmp_path: Path, capsys) -> None:
    assert arms.main([], tmp_path) == 2
    assert "usage:" in capsys.readouterr().out
