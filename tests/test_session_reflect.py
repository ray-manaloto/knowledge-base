# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.session_reflect`.

Every rule gets BOTH arms — a command that must trip it and one that must not.
A detector verified only on the tripping case is decoration: the first draft of
`piped-rc` matched every `| head` and fired 111 times in one session, and only a
must-NOT-fire case makes that visible as a defect rather than as thoroughness.
"""

from __future__ import annotations

import json
from pathlib import Path

from kb_setup import session_reflect as sr


def _transcript(tmp_path: Path, *commands: str, name: str = "sess") -> Path:
    """A minimal transcript carrying `commands` as Bash tool calls."""
    lines = [
        json.dumps(
            {
                "message": {
                    "content": [{"type": "tool_use", "name": "Bash", "input": {"command": c}}]
                }
            }
        )
        for c in commands
    ]
    path = tmp_path / f"{name}.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _ids(findings: list[sr.Finding]) -> set[str]:
    return {f.rule.id for f in findings}


# --- the OWNED table: work a task already does -------------------------------


def test_a_hand_written_mutation_harness_is_reported(tmp_path) -> None:
    path = _transcript(
        tmp_path,
        "uv run python -c \"p.read_text(); p.write_text(x); subprocess.run(['pytest'])\"",
    )
    report = sr.reflect(tmp_path, transcripts=[path])
    assert "mutation-harness" in _ids(report.owned)


def test_the_harness_finding_names_kb_arms(tmp_path) -> None:
    """A finding that names no remedy is a complaint, not a lead."""
    path = _transcript(tmp_path, "uv run python -c \"p.write_text(y); subprocess.run(['pytest'])\"")
    report = sr.reflect(tmp_path, transcripts=[path])
    assert any("kb-arms" in f.rule.remedy for f in report.owned)


def test_an_ordinary_file_edit_is_not_a_harness(tmp_path) -> None:
    """CONTROL ARM: patching a doc with no test run is not a mutation arm."""
    path = _transcript(tmp_path, 'uv run python -c "p.write_text(body)"')
    report = sr.reflect(tmp_path, transcripts=[path])
    assert "mutation-harness" not in _ids(report.owned)


# --- DIRECTIVES: compliance is a rate ----------------------------------------


def test_a_bare_interpreter_is_a_violation(tmp_path) -> None:
    path = _transcript(tmp_path, 'python3 -c "print(1)"')
    assert "bare-interpreter" in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_uv_run_python_is_not_a_violation(tmp_path) -> None:
    """CONTROL ARM: the compliant form must not be counted against the rate."""
    path = _transcript(tmp_path, 'uv run python -c "print(1)"')
    assert "bare-interpreter" not in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_a_gate_piped_to_tail_loses_its_rc(tmp_path) -> None:
    path = _transcript(tmp_path, "mise run lint 2>&1 | tail -40")
    assert "piped-rc" in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_a_display_pipe_over_a_log_is_not_a_violation(tmp_path) -> None:
    """CONTROL ARM, and the reason this rule was rewritten.

    The first draft matched any `| head`, so every display pipe over a /tmp log
    tripped it — 111 firings in one session. A rule at that volume trains the
    reader to skip the section that holds the real finding.
    """
    path = _transcript(tmp_path, "grep -n foo /tmp/out.log | head -5")
    assert "piped-rc" not in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_a_gate_that_records_its_rc_is_not_flagged(tmp_path) -> None:
    """CONTROL ARM: the remedy this rule argues for must itself pass."""
    path = _transcript(tmp_path, 'mise run lint > /tmp/l.log 2>&1; echo "rc=$?" | tail -1')
    assert "piped-rc" not in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


# --- counting greps are a RATE, not a row each -------------------------------


def test_two_counts_in_one_command_count_as_armed(tmp_path) -> None:
    path = _transcript(tmp_path, "grep -c real f; grep -c KNOWN_PRESENT f")
    report = sr.reflect(tmp_path, transcripts=[path])
    assert report.counts == 1
    assert report.counts_armed == 1


def test_a_lone_count_is_unarmed(tmp_path) -> None:
    report = sr.reflect(tmp_path, transcripts=[_transcript(tmp_path, "grep -c missing f")])
    assert (report.counts, report.counts_armed) == (1, 0)


# --- wrapper candidates -------------------------------------------------------


def test_adjacent_mise_tasks_are_a_wrapper_candidate(tmp_path) -> None:
    path = _transcript(tmp_path, "mise run lint", "mise run test")
    runs = sr.reflect(tmp_path, transcripts=[path]).runs
    assert any(run == ("lint", "test") for _, run in runs)


def test_tasks_separated_by_other_work_are_not_a_run(tmp_path) -> None:
    """CONTROL ARM: adjacency is the whole claim.

    Two calls with work between them are two decisions, not one sequence.
    """
    path = _transcript(tmp_path, "mise run lint", "git status", "mise run test")
    assert sr.reflect(tmp_path, transcripts=[path]).runs == []


# --- the self-reference exclusion --------------------------------------------


def test_a_command_editing_this_module_is_skipped(tmp_path) -> None:
    """A rule table contains every pattern by construction, so it matches itself.

    Measured on the first real run: `bounded-search` fired on the `sed` that
    wrote the `bounded-search` rule, reporting the author as the offender.
    """
    path = _transcript(tmp_path, "sed -i '' 's/x/y/' python/src/kb_setup/session_reflect.py")
    report = sr.reflect(tmp_path, transcripts=[path])
    assert report.commands == 0


def test_the_exclusion_does_not_swallow_unrelated_commands(tmp_path) -> None:
    """CONTROL ARM: only self-referential commands are skipped."""
    path = _transcript(tmp_path, "sed -i '' 's/x/y/' python/src/kb_setup/distill.py")
    assert sr.reflect(tmp_path, transcripts=[path]).commands == 1


# --- reporting ---------------------------------------------------------------


def test_a_truncated_section_says_what_it_withheld() -> None:
    """A silent cap reads as "that was everything".

    Which is how a bounded report becomes a wrong one.
    """
    rendered = sr._capped([f"- row {n}" for n in range(25)])
    assert any("15 more not shown" in line for line in rendered)


def test_a_short_section_gets_no_withheld_line() -> None:
    """CONTROL ARM: the notice must not appear when nothing was dropped."""
    assert all("not shown" not in line for line in sr._capped(["- only row"]))


def test_an_empty_report_renders_every_section_as_empty(tmp_path) -> None:
    """An empty section is the common, correct result and must SAY so."""
    rendered = sr.render(sr.reflect(tmp_path, transcripts=[_transcript(tmp_path, "git status")]))
    assert "none observed" in rendered
    assert "nothing — every step went through its task" in rendered


def test_reflect_main_always_exits_zero(tmp_path, capsys) -> None:
    """It reports; it never gates.

    A gate here would block a commit over "you could have used a task", which is
    a cure worse than the disease.
    """
    assert sr.reflect_main(tmp_path) == 0
    assert "session-reflect:" in capsys.readouterr().out


def test_quiet_prints_one_line_not_the_report(tmp_path, capsys) -> None:
    """The SessionEnd hook declares `--quiet`.

    A flag nothing implements is a broken hook, so this pins that it exists and
    is actually terse.
    """
    assert sr.reflect_main(tmp_path, ["--quiet"]) == 0
    out = capsys.readouterr().out
    assert len(out.strip().splitlines()) == 1
    assert "finding(s)" in out


def test_without_quiet_the_full_report_prints(tmp_path, capsys) -> None:
    """CONTROL ARM: the flag must actually change something."""
    assert sr.reflect_main(tmp_path) == 0
    assert "## Hand-rolled work" in capsys.readouterr().out
