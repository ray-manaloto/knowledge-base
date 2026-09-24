# Copyright (c) 2026 Raymond Manaloto
"""Saved workflows may dispatch only built-in or repo-declared agents (knowledge-base#793).

`kb-tool-review.js` dispatched `fable-orchestrator:codex-reviewer`, a PLUGIN agent
whose only copy was a plugin cache that can be garbage-collected. It was the one
runtime dependency on the plugin in either repo, and nothing noticed it until the
removal audit. This test is the class fix: any `agentType` a workflow names must
be a Claude Code built-in or the frontmatter `name:` of a file in `.claude/agents/`.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).parent.parent

#: Claude Code's built-in subagent types. Source: the harness docs' "Built-in
#: subagents" section (`sources/agent-harness-docs/docs/claude-code/sub-agents.md`,
#: lines 31-84: Explore, Plan, general-purpose). `general-purpose` is also the
#: harness default when a call site omits `agentType` (`kb-extract.js` uses it).
BUILTIN_AGENT_TYPES = frozenset({"general-purpose", "Explore", "Plan"})

_AGENT_TYPE_RE = re.compile(r"""agentType:\s*['"]([^'"]+)['"]""")
_NAME_RE = re.compile(r"^name:\s*(\S+)\s*$", re.MULTILINE)


def _declared(agents_dir: Path) -> set[str]:
    return {
        m.group(1)
        for p in sorted(agents_dir.glob("*.md"))
        for m in [_NAME_RE.search(p.read_text(encoding="utf-8"))]
        if m
    }


def undeclared_agent_types(workflows_dir: Path, agents_dir: Path) -> list[str]:
    """Every literal `agentType` no built-in or local agent file declares."""
    allowed = _declared(agents_dir) | BUILTIN_AGENT_TYPES
    return sorted(
        f"{p.name}: {m.group(1)}"
        for p in sorted(workflows_dir.glob("*.js"))
        for m in _AGENT_TYPE_RE.finditer(p.read_text(encoding="utf-8"))
        if m.group(1) not in allowed
    )


def test_real_workflows_dispatch_only_declared_agents() -> None:
    assert (
        undeclared_agent_types(_ROOT / ".claude" / "workflows", _ROOT / ".claude" / "agents") == []
    )


def _fixture(tmp_path: Path, agent_type: str) -> list[str]:
    workflows = tmp_path / "workflows"
    agents = tmp_path / "agents"
    workflows.mkdir(parents=True)
    agents.mkdir(parents=True)
    (agents / "kb-synthesist.md").write_text("---\nname: kb-synthesist\n---\n")
    (workflows / "w.js").write_text(f"await agent('x', {{ agentType: '{agent_type}' }})\n")
    return undeclared_agent_types(workflows, agents)


def test_a_plugin_namespaced_agent_fails(tmp_path: Path) -> None:
    assert _fixture(tmp_path, "fable-orchestrator:codex-reviewer") == [
        "w.js: fable-orchestrator:codex-reviewer"
    ]


def test_an_undeclared_agent_fails(tmp_path: Path) -> None:
    assert _fixture(tmp_path, "ghost-reviewer") == ["w.js: ghost-reviewer"]


def test_a_builtin_and_a_declared_agent_pass(tmp_path: Path) -> None:
    assert _fixture(tmp_path / "a", "general-purpose") == []
    assert _fixture(tmp_path / "b", "kb-synthesist") == []
