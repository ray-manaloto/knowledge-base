# Copyright (c) 2026 Raymond Manaloto
"""Deny a hand-chained lint/typecheck; redirect it to `mise run kb-check`.

Ray's ruling, 2026-08-17, and the argument is a measurement rather than a
preference. `mise run kb-check -- <paths>` exists precisely because nothing
answered *"are these two files clean?"* — `check` is whole-repo and `kb-gates`
runs the ship gates — and the vacuum was filled 35 times in one session by
pipelines that discard the gate's exit code. This round filled it **12 more
times** (`kb-session-reflect`, `gate-by-hand`), in a session that had already
used `kb-check` correctly and then drifted back mid-round.

WHY A DENY AND NOT A WARNING. This repo has the comparison, on its own
directives: the warning-only graph-first rule was complied with **0 times out of
19** in one session, while the DENY that replaced it took its own violations
**62 -> 0**. A directive that costs nothing to ignore is ignored.

WHAT THIS IS NOT. It is a REDIRECT guard, not a sandbox — `$(…)`, `sh -c` and
aliases all get through by design, exactly as `hook_guard` documents for its own
family. Precision over recall: the only measured defects in this repo's guards
have been false positives, never evasion, and a guard that misfires on
legitimate work is one people route around.

SCOPE, kept narrow on purpose:

* Only `ruff check`, `ruff format` and `ty check` — the three `kb-check` runs.
* **`pytest` is deliberately absent.** `mise-tasks-only.md` explicitly allows a
  single-test `uv run pytest tests/x.py::test_y`, and a guard contradicting the
  rule it enforces is worse than no guard.
* A command containing `mise run kb-` is allowed outright, because `kb-check`
  itself shells out to exactly these tools.
* `--version` / `--help` are introspection, not a gate.
"""

from __future__ import annotations

import re

#: The three tools `kb-check` owns, at a COMMAND POSITION — start of the command,
#: or after a shell operator. `uv run ruff …` matches because `ruff` follows
#: `run`, which is how every invocation in this repo is spelled; a bare `ruff …`
#: matches too, since the mise shim makes that reachable.
#:
#: `\bruff\s+(?:check|format)` rather than a bare `ruff`, so `ruff --version` and
#: `ruff rule E501` are untouched — they answer a question rather than gating.
_HAND_GATE = re.compile(
    r"(?:^|[;&|]\s*|\buv\s+run\s+)(?:\S*/)?(?:ruff\s+(?:check|format)|ty\s+check)\b"
)

#: Introspection that happens to be spelled with a gate's name. A version probe
#: is not a gate run, and denying it would be the false positive this guard is
#: most likely to produce.
_INTROSPECTION = re.compile(r"--version|--help|\s-h(?:\s|$)")

_REASON = (
    "Do not hand-chain the gates. Use `mise run kb-check -- <paths>` — it runs "
    "ruff, format, ty AND those paths' own tests, and returns REAL exit codes "
    "with nothing in between to discard them. A hand-run chain has to be piped "
    "to be read, and a pipe returns the LAST command's status: this repo "
    "measured 35 gate invocations in one session whose failure would have been "
    "invisible. For the whole repo use `mise run lint` / `mise run test`, and "
    "for the ship gates `mise run kb-gates` (which records each result to "
    ".agent/kb/gates/). Enforced by kb_setup.check_first; Ray's ruling "
    "2026-08-17, after this directive was violated 12 times in one round."
)


def decide(command: str) -> str | None:
    """Return a deny-reason if `command` hand-runs a gate, else None.

    Public and pure, on `hook_guard.decide`'s precedent: the function that denies
    a command is the one a fixture table can grade, and a gate reaching through a
    private name is a gate that can be refactored out from under.
    """
    if not command or not command.strip():
        return None
    # A mise task legitimately shells out to these tools inside itself. Matched
    # ANYWHERE in the command rather than at the start, deliberately and for the
    # same reason `hook_guard` does it: this is a redirect, so a command that
    # already reaches for the right task is not the behaviour being corrected.
    if re.search(r"\bmise\s+run\s+kb-", command):
        return None
    if not _HAND_GATE.search(command):
        return None
    if _INTROSPECTION.search(command):
        return None
    return _REASON
