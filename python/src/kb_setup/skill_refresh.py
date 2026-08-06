"""Regenerate the vendored graphify skill from the PINNED graphify (#133).

`.claude/skills/graphify/**` is **generated**, not authored: `graphify install
--project` writes it. So a version bump leaves it stale until the generator runs
again, and on 2026-08-06 it had been stale across two bumps — the stamp read
`0.9.32` under a `0.9.34` pin.

Copying the files out of `sources/graphify/graphify/skills/claude/` would work
today and is the wrong answer: it substitutes hand-maintained code for a tool
feature that already exists (`use-tool-builtins.md`), and it would drift the
moment upstream changes where or how the skill is assembled. Ray, 2026-08-06:
*"we shouldnt be copying the graphify skill, doesnt graphify generate that?"*

## Why the generator needs a wrapper at all

`graphify install --project` regresses three things in `.claude/settings.json`
every time it runs (#133, observed 0.9.23 -> 0.9.31):

1. both graphify hook commands are rewritten from
   `mise exec -C "${CLAUDE_PROJECT_DIR:-.}" -- graphify …` to an **absolute,
   version-frozen** path under `pipx-graphifyy/<version>/bin/` — machine-
   specific, and it freezes a version into committed config so the hook stops
   following the mise pin;
2. `"timeout": 15` is dropped from both;
3. the trailing newline is stripped, which fails hk's `newlines` step with a
   cause nobody would connect to the installer.

## The restore is reported, never silent

A wrapper that simply overwrote the installer's changes back would be a second
way to go stale: a future graphify that legitimately adds a hook would have it
discarded with no trace. So each protected file is restored to its pre-install
bytes **and the reverted delta is printed as a unified diff**. Accepting an
installer change stays a deliberate human act; losing one silently is not
possible.

`.claude/CLAUDE.md` and the root `CLAUDE.md` are protected for the same reason
and neither is in #133's list. The installer writes a graphify block into
**both** — its own output says so out loud (*"graphify section written to
<repo>/CLAUDE.md"*) — and both are hand-authored and sit at their
`md_size_budget`, so an installer append breaks a gate rather than merely
churning. The root file happened to be rewritten byte-identically on the first
live run; that is idempotence today, not protection.

## The generated tree is not purely generated (`ADDENDA`)

`md-size-budgets.md` calls `.claude/skills/graphify/**` "installer-generated …
and never hand-edited". That was true until PR #190, which hand-added a
paragraph to `references/query.md` recording that 0.9.34's `path` became
direction-respecting — the fix for a cold-lane P2 finding, and something
upstream's own skill still does not document.

**This task's first live run destroyed it.** The installer rewrites the whole
tree, so a hand-patch is silently gone and the `git diff` reads as a routine
regeneration. `ADDENDA` re-applies each local addition after the generator runs
and **fails loudly when its anchor is missing** — an absent anchor means
upstream moved the section the note annotates, which is precisely when a human
must look rather than when a paragraph should quietly vanish.
"""

from __future__ import annotations

import difflib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from kb_setup import atomic, graphify_env

#: Files the installer writes that this repo owns and the installer does not.
#: Relative to the repo root. Order is display order in the report.
PROTECTED = (".claude/settings.json", ".claude/CLAUDE.md", "CLAUDE.md")


@dataclass(frozen=True)
class Addendum:
    """One local paragraph re-applied to a generated skill file after install.

    `anchor` is matched literally and `text` is inserted directly after it. A
    literal anchor rather than a line number on purpose: upstream reflows this
    tree freely, and a line number would silently target the wrong place, which
    is a worse failure than not applying at all.
    """

    path: str
    anchor: str
    text: str


#: Local additions to the GENERATED skill tree, re-applied after every install.
#: Keep this list short — every entry is a piece of upstream's file we have
#: taken responsibility for. An entry that upstream adopts should be DELETED
#: here, not left to double up (`_apply_addenda` is idempotent, so it would
#: not duplicate, but a dead entry still fails the day the anchor moves).
ADDENDA = (
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
)

#: Where the generator drops its stamp. Gitignored until 2026-08-06; tracked
#: since, precisely so a refresh like this one shows up in a diff instead of
#: being a local fact (#133's own "a stamp reading 0.9.23 is a local fact, not
#: a repo fact").
STAMP = Path(".claude/skills/graphify/.graphify_version")


def _read(path: Path) -> str | None:
    """The file's text, or ``None`` when it does not exist.

    ``None`` and ``""`` must stay distinct: an absent file that the installer
    CREATES is a legitimate new artifact to keep, while an existing file it
    rewrites is a regression to revert.
    """
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _diff(name: str, before: str, after: str) -> str:
    """A unified diff of the installer's change, as it would have landed."""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"{name} (kept)",
            tofile=f"{name} (installer wanted)",
        )
    )


