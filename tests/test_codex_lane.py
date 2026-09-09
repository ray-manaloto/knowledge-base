# Copyright (c) 2026 Raymond Manaloto
"""The `codex exec` deny, and the argv the task builds instead.

Half of this file pins the ALLOW set, for the reason `mise-tasks-only.md` states
about every guard here: the measured defects have all been false positives, not
evasion, and a guard that refuses the procedure it protects is worse than none.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from kb_setup import codex_lane, codex_run, hook_guard
from kb_setup.result import Ok, Rc

# ---------------------------------------------------------------------------
# DENY
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        'codex exec "do the thing"',
        'echo "prompt" | codex exec --sandbox read-only -',
        "codex exec --sandbox workspace-write -",
        "codex review",
        "codex exec review",
        # A transparent prefix must not launder it — `command_word` strips these.
        'env FOO=1 codex exec "x"',
        # Second segment of a chain is still a command position.
        'git status && codex exec "x"',
        # A VALUE-TAKING FLAG BEFORE THE SUBCOMMAND. This shape defeated the
        # first version of the guard LIVE: `--cd`'s value was read as the
        # subcommand and `exec` was never looked at, so the command reached the
        # real binary. 18 unit tests passed over that hole; driving the actual
        # CLI found it on the second probe.
        'codex --cd /tmp exec "x"',
        "codex --sandbox read-only exec -",
        'codex -C /some/dir review "x"',
        # THE SECOND HOLE: `app-server` sat in the introspection set and an
        # introspection token ANYWHERE exempted the whole segment, so pairing it
        # with a guarded subcommand sailed past. Found by enumerating codex's
        # real 28 subcommands, not by any test.
        'codex app-server exec "x"',
        # Widened set (#672 U1, Ray's CLI-only constraint): a resumed or forked
        # lane spends the subscription AND, without the hook-trust flag, runs
        # with this repo's guard stack silently off.
        "codex resume --last",
        'codex fork "x"',
        # `apply` is literally `git apply` onto the working tree, and nothing in
        # this repo or dotfiles guards destructive git.
        "codex apply",
        # `sandbox` runs arbitrary commands — a route around every Bash guard.
        "codex sandbox rm -rf /tmp/x",
    ],
)
def test_a_raw_codex_lane_is_denied(command: str) -> None:
    reason = codex_lane.decide(command)
    assert reason is not None, command
    assert "mise run kb-codex" in reason


def test_the_remedy_names_every_flag_a_lane_cannot_be_right_without() -> None:
    """The remedy is the whole point of the guard, so its content is asserted.

    Each of these was learned from a lane failing in a way that looked like the
    thing under test failing; a remedy that dropped one would send the reader
    back into the same hole.
    """
    reason = codex_lane.decide("codex exec -")
    assert reason is not None
    for flag in (
        "--add-dir",
        "sandbox_workspace_write.network_access",
        "--dangerously-bypass-hook-trust",
    ):
        assert flag in reason


# ---------------------------------------------------------------------------
# ALLOW — pinned, because a false positive is the only defect class these
# guards have actually produced.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "codex --version",
        "codex --help",
        "codex exec --help",
        "codex mcp list",
        "codex mcp login graphify",
        "codex logout",
        "codex doctor",
        "codex features",
        "codex agents",
        # `mcp` is the introspection subcommand and comes FIRST, so first-wins
        # keeps it allowed even though later tokens could look guarded.
        "codex mcp add somename",
        # The task itself shells out to codex.
        'mise run kb-codex -- "do the thing"',
        # A quoted mention can never sit at a command position — this is the
        # shape every confirmed false positive on this repo's guards has had.
        'git commit -m "stop running codex exec by hand"',
        'echo "codex exec is denied"',
        # Nothing to do with codex.
        "ls -la",
        "",
    ],
)
def test_introspection_and_mentions_are_never_denied(command: str) -> None:
    assert codex_lane.decide(command) is None, command


def test_an_unparsable_command_degrades_to_allow_not_deny() -> None:
    """A redirect guard is not a sandbox; failing closed here would brick calls."""
    assert codex_lane.decide('codex exec "unterminated') is None


# ---------------------------------------------------------------------------
# Wiring — the guard is only real if `hook_guard` actually calls it.
# ---------------------------------------------------------------------------


def _through_the_chain(command: str) -> str | None:
    """Drive the REAL guard chain, the way the hook does.

    Deliberately NOT `hook_guard.decide`, which is the graphify redirect's own
    decision function and never sees the other guards — calling it here would
    have made this test pass for a reason unrelated to the wiring, which is the
    exact class of self-agreeing check this repo keeps finding.
    """
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = hook_guard.check_hook_call(payload)
    assert isinstance(result, Ok), result
    return result.value


def test_the_guard_is_wired_into_hook_guard() -> None:
    """RED ARM target: deleting `_codex_lane` from the chain makes this fail.

    Deleting the CALL is the realistic break — renaming the definition would
    leave the original as a substring and prove nothing
    (`probes-need-a-control-arm.md` rule 2).
    """
    reason = _through_the_chain('codex exec "x"')
    assert reason is not None
    assert "mise run kb-codex" in reason


def test_hook_guard_still_allows_codex_introspection() -> None:
    assert _through_the_chain("codex mcp list") is None


# ---------------------------------------------------------------------------
# The argv the task builds — asserted without spawning codex.
# ---------------------------------------------------------------------------


def _argv(
    *,
    write: bool = False,
    network: bool = False,
    effort: str = "xhigh",
    sandbox_override: str | None = None,
) -> str:
    return " ".join(
        codex_run._codex_argv(
            codex_run.LaneSpec(
                write=write, network=network, effort=effort, sandbox_override=sandbox_override
            )
        )
    )


def test_a_read_only_lane_gets_no_add_dir() -> None:
    """`--add-dir` under read-only would read as granting something it does not."""
    argv = _argv()
    assert "--sandbox read-only" in argv
    assert "--add-dir" not in argv
    assert "network_access" not in argv


def test_a_write_lane_always_carries_the_uv_cache() -> None:
    """Without this the lane's uv gates exit rc 2, which looks like the gate failing."""
    argv = _argv(write=True)
    assert "--sandbox workspace-write" in argv
    assert "--add-dir" in argv
    assert "Caches" in argv


