# Copyright (c) 2026 Raymond Manaloto
"""Behavioral tests for the reusable Graphify operation receipt."""

from __future__ import annotations

import pytest
from kb_setup.graphify_health import (
    GraphifyEvidence,
    GraphifyOperation,
    GraphifyState,
    IncompleteGraphifyOperationError,
    SourceCoveragePolicy,
    assess,
    require_complete,
)


def test_clean_query_is_complete() -> None:
    receipt = assess(GraphifyOperation.QUERY, GraphifyEvidence(stdout="answer\n"))
    assert receipt.state is GraphifyState.COMPLETE
    assert receipt.reasons == ()


@pytest.mark.parametrize("stderr", ["SyntaxWarning: invalid escape sequence", "coverage reduced"])
def test_success_with_stderr_is_incomplete(stderr: str) -> None:
    receipt = assess(GraphifyOperation.QUERY, GraphifyEvidence(stdout="answer\n", stderr=stderr))
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "stderr" in receipt.reasons


def test_extract_refuses_unclassified_zero_node_and_partial_coverage() -> None:
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            detected_sources=100,
            extracted_sources=45,
            unclassified_files=54,
            zero_node_sources=11,
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert set(receipt.reasons) >= {
        "source-coverage-partial",
        "unclassified-files",
        "zero-node-sources",
    }


def test_coverage_policy_allows_declared_optional_gaps_only() -> None:
    policy = SourceCoveragePolicy(
        required_paths=("mise.toml", "Dockerfile"),
        optional_unclassified_paths=("CHANGELOG.legacy",),
        optional_zero_node_paths=("empty.json",),
    )
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            coverage_policy=policy,
            unclassified_paths=("CHANGELOG.legacy",),
            zero_node_paths=("empty.json",),
        ),
    )
    assert receipt.state is GraphifyState.COMPLETE


def test_required_unsupported_source_is_never_silently_ignored() -> None:
    policy = SourceCoveragePolicy(required_paths=("mise.toml", "Dockerfile"))
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            coverage_policy=policy,
            unclassified_paths=("mise.toml", "Dockerfile"),
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "required-source-unclassified" in receipt.reasons


def test_deep_reflection_artifact_and_scope_expectations_fail_closed() -> None:
    receipt = assess(
        GraphifyOperation.BUILD,
        GraphifyEvidence(
            mode="ast",
            deep_required=True,
            reflection_expected=True,
            reflection_produced=False,
            expected_artifacts=("graph.json", "wiki"),
            produced_artifacts=("graph.json",),
            expected_scope="corpus",
            observed_scope="study",
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert set(receipt.reasons) >= {
        "deep-extraction-missing",
        "reflection-missing",
        "artifacts-partial",
        "source-scope-mismatch",
    }


def test_nonzero_operation_is_failed_and_require_complete_raises() -> None:
    receipt = assess(GraphifyOperation.ARTIFACT, GraphifyEvidence(returncode=2))
    assert receipt.state is GraphifyState.FAILED
    with pytest.raises(IncompleteGraphifyOperationError, match="artifact failed"):
        require_complete(receipt)
