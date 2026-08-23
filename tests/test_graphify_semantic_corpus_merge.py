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
from kb_setup import graphify_semantic_slice

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


# --- Scope-sanitization fixtures --------------------------------------------
#
# Modeled on chunks 12 and 26 of the real 2026-08-23 corpus run rather than
# copied from `graphify-out/graphify-semantic-corpus-chunks/`, which is
# DERIVED/gitignored and absent from a fresh clone (see the module-level
# docstring above). The shape that matters is preserved: a chunk that declares
# several member paths, whose fragment holds a minority of nodes attributed to
# a file NONE of the declared paths name (a report describing its own
# artifacts), with an edge and a hyperedge that reference the misattributed
# node — exactly what makes exclusion cascade, not just drop a node in
# isolation.

_SCOPE_A = "worked/x/README.md"
_SCOPE_B = "worked/x/REPORT.md"


def _edge(
    source: str, target: str, source_file: str, *, relation: str = "references"
) -> dict[str, object]:
    """An edge in the adapter's own shape — see `chunks._EDGE_REQUIRED`."""
    return {
        "source": source,
        "target": target,
        "relation": relation,
        "confidence": "EXTRACTED",
        "confidence_score": 1,
        "weight": 1,
        "source_file": source_file,
    }


def _hyperedge(
    hid: str, members: tuple[str, ...], source_file: str, *, relation: str = "participate_in"
) -> dict[str, object]:
    """A hyperedge in the adapter's own shape — see `chunks._HYPEREDGE_CONFIDENCE`."""
    return {
        "id": hid,
        "label": hid.replace("_", " ").title(),
        "nodes": list(members),
        "relation": relation,
        "confidence": "EXTRACTED",
        "confidence_score": 0.9,
        "source_file": source_file,
    }


def _scope_fragment(out_of_scope_paths: tuple[str, ...]) -> dict[str, object]:
    """9 in-scope nodes over `_SCOPE_A`/`_SCOPE_B`, plus one node per out-of-scope path.

    Only the FIRST out-of-scope node is cited by an edge and a hyperedge — enough
    to exercise the cascade without every excluded node needing its own
    reference. The rest are still counted toward the excluded share, exactly
    like chunk 26's `graph.html`/`manifest.json`, which the real fragment cited
    only from `README.md`, not from every excluded node individually.
    """
    in_scope = [_node(f"readme_{i}", _SCOPE_A) for i in range(1, 5)] + [
        _node(f"report_{i}", _SCOPE_B) for i in range(1, 6)
    ]
    out = [_node(f"out_{i}", path) for i, path in enumerate(out_of_scope_paths)]
    edges = [_edge("readme_1", "report_1", _SCOPE_A)]
    hyperedges = [_hyperedge("readme_set", ("readme_1", "readme_2", "readme_3"), _SCOPE_A)]
    if out:
        out0_id = str(out[0]["id"])
        edges.append(_edge("report_2", out0_id, _SCOPE_B, relation="describes"))
        hyperedges.append(_hyperedge("artifact_set", ("report_1", "report_2", out0_id), _SCOPE_B))
    return {"nodes": [*in_scope, *out], "edges": edges, "hyperedges": hyperedges}


def _scope_fragment_omits_b(out_of_scope_path: str) -> dict[str, object]:
    """5 nodes over `_SCOPE_A` only, plus one out-of-scope node — `_SCOPE_B` gets NONE.

    The out-of-scope node's share (1/6, ~16.7%) clears `_MAX_EXCLUDED_SHARE` on
    its own, isolating the OTHER refusal: `_SCOPE_B` was never covered at all,
    which excluding the out-of-scope node cannot fix and must not paper over.
    """
    nodes = [_node(f"readme_{i}", _SCOPE_A) for i in range(1, 6)] + [
        _node("out_0", out_of_scope_path)
    ]
    return {"nodes": nodes, "edges": [], "hyperedges": []}


