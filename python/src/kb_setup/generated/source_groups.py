# Copyright (c) 2026 Raymond Manaloto
"""Generated source-group models; edit the schema and rerun the generator."""

from enum import StrEnum
from typing import Annotated, Literal

from msgspec import Meta
from msgspec import Struct as _Struct


class Struct(_Struct, forbid_unknown_fields=True):
    """Generated source-group contract type."""


type EpochNs = Annotated[int, Meta(ge=0)]


type NullableEpochNs = EpochNs | None


type NullableNonNegativeInteger1 = Annotated[int, Meta(ge=0)]


type NullableNonNegativeInteger = NullableNonNegativeInteger1 | None


type NullableString = str | None


type CommitSha = Annotated[str, Meta(pattern="^[0-9a-f]{40}$")]


type NullableCommitSha = CommitSha | None


type RepoPath = Annotated[
    str, Meta(min_length=1, pattern="^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*//).+$")
]


type SourceWarning = Annotated[str, Meta(min_length=1)]


class Role(StrEnum):
    """Generated source-group enumeration."""

    REFERENCE_IMPLEMENTATION = "REFERENCE_IMPLEMENTATION"
    PRODUCTION_CONSUMER = "PRODUCTION_CONSUMER"
    EXPERIMENTAL_CONSUMER = "EXPERIMENTAL_CONSUMER"
    TOOLING_INTEGRATION = "TOOLING_INTEGRATION"
    RESEARCH_SOURCE = "RESEARCH_SOURCE"
    ALTERNATIVE_TECHNOLOGY = "ALTERNATIVE_TECHNOLOGY"


class SourceStatus(StrEnum):
    """Generated source-group enumeration."""

    DISCOVERED = "DISCOVERED"
    REVIEWING = "REVIEWING"
    LICENSE_REVIEW_REQUIRED = "LICENSE_REVIEW_REQUIRED"
    CANDIDATE = "CANDIDATE"
    ADMITTED = "ADMITTED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class Capability(StrEnum):
    """Generated source-group enumeration."""

    PROJECT_SETUP = "PROJECT_SETUP"
    INGEST = "INGEST"
    DEEP_EXTRACTION = "DEEP_EXTRACTION"
    REFLECTION = "REFLECTION"
    ARTIFACT_GENERATION = "ARTIFACT_GENERATION"
    ARTIFACT_CONSUMPTION = "ARTIFACT_CONSUMPTION"
    CODEBASE_UNDERSTANDING = "CODEBASE_UNDERSTANDING"
    TOPIC_CORRELATION = "TOPIC_CORRELATION"
    GOD_NODE_CORRELATION = "GOD_NODE_CORRELATION"
    SOURCE_REFRESH = "SOURCE_REFRESH"
    PIVOT_EVALUATION = "PIVOT_EVALUATION"


class EvidenceStage(StrEnum):
    """Generated source-group enumeration."""

    DECLARED = "DECLARED"
    CONFIGURED = "CONFIGURED"
    EXECUTED = "EXECUTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class CapabilityEvidence(Struct):
    """Generated source-group contract type."""

    capability: Capability
    stage: EvidenceStage
    path: RepoPath
    commit: CommitSha
    observed_at_ns: EpochNs
    summary: Annotated[str, Meta(min_length=1)]


class LicenseStatus(StrEnum):
    """Generated source-group enumeration."""

    UNKNOWN = "UNKNOWN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ALLOWED = "ALLOWED"
    RESTRICTED = "RESTRICTED"
    PROHIBITED = "PROHIBITED"


class LicenseEvidence(Struct):
    """Generated source-group contract type."""

    path: RepoPath
    commit: CommitSha


type SpdxId = Annotated[
    str, Meta(pattern="^[A-Za-z0-9][A-Za-z0-9.+-]*(?: WITH [A-Za-z0-9][A-Za-z0-9.+-]*)?$")
]


class License(Struct):
    """Generated source-group contract type."""

    status: LicenseStatus
    spdx_id: SpdxId | None
    evidence: list[LicenseEvidence]
    reviewed_at_ns: NullableEpochNs


class CurrentHead(Struct):
    """Generated source-group contract type."""

    commit: CommitSha
    observed_at_ns: EpochNs


