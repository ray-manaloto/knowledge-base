# Copyright (c) 2026 Raymond Manaloto
"""Public controls for the Graphify-only deterministic baseline."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import msgspec
import pytest
from kb_setup import graph, graphify_baseline

_COMMIT = "7fe58b0b0f3873be9a21c30106b8b8527c353aa6"
_TREE = "15ca81a8dbd3ded7083c4b573197140e62e95fcc"
_REVIEWED_SHA = "f" * 64
_LPK_PATH = "tests/fixtures/sample.lpk"
_LPK_SHA = "d35ab7cfc6b30910020239b7389a4e732b5545269fd4b1cd43d7459aa2c40e1f"
_LPK_BYTES = b"""<?xml version="1.0" encoding="UTF-8"?>
<CONFIG>
  <Package Version="5">
    <Name Value="SamplePackage"/>
    <Description Value="A sample Lazarus package"/>
    <Files Count="2">
      <Item1>
        <Filename Value="sample.pas"/>
        <UnitName Value="sample"/>
      </Item1>
      <Item2>
        <Filename Value="sampleutils.pas"/>
        <UnitName Value="sampleutils"/>
      </Item2>
    </Files>
    <RequiredPkgs Count="2">
      <Item1>
        <PackageName Value="FCL"/>
      </Item1>
      <Item2>
        <PackageName Value="LCL"/>
      </Item2>
    </RequiredPkgs>
  </Package>
