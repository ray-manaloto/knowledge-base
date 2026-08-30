# Copyright (c) 2026 Raymond Manaloto
"""Generated deps.dev package models; edit the pinned protobuf and rerun the generator."""

from __future__ import annotations

from enum import StrEnum

from msgspec import UNSET, UnsetType, field
from msgspec import Struct as _Struct


class Struct(_Struct, rename="camel"):
    """Generated deps.dev protobuf contract type."""


class GoogleApiCustomHttpPattern(Struct):
    """Generated deps.dev protobuf contract type."""

    kind: str | UnsetType = ""
    path: str | UnsetType = ""


class DepsDevV3System(StrEnum):
    """Generated deps.dev protobuf enum."""

    SYSTEM_UNSPECIFIED = "SYSTEM_UNSPECIFIED"
    GO = "GO"
    RUBYGEMS = "RUBYGEMS"
    NPM = "NPM"
    CARGO = "CARGO"
    MAVEN = "MAVEN"
    PYPI = "PYPI"
    NUGET = "NUGET"


class DepsDevV3HashType(StrEnum):
    """Generated deps.dev protobuf enum."""

    HASH_TYPE_UNSPECIFIED = "HASH_TYPE_UNSPECIFIED"
    MD5 = "MD5"
    SHA1 = "SHA1"
    SHA256 = "SHA256"
    SHA512 = "SHA512"


class DepsDevV3DependencyRelation(StrEnum):
    """Generated deps.dev protobuf enum."""

    DEPENDENCY_RELATION_UNSPECIFIED = "DEPENDENCY_RELATION_UNSPECIFIED"
    SELF = "SELF"
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"


class DepsDevV3ProjectRelationType(StrEnum):
    """Generated deps.dev protobuf enum."""

    UNKNOWN_PROJECT_RELATION_TYPE = "UNKNOWN_PROJECT_RELATION_TYPE"
    SOURCE_REPO = "SOURCE_REPO"
    ISSUE_TRACKER = "ISSUE_TRACKER"


class DepsDevV3ProjectRelationProvenance(StrEnum):
    """Generated deps.dev protobuf enum."""

    UNKNOWN_PROJECT_RELATION_PROVENANCE = "UNKNOWN_PROJECT_RELATION_PROVENANCE"
    SLSA_ATTESTATION = "SLSA_ATTESTATION"
    GO_ORIGIN = "GO_ORIGIN"
    PYPI_PUBLISH_ATTESTATION = "PYPI_PUBLISH_ATTESTATION"
    RUBYGEMS_PUBLISH_ATTESTATION = "RUBYGEMS_PUBLISH_ATTESTATION"
    UNVERIFIED_METADATA = "UNVERIFIED_METADATA"


class DepsDevV3PackageKey(Struct):
    """Generated deps.dev protobuf contract type."""

    system: DepsDevV3System | UnsetType = DepsDevV3System.SYSTEM_UNSPECIFIED
    name: str | UnsetType = ""


class DepsDevV3VersionKey(Struct):
    """Generated deps.dev protobuf contract type."""

    system: DepsDevV3System | UnsetType = DepsDevV3System.SYSTEM_UNSPECIFIED
    name: str | UnsetType = ""
    version: str | UnsetType = ""


class DepsDevV3ProjectKey(Struct):
    """Generated deps.dev protobuf contract type."""

    id: str | UnsetType = ""


class DepsDevV3AdvisoryKey(Struct):
    """Generated deps.dev protobuf contract type."""

    id: str | UnsetType = ""


class DepsDevV3Hash(Struct):
    """Generated deps.dev protobuf contract type."""

    type: DepsDevV3HashType | UnsetType = DepsDevV3HashType.HASH_TYPE_UNSPECIFIED
    value: bytes | UnsetType = b""


class DepsDevV3Link(Struct):
    """Generated deps.dev protobuf contract type."""

    label: str | UnsetType = ""
    url: str | UnsetType = ""


class DepsDevV3SLSAProvenance(Struct):
    """Generated deps.dev protobuf contract type."""

    source_repository: str | UnsetType = ""
    commit: str | UnsetType = ""
    url: str | UnsetType = ""
    verified: bool | UnsetType = False


