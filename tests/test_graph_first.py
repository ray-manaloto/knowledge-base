# Copyright (c) 2026 Raymond Manaloto
"""The graph-first guard denies a BROAD source search before any graph query (#253).

Control-armed BOTH directions, and the ALLOW arm is the one that matters here:
every measured defect in this repo's guard family has been a false positive, so
the failure this suite is really written against is a guard that blocks
legitimate work — not one that misses an evasion.
"""

import io
import json
from pathlib import Path

import pytest
from kb_setup import graph_first
from kb_setup.hook_guard import run

# Broad source searches — DENIED until the graph has been queried.
DENY_COMMANDS = [
    'rg "decide" .',
    "rg decide",  # no path at all: repo-wide by default
    'rg "hook_guard" python/',
    'grep -rn "hook_guard" python/',
    'grep -R "hook_guard" .',
    "git grep decide",
    'ag "decide" python/',
    'ls -la && rg "decide" python/',  # a searcher in a later segment still counts
    'rg "decide" python/src tests/',  # several tree targets
    'rg -g "*.py" decide',  # a restriction that still reaches source
    # --- the two P1 FALSE NEGATIVES the cold lane executed against 599584a.
    # Both defeated the guard outright, and both came from identifying a path by
    # POSITION rather than by shape. See `_looks_like_a_path`.
    "rg --sort path decide",  # an unlisted value-flag ate the repo-wide-ness
    "rg -g '!*.md' decide .",  # a NEGATED glob reaches every source file
]

# Never denied — the control arm.
ALLOW_COMMANDS = [
    # Ray's scope: one file is targeted work, not orientation.
    'rg "decide" python/src/kb_setup/hook_guard.py',
    'grep -rn "decide" python/src/kb_setup/hook_guard.py',
    'grep -n "decide" python/src/kb_setup/hook_guard.py',  # not recursive at all
    "grep -c pattern python/src/kb_setup/cli.py",
    # Prose, logs and /tmp are not source — acceptance criterion 3.
    'rg "TODO" docs/',
    'rg "rc=" /private/tmp/base-lint.log',
    'grep -rn "lesson" graphify-out/memory/',
    'rg "handoff" .agent/plans/',
    'rg "TODO" -g "*.md" .',
    # A PIPE searches bytes already in hand. Denying this would punish the very
    # habit the guard exists to encourage, which is how session_reflect's
    # `_last_arg` once reported two properly-armed probes as UNARMED.
    'mise run kb-query -- "how does X work" | rg decide',
    "cat /private/tmp/base-lint.log | grep -r pattern",
    # Text ABOUT a search is not a search. This is the direction all four of
    # hook_guard's first-day false positives came from.
    'echo "run rg decide python/ to find it"',
    'git commit -m "guard: deny `rg decide python/` before a graph query"',
    "cat > /tmp/x.sh <<'EOF'\nrg decide python/\nEOF",
    # --- the two P2 FALSE POSITIVES the cold lane executed against 599584a.
    # A regex cannot see quoting, so an ordinary commit split into a segment that
    # read as a search; and `-e` ate the pattern, so the real file was dropped as
    # "the pattern" and a single-file search was denied against this module's own
    # stated invariant.
    'git commit -m "docs && rg decide"',
    "rg -e decide python/src/kb_setup/hook_guard.py",
    # Not searchers at all.
    "ls -la",
    "mise run lint",
    "git log --oneline -5",
]


