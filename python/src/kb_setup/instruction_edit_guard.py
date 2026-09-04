# Copyright (c) 2026 Raymond Manaloto
"""PreToolUse guard: refuse an instruction-file edit that would breach its budget.

#698, built to the decisions in ``docs/design/edit-write-hook-surface.md`` (#700).

The asymmetry this closes
=========================

Before this, ``.claude/settings.json`` registered ``PreToolUse`` on
``Bash|Grep`` and ``Read|Glob`` and had **no Edit/Write matcher at all**, while
``.codex/hooks.json`` carried a ``PostToolUse`` ``apply_patch`` handler. On the
surface where this repo does most of its editing, the codex lane was the one
receiving edit-time feedback.

Two jobs, one handler
=====================

``PreToolUse`` alone does both, because the payload carries enough to compute the
post-edit size *before* the write happens (``hooks.md:1618-1632``): a ``Write``
brings ``{file_path, content}`` and an ``Edit`` brings
``{file_path, old_string, new_string, replace_all}``.

* **Over budget** -> ``permissionDecision: "deny"`` plus
  ``permissionDecisionReason``, which Claude reads.
* **Within budget** -> ``additionalContext`` carrying the projected headroom,
  and **no ``permissionDecision`` at all**.

Both halves are forced by the contract rather than chosen:

* ``permissionDecisionReason`` reaches Claude **only** on ``"deny"``; on
  ``"allow"``/``"ask"`` it is shown to the user and not to Claude
  (``hooks.md:1745``). So headroom has to ride in ``additionalContext``.
* Returning ``"allow"`` would additionally **skip the user's permission prompt**
  (``hooks.md:1743``) — a side effect nobody asked for. Omitting the field
  leaves the normal flow untouched.
* ``additionalContext`` is ignored under ``"defer"`` (``hooks.md:1747``), so
  defer-plus-headroom discards the very thing it sends.

🔴 A hook ``if`` filter matches on the ACTUAL TOOL NAME
=======================================================

The settings wiring needs **both** ``Edit(<glob>)`` and ``Write(<glob>)`` per
path class — 8 handlers, not 4 — and that is not what the docs' most-quoted line
suggests. ``permissions.md:316``: *"Claude Code checks file permissions against
`Edit(path)` and `Read(path)` rules only. If you write a path rule for `Write`
… Claude Code accepts the rule but never consults it … Use `Edit(docs/**)` in
place of `Write(docs/**)`."*

**That is about the PERMISSION SYSTEM and does not transfer to a hook ``if``.**
``hooks.md:427`` says the field "uses the same syntax as permission rules" —
same *syntax*, not the same tool-name resolution.

Measured 2026-09-04, one variable at a time, by attempting a real over-budget
write and observing whether the file reached disk:

=========================  ==========  ======
``if`` rule                tool call   fires?
=========================  ==========  ======
(none)                     Write       yes
``Edit(.claude/rules/**)`` Write       **NO**
``Write(.claude/rules/**)``Write       yes
``Edit(.claude/rules/**)`` Edit        yes
=========================  ==========  ======

The first wiring here was Edit-only on all four classes, and the unit tests were
all green while the hook fired on nothing. **Unit tests prove the module; only a
live write proves the WIRING** — the same "written is not running" lesson the
codex hook-trust incident taught, arriving on the Claude side.

Why it re-runs the WHOLE sweep
==============================

:func:`kb_setup.md_budget.check` with an ``overrides`` map, never a per-file
checker. A second implementation would be free to disagree with the hk gate, and
the entire value here is that the hook and the gate cannot drift. The sweep is
~0.25 s warm over 50 files; there is nothing to optimise.

Fail CLOSED — and the timeout does not do it for you
====================================================

``hook_guard`` fails OPEN on its own errors, deliberately: a crashed guard must
not brick every Bash call. That reasoning does not carry here. The blast radius
is one instruction file, and a silent internal failure defeats exactly the policy
the hook advertises. So a candidate this module MATCHED but could not evaluate is
denied.

🔴 The timeout path cannot be leaned on. ``hooks.md:845``: *"A timed-out
`command`, `http`, or `mcp_tool` hook doesn't block the tool call... don't count
on a stalled hook to act as a gate."* Fail-closed is implemented here or it does
not exist.

🔴 SCOPE, stated so silence does not imply coverage
===================================================

**This guard sees the ``Edit`` and ``Write`` TOOLS ONLY. A Bash-tool write to an
instruction file is completely invisible to it** — a heredoc (``cat >
.claude/rules/x.md <<'EOF'``), ``tee``, ``sed -i``, ``perl -pi``, a ``python -c``
that writes a file, ``find … -exec``, ``xargs``. None of them reaches a matcher
of ``Edit|Write``.

This is not an oversight, but the previous version of this docstring never said
so, which made it one in effect. ``docs/design/edit-write-hook-surface.md``
decision 5 rules that the Bash surface is a **different tenant** — its sibling
``inplace_edit.py:96-100`` already lists the same blind spots under its own
"SCOPE" heading, and closing them here would put shell parsing inside a budget
guard. Cold review P1 on ``3047b2989777`` was right that the admission existed
for the sibling and had not been carried here.

🔴 **THAT TENANT NOW EXISTS: `kb_setup.instruction_shell_write` (#711, Ray's
ruling 2026-09-04).** The shapes listed above are no longer merely admitted —
a `>`/`>>` redirect, a `tee`, an in-place `sed`/`perl` and a writing
`python -c` are DENIED at a `Bash` matcher, by SHAPE, with the remedy pointing
back at these two tools. So this paragraph's "completely invisible to it" is
still true of THIS module and is no longer true of the repo.

Two things still follow, and the second is the uncomfortable one:

* the hk ``md_size_budget`` step remains the **authority**; both guards are
  faster, earlier signals and neither is the last line;
* the gap is **narrowed, not closed** — ``find … -exec sed -i``, ``xargs``,
  ``sh -c``, ``eval`` and ``$(…)`` still reach these files, and this repo's own
  conventions push agents toward Bash for file work. The sibling module's own
  SCOPE block is the current list; do not read this one as covering it.

What it declines to judge, and why that is not a failure
========================================================

A payload for a tool this module does not model, or a path that is not an
instruction file, produces **no output and exit 0** — not a deny. Fail-closed
applies to a *matched candidate*, and treating "not my business" as a breach
would make the guard block routinely. **A guard that blocks routinely gets
switched off, and a switched-off guard is worse than none** — the reason #700
ordered #697's trim before any denial at all.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from kb_setup import md_budget
from kb_setup.result import Rc

EDIT_TOOLS = frozenset({"Edit", "Write", "NotebookEdit"})
"""Tools whose payload this module knows how to project.