class DepsDevV3Attestation(Struct):
    """Generated deps.dev protobuf contract type."""

    type: str | UnsetType = ""
    url: str | UnsetType = ""
    verified: bool | UnsetType = False
    source_repository: str | UnsetType = ""
    commit: str | UnsetType = ""


class DepsDevV3GetPackageRequest(Struct):
    """Generated deps.dev protobuf contract type."""

    package_key: (
        DepsDevV3PackageKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET


class DepsDevV3PackageVersion(Struct):
    """Generated deps.dev protobuf contract type."""

    version_key: (
        DepsDevV3VersionKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET
    published_at: str | UnsetType = UNSET
    is_default: bool | UnsetType = False
    is_deprecated: bool | UnsetType = False
    deprecated_reason: str | UnsetType = ""


class DepsDevV3Package(Struct):
    """Generated deps.dev protobuf contract type."""

    package_key: (
        DepsDevV3PackageKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET
    versions: list[DepsDevV3PackageVersion] | UnsetType = field(default_factory=list)


class DepsDevV3GetVersionRequest(Struct):
    """Generated deps.dev protobuf contract type."""

    version_key: (
        DepsDevV3VersionKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET


class DepsDevV3VersionProject(Struct):
    """Generated deps.dev protobuf contract type."""

    project_key: (
        DepsDevV3ProjectKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET
    relation_provenance: DepsDevV3ProjectRelationProvenance | UnsetType = (
        DepsDevV3ProjectRelationProvenance.UNKNOWN_PROJECT_RELATION_PROVENANCE
    )
    relation_type: DepsDevV3ProjectRelationType | UnsetType = (
        DepsDevV3ProjectRelationType.UNKNOWN_PROJECT_RELATION_TYPE
    )


class DepsDevV3VersionProjectStatus(Struct):
    """Generated deps.dev protobuf contract type."""

    status: str | UnsetType = ""
    reason: str | UnsetType = ""


class DepsDevV3Version(Struct):
    """Generated deps.dev protobuf contract type."""

    version_key: (
        DepsDevV3VersionKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET
    published_at: str | UnsetType = UNSET
    is_default: bool | UnsetType = False
    is_deprecated: bool | UnsetType = False
    deprecated_reason: str | UnsetType = ""
    licenses: list[str] | UnsetType = field(default_factory=list)
    advisory_keys: list[DepsDevV3AdvisoryKey] | UnsetType = field(default_factory=list)
    links: list[DepsDevV3Link] | UnsetType = field(default_factory=list)
    slsa_provenances: list[DepsDevV3SLSAProvenance] | UnsetType = field(default_factory=list)
    attestations: list[DepsDevV3Attestation] | UnsetType = field(default_factory=list)
    registries: list[str] | UnsetType = field(default_factory=list)
    related_projects: list[DepsDevV3VersionProject] | UnsetType = field(default_factory=list)
    project_status: DepsDevV3VersionProjectStatus | UnsetType = UNSET


class DepsDevV3GetRequirementsRequest(Struct):
    """Generated deps.dev protobuf contract type."""

    version_key: (
        DepsDevV3VersionKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET


class DepsDevV3RequirementsNuGetDependencyGroupDependency(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    requirement: str | UnsetType = ""
    include: str | UnsetType = ""
    exclude: str | UnsetType = ""


class DepsDevV3RequirementsNuGetDependencyGroup(Struct):
    """Generated deps.dev protobuf contract type."""

    target_framework: str | UnsetType = ""
    dependencies: list[DepsDevV3RequirementsNuGetDependencyGroupDependency] | UnsetType = field(
        default_factory=list
    )


class DepsDevV3RequirementsNuGetFrameworkAssembly(Struct):
    """Generated deps.dev protobuf contract type."""

    assembly_name: str | UnsetType = ""
    target_framework: str | UnsetType = ""


class DepsDevV3RequirementsNuGetFrameworkReference(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    target_framework: str | UnsetType = ""


class DepsDevV3RequirementsNuGet(Struct):
    """Generated deps.dev protobuf contract type."""

    dependency_groups: list[DepsDevV3RequirementsNuGetDependencyGroup] | UnsetType = field(
        default_factory=list
    )
    target_frameworks: list[str] | UnsetType = field(default_factory=list)
    development_dependency: bool | UnsetType = False
    framework_assemblies: list[DepsDevV3RequirementsNuGetFrameworkAssembly] | UnsetType = field(
        default_factory=list
    )
    framework_references: list[DepsDevV3RequirementsNuGetFrameworkReference] | UnsetType = field(
        default_factory=list
    )


class DepsDevV3RequirementsNPMDependenciesDependency(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    requirement: str | UnsetType = ""


class DepsDevV3RequirementsNPMDependenciesPeerDependencyMetadata(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    optional: bool | UnsetType = False


class DepsDevV3RequirementsNPMDependencies(Struct):
    """Generated deps.dev protobuf contract type."""

    dependencies: list[DepsDevV3RequirementsNPMDependenciesDependency] | UnsetType = field(
        default_factory=list
    )
    dev_dependencies: list[DepsDevV3RequirementsNPMDependenciesDependency] | UnsetType = field(
        default_factory=list
    )
    optional_dependencies: list[DepsDevV3RequirementsNPMDependenciesDependency] | UnsetType = field(
        default_factory=list
    )
    peer_dependencies: list[DepsDevV3RequirementsNPMDependenciesDependency] | UnsetType = field(
        default_factory=list
    )
    bundle_dependencies: list[str] | UnsetType = field(default_factory=list)
    peer_dependency_metadata: (
        list[DepsDevV3RequirementsNPMDependenciesPeerDependencyMetadata] | UnsetType
    ) = field(default_factory=list)


class DepsDevV3RequirementsNPMBundle(Struct):
    """Generated deps.dev protobuf contract type."""

    path: str | UnsetType = ""
    name: str | UnsetType = ""
    version: str | UnsetType = ""
    dependencies: DepsDevV3RequirementsNPMDependencies | UnsetType = UNSET


class DepsDevV3RequirementsNPM(Struct):
    """Generated deps.dev protobuf contract type."""

    dependencies: DepsDevV3RequirementsNPMDependencies | UnsetType = UNSET
    bundled: list[DepsDevV3RequirementsNPMBundle] | UnsetType = field(default_factory=list)
    os: list[str] | UnsetType = field(default_factory=list)
    cpu: list[str] | UnsetType = field(default_factory=list)


class DepsDevV3RequirementsMavenDependency(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    version: str | UnsetType = ""
    classifier: str | UnsetType = ""
    type: str | UnsetType = ""
    scope: str | UnsetType = ""
    optional: str | UnsetType = ""
    exclusions: list[str] | UnsetType = field(default_factory=list)
    resolved_version: str | UnsetType = ""
    resolved_name: str | UnsetType = ""
    origin: str | UnsetType = ""


class DepsDevV3RequirementsMavenProperty(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    value: str | UnsetType = ""


class DepsDevV3RequirementsMavenRepository(Struct):
    """Generated deps.dev protobuf contract type."""

    id: str | UnsetType = ""
    url: str | UnsetType = ""
    layout: str | UnsetType = ""
    releases_enabled: str | UnsetType = ""
    snapshots_enabled: str | UnsetType = ""
    resolved_url: str | UnsetType = ""


class DepsDevV3RequirementsMavenProfileActivationJDK(Struct):
    """Generated deps.dev protobuf contract type."""

    jdk: str | UnsetType = ""


class DepsDevV3RequirementsMavenProfileActivationOS(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    family: str | UnsetType = ""
    arch: str | UnsetType = ""
    version: str | UnsetType = ""


class DepsDevV3RequirementsMavenProfileActivationProperty(Struct):
    """Generated deps.dev protobuf contract type."""

    property: DepsDevV3RequirementsMavenProperty | UnsetType = UNSET


class DepsDevV3RequirementsMavenProfileActivationFile(Struct):
    """Generated deps.dev protobuf contract type."""

    exists: str | UnsetType = ""
    missing: str | UnsetType = ""


class DepsDevV3RequirementsMavenProfileActivation(Struct):
    """Generated deps.dev protobuf contract type."""

    active_by_default: str | UnsetType = ""
    jdk: DepsDevV3RequirementsMavenProfileActivationJDK | UnsetType = UNSET
    os: DepsDevV3RequirementsMavenProfileActivationOS | UnsetType = UNSET
    property: DepsDevV3RequirementsMavenProfileActivationProperty | UnsetType = UNSET
    file: DepsDevV3RequirementsMavenProfileActivationFile | UnsetType = UNSET


class DepsDevV3RequirementsMavenProfile(Struct):
    """Generated deps.dev protobuf contract type."""

    id: str | UnsetType = ""
    activation: DepsDevV3RequirementsMavenProfileActivation | UnsetType = UNSET
    dependencies: list[DepsDevV3RequirementsMavenDependency] | UnsetType = field(
        default_factory=list
    )
    dependency_management: list[DepsDevV3RequirementsMavenDependency] | UnsetType = field(
        default_factory=list
    )
    properties: list[DepsDevV3RequirementsMavenProperty] | UnsetType = field(default_factory=list)
    repositories: list[DepsDevV3RequirementsMavenRepository] | UnsetType = field(
        default_factory=list
    )


class DepsDevV3RequirementsMaven(Struct):
    """Generated deps.dev protobuf contract type."""

    parent: DepsDevV3VersionKey | UnsetType = UNSET
    dependencies: list[DepsDevV3RequirementsMavenDependency] | UnsetType = field(
        default_factory=list
    )
    dependency_management: list[DepsDevV3RequirementsMavenDependency] | UnsetType = field(
        default_factory=list
    )
    properties: list[DepsDevV3RequirementsMavenProperty] | UnsetType = field(default_factory=list)
    repositories: list[DepsDevV3RequirementsMavenRepository] | UnsetType = field(
        default_factory=list
    )
    profiles: list[DepsDevV3RequirementsMavenProfile] | UnsetType = field(default_factory=list)


class DepsDevV3RequirementsRubyGemsDependency(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    requirement: str | UnsetType = ""


class DepsDevV3RequirementsRubyGems(Struct):
    """Generated deps.dev protobuf contract type."""

    runtime_dependencies: list[DepsDevV3RequirementsRubyGemsDependency] | UnsetType = field(
        default_factory=list
    )
    dev_dependencies: list[DepsDevV3RequirementsRubyGemsDependency] | UnsetType = field(
        default_factory=list
    )
    platform: str | UnsetType = ""
    required_ruby_version: str | UnsetType = ""
    required_rubygems_version: str | UnsetType = ""


class DepsDevV3RequirementsGoDependency(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    requirement: str | UnsetType = ""


class DepsDevV3RequirementsGoReplace(Struct):
    """Generated deps.dev protobuf contract type."""

    src: DepsDevV3RequirementsGoDependency | UnsetType = UNSET
    replacement: DepsDevV3RequirementsGoDependency | UnsetType = UNSET
    local_path: str | UnsetType = ""


class DepsDevV3RequirementsGo(Struct):
    """Generated deps.dev protobuf contract type."""

    direct_dependencies: list[DepsDevV3RequirementsGoDependency] | UnsetType = field(
        default_factory=list
    )
    indirect_dependencies: list[DepsDevV3RequirementsGoDependency] | UnsetType = field(
        default_factory=list
    )
    replaces: list[DepsDevV3RequirementsGoReplace] | UnsetType = field(default_factory=list)
    excludes: list[DepsDevV3RequirementsGoDependency] | UnsetType = field(default_factory=list)


class DepsDevV3RequirementsPyPIDependency(Struct):
    """Generated deps.dev protobuf contract type."""

    project_name: str | UnsetType = ""
    extras: str | UnsetType = ""
    version_specifier: str | UnsetType = ""
    environment_marker: str | UnsetType = ""


class DepsDevV3RequirementsPyPIExternalDependency(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    version_specifier: str | UnsetType = ""
    environment_marker: str | UnsetType = ""


class DepsDevV3RequirementsPyPIExtra(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""


class DepsDevV3RequirementsPyPI(Struct):
    """Generated deps.dev protobuf contract type."""

    dependencies: list[DepsDevV3RequirementsPyPIDependency] | UnsetType = field(
        default_factory=list
    )
    provided_extras: list[DepsDevV3RequirementsPyPIExtra] | UnsetType = field(default_factory=list)
    external_dependencies: list[DepsDevV3RequirementsPyPIExternalDependency] | UnsetType = field(
        default_factory=list
    )
    required_python_version: str | UnsetType = ""


class DepsDevV3RequirementsCargoDependency(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    requirement: str | UnsetType = ""
    kind: str | UnsetType = ""
    optional: bool | UnsetType = False
    package_alias: str | UnsetType = ""
    uses_default_features: bool | UnsetType = False
    features: list[str] | UnsetType = field(default_factory=list)
    target: str | UnsetType = ""


class DepsDevV3RequirementsCargoFeature(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    implies: list[str] | UnsetType = field(default_factory=list)


class DepsDevV3RequirementsCargo(Struct):
    """Generated deps.dev protobuf contract type."""

    dependencies: list[DepsDevV3RequirementsCargoDependency] | UnsetType = field(
        default_factory=list
    )
    features: list[DepsDevV3RequirementsCargoFeature] | UnsetType = field(default_factory=list)


class DepsDevV3Requirements(Struct):
    """Generated deps.dev protobuf contract type."""

    nuget: DepsDevV3RequirementsNuGet | UnsetType = UNSET
    npm: DepsDevV3RequirementsNPM | UnsetType = UNSET
    maven: DepsDevV3RequirementsMaven | UnsetType = UNSET
    rubygems: DepsDevV3RequirementsRubyGems | UnsetType = UNSET
    go: DepsDevV3RequirementsGo | UnsetType = UNSET
    pypi: DepsDevV3RequirementsPyPI | UnsetType = UNSET
    cargo: DepsDevV3RequirementsCargo | UnsetType = UNSET


class DepsDevV3GetDependenciesRequest(Struct):
    """Generated deps.dev protobuf contract type."""

    version_key: (
        DepsDevV3VersionKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET


class DepsDevV3DependenciesNode(Struct):
    """Generated deps.dev protobuf contract type."""

    version_key: (
        DepsDevV3VersionKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET
    bundled: bool | UnsetType = False
    relation: DepsDevV3DependencyRelation | UnsetType = (
        DepsDevV3DependencyRelation.DEPENDENCY_RELATION_UNSPECIFIED
    )
    errors: list[str] | UnsetType = field(default_factory=list)


class DepsDevV3DependenciesEdge(Struct):
    """Generated deps.dev protobuf contract type."""

    from_node: int | UnsetType = 0
    to_node: int | UnsetType = 0
    requirement: str | UnsetType = ""


class DepsDevV3Dependencies(Struct):
    """Generated deps.dev protobuf contract type."""

    nodes: list[DepsDevV3DependenciesNode] | UnsetType = field(default_factory=list)
    edges: list[DepsDevV3DependenciesEdge] | UnsetType = field(default_factory=list)
    error: str | UnsetType = ""


class DepsDevV3GetProjectRequest(Struct):
    """Generated deps.dev protobuf contract type."""

    project_key: (
        DepsDevV3ProjectKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET


class DepsDevV3ProjectScorecardRepository(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    commit: str | UnsetType = ""


class DepsDevV3ProjectScorecardScorecardDetails(Struct):
    """Generated deps.dev protobuf contract type."""

    version: str | UnsetType = ""
    commit: str | UnsetType = ""


class DepsDevV3ProjectScorecardCheckDocumentation(Struct):
    """Generated deps.dev protobuf contract type."""

    short_description: str | UnsetType = ""
    url: str | UnsetType = ""


class DepsDevV3ProjectScorecardCheck(Struct):
    """Generated deps.dev protobuf contract type."""

    name: str | UnsetType = ""
    documentation: DepsDevV3ProjectScorecardCheckDocumentation | UnsetType = UNSET
    score: int | UnsetType = 0
    reason: str | UnsetType = ""
    details: list[str] | UnsetType = field(default_factory=list)


class DepsDevV3ProjectScorecard(Struct):
    """Generated deps.dev protobuf contract type."""

    date: str | UnsetType = UNSET
    repository: DepsDevV3ProjectScorecardRepository | UnsetType = UNSET
    scorecard: DepsDevV3ProjectScorecardScorecardDetails | UnsetType = UNSET
    checks: list[DepsDevV3ProjectScorecardCheck] | UnsetType = field(default_factory=list)
    overall_score: float | UnsetType = 0.0
    metadata: list[str] | UnsetType = field(default_factory=list)


class DepsDevV3ProjectOSSFuzzDetails(Struct):
    """Generated deps.dev protobuf contract type."""

    line_count: int | UnsetType = 0
    line_cover_count: int | UnsetType = 0
    date: str | UnsetType = UNSET
    config_url: str | UnsetType = ""


class DepsDevV3Project(Struct):
    """Generated deps.dev protobuf contract type."""

    project_key: (
        DepsDevV3ProjectKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET
    open_issues_count: int | UnsetType = 0
    stars_count: int | UnsetType = 0
    forks_count: int | UnsetType = 0
    license: str | UnsetType = ""
    description: str | UnsetType = ""
    homepage: str | UnsetType = ""
    scorecard: DepsDevV3ProjectScorecard | UnsetType = UNSET
    oss_fuzz: DepsDevV3ProjectOSSFuzzDetails | UnsetType = UNSET


class DepsDevV3GetProjectPackageVersionsRequest(Struct):
    """Generated deps.dev protobuf contract type."""

    project_key: (
        DepsDevV3ProjectKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET


class DepsDevV3ProjectPackageVersionsVersion(Struct):
    """Generated deps.dev protobuf contract type."""

    version_key: (
        DepsDevV3VersionKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET
    relation_type: DepsDevV3ProjectRelationType | UnsetType = (
        DepsDevV3ProjectRelationType.UNKNOWN_PROJECT_RELATION_TYPE
    )
    relation_provenance: DepsDevV3ProjectRelationProvenance | UnsetType = (
        DepsDevV3ProjectRelationProvenance.UNKNOWN_PROJECT_RELATION_PROVENANCE
    )
    slsa_provenances: list[DepsDevV3SLSAProvenance] | UnsetType = field(default_factory=list)
    attestations: list[DepsDevV3Attestation] | UnsetType = field(default_factory=list)


class DepsDevV3ProjectPackageVersions(Struct):
    """Generated deps.dev protobuf contract type."""

    versions: list[DepsDevV3ProjectPackageVersionsVersion] | UnsetType = field(default_factory=list)


class DepsDevV3GetAdvisoryRequest(Struct):
    """Generated deps.dev protobuf contract type."""

    advisory_key: (
        DepsDevV3AdvisoryKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET


class DepsDevV3Advisory(Struct):
    """Generated deps.dev protobuf contract type."""

    advisory_key: (
        DepsDevV3AdvisoryKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET
    url: str | UnsetType = ""
    title: str | UnsetType = ""
    aliases: list[str] | UnsetType = field(default_factory=list)
    cvss3_score: float | UnsetType = 0.0
    cvss3_vector: str | UnsetType = ""


class DepsDevV3QueryRequest(Struct):
    """Generated deps.dev protobuf contract type."""

    hash: DepsDevV3Hash | UnsetType = UNSET
    version_key: (
        DepsDevV3VersionKey
        | UnsetType  # Keep key-shaped annotations multiline for secret scanning.
    ) = UNSET


class DepsDevV3QueryResultResult(Struct):
    """Generated deps.dev protobuf contract type."""

    version: DepsDevV3Version | UnsetType = UNSET


class DepsDevV3QueryResult(Struct):
    """Generated deps.dev protobuf contract type."""

    results: list[DepsDevV3QueryResultResult] | UnsetType = field(default_factory=list)


class GoogleApiHttpRule(Struct):
    """Generated deps.dev protobuf contract type."""

    selector: str | UnsetType = ""
    get: str | UnsetType = UNSET
    put: str | UnsetType = UNSET
    post: str | UnsetType = UNSET
    delete: str | UnsetType = UNSET
    patch: str | UnsetType = UNSET
    custom: GoogleApiCustomHttpPattern | UnsetType = UNSET
    body: str | UnsetType = ""
    response_body: str | UnsetType = ""
    additional_bindings: list[GoogleApiHttpRule] | UnsetType = field(default_factory=list)


class GoogleApiHttp(Struct):
    """Generated deps.dev protobuf contract type."""

    rules: list[GoogleApiHttpRule] | UnsetType = field(default_factory=list)
    fully_decode_reserved_expansion: bool | UnsetType = False