def test_network_is_off_unless_asked() -> None:
    assert "network_access" not in _argv(write=True)
    assert "sandbox_workspace_write.network_access=true" in _argv(write=True, network=True)


def test_hook_trust_bypass_is_on_every_lane() -> None:
    """Trust is keyed to each hook's HASH, so this is required every time, forever."""
    assert "--dangerously-bypass-hook-trust" in _argv()
    assert "--dangerously-bypass-hook-trust" in _argv(write=True)
    assert "--dangerously-bypass-hook-trust" in _argv(write=True, network=True)


def test_the_prompt_goes_on_stdin() -> None:
    """A large prompt as a positional hits ARG_MAX; the trailing `-` is the fix."""
    assert _argv().endswith(" -")


def test_ephemeral_is_never_passed() -> None:
    """A lane that persists nothing is invisible to `kb-session-search` afterwards."""
    assert "--ephemeral" not in _argv(write=True, network=True)


# ---------------------------------------------------------------------------
# Heredoc bodies are DATA, not command positions.
# ---------------------------------------------------------------------------


def test_a_heredoc_body_mentioning_a_guarded_subcommand_is_not_denied() -> None:
    """The false positive that blocked this very change from being committed.

    `git commit -F - <<'EOF' … codex resume --last … EOF` was DENIED while
    committing the commit that added `resume` to the guarded set. The `-m "…"`
    form is safe because the message is one quoted token; a heredoc body is not
    quoted, so every word in it arrived as a bare token at command position.

    Fixed in `check_first.strip_heredoc_bodies`, which both this guard and
    `absent_binary` inherit — they carried the same latent hole.
    """
    command = (
        "git commit -q -F - <<'EOF'\n"
        "fix: widen the guard\n"
        "\n"
        "  codex resume --last     spends the subscription\n"
        "  codex apply             writes to the tree\n"
        "  codex sandbox echo hi   routes around every guard\n"
        "EOF"
    )
    assert codex_lane.decide(command) is None


