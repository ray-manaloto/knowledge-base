# Copyright (c) 2026 Raymond Manaloto
"""Session-start tripwire: has `.codex/config.toml` been rewritten under us?

Ray's ruling, 2026-09-05 (#710), re-ruled at clear-prep after the defect
recurred: *"Add the check"* — a repo check that fails when `.codex/config.toml`
loses its comment block or its ``[mcp_servers]`` entries, so a daily silent
rewrite becomes a daily loud one. Confirmed 2026-09-08 that he did NOT turn the
upstream sync off, so this guards a live defect that merely went quiet.

The defect
==========

ChatGPT desktop's "Import from another AI app" sync rewrites this repo's
`.codex/config.toml`, destroying every hand-written comment.

**NOT on a daily 03:29 schedule — that claim died on its fourth data point.**
Three occurrences landed within two seconds of the same clock minute, which is
what made a fixed timer so persuasive; the fourth, measured in-session, was at
**22:21:10Z (17:21 local)**. A schedule this repo neither owns nor observes is
not a fact it should assert, so the render no longer states a time.

===========  ===========  ===============  ===================================
event        size         ``[mcp_servers]``  provenance
===========  ===========  ===============  ===================================
2026-09-04   144 -> 27    **removed**      issue #710, not re-measured here
2026-09-05   144 -> 30    kb kept, graphify **added**  issue #710, not re-measured here
2026-09-06   144 -> 30    kb kept, graphify **added**  measured 2026-09-08 in-session
2026-09-08   162 -> 32    kb kept, graphify **added**  measured in-session, 22:21:10Z
===========  ===========  ===============  ===================================

The fourth row is the one with the app's own receipt beside it: the Import
history read "10 imported", itemised ``Settings 1``, ``MCP servers 1``,
``Sessions 8`` — two separate writing categories, which is what refuted
"unticking Settings is enough".

Why this checks the DIFF and not named markers
==============================================

The handoff that queued this work specified asserting that the file still *has*
its ``[mcp_servers.kb]`` **and** ``[mcp_servers.graphify]`` entries. That spec is
wrong twice over, and the table above is why:

1. **The damage is not the same each time.** Only "every comment destroyed" was
   true on all three mornings. ``[mcp_servers.kb]`` was deleted on the 4th and
   survived on the 5th and 6th, so a check asserting its presence would have
   passed on the 4th's damage.
2. **``[mcp_servers.graphify]`` must NOT be here.** ``HEAD`` carries exactly one
   server section, ``kb``; the graphify entry is what the *rewrite adds*, and
   this repo's own comment block records that a project-level ``graphify`` entry
   colliding with the user-global one broke codex outright (*"url is not
   supported for stdio"*). A check demanding its presence would demand the
   outage.

A diff against the committed copy has neither failure mode: it catches every
rewrite, including the fourth morning's, which will damage something nobody
enumerated. The file is tracked, so this costs one ``git diff`` and no
enumeration at all — `use-tool-builtins.md`, applied to git.

The cost Ray accepted for that: it also speaks up when *he* edits the file and
has not committed yet. That is arguably correct — an uncommitted change to this
file is exactly what you want to see at session start either way — and it is why
the message names the recovery command rather than performing it.

Why it never exits non-zero
===========================

`kb-currency-check`'s precedent, for its reason: a session must never be blocked
over this. Ray chose "SessionStart hook, every session" over pairing it with a
ship gate, so this is advisory in the strict sense — it reports and stops.

**That makes the exit code useless as an arm, and the arm is the OUTPUT instead**
(`probes-need-a-control-arm.md`: a check that can only return 0 is not
discriminating on its rc). :func:`status` returns the verdict the tests assert
on; :func:`main` renders it and always reports success to the hook runner.

The third state is kept, never collapsed
========================================

"Could not ask" is not "clean". A missing git, a detached worktree, a
`.codex/config.toml` that is not tracked at all — each yields
:data:`Verdict.UNKNOWN`, which *warns*, because a tripwire that falls silent
when it cannot look is indistinguishable from one that looked and found nothing.
Only :data:`Verdict.CLEAN` is silent.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from kb_setup import events
from kb_setup.result import Rc

WATCHED = Path(".codex/config.toml")
"""The one path this watches.

Ray chose "just `.codex/config.toml`" over adding `.claude/settings.json` or
every tracked config: three measured occurrences here, zero anywhere else, and a
tripwire that fires on files nobody has seen damaged trains you to ignore it.
Adding a second path is one entry once the machinery exists.
"""


_Runner = Callable[..., Any]
"""What :func:`status` needs from ``subprocess.run``, kept deliberately loose.

