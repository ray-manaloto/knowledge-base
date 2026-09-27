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
        "python/src/kb_setup/graph.py",
        ".agents/skills/graphify/SKILL.md",
        ".github/graphify/allowed-signers",
        ".github/workflows/graphify-live-receipt.yml",
        ".github/workflows/graphify-integration.yml",
    ):
        assert needs_live_receipt(_paths(name), b"")


def test_node_only_mise_update_is_exempt() -> None:
    diff = b'--- a/mise.toml\n+++ b/mise.toml\n@@ -48 +48 @@\n-node = "26.9.0"\n+node = "26.10.0"\n'
    assert not needs_live_receipt(
        _paths("mise.toml", "mise.lock"),
        diff,
        base_lock=b'[tools]\nnode = [{version = "26.9.0"}]\nhk = [{version = "2.3.0"}]\n',
        head_lock=b'[tools]\nnode = [{version = "26.10.0"}]\nhk = [{version = "2.3.0"}]\n',
    )


def test_non_node_lock_change_requires_evidence_even_with_node_only_mise_diff() -> None:
    assert needs_live_receipt(
        _paths("mise.toml", "mise.lock"),
        b'-node = "26.9.0"\n+node = "26.10.0"\n',
        base_lock=b'[tools]\nnode = [{version = "26.9.0"}]\nhk = [{version = "2.2.0"}]\n',
        head_lock=b'[tools]\nnode = [{version = "26.10.0"}]\nhk = [{version = "2.3.0"}]\n',
    )


def test_extraction_tool_or_task_change_requires_live_evidence() -> None:
    for line in (
        b'-python = "3.14.6"\n+python = "3.14.7"\n',
        b'-run = "mise run kb-graphify-ingest"\n+run = "python other.py"\n',
        b'+hk = "2.3.0"\n',
    ):
        assert needs_live_receipt(_paths("mise.toml", "mise.lock"), line)


def test_ambiguous_or_oversized_diff_fails_closed() -> None:
    assert needs_live_receipt(b"", b"")
    assert needs_live_receipt(b"mise.toml", b"")
    assert needs_live_receipt(_paths("mise.toml"), b"")
    assert needs_live_receipt(_paths("README.md") + b"x" * 1_000_001, b"")


def test_unrelated_docs_and_workflow_are_exempt() -> None:
    assert not needs_live_receipt(_paths("README.md", ".github/workflows/weekly-report.yml"), b"")
