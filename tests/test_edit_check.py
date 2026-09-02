# Copyright (c) 2026 Raymond Manaloto
"""The codex PostToolUse ty hook.

The contract this pins is codex's, not ours, and each assertion here stands for
a way the hook could silently do nothing while looking wired:

* `apply_patch` sends `tool_input.command`, **not** a file path — an earlier
  plan for this hook assumed `tool_input.file_path` and would have found no
  files, forever, with no error.
* *"Plain text on `stdout` is ignored"* — a hook that prints diagnostics
  achieves nothing. The payload has to be JSON carrying
  `hookSpecificOutput.additionalContext`.
* It must never block. `PostToolUse` accepts `decision: "block"` and
  `continue: false`; both are wrong after an edit that already happened.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import edit_check

_PATCH = """*** Begin Patch
*** Update File: {path}
@@
-old
+new
*** End Patch
"""


def _payload(command: str) -> str:
    return json.dumps({"tool_name": "apply_patch", "tool_input": {"command": command}})


def _run(monkeypatch: pytest.MonkeyPatch, raw: str, root: Path) -> int:
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(raw))
    return edit_check.run(root)


def test_finds_python_paths_in_an_apply_patch_envelope(tmp_path: Path) -> None:
    """The four directives are read from codex's own source, not from memory."""
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.pyi").write_text("x: int\n")
    (tmp_path / "notes.md").write_text("hi\n")
    command = (
        "*** Begin Patch\n"
        "*** Update File: a.py\n"
        "*** Add File: b.pyi\n"
        "*** Update File: notes.md\n"
        "*** Delete File: gone.py\n"
        "*** End Patch\n"
    )

    found = [p.name for p in edit_check._patched_python_files(command, tmp_path)]

    assert found == ["a.py", "b.pyi"]


def test_move_to_names_the_destination(tmp_path: Path) -> None:
    """`Move to:` is the path that now needs checking; the source may be gone."""
    (tmp_path / "new.py").write_text("x = 1\n")
    command = "*** Begin Patch\n*** Update File: old.py\n*** Move to: new.py\n*** End Patch\n"

    found = [p.name for p in edit_check._patched_python_files(command, tmp_path)]

    assert found == ["new.py"]


def test_silent_when_the_patch_touches_no_python(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """This runs after EVERY apply_patch, so a markdown edit must cost nothing."""
    rc = _run(monkeypatch, _payload(_PATCH.format(path="README.md")), tmp_path)

    assert rc == 0
    assert capsys.readouterr().out == ""


def test_silent_when_ty_is_clean(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(edit_check, "_run_ty", lambda *_: None)
    monkeypatch.setattr(Path, "is_file", lambda *_: True)

    rc = _run(monkeypatch, _payload(_PATCH.format(path="a.py")), tmp_path)

    assert rc == 0
    assert capsys.readouterr().out == ""


def test_emits_json_not_plain_text_when_ty_complains(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Codex ignores plain stdout — the diagnostics must arrive as JSON."""
    (tmp_path / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(edit_check, "_run_ty", lambda *_: "error[invalid-argument-type]: boom")
    monkeypatch.setattr(Path, "is_file", lambda *_: True)

    rc = _run(monkeypatch, _payload(_PATCH.format(path="a.py")), tmp_path)

    assert rc == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "boom" in emitted["hookSpecificOutput"]["additionalContext"]


def test_never_blocks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The edit already happened; a type error is information, not a halt.

    Pinned rather than assumed, because `decision: "block"` and
    `continue: false` are both accepted by codex for this event — so the hook
    could acquire blocking behaviour by a one-word edit and nothing else here
    would notice.
    """
    (tmp_path / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(edit_check, "_run_ty", lambda *_: "error: boom")
    monkeypatch.setattr(Path, "is_file", lambda *_: True)

    rc = _run(monkeypatch, _payload(_PATCH.format(path="a.py")), tmp_path)

    assert rc == 0
    emitted = json.loads(capsys.readouterr().out)
    assert "decision" not in emitted
    assert "continue" not in emitted


def test_output_is_capped_below_the_spill_threshold(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Above ~2,500 tokens codex spills to a temp file and shows a preview."""
    (tmp_path / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(edit_check, "_run_ty", lambda *_: "e" * 50_000)
    monkeypatch.setattr(Path, "is_file", lambda *_: True)

    _run(monkeypatch, _payload(_PATCH.format(path="a.py")), tmp_path)

    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert len(context) < 8000
    assert "truncated" in context


@pytest.mark.parametrize(
    "raw",
    ["not json at all", "[]", '{"tool_input": null}', '{"tool_input": {"command": 7}}'],
)
def test_fails_open_on_any_malformed_payload(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path, raw: str
) -> None:
    """A failure inside this hook must never cost the lane its turn."""
    assert _run(monkeypatch, raw, tmp_path) == 0
    assert capsys.readouterr().out == ""
