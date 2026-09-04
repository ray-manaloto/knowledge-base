# Copyright (c) 2026 Raymond Manaloto
"""`kb_setup.instruction_edit_guard` — #698.

WHAT IS ACTUALLY WORTH TESTING HERE. The guard has three exits and they are not
symmetric, so the tests are weighted the same way:

* **deny** — the one that costs a user something when it is wrong;
* **headroom** — must carry `additionalContext` and must NOT carry
  `permissionDecision`, because returning `"allow"` would additionally skip the
  user's permission prompt (`hooks.md:1743`);
* **silent** — no output at all. This is the exit that keeps the guard usable,
  and it is the one a careless implementation turns into a deny.

The fail-CLOSED direction gets its own cases because it inverts `hook_guard`'s
rule, and inverting a sibling's convention is exactly the kind of thing a reader
"corrects" back later.

Every case builds its own tree under `tmp_path` and runs a real `git init`, so
the sweep sees real tracked files rather than a stubbed `tracked_files`. That is
deliberate: the two holes #700 found were both in the WALK (an untracked path,
and a re-read import closure), and a stubbed walk cannot exhibit either.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import instruction_edit_guard as guard
from kb_setup import md_budget
from kb_setup.result import Rc

if TYPE_CHECKING:
    import pytest


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    """A real git repo with ``files`` committed, so `git ls-files` sees them."""
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    for args in (
        ["init", "-q"],
        ["add", "-A"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)
    return tmp_path


def _over_budget_rule(n: int = 400) -> str:
    return "\n".join(f"line {i}" for i in range(n)) + "\n"


# --- the silent exit ---------------------------------------------------------


def test_a_non_instruction_file_is_silent(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"README.md": "hi\n"})
    v = guard.evaluate(root, "Write", {"file_path": str(root / "README.md"), "content": "x" * 99})
    assert v.silent
    assert guard.render(v) is None


def test_a_path_outside_the_repo_is_silent(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    v = guard.evaluate(root, "Write", {"file_path": "/etc/CLAUDE.md", "content": "x"})
    assert v.silent


def test_an_unmodelled_tool_is_silent_not_denied(tmp_path: Path) -> None:
    """`Read` is not this guard's business; silence is the correct exit.

    A guard that denies everything it does not understand blocks routinely, and
    a guard that blocks routinely gets switched off.
    """
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    v = guard.evaluate(root, "Read", {"file_path": str(root / "CLAUDE.md")})
    assert v.silent


def test_a_missing_file_path_is_silent(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    assert guard.evaluate(root, "Write", {}).silent


# --- the deny exit -----------------------------------------------------------


def test_an_over_budget_write_is_denied(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    v = guard.evaluate(
        root,
        "Write",
        {"file_path": str(root / "CLAUDE.md"), "content": _over_budget_rule()},
    )
    assert v.deny
    assert "OVER its budget" in v.reason
    assert "CLAUDE.md" in v.reason


def test_an_over_budget_edit_is_denied(tmp_path: Path) -> None:
    """The Edit path must project old->new, not measure the file as it stands."""
    root = _repo(tmp_path, {"CLAUDE.md": "seed\n"})
    v = guard.evaluate(
        root,
        "Edit",
        {
            "file_path": str(root / "CLAUDE.md"),
            "old_string": "seed",
            "new_string": _over_budget_rule(),
        },
    )
    assert v.deny


def test_deny_renders_as_the_documented_shape(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    v = guard.evaluate(
        root,
        "Write",
        {"file_path": str(root / "CLAUDE.md"), "content": _over_budget_rule()},
    )
    out = json.loads(guard.render(v) or "{}")["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"]
    # `permissionDecisionReason` reaches Claude only on deny (hooks.md:1745),
    # so the message must be there and not in additionalContext.
    assert "additionalContext" not in out


# --- the headroom exit -------------------------------------------------------


def test_a_valid_edit_gets_headroom_and_no_permission_decision(tmp_path: Path) -> None:
    """Returning "allow" would skip the user's permission prompt. Omit it."""
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    v = guard.evaluate(
        root, "Write", {"file_path": str(root / "CLAUDE.md"), "content": "still small\n"}
    )
    assert not v.deny
    out = json.loads(guard.render(v) or "{}")["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in out
    assert "permissionDecisionReason" not in out
    assert "within budget" in out["additionalContext"]


# --- the two holes #700 found in the WALK ------------------------------------


def test_a_write_creating_a_new_rule_is_budgeted(tmp_path: Path) -> None:
    """Hole 1: an untracked, not-yet-existing path was invisible twice over.

    `check()` walked `git ls-files` and then skipped `not path.is_file()`, so the
    one edit that can add a WHOLE file to the eager budget was the one it could
    not see.
    """
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    new = root / ".claude" / "rules" / "brand-new.md"
    assert not new.exists()
    v = guard.evaluate(root, "Write", {"file_path": str(new), "content": _over_budget_rule()})
    assert v.deny, "a created instruction file must be budgeted before it exists"


def test_an_override_reaches_the_import_closure(tmp_path: Path) -> None:
    """Hole 2: `closure_size` re-reads every @import member from disk.

    Overriding only the top-level read left the closure counting stale bytes, so
    an edit to an imported member could pass while the closure it feeds went over.
    """
    root = _repo(
        tmp_path,
        {"CLAUDE.md": "@AGENTS.md\n", "AGENTS.md": "small\n"},
    )
    fat = md_budget.check(root, overrides={"AGENTS.md": _over_budget_rule()})
    lean = md_budget.check(root)
    assert not [v for v in lean.violations if v.path == "CLAUDE.md"]
    assert [v for v in fat.violations if v.path == "CLAUDE.md"], (
        "the override must reach the closure, not just the entry file"
    )


def test_an_override_for_a_tracked_path_is_not_counted_twice(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    plain = md_budget.check(root)
    with_override = md_budget.check(root, overrides={"CLAUDE.md": "hi there\n"})
    assert with_override.counted == plain.counted


def test_a_tracked_file_deleted_from_disk_is_still_skipped(tmp_path: Path) -> None:
    """`Overlay.exists` must not widen the walk when nothing overrides the path.

    This replaced a weaker test that compared `check(root)` with
    `check(root, overrides={})`. Those take literally the same branch
    (`overrides or {}`), so it could not fail — and `kb-arms` proved it: the arm
    aimed at it went red on OTHER tests and was reported `PROBE BROKEN - red
    suite did not name the test`, which is exactly the check that catches an arm
    measuring something its id does not name.

    What the no-override path can actually get wrong is `exists()`: it replaced a
    bare `path.is_file()`, so a tracked-but-deleted file must still be skipped
    rather than read.
    """
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n", ".claude/rules/gone.md": "x\n"})
    (root / ".claude" / "rules" / "gone.md").unlink()

    report = md_budget.check(root)
    assert not [v for v in report.violations if v.path == ".claude/rules/gone.md"]
    assert report.counted == 1, "only the surviving CLAUDE.md should be counted"


# --- fail CLOSED, which inverts hook_guard's convention ----------------------


def test_an_unprojectable_edit_on_a_matched_file_is_denied(tmp_path: Path) -> None:
    """`old_string` absent from the file: size unknown, so refuse.

    `hook_guard` fails OPEN because a crashed guard must not brick every Bash
    call. That reasoning does not carry here — the blast radius is one file, and
    passing an unmeasured edit defeats the whole policy.
    """
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    v = guard.evaluate(
        root,
        "Edit",
        {
            "file_path": str(root / "CLAUDE.md"),
            "old_string": "NOT PRESENT ANYWHERE",
            "new_string": "x",
        },
    )
    assert v.deny
    assert "could not be projected" in v.reason


def test_a_matched_file_with_a_non_string_payload_is_denied(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    v = guard.evaluate(root, "Write", {"file_path": str(root / "CLAUDE.md")})
    assert v.deny


def test_project_returns_none_rather_than_the_current_content(tmp_path: Path) -> None:
    """`None` means "cannot model", never "no change".

    Collapsing the two would report a clean budget for an edit nobody measured.
    """
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    assert guard.project("NotebookEdit", {}, root / "CLAUDE.md") is None


# --- projection details ------------------------------------------------------


def test_replace_all_false_replaces_only_the_first(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"CLAUDE.md": "a\na\n"})
    got = guard.project(
        "Edit",
        {"old_string": "a", "new_string": "b"},
        root / "CLAUDE.md",
    )
    assert got == "b\na\n"


def test_replace_all_true_replaces_every_occurrence(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"CLAUDE.md": "a\na\n"})
    got = guard.project(
        "Edit",
        {"old_string": "a", "new_string": "b", "replace_all": True},
        root / "CLAUDE.md",
    )
    assert got == "b\nb\n"


# --- the CLI seam ------------------------------------------------------------


def test_main_prints_the_deny_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path, {"CLAUDE.md": "hi\n"})
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(root / "CLAUDE.md"),
                "content": _over_budget_rule(),
            },
        }
    )
    assert guard.main(root, payload) == Rc.OK
    out = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"


def test_main_prints_nothing_when_silent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path, {"README.md": "hi\n"})
    payload = json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": str(root / "README.md"), "content": "x"}}
    )
    assert guard.main(root, payload) == Rc.OK
    assert capsys.readouterr().out == ""


def test_main_survives_unparsable_stdin(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """No file_path means no matched candidate, so this is silent, not a deny."""
    assert guard.main(tmp_path, "{not json") == Rc.OK
    assert capsys.readouterr().out == ""


def test_main_survives_empty_stdin(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert guard.main(tmp_path, "") == Rc.OK
    assert capsys.readouterr().out == ""
