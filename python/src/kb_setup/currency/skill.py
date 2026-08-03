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
    #: Paths the installer dirtied that are STILL dirty after the repair ran.
    #: Non-empty means damage is sitting in the working tree right now, and the
    #: only honest thing to do is name the files — a caller who commits after
    #: reading a cheerful note picks the damage up with the bump.
    unrepaired: tuple[str, ...] = ()
    note: str = ""


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=_TIMEOUT,
    )


def _repair(repo_root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Revert whatever the installer dirtied in `_REPAIR`; return (reverted, still-dirty).

    **The rc is not enough, and neither is one call.** `git checkout -- a b` is
    ATOMIC across its pathspecs: if any one of them is unresolvable from the index
    the whole invocation fails with rc=1 and reverts *nothing*, including the paths
    that would have worked. The previous version knew that — its comment says so —
    and still discarded the `CompletedProcess`, so the one case it did not narrow
    away silently reported success over unreverted damage.

    That case is reachable: `_dirty` reads `git status --porcelain`, whose `??`
    lines are UNTRACKED files. An untracked `_REPAIR` path (a consumer with no
    committed root `CLAUDE.md`, which this module's docstring explicitly invites)
    therefore lands in the checkout argv and poisons the whole batch. Control-armed
    in a scratch repo: `git checkout -- tracked untracked` → rc=1, and `tracked`
    keeps its damaged contents.

    So the batch is attempted first (cheap, and the normal case), then each path is
    retried alone so one bad pathspec cannot veto the rest — and the ANSWER comes
    from re-reading the tree, not from any exit code. What a caller needs to know is
    "is the file clean now", and only `git status` can say that.
    """
    dirty = _dirty(repo_root, _REPAIR)
    if not dirty:
        return (), ()
    _git(repo_root, "checkout", "--", *dirty)
    still = _dirty(repo_root, _REPAIR)
    for path in still:
        _git(repo_root, "checkout", "--", path)
    remaining = _dirty(repo_root, _REPAIR)
    return tuple(p for p in dirty if p not in remaining), remaining


def _clear_backups(repo_root: Path, skill_dir: Path) -> None:
    """Delete the `.graphify-bak` files the installer leaves beside what it rewrote.

    Scoped to where a backup can actually land — the skill directory, plus the
    parent of every `_REPAIR` path — rather than to `skill.parent.parent`, which
    was both too wide and too narrow: for `.claude/skills/graphify` it resolved to
    `.claude/`, sweeping any `*.graphify-bak` anywhere under it while never
    reaching a backup beside the ROOT `CLAUDE.md`, which is in `_REPAIR`.

    The `_REPAIR` parents are globbed NON-recursively, and that is not fastidiousness.
    `CLAUDE.md`'s parent is the repo root, so an `rglob` there would descend into
    `.git/`, `sources/` and `graphify-out/` — **10.7 GB measured on this machine** —
    on every skill refresh, to find a file the installer writes directly beside the
    one it rewrote. Recursion buys nothing here and costs a full-tree walk. Only the
    skill directory keeps `rglob`, because the installer really does write nested
    files there.
    """
    for bak in skill_dir.rglob("*.graphify-bak") if skill_dir.is_dir() else ():
        bak.unlink(missing_ok=True)
    for parent in {(repo_root / p).parent for p in _REPAIR}:
        if parent.is_dir():
            for bak in parent.glob("*.graphify-bak"):
                bak.unlink(missing_ok=True)


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
        # REPAIR ON THE FAILURE PATH TOO. The pre-flight above proved the tree
        # started clean, so anything dirty in `_REPAIR` now was written by this
        # run — a half-finished installer (disk full, permission error, its own
        # assertion) leaves exactly the machine-specific absolute path in
        # settings.json that this module exists to prevent. Returning early with
        # only "installer failed" left that sitting in the working tree, unnamed,
        # for whoever commits the bump next.
        reverted, still = _repair(repo_root)
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return SkillResult(
            ran=False,
            repaired=reverted,
            unrepaired=still,
            note=(
                f"installer failed (rc={proc.returncode}): {' / '.join(tail)}"
                + (f". Reverted {', '.join(reverted)}" if reverted else "")
                + (f". ⚠ STILL DIRTY, fix before committing: {', '.join(still)}" if still else "")
            ),
        )

    repaired, unrepaired = _repair(repo_root)
    _clear_backups(repo_root, skill)

    changed = _dirty(repo_root, (spec.skill_dir,))
    return SkillResult(
        # `ran` describes the INSTALL, which did run. Whether the tree is clean
        # afterwards is `unrepaired`'s job — collapsing the two would make a
        # successful install with unreverted damage indistinguishable from an
        # installer that never started.
        ran=True,
        changed=changed,
        repaired=repaired,
        unrepaired=unrepaired,
        note=(
            f"skill refreshed; {len(changed)} file(s) changed"
            + (
                f"; repaired {', '.join(repaired)} after the installer rewrote it"
                if repaired
                else ""
            )
            + (
                f". ⚠ COULD NOT REVERT {', '.join(unrepaired)} — the installer's changes "
                f"are still in the working tree; inspect them before committing"
                if unrepaired
                else ""
            )
            + ". Review the diff — a version bump often changes NOTHING here "
            "(0.9.31 -> 0.9.32 changed 0 lines), so a large diff is usually formatting."
        ),
    )
