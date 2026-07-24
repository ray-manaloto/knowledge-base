"""The broad sweep — `mise outdated` for every tool NOT deep-tracked.

The deep engine (steps 1-6) gives a handful of tools full due-diligence. But a
repo pins dozens more, and Ray wants the daily signal to keep covering them
(decided 2026-07-24): deep due-diligence on the fast-movers, a broad
`mise outdated --bump` table on the rest, merged into one report.

This is the ONE currency implementation (D2/G4): dotfiles' old `tool_currency.py`
rendered exactly this table and is deleted; its logic is absorbed here so both
repos share it. The broad table is a SIGNAL (what moved), not judgment — the deep
engine and the skill own judgment.

`--bump` is mandatory: every pin in these repos is EXACT, so the range that
"matches the current config" IS the pin and bare `mise outdated` can never report
anything (control-armed 2026-07-20: it said "up to date" while graphify sat at
0.9.20 vs PyPI 0.9.22). `--bump` compares the pin against latest.
"""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

from kb_setup.currency import config

if TYPE_CHECKING:
    from pathlib import Path

_OUTDATED_TIMEOUT_S = 300.0
_REGISTRY_URL = "https://mise.jdx.dev/registry.html"


def release_link(tool_key: str) -> str:
    """Best-effort release-notes URL for a mise tool key.

    Backend-prefixed keys encode their source; short registry names fall back to
    the mise registry page (which links each tool's homepage). Absorbed verbatim
    from dotfiles' `tool_currency.py` so the one implementation keeps its
    behaviour.
    """
    backend, _, rest = tool_key.partition(":")
    if backend in ("github", "aqua", "ubi") and "/" in rest:
        return f"https://github.com/{rest}/releases"
    if backend == "npm":
        return f"https://www.npmjs.com/package/{rest}?activeTab=versions"
    if backend in ("pipx", "uvx"):
        return f"https://pypi.org/project/{rest.partition('[')[0]}/#history"
    if backend == "cargo":
        return f"https://crates.io/crates/{rest}/versions"
    return _REGISTRY_URL


def mise_outdated(repo_root: Path) -> tuple[dict[str, dict[str, str]], str]:
    """`mise outdated --bump --json` for `repo_root`, as (mapping, error).

    `--local` is NOT passed: unlike a workstation, these repos want the merged
    project config (root + conf.d), which is what a bare project-scoped run reads.
    Runs with cwd=repo_root so the project's mise.toml is the one consulted.
    """
    try:
        res = subprocess.run(
            ["mise", "outdated", "--bump", "--json"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=_OUTDATED_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {}, f"mise outdated failed: {e}"
    if res.returncode != 0:
        return {}, res.stderr.strip() or "mise outdated failed"
    try:
        data = json.loads(res.stdout or "{}")
    except json.JSONDecodeError as e:
        return {}, f"mise outdated returned non-JSON: {e}"
    return (data, "") if isinstance(data, dict) else ({}, "mise outdated returned a non-object")


def render_broad(outdated: dict[str, dict[str, str]], *, exclude: set[str]) -> str:
    """Markdown table of outdated tools, minus the ones the deep engine tracks.

    Excluding the deep-tracked keys is the whole point of merging here rather than
    running two disjoint reports: a tool must not appear in BOTH the deep section
    (with a verdict) and the broad table (as a bare row), which would read as two
    unrelated findings for one tool.
    """
    rows = {k: v for k, v in outdated.items() if k not in exclude}
    if not rows:
        return "_No other pinned tool has upstream movement._"
    lines = [
        "| tool | current | latest | release notes |",
        "|---|---|---|---|",
    ]
    for key in sorted(rows):
        info = rows[key]
        current = info.get("current") or info.get("requested") or "?"
        latest = info.get("latest") or info.get("bump") or "?"
        lines.append(f"| `{key}` | {current} | {latest} | {release_link(key)} |")
    return "\n".join(lines)


def broad_section(repo_root: Path, *, exclude: set[str]) -> str:
    """The broad sweep as a self-contained markdown section (heading + body)."""
    outdated, err = mise_outdated(repo_root)
    heading = "## Broad sweep — other pinned tools (`mise outdated`)"
    if err:
        # A probe failure is NOT "nothing moved" — say so, or a broken mise reads
        # as an all-clear (`probes-need-a-control-arm.md`).
        return f"{heading}\n\n_Could not run the broad sweep: {err}_"
    return f"{heading}\n\n{render_broad(outdated, exclude=exclude)}"


def deep_tracked_keys(repo_root: Path) -> set[str]:
    """The mise keys the deep engine owns — excluded from the broad table."""
    return {spec.mise_key for spec in config.load(repo_root)}