def _apply_addenda(root: Path) -> int:
    """Re-apply every `ADDENDA` entry; return 0, or 1 if any anchor is missing.

    Idempotent: an addendum already present is left alone, so a refresh run
    twice does not double the paragraph.
    """
    rc = 0
    for add in ADDENDA:
        path = root / add.path
        text = _read(path)
        if text is None:
            print(f"[skill-refresh] ADDENDUM LOST: {add.path} does not exist after install")
            rc = 1
            continue
        if add.text in text:
            continue
        if add.anchor not in text:
            print(
                f"[skill-refresh] ADDENDUM LOST: {add.path} no longer contains its anchor, "
                f"so this repo's local note was NOT re-applied. Upstream moved the section "
                f"it annotates — re-anchor it in kb_setup.skill_refresh.ADDENDA, or drop it "
                f"if upstream now says the same thing."
            )
            rc = 1
            continue
        atomic.write_text(path, text.replace(add.anchor, add.anchor + add.text, 1))
        print(f"[skill-refresh] {add.path}: re-applied this repo's local addendum")
    return rc


def refresh(repo_root: Path | None = None) -> int:
    """Run the generator, restore what it must not own, report; return an rc.

    Returns 0 on success. A failing installer or formatter propagates ITS OWN
    rc, so a caller reading the code knows which step failed. The one rc this
    function invents is 1 for a lost addendum — see the comment at the return.
    """
    root = repo_root or Path.cwd()

    # Same discipline as the graph writers: generating the skill from a stale
    # binary produces exactly the drift this task exists to remove, and it would
    # do so while LOOKING like a refresh. Refuses (SystemExit) on a mismatch and
    # prints "could not compare" as itself.
    graphify_env.assert_pinned_graphify(root)
    exe = graphify_env.graphify_exe(root)

    before_stamp = _read(root / STAMP)
    before = {name: _read(root / name) for name in PROTECTED}
    preexisting_baks = {
        f"{name}.graphify-bak" for name in PROTECTED if (root / f"{name}.graphify-bak").is_file()
    }

    print(f"[skill-refresh] {exe} install --project")
    proc = subprocess.run(
        [exe, "install", "--project"],
        cwd=root,
        env=graphify_env.clean_env(),
        check=False,
    )
    if proc.returncode != 0:
        print(f"[skill-refresh] installer FAILED rc={proc.returncode} — nothing restored")
        return proc.returncode

    for name in PROTECTED:
        path = root / name
        original = before[name]
        current = _read(path)
        if original is None:
            if current is not None:
                print(f"[skill-refresh] {name}: CREATED by the installer — kept, review it")
            continue
        if current is None:
            atomic.write_text(path, original)
            print(f"[skill-refresh] {name}: DELETED by the installer — restored")
            continue
        if current == original:
            continue
        atomic.write_text(path, original)
        print(f"[skill-refresh] {name}: reverted the installer's rewrite (#133). It wanted:")
        print(_diff(name, original, current), end="")

    # The installer leaves a `<file>.graphify-bak` beside anything it rewrote.
    # Ours is worthless — the restore above already put the real bytes back —
    # and an untracked stray in `.claude/` is exactly the debris a later
    # `git status` reads as an unfinished change. Removed only when the run
    # created it, so a backup that predates this run is never touched.
    for name in PROTECTED:
        rel = f"{name}.graphify-bak"
        bak = root / rel
        if rel not in preexisting_baks and bak.is_file():
            bak.unlink()
            print(f"[skill-refresh] removed the installer's {rel}")

    addenda_rc = _apply_addenda(root)

    # The generated markdown is upstream's formatting, not ours; without this
    # the next `mise run lint` fails on files this task just wrote. Runs after
    # the addenda so their bytes are formatted too.
    print("[skill-refresh] mise run fmt")
    fmt = subprocess.run(["mise", "run", "fmt"], cwd=root, check=False)
    if fmt.returncode != 0:
        print(f"[skill-refresh] fmt FAILED rc={fmt.returncode} — skill files may not lint")
        return fmt.returncode

    after_stamp = _read(root / STAMP)
    print(
        f"[skill-refresh] stamp {(before_stamp or 'ABSENT').strip()} "
        f"-> {(after_stamp or 'ABSENT').strip()} "
        f"(pin {graphify_env.pinned_graphify_version(root) or 'UNKNOWN'})"
    )
    print("[skill-refresh] review `git diff .claude/` before committing")
    # A lost addendum is the ONLY failure this function invents an rc for, and
    # it is worth inventing: the refresh otherwise succeeded, so a 0 here would
    # send the operator to commit a diff that silently dropped a local fix —
    # which is exactly what the first live run did.
    return addenda_rc
