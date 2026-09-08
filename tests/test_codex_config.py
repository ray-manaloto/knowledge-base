# Copyright (c) 2026 Raymond Manaloto
"""Tests for the `.codex/config.toml` session tripwire (#710).

The exit code is deliberately useless as an arm here — `main` always returns
`Rc.OK` so a session is never blocked over a config rewrite — so every arm below
asserts on the VERDICT and on the emitted event, which is where the finding
actually lives.

`capsys` rather than `caplog` because `events.warn` renders to **stderr** and
that rendered line is what a session-start hook actually shows the reader;
probed both ways before writing (each catches it).
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from kb_setup import codex_config
from kb_setup.codex_config import Report, Verdict
from kb_setup.result import Rc

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    import pytest


def _proc(returncode: int, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"], returncode=returncode, stdout=stdout, stderr=""
    )


def _runner(
    responses: dict[str, subprocess.CompletedProcess[str]] | None = None, *, raises: bool = False
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """A fake `subprocess.run` keyed on the git subcommand.

    Keyed on `args[1]` (`ls-files` / `diff` / `show`) so a test states only the
    arms it cares about and everything else defaults to success. Injectable
    precisely so all three verdicts are reachable without a real repository.
    """

    def run(args: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if raises:
            raise OSError("git not found")
        return (responses or {}).get(args[1], _proc(0))

    return run


def _drain(capsys: pytest.CaptureFixture[str]) -> str:
    """Read stdout+stderr ONCE — `readouterr` clears the buffer on every call."""
    captured = capsys.readouterr()
    return captured.out + captured.err


def _write_watched(root: Path, text: str) -> None:
    (root / codex_config.WATCHED).parent.mkdir(parents=True, exist_ok=True)
    (root / codex_config.WATCHED).write_text(text, encoding="utf-8")


# --- verdicts -------------------------------------------------------------


def test_clean_when_worktree_matches_head(tmp_path: Path) -> None:
    """`git diff --quiet` exiting 0 is the only silent outcome."""
    report = codex_config.status(tmp_path, run=_runner({"diff": _proc(0)}))
    assert report.verdict is Verdict.CLEAN


def test_changed_when_diff_reports_a_difference(tmp_path: Path) -> None:
    """Rc 1 from `git diff --quiet` is the defect signature.

    The line counts reproduce the real 2026-09-06 shape: 144 committed, 30 left.
    """
    _write_watched(tmp_path, "x\n" * 30)
    run = _runner({"diff": _proc(1), "show": _proc(0, "x\n" * 144)})
    report = codex_config.status(tmp_path, run=run)
    assert report.verdict is Verdict.CHANGED
    assert report.committed_lines == 144
    assert report.worktree_lines == 30


def test_deleted_file_counts_as_zero_lines(tmp_path: Path) -> None:
    """The 2026-09-04 occurrence removed content outright; absence is not a crash."""
    run = _runner({"diff": _proc(1), "show": _proc(0, "x\n" * 144)})
    report = codex_config.status(tmp_path, run=run)
    assert report.verdict is Verdict.CHANGED
    assert report.worktree_lines == 0


def test_untracked_file_is_unknown_not_clean(tmp_path: Path) -> None:
    """No committed copy means the question cannot be answered — never CLEAN."""
    report = codex_config.status(tmp_path, run=_runner({"ls-files": _proc(1)}))
    assert report.verdict is Verdict.UNKNOWN
    assert "not tracked" in report.detail


def test_git_missing_is_unknown(tmp_path: Path) -> None:
    """A git that will not start is 'we did not look', not 'nothing found'."""
    assert codex_config.status(tmp_path, run=_runner(raises=True)).verdict is Verdict.UNKNOWN


def test_unexpected_diff_rc_is_unknown(tmp_path: Path) -> None:
    """`git diff --quiet` documents 0 and 1; anything else is git failing.

    Reporting rc 128 as CHANGED would invent a finding, and as CLEAN would hide
    one — so it is the third state.
    """
    report = codex_config.status(tmp_path, run=_runner({"diff": _proc(128)}))
    assert report.verdict is Verdict.UNKNOWN
    assert "128" in report.detail


# --- the recovery command -------------------------------------------------


def test_recovery_command_is_the_stash_form() -> None:
    """A plain `git restore` is denied by `destructive_git` on a dirty tree.

    The stash form preserves the evidence AND restores the good file in one
    step, which is why it is the command printed. The `git restore` assertion is
    the load-bearing half: printing a denied command would be worse than
    printing none.
    """
    cmd = codex_config.recovery_command()
    assert cmd.startswith("git stash push -m ")
    assert "EVIDENCE #710" in cmd
    assert str(codex_config.WATCHED) in cmd
    assert "git restore" not in cmd


# --- rendering ------------------------------------------------------------


def test_clean_emits_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    """The silent arm — a clean session start must print nothing at all."""
    codex_config.render(Report(Verdict.CLEAN, "matches the committed copy"))
    assert _drain(capsys) == ""


def test_changed_names_the_recovery_command(capsys: pytest.CaptureFixture[str]) -> None:
    """The CHANGED arm must carry the command, not merely the fact.

    This is the difference between a report the reader can act on and one they
    have to re-derive — the recovery has been the same command three times.
    """
    codex_config.render(Report(Verdict.CHANGED, "differs from the committed copy", 144, 30))
    out = _drain(capsys)
    assert "git stash push" in out
    assert "144" in out
    assert "30" in out
    assert "#710" in out


def test_unknown_says_it_is_not_a_pass(capsys: pytest.CaptureFixture[str]) -> None:
    """'Could not check' must never render as green."""
    codex_config.render(Report(Verdict.UNKNOWN, "git could not be run at all"))
    assert "NOT a pass" in _drain(capsys)


# --- CLI entry ------------------------------------------------------------


def test_main_reports_ok_even_when_the_tripwire_fires(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A session is never blocked over this — the finding lives in the output.

    `main` builds its own runner, so this drives the real `git` against an empty
    `tmp_path`: not a repository, hence UNKNOWN. What is being pinned is that a
    non-CLEAN verdict still exits 0 while SAYING something.
    """
    assert codex_config.main(tmp_path, []) == Rc.OK
    assert _drain(capsys) != ""


def test_main_rejects_unknown_arguments(tmp_path: Path) -> None:
    """A malformed request is a real error, unlike a finding."""
    assert codex_config.main(tmp_path, ["--nope"]) == Rc.BAD_REQUEST
