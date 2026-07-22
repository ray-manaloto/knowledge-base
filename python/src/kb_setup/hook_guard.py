"""PreToolUse guard: NEVER run graphify by hand — go through a mise task.

Ray, 2026-07-22: all graphify operations must be driven by a skill that calls a
mise task (kb-add / kb-build / kb-update / kb-merge / kb-label / kb-transcribe /
kb-query / kb-artifacts / ...), never a raw `graphify …` / `_merge_docs.py` /
graphify-bundled-python invocation. This guard is the machine enforcement of that
rule (the sibling of dotfiles' `dotfiles_setup.hook_guard`).

Wired in `.claude/settings.json` as a PreToolUse `Bash` hook. It reads the tool
call from stdin, and if the command runs graphify directly it returns a `deny`
with the canonical mise-task redirect. It FAILS OPEN on any internal error — a
crashed guard must never brick every Bash call.

Read-only introspection with no task equivalent (`graphify path/explain/god-nodes/
affected/diagnose`) is allowed; everything that mutates the graph, calls an LLM,
or has a task equivalent is redirected.
"""

from __future__ import annotations

import json
import re
import sys

# Command-position matcher: `graphify` as a command word (line start or after a
# shell separator), not the substring inside a URL/arg. Captures the subcommand.
_GRAPHIFY_CMD = re.compile(
    r"(?:^|[;&|]|&&|\|\||\bthen\b|\bdo\b)\s*graphify\s+([a-z][a-z-]*)", re.IGNORECASE
)
# graphify's bundled interpreter, or any python running _merge_docs / import graphify.
_GRAPHIFY_PY = re.compile(
    r"(graphifyy/[^\s]*/bin/python|_merge_docs\.py|import\s+graphify|graphify\.transcribe)"
)

# subcommand -> the mise task (or None = not allowed at all) that replaces it.
_REDIRECT: dict[str, str] = {
    "add": "mise run kb-add -- <url>",
    "label": "mise run kb-label",
    "cluster": "mise run kb-label   (or mise run kb-build to rebuild)",
    "cluster-only": "mise run kb-label",
    "update": "mise run kb-update -- <name>",
    "extract": "mise run kb-build",
    "merge-graphs": "mise run kb-build   (or mise run kb-merge -- <chunk> for a doc chunk)",
    "clone": "mise run kb-build   (add a sources/<name>.manifest first)",
    "query": 'mise run kb-query -- "<question>"',
    "save-result": 'mise run kb-remember -- --question "Q" --answer "A" --outcome useful',
    "reflect": "mise run kb-reflect",
    "add-watch": "NOT ALLOWED — never `graphify watch`",
    "watch": "NOT ALLOWED in this repo (do-not: graphify --watch / hook install)",
    "install": "NOT ALLOWED — graphify install mutates config; this KB is project-only",
    "uninstall": "NOT ALLOWED here",
    "hook": "NOT ALLOWED — never `graphify hook install`",
}
# read-only introspection with no task equivalent — allowed as-is.
_ALLOWED_READONLY = {
    "path",
    "explain",
    "god-nodes",
    "affected",
    "diagnose",
    "--help",
    "-h",
    "--version",
}

_REASON_PY = (
    "Do not run graphify by hand via its bundled interpreter or _merge_docs.py. "
    "Use the mise task instead: `mise run kb-merge -- <chunk> [root]` to merge a "
    "doc chunk, `mise run kb-transcribe -- <audio>` to transcribe. All graphify "
    "work goes through a mise task (KB CLAUDE.md; enforced by kb_setup.hook_guard)."
)


def _deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def _verdict(command: str) -> str | None:
    """Return a deny-reason if `command` runs graphify by hand, else None."""
    # A mise task legitimately shells out to graphify inside itself — allow it.
    # (The guard only sees the Bash command Claude issues, not the task's children.)
    if re.search(r"\bmise\s+run\s+kb-", command):
        return None

    m = _GRAPHIFY_CMD.search(command)
    if m:
        sub = m.group(1).lower()
        if sub in _ALLOWED_READONLY:
            return None
        task = _REDIRECT.get(sub)
        if task:
            return (
                f"Do not run `graphify {sub}` by hand. Use the mise task: {task}. "
                "All graphify work goes through a mise task (KB CLAUDE.md; enforced "
                "by kb_setup.hook_guard)."
            )
        return (
            f"Do not run `graphify {sub}` by hand — drive graphify through a mise "
            "task (kb-add/kb-build/kb-update/kb-merge/kb-label/kb-transcribe/"
            "kb-query/kb-artifacts). Enforced by kb_setup.hook_guard."
        )

    if _GRAPHIFY_PY.search(command):
        return _REASON_PY
    return None


def run() -> int:
    """PreToolUse entry. Reads the tool call on stdin; denies hand-run graphify.

    Fails OPEN (exit 0, no output = allow) on any parse/internal error.
    """
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError, ValueError:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not command.strip():
        return 0
    try:
        reason = _verdict(command)
    except Exception:
        return 0
    if reason:
        _deny(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
