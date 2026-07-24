"""Declarative per-tool currency config (`currency.toml`, one per repo).

One `[tool.<name>]` table per tracked tool. graphify is the pilot; mise, hk, uv,
ruff and ty adopt the same shape with no engine change — which is the whole
reason this is a config file rather than hard-coded checks.

Each repo carries its own config and runs independently (decided 2026-07-23):
there is deliberately NO cross-repo assertion, so this repo never learns
anything about a consumer.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_NAME = "currency.toml"

# mise spells platforms this way (`os = ["macos"]`); match it so a config author
# writing `os` here does not have to remember a second vocabulary.
_PLATFORM_ALIASES = {"darwin": "macos", "win32": "windows"}


def current_platform() -> str:
    """This host in mise's `os` vocabulary (`macos`, `linux`, `windows`)."""
    return _PLATFORM_ALIASES.get(sys.platform, sys.platform)


@dataclass(frozen=True)
class WatchItem:
    """One thing step 4 re-reads every run: an upstream issue, or a local note.

    `kind = "issue"` is fetched from GitHub; `kind = "local"` is a finding of ours
    with no upstream ticket (the `label_communities` schema gap is the founding
    example) and is carried forward untouched so it cannot be quietly forgotten.
    """

    kind: str
    ref: str
    note: str = ""
    repo: str = ""

    @property
    def key(self) -> str:
        """Stable identity used to diff this run's observation against the last."""
        return f"{self.kind}:{self.repo}#{self.ref}" if self.repo else f"{self.kind}:{self.ref}"


@dataclass(frozen=True)
class ToolSpec:
    """Everything the engine needs to assess one tool's currency.

    Only `name` and `mise_key` are required. Every other field switches a check
    ON when present and omits it when absent, so a tool with no source manifest
    or no build artifact simply has fewer checks rather than failing ones.
    """

    name: str
    mise_key: str
    binary: str = ""
    pypi: str = ""
    github: str = ""
    extras: tuple[str, ...] = ()
    # Packages that must actually BE INSTALLED for the declared extras to mean
    # anything. Deliberately author-chosen rather than derived: several of
    # graphify's `[all]` deps auto-skip by PEP 508 marker on Python 3.14
    # (graspologic/leidenalg/igraph → Louvain fallback, an accepted state), so a
    # naive "every extra must import" check would report drift that is not drift.
    extra_probes: tuple[str, ...] = ()
    manifest: str = ""
    artifact: str = ""
    stamp: str = ""
    os: tuple[str, ...] = ()
    watch: tuple[WatchItem, ...] = ()

    def applies_here(self) -> bool:
        """Whether this tool is expected to exist on the current host.

        A macOS-only tool on an Ubuntu CI runner must report NOT-APPLICABLE, never
        FAIL: "cannot check here" and "checked and it is wrong" are different
        answers, and conflating them is the silent-false-negative shape
        `.claude/rules/probes-need-a-control-arm.md` exists to prevent.
        """
        return not self.os or current_platform() in self.os


def _watch_items(raw: object) -> tuple[WatchItem, ...]:
    if not isinstance(raw, list):
        return ()
    items: list[WatchItem] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        fields: dict[str, object] = {str(k): v for k, v in entry.items()}
        ref = fields.get("ref")
        if ref is None:
            continue
        items.append(
            WatchItem(
                kind=str(fields.get("kind", "issue")),
                ref=str(ref),
                note=str(fields.get("note", "")),
                repo=str(fields.get("repo", "")),
            )
        )
    return tuple(items)


def _tool_spec(name: str, table: dict[str, object]) -> ToolSpec:
    if "mise_key" not in table:
        raise ValueError(f"{CONFIG_NAME}: [tool.{name}] is missing required key 'mise_key'")

    def _str(key: str) -> str:
        value = table.get(key, "")
        return str(value) if value else ""

    def _tuple(key: str) -> tuple[str, ...]:
        value = table.get(key, [])
        return tuple(str(v) for v in value) if isinstance(value, list) else ()

    return ToolSpec(
        name=name,
        mise_key=str(table["mise_key"]),
        binary=_str("binary") or name,
        pypi=_str("pypi"),
        github=_str("github"),
        extras=_tuple("extras"),
        extra_probes=_tuple("extra_probes"),
        manifest=_str("manifest"),
        artifact=_str("artifact"),
        stamp=_str("stamp"),
        os=_tuple("os"),
        watch=_watch_items(table.get("watch")),
    )


def load(repo_root: Path) -> tuple[ToolSpec, ...]:
    """Parse `<repo_root>/currency.toml` into ToolSpecs, sorted by tool name.

    A missing config is an empty tuple, not an error — a repo that has not adopted
    the engine yet must not fail its own session-start hook.
    """
    path = repo_root / CONFIG_NAME
    if not path.exists():
        return ()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    tools = data.get("tool", {})
    if not isinstance(tools, dict):
        raise TypeError(f"{path}: expected a [tool.<name>] table")
    specs: list[ToolSpec] = []
    for raw_name, table in sorted(tools.items(), key=lambda kv: str(kv[0])):
        if not isinstance(table, dict):
            continue
        # Re-key explicitly: tomllib hands back `dict[Unknown, Unknown]`, and dict
        # is invariant, so passing it straight through does not type-check.
        specs.append(_tool_spec(str(raw_name), {str(k): v for k, v in table.items()}))
    return tuple(specs)
