# Copyright (c) 2026 Raymond Manaloto
"""Tests for assembling staged semantic-corpus chunks into a committed doc chunk.

The fixture builds a whole staged run — plan directory, ledger, receipts, staged
fragments — from the published structs, so nothing here depends on
`graphify-out/graphify-semantic-corpus`, which is DERIVED and gitignored and
therefore absent from a fresh clone. A test that skipped when the real plan is
missing would be a test that never runs in CI or on another machine.
"""

from __future__ import annotations

import json
from pathlib import Path

import msgspec
import pytest
from kb_setup import graphify_semantic_corpus as corpus
from kb_setup import graphify_semantic_corpus_merge as merge

_NAMESPACE = "a" * 64
_CACHE_NAMESPACE = "b" * 64


class _Staged(msgspec.Struct, frozen=True):
    """One chunk to stage. A struct rather than six positional parameters."""

    ordinal: int
    source_file: str
    nodes: tuple[str, ...]
    namespace: str = _NAMESPACE
    status: str = "complete"

    @property
    def fragment(self) -> dict[str, object]:
        return {
            "nodes": [_node(nid, self.source_file) for nid in self.nodes],
            "edges": [],
            "hyperedges": [],
        }


def _node(nid: str, source_file: str) -> dict[str, object]:
    """A node in the shape the adapter actually emits — WITHOUT `_origin`.

    The absence is the point: it is what makes a staged fragment unmergeable, and a
    fixture that helpfully included it could not exhibit the bug this module exists
    to fix.
    """
    return {
        "id": nid,
        "label": nid.replace("_", " ").title(),
        "file_type": "document",
        "source_file": source_file,
        "source_url": None,
        "source_location": None,
        "author": None,
        "captured_at": None,
        "contributor": None,
        "rationale": None,
    }


def _fragment(nid: str, source_file: str) -> dict[str, object]:
    return {"nodes": [_node(nid, source_file)], "edges": [], "hyperedges": []}


def _plan(tmp_path: Path, chunk_specs: list[tuple[int, str]]) -> Path:
    """Write a plan directory whose ledger holds one chunk per spec."""
    candidate = tmp_path / "plan"
    candidate.mkdir(parents=True, exist_ok=True)
    total = len(chunk_specs)
    ledger = corpus.ChunkLedger(
        token_budget=20000,
        unit_count=total,
        chunks=tuple(
            corpus.PlannedChunk(
                ordinal=ordinal,
                total=total,
                estimated_tokens=100,
                members=(
                    corpus.ChunkMember(
                        unit_ordinal=ordinal,
                        path=source_file,
                        slice_index=0,
                        sha256="c" * 64,
                        estimated_tokens=100,
                    ),
                ),
            )
            for ordinal, source_file in chunk_specs
        ),
    )
    (candidate / "chunk-ledger.json").write_bytes(corpus.encode_canonical(ledger))
    (candidate / "manifest.json").write_text('{"schema_id": "test"}')
    (candidate / "execution-config.json").write_text(
        json.dumps({"cache_namespace_sha256": _CACHE_NAMESPACE})
    )
    return candidate


def _stage(candidate: Path, spec: _Staged, **overrides: object) -> Path:
    """Stage one chunk exactly as the run driver's `stage_chunk` would.

    `overrides` is how a test corrupts ONE field of an otherwise-valid receipt, so
    each refusal test isolates the check it names instead of asserting on a receipt
    that is wrong in several ways at once.
    """
    ledger, config = merge._plan_members(candidate)
    planned = {c.ordinal: c for c in ledger.chunks}[spec.ordinal]
    fragment = spec.fragment
    raw = corpus.encode_canonical(fragment)
    fields: dict[str, object] = {
        "status": spec.status,
        "cache_namespace_sha256": config.cache_namespace_sha256,
        "run_namespace_sha256": spec.namespace,
        "chunk_ordinal": spec.ordinal,
        "chunk_total": planned.total,
        "chunk_sha256": corpus.sha256_bytes(corpus.encode_canonical(planned)),
        "plan_manifest_sha256": corpus.sha256_path(candidate / "manifest.json"),
        "execution_config_sha256": corpus.sha256_path(candidate / "execution-config.json"),
        "prompt_contract_sha256": "d" * 64,
        "structured_schema_sha256": "e" * 64,
        "provider_prompt_sha256": "f" * 64,
        "source_paths": (spec.source_file,),
        "fragment_sha256": corpus.sha256_bytes(raw),
        "fragment_size": len(raw),
        "provider_receipt_sha256": "0" * 64,
        "provider_receipt_size": 1,
        "adapter_metadata_sha256": "1" * 64,
        "adapter_metadata_size": 1,
        "node_count": len(spec.nodes),
        "edge_count": 0,
        "hyperedge_count": 0,
        "warnings": (),
        "errors": (),
        "reasons": (),
    }
    fields.update(overrides)
    receipt = msgspec.convert(fields, type=corpus.ChunkStageReceipt, strict=False)
    stage = merge.cache_root_for(candidate) / spec.namespace / "chunks" / f"{spec.ordinal:04d}"
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "semantic-fragment.json").write_bytes(raw)
    (stage / "receipt.json").write_bytes(corpus.encode_canonical(receipt))
    return stage


