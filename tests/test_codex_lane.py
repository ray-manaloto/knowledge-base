# Copyright (c) 2026 Raymond Manaloto
"""The `codex exec` deny, and the argv the task builds instead.

Half of this file pins the ALLOW set, for the reason `mise-tasks-only.md` states
about every guard here: the measured defects have all been false positives, not
evasion, and a guard that refuses the procedure it protects is worse than none.
"""

from __future__ import annotations

import json

import pytest
from kb_setup import codex_lane, codex_run, hook_guard
from kb_setup.result import Ok

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
            write=write, network=network, effort=effort, sandbox_override=sandbox_override
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
