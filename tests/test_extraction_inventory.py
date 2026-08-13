# Copyright (c) 2026 Raymond Manaloto
"""The extraction inventory is an immutable committed-tree receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from kb_setup import extraction_inventory

if TYPE_CHECKING:
    from collections.abc import Callable


def _chunk(*, node_id: str = "n1", producer: bool = False) -> bytes:
    data: dict[str, object] = {
        "nodes": [
            {
                "id": node_id,
                "_origin": "semantic",
                "label": "N1",
                "file_type": "concept",
                "source_file": "docs/a.md",
                "source_url": "https://example.test/a",
                "captured_at": "2026-08-11",
            }
        ],
        "edges": [],
        "hyperedges": [],
        "input_tokens": 1,
        "output_tokens": 1,
    }
    if producer:
        data["extraction_receipt"] = {"model": "fixture", "source_sha256": "0" * 64}
    return json.dumps(data, sort_keys=True).encode()


def _commit_bytes(git: Callable[..., str], root: Path, relative: str, body: bytes) -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    git("add", "--", relative)
    git("commit", "-q", "-m", f"add {relative}")
    return git("rev-parse", "HEAD")


def test_inventory_reads_and_binds_exact_committed_blob(
    git: Callable[..., str], tmp_path: Path
) -> None:
    body = _chunk(producer=True)
    commit = _commit_bytes(git, tmp_path, "sources/extractions/bound.json", body)
    tree = git("rev-parse", f"{commit}^{{tree}}")
    oid = git("rev-parse", f"{commit}:sources/extractions/bound.json")

    receipt = extraction_inventory.snapshot(tmp_path)

    assert receipt.authority == "git_tree_snapshot"
    assert receipt.resolved_commit == commit
    assert receipt.resolved_tree == tree
    assert receipt.complete is True
    assert receipt.diagnostics == ()
    assert len(receipt.records) == 1
    record = receipt.records[0]
    assert record.chunk == "bound.json"
    assert record.blob_oid == oid
    assert record.size_bytes == len(body)
    assert record.sha256 == hashlib.sha256(body).hexdigest()
    assert record.status == "VALID_BOUND"
    assert len(receipt.inventory_digest) == 64


def test_late_worktree_mutation_cannot_change_committed_bytes(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    committed = _chunk(node_id="committed")
    _commit_bytes(git, tmp_path, "sources/extractions/a.json", committed)
    original = extraction_inventory._read_blobs

    def mutate_after_read(
        repo_root: Path, entries: tuple[extraction_inventory._TreeEntry, ...]
    ) -> tuple[bytes, ...]:
        bodies = original(repo_root, entries)
        (repo_root / "sources/extractions/a.json").write_bytes(_chunk(node_id="mutated"))
        return bodies

    monkeypatch.setattr(extraction_inventory, "_read_blobs", mutate_after_read)

    receipt = extraction_inventory.snapshot(tmp_path)

    assert receipt.records[0].sha256 == hashlib.sha256(committed).hexdigest()
    assert receipt.complete is False
    assert receipt.diagnostics == ("worktree_unstaged",)


def test_checkout_drift_is_diagnostic_but_never_inventory_authority(
    git: Callable[..., str], tmp_path: Path
) -> None:
    committed = _chunk(node_id="committed")
    _commit_bytes(git, tmp_path, "sources/extractions/a.json", committed)
    target = tmp_path / "sources/extractions/a.json"
    target.write_bytes(_chunk(node_id="staged"))
    git("add", "--", "sources/extractions/a.json")
    target.write_bytes(_chunk(node_id="unstaged"))
    (tmp_path / "sources/extractions/untracked.json").write_bytes(_chunk(node_id="new"))

    receipt = extraction_inventory.snapshot(tmp_path)

    assert receipt.records[0].sha256 == hashlib.sha256(committed).hexdigest()
    assert receipt.diagnostics == (
        "worktree_staged",
        "worktree_unstaged",
        "worktree_untracked",
    )
    assert receipt.complete is False


def test_head_movement_does_not_mix_commits(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    committed = _chunk(node_id="old")
    first_commit = _commit_bytes(git, tmp_path, "sources/extractions/a.json", committed)
    original = extraction_inventory._read_blobs

    def advance_head(
        repo_root: Path, entries: tuple[extraction_inventory._TreeEntry, ...]
    ) -> tuple[bytes, ...]:
        bodies = original(repo_root, entries)
        marker = repo_root / "marker.txt"
        marker.write_text("new commit\n", encoding="utf-8")
        git("add", "--", "marker.txt")
        git("commit", "-q", "-m", "advance head")
        return bodies

    monkeypatch.setattr(extraction_inventory, "_read_blobs", advance_head)

    receipt = extraction_inventory.snapshot(tmp_path)

    assert receipt.resolved_commit == first_commit
    assert receipt.records[0].sha256 == hashlib.sha256(committed).hexdigest()
    assert receipt.diagnostics == ("head_changed",)
    assert receipt.complete is False


def test_gitattributes_cannot_transform_blob_authority(
    git: Callable[..., str], tmp_path: Path
) -> None:
    body = _chunk(node_id="$Id$")
    target = tmp_path / "sources/extractions/a.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(body)
    (tmp_path / ".gitattributes").write_text("sources/extractions/*.json ident\n", encoding="utf-8")
    git("add", "--", ".gitattributes", "sources/extractions/a.json")
    git("commit", "-q", "-m", "attributes cannot rewrite object reads")

    receipt = extraction_inventory.snapshot(tmp_path)

    assert receipt.records[0].sha256 == hashlib.sha256(body).hexdigest()


def test_symlink_and_submodule_modes_are_rejected(git: Callable[..., str], tmp_path: Path) -> None:
    target = tmp_path / "sources/extractions/link.json"
    target.parent.mkdir(parents=True)
    target.symlink_to("../../outside")
    git("add", "--", "sources/extractions/link.json")
    git("commit", "-q", "-m", "symlink")

    with pytest.raises(extraction_inventory.InventoryError) as symlink_error:
        extraction_inventory.snapshot(tmp_path)
    assert symlink_error.value.code == "non_regular_extraction_blob"

    target.unlink()
    git("rm", "-q", "--", "sources/extractions/link.json")
    commit_oid = git("rev-parse", "HEAD")
    git(
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{commit_oid},sources/extractions/submodule.json",
    )
    git("commit", "-q", "-m", "gitlink")

    with pytest.raises(extraction_inventory.InventoryError) as gitlink_error:
        extraction_inventory.snapshot(tmp_path)
    assert gitlink_error.value.code == "non_regular_extraction_blob"


def test_malformed_json_is_total_and_never_echoes_body(
    git: Callable[..., str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sensitive_body_marker = "private-token-must-not-leak"
    _commit_bytes(
        git,
        tmp_path,
        "sources/extractions/malformed.json",
        f'{{"nodes": ["{sensitive_body_marker}"],'.encode(),
    )

    assert extraction_inventory.report(tmp_path, ["--json"]) == 1
    output = capsys.readouterr().out
    assert sensitive_body_marker not in output
    assert str(tmp_path) not in output
    assert '"issues": [' in output
    assert '"invalid_json"' in output


def test_duplicate_node_ids_are_invalid_without_echoing_the_id(
    git: Callable[..., str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    duplicate = "private-duplicate-id"
    data = json.loads(_chunk(node_id=duplicate))
    data["nodes"].append(dict(data["nodes"][0]))
    _commit_bytes(
        git,
        tmp_path,
        "sources/extractions/duplicate.json",
        json.dumps(data).encode(),
    )

    assert extraction_inventory.report(tmp_path, ["--json"]) == 1
    output = capsys.readouterr().out
    assert duplicate not in output
    assert '"invalid_chunk_schema"' in output


def test_duplicate_blob_oids_and_nested_json_paths_are_rejected(
    git: Callable[..., str], tmp_path: Path
) -> None:
    body = _chunk()
    first = tmp_path / "sources/extractions/a.json"
    second = tmp_path / "sources/extractions/b.json"
    first.parent.mkdir(parents=True)
    first.write_bytes(body)
    second.write_bytes(body)
    git("add", "--", "sources/extractions/a.json", "sources/extractions/b.json")
    git("commit", "-q", "-m", "duplicate object")

    with pytest.raises(extraction_inventory.InventoryError) as duplicate_error:
        extraction_inventory.snapshot(tmp_path)
    assert duplicate_error.value.code == "duplicate_extraction_blob_oid"

    second.unlink()
    nested = tmp_path / "sources/extractions/nested/c.json"
    nested.parent.mkdir()
    nested.write_bytes(_chunk(node_id="nested"))
    git("add", "-A", "--", "sources/extractions")
    git("commit", "-q", "-m", "nested object")

    with pytest.raises(extraction_inventory.InventoryError) as nested_error:
        extraction_inventory.snapshot(tmp_path)
    assert nested_error.value.code == "noncanonical_extraction_path"


def test_size_limits_fail_before_blob_read(
    git: Callable[..., str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _commit_bytes(git, tmp_path, "sources/extractions/a.json", _chunk())
    monkeypatch.setattr(extraction_inventory, "_MAX_BLOB_BYTES", 1)

    with pytest.raises(extraction_inventory.InventoryError) as error:
        extraction_inventory.snapshot(tmp_path)
    assert error.value.code == "extraction_blob_size_limit_exceeded"


def test_receipt_and_default_cli_are_deterministic_and_name_authority(
    git: Callable[..., str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _commit_bytes(git, tmp_path, "sources/extractions/a.json", _chunk())

    first = extraction_inventory.snapshot(tmp_path)
    second = extraction_inventory.snapshot(tmp_path)

    assert first == second
    assert extraction_inventory.report(tmp_path) == 0
    output = capsys.readouterr().out
    assert "authority: git_tree_snapshot" in output
    assert "scope: sources/extractions/*.json" in output