class Repository(Struct):
    """Generated source-group contract type."""

    repo_id: Annotated[str, Meta(pattern="^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")]
    canonical_url: Annotated[
        str, Meta(pattern="^https://github\\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    ]
    ref: Annotated[str, Meta(min_length=1)]
    default_branch: Annotated[str, Meta(min_length=1)]
    reviewed_commit: NullableCommitSha
    current_head: CurrentHead | None
    is_fork: bool
    is_archived: bool
    is_vendor_mirror: bool


class GraphifyIgnorePolicy(StrEnum):
    """Generated source-group enumeration."""

    REQUIRE_AND_HONOR = "REQUIRE_AND_HONOR"
    HONOR_IF_PRESENT = "HONOR_IF_PRESENT"
    EXPLICIT_PATHS_ONLY = "EXPLICIT_PATHS_ONLY"


class PathSelection(Struct):
    """Generated source-group contract type."""

    include_paths: list[RepoPath]
    exclude_paths: list[RepoPath]
    graphifyignore_policy: GraphifyIgnorePolicy
    graphifyignore_path: RepoPath | None


class LifecycleTimestamps(Struct):
    """Generated source-group contract type."""

    discovered_at_ns: EpochNs
    last_reviewed_at_ns: NullableEpochNs
    last_status_change_at_ns: EpochNs


class SourceBudget(Struct):
    """Generated source-group contract type."""

    estimated_checkout_bytes: NullableNonNegativeInteger
    estimated_selected_files: NullableNonNegativeInteger
    estimated_ingest_seconds: NullableNonNegativeInteger


class SemanticBudget(Struct):
    """Generated source-group contract type."""

    estimated_input_tokens: NullableNonNegativeInteger
    max_output_tokens: NullableNonNegativeInteger
    estimated_deep_seconds: NullableNonNegativeInteger
    max_cost_usd_micros: NullableNonNegativeInteger


class ResourceBudgets(Struct):
    """Generated source-group contract type."""

    source: SourceBudget
    semantic: SemanticBudget


class RegistryAdmissionPolicy(StrEnum):
    """Generated source-group enumeration."""

    METADATA_ONLY = "METADATA_ONLY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ADMITTED = "ADMITTED"
    DENIED = "DENIED"


class GraphIngestionPolicy(StrEnum):
    """Generated source-group enumeration."""

    DISABLED = "DISABLED"
    SELECTED_PATHS_ONLY = "SELECTED_PATHS_ONLY"


class DeepExtractionPolicy(StrEnum):
    """Generated source-group enumeration."""

    DISABLED = "DISABLED"
    CANARY = "CANARY"
    ENABLED = "ENABLED"


class ReflectionPolicy(StrEnum):
    """Generated source-group enumeration."""

    DISABLED = "DISABLED"
    AFTER_SUCCESSFUL_DEEP = "AFTER_SUCCESSFUL_DEEP"


class ArtifactPolicy(StrEnum):
    """Generated source-group enumeration."""

    DISABLED = "DISABLED"
    STRUCTURAL_ONLY = "STRUCTURAL_ONLY"
    SEMANTIC_ON_SUCCESS = "SEMANTIC_ON_SUCCESS"
    STRUCTURAL_AND_SEMANTIC = "STRUCTURAL_AND_SEMANTIC"


class PromotionPolicy(StrEnum):
    """Generated source-group enumeration."""

    BLOCKED = "BLOCKED"
    MANUAL_AFTER_GATES = "MANUAL_AFTER_GATES"
    AUTOMATIC_AFTER_GATES = "AUTOMATIC_AFTER_GATES"


class Policies(Struct):
    """Generated source-group contract type."""

    registry_admission: RegistryAdmissionPolicy
    graph_ingestion: GraphIngestionPolicy
    deep_extraction: DeepExtractionPolicy
    reflection: ReflectionPolicy
    artifacts: ArtifactPolicy
    promotion: PromotionPolicy


class RefreshCadence(StrEnum):
    """Generated source-group enumeration."""

    MANUAL = "MANUAL"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"


class Refresh(Struct):
    """Generated source-group contract type."""

    cadence: RefreshCadence
    last_checked_at_ns: NullableEpochNs
    next_check_after_ns: NullableEpochNs
    update_available: bool


class PivotEvaluationStatus(StrEnum):
    """Generated source-group enumeration."""

    NOT_EVALUATED = "NOT_EVALUATED"
    QUEUED = "QUEUED"
    ACTIVE = "ACTIVE"
    SUPERIOR = "SUPERIOR"
    INFERIOR = "INFERIOR"
    COMPLEMENTARY = "COMPLEMENTARY"
    REJECTED = "REJECTED"


class PivotDimension(StrEnum):
    """Generated source-group enumeration."""

    PROTOCOL_COMPATIBILITY = "PROTOCOL_COMPATIBILITY"
    SEMANTIC_QUALITY = "SEMANTIC_QUALITY"
    STRUCTURAL_QUALITY = "STRUCTURAL_QUALITY"
    PERFORMANCE = "PERFORMANCE"
    COST = "COST"
    OPERABILITY = "OPERABILITY"
    MAINTENANCE = "MAINTENANCE"
    LICENSE = "LICENSE"


class PivotCandidate(Struct):
    """Generated source-group contract type."""

    is_candidate: bool
    technology_name: NullableString
    status: PivotEvaluationStatus
    comparison_dimensions: list[PivotDimension]
    last_evaluated_at_ns: NullableEpochNs
    next_evaluation_after_ns: NullableEpochNs
    recommendation: NullableString


class SourceRecord(Struct):
    """Generated source-group contract type."""

    source_id: Annotated[str, Meta(pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$")]
    repository: Repository
    role: Role
    status: SourceStatus
    capability_evidence: list[CapabilityEvidence]
    license: License
    paths: PathSelection
    timestamps: LifecycleTimestamps
    budgets: ResourceBudgets
    policies: Policies
    warnings: list[SourceWarning]
    refresh: Refresh
    pivot: PivotCandidate


class SourceGroupConfig(Struct):
    """Generated source-group contract type."""

    schema_version: Literal[1]
    group_id: Annotated[str, Meta(pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$")]
    generated_at_ns: EpochNs
    sources: list[SourceRecord]
