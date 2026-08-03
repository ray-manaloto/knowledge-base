"""Refresh a tool's PROJECT-SCOPED agent skill when its version moves.

The fourth thing a version bump has to carry, alongside the `mise.toml` pin, the
source manifest, and the clone. Ray, 2026-08-03: this belongs *inside* the
workflow that syncs the version — not as a separate task someone has to remember
— because a skill left behind describes a tool we no longer run, and nothing in
the repo records that it drifted.

Nothing here is graphify-specific: the installer argv comes from
:class:`~kb_setup.currency.config.ToolSpec`, so a second tool that ships a
project-scoped skill declares `skill_dir` / `skill_install` and gets the same
treatment.

## Why this cannot be "just run the installer"

Measured 2026-08-03 at 0.9.23 -> 0.9.31. `graphify install --project` is
home-safe — `_refresh_all_version_stamps()`, the only writer of `Path.home()`
stamps, sits on the non-project branch at `install.py:667`, so `--project` never
reaches it (control-armed: `~/.claude/skills/graphify` still absent afterwards,
`~/.claude/CLAUDE.md` still carries no `# graphify` H1).

But it **regresses `.claude/settings.json`** three ways, every time:

1. it rewrites both graphify hook commands from
   `mise exec -C "${CLAUDE_PROJECT_DIR:-.}" -- graphify …` to an ABSOLUTE
   `/Users/<me>/.local/share/mise/installs/pipx-graphifyy/<ver>/bin/graphify` —
   machine-specific, and it freezes the version into committed config so the hook
   stops following the mise pin. That is precisely the defect
   `graphify_env.graphify_exe` exists to prevent, reintroduced into the one file
   `graphify_exe` cannot reach;
2. it drops `"timeout": 15` from both hooks;
3. it strips the trailing newline, which hk's `newlines` step then fails on.

So the refresh is installer + repair, and the repair is not optional. Doing it by
hand is how those three land in a commit unnoticed (#133).

## What it deliberately does NOT do

It does not decide whether a refresh is warranted — the caller does, on the
version having moved. And it does not touch `.graphify_version`; the installer
writes that itself, and the file is gitignored here, so it is a local marker
rather than a tracked fact. Treat a stamp lag as a prompt to look, never as
evidence of content drift: at 0.9.31 -> 0.9.32 the stamp lagged while every
shipped `references/*.md` was byte-identical and `install.py` had zero changed
lines.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup.graphify_env import clean_env

if TYPE_CHECKING:
    from kb_setup.currency.config import ToolSpec

#: Files the installer is known to damage, restored from git after it runs.
#: Named rather than discovered: restoring "whatever the installer touched" would
#: also revert the skill content we ran it FOR.
_REPAIR = (".claude/settings.json", "CLAUDE.md")

#: `CLAUDE.md` is in that list because the installer rewrites it too — measured, it
#: strips the blank line after `Rules:` in the graphify block, which rumdl then
#: fails on. Found only by running the real installer: the unit tests use a fake
#: one, so they could never have surfaced it.

_TIMEOUT = 300


@dataclass(frozen=True)
class SkillResult:
    """What the refresh did — reported, never silently absorbed."""

    ran: bool
    changed: tuple[str, ...] = ()
    repaired: tuple[str, ...] = ()
    note: str = ""


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=_TIMEOUT,
    )


def _dirty(repo_root: Path, paths: tuple[str, ...]) -> tuple[str, ...]:
    out = _git(repo_root, "status", "--porcelain", "--", *paths)
    return tuple(sorted({line[3:] for line in out.stdout.splitlines() if line[3:]}))


def refresh(repo_root: Path, spec: ToolSpec) -> SkillResult:
    """Re-install `spec`'s project-scoped skill, then repair what that breaks.

    Returns rather than raises on installer failure: the caller has already
    written the pin and the manifest, and a skill that did not refresh must not
    roll those back — it must be *reported*, which is what `SkillResult.note` is
    for. A silent success here would be the worst outcome, because the skill is
    exactly the artifact nobody re-reads.
    """
    if not (spec.skill_dir and spec.skill_install):
        return SkillResult(ran=False, note="tool declares no project-scoped skill")

    skill = repo_root / spec.skill_dir
    if not skill.is_dir():
        return SkillResult(ran=False, note=f"{spec.skill_dir} is not present — nothing to refresh")

    # REFUSE on a pre-dirty repair target. The repair below is `git checkout --`,
    # which would discard the user's own uncommitted edit to settings.json along
    # with the installer's damage — and they would have no way to tell which. A
    # refresh is never worth silently eating unrelated work.
    pre = _dirty(repo_root, _REPAIR)
    if pre:
        return SkillResult(
            ran=False,
            note=(
                f"refusing: {', '.join(pre)} has uncommitted changes, and the post-install "
                f"repair is `git checkout --` on exactly those paths — it would discard them. "
                f"Commit or stash first."
            ),
        )

    proc = subprocess.run(
        list(spec.skill_install),
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=_TIMEOUT,
        env=clean_env(),
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return SkillResult(
            ran=False,
            note=f"installer failed (rc={proc.returncode}): {' / '.join(tail)}",
        )

    # Revert only what the installer ACTUALLY dirtied, not the whole `_REPAIR`
    # list. `git checkout -- a b` fails outright when `b` is not in the index, so
    # naming a path this repo happens not to have (a consumer with no root
    # `CLAUDE.md`) aborted the entire repair and left settings.json damaged —
    # caught by the unit test the moment `CLAUDE.md` joined the list.
    repaired = _dirty(repo_root, _REPAIR)
    if repaired:
        _git(repo_root, "checkout", "--", *repaired)
    # The installer also leaves a `.graphify-bak` beside the file it rewrote.
    for bak in skill.parent.parent.rglob("*.graphify-bak"):
        bak.unlink(missing_ok=True)

    changed = _dirty(repo_root, (spec.skill_dir,))
    return SkillResult(
        ran=True,
        changed=changed,
        repaired=repaired,
        note=(
            f"skill refreshed; {len(changed)} file(s) changed"
            + (
                f"; repaired {', '.join(repaired)} after the installer rewrote it"
                if repaired
                else ""
            )
            + ". Review the diff — a version bump often changes NOTHING here "
            "(0.9.31 -> 0.9.32 changed 0 lines), so a large diff is usually formatting."
        ),
    )