@pytest.fixture
def cwd(tmp_path: Path) -> Path:
    """A project root with the real repo's shape, so `is_dir` answers truthfully."""
    for d in ("python/src/kb_setup", "tests", "docs", ".agent/plans", "graphify-out/memory"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    for f in ("python/src/kb_setup/hook_guard.py", "python/src/kb_setup/cli.py"):
        (tmp_path / f).touch()
    return tmp_path


@pytest.mark.parametrize("command", DENY_COMMANDS)
def test_denies_a_broad_source_search_before_any_query(command: str, cwd: Path) -> None:
    reason = graph_first.decide("Bash", {"command": command}, cwd, queried=False)
    assert reason is not None, f"guard let a broad source search through: {command}"
    assert "mise run kb-query" in reason, "the refusal must print the exact query to run"


@pytest.mark.parametrize("command", ALLOW_COMMANDS)
def test_allows_targeted_prose_and_piped_searches(command: str, cwd: Path) -> None:
    assert graph_first.decide("Bash", {"command": command}, cwd, queried=False) is None


@pytest.mark.parametrize("command", DENY_COMMANDS)
def test_one_graph_query_unblocks_every_search(command: str, cwd: Path) -> None:
    """Acceptance 4. The same commands, after the session has queried the graph."""
    assert graph_first.decide("Bash", {"command": command}, cwd, queried=True) is None


# ─── the Grep TOOL, which has no shell string to parse ───────────────────────
#
# This half cannot be exercised from a Bash probe — the tool is a separate
# PreToolUse matcher, which is why `.claude/settings.json` had to grow `|Grep`.


@pytest.mark.parametrize(
    "tool_input",
    [
        {"pattern": "decide"},  # no path: repo-wide
        {"pattern": "decide", "path": "python"},  # a directory
        {"pattern": "decide", "path": "."},
        {"pattern": "decide", "path": "python", "glob": "*.py"},
    ],
)
def test_denies_a_broad_grep_tool_call(tool_input: dict, cwd: Path) -> None:
    reason = graph_first.decide("Grep", tool_input, cwd, queried=False)
    assert reason is not None, f"guard let a broad Grep through: {tool_input}"
    assert "mise run kb-query" in reason


@pytest.mark.parametrize(
    "tool_input",
    [
        {"pattern": "decide", "path": "python/src/kb_setup/hook_guard.py"},
        {"pattern": "decide", "path": "docs"},
        {"pattern": "decide", "path": "/private/tmp/base-lint.log"},
        {"pattern": "decide", "glob": "*.md"},
    ],
)
def test_allows_a_targeted_or_prose_grep_tool_call(tool_input: dict, cwd: Path) -> None:
    assert graph_first.decide("Grep", tool_input, cwd, queried=False) is None


def test_read_of_a_named_file_is_never_denied(cwd: Path) -> None:
    """Acceptance 2. `Read` is not a search, and Ray scoped the deny to searches."""
    assert graph_first.decide("Read", {"file_path": "python/x.py"}, cwd, queried=False) is None


# ─── the session marker ──────────────────────────────────────────────────────


def test_a_query_marks_the_session_and_nothing_else_does(cwd: Path) -> None:
    assert graph_first.has_queried(cwd, "sess-1") is False
    graph_first.note_query(cwd, "sess-1", "ls -la")
    assert graph_first.has_queried(cwd, "sess-1") is False, "a non-query must not unblock"
    graph_first.note_query(cwd, "sess-1", 'mise run kb-query -- "how does X work"')
    assert graph_first.has_queried(cwd, "sess-1") is True


def test_a_denied_graphify_query_does_not_earn_the_unblock(cwd: Path) -> None:
    """`graphify query` is DENIED by hook_guard, so it never runs and cannot orient.

    Crediting it would hand out the unblock for free — the escape hatch Ray
    explicitly rejected, arriving by accident instead of by design.
    """
    graph_first.note_query(cwd, "sess-2", 'graphify query "how does X work"')
    assert graph_first.has_queried(cwd, "sess-2") is False


def test_the_marker_is_scoped_to_one_session(cwd: Path) -> None:
    """The session id IS the invalidation rule, which is why there is no TTL."""
    graph_first.note_query(cwd, "sess-a", "mise run kb-query -- q")
    assert graph_first.has_queried(cwd, "sess-a") is True
    assert graph_first.has_queried(cwd, "sess-b") is False


def test_an_unknown_session_allows(cwd: Path) -> None:
    """Ambiguity resolves to ALLOW everywhere in this module, including here."""
    assert graph_first.has_queried(cwd, "") is True
    assert graph_first.decide("Bash", {"command": "rg decide ."}, cwd, queried=True) is None


# ─── the wired hook, end to end ──────────────────────────────────────────────


def _hook(payload: dict, monkeypatch, capsys) -> str:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert run() == 0
    return capsys.readouterr().out


def test_the_hook_denies_a_broad_search_and_a_query_unblocks_it(
    cwd: Path, monkeypatch, capsys
) -> None:
    """The wiring, not just the decision — `run()` is what settings.json calls."""
    search = {
        "tool_name": "Bash",
        "session_id": "hook-sess",
        "cwd": str(cwd),
        "tool_input": {"command": 'rg "decide" python/'},
    }
    out = json.loads(_hook(search, monkeypatch, capsys))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "mise run kb-query" in out["hookSpecificOutput"]["permissionDecisionReason"]

    query = dict(search, tool_input={"command": 'mise run kb-query -- "how does X work"'})
    assert _hook(query, monkeypatch, capsys).strip() == ""
    assert _hook(search, monkeypatch, capsys).strip() == ""


def test_the_graphify_redirect_still_wins_over_this_guard(cwd: Path, monkeypatch, capsys) -> None:
    """A hand-run graphify must keep reporting the mise-task redirect.

    Both refusals are correct for `graphify label`; only one of them tells you
    what to do about it. A newer guard shadowing an older one's remediation is a
    silent regression no assertion on "was it denied" would catch.
    """
    payload = {
        "tool_name": "Bash",
        "session_id": "hook-sess-2",
        "cwd": str(cwd),
        "tool_input": {"command": "graphify label"},
    }
    out = json.loads(_hook(payload, monkeypatch, capsys))
    assert "kb-label" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_a_command_tripping_both_guards_emits_exactly_one_decision(
    cwd: Path, monkeypatch, capsys
) -> None:
    """One command, one hook response — `json.loads` on two objects is a crash.

    Added because the arm that deletes the early `return 0` SURVIVED: the fixture
    above uses `graphify label`, which is not also a search, so the mutation was a
    no-op for it and the sweep graded a live line as dead. The command that
    exhibits the harm has to trip BOTH guards at once
    (`a-surviving-arm-can-be-a-no-op`).
    """
    payload = {
        "tool_name": "Bash",
        "session_id": "hook-sess-both",
        "cwd": str(cwd),
        "tool_input": {"command": 'graphify label && rg "decide" python/'},
    }
    out = _hook(payload, monkeypatch, capsys)
    assert out.strip().count("hookSpecificOutput") == 1, f"two decisions emitted: {out}"
    assert "kb-label" in json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]


def test_the_hook_still_ignores_tools_it_does_not_guard(cwd: Path, monkeypatch, capsys) -> None:
    payload = {
        "tool_name": "Read",
        "session_id": "hook-sess-3",
        "cwd": str(cwd),
        "tool_input": {"file_path": "python/src/kb_setup/hook_guard.py"},
    }
    assert _hook(payload, monkeypatch, capsys).strip() == ""
