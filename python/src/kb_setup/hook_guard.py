# Copyright (c) 2026 Raymond Manaloto
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

# Command position: start of string or just after a shell separator, tolerating
# an `env`/`VAR=x` prefix so `FOO=1 graphify add …` cannot slip past (it did
# before — `_GRAPHIFY_CMD` required `graphify` to sit immediately after the
# separator). Shared by every pattern below so they cannot drift apart.
_CMD_POS = r"(?:^|[;&|]|&&|\|\||\bthen\b|\bdo\b)\s*(?:(?:env\s+)?(?:\w+=\S*\s+)*)"

# `graphify` as a command word, not the substring inside a URL/arg or a quoted
# mention. Captures the subcommand.
_GRAPHIFY_CMD = re.compile(_CMD_POS + r"graphify\s+([a-z][a-z-]*)", re.IGNORECASE)

# graphify's bundled interpreter, invoked as the command.
_GRAPHIFY_PYBIN = re.compile(_CMD_POS + r"\S*graphifyy/\S*/bin/python\b")

# A python-ish command head DRIVING graphify — the head and the payload must sit
# in the same segment (`[^;&|\n]*` stops at the next separator).
#
# The command head is what makes this precise, and it is the whole fix (found by
# this repo's own tier-2 fixture table, 2026-07-25). The pattern used to be a
# bare payload search with NO anchoring, so grepping FOR it tripped it:
# `grep -rn "import graphify" python/` and `rg "_merge_docs.py" .` both DENIED.
# That is dotfiles #265 one level down — false positives are the only defect
# class ever measured in either guard, and both rows are now pinned.
#
# Masking quoted spans (dotfiles' `_inert_masked` fix for the same class) is the
# WRONG fix here and was rejected on evidence: the real deny,
# `python -c "import graphify"`, carries its payload legitimately quoted, so
# blanking quoted content would break the very denial the rule exists for. The
# discriminator between the two is the command head, not the quoting.
#
# Documented fail-open, consistent with the rest of this guard: `python -m
# kb_setup._merge_docs` (no `.py`) is not matched, and a `mise run kb-…` anywhere
# in the command short-circuits the whole guard (see `decide`).
_PY_DRIVES_GRAPHIFY = re.compile(
    _CMD_POS + r"(?:\S*/)?(?:python[\d.]*|uv\s+run)\b[^;&|\n]*"
    r"(?:_merge_docs\.py|import\s+graphify|graphify\.transcribe)"
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


def decide(command: str) -> str | None:
    """Return a deny-reason if `command` runs graphify by hand, else None.

    The guard's decision function, and its introspection surface: the tier-2
    fixture table in :mod:`kb_setup.eval_cases` drives every row through THIS
    call, so the function that denies a command is the one the corpus grades.
    Public (it was `_verdict`) for exactly that reason — a gate reaching through
    a private name is a gate that can be refactored out from under.
    """
    # A mise task legitimately shells out to graphify inside itself — allow it.
    # (The guard only sees the Bash command Claude issues, not the task's children.)
    # Fail-open by design, and deliberately not narrowed: it matches anywhere in
    # the command, so `mise run kb-build && graphify query "x"` is allowed. Same
    # class as dotfiles' documented `$(…)`/`sh -c`/`eval` holes — this is a
    # redirect guard, not a sandbox.
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

    if _GRAPHIFY_PYBIN.search(command) or _PY_DRIVES_GRAPHIFY.search(command):
        return _REASON_PY
    return _bare_python(command)


#: A bare interpreter at a COMMAND POSITION. `uv run python …` is unaffected:
#: the leading alternation requires the token to start a command, and in
#: `uv run python` the preceding token is `run`, so it never matches there.
#: (This comment said "lookbehind" until the standards review pointed out there
#: is none — prose asserting a mechanism the next line does not implement.)
#:
#: **A NEWLINE is a command separator.** It was missing from this class until the
#: spec review measured the hole: a second-line `python3 -c 1` was allowed while
#: the control `"ls && python3 x.py"` denied, so the probe discriminated and the
#: gap was real. Multi-line Bash is the ordinary shape here, not an exotic one,
#: which made this the common evasion rather than a corner case.
#:
#: There is deliberately NO `-m pytest` exemption. One was written, justified by
#: `kb_setup.arms` building `[sys.executable, "-m", "pytest", ...]` — but that is
#: a `subprocess` argv (`arms.py`), which never reaches a Bash PreToolUse hook at
#: all. The exemption defended a scenario this guard cannot observe, and a hole
#: argued from an unreachable case is a hole. Typed at a shell, `python3 -m
#: pytest` is exactly the bare interpreter Ray asked to deny.
_BARE_PYTHON = re.compile(r"(?:^|[|;&\n]\s*|\breturn\s+)\s*(?:command\s+)?(python3?)\b")

_REASON_BARE_PY = (
    "Do not run `{exe}` directly — use `uv run python …`, or the mise task that owns "
    "this work. A bare interpreter resolves off $PATH, so it silently depends on "
    "whether a venv happens to be active: this repo ran its gates on 3.14.0 under a "
    "3.14.7 pin for two weeks that way. `uv run` reads pyproject.toml and cannot "
    "drift. If you are about to write a throwaway script for the second time, that "
    "is what `mise run kb-distill` exists to catch — give it a kb_setup module and a "
    "mise task instead (Ray, standing directive; kb_setup.hook_guard)."
)


#: A heredoc body is DATA, never a command — everything from `<<TAG` onward is
#: payload the shell hands to a program. Matching inside it is how this guard
#: denied the very commit message that documented it.
_HEREDOC = re.compile(r"<<-?\s*'?\"?\w+")

#: A quoted span is likewise data: a grep pattern, an echo string, a `-m` message.
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def _code_only(command: str) -> str:
    """Strip heredoc bodies and quoted spans, leaving the shell's CODE.

    Written after **four measured false positives in five minutes**, every one of
    them text that *described* the guard rather than invoking an interpreter:

    1. a probe whose test data listed ``&& python3`` as a case;
    2. a heredoc writing this guard's own test file;
    3. ``grep`` whose search PATTERN contained ``; python``;
    4. the ``git commit`` message documenting all of the above.

    That is the direction every measured defect in this repo's guards has come
    from — dotfiles #176 is the same shape one level up, and had to allowlist a
    commit message describing the graphify ban. Precision over recall is the
    trade this guard family makes on purpose: it is a redirect, not a sandbox,
    and a guard that misfires on ordinary prose gets disabled by the humans it
    annoys, which costs more than the evasions it prevents.
    """
    head = _HEREDOC.split(command, maxsplit=1)[0]
    return _QUOTED.sub(" ", head)


def _bare_python(command: str) -> str | None:
    """Deny a bare `python`/`python3` at a command position; allow `uv run python`.

    Ray, 2026-08-07, after catching this session shelling out to `python3 -c` eight
    times while building a tool whose whole premise is skill -> mise task -> python
    library. The measured harm is not hypothetical: `python3` resolved correctly
    here only because a venv happened to be active, which is luck rather than
    correctness.

    Scoped to a command position AND to code rather than data (see `_code_only`),
    so it cannot fire on prose, a `--python3` flag, or a path containing the word.
    The mutation harness is unaffected without any exemption: `kb_setup.arms`
    invokes pytest through `subprocess`, which never routes through a Bash hook.
    """
    m = _BARE_PYTHON.search(_code_only(command))
    if not m:
        return None
    return _REASON_BARE_PY.format(exe=m.group(1))


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
        reason = decide(command)
    except Exception:
        return 0
    if reason:
        _deny(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
