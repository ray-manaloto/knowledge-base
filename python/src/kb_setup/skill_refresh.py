"""`kb-setup skill-refresh` — the standalone entry point to a skill refresh (#133).

**The refresh itself lives in `kb_setup.currency.skill`**, which already did
installer-plus-repair when this was written and is already wired into
`currency.apply`. This module is a task wrapper, not a second implementation:
the first version of it WAS a second implementation, written by reading #133's
"Ask" without first checking whether this repo had already answered it — and the
existing module was more correct on the one detail they disagreed about (it
repairs the ROOT `CLAUDE.md`, which is the file the installer actually writes).

What lives here rather than there, and why:

1. **The pinned-version gate.** Generating the skill from a stale binary produces
   exactly the drift a refresh exists to remove, while looking like a refresh —
   live on this host, where the skill sat at 0.9.32 under a 0.9.34 pin. It cannot
   go in `currency.skill`: `currency.apply` writes the NEW pin and then calls
   that module, so at that moment the resolved binary legitimately disagrees and
   a gate there would refuse every bump. A deliberate refresh has no such excuse.

2. **`mise run fmt`.** The generated markdown carries upstream's formatting, and
   the installer strips the stamp file's trailing newline, so without this the
   next `mise run lint` fails on files this task just wrote. `currency.apply`
   has its own formatting step in its own flow.

3. **Printing.** `currency.skill` returns a `SkillResult` and never prints,
   correctly — it has two callers with different output surfaces.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from kb_setup import graphify_env

#: The tool whose skill this task refreshes. `currency.skill` is generic over
#: `ToolSpec`; this task is not, because the version gate above is graphify's.
_TOOL = "graphify"


def refresh(repo_root: Path | None = None) -> int:
    """Refresh the project-scoped graphify skill; return a process exit code."""
    from kb_setup.currency import config, skill

    root = repo_root or Path.cwd()

    # Refuses (SystemExit) on a mismatch, and prints "could not compare" as
    # itself rather than collapsing it into either answer.
    graphify_env.assert_pinned_graphify(root)

    spec = next((s for s in config.load(root) if s.name == _TOOL), None)
    if spec is None:
        print(f"[skill-refresh] currency.toml declares no [tool.{_TOOL}] — nothing to refresh")
        return 2

    result = skill.refresh(root, spec)
    print(f"[skill-refresh] {result.note}")
    if not result.ran:
        return 1

    # After the addenda, so their bytes are formatted too.
    print("[skill-refresh] mise run fmt")
    fmt = subprocess.run(["mise", "run", "fmt"], cwd=root, check=False)
    if fmt.returncode != 0:
        print(f"[skill-refresh] fmt FAILED rc={fmt.returncode} — skill files may not lint")
        return fmt.returncode

    print("[skill-refresh] review `git diff .claude/` before committing")
    # A lost addendum is the one condition that fails an otherwise-successful
    # refresh: the install worked, so a 0 would send the operator to commit a
    # diff that silently dropped a local fix — which is what happened the first
    # time this ran.
    return 1 if result.lost_addenda else 0
