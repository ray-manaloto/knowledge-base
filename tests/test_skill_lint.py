# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.skill_lint` — the #128 gate.

Every test here exists because the corresponding arm was RUN, not assumed. The
FAIL direction is the load-bearing half: a gate verified only on clean input is
decoration (`probes-need-a-control-arm.md` rule 2), and #128 asks for the FAIL
arm by name.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from kb_setup import cli, hook_guard, skill_lint
from kb_setup.result import Err, Ok, Rc, exit_code

_BAD = """# bad
```bash
graphify extract .
graphify query "what does this cover?"
```
Prose mentioning `graphify query` must NOT be flagged.
```json
{"graphify": "extract"}
```
"""

_GOOD = """# good
```bash
mise run kb-build
graphify explain "SomeNode"
git rev-parse HEAD
```
"""


def _skill(root: Path, name: str, body: str) -> None:
    d = root / ".claude" / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")


def test_flags_a_command_a_mise_task_owns(tmp_path: Path) -> None:
    """FAIL arm: the realistic violation is a shell fence telling an agent to run graphify."""
    _skill(tmp_path, "bad", _BAD)
    report = skill_lint.check(tmp_path)
    assert report.failed
    assert [f.command for f in report.findings] == [
        "graphify extract .",
        'graphify query "what does this cover?"',
    ]


def test_finding_carries_the_canonical_task_not_just_a_refusal(tmp_path: Path) -> None:
    """The graph's own doctrine: lint messages inject REMEDIATION, not just denial."""
    _skill(tmp_path, "bad", _BAD)
    remedies = [f.remedy for f in skill_lint.check(tmp_path).findings]
    assert any("mise run kb-build" in r for r in remedies)
    assert any("mise run kb-query" in r for r in remedies)


def test_passes_on_mise_tasks_and_allowed_readonly(tmp_path: Path) -> None:
    """PASS arm, and it is not trivial: three DIFFERENT allow-reasons in one fence."""
    _skill(tmp_path, "good", _GOOD)
    report = skill_lint.check(tmp_path)
    assert not report.failed
    assert report.scanned == (".claude/skills/good/SKILL.md",)


def test_prose_mention_is_not_an_instruction(tmp_path: Path) -> None:
    """A skill DESCRIBING a tool must not trip the gate that governs running it.

    Without this the gate fires on its own documentation, which is how a gate
    loses the readers it exists to serve.
    """
    _skill(tmp_path, "prose", "# p\nRun `graphify query` is described here.\nNo fence at all.\n")
    assert not skill_lint.check(tmp_path).failed


def test_non_shell_fence_is_not_an_instruction(tmp_path: Path) -> None:
    """A json/markdown sample containing the word graphify is data, not a command."""
    _skill(tmp_path, "json", '# j\n```json\n{"cmd": "graphify extract ."}\n```\n')
    assert not skill_lint.check(tmp_path).failed


def test_installer_generated_tree_is_excluded(tmp_path: Path) -> None:
    """`.claude/skills/graphify/**` is regenerated wholesale — not ours to gate.

    Same carve-out and same reason as `md_budget.DEFAULT_EXCLUDED_PREFIXES`.
    """
    _skill(tmp_path, "graphify", _BAD)
    report = skill_lint.check(tmp_path)
    assert report.scanned == ()
    assert not report.failed


def test_no_skills_matched_is_a_skip_not_a_pass(tmp_path: Path) -> None:
    """`0 files` is a gate that never asked the question, so it must not exit 0.

    This is `verify-before-advancing.md`'s rule applied to this gate itself, and
    it is the arm that #214 (md-budget's index-only scope) showed is worth having.

    The code changed from a bare `1` to `Rc.NOT_RUN` in §2 R5. The assertion the
    test's NAME makes — not a pass — is unchanged and still checked below; what
    was wrong before is that `1` also means "we looked and found something",
    which is the opposite of what happened.
    """
    rc = skill_lint.skill_lint_main(tmp_path)

    assert rc == Rc.NOT_RUN
    # The name's claim, asserted separately so a future change to NOT_RUN's
    # value cannot make this test silently stop checking "not a pass".
    assert rc != Rc.OK
    # ...and not the two codes that would MISDESCRIBE it: we did not look
    # (so not FINDINGS), and the request was fine (so not BAD_REQUEST).
    assert rc not in (Rc.FINDINGS, Rc.BAD_REQUEST)


def test_decide_is_injectable_so_the_walker_is_reusable(tmp_path: Path) -> None:
    """`check` must not hard-depend on graphify's redirect table.

    The injection is what makes this a reusable walker rather than a second
    hard-coded copy of hook_guard — the modularity Ray asked for.
    """
    _skill(tmp_path, "any", "# a\n```bash\nsomething-else --flag\n```\n")
    report = skill_lint.check(tmp_path, decide=lambda _c: "USE THE TASK")
    assert [f.remedy for f in report.findings] == ["USE THE TASK"]


def test_shares_one_decision_function_with_the_runtime_guard() -> None:
    """The whole design claim: ONE table, two consumers.

    If this ever fails, the authoring-time gate and the runtime guard have
    forked — the `_safe_lane` writer/reader divergence, one layer up.
    """
    default = inspect.signature(skill_lint.check).parameters["decide"].default
    assert default is hook_guard.decide
    assert hook_guard.decide("graphify extract .") is not None