``NotebookEdit`` is listed so that a payload naming an instruction file reaches
a DECISION rather than slipping past as an unknown tool. It is not in the
settings matcher — it writes ``.ipynb``, which is not instruction markdown — and
its payload shape is not modelled, so :func:`project` returns ``None`` and the
candidate is **DENIED**, fail-closed.

That last word is a correction (cold review P2 on ``3047b2989777``). This
docstring previously said such a payload was *"declined rather than guessed at"*,
which reads as the silent exit and is the opposite of what runs. Measured:

.. code-block:: text

    {"tool_name":"NotebookEdit","tool_input":{"file_path":".claude/rules/do-not.md",...}}
    -> permissionDecision: "deny"

Deny is the correct behaviour — an unmodelled payload against a budgeted file has
an unknown post-edit size, and this guard fails closed on a matched candidate.
Only the prose was wrong, which is the more dangerous half: a reader trusting it
would have "fixed" the code to match.

``MultiEdit`` is deliberately absent: **0** occurrences in the pinned docs. That
tool no longer exists.
"""


@dataclass(frozen=True)
class Verdict:
    """What the guard decided, before it is rendered as hook JSON."""

    deny: bool
    reason: str
    """Non-empty only when the guard has something to say."""

    @property
    def silent(self) -> bool:
        """True when the guard has no opinion and must emit nothing."""
        return not self.deny and not self.reason


SILENT = Verdict(deny=False, reason="")


def _project_edit(payload: dict[str, object], path: Path) -> str | None:
    """Apply an ``Edit`` payload to ``path``'s current bytes."""
    old = payload.get("old_string")
    new = payload.get("new_string")
    if not isinstance(old, str) or not isinstance(new, str):
        return None
    try:
        current = path.read_text(errors="replace") if path.is_file() else ""
    except OSError:
        return None
    if payload.get("replace_all") is True:
        return current.replace(old, new) if old in current else None
    # Mirror the real Edit tool's preconditions, or this projects a write that
    # can never reach disk. It requires `old_string` to be present AND unique
    # unless `replace_all` is set, so both a miss and an ambiguous match are
    # "cannot model" -> deny, not a guessed first-occurrence replacement.
    # (Cold review P3 on `3047b2989777`: only the miss was handled.)
    if old and current.count(old) != 1:
        return None
    return current.replace(old, new, 1)


