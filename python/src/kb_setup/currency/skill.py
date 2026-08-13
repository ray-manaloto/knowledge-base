# Copyright (c) 2026 Raymond Manaloto
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

## The generated tree is not purely generated (`ADDENDA`)

The installer rewrites its whole tree, so anything this repo hand-added to it is
destroyed on every refresh — silently, because the `git diff` reads as a routine
regeneration. That is not hypothetical: PR #190 hand-added a paragraph to
`.claude/skills/graphify/references/query.md` recording that 0.9.34's `path`
became direction-respecting (the fix for a cold-lane P2, and something upstream's
own skill still does not carry), and a refresh ate it on 2026-08-06.

`ADDENDA` re-applies each local addition after the installer runs, matched on a
literal ANCHOR rather than a line number — upstream reflows this tree freely, and
a line number would silently target the wrong place, which is worse than not
applying at all. A missing anchor is REPORTED as a lost addendum rather than
skipped: it means upstream moved the section the note annotates, which is exactly
when a human must look.

## What it deliberately does NOT do

It does not decide whether a refresh is warranted — the caller does, on the
version having moved. It does not touch `.graphify_version` either; the installer
writes that itself. Treat a stamp lag as a prompt to look, never as evidence of
content drift: at 0.9.31 -> 0.9.32 the stamp lagged while every shipped
`references/*.md` was byte-identical and `install.py` had zero changed lines.
(That stamp is TRACKED here since 2026-08-06 — the skill files it stamps are
committed, so it is the only record of which version generated them.)

