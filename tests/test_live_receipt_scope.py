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
        assert needs_live_receipt(_paths(name), b"")


def test_node_only_mise_update_is_exempt() -> None:
    diff = b'--- a/mise.toml\n+++ b/mise.toml\n@@ -48 +48 @@\n-node = "26.9.0"\n+node = "26.10.0"\n'
    assert not needs_live_receipt(
        _paths("mise.toml", "mise.lock"),
        diff,
        base_lock=b'[tools]\nnode = [{version = "26.9.0"}]\nhk = [{version = "2.3.0"}]\n',
        head_lock=b'[tools]\nnode = [{version = "26.10.0"}]\nhk = [{version = "2.3.0"}]\n',
    )


def test_extraction_lock_change_requires_evidence_even_with_node_only_mise_diff() -> None:
    assert needs_live_receipt(
        _paths("mise.toml", "mise.lock"),
        b'-node = "26.9.0"\n+node = "26.10.0"\n',
        base_lock=b'[tools]\nnode = [{version = "26.9.0"}]\npython = [{version = "3.14.6"}]\n',
        head_lock=b'[tools]\nnode = [{version = "26.10.0"}]\npython = [{version = "3.14.7"}]\n',
    )


_LOCK = (
    b'conda-packages = {}\n[tools]\nhk = [{version = "1.57.0"}]\nrumdl = [{version = "0.2.62"}]\n'
    b'antigravity-cli = [{version = "1.2.12"}]\npython = [{version = "3.14.7"}]\n'
    b'uv = [{version = "0.12.8"}]\n"npm:@openai/codex" = [{version = "0.154.0"}]\n'
)


def _lock_only(head: bytes) -> bool:
    return needs_live_receipt(_paths("mise.lock"), b"", base_lock=_LOCK, head_lock=head)


def test_plain_tool_pin_lock_changes_are_exempt() -> None:
    """#824: a lock diff touching only non-extraction tools needs no live evidence."""
    assert not _lock_only(_LOCK.replace(b'"1.57.0"', b'"2.4.0"'))
    assert not _lock_only(_LOCK.replace(b'"1.57.0"', b'"2.4.0"').replace(b'"0.2.62"', b'"0.2.78"'))
    assert not _lock_only(_LOCK.replace(b'antigravity-cli = [{version = "1.2.12"}]\n', b""))
    assert not _lock_only(_LOCK + b'gh = [{version = "2.80.0"}]\n')


def test_extraction_relevant_lock_changes_require_evidence() -> None:
    assert _lock_only(_LOCK.replace(b'"3.14.7"', b'"3.14.8"'))
    assert _lock_only(_LOCK.replace(b'"0.12.8"', b'"0.12.9"'))
    assert _lock_only(_LOCK.replace(b'"0.154.0"', b'"0.156.0"'))
    assert _lock_only(_LOCK + b'"pipx:graphifyy" = [{version = "0.9.61"}]\n')
    assert _lock_only(_LOCK + b'"claude-code" = [{version = "2.1.287"}]\n')


def test_mixed_lock_change_requires_evidence() -> None:
    assert _lock_only(_LOCK.replace(b'"1.57.0"', b'"2.4.0"').replace(b'"3.14.7"', b'"3.14.8"'))


def test_malformed_or_non_tool_lock_change_fails_closed() -> None:
    assert _lock_only(b"[tools\nnot toml")
    assert _lock_only(b"")
    assert _lock_only(b'tools = "not a table"\n')
    assert _lock_only(_LOCK.replace(b"conda-packages = {}", b'conda-packages = {x = "1"}'))
    assert needs_live_receipt(_paths("mise.lock"), b"", base_lock=b"", head_lock=_LOCK)


def test_extraction_tool_or_task_change_requires_live_evidence() -> None:
    for line in (
        b'-python = "3.14.6"\n+python = "3.14.7"\n',
        b'-run = "mise run kb-graphify-ingest"\n+run = "python other.py"\n',
        b'-pkl = "0.32.0"\n+pkl = "0.32.1"\n',
    ):
        assert needs_live_receipt(_paths("mise.toml"), line)


def test_hk_and_postinstall_mise_lines_are_exempt() -> None:
    """#824: the hk pin and the postinstall hook are not extraction inputs."""
    for line in (
        b'-hk = "1.57.0"\n+hk = "2.4.0"\n',
        b'-postinstall = "mise reshim && hk install --mise"\n+postinstall = "mise reshim"\n',
    ):
        assert not needs_live_receipt(_paths("mise.toml"), line)


def test_ambiguous_or_oversized_diff_fails_closed() -> None:
    assert needs_live_receipt(b"", b"")
    assert needs_live_receipt(b"mise.toml", b"")
    assert needs_live_receipt(_paths("mise.toml"), b"")
    assert needs_live_receipt(_paths("README.md") + b"x" * 1_000_001, b"")


def test_unrelated_docs_and_workflow_are_exempt() -> None:
    assert not needs_live_receipt(_paths("README.md", ".github/workflows/weekly-report.yml"), b"")