def project(tool: str, payload: dict[str, object], path: Path) -> str | None:
    """The content ``path`` would hold after this call, or ``None`` if unknowable.

    ``None`` is "I cannot model this", never "no change" — the caller must not
    collapse the two, because an unmodelled payload evaluated as the current
    file would report a clean budget for an edit nobody measured.
    """
    if tool == "Write":
        content = payload.get("content")
        return content if isinstance(content, str) else None
    if tool == "Edit":
        return _project_edit(payload, path)
    return None


def _headroom(report: md_budget.Report, rel: str) -> str:
    """One line of projected headroom for ``rel``, for ``additionalContext``."""
    return (
        f"[md-budget] After this edit {rel} is within budget. "
        f"{report.counted} instruction files counted; "
        f"eager context ~{report.eager_bytes} bytes every session."
    )


def _matched(root: Path, tool: str, payload: dict[str, object]) -> tuple[Path, str] | None:
    """``(path, rel)`` when this payload is a budgeted candidate, else ``None``.

    Split out so :func:`evaluate` holds only DECISIONS. Everything this function
    rejects exits silently; everything it returns is owed a verdict, and keeping
    the two sets in separate functions is what stops a later edit blurring them.
    """
    raw_path = payload.get("file_path")
    if tool not in EDIT_TOOLS or not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError, OSError:
        return None  # outside this repo; not ours to budget
    if md_budget.classify(rel) is None:
        return None  # not an instruction file
    return path, rel


def evaluate(root: Path, tool: str, payload: dict[str, object]) -> Verdict:
    """Decide on one PreToolUse payload. Never raises."""
    candidate = _matched(root, tool, payload)
    if candidate is None:
        return SILENT
    path, rel = candidate

    # From here the candidate IS matched, so every remaining exit is a decision.
    proposed = project(tool, payload, path)
    if proposed is None:
        return Verdict(
            deny=True,
            reason=(
                f"[md-budget] {rel} is a budgeted instruction file, but this "
                f"{tool} payload could not be projected, so its post-edit size "
                f"is unknown. Refusing rather than guessing. Re-run "
                f"`mise run lint` after any manual edit."
            ),
        )
    try:
        report = md_budget.check(root, overrides={rel: proposed})
    except (OSError, ValueError, RecursionError) as exc:
        return Verdict(
            deny=True,
            reason=(
                f"[md-budget] could not evaluate {rel} against its budget "
                f"({type(exc).__name__}: {exc}). Refusing rather than passing an "
                f"unmeasured edit — this guard fails CLOSED on a matched file."
            ),
        )

    mine = [v for v in report.violations if v.path == rel]
    if not mine:
        return Verdict(deny=False, reason=_headroom(report, rel))
    detail = "; ".join(v.message for v in mine)
    return Verdict(
        deny=True,
        reason=(
            f"[md-budget] this edit puts {rel} OVER its budget — {detail}. "
            f"Trim before writing: de-duplicate against the rule that owns the "
            f"fact, re-home evidence to docs/ keeping the norm, or move detail "
            f"into a references/ sidecar (unbudgeted). See "
            f"`.claude/rules/md-size-budgets.md`."
        ),
    )


def render(verdict: Verdict) -> str | None:
    """The hook's stdout JSON, or ``None`` when it must stay silent.

    On the allow path this deliberately emits ``additionalContext`` with **no**
    ``permissionDecision`` key — see the module docstring.
    """
    if verdict.silent:
        return None
    out: dict[str, object] = {"hookEventName": "PreToolUse"}
    if verdict.deny:
        out["permissionDecision"] = "deny"
        out["permissionDecisionReason"] = verdict.reason
    else:
        out["additionalContext"] = verdict.reason
    return json.dumps({"hookSpecificOutput": out})


def main(root: Path, stdin_text: str | None = None) -> int:
    """CLI entry: read a PreToolUse payload on stdin, print the decision."""
    text = sys.stdin.read() if stdin_text is None else stdin_text
    try:
        event = json.loads(text or "{}")
    except json.JSONDecodeError, TypeError:
        # A payload we cannot parse is not a matched candidate — there is no
        # file_path to match on — so this stays silent rather than denying.
        return Rc.OK
    if not isinstance(event, dict):
        return Rc.OK
    tool = event.get("tool_name")
    payload = event.get("tool_input")
    verdict = evaluate(
        root,
        tool if isinstance(tool, str) else "",
        payload if isinstance(payload, dict) else {},
    )
    rendered = render(verdict)
    if rendered is not None:
        print(rendered)
    return Rc.OK