@pytest.mark.parametrize("fence", ["```bash", "```sh", "```shell", "```console", "```zsh"])
def test_every_shell_fence_marker_is_scanned(tmp_path: Path, fence: str) -> None:
    """A violation must not escape by picking a different fence word.

    A token spelling is a bound (`probes-need-a-control-arm.md` rule 3); this is
    that bound, armed.
    """
    _skill(tmp_path, "f", f"# f\n{fence}\ngraphify extract .\n```\n")
    assert skill_lint.check(tmp_path).failed


def test_a_nested_fence_is_not_an_instruction(tmp_path: Path) -> None:
    """A ```bash block INSIDE a ````markdown example is illustration, not instruction.

    CommonMark closes a fence of N backticks only with N-or-more; a shorter run
    inside is literal text. Without fence-length tracking, a SKILL.md
    documenting *this gate* — the most likely file to contain such an example —
    would be denied for its own example. Found by the cold lane on c20d982.
    """
    body = "# d\n````markdown\n```bash\ngraphify extract .\n```\n````\n"
    _skill(tmp_path, "nested", body)
    assert not skill_lint.check(tmp_path).failed


def test_tilde_fences_are_scanned(tmp_path: Path) -> None:
    """`~~~bash` renders identically to ```bash and must not bypass the gate.

    A marker spelling is a bound (`probes-need-a-control-arm.md` rule 3). This
    one was live: the first implementation returned zero findings for it.
    """
    _skill(tmp_path, "tilde", "# d\n~~~bash\ngraphify extract .\n~~~\n")
    assert skill_lint.check(tmp_path).failed


def test_gate_is_reachable_through_the_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#128's named mutation: delete the CLI wiring line and this must go red.

    Every other test calls `check`/`skill_lint_main` directly, so deleting the
    dispatch branch left all 15 green while `uv run kb-setup skill-lint` was
    already broken — a false green on exactly the regression the ticket named.
    Only the hk step caught it. This closes that, at the level the ticket asked.
    """
    _skill(tmp_path, "bad", _BAD)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["skill-lint"]) == 1

    _skill(tmp_path, "bad", _GOOD)
    assert cli.main(["skill-lint"]) == 0


def test_the_real_repo_passes() -> None:
    """The PASS arm on the actual tree — 6 skills, every command a task or allowed.

    Kept as a test rather than a one-off run so a future skill that regresses is
    caught by `mise run test`, not only by the hk step.
    """
    root = Path(__file__).resolve().parents[1]
    report = skill_lint.check(root)
    assert report.scanned, "glob matched no skills — the gate did not run"
    assert not report.failed, [f"{f.path}:{f.line} {f.command}" for f in report.findings]


# --------------------------------------------------------------------------
# The `check_skill_lint` boundary (§2 R5)
# --------------------------------------------------------------------------
#
# `skill_lint_main` returns an int and is asserted above; those assertions are
# the regression arm proving the Result split changed no exit code. What is NEW
# is that the two non-zero outcomes are now DIFFERENT TYPES — findings are an
# `Ok` carrying the report, "nothing scanned" is an `Err`. No int-returning test
# can fail if that distinction is lost, because both were 127/1 before and are
# 127/1 after.


def test_skill_lint_findings_are_ok_not_err(tmp_path: Path) -> None:
    """A gate that ran and found something SUCCEEDED — the one sentence R5 carries.

    If someone "simplifies" this to an `Err`, every pre-existing exit-code
    assertion in this file stays green. Only this test notices.
    """
    _skill(tmp_path, "bad", _BAD)

    result = skill_lint.check_skill_lint(tmp_path)

    assert isinstance(result, Ok)
    assert result.rc is Rc.FINDINGS
    assert [f.command for f in result.value.findings] == [
        "graphify extract .",
        'graphify query "what does this cover?"',
    ]


def test_skill_lint_clean_tree_is_ok_with_rc_ok(tmp_path: Path) -> None:
    """CONTROL ARM: `Ok` is reachable with BOTH rcs, so the test above discriminates."""
    _skill(tmp_path, "good", _GOOD)

    result = skill_lint.check_skill_lint(tmp_path)

    assert isinstance(result, Ok)
    assert result.rc is Rc.OK


def test_skill_lint_nothing_scanned_is_an_err(tmp_path: Path) -> None:
    """A gate that never looked is a THIRD state, and the type now says so.

    The int has been 127 since §2 R5 and `test_no_skills_matched_is_a_skip_not_a_pass`
    pins it. What that test cannot see is whether 127 arrived as an `Ok` — which
    would assert the gate ran — or as an `Err`, which is the truth.
    """
    result = skill_lint.check_skill_lint(tmp_path)

    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "did not run" in result.message


def test_skill_lint_boundary_prints_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Rendering belongs to `skill_lint_main`; the boundary only returns.

    Armed on the FINDINGS path specifically — the clean path printing nothing
    would be true of a boundary that only forgot to print its failures.
    """
    _skill(tmp_path, "bad", _BAD)

    skill_lint.check_skill_lint(tmp_path)
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""


def test_skill_lint_int_wrapper_is_exit_code_of_boundary(tmp_path: Path) -> None:
    """The equivalence that makes the split safe, asserted on all three outcomes.

    This is the arm that would catch a renderer which computes its own rc
    instead of funnelling through `exit_code` — the single-conversion property
    `result.exit_code` exists to guarantee.
    """
    assert skill_lint.skill_lint_main(tmp_path) == exit_code(skill_lint.check_skill_lint(tmp_path))

    _skill(tmp_path, "good", _GOOD)
    assert skill_lint.skill_lint_main(tmp_path) == exit_code(skill_lint.check_skill_lint(tmp_path))

    _skill(tmp_path, "bad", _BAD)
    assert skill_lint.skill_lint_main(tmp_path) == exit_code(skill_lint.check_skill_lint(tmp_path))