def _scope_plan(tmp_path: Path, source_paths: tuple[str, ...]) -> Path:
    """A one-chunk plan whose single chunk declares MULTIPLE member paths.

    `_plan()` above packs one source file per chunk; chunk 26/12 of the real
    run packed several, which is exactly the shape that lets the model
    describe an artifact of one declared file while it was dispatched to read
    another. A single-source plan cannot exhibit the bug this fixture exists
    to reproduce.
    """
    candidate = tmp_path / "scope-plan"
    candidate.mkdir(parents=True, exist_ok=True)
    ledger = corpus.ChunkLedger(
        token_budget=20000,
        unit_count=len(source_paths),
        chunks=(
            corpus.PlannedChunk(
                ordinal=1,
                total=1,
                estimated_tokens=100,
                members=tuple(
                    corpus.ChunkMember(
                        unit_ordinal=i,
                        path=path,
                        slice_index=0,
                        sha256="c" * 64,
                        estimated_tokens=100,
                    )
                    for i, path in enumerate(source_paths)
                ),
            ),
        ),
    )
    (candidate / "chunk-ledger.json").write_bytes(corpus.encode_canonical(ledger))
    (candidate / "manifest.json").write_text('{"schema_id": "test"}')
    (candidate / "execution-config.json").write_text(
        json.dumps({"cache_namespace_sha256": _CACHE_NAMESPACE})
    )
    return candidate


def _stage_fragment(
    candidate: Path,
    fragment: dict[str, object],
    source_paths: tuple[str, ...],
    *,
    namespace: str = _NAMESPACE,
    **overrides: object,
) -> Path:
    """Stage the ONE chunk `_scope_plan` declared, from an arbitrary fragment.

    `status`/`reasons` are DERIVED from the REAL validator
    (`graphify_semantic_slice.fragment_scope_reasons`), not hand-picked — these
    tests are about what that derivation actually produces for a multi-source,
    name-dropping fragment, and hand-picking the reasons would make the
    fixture agree with itself instead of exercising the real rule (the same
    reasoning as `test_assembled_chunk_passes_the_chunk_validator` above).
    `overrides` still wins, for the one test that needs a reason the real
    validator would never produce on its own.
    """
    ledger, config = merge._plan_members(candidate)
    planned = ledger.chunks[0]
    raw = corpus.encode_canonical(fragment)
    fragment_nodes = fragment["nodes"]
    fragment_edges = fragment["edges"]
    fragment_hyperedges = fragment.get("hyperedges", [])
    assert isinstance(fragment_nodes, list)
    assert isinstance(fragment_edges, list)
    assert isinstance(fragment_hyperedges, list)
    counts = (len(fragment_nodes), len(fragment_edges), len(fragment_hyperedges))
    reasons = graphify_semantic_slice.fragment_scope_reasons(fragment, source_paths=source_paths)
    fields: dict[str, object] = {
        "status": "failed" if reasons else "complete",
        "cache_namespace_sha256": config.cache_namespace_sha256,
        "run_namespace_sha256": namespace,
        "chunk_ordinal": planned.ordinal,
        "chunk_total": planned.total,
        "chunk_sha256": corpus.sha256_bytes(corpus.encode_canonical(planned)),
        "plan_manifest_sha256": corpus.sha256_path(candidate / "manifest.json"),
        "execution_config_sha256": corpus.sha256_path(candidate / "execution-config.json"),
        "prompt_contract_sha256": "d" * 64,
        "structured_schema_sha256": "e" * 64,
        "provider_prompt_sha256": "f" * 64,
        "source_paths": source_paths,
        "fragment_sha256": corpus.sha256_bytes(raw),
        "fragment_size": len(raw),
        "provider_receipt_sha256": "0" * 64,
        "provider_receipt_size": 1,
        "adapter_metadata_sha256": "1" * 64,
        "adapter_metadata_size": 1,
        "node_count": counts[0],
        "edge_count": counts[1],
        "hyperedge_count": counts[2],
        "warnings": (),
        "errors": (),
        "reasons": tuple(reasons),
    }
    fields.update(overrides)
    receipt = msgspec.convert(fields, type=corpus.ChunkStageReceipt, strict=False)
    stage = merge.cache_root_for(candidate) / namespace / "chunks" / f"{planned.ordinal:04d}"
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "semantic-fragment.json").write_bytes(raw)
    (stage / "receipt.json").write_bytes(corpus.encode_canonical(receipt))
    return stage


# -----------------------------------------------------------------------------


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


# --- Scope sanitization: chunks 12/26's shape, sanitized rather than refused ---


