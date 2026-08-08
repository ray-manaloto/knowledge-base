# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.session_reflect`.

Every rule gets BOTH arms — a command that must trip it and one that must not.
A detector verified only on the tripping case is decoration: the first draft of
`piped-rc` matched every `| head` and fired 111 times in one session, and only a
must-NOT-fire case makes that visible as a defect rather than as thoroughness.
"""

from __future__ import annotations

import json
import time
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
    """CONTROL ARM: patching a doc with no test run is not a mutation arm.

    Also the arm on the `also` split: the rule's own pattern now matches a bare
    `write_text`, so if `scan` stopped consulting `Rule.also` this case would
    start firing while every must-FIRE case stayed green.
    """
    path = _transcript(tmp_path, 'uv run python -c "p.write_text(body)"')
    report = sr.reflect(tmp_path, transcripts=[path])
    assert "mutation-harness" not in _ids(report.owned)


def test_running_a_test_without_patching_anything_is_not_a_harness(tmp_path) -> None:
    """CONTROL ARM on the other half: a plain test run is not a mutation arm."""
    path = _transcript(tmp_path, "uv run python -c \"subprocess.run(['pytest'])\"")
    assert "mutation-harness" not in _ids(sr.reflect(tmp_path, transcripts=[path]).owned)


def test_many_patches_and_no_test_run_finish_promptly(tmp_path) -> None:
    """The spanning `A.*?B` form was QUADRATIC, and this is its shape.

    Under DOTALL the lazy gap was re-expanded to end-of-string from every
    `write_text` start, so a command with many patch tokens and no run token —
    the worst case, and an ordinary one — cost O(k·n). Measured on the old
    pattern: 5.98 ms at k=200 rising to 395 ms at k=1600, an 8x input for a 66x
    cost. The split form is two linear searches: 0.049 ms to 0.270 ms.

    Timed rather than merely correct, because correctness never regressed —
    only the cost did, and a cost regression in an ADVISORY report is invisible
    until it stalls a session's last command.

    UNARMED, deliberately and with the measurement to say so. Restoring the
    spanning pattern leaves this test GREEN, because `scan` consults `also`
    first and this command fails it — 398 ms executing that pattern directly
    against these bytes, 0.28 ms through `scan`. No single-line mutation makes
    this go red: the fix is the short-circuit, and its arm is
    `also-not-consulted`. Naming that here rather than shipping a
    predicted-survivor arm, which is the shape that gets read as confirmation.
    """
    command = "; ".join(f"p{n}.write_text(chunk_{n})" for n in range(1600))
    start = time.perf_counter()
    report = sr.reflect(tmp_path, transcripts=[_transcript(tmp_path, command)])
    elapsed = time.perf_counter() - start
    assert "mutation-harness" not in _ids(report.owned)
    # Two orders of magnitude of headroom over the measured 0.27 ms, and still
    # ~10x under the 395 ms the old pattern spent — a bound loose enough not to
    # flake on a loaded machine and tight enough that the old form fails it.
    assert elapsed < 0.05, f"took {elapsed * 1000:.1f} ms — the spanning form is back"


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


def test_an_rc_captured_after_the_pipe_is_still_a_violation(tmp_path) -> None:
    """The FALSE NEGATIVE, and it hid the exact mistake the directive names.

    In `mise run lint | tail; echo "rc=$?"` that `$?` is TAIL's status, not the
    gate's — so the command reports success for a failed gate while LOOKING
    compliant. The old gap and lookahead both ran past the `;`, found `rc=`,
    and suppressed the rule (cold lane, 2026-08-08).
    """
    path = _transcript(tmp_path, 'mise run lint | tail; echo "rc=$?"')
    assert "piped-rc" in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_pipestatus_reads_the_gates_own_status_and_is_exempt(tmp_path) -> None:
    """CONTROL ARM: the one piped form that does NOT lose the gate's rc."""
    path = _transcript(tmp_path, "mise run lint | tail -5; echo ${PIPESTATUS[0]}")
    assert "piped-rc" not in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_the_wrong_pipestatus_index_is_not_an_exemption(tmp_path) -> None:
    r"""Index 1 is TAIL's status — the very thing the directive is about.

    A bare `\bPIPESTATUS\b` exemption excused it, which is the same
    whole-command over-reach as the `rc=$?` exemption it replaced, reintroduced
    one commit later (cold lane, round 1).
    """
    path = _transcript(tmp_path, "mise run lint | tail -5; echo ${PIPESTATUS[1]}")
    assert "piped-rc" in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_merely_mentioning_pipestatus_is_not_an_exemption(tmp_path) -> None:
    """The word in prose bought a full exemption for a real violation."""
    path = _transcript(tmp_path, 'mise run lint | tail -5; echo "see PIPESTATUS docs"')
    assert "piped-rc" in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_the_pipestatus_exemption_requires_an_actual_expansion(tmp_path) -> None:
    """Without the `$` sigil nothing is read; the text is just text.

    Third too-wide exemption on this one rule — `rc=$?`, bare `PIPESTATUS`, then
    an unsigiled `PIPESTATUS[0]`. `unless` is searched against the WHOLE command,
    so it must name a form that occurs only when the thing is really happening.
    """
    path = _transcript(tmp_path, 'mise run lint | tail; echo "read PIPESTATUS[0] first"')
    assert "piped-rc" in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_a_gate_inside_a_conditional_is_still_a_lost_rc(tmp_path) -> None:
    """`if mise run test | head; then` — the WORST case, not an edge one.

    The exit code is not merely discarded, it is what the conditional branches
    on. A command-position anchor of `^` or `[;&|]` alone never saw it.
    """
    path = _transcript(tmp_path, "if mise run test | head; then echo ok; fi")
    assert "piped-rc" in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_the_composite_check_task_is_a_gate_too(tmp_path) -> None:
    """`mise run check` is `depends = ["lint", "test"]` — two gates, one rc.

    A hand-maintained task list fails by OMISSION, and this one had one on
    arrival: piping the composite gate discarded both exit codes and tripped
    nothing.
    """
    path = _transcript(tmp_path, "mise run check | tail -20")
    assert "piped-rc" in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_grepping_for_the_word_pytest_is_not_a_lost_gate(tmp_path) -> None:
    r"""FALSE POSITIVE: `\bpytest\b` matched the word ANYWHERE in the command.

    `rg pytest /tmp/log | head` searches a log FOR a string. Its exit code is
    not evidence of anything, so calling it a discarded gate reports the
    directive as violated where the directive does not apply.
    """
    path = _transcript(tmp_path, "rg pytest /tmp/log | head")
    assert "piped-rc" not in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_piping_a_read_only_task_into_head_is_a_browse(tmp_path) -> None:
    """CONTROL ARM on narrowing `mise run` to the GATE tasks.

    Most tasks here are reads. Piping `kb-query` into `head` bounds a display,
    it does not discard a result anyone would act on.
    """
    path = _transcript(tmp_path, 'mise run kb-query -- "how does X work" | head -20')
    assert "piped-rc" not in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_a_gate_redirecting_stderr_before_the_pipe_still_fires(tmp_path) -> None:
    """`2>&1` is the commonest thing between a gate and its pipe.

    Refusing `&` outright to keep the scan inside one simple command would have
    stopped the CANONICAL violation from matching at all, so `_SEG` allows a
    single `&` and blocks only `&&`.
    """
    path = _transcript(tmp_path, "mise run test 2>&1 | tail -40")
    assert "piped-rc" in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_a_relative_cd_is_a_violation(tmp_path) -> None:
    path = _transcript(tmp_path, "cd sources/mise")
    assert "relative-cd" in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_a_shell_expanded_absolute_cd_is_not_a_violation(tmp_path) -> None:
    """CONTROL ARM: `~`, `$HOME` and `$(…)` all expand to ABSOLUTE paths.

    The rule checked for a literal leading `/`, so all three were reported as
    relative — inflating the rate with commands that were already compliant.
    What the directive is about is a target relative to a cwd that persists
    across Bash calls, and none of these is one.
    """
    for command in (
        "cd ~",
        'cd "$HOME/repo"',
        "cd ${HOME}/repo",
        "cd $(git rev-parse --show-toplevel)",
    ):
        path = _transcript(tmp_path, command, name=f"s{abs(hash(command))}")
        found = _ids(sr.reflect(tmp_path, transcripts=[path]).violations)
        assert "relative-cd" not in found, command