def test_a_real_lane_after_a_heredoc_is_still_denied() -> None:
    """Stripping the BODY must not blind the guard to what follows it.

    The opening line is kept and so is everything after the closing delimiter,
    so a genuine lane on the far side of a heredoc still reports.
    """
    command = "cat <<'EOF' > /tmp/p.md\nsome prompt text\nEOF\ncodex exec -"
    reason = codex_lane.decide(command)
    assert reason is not None
    assert "mise run kb-codex" in reason


def test_a_mise_task_elsewhere_does_not_exempt_a_raw_lane() -> None:
    """P1 from `codex review`, confirmed by running it before fixing.

    The exemption was a whole-string `if "mise run kb-" in command` evaluated
    BEFORE tokenising, so one mention anywhere waved the entire command through.
    Now judged per SEGMENT, like every other question in this guard.
    """
    reason = codex_lane.decide("mise run kb-query -- x; codex exec -")
    assert reason is not None
    assert "mise run kb-codex" in reason


def test_the_task_segment_itself_is_still_exempt() -> None:
    """The ALLOW half of the same fix: the task really does shell out to codex."""
    assert codex_lane.decide('mise run kb-codex -- "do the thing"') is None
    assert codex_lane.decide("mise run kb-query -- x && mise run kb-codex -- y") is None


@pytest.mark.parametrize("command", ["codex e -", 'codex a "x"', "codex cloud-tasks list"])
def test_the_short_aliases_are_guarded(command: str) -> None:
    """P1 from the METHOD-instructed `codex review`, confirmed in the source.

    `codex-rs/cli/src/main.rs:137` declares `visible_alias = "e"` for exec, `:188`
    `visible_alias = "a"` for apply, `:213` `alias = "cloud-tasks"`. A guard that
    matches only the long spelling of a command with a one-letter alias is
    decoration; the lane ran `codex e --help` and `codex a --help` and got rc 0
    from both while the guard allowed them.
    """
    assert codex_lane.decide(command) is not None, command


# ---------------------------------------------------------------------------
# `--review` argv — #678. NOTHING pinned this shape, which is how three flags
# were accepted and dropped for a whole release. Every assertion below fails on
# the pre-fix builder.
# ---------------------------------------------------------------------------


def _review(**spec: str | None) -> str:
    return " ".join(codex_run._review_argv(codex_run.ReviewSpec(base="origin/main", **spec)))


def test_review_forwards_the_model_as_review_model() -> None:
    """`codex review` has no `-m`; `-c review_model=` is the only channel.

    `ReviewArgs` (`sources/codex/codex-rs/exec/src/cli.rs:270-303`) declares no
    model flag, and `start_review_conversation` reads `config.review_model` first
    (`core/src/tasks/review.rs:123-127`).
    """
    argv = _review(model="gpt-6-astra")
    assert '-c review_model="gpt-6-astra"' in argv
    # The flag `codex review` would REJECT must never appear.
    assert "--model" not in argv


def test_review_forwards_the_reasoning_effort() -> None:
    """The whole point of the lane is xhigh; it ran at codex's default instead."""
    assert "-c model_reasoning_effort=xhigh" in _review(effort="xhigh")


def test_review_omits_both_keys_when_neither_is_asked_for() -> None:
    """The control arm: the probe above discriminates, rather than always passing."""
    argv = _review()
    assert "review_model" not in argv
    assert "model_reasoning_effort" not in argv
    assert argv == "codex review --base origin/main"


def test_review_never_grows_an_output_flag() -> None:
    """`codex review --help` lists no `-o`. `--output` is teed by us instead."""
    argv = _review(model="gpt-6-astra", effort="xhigh", instructions="METHOD: run it")
    assert " -o " not in f" {argv} "
    assert "--output-last-message" not in argv