def test_a_scope_mismatch_chunk_merges_with_exclusions_recorded_and_absent(repo) -> None:
    """The success path: exactly the two survivable reasons, under the bound.

    One out-of-scope node (10% of 10) with an edge and a hyperedge citing it —
    all three must be dropped, recorded, and the REST of the chunk must reach
    `chunks.assemble` unchanged. Asserted against the real chunk validator, not
    just this module's own bookkeeping, for the same reason
    `test_assembled_chunk_passes_the_chunk_validator` is.
    """
    from kb_setup import chunks

    out_of_scope = "worked/x/graph.json"
    candidate = _scope_plan(repo, (_SCOPE_A, _SCOPE_B))
    _stage_fragment(candidate, _scope_fragment((out_of_scope,)), (_SCOPE_A, _SCOPE_B))

    out, accepted = merge.assemble(repo, candidate, "corpus-probe")

    (staged,) = accepted
    sanitization = staged.scope_sanitization
    assert sanitization is not None
    assert sanitization.excluded_count == 1
    assert sanitization.excluded_share == pytest.approx(0.1)
    (excluded_node,) = sanitization.excluded_nodes
    assert excluded_node.id == "out_0"
    assert excluded_node.source_file == out_of_scope
    (excluded_edge,) = sanitization.excluded_edges
    assert excluded_edge.source == "report_2"
    assert excluded_edge.target == "out_0"
    assert sanitization.excluded_hyperedge_ids == ("artifact_set",)

    # The counts a summary would print are the POST-exclusion ones.
    assert staged.node_count == 9
    assert staged.edge_count == 1
    assert staged.hyperedge_count == 1

    written = json.loads(out.read_text())
    written_ids = {n["id"] for n in written["nodes"]}
    assert "out_0" not in written_ids
    assert written_ids == {f"readme_{i}" for i in range(1, 5)} | {
        f"report_{i}" for i in range(1, 6)
    }
    assert all(e["source"] != "out_0" and e["target"] != "out_0" for e in written["edges"])
    assert [h["id"] for h in written["hyperedges"]] == ["readme_set"]
    assert chunks.validate(written) == []

    # Discoverable without re-deriving it from the fragment.
    record_path = merge._staging_dir(candidate) / "chunk-0001-scope-exclusions.json"
    recorded = json.loads(record_path.read_text())
    assert recorded["excluded_count"] == 1
    assert recorded["excluded_nodes"] == [{"id": "out_0", "source_file": out_of_scope}]


def test_dropping_only_the_node_without_the_cascade_would_still_refuse(repo) -> None:
    """The control arm for the cascade in `_sanitize_scope`.

    If exclusion stopped at the node and left the edge/hyperedge that cite it
    in place, `chunks.assemble` would refuse the "sanitized" fragment anyway —
    just later, and less legibly, than naming the real cause up front (the
    module docstring's claim, made concrete). Node-only exclusion is not a
    hypothetical near-miss; it is what a first attempt at this fix would most
    naturally produce.
    """
    from kb_setup import chunks

    raw = _scope_fragment(("worked/x/graph.json",))
    raw_nodes = raw["nodes"]
    assert isinstance(raw_nodes, list)
    for node in raw_nodes:
        assert isinstance(node, dict)
        node["_origin"] = "semantic"
    node_only = json.loads(json.dumps(raw))
    node_only["nodes"] = [n for n in node_only["nodes"] if n["id"] != "out_0"]
    issues = chunks.validate(node_only)
    assert any("dangling" in i for i in issues)


def test_excluded_share_over_the_bound_still_refuses(repo) -> None:
    """Three out-of-scope nodes out of 12 (25%) crosses `_MAX_EXCLUDED_SHARE` (20%)."""
    candidate = _scope_plan(repo, (_SCOPE_A, _SCOPE_B))
    _stage_fragment(
        candidate,
        _scope_fragment(("worked/x/graph.json", "worked/x/graph.html", "worked/x/manifest.json")),
        (_SCOPE_A, _SCOPE_B),
    )
    with pytest.raises(ValueError, match="scope-exclusion-share-exceeded"):
        merge.assemble(repo, candidate, "corpus-probe")
    # Nothing written on a refusal.
    assert not merge._staging_dir(candidate).exists()