def test_a_bare_variable_target_is_still_flagged(tmp_path) -> None:
    """The first fix exempted `$` WHOLESALE, and went too far the other way.

    `REL=sources/x; cd $REL` is the rule's exact hazard — a target relative to a
    cwd that persists across Bash calls — and a blanket `$` excused it (cold
    lane, round 1). The exemption names the provably-absolute forms instead.

    This knowingly costs a false positive on a variable holding an absolute
    path: a variable's contents cannot be read from the command, so "could not
    be shown absolute" is the honest reading, and this rule reports a rate of
    candidates rather than a verdict on each.
    """
    path = _transcript(tmp_path, "REL=sources/mise; cd $REL")
    assert "relative-cd" in _ids(sr.reflect(tmp_path, transcripts=[path]).violations)


def test_quoting_decides_what_expands_so_a_quote_is_not_skippable(tmp_path) -> None:
    """`cd "~/repo"` and `cd '$HOME/repo'` are RELATIVE, and were excused.

    A leading quote was treated as decoration to be skipped over. It is not:
    `~` expands only UNQUOTED, and `$…` expands unquoted or in double quotes but
    never in single. Both commands here name directories literally called `~`
    and `$HOME` beneath the cwd — the rule's own hazard, wearing a quote.
    """
    for command in ('cd "~/repo"', "cd '$HOME/repo'"):
        path = _transcript(tmp_path, command, name=f"q{abs(hash(command))}")
        found = _ids(sr.reflect(tmp_path, transcripts=[path]).violations)
        assert "relative-cd" in found, command


