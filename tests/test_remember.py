# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.remember` — the work-memory writer and its lesson gate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kb_setup.remember import (
    check_memory_lessons,
    check_mode,
    check_remember,
    main,
    render_audit,
    wants_audit,
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
    result = check_remember(["--question", "Q", "--answer", "A", "--outcome", "corrected"])
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert "--correction" in result.message


def test_corrected_with_a_whitespace_correction_is_refused() -> None:
    """A blank string renders exactly as an absent one — so it is refused too."""
    result = check_remember(
        ["--question", "Q", "--answer", "A", "--outcome", "corrected", "--correction", "   "]
    )
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST


def test_corrected_with_a_correction_is_accepted() -> None:
    """CONTROL ARM: the same request with a lesson must pass, or the gate is a wall."""
    result = check_remember(
        [
            "--question",
            "Q",
            "--answer",
            "A",
            "--outcome",
            "corrected",
            "--correction",
            "the real answer",
        ]
    )
    assert isinstance(result, Ok)
    assert result.value.correction == "the real answer"


def test_correction_file_is_read(tmp_path: Path) -> None:
    """`--correction-file` is how a multi-line lesson is passed at all."""
    lesson = tmp_path / "lesson.md"
    lesson.write_text("line one\nline two", encoding="utf-8")
    result = check_remember(
        [
            "--question",
            "Q",
            "--answer",
            "A",
            "--outcome",
            "corrected",
            "--correction-file",
            str(lesson),
        ]
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
        [
            "--question",
            "Q",
            "--answer",
            "A",
            "--outcome",
            "corrected",
            "--correction",
            "use `ls` here",
        ]
    )
    assert isinstance(result, Ok)
    argv = result.value.argv("graphify")
    assert isinstance(argv, list)
    assert "use `ls` here" in argv


def test_memory_dir_passes_through(tmp_path: Path) -> None:
    """The write path must be exercisable without writing to the corpus."""
    scratch = str(tmp_path / "scratch")
    result = check_remember(["--question", "Q", "--answer", "A", "--memory-dir", scratch])
    assert isinstance(result, Ok)
    argv = result.value.argv("graphify")
    assert argv[argv.index("--memory-dir") + 1] == scratch


def test_remember_boundary_prints_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    """Recipe rule 3 — a boundary that prints cannot be re-rendered by a sink."""
    check_remember(["--question", "Q", "--outcome", "corrected"])
    check_remember(["--question", "Q", "--outcome", "useful"])
    assert capsys.readouterr().out == ""


def test_answer_is_required() -> None:
    """An answer is required, matching what `save-result` itself demands.

    This gate did not require one, so a request valid HERE died downstream in a
    raw argparse dump from graphify with our own message never printed. Found by
    the CONTROL ARM of the cold lane's finding, not by the finding.
    """
    result = check_remember(["--question", "Q"])
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert "--answer" in result.message


def test_blank_answer_is_refused() -> None:
    result = check_remember(["--question", "Q", "--answer", "   "])
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST


# --- mode dispatch: --audit must not swallow a record request -------------------


def test_audit_combined_with_a_record_request_is_refused() -> None:
    """The cold lane's finding: `if "--audit" in args` is a membership test.

    A typo or scripted call carrying both flags had its RECORD REQUEST silently
    discarded — the audit printed, the rc was the audit's, and nothing was
    written or warned about. Reproduced live before this fix.
    """
    bad = check_mode(["--question", "Q", "--answer", "A", "--outcome", "corrected", "--audit"])
    assert bad is not None
    assert bad.rc is Rc.BAD_REQUEST
    assert "--question" in bad.message


def test_audit_alone_is_allowed() -> None:
    """CONTROL ARM: the refusal must not make `--audit` itself unusable."""
    assert check_mode(["--audit"]) is None


def test_a_record_request_alone_is_allowed() -> None:
    """CONTROL ARM, the other direction."""
    assert check_mode(["--question", "Q", "--answer", "A"]) is None


def test_every_record_flag_triggers_the_refusal(tmp_path: Path) -> None:
    """One flag was enough to find the bug; the class is what must be closed.

    BOTH argv spellings, and that is the point. Round 2 of the review found that
    the first fix matched flag STRINGS, so `--question=Q --audit` — argparse's
    own `=`-joined syntax — bypassed it entirely and the record was discarded
    exactly as before. This test previously used only the two-token form, which
    is precisely why it could not see it.
    """
    somewhere = str(tmp_path / "x.md")
    for flag, value in (
        ("--question", "Q"),
        ("--answer", "A"),
        ("--answer-file", somewhere),
        ("--outcome", "useful"),
        ("--correction", "C"),
        ("--correction-file", somewhere),
    ):
        assert check_mode([flag, value, "--audit"]) is not None, f"space form: {flag}"
        assert check_mode([f"{flag}={value}", "--audit"]) is not None, f"= form: {flag}"


def test_the_equals_joined_form_is_refused_through_main(tmp_path: Path) -> None:
    """Round 2's finding, end to end.

    Verified live before the fix: `--question=Q … --audit` exited 1 (the audit's
    code) having written nothing, with no error — the round-1 bug reachable
    through a different spelling of the same request.
    """
    lesson = tmp_path / "lesson.md"
    lesson.write_text("a lesson that must not vanish", encoding="utf-8")
    memories = tmp_path / "mem"
    memories.mkdir()
    rc = main(
        tmp_path,
        [
            "--question=Q",
            "--answer=A",
            "--outcome=corrected",
            f"--correction-file={lesson}",
            f"--memory-dir={memories}",
            "--audit",
        ],
    )
    assert rc == Rc.BAD_REQUEST
    assert list(memories.iterdir()) == [], "the =-joined record request was dropped"


def test_wants_audit_parses_rather_than_matches() -> None:
    """The structural fix: mode comes from the PARSED request, not from tokens."""
    assert wants_audit(["--audit"]) is True
    assert wants_audit(["--question", "Q"]) is False
    # CONTROL: the flag text appearing as a VALUE is not the flag. Written in the
    # `=` form on purpose — `["--question", "--audit"]` makes argparse treat
    # `--audit` as the next flag, leaving `--question` without a value, and
    # argparse then calls sys.exit rather than returning (see the module
    # docstring's note on that divergence).
    assert wants_audit(["--question=--audit"]) is False


def test_main_refuses_the_mixed_request_and_writes_nothing(tmp_path: Path) -> None:
    """Through `main`, which is where the loss actually happened.

    Every pre-existing test called `check_remember`/`check_memory_lessons`
    directly, so none of them could ever have seen a dispatch defect.
    """
    lesson = tmp_path / "lesson.md"
    lesson.write_text("a lesson that must not be lost", encoding="utf-8")
    memories = tmp_path / "mem"
    memories.mkdir()
    rc = main(
        tmp_path,
        [
            "--question",
            "Q",
            "--answer",
            "A",
            "--outcome",
            "corrected",
            "--correction-file",
            str(lesson),
            "--memory-dir",
            str(memories),
            "--audit",
        ],
    )
    assert rc == Rc.BAD_REQUEST
    assert list(memories.iterdir()) == [], "the record request was silently dropped"


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
