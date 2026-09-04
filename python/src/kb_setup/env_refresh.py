# Copyright (c) 2026 Raymond Manaloto
"""Write mise's shim directory to the head of ``CLAUDE_ENV_FILE``'s ``PATH``.

Ray, 2026-09-03 (#702): *"there should be a way to do that without having to
restart the terminal session"*.

The problem this exists for
===========================

Every Bash tool call is a fresh ``zsh -c`` that re-sources
``~/.claude/shell-snapshots/snapshot-zsh-<id>.sh``, whose **final line is a
literal** ``export PATH='…'`` captured once when the session started. So a
``mise use`` that installs a new version mid-session cannot reach the Bash tool:
the snapshot re-asserts the old install directory before every command, and
nothing recomputes it. Measured on #702's session — ``codex --version`` reported
``0.152.0`` while ``mise exec -- codex --version`` reported ``0.153.1`` under a
``0.153.1`` pin.

The freeze is **tool-scoped, not machine-scoped**: a subagent spawned through a
different path does not inherit the frozen ``PATH`` and so *cannot see the
condition*. A cold review lane on ``217b3537`` honestly reported "no such skew
today" while the main session's own Bash tool was skewed at that same moment.
Do not ask a subagent to verify a claim about this.

Why the shim directory rather than a regenerated ``mise env``
=============================================================

#702's body proposed writing a fresh ``mise env`` into ``CLAUDE_ENV_FILE`` on
every ``FileChanged``. **A later codex pass replaced that, and the issue says
so.** A mise shim is a symlink to the ``mise`` binary itself, never to a
version-named path — verified here, ``<shims>/codex -> ~/.local/bin/mise`` —
so it resolves the *current* version at exec time. That makes one line correct
for every future bump:

* nothing to regenerate, so the trigger can be ``SessionStart`` alone;
* ``PATH`` does not grow on repeated writes;
* no environment **values** are copied into a file, secret or otherwise, which
  a ``mise env`` dump cannot promise.

``shims_on_path`` is already ``true`` on this host — the shims directory is not
missing from ``PATH``, it sits *behind* the frozen install directory. This
module changes precedence, not presence, so it introduces no new
shim-auto-install surface that was not already reachable.

Why the directory is asked for rather than hardcoded
====================================================

``mise doctor --json`` reports it at ``.dirs.shims`` (measured 0.14 s, three
runs, so it is affordable in a SessionStart hook). ``use-tool-builtins.md``:
prefer the tool's own answer over a homegrown one. A hardcoded
``~/.local/share/mise/shims`` is wrong under ``MISE_DATA_DIR`` and wrong on any
host that moved it, and it would fail *silently* — writing a ``PATH`` entry that
resolves nothing looks exactly like a hook that worked.

The arm that bought this, and what it measured
==============================================

That a ``PATH`` written to ``CLAUDE_ENV_FILE`` actually OVERRIDES the snapshot's
final ``export PATH`` was inferred, never measured, and the whole recommendation
rested on it. (#702 puts that line at 1825 of 1825. Re-derived here on a
DIFFERENT session's snapshot rather than carried over: 1825 lines, the last
beginning ``export PATH='``, and exactly one line in the file matching
``^export PATH=`` — so the count is a coincidence of a stable environment, and
the load-bearing fact is *last line, sole assignment*, not the number.)
Armed three ways on 2026-09-04, reading the result in a LATER Bash call:

* marker :data:`SENTINEL_VAR` absent -> the hook never ran -> conclude nothing;
* marker set but the sentinel missing from ``PATH`` -> the snapshot won -> reject;
* sentinel present -> **ship**.

Result: ``KB_ENV_PROBE=armed`` with ``PATH`` position 1 = the shims directory and
position 2 = the sentinel. The env file runs AFTER the snapshot re-source, so it
wins. End to end, ``command -v codex`` moved from
``…/installs/npm-openai-codex/0.153.1/bin/codex`` to ``<shims>/codex`` in the
same session, with no restart.

**One trigger did not fire, and that is recorded rather than smoothed over.**
The same hook wired as ``FileChanged`` on a root file, then appended to with the
Bash tool, did NOT run — marker absent, sentinel absent. Wired as ``CwdChanged``
and fired with a ``cd``, it ran immediately. The likely reason is that Claude
Code "starts the watcher only when something names a file to watch"
(``hooks.md``, FileChanged) and a group added mid-session does not start one, but
that cause is UNVERIFIED. What is measured is only that FileChanged did not fire
here. The ship target does not depend on it: with a version-independent shim
there is nothing for a file change to react to.

**Known limit.** A tool that has never been installed has no shim, so this line
cannot resolve it until mise creates one. It fixes a *version* moving under an
existing shim, which is #702's case, not a brand-new tool's first install.

Exit codes, and why an absent variable is not a pass
====================================================

``CLAUDE_ENV_FILE`` is exposed **only** to ``SessionStart``, ``Setup``,
``CwdChanged`` and ``FileChanged`` hooks (``hooks.md:1219``). Wiring this module
to any other event leaves the variable unset. That returns
:attr:`~kb_setup.result.Rc.NOT_RUN`, never ``OK``: a hook that never asked the
question is not a pass (`probes-need-a-control-arm.md`), and the whole failure
mode here is that *a hook which writes a file nothing reads looks identical to a
hook that works*.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kb_setup import events
from kb_setup.result import Rc

ENV_FILE_VAR = "CLAUDE_ENV_FILE"
"""The variable Claude Code exports to a hook that may persist environment."""

MARKER = "# kb_setup.env_refresh: mise shims first"
"""Idempotence marker.

