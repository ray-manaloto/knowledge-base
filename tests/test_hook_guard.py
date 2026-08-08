# Copyright (c) 2026 Raymond Manaloto
"""The PreToolUse guard denies hand-run graphify and redirects to the mise task.

Control-armed BOTH directions (probes-need-a-control-arm): every DENY case has a
matching ALLOW case, so the guard can produce both verdicts — a guard that only
ever denies (or only ever allows) is not a guard.
"""

import io
import json

import pytest
from kb_setup.hook_guard import decide, run

# (command, expected_task_substring) — must be DENIED, reason names the task.
DENY = [
    ("graphify add https://example.com/x", "kb-add"),
    ("graphify label", "kb-label"),
    ("graphify label . --backend=gemini", "kb-label"),
    ("graphify update deer-flow", "kb-update"),
    ("graphify extract sources/x --code-only", "kb-build"),
    ("graphify merge-graphs a.json b.json", "kb-build"),
    ('graphify query "how does X work"', "kb-query"),
    ("cd /kb && graphify label", "kb-label"),
    ("graphify save-result --question q", "kb-remember"),
    ("graphify reflect --graph g.json", "kb-reflect"),
    (
        "/x/graphifyy/0.9.23/graphifyy/bin/python _merge_docs.py c.json r out",
        "kb-merge",
    ),
    ("python -c 'import graphify; graphify.x()'", "kb-merge"),
    # Was `gpy -c '…'` until 2026-07-25. `gpy` is a VARIABLE NAME in graph.py /
    # graphify_ops.py holding the path to graphify's bundled interpreter — not a
    # command any session could type, so it pinned a break that cannot happen.
    # The realistic invocation is the resolved path, which is what is pinned now.
    (
        "/x/graphifyy/0.9.23/graphifyy/bin/python -c 'from graphify.transcribe import transcribe'",
        "kb-transcribe",
    ),
    ("FOO=1 graphify add https://example.com/x", "kb-add"),
    ("for f in a b; do graphify update $f; done", "kb-update"),
]

# Must be ALLOWED (verdict None) — the control arm.
ALLOW = [
    "mise run kb-add -- https://example.com/x",
    "mise run kb-label",
    "mise run kb-merge -- sources/extractions/c.json",
    "cd /kb && mise run kb-label -- --deterministic",
    'mise run kb-query -- "how does X work"',
    'graphify path "a" "b"',  # read-only introspection, no task
    'graphify explain "node"',  # read-only
    "graphify god-nodes --top 10",  # read-only
    "graphify-mcp /path/graph.json",  # kb-serve's binary — not `graphify <sub>`
    'echo "see graphify add in the docs"',  # graphify not at a command position
    "git log --oneline",
    'grep -r "graphify label" .',  # mention inside a grep pattern, not a run
    # --- the two live FALSE POSITIVES, measured 2026-07-25 by the tier-2
    # fixture table (kb_setup.eval_cases.GUARD_FIXTURES) and fixed the same day.
    # The python payload patterns had NO command-position anchoring at all, so
    # grepping FOR them denied. This is dotfiles #265 one level down.
    'grep -rn "import graphify" python/',
    'rg "_merge_docs.py" .',
    'rg "graphify.transcribe" python/',
    # The same payload with a python head in a DIFFERENT segment: the head and
    # the payload must co-occur in one segment, or `rg …; <python> -c …` denies.
    #
    # Written with `uv run python` since 2026-08-07. It was a bare `python -c`,
    # which the new bare-interpreter guard denies — correctly, but for a reason
    # this row is not about. The row exists to pin the GRAPHIFY payload check's
    # segment anchoring, so it has to reach that check rather than being stopped
    # earlier; a fixture that denies for the wrong reason still passes a
    # DENY assertion and silently stops testing what it names.
    'rg "import graphify" . ; uv run python -c "print(1)"',
]


@pytest.mark.parametrize(("command", "task"), DENY)
def test_denies_hand_run_graphify(command: str, task: str) -> None:
    reason = decide(command)
    assert reason is not None, f"should deny: {command!r}"
    assert task in reason, f"reason should redirect to {task!r}: {reason!r}"