@pytest.fixture
def repo(tmp_path) -> Path:
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    return tmp_path


def test_assemble_stamps_semantic_origin_on_every_node(repo) -> None:
    """The gap that made a staged fragment unmergeable, closed and asserted.

    Without `_origin`, graphify 0.9.32+ reads the tier off `source_location` and
    drops the node from `graph-prose.json` — merged clean, silently short.
    """
    candidate = _plan(repo, [(1, "docs/a.md")])
    _stage(candidate, _Staged(1, "docs/a.md", ("a_one",)))
    out, accepted = merge.assemble(repo, candidate, "corpus-probe", allow_partial=True)
    written = json.loads(out.read_text())
    assert [n["_origin"] for n in written["nodes"]] == ["semantic"]
    assert [c.ordinal for c in accepted] == [1]


def test_assembled_chunk_passes_the_chunk_validator(repo) -> None:
    """End to end against the REAL gate, not a restatement of the stamp.

    `kb-validate-chunks` is what refuses an unstamped fragment, so the assembled
    artifact must clear `chunks.validate` itself — asserting only that `_origin` is
    set would be this module agreeing with itself.
    """
    from kb_setup import chunks

    candidate = _plan(repo, [(1, "docs/a.md"), (2, "docs/b.md")])
    _stage(candidate, _Staged(1, "docs/a.md", ("a_one",)))
    _stage(candidate, _Staged(2, "docs/b.md", ("b_one",)))
    out, _accepted = merge.assemble(repo, candidate, "corpus-probe")
    assert chunks.validate(json.loads(out.read_text())) == []


def test_unstamped_fragment_would_be_refused_by_the_validator(repo) -> None:
    """The control arm for the test above: the fixture CAN produce a refusal.

    Without it, `test_assembled_chunk_passes_the_chunk_validator` is a probe with
    one face — a fragment the validator happens to like either way would pass it.
    """
    from kb_setup import chunks

    raw = _fragment("a_one", "docs/a.md")
    raw["input_tokens"] = 0
    raw["output_tokens"] = 0
    issues = chunks.validate(raw)
    assert any("_origin" in i for i in issues)


def test_a_short_run_is_refused_unless_partial_is_asked_for(repo) -> None:
    """A corpus missing 57 of 58 chunks merges cleanly and reads as success."""
    candidate = _plan(repo, [(1, "docs/a.md"), (2, "docs/b.md")])
    _stage(candidate, _Staged(1, "docs/a.md", ("a_one",)))
    with pytest.raises(ValueError, match="staged 1 of 2 planned chunk"):
        merge.assemble(repo, candidate, "corpus-probe")
    out, accepted = merge.assemble(repo, candidate, "corpus-probe", allow_partial=True)
    assert len(accepted) == 1
    assert out.exists()


def test_a_failed_chunk_is_never_assembled(repo) -> None:
    candidate = _plan(repo, [(1, "docs/a.md")])
    _stage(
        candidate,
        _Staged(1, "docs/a.md", ("a_one",), status="failed"),
        reasons=("fragment-out-of-scope",),
    )
    with pytest.raises(ValueError, match="chunk-status-failed"):
        merge.assemble(repo, candidate, "corpus-probe", allow_partial=True)


def test_a_tampered_fragment_is_refused(repo) -> None:
    """The receipt's digest is what makes the staged bytes evidence."""
    candidate = _plan(repo, [(1, "docs/a.md")])
    stage = _stage(candidate, _Staged(1, "docs/a.md", ("a_one",)))
    (stage / "semantic-fragment.json").write_text(json.dumps(_fragment("substituted", "docs/a.md")))
    with pytest.raises(ValueError, match="fragment-digest-mismatch"):
        merge.assemble(repo, candidate, "corpus-probe", allow_partial=True)


def test_a_chunk_staged_against_another_plan_is_refused(repo) -> None:
    """Same ordinal, different member packing — the ledger digest is the binding."""
    candidate = _plan(repo, [(1, "docs/a.md")])
    _stage(candidate, _Staged(1, "docs/a.md", ("a_one",)))
    # Re-plan the SAME ordinal over a different source unit, leaving the staged
    # evidence in place. Nothing about the path changed; only the packing did.
    _plan(repo, [(1, "docs/moved.md")])
    with pytest.raises(ValueError, match="chunk-digest-mismatch"):
        merge.assemble(repo, candidate, "corpus-probe", allow_partial=True)


