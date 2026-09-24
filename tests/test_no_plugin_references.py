# Copyright (c) 2026 Raymond Manaloto
"""No live surface may name or enable fable-orchestrator again (knowledge-base#797).

The plugin was removed from both repos (spec ray-manaloto/dotfiles#1310): its
upstream is 404 and its only copy was a plugin cache that can be garbage-
collected, which is how `kb-tool-review.js` came to depend on an agent that could
vanish. dotfiles enforces the same ban through its `orchestration.no-plugin-references`
verify contract; this is the knowledge-base equivalent.

Scope is the live instruction and config surface: every Claude project config,
setting, agent, workflow, codex agent, rule and skill (both skill trees). Records
are out of scope on purpose — `sources/`, `docs/`, `graphify-out/memory/`, and the
brain tests, which keep the plugin's names as provenance.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).parent.parent

#: `plugin:agent` / `plugin:skill` names and `plugin@marketplace` enablement keys.
FORBIDDEN = ("fable-orchestrator:", "fable-orchestrator@")

SURFACE_GLOBS = (
    "CLAUDE.md",
    ".claude/CLAUDE.md",
    ".claude/settings.json",
    ".claude/agents/*.md",
    ".claude/workflows/*.js",
    ".claude/rules/*.md",
    ".claude/skills/**/*.md",
    ".agents/skills/**/*.md",
    ".codex/agents/*.toml",
)


def plugin_references(root: Path) -> list[str]:
    """Every `path:line: token` hit of a forbidden token on the live surface."""
    hits: list[str] = []
    for pattern in SURFACE_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                hits.extend(
                    f"{path.relative_to(root)}:{n}: {tok}" for tok in FORBIDDEN if tok in line
                )
    return hits


def test_every_surface_glob_matches_something() -> None:
    """A glob that matches nothing is a check scanning nothing."""
    empty = [g for g in SURFACE_GLOBS if not any(_ROOT.glob(g))]
    assert empty == []


def test_the_live_surface_names_no_plugin() -> None:
    assert plugin_references(_ROOT) == []


def test_a_reintroduced_reference_fails(tmp_path: Path) -> None:
    """FAIL arm: the realistic regression — a plugin agent written back into an agent file."""
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "claude-advisor.md").write_text("Fallback: `fable-orchestrator:fable-advisor`.\n")
    (tmp_path / ".claude" / "settings.json").write_text(
        '{"enabledPlugins": {"fable-orchestrator@fable-orchestrator": true}}\n'
    )
    assert plugin_references(tmp_path) == [
        ".claude/settings.json:1: fable-orchestrator@",
        ".claude/agents/claude-advisor.md:1: fable-orchestrator:",
    ]


def test_a_clean_surface_passes(tmp_path: Path) -> None:
    """Control arm, same fixture shape: the removal note itself is allowed."""
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "claude-advisor.md").write_text("Replaced the fable-orchestrator plugin.\n")
    assert plugin_references(tmp_path) == []
