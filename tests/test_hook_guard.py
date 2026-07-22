"""The PreToolUse guard denies hand-run graphify and redirects to the mise task.

Control-armed BOTH directions (probes-need-a-control-arm): every DENY case has a
matching ALLOW case, so the guard can produce both verdicts — a guard that only
ever denies (or only ever allows) is not a guard.
"""

import io
import json

import pytest
from kb_setup.hook_guard import _verdict, run

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
    ("gpy -c 'from graphify.transcribe import transcribe'", "kb-transcribe"),
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
]


@pytest.mark.parametrize(("command", "task"), DENY)
def test_denies_hand_run_graphify(command: str, task: str) -> None:
    reason = _verdict(command)
    assert reason is not None, f"should deny: {command!r}"
    assert task in reason, f"reason should redirect to {task!r}: {reason!r}"


@pytest.mark.parametrize("command", ALLOW)
def test_allows_tasks_and_readonly(command: str) -> None:
    assert _verdict(command) is None, f"should allow: {command!r}"


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