@pytest.mark.parametrize("command", ALLOW)
def test_allows_tasks_and_readonly(command: str) -> None:
    assert decide(command) is None, f"should allow: {command!r}"


def test_run_emits_deny_json(monkeypatch, capsys) -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "graphify label"}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert run() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "kb-label" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_run_allows_non_graphify(monkeypatch, capsys) -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "mise run kb-label"}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert run() == 0
    assert capsys.readouterr().out.strip() == ""  # no deny emitted


def test_run_fails_open_on_garbage(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("not json{"))
    assert run() == 0
    assert capsys.readouterr().out.strip() == ""


def test_run_ignores_non_bash_tools(monkeypatch, capsys) -> None:
    payload = {"tool_name": "Read", "tool_input": {"file_path": "graphify label"}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert run() == 0
    assert capsys.readouterr().out.strip() == ""


# ─── bare interpreter denial (Ray, 2026-08-07) ───────────────────────────────
#
# These live in the SUITE rather than in an ad-hoc probe for a reason worth
# keeping: the first two attempts to check this guard were shell commands whose
# own TEST DATA contained the denied patterns, so the guard fired on the probe
# itself — twice. A guard whose patterns appear in ordinary text cannot be
# exercised from the command line it guards, which is also why writing this file
# needed the Write tool rather than a heredoc. That is the guard working.

_DENIED_BARE = [
    'python3 -c "import shutil"',
    "python3 - <<PY",
    'python -c "x"',
    "ls && python3 foo.py",
    "cat f | python3 -",
    "python3 script.py",
]

#: The four FALSE POSITIVES this guard produced in its first five minutes, each
#: text that DESCRIBED the guard rather than invoking an interpreter. They are
#: fixtures rather than an anecdote because they are the evidence for
#: `_code_only`, and because this is the direction every measured defect in this
#: repo's guards has come from — not evasion.
_MEASURED_FALSE_POSITIVES = [
    # 1. a probe whose own test data listed the denied shapes
    "echo \"cases: 'ls && python3 foo.py' and 'python3 -c x'\"",
    # 2. a heredoc writing this guard's test file (body is DATA, not commands)
    "cat >> tests/test_hook_guard.py <<'TEOF'\nls && python3 foo.py\nTEOF",
    # 3. a grep whose SEARCH PATTERN contained a denied shape
    "grep -n 'import graphify . ; python' tests/test_hook_guard.py",
    # 4. the commit message documenting all of the above
    'git commit -m "guard: deny bare python3, e.g. `ls && python3 x`"',
]

_ALLOWED_PY = [
    *_MEASURED_FALSE_POSITIVES,
    'uv run python -c "x"',
    "uv run python -V",
    "uv run kb-setup reclaim",
    "uv run pytest tests/",
    "grep python3 file.txt",
    'echo "use python3 for this"',
    "/usr/bin/python3 -c 'x'",
    "ls -la",
]


@pytest.mark.parametrize("command", _DENIED_BARE)
def test_denies_a_bare_interpreter_at_a_command_position(command: str) -> None:
    """A bare `python`/`python3` resolves off $PATH and silently follows the venv."""
    reason = decide(command)
    assert reason is not None, f"guard let a bare interpreter through: {command}"
    assert "uv run python" in reason, "the refusal must name the replacement"


@pytest.mark.parametrize("command", _ALLOWED_PY)
def test_allows_uv_run_and_non_command_mentions(command: str) -> None:
    """The control arm. A guard that also blocks `uv run python` is an outage.

    `/usr/bin/python3` is deliberately allowed: it names an explicit interpreter
    rather than resolving off `$PATH`, so it does not have the drift this guard
    exists to prevent.
    """
    assert decide(command) is None, f"guard misfired on: {command}"


def test_the_arms_harness_invocation_is_not_broken_by_the_guard() -> None:
    """`kb_setup.arms` runs `[sys.executable, "-m", "pytest", ...]`.

    A guard that breaks the mutation harness would cost more than it saves —
    every fix in this repo is verified through it.
    """
    assert decide("python3 -m pytest tests/") is None