``hooks.md:1185`` says to APPEND with ``>>`` so other hooks' variables survive,
which means this module can be invoked repeatedly against one file. Skipping on
this marker is what keeps ``PATH`` from growing a duplicate entry per fire —
harmless in effect, unbounded in size, and the exact thing a ``CwdChanged`` or
``FileChanged`` trigger would do dozens of times a session.
"""

SENTINEL_DIR = "/__claude_env_probe__"
"""A directory that cannot exist, written FIRST under ``--sentinel``.

It exists to be *looked for* in a later Bash call. Its absence from ``PATH``
while :data:`SENTINEL_VAR` is set is the only evidence that separates "the
snapshot won" from "the hook never fired".
"""

SENTINEL_VAR = "KB_ENV_PROBE"
"""Set alongside :data:`SENTINEL_DIR` so the third arm is distinguishable.

Without it, a missing sentinel means either *the write lost to the snapshot* or
*the hook never ran*, and those demand opposite responses.
"""


_Runner = Callable[..., Any]
"""What :func:`shims_dir` needs from ``subprocess.run``, kept deliberately loose.

`do-not.md` #9 rejects every inline type-checker suppression under
``python/src/``, so this alias exists to make the seam typed without one. A
precise ``Protocol`` was tried first and rejected: ``subprocess.run`` is a
four-way overload and no single ``__call__`` shape is assignable from it, so the
precise version bought its accuracy back in exactly the suppression it was meant
to avoid.

The wording here is deliberate too. ``no_lint_skip`` matches the suppression
markers as LITERAL TEXT and does not exempt this file the way it exempts its own
implementation, so naming one in prose fails the gate — which it did, once,
before this sentence replaced it.
"""


def shims_dir(run: _Runner | None = None) -> Path | None:
    """Ask mise where its shims live; ``None`` when it cannot say.

    ``run`` is injectable so a test can drive both the answer and the failure
    without a real mise on ``PATH``.
    """
    runner: _Runner = subprocess.run if run is None else run
    try:
        proc = runner(
            ["mise", "doctor", "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if proc.returncode != 0 and not proc.stdout:
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError, TypeError:
        return None
    raw = (payload or {}).get("dirs", {}).get("shims")
    return Path(raw) if isinstance(raw, str) and raw else None


def lines_for(shims: Path, *, sentinel: bool = False) -> list[str]:
    """The exact lines appended to the env file, marker first.

    Each ``export PATH="X:$PATH"`` PREPENDS, so the last line written ends up
    first in ``PATH``. The sentinel is therefore emitted BEFORE the shims entry
    on purpose: it settles at position 2 with the shims directory at position 1,
    which is the ordering the ship wants and still leaves the sentinel readable.
    Measured that way — ``1 <shims>``, ``2 /__claude_env_probe__``.
    """
    out = [MARKER]
    if sentinel:
        out.append(f'export {SENTINEL_VAR}="armed"')
        out.append(f'export PATH="{SENTINEL_DIR}:$PATH"')
    out.append(f'export PATH="{shims}:$PATH"')
    return out


def apply(env: dict[str, str], *, sentinel: bool = False, run: _Runner | None = None) -> int:
    """Append the shims line to ``CLAUDE_ENV_FILE``. Idempotent on :data:`MARKER`."""
    target = env.get(ENV_FILE_VAR)
    if not target:
        events.warn(
            "env-refresh.no-env-file",
            f"{ENV_FILE_VAR} is unset — this hook event cannot persist environment "
            "(hooks.md:1219 allows only SessionStart/Setup/CwdChanged/FileChanged). "
            "Nothing written; this is NOT a pass.",
        )
        return Rc.NOT_RUN
    shims = shims_dir(run=run)
    if shims is None:
        events.fail(
            "env-refresh.no-shims-dir",
            "mise could not report .dirs.shims — refusing to guess a path, because "
            "a PATH entry that resolves nothing is indistinguishable from success.",
        )
        return Rc.NOT_RUN
    path = Path(target)
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if MARKER in existing:
            events.say(
                "env-refresh.already",
                f"{path} already carries the shims entry — nothing appended.",
            )
            return Rc.OK
        body = "\n".join(lines_for(shims, sentinel=sentinel)) + "\n"
        prefix = "" if existing.endswith("\n") or not existing else "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(prefix + body)
    except OSError as exc:
        # Cold review P2 on b5404f11: `shims_dir` above catches OSError and this
        # path did not, so an unwritable target — a missing parent directory, a
        # read-only file — left the hook dying on a raw traceback at exit 1.
        # `Rc.NOT_RUN` is the honest code for it, and it is the same code the
        # unset-variable arm returns for the same reason: nothing was written,
        # so nothing may report success.
        events.fail(
            "env-refresh.unwritable",
            f"could not write {path}: {exc}. Nothing written; this is NOT a pass.",
        )
        return Rc.NOT_RUN
    events.say(
        "env-refresh.wrote",
        f"appended mise shims ({shims}) to the head of PATH in {path}"
        + (f" plus the {SENTINEL_DIR} sentinel" if sentinel else ""),
    )
    return Rc.OK


def main(rest: list[str], env: dict[str, str] | None = None) -> int:
    """CLI entry: ``uv run kb-setup env-refresh [--sentinel]``."""
    unknown = [arg for arg in rest if arg != "--sentinel"]
    if unknown:
        events.fail("env-refresh.bad-request", f"unknown argument(s): {unknown}")
        return Rc.BAD_REQUEST
    return apply(dict(os.environ if env is None else env), sentinel="--sentinel" in rest)
