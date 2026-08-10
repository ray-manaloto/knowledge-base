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
from pathlib import Path

from kb_setup import graph_first
from kb_setup.result import Ok, Result, exit_code

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
    "save-result": (
        'mise run kb-remember -- --question "Q" --answer-file A.md --outcome useful'
        "   (--outcome corrected also needs --correction-file C.md, or the lesson "
        "renders empty in LESSONS.md)"
    ),
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
#:
#: Imported from :mod:`kb_setup.graph_first` rather than defined twice: that
#: guard needs the identical answer to "where do the shell's commands stop?", and
#: two copies of a pattern this subtle is how a redirect table drifts from its
#: enforcement. Same reason `decide` is shared with `skill_lint`.
_HEREDOC = graph_first.HEREDOC

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


def check_hook_call(raw: str) -> Result[str | None]:
    """The boundary (§2 R5): the denial reason for one PreToolUse payload, or None.

    Returns rather than raises, and prints nothing — :func:`run` renders the
    deny JSON. Same split as ``skill_lint.check_skill_lint``/``skill_lint_main``.

    **This is the one converted boundary whose `rc` carries no information, and
    the reason is the protocol rather than an oversight.** A PreToolUse hook's
    verdict travels in the JSON it writes to *stdout*; its exit code is only
    "did the hook itself survive", and this guard is documented to fail OPEN —
    every path returns 0, including the ones that deny. So a denial is
    `Ok(reason)` at `Rc.OK`, not `Rc.FINDINGS`: returning FINDINGS would make
    :func:`exit_code` hand back 1, which in this protocol means the hook crashed
    and would change how Claude Code treats the call.

    What the split buys where the integer bought nothing: a caller — the
    ``skill_lint`` gate is already one, via :func:`decide` — can now ask this
    module for a verdict without going through stdin and a JSON envelope, and
    the three ways a payload can produce "allow" (not our tool, nothing matched,
    an internal error we swallowed) stay distinguishable at the type level
    instead of collapsing into one `return 0`.
    """
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError, ValueError:
        return Ok(None)
    tool_name = payload.get("tool_name")
    if tool_name not in {"Bash", "Grep"}:
        return Ok(None)
    tool_input = payload.get("tool_input") or {}
    if tool_name == "Bash":
        reason = _graphify_redirect(tool_input)
        if reason:
            return Ok(reason)
    try:
        return Ok(_graph_first(payload, tool_name, tool_input))
    except Exception:
        return Ok(None)


def run() -> int:
    """PreToolUse entry. Reads the tool call on stdin; denies hand-run graphify.

    Fails OPEN (exit 0, no output = allow) on any parse/internal error.

    Kept returning ``int``: ``.claude/settings.json`` invokes this as a hook and
    this module's existing exit-code assertions are the regression arm proving
    the ``Result`` split changed no behaviour.
    """
    result = check_hook_call(sys.stdin.read())
    # Narrowed on `Ok`, not against `Err`: `Result` has a THIRD variant, and
    # `External` carries no `.value`. ty catches the negative form.
    if isinstance(result, Ok) and result.value:
        _deny(result.value)
    return exit_code(result)


def _graphify_redirect(tool_input: dict) -> str | None:
    """The original guard's verdict for a Bash call, or None. Never raises.

    Extracted from `run` so each guard is one call there rather than an inline
    block — the ORDER of the two is load-bearing (see `_graph_first`), and an
    order you can read in three lines is one that survives the next edit.
    """
    command = tool_input.get("command", "")
    if not isinstance(command, str) or not command.strip():
        return None
    try:
        return decide(command)
    except Exception:
        return None


def _graph_first(payload: dict, tool_name: str, tool_input: dict) -> str | None:
    """Deny a broad source search until this session has queried the graph (#253).

    Runs AFTER the graphify redirect above, and only on a command that redirect
    allowed. Order matters in both directions: a denied `graphify query` must not
    earn the unblock (it never runs), and a hand-run graphify must keep reporting
    the mise-task redirect rather than being shadowed by this newer refusal.

    `cwd` and `session_id` come from the payload — both verified present against a
    real captured PreToolUse payload rather than assumed, because the whole
    session-scoping design rests on the second one existing.
    """
    session_id = payload.get("session_id")
    session_id = session_id if isinstance(session_id, str) else ""
    cwd_raw = payload.get("cwd")
    cwd = Path(cwd_raw) if isinstance(cwd_raw, str) and cwd_raw else Path.cwd()
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if isinstance(command, str):
            graph_first.note_query(cwd, session_id, command)
    queried = graph_first.has_queried(cwd, session_id)
    return graph_first.decide(tool_name, tool_input, cwd, queried=queried)


if __name__ == "__main__":
    raise SystemExit(run())