# --- counting greps are a RATE, not a row each -------------------------------


def test_two_counts_in_one_command_count_as_armed(tmp_path) -> None:
    path = _transcript(tmp_path, "grep -c real f; grep -c KNOWN_PRESENT f")
    report = sr.reflect(tmp_path, transcripts=[path])
    assert report.counts == 1
    assert report.counts_armed == 1


def test_a_lone_count_is_unarmed(tmp_path) -> None:
    report = sr.reflect(tmp_path, transcripts=[_transcript(tmp_path, "grep -c missing f")])
    assert (report.counts, report.counts_armed) == (1, 0)


def test_two_counts_over_different_corpora_do_not_arm_each_other(tmp_path) -> None:
    """The defect: OCCURRENCES were counted, never relatedness.

    `grep -c missing a; grep -c unrelated b` asks two independent questions and
    answers neither. Crediting it as one control-armed probe reports two
    unvalidated negatives as one validated one — the precise failure the
    "probes that could not have answered" section exists to name.
    """
    path = _transcript(tmp_path, "grep -c missing a; grep -c unrelated b")
    report = sr.reflect(tmp_path, transcripts=[path])
    assert (report.counts, report.counts_armed) == (1, 0)


def test_a_shared_target_among_several_counts_is_armed(tmp_path) -> None:
    """CONTROL ARM: relatedness, not a bare pair, is what the rule now needs."""
    path = _transcript(tmp_path, "grep -c a f; grep -c b g; grep -c c f")
    report = sr.reflect(tmp_path, transcripts=[path])
    assert (report.counts, report.counts_armed) == (1, 1)


def test_quoted_targets_are_compared_as_whole_arguments(tmp_path) -> None:
    """A quoted path is ONE argument, and `str.split` did not know that.

    `grep -c missing "a corpus"; grep -c known "b corpus"` left both targets as
    the trailing token `corpus"`, so two probes over different corpora matched —
    the exact false ARMED this function was written to remove, reproduced by its
    own tokenizer (cold lane, round 1).
    """
    path = _transcript(tmp_path, 'grep -c missing "a corpus"; grep -c known "b corpus"')
    report = sr.reflect(tmp_path, transcripts=[path])
    assert (report.counts, report.counts_armed) == (1, 0)


def test_a_genuinely_shared_quoted_target_is_still_armed(tmp_path) -> None:
    """CONTROL ARM: quote-awareness must not stop real pairs from matching."""
    path = _transcript(tmp_path, 'grep -c a "one file"; grep -c b "one file"')
    report = sr.reflect(tmp_path, transcripts=[path])
    assert (report.counts, report.counts_armed) == (1, 1)


def test_counts_redirected_to_separate_files_are_still_armed(tmp_path) -> None:
    """A redirect names a STREAM, never the corpus — and this one punished care.

    `grep -c missing corpus > /tmp/miss; grep -c known corpus > /tmp/control`
    compared `/tmp/miss` against `/tmp/control` and called a genuinely armed
    pair UNARMED. Redirecting each count to its own file is what a careful probe
    DOES, so the rule was penalising the habit it exists to encourage.
    """
    path = _transcript(
        tmp_path, "grep -c missing corpus > /tmp/miss; grep -c known corpus > /tmp/control"
    )
    report = sr.reflect(tmp_path, transcripts=[path])
    assert (report.counts, report.counts_armed) == (1, 1)


def test_a_redirect_does_not_make_unrelated_counts_look_armed(tmp_path) -> None:
    """CONTROL ARM: stripping redirects must not collapse different corpora."""
    path = _transcript(tmp_path, "grep -c missing a > /tmp/x; grep -c known b > /tmp/y")
    report = sr.reflect(tmp_path, transcripts=[path])
    assert (report.counts, report.counts_armed) == (1, 0)


def test_an_unbalanced_quote_falls_back_rather_than_raising(tmp_path) -> None:
    """A transcript fragment can carry one, and `shlex` raises on it.

    Losing the whole command to a ValueError would be a worse answer than an
    approximate target, in a module that never gates anything.
    """
    path = _transcript(tmp_path, 'grep -c a "unbalanced; grep -c b f')
    assert sr.reflect(tmp_path, transcripts=[path]).counts == 1


# --- the graph-first ratio ----------------------------------------------------


def test_a_grep_carrying_a_path_counts_as_a_source_read() -> None:
    """A Grep record has `path`, never `file_path`.

    The chain read `file_path` then fell through to `pattern` — asking whether
    the SEARCH TERM looked like a filename. Every targeted grep of a module went
    uncounted, understating the half of the ratio meant to be uncomfortable.
    """
    assert sr._reads_source({"pattern": "needle", "path": "python/src/kb_setup/cli.py"})


def test_a_grep_over_prose_is_not_a_source_read() -> None:
    """CONTROL ARM: adding `path` must not make every Grep a source read."""
    assert not sr._reads_source({"pattern": "needle", "path": "docs/x.md"})


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