def test_a_third_reason_alongside_the_two_scope_reasons_still_refuses(repo) -> None:
    """Only the two scope reasons (plus their status restatement) are survivable.

    `_is_scope_sanitizable` admits exactly those — anything else, and the
    chunk refuses exactly as before.
    """
    candidate = _scope_plan(repo, (_SCOPE_A, _SCOPE_B))
    _stage_fragment(
        candidate,
        _scope_fragment(("worked/x/graph.json",)),
        (_SCOPE_A, _SCOPE_B),
        reasons=(
            "fragment-source-scope-mismatch",
            "fragment-source-coverage-mismatch",
            "some-other-reason",
        ),
    )
    with pytest.raises(ValueError, match="run-reason:some-other-reason"):
        merge.assemble(repo, candidate, "corpus-probe")


def test_a_declared_file_left_at_zero_nodes_after_exclusion_still_refuses(repo) -> None:
    """The omission direction.

    Excluding the out-of-scope node cannot resurrect a declared file the
    model never produced a single node for.
    """
    candidate = _scope_plan(repo, (_SCOPE_A, _SCOPE_B))
    _stage_fragment(candidate, _scope_fragment_omits_b("worked/x/graph.json"), (_SCOPE_A, _SCOPE_B))
    with pytest.raises(ValueError, match=f"scope-exclusion-empties-declared-file:{_SCOPE_B}"):
        merge.assemble(repo, candidate, "corpus-probe")


def test_merge_main_reports_the_scope_exclusion_it_made(repo, capsys) -> None:
    """The CLI summary names the exclusion, not just the arithmetic that survived it."""
    candidate = _scope_plan(repo, (_SCOPE_A, _SCOPE_B))
    _stage_fragment(candidate, _scope_fragment(("worked/x/graph.json",)), (_SCOPE_A, _SCOPE_B))
    assert merge.merge_main(repo, ["corpus-probe", str(candidate)]) == 0
    out = capsys.readouterr().out
    assert "9 nodes, 1 edges, 1 hyperedges" in out
    assert "chunk 0001: excluded 1/10 out-of-scope node(s) (10.0%)" in out
    assert "chunk-0001-scope-exclusions.json" in out


@pytest.mark.parametrize(
    ("bad_id", "expected_reason"),
    [
        (None, "semantic-node-identity-invalid"),
        ("readme_1", "duplicate-semantic-node-identity"),
    ],
    ids=["non-string-id", "id-collides-with-an-in-scope-node"],
)
def test_a_malformed_node_id_refuses_upstream_and_never_reaches_sanitization(
    repo, bad_id: object, expected_reason: str
) -> None:
    """Both reaching cases for "exclusion by id mishandles a node" — REFUSED upstream.

    Read in isolation, deriving `kept_nodes` from an id set rather than from the
    predicate that built `excluded_nodes` is wrong in two opposite directions: a
    node with no string `id` would be COUNTED as excluded and then KEPT (counts
    and bytes diverge), and an in-scope node sharing an id with an excluded one
    would be DROPPED (silent loss, under-counted). The cold lane on `0e088a04`
    raised the first and argued the `emptied` guard made the second impossible.

    Neither is reachable end-to-end, and this test is how that was established
    rather than reasoned: staging validates node identity first and emits a
    reason that is NOT one of the two survivable scope reasons, so such a
    fragment refuses before `_sanitize_scope` runs at all.
    `probes-need-a-control-arm.md` rule 9 — "unreachable by construction" is
    earned by building the reaching case and watching it be rejected, never by a
    chain of true premises. Both cases were built; both were rejected.

    The fix in `_sanitize_scope` stands anyway, because it costs nothing and
    makes the two lists exact complements by construction instead of by
    coincidence — but it is a latent-trap removal, not a live-bug fix, and this
    test is what stops the next reader believing otherwise or "simplifying" the
    predicate back to an id lookup.
    """
    out_of_scope = "worked/x/graph.json"
    fragment = _scope_fragment((out_of_scope,))
    nodes = fragment["nodes"]
    assert isinstance(nodes, list)
    nodes[-1] = {**nodes[-1], "id": bad_id}

    candidate = _scope_plan(repo, (_SCOPE_A, _SCOPE_B))
    _stage_fragment(candidate, fragment, (_SCOPE_A, _SCOPE_B))

    with pytest.raises(ValueError, match=expected_reason):
        merge.assemble(repo, candidate, "corpus-probe")
