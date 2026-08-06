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

`.claude/CLAUDE.md` is protected for the same reason and is NOT in #133's list:
the installer also writes a `# graphify` block there, that file is hand-authored
(issue-tracker pointer, cross-vendor orchestration doctrine) and sits at its
size budget, so an installer append would break `md_size_budget` rather than
merely churn.
"""

from __future__ import annotations

import difflib
import subprocess
from pathlib import Path

from kb_setup import atomic, graphify_env

#: Files the installer writes that this repo owns and the installer does not.
#: Relative to the repo root. Order is display order in the report.
PROTECTED = (".claude/settings.json", ".claude/CLAUDE.md")

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


def refresh(repo_root: Path | None = None) -> int:
    """Run the generator, restore what it must not own, report; return an rc.

    Returns 0 on success. A non-zero rc is the installer's or the formatter's
    own — this function never invents one, so a caller reading the code knows
    which step failed.
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

    # The generated markdown is upstream's formatting, not ours; without this
    # the next `mise run lint` fails on files this task just wrote.
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
    return 0
