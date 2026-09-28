# Copyright (c) 2026 Raymond Manaloto
"""Fail-closed controls for conditional signed Graphify live evidence."""

from kb_setup.live_receipt_scope import needs_live_receipt


def _paths(*names: str) -> bytes:
    return b"".join(name.encode() + b"\0" for name in names)


def test_graphify_fork_and_adapter_changes_require_live_evidence() -> None:
    for name in (
        "pyproject.toml",
        "uv.lock",
        "sources/graphify.manifest",
        "sources/planning-with-files.manifest",
        "python/src/kb_setup/graphify_ingest.py",
        "python/src/kb_setup/cli.py",
        "python/src/kb_setup/graph.py",
        ".claude/workflows/kb-extract.js",
        ".agents/skills/graphify/SKILL.md",
        ".github/graphify/allowed-signers",
        ".github/workflows/graphify-live-receipt.yml",
        ".github/workflows/graphify-integration.yml",
        "python/src/kb_setup/live_receipt_produce.py",
    ):
        assert needs_live_receipt(_paths(name))


def test_shared_and_new_package_helpers_require_live_evidence() -> None:
    for name in (
        "python/src/kb_setup/result.py",
        "python/src/kb_setup/future_extraction_helper.py",
    ):
        assert needs_live_receipt(_paths(name))


def test_active_agent_instructions_require_live_evidence() -> None:
    for name in (
        "AGENTS.md",
        "CLAUDE.md",
        ".claude/CLAUDE.md",
        ".claude/settings.json",
        ".mcp.json",
        ".agents/skills/kb-graphify-ingest/SKILL.md",
        ".claude/skills/kb-graphify-ingest/SKILL.md",
        ".agents/skills/kb-curator/SKILL.md",
        ".claude/skills/kb-curator/SKILL.md",
        ".claude/rules/ai-cli-invocation.md",
        ".claude/agents/kb-extraction-worker.md",
        ".claude/mods/kb-settings-guard/hooks/register.ts",
        ".claude/workflows/future-extractor.js",
        ".codex/agents/kb-extraction-worker.toml",
        ".codex/agents/kb-corpus-curator.toml",
        ".codex/config.toml",
        ".codex/hooks.json",
        ".agents/skills/future-backend/SKILL.md",
    ):
        assert needs_live_receipt(_paths(name))


def test_mise_changes_always_require_live_evidence() -> None:
    # Even a Node-only pin affects the runtime for kb-extract.js. The same paths
    # can also alter PATH, CODEX_HOME, multiline task selectors or lock URLs.
    for paths in (
        _paths("mise.toml"),
        _paths("mise.lock"),
        _paths("mise.toml", "mise.lock"),
        _paths("README.md", "mise.toml"),
    ):
        assert needs_live_receipt(paths)


def test_ambiguous_or_oversized_paths_fail_closed() -> None:
    assert needs_live_receipt(b"")
    assert needs_live_receipt(b"mise.toml")
    assert needs_live_receipt(_paths("mise.toml"))
    assert needs_live_receipt(_paths("README.md") + b"x" * 1_000_001)


def test_unrelated_docs_and_workflow_are_exempt() -> None:
    assert not needs_live_receipt(_paths("README.md", ".github/workflows/weekly-report.yml"))