def test_review_still_delivers_the_method_paragraph() -> None:
    """Regression guard: the channel that already worked must survive the fix."""
    argv = _review(model="gpt-6-astra", instructions='say "hi"')
    assert 'developer_instructions="say \\"hi\\""' in argv


def test_both_builders_spell_the_effort_key_the_same_way() -> None:
    """One key, two builders, one spelling — the drift this fix could have added."""
    exec_argv = " ".join(codex_run._codex_argv(codex_run.LaneSpec(effort="xhigh")))
    assert "-c model_reasoning_effort=xhigh" in exec_argv
    assert "-c model_reasoning_effort=xhigh" in _review(effort="xhigh")


def test_print_argv_pins_the_whole_review_shape(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """End-to-end through `run()`, which is where #678 was actually observed.

    Its "Suggested fix" asks for exactly this: a `--print-argv` test pinning
    review-mode argv, so the next flag added to `exec` cannot quietly skip
    `review` again.

    stdin is stubbed EMPTY rather than left alone: `_run_review` reads it
    whenever it is not a tty to pick up a piped METHOD paragraph, and under
    pytest's capture that read raises. An empty read is the honest stand-in for
    "no instructions were piped", and it keeps `developer_instructions` out of
    the argv this test is pinning.
    """
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    rc = codex_run.run(
        [
            "--review",
            "--base",
            "origin/main",
            "--model",
            "gpt-6-astra",
            "--effort",
            "xhigh",
            "--output",
            str(tmp_path / "does-not-matter.md"),
            "--print-argv",
        ]
    )
    assert rc == Rc.OK
    printed = capsys.readouterr().out.strip()
    assert printed == (
        "codex review --base origin/main "
        '-c review_model="gpt-6-astra" '
        "-c model_reasoning_effort=xhigh"
    )


# ---------------------------------------------------------------------------
# `_spawn` — the timeout bound and the review-mode tee.
# ---------------------------------------------------------------------------


def test_an_unbounded_spawn_returns_the_child_rc() -> None:
    """Default unchanged: no timeout, no new session, the lane's own code."""
    assert codex_run._spawn(["true"]) == 0
    assert codex_run._spawn(["false"]) == 1


def test_a_timeout_ends_the_lane_and_returns_124() -> None:
    """The bound must KILL, not wait the sleep out — the wall clock is the arm.

    `sleep 30` under a 0.3s bound: rc 124 proves the watchdog reported, and
    finishing in well under 30s proves it actually ended the process rather than
    letting it run and relabelling the result.
    """
    started = time.monotonic()
    rc = codex_run._spawn(["sleep", "30"], timeout=0.3)
    elapsed = time.monotonic() - started
    assert rc == 124
    assert elapsed < 10.0, f"the lane was not killed; it took {elapsed:.1f}s"


def test_a_lane_that_finishes_inside_its_bound_keeps_its_own_rc() -> None:
    """The other direction: a bound that does not fire changes nothing."""
    assert codex_run._spawn(["true"], timeout=30) == 0
    assert codex_run._spawn(["false"], timeout=30) == 1


def test_the_tee_writes_the_file_and_still_prints(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """#678's actual cost: rc 0, and no file where `--output` promised one."""
    target = tmp_path / "nested" / "review-abc-cold.md"
    rc = codex_run._spawn(["echo", "NO FINDINGS"], tee=target)
    assert rc == 0
    assert target.read_text(encoding="utf-8") == "NO FINDINGS\n"
    assert "NO FINDINGS" in capfd.readouterr().out


def test_the_tee_creates_a_missing_report_directory(tmp_path: Path) -> None:
    """`.agent/kb/review/reports/` is gitignored, so a fresh clone lacks it."""
    target = tmp_path / "a" / "b" / "c" / "report.md"
    assert codex_run._spawn(["echo", "hi"], tee=target) == 0
    assert target.exists()


def test_a_timed_out_tee_keeps_what_the_lane_had_already_written(tmp_path: Path) -> None:
    """A killed lane reviewed a SUBSET — its partial report must survive.

    This is the line-buffered flush earning its keep: a capture-then-write tee
    would leave an empty file exactly when the run was long enough to need one.
    """
    target = tmp_path / "partial.md"
    rc = codex_run._spawn(
        ["sh", "-c", "echo first-finding; sleep 30"],
        timeout=1.0,
        tee=target,
    )
    assert rc == 124
    assert "first-finding" in target.read_text(encoding="utf-8")


def test_spawn_refuses_to_write_stdin_and_drain_stdout_at_once(tmp_path: Path) -> None:
    """They never co-occur, and the deadlock if they did would be silent."""
    with pytest.raises(ValueError, match="stdin"):
        codex_run._spawn(["true"], prompt="hi", tee=tmp_path / "never-written.md")


def test_terminate_group_signals_a_child_that_shares_our_own_group() -> None:
    """The `own_group` arm, and the fact that this test returns IS the arm.

    The child below is spawned with no `start_new_session`, so it sits in this
    test runner's own process group. `_terminate_group` must therefore signal the
    child alone: if it took the `killpg` branch it would SIGTERM this process,
    pytest, and the mise task around it, and no assertion below would ever run.
    """
    proc = subprocess.Popen(["sleep", "30"], text=True)
    try:
        codex_run._terminate_group(proc, own_group=False)
        assert proc.wait(timeout=10) != 0  # died by signal, not by finishing
    finally:
        if proc.poll() is None:  # pragma: no cover — only on a failed arm
            proc.kill()


def test_review_mode_hands_output_and_timeout_to_the_spawn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#678 in one line: a flag is only honoured if it reaches what acts on it.

    `--output` cannot be an argv flag here (`codex review` has no `-o`), so the
    ONLY evidence it was honoured is that `_run_review` handed it to `_spawn` as
    the tee. Asserting the argv — the obvious test — would pass while the file
    was never written, which is exactly how the bug shipped.
    """
    seen: dict[str, object] = {}

    def _fake_spawn(
        argv: list[str],
        *,
        prompt: str | None = None,
        timeout: float | None = None,
        tee: Path | None = None,
    ) -> int:
        seen["argv"] = argv
        seen["timeout"] = timeout
        seen["tee"] = tee
        return 0

    monkeypatch.setattr(codex_run, "_spawn", _fake_spawn)
    monkeypatch.setattr(codex_run.shutil, "which", lambda _name: "/usr/bin/codex")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    report = tmp_path / "review-abc123456789-cold.md"
    rc = codex_run.run(["--review", "--output", str(report), "--timeout", "5400"])

    assert rc == 0
    assert seen["tee"] == report
    assert seen["timeout"] == 5400.0


def test_the_tee_flushes_each_line_while_the_lane_is_still_running(tmp_path: Path) -> None:
    """The per-line flush, armed against what it is actually FOR.

    A first version of this arm mutated the flush away and SURVIVED: closing the
    file at the end of `_tee` flushes the buffer regardless, so a report read
    after the lane exits looks identical either way. The property the flush buys
    is only observable WHILE the lane runs — a caller tailing a 40-minute Astra
    review sees nothing until 8KB has accumulated without it.

    So the assertion that the lane had not yet exited is not decoration; it is
    the control on this test. Without it the test would pass for the wrong
    reason, which is exactly how the first arm survived.
    """
    target = tmp_path / "live.md"
    finished = threading.Event()

    def _run_lane() -> None:
        codex_run._spawn(["sh", "-c", "echo early-finding; sleep 2"], tee=target)
        finished.set()

    worker = threading.Thread(target=_run_lane, daemon=True)
    worker.start()
    try:
        seen = ""
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and "early-finding" not in seen:
            if target.exists():
                seen = target.read_text(encoding="utf-8")
            time.sleep(0.02)
        assert not finished.is_set(), "the lane already exited; this proves nothing about flushing"
        assert "early-finding" in seen, "the report was still sitting in a buffer mid-run"
    finally:
        worker.join(timeout=15)


def test_review_forwards_the_sandbox_as_a_config_override() -> None:
    """The ONLY channel that sandboxes a review, and `do-not.md` #13 needs it.

    `codex review` has no `-s/--sandbox`, and a role file is refused one by
    design (`role.rs:80-89`). A CLI `-c` is a different layer and is not
    filtered — `SessionFlags` precedence 30 beats the user config's 20
    (`config_layer_source.rs:38-47`) — and the reviewer sub-agent inherits it
    because `start_review_conversation` clones the whole config
    (`review.rs:106`) without touching the sandbox.
    """
    argv = _review(sandbox="read-only")
    assert '-c sandbox_mode="read-only"' in argv
    # The flag `codex review` would REJECT must never appear.
    assert "--sandbox" not in argv


def test_review_omits_the_sandbox_key_when_not_asked() -> None:
    """Control arm: the probe above discriminates rather than always passing."""
    assert "sandbox_mode" not in _review()


def test_review_never_forwards_approval_policy() -> None:
    """It would be a flag that does nothing — the #678 defect, re-introduced.

    `start_review_conversation` hard-sets the sub-agent's approval policy to
    `Never` (`review.rs:121`), so any value we sent would be overwritten before
    the reviewer ran.
    """
    assert "approval_policy" not in _review(sandbox="read-only", model="gpt-6-astra")


# ---------------------------------------------------------------------------
# Round-1 cold-review fixes. Each of these fails on the pre-fix code.
# ---------------------------------------------------------------------------


def test_the_bound_holds_when_a_descendant_ignores_sigterm(tmp_path: Path) -> None:
    """P1: the watchdog must wait on the GROUP, not on codex alone.

    The leader exits on SIGTERM immediately; the descendant traps it and keeps
    stdout open. A leader-only check returned before ever sending SIGKILL, so the
    tee blocked on a pipe nothing would close and the "hard bound" was unbounded.
    """
    target = tmp_path / "out.md"
    started = time.monotonic()
    rc = codex_run._spawn(
        ["sh", "-c", "sh -c 'trap \"\" TERM; sleep 30' & exec sleep 0.2"],
        timeout=0.3,
        tee=target,
    )
    elapsed = time.monotonic() - started
    assert rc == 124
    # _KILL_GRACE is 5s, so a correct run ends by ~5.5s; the pre-fix code hung
    # until the descendant's own 30s sleep expired.
    assert elapsed < 15.0, f"the group outlived its bound; took {elapsed:.1f}s"


def test_the_tee_captures_stderr_where_codex_puts_its_progress(tmp_path: Path) -> None:
    """P2: agent messages go to stderr; stdout gets only the final message.

    `exec/src/event_processor_with_human_output.rs:99-105` uses `eprintln!` for
    every agent message and `:399-408` prints the final one to stdout at
    shutdown. A stdout-only tee wrote an empty file for the entire run.
    """
    target = tmp_path / "out.md"
    rc = codex_run._spawn(["sh", "-c", "echo progress-line >&2; echo final-line"], tee=target)
    assert rc == 0
    captured = target.read_text(encoding="utf-8")
    assert "progress-line" in captured, "stderr progress never reached the report"
    assert "final-line" in captured


def test_a_child_that_exits_before_reading_the_prompt_keeps_its_rc() -> None:
    """P2: a closed stdin is the CHILD's story, not a wrapper traceback.

    Writing a large prompt to an early-exiting child raised BrokenPipeError and
    replaced the child's exit code with rc 1.
    """
    big = "x" * (1024 * 1024)
    assert codex_run._spawn(["sh", "-c", "exit 7"], prompt=big) == 7


def test_a_timeout_during_a_blocked_stdin_write_still_reports_124() -> None:
    """P2, the same defect's worse half: the SUBSET warning was swallowed too."""
    big = "x" * (1024 * 1024)
    rc = codex_run._spawn(["sh", "-c", "exec sleep 30"], prompt=big, timeout=0.5)
    assert rc == 124


def test_an_unopenable_output_path_does_not_orphan_the_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2: `_tee` raising must not leave a child whose watchdog was cancelled.

    `/dev/null/x.md` cannot be created — `mkdir(parents=True)` over `/dev/null`
    raises `FileExistsError`, since it exists and is not a directory. The child
    is already running at that point, so the error path has to kill and reap it
    before the `finally` cancels the only thing that would have bounded it.

    The spy is the whole test. Asserting only that the OSError propagates would
    pass with the cleanup deleted — the same empty-arm shape that let A7 survive
    its first anchor. What must be true is that something terminated the child
    AND that it was reaped.
    """
    seen: dict[str, object] = {}
    real = codex_run._terminate_group

    def _spy(proc: subprocess.Popen[str], *, own_group: bool) -> None:
        seen["proc"] = proc
        real(proc, own_group=own_group)

    monkeypatch.setattr(codex_run, "_terminate_group", _spy)
    with pytest.raises(OSError, match="File exists"):
        codex_run._spawn(["sh", "-c", "exec sleep 30"], timeout=0.3, tee=Path("/dev/null/x.md"))

    child = seen.get("proc")
    assert child is not None, "the child was left running; nothing terminated it"
    assert isinstance(child, subprocess.Popen)
    assert child.returncode is not None, "the child was terminated but never reaped"


def test_the_bound_kills_the_group_on_a_non_tee_run(tmp_path: Path) -> None:
    """P1, round 2: the non-tee path returned before the group was cleaned up.

    Without a tee the main thread sits in `proc.wait()`, which returns the moment
    the LEADER dies — so the watchdog was still inside its grace period when
    `_spawn` returned, and a `returncode` guard then suppressed the SIGKILL it
    was about to send. Measured by the cold lane: rc 124 in 0.60s with a
    TERM-ignoring descendant still running past the five-second grace.

    TWO THINGS ABOUT THIS FIXTURE, both learned by getting them wrong:

    1. **The leader must OUTLIVE the bound**, or the watchdog never fires and the
       run simply succeeds. A first version slept 0.2s and asserted rc 124
       against a clean rc 0.
    2. **The descendant must ignore SIGTERM in the process that SLEEPS.**
       `sh -c 'trap "" TERM; sleep 30'` does not: `sh` ignores TERM but runs
       `sleep` as a child, and `killpg` reaches that child directly, which has
       default disposition and dies. Both round-2 arms SURVIVED against that
       fixture — it was never testing what its name claimed. A python child that
       installs `SIG_IGN` on itself before sleeping is TERM-proof for real, so
       only the SIGKILL at the end of the grace can end it.

    Asserting rc alone proves nothing: rc was already 124 while the leak was live.
    The assertion is on the descendant.
    """
    pidfile = tmp_path / "descendant.pid"
    inner = (
        "import os, signal, time;"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
        f"open({str(pidfile)!r}, 'w').write(str(os.getpid()));"
        "time.sleep(30)"
    )
    spawn_descendant = f"{shlex.quote(sys.executable)} -c {shlex.quote(inner)}"
    started = time.monotonic()
    rc = codex_run._spawn(["sh", "-c", f"{spawn_descendant} & exec sleep 30"], timeout=0.5)
    elapsed = time.monotonic() - started

    assert rc == 124
    pid = int(pidfile.read_text(encoding="utf-8").strip())
    # `_spawn` must not return until the watchdog has finished escalating, so by
    # here the group is killed. The short poll absorbs only the zombie window
    # before init reaps it; an unkilled descendant sleeps 30s and never clears.
    deadline = time.monotonic() + 3.0
    alive = True
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            alive = False
            break
        time.sleep(0.05)
    if alive:  # pragma: no cover — only on a failed arm
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
        pytest.fail(f"descendant {pid} survived the bound; _spawn returned after {elapsed:.2f}s")
