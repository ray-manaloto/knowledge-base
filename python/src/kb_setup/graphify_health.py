# Copyright (c) 2026 Raymond Manaloto
"""Typed, fail-closed health receipts for Graphify operations."""

from __future__ import annotations

from enum import StrEnum

import msgspec


class GraphifyOperation(StrEnum):
    """Graphify lifecycle operations covered by the shared health contract."""

    HEALTH = "health"
    QUERY = "query"
    DETECT = "detect"
    EXTRACT = "extract"
    BUILD = "build"
    REFLECT = "reflect"
    ARTIFACT = "artifact"


class GraphifyState(StrEnum):
    """Whether an operation produced evidence safe for downstream use."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class GraphifyReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Serializable result retaining output, coverage, and integrity findings."""

    operation: GraphifyOperation
    state: GraphifyState
    returncode: int
    reasons: tuple[str, ...]
    stdout: str = ""
    stderr: str = ""
    detected_sources: int | None = None
    extracted_sources: int | None = None
    unclassified_files: int = 0
    zero_node_sources: int = 0
    mode: str | None = None
    expected_artifacts: tuple[str, ...] = ()
    produced_artifacts: tuple[str, ...] = ()
    expected_scope: str | None = None
    observed_scope: str | None = None


class SourceCoveragePolicy(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Explicit source-coverage boundary; required paths can never be allowlisted."""

    required_paths: tuple[str, ...] = ()
    optional_unclassified_paths: tuple[str, ...] = ()
    optional_zero_node_paths: tuple[str, ...] = ()


class IncompleteGraphifyOperationError(RuntimeError):
    """A Graphify receipt cannot authorize downstream work."""


class GraphifyEvidence(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Raw observations to classify for one Graphify operation."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    detected_sources: int | None = None
    extracted_sources: int | None = None
    unclassified_files: int = 0
    zero_node_sources: int = 0
    unclassified_paths: tuple[str, ...] = ()
    zero_node_paths: tuple[str, ...] = ()
    coverage_policy: SourceCoveragePolicy | None = None
    mode: str | None = None
    deep_required: bool = False
    reflection_expected: bool = False
    reflection_produced: bool = False
    expected_artifacts: tuple[str, ...] = ()
    produced_artifacts: tuple[str, ...] = ()
    expected_scope: str | None = None
    observed_scope: str | None = None


def _basic_reasons(evidence: GraphifyEvidence) -> list[str]:
    reasons: list[str] = []
    if evidence.stderr.strip():
        reasons.append("stderr")
    if "truncated" in f"{evidence.stdout}\n{evidence.stderr}".casefold():
        reasons.append("truncated")
    if (
        evidence.detected_sources is not None
        and evidence.extracted_sources is not None
        and evidence.extracted_sources < evidence.detected_sources
    ):
        reasons.append("source-coverage-partial")
    return reasons


def _coverage_reasons(evidence: GraphifyEvidence) -> list[str]:
    reasons: list[str] = []
    if evidence.coverage_policy is None:
        if evidence.unclassified_files or evidence.unclassified_paths:
            reasons.append("unclassified-files")
        if evidence.zero_node_sources or evidence.zero_node_paths:
            reasons.append("zero-node-sources")
    else:
        required = set(evidence.coverage_policy.required_paths)
        unclassified = set(evidence.unclassified_paths)
        zero_node = set(evidence.zero_node_paths)
        if required & unclassified:
            reasons.append("required-source-unclassified")
        if required & zero_node:
            reasons.append("required-source-zero-nodes")
        if unclassified - set(evidence.coverage_policy.optional_unclassified_paths):
            reasons.append("unclassified-files")
        if zero_node - set(evidence.coverage_policy.optional_zero_node_paths):
            reasons.append("zero-node-sources")
    return reasons


def _output_reasons(evidence: GraphifyEvidence) -> list[str]:
    reasons: list[str] = []
    if evidence.deep_required and evidence.mode != "deep":
        reasons.append("deep-extraction-missing")
    if evidence.reflection_expected and not evidence.reflection_produced:
        reasons.append("reflection-missing")
    if set(evidence.expected_artifacts) - set(evidence.produced_artifacts):
        reasons.append("artifacts-partial")
    if evidence.expected_scope is not None and evidence.observed_scope != evidence.expected_scope:
        reasons.append("source-scope-mismatch")
    return reasons


def assess(
    operation: GraphifyOperation,
    evidence: GraphifyEvidence | None = None,
) -> GraphifyReceipt:
    """Classify explicit Graphify evidence without converting unknowns into success."""
    evidence = evidence or GraphifyEvidence()
    reasons = [
        *_basic_reasons(evidence),
        *_coverage_reasons(evidence),
        *_output_reasons(evidence),
    ]

    state = GraphifyState.COMPLETE
    if evidence.returncode != 0:
        state = GraphifyState.FAILED
        reasons.insert(0, "nonzero-returncode")
    elif reasons:
        state = GraphifyState.INCOMPLETE
    return GraphifyReceipt(
        operation=operation,
        state=state,
        returncode=evidence.returncode,
        reasons=tuple(dict.fromkeys(reasons)),
        stdout=evidence.stdout,
        stderr=evidence.stderr,
        detected_sources=evidence.detected_sources,
        extracted_sources=evidence.extracted_sources,
        unclassified_files=evidence.unclassified_files,
        zero_node_sources=evidence.zero_node_sources,
        mode=evidence.mode,
        expected_artifacts=evidence.expected_artifacts,
        produced_artifacts=evidence.produced_artifacts,
        expected_scope=evidence.expected_scope,
        observed_scope=evidence.observed_scope,
    )


def require_complete(receipt: GraphifyReceipt) -> GraphifyReceipt:
    """Return a complete receipt or raise with its retained integrity reasons."""
    if receipt.state is not GraphifyState.COMPLETE:
        detail = ", ".join(receipt.reasons) or "unknown integrity failure"
        raise IncompleteGraphifyOperationError(
            f"Graphify {receipt.operation.value} failed closed ({receipt.state.value}): {detail}"
        )
    return receipt