</CONFIG>
"""
_LPK_COLLISION_ID = "tests_fixtures_sample_lpk_tests_fixtures_sample"
_LPK_PACKAGE_ID = "tests_fixtures_sample_samplepackage"
_LPK_FILE_ID = _LPK_COLLISION_ID
_PAS_FILE_ID = "tests_fixtures_sample_pas_tests_fixtures_sample"
_METADATA_PATH = "tests/fixtures/extraction.json"
_METADATA_SHA = "e" * 64
_FIXTURE_AUTHORITIES: dict[Path, graphify_baseline.BaselineAuthority] = {}


def _write_public_candidate(root: Path) -> Path:
    root.mkdir()
    control_reasons = {
        "clean": [],
        "unknown-file": ["unclassified-files", "unknown.issue299"],
        "changed-reviewed-file": ["disposition-evidence-mismatch:.dockerignore"],
        "new-ignored-tracked-path": ["disposition-evidence-mismatch:docs/superpowers"],
        "post-admission-snapshot-drift": ["source-snapshot-drift"],
    }
    payload_objects = {
        "ast-graph.json": {
            "nodes": [{"id": "n"}],
            "links": [],
            "hyperedges": [],
            "built_at_commit": _COMMIT,
        },
        "source-census.json": {
            "schema_version": 1,
            "state": "complete",
            "total_sources": 1,
            "status_counts": [["complete", 1]],
            "category_counts": [],
            "integrity_errors": [],
            "sources": [
                {
                    "source": "graphify",
                    "kind": "code",
                    "status": "complete",
                    "declared_pin": _COMMIT,
                    "resolved_commit": _COMMIT,
                    "tree_digest": _TREE,
                    "detected_count": 1,
                    "unclassified_count": 1,
                    "ignored_count": 0,
                    "unclassified": [
                        {
                            "path": ".dockerignore",
                            "sha256": _REVIEWED_SHA,
                            "size": 1,
                            "file_type": "regular",
                        }
                    ],
                    "ignored": [],
                }
            ],
        },
        "source-manifest.json": {
            "schema_version": 1,
            "source": "graphify",
            "commit": _COMMIT,
            "tree": _TREE,
            "members": [
                {
                    "path": ".dockerignore",
                    "mode": "100644",
                    "git_object": "a" * 40,
                    "sha256": _REVIEWED_SHA,
                    "size": 1,
                }
            ],
        },
        "build-receipt.json": {
            "schema_version": 1,
            "status": "complete",
            "source_commit": _COMMIT,
            "source_tree": _TREE,
            "runtime_version": "0.9.42",
            "detected_count": 1,
            "extracted_count": 1,
            "node_count": 1,
            "edge_count": 0,
            "hyperedge_count": 0,
            "reviewed_metadata_paths": [],
            "zero_node_paths": [],
            "excluded_paths": [],
            "compatibility_corrections": [],
            "approved_classifications": [],
            "warnings": [],
        },
        "health.json": {
            "schema_version": 1,
            "state": "complete",
            "source": "graphify",
            "source_commit": _COMMIT,
            "source_tree": _TREE,
            "warnings": [],
        },
        "runtime.json": {
            "schema_version": 1,
            "version": "0.9.42",
            "cli_version": "0.9.42",
            "sdk_version": "0.9.42",
            "executable": ".venv/bin/graphify",
            "sdk_fingerprint_sha256": (
                "b10406f90fe7c369fc1396991679f6e4490e59f9351332c30b9fe2216f071157"
            ),
            "wheel_sha256": ("d87bec57d5dbca1203ce719f4b4afb83ae5eb6cea1b4af2d62d0c10c1c3e26e6"),
            "sdist_sha256": ("a45ff2d9517340a429d8e74a7dc7a74062d1bbc18019f26ec62b98b03863eb1b"),
        },
        "controls.json": {
            "schema_version": 1,
            "state": "complete",
            "source_commit": _COMMIT,
            "source_tree": _TREE,
            "cases": [
                {
                    "name": name,
                    "expected": "complete" if name == "clean" else "failed",
                    "observed": "complete" if name == "clean" else "failed",
                    "reasons": reasons,
                }
                for name, reasons in control_reasons.items()
            ],
        },
        "dispositions.json": {
            "schema_version": 1,
            "source": "graphify",
            "source_ref": "v0.9.42",
            "source_commit": _COMMIT,
            "source_tree": _TREE,
            "entries": [
                {
                    "path": ".dockerignore",
                    "kind": "unsupported-file",
                    "reason": "reviewed fixture",
                    "sha256": _REVIEWED_SHA,
                    "size": 1,
                    "file_type": "regular",
                }
            ],
        },
    }
    payloads = {
        name: (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
        for name, payload in payload_objects.items()
    }
    for name, raw in payloads.items():
        (root / name).write_bytes(raw)
    members = [
        {
            "name": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        }
        for name, raw in sorted(payloads.items())
    ]
    manifest = {
        "schema_id": "graphify-deterministic-baseline/v0",
        "source": "graphify",
        "source_ref": "v0.9.42",
        "source_commit": _COMMIT,
        "source_tree": _TREE,
        "catalog_sha256": hashlib.sha256(payloads["dispositions.json"]).hexdigest(),
        "members": members,
        "warnings": [],
        "semantic_evidence_present": False,
        "release_evidence_present": False,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    source_manifest_sha256 = hashlib.sha256(payloads["source-manifest.json"]).hexdigest()
    _FIXTURE_AUTHORITIES[root] = graphify_baseline.BaselineAuthority(
        source_ref="v0.9.42",
        source_commit=_COMMIT,
        source_tree=_TREE,
        catalog_sha256=hashlib.sha256(payloads["dispositions.json"]).hexdigest(),
        source_manifest_sha256=source_manifest_sha256,
        detected_count=1,
        extracted_count=1,
    )
    return root


def _verify_fixture_candidate(candidate: Path) -> graphify_baseline.BaselineVerification:
    return graphify_baseline._verify_candidate(candidate, _FIXTURE_AUTHORITIES[candidate])


def _refresh_fixture_authority(candidate: Path) -> None:
    manifest = json.loads((candidate / "manifest.json").read_bytes())
    members = manifest["members"]
    assert isinstance(members, list)
    source_member = next(item for item in members if item["name"] == "source-manifest.json")
    build = json.loads((candidate / "build-receipt.json").read_bytes())
    _FIXTURE_AUTHORITIES[candidate] = graphify_baseline.BaselineAuthority(
        source_ref="v0.9.42",
        source_commit=_COMMIT,
        source_tree=_TREE,
        catalog_sha256=str(manifest["catalog_sha256"]),
        source_manifest_sha256=str(source_member["sha256"]),
        detected_count=int(build["detected_count"]),
        extracted_count=int(build["extracted_count"]),
    )


def _rewrite_member(
    candidate: Path, name: str, mutate: Callable[[dict[str, object]], None]
) -> None:
    payload = json.loads((candidate / name).read_bytes())
    mutate(payload)
    _replace_member(candidate, name, payload)


def _replace_member(candidate: Path, name: str, payload: object) -> None:
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (candidate / name).write_bytes(raw)
    manifest = json.loads((candidate / "manifest.json").read_bytes())
    member = next(item for item in manifest["members"] if item["name"] == name)
    member["sha256"] = hashlib.sha256(raw).hexdigest()
    member["size"] = len(raw)
    if name == "dispositions.json":
        manifest["catalog_sha256"] = member["sha256"]
    (candidate / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _replace_census_source(payload: dict[str, object]) -> None:
    sources = payload["sources"]
    assert isinstance(sources, list)
    source = sources[0]
    assert isinstance(source, dict)
    source["source"] = "other"


def _clear_control_reasons(payload: dict[str, object]) -> None:
    cases = payload["cases"]
    assert isinstance(cases, list)
    for case in cases:
        assert isinstance(case, dict)
        case["reasons"] = []


def _append_payload_item(payload: dict[str, object], key: str, item: object) -> None:
    items = payload[key]
    assert isinstance(items, list)
    items.append(item)


def _remove_last_graph_node(payload: dict[str, object]) -> None:
    nodes = payload["nodes"]
    assert isinstance(nodes, list)
    nodes.pop()


def _remove_last_source_member(payload: dict[str, object]) -> None:
    members = payload["members"]
    assert isinstance(members, list)
    members.pop()


def _set_census_detected_count(payload: dict[str, object], count: int) -> None:
    sources = payload["sources"]
    assert isinstance(sources, list)
    source = sources[0]
    assert isinstance(source, dict)
    source["detected_count"] = count


def _add_lpk_correction_evidence(candidate: Path) -> None:
    _rewrite_member(
        candidate,
        "dispositions.json",
        lambda payload: _append_payload_item(
            payload,
            "entries",
            {
                "path": _LPK_PATH,
                "kind": "compatibility-correction",
                "reason": "Graphify 0.9.42 LPK file/unit identity collision",
                "sha256": _LPK_SHA,
                "size": len(_LPK_BYTES),
                "file_type": "regular",
                "extraction_disposition": "graphify-0.9.42-lpk-file-unit-identity",
            },
        ),
    )
    _rewrite_member(
        candidate,
        "source-manifest.json",
        lambda payload: _append_payload_item(
            payload,
            "members",
            {
                "path": _LPK_PATH,
                "mode": "100644",
                "git_object": "b" * 40,
                "sha256": _LPK_SHA,
                "size": len(_LPK_BYTES),
            },
        ),
    )
    _rewrite_member(
        candidate,
        "source-census.json",
        lambda payload: _set_census_detected_count(payload, 2),
    )
    _rewrite_member(
        candidate,
        "build-receipt.json",
        lambda payload: payload.update(
            {
                "detected_count": 2,
                "extracted_count": 2,
                "node_count": 4,
                "edge_count": 2,
                "compatibility_corrections": [
                    {
                        "name": "graphify-0.9.42-lpk-file-unit-identity",
                        "source_path": _LPK_PATH,
                        "source_sha256": _LPK_SHA,
                        "original_id": _LPK_COLLISION_ID,
                        "replacement_ids": [_LPK_FILE_ID, _PAS_FILE_ID],
                        "rewritten_edges": 1,
                    }
                ],
            }
        ),
    )
    _rewrite_member(
        candidate,
        "ast-graph.json",
        lambda payload: payload.update(
            {
                "nodes": [
                    {"id": "n"},
                    {
                        "_origin": "ast",
                        "file_type": "code",
                        "id": _LPK_FILE_ID,
                        "label": "sample.lpk",
                        "source_file": _LPK_PATH,
                        "source_location": "L1",
                    },
                    {
                        "_origin": "ast",
                        "file_type": "code",
                        "id": _PAS_FILE_ID,
                        "label": "sample.pas",
                        "source_file": "tests/fixtures/sample.pas",
                        "source_location": "L1",
                    },
                    {
                        "_origin": "ast",
                        "file_type": "code",
                        "id": _LPK_PACKAGE_ID,
                        "label": "SamplePackage",
                        "source_file": _LPK_PATH,
                        "source_location": "L1",
                    },
                ],
                "links": [
                    {
                        "_origin": "ast",
                        "confidence": "EXTRACTED",
                        "relation": "contains",
                        "source": _LPK_FILE_ID,
                        "source_file": _LPK_PATH,
                        "source_location": "L1",
                        "target": _LPK_PACKAGE_ID,
                        "weight": 1.0,
                        "confidence_score": 1.0,
                    },
                    {
                        "_origin": "ast",
                        "confidence": "EXTRACTED",
                        "relation": "contains",
                        "source": _LPK_PACKAGE_ID,
                        "source_file": _LPK_PATH,
                        "source_location": "L1",
                        "target": _PAS_FILE_ID,
                        "weight": 1.0,
                        "confidence_score": 1.0,
                    },
                ],
            }
        ),
    )
    _refresh_fixture_authority(candidate)


def _add_reviewed_metadata_evidence(candidate: Path) -> None:
    _rewrite_member(
        candidate,
        "dispositions.json",
        lambda payload: _append_payload_item(
            payload,
            "entries",
            {
                "path": _METADATA_PATH,
                "kind": "zero-node-file",
                "reason": "reviewed metadata-only extraction fixture",
                "sha256": _METADATA_SHA,
                "size": 1,
                "file_type": "regular",
                "extraction_disposition": "reviewed-metadata-only",
            },
        ),
    )
    _rewrite_member(
        candidate,
        "source-manifest.json",
        lambda payload: _append_payload_item(
            payload,
            "members",
            {
                "path": _METADATA_PATH,
                "mode": "100644",
                "git_object": "c" * 40,
                "sha256": _METADATA_SHA,
                "size": 1,
            },
        ),
    )
    _rewrite_member(
        candidate,
        "source-census.json",
        lambda payload: _set_census_detected_count(payload, 2),
    )
    _rewrite_member(
        candidate,
        "build-receipt.json",
        lambda payload: payload.update(
            {
                "detected_count": 2,
                "reviewed_metadata_paths": [_METADATA_PATH],
                "zero_node_paths": [],
                "approved_classifications": [],
            }
        ),
    )
    _refresh_fixture_authority(candidate)


def _lpk_correction_entry() -> graphify_baseline.SourceDisposition:
    return graphify_baseline.SourceDisposition(
        path=_LPK_PATH,
        kind=graphify_baseline.DispositionKind.COMPATIBILITY_CORRECTION,
        reason="Graphify 0.9.42 LPK file/unit identity collision",
        sha256=_LPK_SHA,
        size=len(_LPK_BYTES),
        file_type="regular",
        extraction_disposition="graphify-0.9.42-lpk-file-unit-identity",
    )


def _observed_lpk_collision_extraction() -> dict[str, object]:
    node_common = {
        "_origin": "ast",
        "file_type": "code",
        "id": _LPK_COLLISION_ID,
        "source_file": _LPK_PATH,
        "source_location": "L1",
    }
    edge_common = {
        "_origin": "ast",
        "confidence": "EXTRACTED",
        "relation": "contains",
        "source_file": _LPK_PATH,
        "source_location": "L1",
        "weight": 1.0,
    }
    return {
        "nodes": [
            {**node_common, "label": "sample.lpk"},
            {**node_common, "label": "sample"},
            {
                "_origin": "ast",
                "file_type": "code",
                "id": _PAS_FILE_ID,
                "label": "sample.pas",
                "source_file": "tests/fixtures/sample.pas",
                "source_location": "L1",
            },
        ],
        "edges": [
            {**edge_common, "source": _LPK_COLLISION_ID, "target": _LPK_PACKAGE_ID},
            {**edge_common, "source": _LPK_PACKAGE_ID, "target": _LPK_COLLISION_ID},
        ],
        "failed_sources": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }


def _write_exact_lpk(root: Path) -> None:
    path = root / _LPK_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(_LPK_BYTES)


def test_highest_public_verifier_reports_only_deliberately_absent_phases(
    tmp_path: Path,
) -> None:
    candidate = _write_public_candidate(tmp_path / "candidate")

    receipt = _verify_fixture_candidate(candidate)

    assert receipt.state is graphify_baseline.BaselineState.INCOMPLETE
    assert receipt.deterministic_complete
    assert receipt.reasons == ("semantic-evidence-missing", "release-evidence-missing")


def test_highest_public_verifier_distinguishes_missing_corrupt_and_digest_drift(
    tmp_path: Path,
) -> None:
    missing = _write_public_candidate(tmp_path / "missing")
    (missing / "health.json").unlink()
    missing_receipt = _verify_fixture_candidate(missing)

    corrupt = _write_public_candidate(tmp_path / "corrupt")
    (corrupt / "ast-graph.json").write_text("not-json\n", encoding="utf-8")
    corrupt_receipt = _verify_fixture_candidate(corrupt)

    assert missing_receipt.state is graphify_baseline.BaselineState.FAILED
    assert missing_receipt.reasons == ("member-missing:health.json",)
    assert corrupt_receipt.state is graphify_baseline.BaselineState.FAILED
    assert corrupt_receipt.reasons == (
        "member-size-mismatch:ast-graph.json",
        "member-digest-mismatch:ast-graph.json",
        "member-corrupt:ast-graph.json",
    )


def test_highest_public_verifier_keeps_failure_classes_distinct(tmp_path: Path) -> None:
    zero = _write_public_candidate(tmp_path / "zero")
    _rewrite_member(zero, "ast-graph.json", lambda payload: payload.__setitem__("nodes", []))
    version = _write_public_candidate(tmp_path / "version")
    _rewrite_member(
        version,
        "runtime.json",
        lambda payload: payload.__setitem__("sdk_version", "0.9.41"),
    )
    scope = _write_public_candidate(tmp_path / "scope")
    _rewrite_member(
        scope,
        "source-census.json",
        _replace_census_source,
    )
    stale = _write_public_candidate(tmp_path / "stale")
    _rewrite_member(
        stale,
        "health.json",
        lambda payload: payload.__setitem__("source_commit", "e" * 40),
    )
    truncated = _write_public_candidate(tmp_path / "truncated")
    manifest = json.loads((truncated / "manifest.json").read_bytes())
    manifest["warnings"] = ["truncated extractor response"]
    (truncated / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    assert "zero-node-ast-graph" in _verify_fixture_candidate(zero).reasons
    assert "runtime-version-drift" in _verify_fixture_candidate(version).reasons
    assert "source-census-scope-mismatch" in _verify_fixture_candidate(scope).reasons
    assert "source-identity-mismatch:health.json" in _verify_fixture_candidate(stale).reasons
    assert _verify_fixture_candidate(truncated).reasons == (
        "warning-bearing",
        "truncated",
    )


@pytest.mark.parametrize(
    "name",
    [
        "ast-graph.json",
        "build-receipt.json",
        "runtime.json",
        "health.json",
        "source-manifest.json",
    ],
)
def test_public_verifier_rejects_rehashed_non_object_members(tmp_path: Path, name: str) -> None:
    candidate = _write_public_candidate(tmp_path / name.removesuffix(".json"))
    _replace_member(candidate, name, [])

    receipt = _verify_fixture_candidate(candidate)

    assert receipt.state is graphify_baseline.BaselineState.FAILED
    assert f"member-schema-mismatch:{name}" in receipt.reasons


def test_public_verifier_reconciles_graph_counts_and_catalog_bytes(tmp_path: Path) -> None:
    counts = _write_public_candidate(tmp_path / "counts")
    _rewrite_member(
        counts,
        "build-receipt.json",
        lambda payload: payload.__setitem__("node_count", 2),
    )
    catalog = _write_public_candidate(tmp_path / "catalog")
    _rewrite_member(
        catalog,
        "dispositions.json",
        lambda payload: payload.__setitem__("entries", []),
    )

    assert "graph-build-count-mismatch" in _verify_fixture_candidate(counts).reasons
    catalog_reasons = _verify_fixture_candidate(catalog).reasons
    assert "catalog-unclassified-mismatch" in catalog_reasons


@pytest.mark.parametrize("member", ["nodes", "links", "hyperedges"])
def test_public_verifier_rejects_rehashed_non_object_graph_members(
    tmp_path: Path, member: str
) -> None:
    candidate = _write_public_candidate(tmp_path / member)
    _rewrite_member(
        candidate,
        "ast-graph.json",
        lambda payload: _append_payload_item(payload, member, 7),
    )
    count_key = {"nodes": "node_count", "links": "edge_count", "hyperedges": "hyperedge_count"}[
        member
    ]
    _rewrite_member(
        candidate,
        "build-receipt.json",
        lambda payload: payload.__setitem__(count_key, 2 if member == "nodes" else 1),
    )

    receipt = _verify_fixture_candidate(candidate)

    assert "ast-graph-schema-mismatch" in receipt.reasons


def test_public_verifier_rejects_coherently_rehashed_authority_drift(tmp_path: Path) -> None:
    candidate = _write_public_candidate(tmp_path / "candidate")
    _rewrite_member(
        candidate,
        "dispositions.json",
        lambda payload: payload.__setitem__("source_commit", "1" * 40),
    )
    _rewrite_member(
        candidate,
        "source-manifest.json",
        lambda payload: payload.__setitem__("commit", "1" * 40),
    )
    manifest = json.loads((candidate / "manifest.json").read_bytes())
    manifest["source_commit"] = "1" * 40
    (candidate / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    receipt = _verify_fixture_candidate(candidate)

    assert "authority-source-commit-mismatch" in receipt.reasons
    assert "authority-catalog-mismatch" in receipt.reasons
    assert "authority-source-manifest-mismatch" in receipt.reasons


def test_public_verifier_rejects_rehashed_non_catalog_source_manifest_omission(
    tmp_path: Path,
) -> None:
    candidate = _write_public_candidate(tmp_path / "candidate")
    _rewrite_member(
        candidate,
        "source-manifest.json",
        lambda payload: _append_payload_item(
            payload,
            "members",
            {
                "path": "README.md",
                "mode": "100644",
                "git_object": "d" * 40,
                "sha256": "d" * 64,
                "size": 1,
            },
        ),
    )
    _refresh_fixture_authority(candidate)
    _rewrite_member(
        candidate,
        "source-manifest.json",
        _remove_last_source_member,
    )

    receipt = _verify_fixture_candidate(candidate)

    assert "authority-source-manifest-mismatch" in receipt.reasons


def test_public_verifier_certifies_reviewed_metadata_as_pre_extraction_exclusion(
    tmp_path: Path,
) -> None:
    candidate = _write_public_candidate(tmp_path / "candidate")
    _add_reviewed_metadata_evidence(candidate)

    receipt = _verify_fixture_candidate(candidate)

    assert receipt.deterministic_complete
    assert receipt.reasons == ("semantic-evidence-missing", "release-evidence-missing")


@pytest.mark.parametrize(
    ("member", "key", "value", "reason"),
    [
        (
            "runtime.json",
            "executable",
            "/usr/local/bin/fake-graphify",
            "runtime-executable-drift",
        ),
        ("build-receipt.json", "runtime_version", "0.9.41", "build-runtime-version-drift"),
        (
            "build-receipt.json",
            "approved_classifications",
            ["metadata-only"],
            "build-approved-classifications",
        ),
        ("build-receipt.json", "detected_count", 999, "build-source-count-mismatch"),
        ("build-receipt.json", "extracted_count", 999, "build-source-count-mismatch"),
    ],
)
def test_public_verifier_rejects_rehashed_runtime_and_build_claim_drift(
    tmp_path: Path,
    member: str,
    key: str,
    value: object,
    reason: str,
) -> None:
    candidate = _write_public_candidate(tmp_path / key)
    _rewrite_member(
        candidate,
        member,
        lambda payload: payload.__setitem__(key, value),
    )

    receipt = _verify_fixture_candidate(candidate)

    assert reason in receipt.reasons


def test_public_verifier_rejects_duplicate_reviewed_metadata_receipt_path(
    tmp_path: Path,
) -> None:
    candidate = _write_public_candidate(tmp_path / "candidate")
    _add_reviewed_metadata_evidence(candidate)
    _rewrite_member(
        candidate,
        "build-receipt.json",
        lambda payload: _append_payload_item(payload, "reviewed_metadata_paths", _METADATA_PATH),
    )

    receipt = _verify_fixture_candidate(candidate)

    assert "catalog-reviewed-metadata-duplicate" in receipt.reasons


def test_public_verifier_rejects_rehashed_empty_edge_with_reconciled_count(
    tmp_path: Path,
) -> None:
    candidate = _write_public_candidate(tmp_path / "candidate")
    _rewrite_member(
        candidate,
        "ast-graph.json",
        lambda payload: _append_payload_item(payload, "links", {}),
    )
    _rewrite_member(
        candidate,
        "build-receipt.json",
        lambda payload: payload.__setitem__("edge_count", 1),
    )

    receipt = _verify_fixture_candidate(candidate)

    assert "ast-graph-schema-mismatch" in receipt.reasons


def test_public_verifier_requires_exact_runtime_ref_and_control_evidence(
    tmp_path: Path,
) -> None:
    runtime = _write_public_candidate(tmp_path / "runtime")
    _rewrite_member(
        runtime,
        "runtime.json",
        lambda payload: payload.__setitem__("wheel_sha256", "0" * 64),
    )
    source_ref = _write_public_candidate(tmp_path / "source-ref")
    manifest = json.loads((source_ref / "manifest.json").read_bytes())
    manifest["source_ref"] = "v0.9.41"
    (source_ref / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    controls = _write_public_candidate(tmp_path / "controls")
    _rewrite_member(
        controls,
        "controls.json",
        _clear_control_reasons,
    )

    assert "runtime-identity-drift:wheel_sha256" in _verify_fixture_candidate(runtime).reasons
    assert "source-ref-mismatch" in _verify_fixture_candidate(source_ref).reasons
    assert "controls-incomplete" in _verify_fixture_candidate(controls).reasons


def test_public_verifier_certifies_exact_lpk_compatibility_correction(tmp_path: Path) -> None:
    candidate = _write_public_candidate(tmp_path / "candidate")
    _add_lpk_correction_evidence(candidate)

    receipt = _verify_fixture_candidate(candidate)

    assert receipt.deterministic_complete
    assert receipt.reasons == ("semantic-evidence-missing", "release-evidence-missing")


def test_public_verifier_rejects_rehashed_missing_or_unproven_lpk_correction(
    tmp_path: Path,
) -> None:
    missing_receipt = _write_public_candidate(tmp_path / "missing-receipt")
    _add_lpk_correction_evidence(missing_receipt)
    _rewrite_member(
        missing_receipt,
        "build-receipt.json",
        lambda payload: payload.__setitem__("compatibility_corrections", []),
    )
    missing_entity = _write_public_candidate(tmp_path / "missing-entity")
    _add_lpk_correction_evidence(missing_entity)
    _rewrite_member(
        missing_entity,
        "ast-graph.json",
        _remove_last_graph_node,
    )
    _rewrite_member(
        missing_entity,
        "build-receipt.json",
        lambda payload: payload.__setitem__("node_count", 2),
    )

    assert "compatibility-correction-mismatch" in _verify_fixture_candidate(missing_receipt).reasons
    assert (
        "compatibility-correction-graph-mismatch"
        in _verify_fixture_candidate(missing_entity).reasons
    )


@pytest.mark.parametrize(
    "mutation",
    ["duplicate-node", "duplicate-edge", "wrong-relation", "wrong-provenance", "legacy-edge"],
)
def test_public_verifier_rejects_rehashed_lpk_proof_drift(tmp_path: Path, mutation: str) -> None:
    candidate = _write_public_candidate(tmp_path / mutation)
    _add_lpk_correction_evidence(candidate)
    graph_payload = json.loads((candidate / "ast-graph.json").read_bytes())
    nodes = graph_payload["nodes"]
    links = graph_payload["links"]
    assert isinstance(nodes, list)
    assert isinstance(links, list)
    if mutation == "duplicate-node":
        nodes.append(dict(nodes[1]))
    elif mutation == "duplicate-edge":
        links.append(dict(links[1]))
    elif mutation == "wrong-relation":
        links[1]["relation"] = "calls"
    elif mutation == "wrong-provenance":
        links[1]["confidence"] = "INFERRED"
    else:
        links.append({**links[1], "target": _LPK_FILE_ID})
    _replace_member(candidate, "ast-graph.json", graph_payload)
    _rewrite_member(
        candidate,
        "build-receipt.json",
        lambda payload: payload.update(
            {
                "node_count": len(nodes),
                "edge_count": len(links),
            }
        ),
    )

    receipt = _verify_fixture_candidate(candidate)

    assert "compatibility-correction-graph-mismatch" in receipt.reasons


def test_committed_graphify_disposition_catalog_is_typed_and_exact() -> None:
    repo = Path(__file__).parent.parent

    catalog = graphify_baseline.load_disposition_catalog(repo)

    assert catalog.source == "graphify"
    assert catalog.source_commit == "7fe58b0b0f3873be9a21c30106b8b8527c353aa6"
    assert catalog.source_tree == "15ca81a8dbd3ded7083c4b573197140e62e95fcc"
    assert len(catalog.entries) == 21
    assert (
        next(
            entry
            for entry in catalog.entries
            if entry.path == "worked/rsl-siege-manager/graph.json"
        ).kind
        is graphify_baseline.DispositionKind.EXCLUDED_AST_FIXTURE
    )
    assert (
        next(entry for entry in catalog.entries if entry.path == "tests/fixtures/sample.lpk").kind
        is graphify_baseline.DispositionKind.COMPATIBILITY_CORRECTION
    )
    assert {entry.path for entry in catalog.entries} == {
        ".dockerignore",
        ".gitattributes",
        ".gitignore",
        "Dockerfile",
        "LICENSE",
        "LICENSE-MIT",
        "NOTICE",
        "docs/superpowers",
        "tools/skillgen/fragments/dispatch/.gitkeep",
        "tools/skillgen/fragments/extra/.gitkeep",
        "tools/skillgen/platforms.toml",
        "uv.lock",
        "tests/fixtures/extraction.json",
        "tests/fixtures/sample.mcp.json",
        "worked/httpx/graph.json",
        "worked/karpathy-repos/graph.json",
        "worked/mixed-corpus/graph.json",
        "worked/rsl-siege-manager/graph.json",
        "tests/fixtures/sample.lpk",
        "tests/fixtures/sample.luau",
        "tests/fixtures/sample.dmf",
    }


def test_runtime_identity_binds_lock_cli_sdk_and_public_fingerprint() -> None:
    repo = Path(__file__).parent.parent

    identity = graphify_baseline.runtime_identity(repo)

    assert identity.version == "0.9.42"
    assert identity.cli_version == identity.sdk_version == identity.version
    assert identity.executable == ".venv/bin/graphify"
    assert identity.wheel_sha256 == (
        "d87bec57d5dbca1203ce719f4b4afb83ae5eb6cea1b4af2d62d0c10c1c3e26e6"
    )
    assert identity.sdist_sha256 == (
        "a45ff2d9517340a429d8e74a7dc7a74062d1bbc18019f26ec62b98b03863eb1b"
    )
    assert len(identity.sdk_fingerprint_sha256) == 64


def test_source_manifest_binds_every_git_blob_in_path_order(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.py").write_text("A = 1\n", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.txt").write_text("B\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", "a.py", "nested/b.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    manifest = graphify_baseline.source_manifest(tmp_path, commit=commit, tree=tree)

    assert [member.path for member in manifest.members] == ["a.py", "nested/b.txt"]
    assert [member.sha256 for member in manifest.members] == [
        "06edbcf4336165a271e6524025a6439c3caa3246fd0796f116772279707a5325",
        "c0cde77fa8fef97d476c10aad3d2d54fcc2f336140d073651c2dcccf1e379fd6",
    ]
    assert manifest.commit == commit
    assert manifest.tree == tree


def test_exact_graphify_0942_lpk_correction_preserves_both_entities_and_roles(
    tmp_path: Path,
) -> None:
    _write_exact_lpk(tmp_path)
    observed = _observed_lpk_collision_extraction()
    original = json.loads(json.dumps(observed))

    corrected, receipts = graphify_baseline.apply_compatibility_corrections(
        tmp_path,
        observed,
        (_lpk_correction_entry(),),
    )

    assert observed == original
    nodes = corrected["nodes"]
    edges = corrected["edges"]
    assert isinstance(nodes, list)
    assert isinstance(edges, list)
    assert {node["id"] for node in nodes} == {_LPK_FILE_ID, _PAS_FILE_ID}
    assert {(edge["source"], edge["target"]) for edge in edges} == {
        (_LPK_FILE_ID, _LPK_PACKAGE_ID),
        (_LPK_PACKAGE_ID, _PAS_FILE_ID),
    }
    assert receipts == (
        graphify_baseline.CompatibilityCorrection(
            name="graphify-0.9.42-lpk-file-unit-identity",
            source_path=_LPK_PATH,
            source_sha256=_LPK_SHA,
            original_id=_LPK_COLLISION_ID,
            replacement_ids=(_LPK_FILE_ID, _PAS_FILE_ID),
            rewritten_edges=1,
        ),
    )


@pytest.mark.parametrize(
    "mutation",
    ["changed-hash", "extra-collision", "wrong-labels", "wrong-roles", "edge-multiplicity"],
)
def test_graphify_0942_lpk_correction_fails_closed_on_observed_drift(
    tmp_path: Path, mutation: str
) -> None:
    _write_exact_lpk(tmp_path)
    extraction = _observed_lpk_collision_extraction()
    nodes = extraction["nodes"]
    edges = extraction["edges"]
    assert isinstance(nodes, list)
    assert isinstance(edges, list)
    if mutation == "changed-hash":
        (tmp_path / _LPK_PATH).write_bytes(_LPK_BYTES + b"\n")
    elif mutation == "extra-collision":
        nodes.append(dict(nodes[0]))
    elif mutation == "wrong-labels":
        nodes[1]["label"] = "other"
    elif mutation == "wrong-roles":
        edges[0]["target"] = "other"
    else:
        edges.append(dict(edges[0]))

    with pytest.raises(ValueError, match="compatibility-correction"):
        graphify_baseline.apply_compatibility_corrections(
            tmp_path,
            extraction,
            (_lpk_correction_entry(),),
        )


def test_graphify_0942_lpk_correction_rejects_already_fixed_upstream_shape(
    tmp_path: Path,
) -> None:
    _write_exact_lpk(tmp_path)
    extraction = _observed_lpk_collision_extraction()
    nodes = extraction["nodes"]
    edges = extraction["edges"]
    assert isinstance(nodes, list)
    assert isinstance(edges, list)
    nodes.pop(1)
    edges[1]["target"] = _PAS_FILE_ID

    with pytest.raises(ValueError, match="compatibility-correction-not-applicable"):
        graphify_baseline.apply_compatibility_corrections(
            tmp_path,
            extraction,
            (_lpk_correction_entry(),),
        )


def test_real_sdk_build_keeps_one_immutable_snapshot_and_emits_verifiable_candidate(
    tmp_path: Path,
) -> None:
    repo = Path(__file__).parent.parent
    source = tmp_path / "source"
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "sample.py").write_text(
        "def answer() -> int:\n    return 42\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(source), "add", "--", "sample.py"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    catalog = graphify_baseline.DispositionCatalog(
        source="graphify",
        source_commit=commit,
        source_tree=tree,
        entries=(),
    )
    source_inventory = graphify_baseline.source_manifest(source, commit=commit, tree=tree)
    authority = graphify_baseline.BaselineAuthority(
        source_ref=catalog.source_ref,
        source_commit=commit,
        source_tree=tree,
        catalog_sha256=hashlib.sha256(msgspec.json.encode(catalog) + b"\n").hexdigest(),
        source_manifest_sha256=hashlib.sha256(
            msgspec.json.encode(source_inventory) + b"\n"
        ).hexdigest(),
        detected_count=1,
        extracted_count=1,
    )
    output = tmp_path / "candidate"

    graphify_baseline.build_from_snapshot(
        source,
        output,
        inputs=graphify_baseline.BaselineBuildInputs(
            catalog=catalog,
            runtime=graphify_baseline.runtime_identity(repo),
            controls=graphify_baseline.ControlsReceipt(
                state="complete",
                source_commit=commit,
                source_tree=tree,
                cases=tuple(
                    graphify_baseline.ControlOutcome(
                        name=name,
                        expected=expected,
                        observed=expected,
                        reasons=reasons,
                    )
                    for name, expected, reasons in (
                        ("clean", "complete", ()),
                        (
                            "unknown-file",
                            "failed",
                            ("unclassified-files", "unknown.issue299"),
                        ),
                        (
                            "changed-reviewed-file",
                            "failed",
                            ("disposition-evidence-mismatch:.dockerignore",),
                        ),
                        (
                            "new-ignored-tracked-path",
                            "failed",
                            ("disposition-evidence-mismatch:docs/superpowers",),
                        ),
                        (
                            "post-admission-snapshot-drift",
                            "failed",
                            ("source-snapshot-drift",),
                        ),
                    )
                ),
            ),
            authority=authority,
        ),
    )

    receipt = graphify_baseline._verify_candidate(output, authority)
    assert receipt.state is graphify_baseline.BaselineState.INCOMPLETE
    assert receipt.deterministic_complete
    assert (
        subprocess.run(
            ["git", "-C", str(source), "status", "--porcelain=v1", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        == ""
    )


def test_disposition_catalog_binds_exact_observed_paths_and_current_bytes(tmp_path: Path) -> None:
    reviewed = tmp_path / "UNSUPPORTED"
    reviewed.write_text("reviewed\n", encoding="utf-8")
    observed = graph.SourcePathEvidence(
        path="UNSUPPORTED",
        sha256="a9f2d25d1f71f8065e2119e538bde8846570fcdad320388236e99d9e225c290d",
        size=9,
    )
    catalog = graphify_baseline.DispositionCatalog(
        source="graphify",
        source_commit="a" * 40,
        source_tree="b" * 40,
        entries=(
            graphify_baseline.SourceDisposition(
                path="UNSUPPORTED",
                kind=graphify_baseline.DispositionKind.UNSUPPORTED_FILE,
                reason="reviewed non-graph source metadata",
                sha256=observed.sha256 or "",
                size=9,
                file_type="regular",
            ),
        ),
    )

    clean = graphify_baseline.verify_dispositions(
        tmp_path,
        catalog,
        unclassified=(observed,),
        ignored=(),
    )
    assert clean.state is graphify_baseline.BaselineState.COMPLETE
    assert clean.reasons == ()

    reviewed.write_text("changed\n", encoding="utf-8")
    changed = graphify_baseline.verify_dispositions(
        tmp_path,
        catalog,
        unclassified=(observed,),
        ignored=(),
    )
    assert changed.state is graphify_baseline.BaselineState.FAILED
    assert changed.reasons == ("source-snapshot-drift:UNSUPPORTED",)


def test_disposition_catalog_fails_closed_on_new_removed_or_retyped_path(tmp_path: Path) -> None:
    reviewed = tmp_path / "UNSUPPORTED"
    reviewed.write_text("reviewed\n", encoding="utf-8")
    expected = graph.SourcePathEvidence(
        path="UNSUPPORTED",
        sha256="a9f2d25d1f71f8065e2119e538bde8846570fcdad320388236e99d9e225c290d",
        size=9,
    )
    catalog = graphify_baseline.DispositionCatalog(
        source="graphify",
        source_commit="a" * 40,
        source_tree="b" * 40,
        entries=(
            graphify_baseline.SourceDisposition(
                path="UNSUPPORTED",
                kind=graphify_baseline.DispositionKind.UNSUPPORTED_FILE,
                reason="reviewed non-graph source metadata",
                sha256=expected.sha256 or "",
                size=9,
                file_type="regular",
            ),
        ),
    )

    unknown = graph.SourcePathEvidence(
        path="NEW.unknown",
        sha256="c" * 64,
        size=1,
    )
    added = graphify_baseline.verify_dispositions(
        tmp_path,
        catalog,
        unclassified=(expected, unknown),
        ignored=(),
    )
    removed = graphify_baseline.verify_dispositions(
        tmp_path,
        catalog,
        unclassified=(),
        ignored=(),
    )
    retyped = graphify_baseline.verify_dispositions(
        tmp_path,
        catalog,
        unclassified=(),
        ignored=(expected,),
    )

    assert added.reasons == ("unexpected-disposition:unsupported-file:NEW.unknown",)
    assert removed.reasons == ("missing-disposition:unsupported-file:UNSUPPORTED",)
    assert retyped.reasons == (
        "missing-disposition:unsupported-file:UNSUPPORTED",
        "unexpected-disposition:ignored-tree:UNSUPPORTED",
    )
