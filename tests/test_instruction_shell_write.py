# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.instruction_shell_write` (#711).

🔴 WHAT THESE CANNOT SEE, said first because it is the more important half.
These tests exercise the DECISION FUNCTION. They cannot tell whether
`.claude/settings.json` routes a Bash call into it, and on the sibling change
(#698) that was the actual defect: 55 green unit tests beside a hook that fired
on nothing, because an `Edit(<glob>)` `if` rule does not match a `Write` call.
The live arm for this guard is run by hand and recorded in the arms spec — a
real `cat > .claude/rules/…` attempted and refused. A green file here says the
suite can go red; it says nothing about the settings file beside it.

The repository fixture is real (`git init` + real files) rather than stubbed,
because `evaluate` resolves paths against a root and asks `md_budget.classify`,
and a stub of either would be a test of my reading rather than of the guard.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from kb_setup import instruction_shell_write as guard


def _repo(tmp_path: Path) -> Path:
    """A real git repo with one file of each budgeted shape."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "CLAUDE.md").write_text("# root\n")
    (tmp_path / "AGENTS.md").write_text("# agents\n")
    (tmp_path / "README.md").write_text("# readme\n")
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "a.md").write_text("# rule\n")
    (tmp_path / ".claude" / "skills" / "s").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "s" / "SKILL.md").write_text("# skill\n")
    return tmp_path


# --- the deny direction ------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "cat > .claude/rules/a.md",
        "cat >> CLAUDE.md",
        "echo hi > .claude/skills/s/SKILL.md",
        "tee .claude/rules/a.md < big.md",
        "tee -a AGENTS.md",
        "sed -i '' 's/a/b/' CLAUDE.md",
        "perl -pi -e 's/a/b/' .claude/rules/a.md",
        "sed --in-place 's/a/b/' CLAUDE.md",
    ],
)
def test_a_shell_write_to_an_instruction_file_is_denied(tmp_path: Path, command: str) -> None:
    assert guard.evaluate(_repo(tmp_path), command).deny


def test_a_python_c_that_writes_is_denied(tmp_path: Path) -> None:
    command = "uv run python -c \"open('CLAUDE.md','w').write(x)\""
    assert guard.evaluate(_repo(tmp_path), command).deny


def test_a_bare_python3_c_that_writes_is_denied(tmp_path: Path) -> None:
    command = "python3 -c \"from pathlib import Path; Path('AGENTS.md').write_text(x)\""
    assert guard.evaluate(_repo(tmp_path), command).deny


def test_the_reason_names_the_file_it_would_write(tmp_path: Path) -> None:
    verdict = guard.evaluate(_repo(tmp_path), "cat > .claude/rules/a.md")
    assert ".claude/rules/a.md" in verdict.reason


def test_the_reason_points_at_the_edit_tool_not_at_a_size(tmp_path: Path) -> None:
    """The remedy is a SURFACE change, so it must not read as a budget failure."""
    verdict = guard.evaluate(_repo(tmp_path), "cat > CLAUDE.md")
    assert "Edit or Write tool" in verdict.reason
    assert "deny by SHAPE" in verdict.reason


def test_the_reason_states_what_it_cannot_see(tmp_path: Path) -> None:
    """A guard that does not declare its blind spots lets silence imply coverage."""
    verdict = guard.evaluate(_repo(tmp_path), "cat > CLAUDE.md")
    assert "SCOPE" in verdict.reason
    assert "-exec sed -i" in verdict.reason


# --- the allow direction, which is what keeps the guard usable ---------------


@pytest.mark.parametrize(
    "command",
    [
        "cat README.md",
        "cat > README.md",
        "cat > docs/artifacts/x.html",
        "cat > /tmp/x.md",
        "sed -n '1,5p' CLAUDE.md",
        "grep -n foo CLAUDE.md",
        "uv run ruff check .",
        "mise run lint",
        "uv run pytest -k run",
        # Discriminates the forward-scan regression: a naive unwrap that hunts
        # for the first python-ish token promotes `-k`'s ARGUMENT into the
        # command position. `check_first._segment_is_a_gate` shipped exactly
        # that defect once (round-2 finding 2).
        "uv run pytest -k python",
        "git diff -- CLAUDE.md",
    ],
)
def test_an_ordinary_command_is_silent(tmp_path: Path, command: str) -> None:
    assert not guard.evaluate(_repo(tmp_path), command).deny


def test_a_python_c_that_only_reads_is_silent(tmp_path: Path) -> None:
    """A read is not a write, so both conditions must hold.

    Denying a read would be the false-positive direction every measured defect
    in this guard family has come from.
    """
    command = "uv run python -c \"print(open('CLAUDE.md').read())\""
    assert not guard.evaluate(_repo(tmp_path), command).deny


def test_a_quoted_mention_is_not_a_redirect(tmp_path: Path) -> None:
    """A `>` inside a quoted string is one token, never a redirect.

    The tokeniser is what makes this pass; a regex denied exactly this shape in
    both of `check_first`'s confirmed false positives.
    """
    command = "git commit -m 'wrote a note > CLAUDE.md today'"
    assert not guard.evaluate(_repo(tmp_path), command).deny


def test_a_read_redirect_is_not_a_write(tmp_path: Path) -> None:
    assert not guard.evaluate(_repo(tmp_path), "wc -l < CLAUDE.md").deny


def test_a_path_outside_the_repo_is_silent(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    other = tmp_path_factory.mktemp("other")
    assert not guard.evaluate(_repo(tmp_path), f"cat > {other}/CLAUDE.md").deny


# --- failure modes -----------------------------------------------------------


def test_an_unparsable_command_fails_open(tmp_path: Path) -> None:
    """Fail OPEN, on `hook_guard`'s convention and the opposite of #698's.

    A guard that denied every command a tokeniser trips on would brick the Bash
    tool, and an unparsable command is overwhelmingly an ordinary one.
    """
    assert guard.written_paths("cat > 'unterminated") == []
    assert not guard.evaluate(_repo(tmp_path), "cat > 'unterminated").deny


def test_written_paths_needs_no_repository() -> None:
    """Shape detection and classification are separate on purpose."""
    assert guard.written_paths("cat > anything.md") == ["anything.md"]


# --- the rendered hook response ----------------------------------------------


def test_a_deny_renders_a_permission_decision(tmp_path: Path) -> None:
    out = guard.render(guard.evaluate(_repo(tmp_path), "cat > CLAUDE.md"))
    assert out is not None
    body = json.loads(out)["hookSpecificOutput"]
    assert body["permissionDecision"] == "deny"
    assert body["hookEventName"] == "PreToolUse"


def test_an_allow_renders_nothing_at_all(tmp_path: Path) -> None:
    """Nothing at all — deliberately not `allow`.

    Returning `allow` would ALSO skip the user's permission prompt, a regression
    that looks like success in every other assertion.
    """
    assert guard.render(guard.evaluate(_repo(tmp_path), "cat README.md")) is None


# --- the stdin entry point ---------------------------------------------------


def test_main_denies_on_a_real_payload(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    payload = json.dumps({"tool_input": {"command": "cat > CLAUDE.md"}})
    assert guard.main(_repo(tmp_path), payload) == 0
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "payload",
    ["not json at all", "[]", "{}", '{"tool_input": {}}', '{"tool_input": {"command": ""}}'],
)
def test_main_is_silent_and_zero_on_anything_unexpected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], payload: str
) -> None:
    """Always rc 0, whatever arrives on stdin.

    A hook exiting non-zero on its own confusion is a much larger failure than
    the one this guard prevents.
    """
    assert guard.main(_repo(tmp_path), payload) == 0
    assert capsys.readouterr().out == ""


# --- cold-review regressions on d3437a7059e1 ---------------------------------
#
# Every one of these was a finding the lane REPRODUCED by running the module,
# not by reading it. They are kept as named tests rather than folded into the
# parametrized lists above so a future failure says which defect came back.


@pytest.mark.parametrize(
    "command",
    ["grep '>' CLAUDE.md", 'echo ">" CLAUDE.md', "awk '>' CLAUDE.md"],
)
def test_a_quoted_redirect_character_is_not_a_redirect(tmp_path: Path, command: str) -> None:
    """P1: posix shlex strips quotes, so `'>'` and `>` are the same token.

    Reading redirects off token VALUES therefore denied an ordinary `grep`.
    `check_first.tokenise_marked` re-lexes with quoting preserved so the two can
    be told apart.
    """
    assert not guard.evaluate(_repo(tmp_path), command).deny


@pytest.mark.parametrize("op", ["&>", "&>>", ">|"])
def test_the_other_writing_redirects_are_denied(tmp_path: Path, op: str) -> None:
    """P1: `&>`, `&>>` and `>|` are real writes and were reaching disk."""
    assert guard.evaluate(_repo(tmp_path), f"cat {op} CLAUDE.md").deny


def test_a_cd_before_the_write_is_followed(tmp_path: Path) -> None:
    """P1: one token was the whole bypass — `cd` into the directory first."""
    assert guard.evaluate(_repo(tmp_path), "cd .claude/rules && cat > a.md").deny


def test_a_cd_out_of_the_repo_is_followed_too(tmp_path: Path) -> None:
    """CONTROL ARM for the test above, and the inverse defect it also fixed.

    Without this, the cd-tracking is satisfied by an implementation that treats
    every relative path as repo-rooted — which is the ORIGINAL bug, and it
    wrongly denied a write that lands outside the repository entirely.
    """
    assert not guard.evaluate(_repo(tmp_path), "cd /tmp && cat > CLAUDE.md").deny


def test_a_sed_script_file_is_not_a_write_target(tmp_path: Path) -> None:
    """P2: `-f` names the SCRIPT, which sed READS."""
    assert not guard.evaluate(_repo(tmp_path), "sed -i -f CLAUDE.md target.txt").deny


def test_gnu_in_place_with_a_suffix_is_recognised(tmp_path: Path) -> None:
    """P2: `--in-place=.bak` is one token, so an equality check missed it."""
    assert guard.evaluate(_repo(tmp_path), "sed --in-place=.bak 's/a/b/' CLAUDE.md").deny


def test_a_python_c_that_merely_mentions_a_write_method_is_silent(tmp_path: Path) -> None:
    """P2: the write pattern matched prose. Every alternative now needs a paren."""
    command = "python -c \"print('write_text CLAUDE.md')\""
    assert not guard.evaluate(_repo(tmp_path), command).deny


def test_a_home_relative_path_is_not_this_repos_business(tmp_path: Path) -> None:
    """A `~`-rooted path is $HOME, not this repository.

    Found while fixing P1b: `root / "~/CLAUDE.md"` lands INSIDE the root and
    classifies as a nested entry point, so the guard denied a write to the
    user's own config — which `do-not.md` #11 puts outside this repo's remit.
    """
    assert not guard.evaluate(_repo(tmp_path), "cat > ~/CLAUDE.md").deny


def test_main_ignores_a_payload_from_another_tool(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """P2: the matcher is `Bash`, but the module must not depend on that alone.

    🔴 THE FIRST VERSION OF THIS TEST ASSERTED ONLY `main(...) == 0` AND COULD
    NOT FAIL — `main` returns 0 unconditionally, by design, because a hook that
    exits non-zero on its own confusion breaks every Bash call. Arm F8 caught it:
    disabling the tool check killed no test. The observable that actually
    distinguishes the two behaviours is whether anything is PRINTED.
    """
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"command": "cat > CLAUDE.md"}})
    assert guard.main(_repo(tmp_path), payload) == 0
    assert capsys.readouterr().out == ""


def test_main_still_denies_when_the_tool_name_is_bash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTROL ARM for the tool-name check above.

    Without it, that test is satisfied by a guard that ignores every payload.
    """
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "cat > CLAUDE.md"}})
    assert guard.main(_repo(tmp_path), payload) == 0
    assert "deny" in capsys.readouterr().out
