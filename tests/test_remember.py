# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.remember` — the work-memory writer and its lesson gate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kb_setup.remember import (
    check_memory_lessons,
    check_remember,
    render_audit,
)
from kb_setup.result import Err, Ok, Rc, external_from_returncode

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _memory(path: Path, name: str, *, outcome: str, correction: str | None = None) -> Path:
    """Write a memory file in the shape `graphify save-result` produces."""
    lines = ["---", 'type: "query"', f'question: "Q {name}"', f'outcome: "{outcome}"']
    if correction is not None:
        lines.append(f'correction: "{correction}"')
    lines += ["---", "", f"# Q: Q {name}", "", "## Answer", "", "body text"]
    target = path / f"{name}.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


# --- the gate this module exists for ------------------------------------------


def test_corrected_without_a_correction_is_refused() -> None:
    """The defect that motivated the module: 21 of 32 corrections had no lesson."""
    result = check_remember(["--question", "Q", "--outcome", "corrected"])
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert "--correction" in result.message


def test_corrected_with_a_whitespace_correction_is_refused() -> None:
    """A blank string renders exactly as an absent one — so it is refused too."""
    result = check_remember(["--question", "Q", "--outcome", "corrected", "--correction", "   "])
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST


def test_corrected_with_a_correction_is_accepted() -> None:
    """CONTROL ARM: the same request with a lesson must pass, or the gate is a wall."""
    result = check_remember(
        ["--question", "Q", "--outcome", "corrected", "--correction", "the real answer"]
    )
    assert isinstance(result, Ok)
    assert result.value.correction == "the real answer"


def test_correction_file_is_read(tmp_path: Path) -> None:
    """`--correction-file` is how a multi-line lesson is passed at all."""
    lesson = tmp_path / "lesson.md"
    lesson.write_text("line one\nline two", encoding="utf-8")
    result = check_remember(
        ["--question", "Q", "--outcome", "corrected", "--correction-file", str(lesson)]
    )
    assert isinstance(result, Ok)
    assert result.value.correction == "line one\nline two"


def test_useful_needs_no_correction() -> None:
    """Only `corrected` obliges a lesson; a useful answer's lesson IS its answer."""
    result = check_remember(["--question", "Q", "--outcome", "useful", "--answer", "A"])
    assert isinstance(result, Ok)


# --- ordinary request validation ----------------------------------------------


def test_missing_question_is_bad_request() -> None:
    result = check_remember(["--answer", "A"])
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST


def test_unknown_outcome_is_bad_request() -> None:
    result = check_remember(["--question", "Q", "--outcome", "nope"])
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST


def test_both_correction_forms_is_bad_request(tmp_path: Path) -> None:
    lesson = tmp_path / "lesson.md"
    lesson.write_text("x", encoding="utf-8")
    result = check_remember(
        [
            "--question",
            "Q",
            "--outcome",
            "corrected",
            "--correction",
            "inline",
            "--correction-file",
            str(lesson),
        ]
    )
    assert isinstance(result, Err)
    assert "not both" in result.message


def test_missing_correction_file_is_bad_request(tmp_path: Path) -> None:
    result = check_remember(
        [
            "--question",
            "Q",
            "--outcome",
            "corrected",
            "--correction-file",
            str(tmp_path / "absent.md"),
        ]
    )
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST


def test_argv_is_a_list_so_no_shell_runs() -> None:
    """Backticks in a lesson must be recorded, not executed (this has happened)."""
    result = check_remember(
        ["--question", "Q", "--outcome", "corrected", "--correction", "use `ls` here"]
    )
    assert isinstance(result, Ok)
    argv = result.value.argv("graphify")
    assert isinstance(argv, list)
    assert "use `ls` here" in argv


def test_memory_dir_passes_through(tmp_path: Path) -> None:
    """The write path must be exercisable without writing to the corpus."""
    scratch = str(tmp_path / "scratch")
    result = check_remember(["--question", "Q", "--memory-dir", scratch])
    assert isinstance(result, Ok)
    argv = result.value.argv("graphify")
    assert argv[argv.index("--memory-dir") + 1] == scratch


def test_remember_boundary_prints_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    """Recipe rule 3 — a boundary that prints cannot be re-rendered by a sink."""
    check_remember(["--question", "Q", "--outcome", "corrected"])
    check_remember(["--question", "Q", "--outcome", "useful"])
    assert capsys.readouterr().out == ""


# --- the audit ----------------------------------------------------------------


def test_audit_finds_a_correction_with_no_lesson(tmp_path: Path) -> None:
    _memory(tmp_path, "lossy", outcome="corrected")
    _memory(tmp_path, "intact", outcome="corrected", correction="the replacement belief")
    result = check_memory_lessons(tmp_path)
    assert isinstance(result, Ok)
    assert result.rc is Rc.FINDINGS
    assert result.value.corrected == 2
    assert result.value.intact == 1
    assert [m.path.name for m in result.value.lossy] == ["lossy.md"]


def test_audit_is_ok_when_every_correction_states_its_lesson(tmp_path: Path) -> None:
    """CONTROL ARM for the audit: it must be able to report clean."""
    _memory(tmp_path, "intact", outcome="corrected", correction="the replacement belief")
    _memory(tmp_path, "useful", outcome="useful")
    result = check_memory_lessons(tmp_path)
    assert isinstance(result, Ok)
    assert result.rc is Rc.OK
    assert result.value.lossy == []


def test_audit_of_an_empty_dir_is_not_run(tmp_path: Path) -> None:
    """A walk that matched nothing never asked the question — NOT_RUN, not OK."""
    result = check_memory_lessons(tmp_path)
    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN


def test_audit_of_an_absent_dir_is_not_run(tmp_path: Path) -> None:
    result = check_memory_lessons(tmp_path / "nope")
    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN


def test_audit_boundary_prints_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _memory(tmp_path, "lossy", outcome="corrected")
    check_memory_lessons(tmp_path)
    assert capsys.readouterr().out == ""


def test_render_audit_names_the_lossy_file(tmp_path: Path) -> None:
    _memory(tmp_path, "lossy", outcome="corrected")
    result = check_memory_lessons(tmp_path)
    assert isinstance(result, Ok)
    rendered = render_audit(result.value)
    assert "lossy.md" in rendered
    assert "WITHOUT" in rendered


# --- the signal conversion this module is the first user of --------------------


def test_signal_returncode_becomes_128_plus_n() -> None:
    """SIGKILL (-9) must report 137, the POSIX shell convention — never 9, never 247."""
    assert external_from_returncode(-9).code == 137
    assert external_from_returncode(-15).code == 143


def test_ordinary_returncode_passes_through() -> None:
    assert external_from_returncode(0).code == 0
    assert external_from_returncode(2).code == 2


def test_signal_note_is_stated() -> None:
    """An unexplained non-zero rc is the defect R9 names."""
    assert "signal 9" in external_from_returncode(-9).message