def test_two_run_namespaces_binding_to_one_plan_are_refused_not_chosen_between(repo) -> None:
    """Discovery is by content, so it must say when the content is ambiguous."""
    candidate = _plan(repo, [(1, "docs/a.md")])
    _stage(candidate, _Staged(1, "docs/a.md", ("a_one",)))
    _stage(candidate, _Staged(1, "docs/a.md", ("a_one",), namespace="9" * 64))
    with pytest.raises(ValueError, match="2 run namespaces bind to this plan"):
        merge.assemble(repo, candidate, "corpus-probe", allow_partial=True)


def test_a_staged_dir_whose_receipt_names_another_namespace_is_refused(repo) -> None:
    candidate = _plan(repo, [(1, "docs/a.md")])
    _stage(candidate, _Staged(1, "docs/a.md", ("a_one",)), run_namespace_sha256="7" * 64)
    with pytest.raises(ValueError, match="run-namespace-mismatch"):
        merge.assemble(repo, candidate, "corpus-probe", allow_partial=True)


def test_an_empty_cache_root_is_a_refusal_not_an_empty_chunk(repo) -> None:
    candidate = _plan(repo, [(1, "docs/a.md")])
    with pytest.raises(ValueError, match="no staged chunk binds to this plan"):
        merge.assemble(repo, candidate, "corpus-probe", allow_partial=True)
    assert not list((repo / "sources" / "extractions").iterdir())


def test_cross_chunk_id_collision_is_reported_with_the_chunk_ordinal(repo) -> None:
    """The naming half of gap 2, asserted through this module's own output.

    Both staged fragments are `semantic-fragment.json`; the assembled per-chunk
    files are not, so the refusal names which ordinals collided.
    """
    candidate = _plan(repo, [(1, "docs/a.md"), (2, "docs/b.md")])
    _stage(candidate, _Staged(1, "docs/a.md", ("dup",)))
    _stage(candidate, _Staged(2, "docs/b.md", ("dup",)))
    with pytest.raises(ValueError, match="id collision 'dup'") as excinfo:
        merge.assemble(repo, candidate, "corpus-probe")
    assert "chunk-0001.json" in str(excinfo.value)
    assert "chunk-0002.json" in str(excinfo.value)


def test_a_prior_merges_intermediates_are_cleared(repo) -> None:
    """The staging dir must describe THIS artifact, not a mix of two runs."""
    candidate = _plan(repo, [(1, "docs/a.md")])
    _stage(candidate, _Staged(1, "docs/a.md", ("a_one",)))
    staging = merge._staging_dir(candidate)
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "chunk-0042.json").write_text("{}")
    unrelated = staging / "notes.md"
    unrelated.write_text("left by hand")

    merge.assemble(repo, candidate, "corpus-probe", allow_partial=True)

    assert not (staging / "chunk-0042.json").exists()
    assert (staging / "chunk-0001.json").is_file()
    # Only the ordinal-named files this module owns are cleared.
    assert unrelated.is_file()


def test_merge_main_refuses_a_missing_plan_directory(repo) -> None:
    assert merge.merge_main(repo, ["corpus-probe", str(repo / "absent")]) == 2


def test_merge_main_rejects_an_unknown_flag(repo) -> None:
    """The plan must be VALID and complete, or rc=2 proves nothing.

    First written as `["corpus-probe", "--force"]` against no plan at all, which
    returned 2 for the missing-directory reason and stayed green with the flag check
    deleted — a mutation SURVIVED on it. With a staged, complete plan the only
    remaining route to a non-zero rc is the flag itself.
    """
    candidate = _plan(repo, [(1, "docs/a.md")])
    _stage(candidate, _Staged(1, "docs/a.md", ("a_one",)))
    assert merge.merge_main(repo, ["corpus-probe", str(candidate)]) == 0
    assert merge.merge_main(repo, ["corpus-probe", str(candidate), "--force"]) == 2


def test_merge_main_reports_the_arithmetic_it_assembled(repo, capsys) -> None:
    """The printed counts are what a reader checks the merge against.

    TWO nodes in ONE chunk, deliberately: with one of each, node count and chunk
    count are both 1 and the assertion cannot tell them apart — a mutation printing
    `len(accepted)` where the node total belongs SURVIVED on the one-node fixture.
    """
    candidate = _plan(repo, [(1, "docs/a.md")])
    _stage(candidate, _Staged(1, "docs/a.md", ("a_one", "a_two")))
    assert merge.merge_main(repo, ["corpus-probe", str(candidate), "--partial"]) == 0
    out = capsys.readouterr().out
    assert "assembled 1/1 chunk(s)" in out
    assert "2 nodes, 0 edges, 0 hyperedges" in out
    assert "mise run kb-merge --" in out
