# Copyright (c) 2026 Raymond Manaloto
"""Behavioral tests for the reusable Graphify operation receipt."""

from __future__ import annotations

import pytest
from kb_setup.graphify_health import (
    APPROVED_METADATA_ZERO_NODE_WARNING,
    GraphifyEvidence,
    GraphifyOperation,
    GraphifyState,
    IncompleteGraphifyOperationError,
    SourceCoveragePolicy,
    assess,
    require_complete,
)


def test_clean_query_is_complete() -> None:
    receipt = assess(GraphifyOperation.QUERY, GraphifyEvidence(observed=True, stdout="answer\n"))
    assert receipt.state is GraphifyState.COMPLETE
    assert receipt.reasons == ()


@pytest.mark.parametrize("stderr", ["SyntaxWarning: invalid escape sequence", "coverage reduced"])
def test_success_with_stderr_is_incomplete(stderr: str) -> None:
    receipt = assess(
        GraphifyOperation.QUERY,
        GraphifyEvidence(observed=True, stdout="answer\n", stderr=stderr),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "stderr" in receipt.reasons


def test_fully_accounted_stderr_is_retained_with_classification() -> None:
    warning = "upstream zero-node warning"
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr=warning,
            residual_stderr="",
            approved_classifications=(APPROVED_METADATA_ZERO_NODE_WARNING,),
        ),
    )
    assert receipt.state is GraphifyState.COMPLETE
    assert receipt.stderr == warning
    assert receipt.approved_classifications == (APPROVED_METADATA_ZERO_NODE_WARNING,)


def test_classification_token_alone_never_approves_stderr() -> None:
    """The token records WHY something was approved; it is not itself approval.

    Before #328 this shape passed: one recognised token approved everything the
    subprocess printed, so a second, unrelated warning rode in on the first one's
    approval. Approval is now per warning, and an empty residual is the only
    thing that clears stderr.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr="upstream zero-node warning\nan entirely different warning",
            approved_classifications=(APPROVED_METADATA_ZERO_NODE_WARNING,),
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "stderr" in receipt.reasons


def test_residual_stderr_blocks_and_is_named_in_the_failure() -> None:
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr="  warning: reviewed\n  warning: NOT reviewed",
            residual_stderr="  warning: NOT reviewed",
            approved_classifications=(APPROVED_METADATA_ZERO_NODE_WARNING,),
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    with pytest.raises(IncompleteGraphifyOperationError) as raised:
        require_complete(receipt)
    # The reason is one word; the message has to name WHICH line blocked, or a
    # reader has to re-run the build to find out.
    assert "NOT reviewed" in str(raised.value)
    assert "warning: reviewed" not in str(raised.value)


def test_extract_refuses_unclassified_zero_node_and_partial_coverage() -> None:
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
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


def test_query_partial_count_banner_is_incomplete() -> None:
    receipt = assess(
        GraphifyOperation.QUERY,
        GraphifyEvidence(observed=True, stdout="PARTIAL: 278/562 nodes\n"),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "partial-result" in receipt.reasons


def test_coverage_policy_allows_declared_optional_gaps_only() -> None:
    policy = SourceCoveragePolicy(
        required_paths=("mise.toml", "Dockerfile"),
        optional_unclassified_paths=("CHANGELOG.legacy",),
        optional_zero_node_paths=("empty.json",),
    )
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            coverage_policy=policy,
            unclassified_paths=("CHANGELOG.legacy",),
            zero_node_paths=("empty.json",),
        ),
    )
    assert receipt.state is GraphifyState.COMPLETE


def test_coverage_policy_allows_only_declared_ignored_paths() -> None:
    reviewed = assess(
        GraphifyOperation.DETECT,
        GraphifyEvidence(
            observed=True,
            ignored_paths=("docs/superpowers",),
            coverage_policy=SourceCoveragePolicy(
                optional_ignored_paths=("docs/superpowers",),
            ),
        ),
    )
    changed = assess(
        GraphifyOperation.DETECT,
        GraphifyEvidence(
            observed=True,
            ignored_paths=("docs/superpowers", "new-ignored"),
            coverage_policy=SourceCoveragePolicy(
                optional_ignored_paths=("docs/superpowers",),
            ),
        ),
    )

    assert reviewed.state is GraphifyState.COMPLETE
    assert changed.state is GraphifyState.INCOMPLETE
    assert changed.reasons == ("ignored-paths",)


def test_required_ignored_path_is_never_allowlisted() -> None:
    receipt = assess(
        GraphifyOperation.DETECT,
        GraphifyEvidence(
            observed=True,
            ignored_paths=("mise.toml",),
            coverage_policy=SourceCoveragePolicy(
                required_paths=("mise.toml",),
                optional_ignored_paths=("mise.toml",),
            ),
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert receipt.reasons == ("required-source-ignored",)


def test_required_unsupported_source_is_never_silently_ignored() -> None:
    policy = SourceCoveragePolicy(required_paths=("mise.toml", "Dockerfile"))
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            coverage_policy=policy,
            unclassified_paths=("mise.toml", "Dockerfile"),
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "required-source-unclassified" in receipt.reasons


def test_receipt_retains_bounded_source_qualified_paths() -> None:
    paths = tuple(f"deep/path/{index}-{'x' * 200}.unknown" for index in range(30))
    receipt = assess(
        GraphifyOperation.DETECT,
        GraphifyEvidence(
            observed=True,
            source_name="hostile-source",
            unclassified_files=len(paths),
            unclassified_paths=paths,
        ),
    )

    assert receipt.source_name == "hostile-source"
    assert len(receipt.unclassified_paths) == 12
    assert all(len(path) <= 160 for path in receipt.unclassified_paths)


def test_deep_reflection_artifact_and_scope_expectations_fail_closed() -> None:
    receipt = assess(
        GraphifyOperation.BUILD,
        GraphifyEvidence(
            observed=True,
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
    receipt = assess(GraphifyOperation.ARTIFACT, GraphifyEvidence(observed=True, returncode=2))
    assert receipt.state is GraphifyState.FAILED
    with pytest.raises(IncompleteGraphifyOperationError, match="artifact failed"):
        require_complete(receipt)


@pytest.mark.parametrize("operation", list(GraphifyOperation))
def test_missing_evidence_is_incomplete_for_every_operation(
    operation: GraphifyOperation,
) -> None:
    receipt = assess(operation)
    assert receipt.state is GraphifyState.INCOMPLETE
    assert receipt.reasons == ("evidence-missing",)
