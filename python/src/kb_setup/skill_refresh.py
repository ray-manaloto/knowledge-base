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

import os
import shutil
import tempfile
from importlib.metadata import version as distribution_version
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

_CODEX_SKILL_DIR = Path(".agents/skills/graphify")

_CODEX_SKILL = """---
name: graphify
description: Query and maintain this repository's provenance-bound Graphify knowledge graph.
---

# Graphify in knowledge-base

Use the repository's reviewed tasks. Do not invoke a global Graphify binary, the
upstream installer, or a raw source search before attempting the graph.

## Before reading source

1. Run `mise run kb-query -- "<question>"`.
2. Treat missing, stale, corrupt, warning-bearing, or truncated graph evidence as
   unavailable, never as an empty or complete answer.
3. If the graph is unavailable, say so and use source only as the fallback
   authority. Use `mise run kb-build` to reproduce the graph when the task
   authorizes a build.

## Supported operations

- Query: `mise run kb-query -- "<question>"`
- Reverse impact: `mise run kb-affected -- "<symbol>"`
- Rebuild committed inputs: `mise run kb-build`
- Advance one reviewed source: `mise run kb-update -- <source>`
- Verify the installed SDK boundary: `mise run kb-graphify-contract`
- Refresh Graphify skills after a version change: `mise run kb-skill-refresh`

Never hide Graphify stderr, warnings, truncation, source omissions, or receipt
failures. Never treat a queued build or an existing `graphify-out/graph.json` as
proof that the graph is current. Cite graph source locations when an answer uses
graph evidence.

Detailed upstream workflows remain in the generated Claude reference tree under
`.claude/skills/graphify/references/`; repository tasks and rules take precedence.
"""


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sync_codex_skill(repo_root: Path) -> None:
    """Publish the reviewed project Codex skill without installer side effects."""
    target = repo_root / _CODEX_SKILL_DIR
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.with_name(f".{target.name}.backup-{os.getpid()}")
    if backup.exists() or backup.is_symlink():
        raise RuntimeError(f"Codex skill recovery path already exists: {backup}")

    with tempfile.TemporaryDirectory(prefix=".graphify-codex-", dir=target.parent) as raw_stage:
        stage = Path(raw_stage)
        (stage / "SKILL.md").write_text(_CODEX_SKILL, encoding="utf-8")
        version = distribution_version("graphifyy")
        if not version:
            raise RuntimeError("could not read the installed Graphify version")
        (stage / ".graphify_version").write_text(f"{version}\n", encoding="utf-8")

        replaced = target.exists()
        if replaced:
            target.replace(backup)
        try:
            stage.replace(target)
            _fsync_directory(target.parent)
        except BaseException:
            if target.exists():
                shutil.rmtree(target)
            if replaced:
                backup.replace(target)
                _fsync_directory(target.parent)
            raise
        if replaced:
            shutil.rmtree(backup)
            _fsync_directory(target.parent)


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
        # `emit` always renders one line, so ONE trailing newline is removed here
        # rather than the sink learning about `end=` — the sink renders events,
        # and "this string already ends in a newline" is a property of THIS
        # caller's payload, not of event rendering.
        #
        # `removesuffix`, not `rstrip("\n")`: rstrip removes ALL trailing
        # newlines, so a delta ending in a blank line would silently lose it and
        # print differently from the `print(..., end="")` it replaces. The
        # producer is `git diff`, which conventionally emits exactly one — but
        # "conventionally" is not a guarantee, and the precise call costs nothing.
        # (Cold lane raised this as low-confidence and unverified; it is right
        # that the edge case is hard to reach, and right that the loose call had
        # no reason to be loose.)
        events.say(
            "skill_refresh.repair_delta",
            result.repair_delta.removesuffix("\n"),
            delta=result.repair_delta,
        )
    if not result.ran:
        return 1

    try:
        _sync_codex_skill(root)
    except (OSError, RuntimeError) as exc:
        events.say(
            "skill_refresh.codex_failed",
            f"[skill-refresh] Codex bundle FAILED: {type(exc).__name__}",
            error_type=type(exc).__name__,
        )
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
        "[skill-refresh] review `git diff .claude/ .agents/` before committing",
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
