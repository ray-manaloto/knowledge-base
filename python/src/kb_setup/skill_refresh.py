# Copyright (c) 2026 Raymond Manaloto
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

from pathlib import Path
from subprocess import run

from kb_setup import events, graphify_env

# `from subprocess import run` rather than `import subprocess`, so a test
# monkeypatching this module's `run` patches THIS module and not
# `sys.modules["subprocess"]` process-wide. `skill_refresh.subprocess` was the
# stdlib module itself, so the old form replaced `subprocess.run` for every
# other module for the duration — harmless while nothing else in the same test
# needed a real subprocess, and a loaded gun beside `test_currency_skill.py`,
# which runs real `git`. (Cold lane on 5204e57, F12.)

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
        events.say(
            "skill_refresh.no_tool",
            f"[skill-refresh] currency.toml declares no [tool.{_TOOL}] — nothing to refresh",
            tool=_TOOL,
        )
        return 2

    result = skill.refresh(root, spec)
    events.say("skill_refresh.result", f"[skill-refresh] {result.note}", ran=result.ran)
    # The bytes, not just the filenames. Reverting an installer change with only
    # its path recorded is how a future graphify that legitimately adds a hook
    # gets it discarded without trace (cold lane on 5204e57, F8).
    if result.repair_delta:
        events.say(
            "skill_refresh.reverted",
            "[skill-refresh] the installer wanted this, and it was reverted:",
        )
        # `end=""` had no newline of its own because the delta carries them.
        # `emit` always renders one line, so the trailing newline is stripped
        # here rather than the sink learning about `end=` — the sink renders
        # events, and "this string already ends in a newline" is a property of
        # THIS caller's payload, not of event rendering.
        events.say(
            "skill_refresh.repair_delta",
            result.repair_delta.rstrip("\n"),
            delta=result.repair_delta,
        )
    if not result.ran:
        return 1

    # After the addenda, so their bytes are formatted too. This is the
    # print -> subprocess -> print shape that recipe rule 3 could not absorb
    # before the sink existed: the operator must see "fmt" START, because it is
    # the slow step.
    events.say("skill_refresh.fmt", "[skill-refresh] mise run fmt")
    fmt = run(["mise", "run", "fmt"], cwd=root, check=False)
    if fmt.returncode != 0:
        events.say(
            "skill_refresh.fmt_failed",
            f"[skill-refresh] fmt FAILED rc={fmt.returncode} — skill files may not lint",
            rc=fmt.returncode,
        )
        return fmt.returncode

    events.say(
        "skill_refresh.review",
        "[skill-refresh] review `git diff .claude/` before committing",
    )
    # TWO conditions fail an otherwise-successful refresh, and the line above is
    # why both must: it tells the operator to go commit.
    #
    # - `lost_addenda` — the install worked and a local fix is silently gone,
    #   which is what happened the first time this ran.
    # - `unrepaired` — the installer's damage is STILL in the working tree.
    #   `SkillResult` documents that field as "the only honest thing to do is
    #   name the files", and this returned 0 anyway, so the name was printed and
    #   the exit code contradicted it (cold lane on 5204e57, F4).
    return 1 if (result.lost_addenda or result.unrepaired) else 0