Same alias and same reason as `env_refresh._Runner`, which recorded the finding:
`do-not.md` #9 rejects every inline type-checker suppression under
``python/src/``, and a precise ``Protocol`` cannot be written here because
``subprocess.run`` is a four-way overload that no single ``__call__`` shape is
assignable from. A precise Protocol was in fact written here first and traded a
`ty` pass for a `PLR0913` failure — the accuracy bought back exactly the
suppression it was meant to avoid.
"""


class Verdict(Enum):
    """What the tripwire found. Three states, deliberately — see the module docstring."""

    CLEAN = "clean"
    """Worktree copy matches the committed one. Silent."""

    CHANGED = "changed"
    """It differs. Warn, and name the recovery."""

    UNKNOWN = "unknown"
    """We could not ask. Warn — this is NOT a pass."""


@dataclass(frozen=True)
class Report:
    """A verdict plus the detail the rendered line needs."""

    verdict: Verdict
    detail: str
    committed_lines: int | None = None
    worktree_lines: int | None = None


def recovery_command(now: datetime | None = None) -> str:
    """The command that both preserves the evidence and restores the good file.

    A plain `git restore` is denied by `kb_setup.destructive_git` on a dirty
    tree; the stash form is the one that works, and it does both jobs in one
    step. This is the command that was run by hand on 2026-09-08 and on the two
    prior occurrences — printing it is the whole difference between a report the
    reader can act on and one they have to re-derive.

    🔴 IT PRESERVES EVIDENCE; IT DOES NOT STOP THE REWRITE, AND ON ITS OWN IT
    INVITES THE NEXT ONE. Read from the importer's own source at
    `sources/codex/codex-rs/external-agent-migration/`: a category writes only
    when the merge finds something ABSENT — `import_config` needs a missing
    value (`service.rs:590-595`), `import_mcp_server_config` a missing server
    NAME (`:633-635`). `HEAD` deliberately carries no `[mcp_servers.graphify]`,
    so every restore re-creates precisely the gap the next import fills, and the
    whole-file `toml::to_string_pretty` + `fs::write`
    (`config_values.rs:77-80`) takes the comments with it again.

    So the caller is told both halves. The durable fixes are outside this
    repository — untick the writing categories, or turn Automatic sync off —
    with an in-repo alternative that is NOT implemented here: `MigrationScope::
    repository` returns `None` if `.codex/config.toml` (or five sibling paths)
    is a symlink (`scope.rs:57-71`), which opts this repo out of those branches.

    The message also no longer claims a time. It said "~03:29", true of the
    2026-09-05 and 09-06 events, and falsified on 2026-09-08 by one at 22:21Z.
    A schedule this repo does not own is not a fact this repo should assert.
    """
    stamp = (now or datetime.now(tz=UTC)).strftime("%Y-%m-%d %H:%M:%SZ")
    return f'git stash push -m "EVIDENCE #710 recurrence {stamp}" -- {WATCHED}'


def _run(
    runner: _Runner, repo_root: Path, args: list[str]
) -> subprocess.CompletedProcess[str] | None:
    """Run a git command in `repo_root`; `None` when it could not run at all."""
    try:
        return runner(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
            cwd=repo_root,
            timeout=30,
        )
    # PEP 758 syntax, and the FORMATTER's own output — not a missing pair of
    # parentheses. Python 3.14 re-allows an unparenthesized `except` tuple
    # (`requires-python = ">=3.14"`, running 3.14.7), and `ruff format` at
    # `target-version = "py314"` normalizes TO this form.
    #
    # Armed both directions rather than argued: `except (OSError, ...)` here was
    # rewritten back to this line by `mise run fmt`, which reported
    # `1 file reformatted`; and this form passes `format --check` at rc=0. Adding
    # parens is not a fix that can be kept — the next `fmt` removes them.
    #
    # Recorded because it reads like the Python-2 `except Type, name:` footgun
    # and was filed as such by the cold review of de258a00 (P2, non-blocking).
    # Nothing flags it because it is what the formatter wants; the note is the
    # only thing that stops the finding recurring.
    except OSError, subprocess.SubprocessError:
        return None


def _line_count(text: str) -> int:
    """Lines in `text`, counting the way `wc -l` does."""
    return text.count("\n")


def status(repo_root: Path, run: _Runner | None = None) -> Report:
    """Compare the worktree's `.codex/config.toml` against the committed copy.

    `run` is injectable so a test can drive CLEAN, CHANGED and UNKNOWN without a
    real repository — which is what makes all three arms reachable.
    """
    runner: _Runner = subprocess.run if run is None else run

    tracked = _run(runner, repo_root, ["ls-files", "--error-unmatch", str(WATCHED)])
    if tracked is None:
        return Report(Verdict.UNKNOWN, "git could not be run at all")
    if tracked.returncode != 0:
        # Not reported as tracked: there is no committed copy to compare
        # against, so the question this module asks cannot be answered here.
        # Never CLEAN.
        #
        # The wording states only what `ls-files --error-unmatch` actually
        # settles. It exits non-zero for TWO different worlds — a repository
        # that does not track the file, and a directory that is no repository at
        # all — and this probe cannot tell them apart without another git call.
        # Saying "in this repository" asserted the first and was wrong in the
        # second (cold review of de258a00, P3), which is the shape a check owes
        # a reader: declare what it cannot see rather than pick a side.
        return Report(
            Verdict.UNKNOWN,
            f"git does not report {WATCHED} as tracked here — either it is "
            "untracked, or this is not a git repository — so there is no "
            "committed copy to compare against",
        )

    diff = _run(runner, repo_root, ["diff", "--quiet", "--", str(WATCHED)])
    if diff is None:
        return Report(Verdict.UNKNOWN, "git diff could not be run")
    if diff.returncode == 0:
        return Report(Verdict.CLEAN, "matches the committed copy")
    if diff.returncode != 1:
        # `git diff --quiet` documents 0 (same) and 1 (differs); anything else
        # is git failing, not an answer. Reporting it as CHANGED would invent a
        # finding, and as CLEAN would hide one.
        return Report(
            Verdict.UNKNOWN,
            f"git diff --quiet exited {diff.returncode}, which is neither "
            "'same' (0) nor 'differs' (1)",
        )

    committed = _run(runner, repo_root, ["show", f"HEAD:{WATCHED}"])
    committed_lines = (
        _line_count(committed.stdout) if committed and committed.returncode == 0 else None
    )
    path = repo_root / WATCHED
    try:
        worktree_lines = _line_count(path.read_text(encoding="utf-8")) if path.exists() else 0
    except OSError:
        worktree_lines = None

    return Report(
        Verdict.CHANGED,
        "differs from the committed copy",
        committed_lines=committed_lines,
        worktree_lines=worktree_lines,
    )


def render(report: Report) -> None:
    """Emit the report. CLEAN says nothing; the other two both warn."""
    if report.verdict is Verdict.CLEAN:
        return

    if report.verdict is Verdict.UNKNOWN:
        events.warn(
            "codex-config.unknown",
            f"[codex-config] could not check {WATCHED}: {report.detail}. "
            "This is NOT a pass — the tripwire did not ask the question.",
            path=str(WATCHED),
        )
        return

    size = ""
    if report.committed_lines is not None and report.worktree_lines is not None:
        size = f" ({report.committed_lines} lines committed, {report.worktree_lines} now)"
    events.warn(
        "codex-config.changed",
        f"[codex-config] {WATCHED} {report.detail}{size}. If you did not edit it, "
        f"this is #710 — ChatGPT desktop's import sync rewrites this file whole and "
        f"destroys every comment. Preserve the evidence:\n"
        f"  {recovery_command()}\n"
        f"  A RESTORE ALONE RE-ARMS THE NEXT REWRITE. The importer writes only "
        f"when something looks MISSING, so putting back a copy that omits what it "
        f"added re-creates the condition it fills. Durable fix: untick the writing "
        f"categories (Settings, MCP servers, Agents, Hooks) or turn Automatic sync "
        f"off in ChatGPT desktop — see docs/research/reports/"
        f"2026-09-08-chatgpt-import-tracker.md.",
        path=str(WATCHED),
        committed_lines=report.committed_lines,
        worktree_lines=report.worktree_lines,
    )


def main(repo_root: Path, rest: list[str] | None = None) -> int:
    """CLI entry: ``uv run kb-setup codex-config-check``.

    Always returns :data:`Rc.OK` — see the module docstring. The verdict lives in
    the emitted event, not the exit code.
    """
    unknown = list(rest or [])
    if unknown:
        events.fail("codex-config.bad-request", f"unknown argument(s): {unknown}")
        return Rc.BAD_REQUEST
    render(status(repo_root))
    return Rc.OK