And it does **not** gate on the running binary matching the pin, though the
standalone `kb-setup skill-refresh` task does. The difference is the caller:
`currency.apply` writes the NEW pin and then calls this, so at that moment the
resolved binary legitimately disagrees with the pin and a gate here would refuse
every bump it exists to serve. A deliberate refresh has no such excuse, so the
gate lives at that entry point instead.
"""

from __future__ import annotations

import hashlib
import re
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
_REPAIR = (".claude/settings.json", "CLAUDE.md", ".claude/CLAUDE.md")

#: The ROOT `CLAUDE.md` is in that list because the installer rewrites it too —
#: measured, it strips the blank line after `Rules:` in the graphify block, which
#: rumdl then fails on. Found only by running the real installer: the unit tests
#: use a fake one, so they could never have surfaced it.
#:
#: `.claude/CLAUDE.md` was MISSING until 2026-08-06 (cold lane on 5204e57, F9),
#: and the pathspec `CLAUDE.md` does not match it. The installer writes both —
#: `install.py:263` and `:629` target `.claude/CLAUDE.md`, `:1708` the root one —
#: and this repo's `.claude/CLAUDE.md` is hand-authored and sits at its
#: `md_size_budget`, so an installer append there breaks a gate rather than
#: merely churning bytes. It has not fired yet only because the append is
#: marker-idempotent (`_CLAUDE_MD_MARKER = "## graphify"`, `install.py:683`); it
#: fires the first time upstream edits that block's content.

_TIMEOUT = 300

#: Written by the installer with `write_text(__version__)` — no trailing newline
#: (`install.py:229`). Harmless while the file was gitignored; since it became
#: TRACKED it fails hk's `newlines` builtin, which does not exclude the skill
#: tree. Normalised HERE rather than left to a caller's `mise run fmt`, because
#: only one of the two callers runs one: `currency.apply` commits what this
#: returns without formatting, so a plain auto-applied bump produced a
#: lint-failing commit (cold lane on 5204e57, F3).
_STAMP_SUFFIX = ".graphify_version"


def transaction_paths(repo_root: Path, spec: ToolSpec) -> tuple[Path, ...]:
    """Every repository path a declared installer may mutate or repair."""
    paths = [repo_root / path for path in _REPAIR]
    if spec.skill_dir:
        paths.append(repo_root / spec.skill_dir)
    return tuple(dict.fromkeys(paths))


@dataclass(frozen=True)
class Addendum:
    """One local paragraph re-applied to a generated skill file after install.

    `text` is inserted directly after the first literal occurrence of `anchor`.
    Both are matched literally, and `path` is repo-relative.
    """

    path: str
    anchor: str
    text: str


#: Local additions to a generated skill tree, keyed by the tool's `skill_dir` so
#: this module stays generic over `ToolSpec` — a second tool with a project skill
#: adds its own key and needs no code change.
#:
#: Keep each list short. Every entry is a piece of upstream's file this repo has
#: taken responsibility for, and an entry upstream later adopts should be DELETED
#: rather than left in place: `_apply_addenda` is idempotent so it would not
#: double the text, but a dead entry still fails the day its anchor moves.
ADDENDA: dict[str, tuple[Addendum, ...]] = {
    ".claude/skills/graphify": (
        Addendum(
            path=".claude/skills/graphify/references/query.md",
            anchor='graphify path "NODE_A" "NODE_B"\n```\n',
            text=(
                "\nSince graphify 0.9.34 (#2487), `path` respects edge DIRECTION by default and\n"
                "says so when no directed path exists — pass `--undirected` to search ignoring\n"
                "direction. Before 0.9.34 it always searched an undirected view and could\n"
                "silently return a path that traverses edges backwards, so the same query can\n"
                "legitimately answer differently across that version boundary. The inline\n"
                "fallback below inherits whatever the file's own `directed` flag yields from\n"
                "`node_link_graph`, which is not necessarily the CLI's behaviour on the same\n"
                "graph — prefer the CLI when it is installed.\n"
            ),
        ),
        Addendum(
            path=".claude/skills/graphify/SKILL.md",
            anchor="### Step 5 - Label communities\n",
            text=(
                "\n> **DO NOT RUN STEP 5 IN THIS REPO — use `mise run kb-label`.** Two reasons,\n"
                "> both verified against the 0.9.34 installer template rather than assumed:\n"
                ">\n"
                "> 1. Its block writes `GRAPH_REPORT.md` and `.graphify_labels.json` BEFORE\n"
                ">    attempting the `graph.json` export, and its final\n"
                ">    `print('Report updated with community labels')` sits at indent 0 — so a\n"
                ">    REFUSED export (the #479 shrink guard) prints an error and then reports\n"
                ">    success, exiting 0 with two sidecars describing a graph that was never\n"
                ">    written. Step 4 has the correct shape twenty lines earlier and its own\n"
                ">    comment names the upstream issue this reintroduces (#1392).\n"
                "> 2. It writes `graph.json` through graphify's bundled interpreter, which\n"
                ">    bypasses the pinned-version gate every `kb-setup` graph writer pays and\n"
                ">    is exactly what `kb_setup.hook_guard` denies.\n"
                ">\n"
                "> `mise run kb-label` has neither problem and needs no LLM. This note is an\n"
                "> ADDENDUM, not a hand-edit: the tree is regenerated, so editing the block\n"
                "> itself would be eaten by the next refresh. (Cold lane on 5204e57, F1/F2.)\n"
            ),
        ),
    ),
}


@dataclass(frozen=True)
class SkillResult:
    """What the refresh did — reported, never silently absorbed."""

    ran: bool
    changed: tuple[str, ...] = ()
    repaired: tuple[str, ...] = ()
    #: The unified diff of what `_repair` reverted, captured BEFORE the revert.
    #: Empty when nothing was reverted. A caller that shows only `repaired` names
    #: the files and loses the bytes, which is how a legitimately-added upstream
    #: hook would be discarded without trace.
    repair_delta: str = ""
    #: Local addenda re-applied into the regenerated tree.
    addenda: tuple[str, ...] = ()
    #: Addenda that could NOT be re-applied — the file or its anchor is gone, so
    #: this repo's local note is missing from the tree right now. Kept separate
    #: from `unrepaired` because the remedy differs: that one is a `git checkout`
    #: away, this one needs someone to re-anchor or retire the note.
    lost_addenda: tuple[str, ...] = ()
    #: Paths the installer dirtied that are STILL dirty after the repair ran.
    #: Non-empty means damage is sitting in the working tree right now, and the
    #: only honest thing to do is name the files — a caller who commits after
    #: reading a cheerful note picks the damage up with the bump.
    unrepaired: tuple[str, ...] = ()
    process_warning: bool = False
    diagnostic_bytes: int = 0
    diagnostic_sha256: str = ""
    note: str = ""


def _process_diagnostics(stdout: str, stderr: str) -> tuple[bool, int, str]:
    """Return warning presence plus body-free diagnostics for a child process."""
    raw = stdout.encode() + b"\0" + stderr.encode()
    warning = bool(stderr) or re.search(r"\bwarn(?:ing)?\b", stdout, re.IGNORECASE) is not None
    return warning, len(raw) - 1, hashlib.sha256(raw).hexdigest()


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=_TIMEOUT,
    )


def _repair(repo_root: Path) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    """Revert what the installer dirtied in `_REPAIR`; return (reverted, still-dirty, delta).

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

    **The delta is CAPTURED before the revert, and returned.** Reverting with only
    the filename recorded makes this a second way to go stale: a future graphify
    that legitimately adds a hook would have it discarded with nothing to read.
    The capture is `git diff` against the index over exactly the dirty paths, run
    while the damage is still on disk — after the checkout there is nothing left
    to diff. An untracked path contributes no diff and that is correct: there is
    no committed version for it to differ FROM, and its whole content is already
    named by `reverted`. (Cold lane on 5204e57, F8: `mise.toml` promised this
    report and no code emitted one.)
    """
    dirty = _dirty(repo_root, _REPAIR)
    if not dirty:
        return (), (), ""
    # The capture's rc is READ. `_git` runs with `check=False`, so a failed
    # `git diff` returns an empty stdout that is indistinguishable from "nothing
    # to show" — and the checkout on the next line then destroys the only copy
    # of what it would have shown. Reporting the failure keeps the two states
    # apart, which is this repo's DRIFT/SKIP/OK discipline applied to a delta
    # (cold lane round 2 on ea6ab63).
    shown = _git(repo_root, "diff", "--", *dirty)
    delta = (
        shown.stdout
        if shown.returncode == 0
        else (
            f"[skill] COULD NOT CAPTURE the reverted delta (git diff rc="
            f"{shown.returncode}): {(shown.stderr or '').strip()[:200]}\n"
            f"[skill] the revert below still happened; only its diff is unavailable.\n"
        )
    )
    _git(repo_root, "checkout", "--", *dirty)
    still = _dirty(repo_root, _REPAIR)
    for path in still:
        _git(repo_root, "checkout", "--", path)
    remaining = _dirty(repo_root, _REPAIR)
    return tuple(p for p in dirty if p not in remaining), remaining, delta


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


def _normalise_stamp(repo_root: Path, skill_dir: str) -> None:
    """Give the installer's version stamp the trailing newline hk requires.

    `install.py:229` writes it with `write_text(__version__)` — no newline. That
    was invisible while the file was gitignored; since it became TRACKED
    (2026-08-06) hk's `newlines` builtin fails on it, and `.claude/skills/**` is
    in neither of hk's exclude lists.

    Done here rather than left to `mise run fmt`, because only ONE of this
    module's two callers runs a formatter: `currency.apply` commits what this
    returns as-is, so an ordinary auto-applied graphify bump produced a
    lint-failing commit (cold lane on 5204e57, F3). Fixing it at the writer
    covers both callers and cannot drift apart the way two fixes would.
    """
    stamp = repo_root / skill_dir / _STAMP_SUFFIX
    try:
        text = stamp.read_text(encoding="utf-8")
    except OSError:
        return  # No stamp is not this function's problem to report.
    if text and not text.endswith("\n"):
        stamp.write_text(text + "\n", encoding="utf-8")


def _apply_addenda(repo_root: Path, skill_dir: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Re-apply this repo's local notes into the regenerated tree.

    Returns `(applied, lost)`. Idempotent — an addendum already present is left
    alone, so refreshing twice does not stack the paragraph.
    """
    applied: list[str] = []
    lost: list[str] = []
    for add in ADDENDA.get(skill_dir, ()):
        path = repo_root / add.path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            lost.append(f"{add.path} (file absent after install)")
            continue
        if add.text in text:
            continue
        if add.anchor not in text:
            lost.append(f"{add.path} (anchor moved — re-anchor it in currency.skill.ADDENDA)")
            continue
        path.write_text(text.replace(add.anchor, add.anchor + add.text, 1), encoding="utf-8")
        applied.append(add.path)
    return tuple(applied), tuple(lost)


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
    process_warning, diagnostic_bytes, diagnostic_sha256 = _process_diagnostics(
        proc.stdout, proc.stderr
    )
    if proc.returncode != 0:
        # REPAIR ON THE FAILURE PATH TOO. The pre-flight above proved the tree
        # started clean, so anything dirty in `_REPAIR` now was written by this
        # run — a half-finished installer (disk full, permission error, its own
        # assertion) leaves exactly the machine-specific absolute path in
        # settings.json that this module exists to prevent. Returning early with
        # only "installer failed" left that sitting in the working tree, unnamed,
        # for whoever commits the bump next.
        reverted, still, delta = _repair(repo_root)
        # AND THE STAMP, for the third time on this path. An installer that
        # writes the stamp and then fails later leaves a tracked, newline-less
        # file behind while `currency.apply` still lands the pin — so the bump
        # commit fails hk's `newlines` for a reason nobody would connect to a
        # FAILED install (cold lane round 2 on ea6ab63).
        _normalise_stamp(repo_root, spec.skill_dir)
        # ADDENDA ON THE FAILURE PATH TOO, and for the same reason as the repair
        # above. A half-finished installer regenerates the skill tree and THEN
        # exits nonzero, so the local paragraph is already gone — and running
        # only on the success path left `lost_addenda` at its empty default, so
        # the one loss this whole mechanism exists to catch survived on the one
        # path it did not cover (cold lane on 5204e57, F5).
        f_applied, f_lost = _apply_addenda(repo_root, spec.skill_dir)
        return SkillResult(
            ran=False,
            repaired=reverted,
            unrepaired=still,
            repair_delta=delta,
            addenda=f_applied,
            lost_addenda=f_lost,
            process_warning=process_warning,
            diagnostic_bytes=diagnostic_bytes,
            diagnostic_sha256=diagnostic_sha256,
            note=(
                f"installer failed (rc={proc.returncode}; bytes={diagnostic_bytes}; "
                f"sha256={diagnostic_sha256})"
                + (f". Reverted {', '.join(reverted)}" if reverted else "")
                + (f". ⚠ STILL DIRTY, fix before committing: {', '.join(still)}" if still else "")
                + (f". ⚠ LOCAL ADDENDUM LOST: {', '.join(f_lost)}" if f_lost else "")
            ),
        )

    repaired, unrepaired, delta = _repair(repo_root)
    _clear_backups(repo_root, skill)
    _normalise_stamp(repo_root, spec.skill_dir)
    # AFTER the repair and BEFORE reading `changed`: the addenda are edits to the
    # skill tree, which `_repair` never touches, and they must show up in the
    # changed set or a caller reading it would not know the tree moved.
    applied, lost = _apply_addenda(repo_root, spec.skill_dir)

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
        repair_delta=delta,
        addenda=applied,
        lost_addenda=lost,
        process_warning=process_warning,
        diagnostic_bytes=diagnostic_bytes,
        diagnostic_sha256=diagnostic_sha256,
        note=(
            f"skill refreshed; {len(changed)} file(s) changed"
            + (f"; re-applied local addenda to {', '.join(applied)}" if applied else "")
            + (
                f". ⚠ LOCAL ADDENDUM LOST: {', '.join(lost)} — this repo's note is NOT in "
                f"the tree; the installer wiped it and it could not be put back"
                if lost
                else ""
            )
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
