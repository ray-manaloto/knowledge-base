# Copyright (c) 2026 Raymond Manaloto
"""Pure policy core for discovering Graphify consumers and alternatives.

This module deliberately knows nothing about HTTP, ``gh``, manifests, or the
knowledge graph.  An adapter may execute :func:`build_search_plan`, translate
the returned GitHub observations into the immutable inputs below, and pass them
to :func:`check_candidate`.  Keeping the policy at this seam makes incomplete
searches observable and makes it impossible for discovery itself to mutate the
source registry or derived graph.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import PurePosixPath
from urllib.parse import urlparse

_GITHUB_RESULTS_PER_PAGE_MAX = 100
_GITHUB_SEARCH_PAGES_MAX = 10
_REPOSITORY_ID_PARTS = 2


class SearchKind(StrEnum):
    """GitHub search API families used by discovery."""

    CODE = "code"
    COMMIT = "commit"


class SearchTarget(StrEnum):
    """Why a search request exists."""

    GRAPHIFY_CONSUMER = "graphify-consumer"
    ALTERNATIVE = "alternative"


class EvidenceKind(StrEnum):
    """How an exact path/call site evidenced Graphify."""

    PACKAGE_DEFINITION = "package-definition"
    DECLARATION = "declaration"
    DOCUMENTATION = "documentation"
    CLI_CALL = "cli-call"
    SDK_CALL = "sdk-call"


class UsageClass(StrEnum):
    """The intentionally small claims discovery is allowed to make."""

    DECLARED_ONLY = "DECLARED_ONLY"
    DOCS_ONLY = "DOCS_ONLY"
    CLI_BASIC = "CLI_BASIC"
    SDK_BASIC = "SDK_BASIC"


class CandidateStatus(StrEnum):
    """Whether discovery produced a reviewable Graphify source candidate."""

    CANDIDATE = "CANDIDATE"
    REFRESH_REQUIRED = "REFRESH_REQUIRED"
    NO_USAGE_EVIDENCE = "NO_USAGE_EVIDENCE"
    EXCLUDED_SELF_PACKAGE = "EXCLUDED_SELF_PACKAGE"
    INCOMPLETE = "INCOMPLETE"


class RefreshTrigger(StrEnum):
    """Evidence changes that require a prior review to be repeated."""

    EVIDENCE_PATH_CHANGED = "EVIDENCE_PATH_CHANGED"
    DEPENDENCY_DRIFT = "DEPENDENCY_DRIFT"
    VERSION_DRIFT = "VERSION_DRIFT"


@dataclass(frozen=True, slots=True)
class Evidence:
    """One exact, revision-bound repository observation."""

    path: str
    kind: EvidenceKind
    exact: str
    commit_sha: str

    def __post_init__(self) -> None:
        """Require reproducible evidence rather than an unlocated mention."""
        candidate = PurePosixPath(self.path)
        if not self.path.strip() or candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("evidence path must be an exact repository-relative path")
        if not self.exact.strip():
            raise ValueError("evidence must retain the exact declaration or call site")
        if not self.commit_sha.strip():
            raise ValueError("evidence must retain its path commit")


@dataclass(frozen=True, slots=True)
class PathCommit:
    """Last commit observed for one evidence-bearing path."""

    path: str
    commit_sha: str

    def __post_init__(self) -> None:
        """Reject a path or revision that cannot be compared exactly."""
        candidate = PurePosixPath(self.path)
        if not self.path.strip() or candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("path commit must name an exact repository-relative path")
        if not self.commit_sha.strip():
            raise ValueError("path commit must retain its commit SHA")


@dataclass(frozen=True, slots=True)
class ReviewedSnapshot:
    """The evidence-bound state of the most recent human review."""

    reviewed_sha: str
    evidence_path_commits: tuple[PathCommit, ...]
    dependency_version: str = ""
    graphify_version: str = ""

    def __post_init__(self) -> None:
        """A review must name its revision and each evidence path once."""
        if not self.reviewed_sha.strip():
            raise ValueError("reviewed_sha must not be empty")
        paths = tuple(item.path for item in self.evidence_path_commits)
        if len(paths) != len(set(paths)):
            raise ValueError("reviewed evidence paths must be unique")


@dataclass(frozen=True, slots=True)
class SearchCoverage:
    """Completeness signals retained from GitHub/API execution."""

    truncated: bool = False
    rate_limited: bool = False
    partial: bool = False
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Warnings must remain actionable rather than blank flags."""
        if any(not warning.strip() for warning in self.warnings):
            raise ValueError("search warnings must state their reason")

    @property
    def incomplete_reasons(self) -> tuple[str, ...]:
        """Stable, operator-readable reasons the result cannot be classified."""
        reasons: list[str] = []
        if self.truncated:
            reasons.append("github search results were truncated")
        if self.rate_limited:
            reasons.append("github search was rate limited")
        if self.partial:
            reasons.append("github search returned partial results")
        reasons.extend(f"unclassified warning: {warning}" for warning in self.warnings)
        return tuple(reasons)

    @property
    def complete(self) -> bool:
        """True only when no failure signal was observed."""
        return not self.incomplete_reasons


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """One bounded GitHub search request for an external adapter to execute."""

    kind: SearchKind
    target: SearchTarget
    query: str
    per_page: int = 100
    max_pages: int = 2

    def __post_init__(self) -> None:
        """Reject an unbounded or GitHub-invalid request."""
        if not self.query.strip():
            raise ValueError("search query must not be empty")
        if not 1 <= self.per_page <= _GITHUB_RESULTS_PER_PAGE_MAX:
            raise ValueError("per_page must be within GitHub's 1..100 bound")
        if not 1 <= self.max_pages <= _GITHUB_SEARCH_PAGES_MAX:
            raise ValueError("max_pages must be within the 1..10 search-result bound")

    @property
    def max_results(self) -> int:
        """Maximum observations this request is allowed to return."""
        return self.per_page * self.max_pages


@dataclass(frozen=True, slots=True)
class SearchPlan:
    """Deterministic, finite work for a GitHub search adapter."""

    requests: tuple[SearchRequest, ...]

    @property
    def max_total_results(self) -> int:
        """Hard upper bound across all requests."""
        return sum(request.max_results for request in self.requests)


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    """Read-only repository metadata returned by a GitHub adapter.

    Lineage fields are explicit API or review evidence.  A shared commit SHA is
    never treated as lineage: identical commits routinely exist in independent
    vendor copies and Git object ids are not repository identities.
    """

    repository: str
    head_sha: str
    license_spdx: str | None
    is_fork: bool
    archived: bool
    default_branch: str
    evidence: tuple[Evidence, ...] = ()
    declared_packages: tuple[str, ...] = ()
    fork_parent: str = ""
    template_parent: str = ""
    vendor_origin: str = ""
    dependency_version: str = ""
    graphify_version: str = ""

    def __post_init__(self) -> None:
        """Validate identity-bearing fields while preserving opaque revisions."""
        canonical_repo_id(self.repository)
        related_repositories = (self.fork_parent, self.template_parent, self.vendor_origin)
        for related in related_repositories:
            if related:
                canonical_repo_id(related)
        if sum(bool(related) for related in related_repositories) > 1:
            raise ValueError("repository declares contradictory lineage sources")
        if not self.head_sha.strip():
            raise ValueError("head_sha must not be empty")
        if not self.default_branch.strip():
            raise ValueError("default_branch must not be empty")


@dataclass(frozen=True, slots=True)
class CandidateGroup:
    """One canonical source family after explicit-lineage deduplication."""

    canonical_repo_id: str
    representative: RepositorySnapshot
    members: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateCheck:
    """Metadata-only discovery output suitable for source-group integration."""

    canonical_repo_id: str
    observed_repo_id: str
    head_sha: str
    reviewed_sha: str
    reviewed_sha_moved: bool
    license_spdx: str | None
    is_fork: bool
    archived: bool
    default_branch: str
    usage: UsageClass | None
    usage_evidence_paths: tuple[str, ...]
    checked_at_ns: int
    status: CandidateStatus
    refresh_triggers: tuple[RefreshTrigger, ...]
    incomplete_reasons: tuple[str, ...]


_DOC_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".adoc"})
_DOC_BASENAME_PREFIXES = ("readme", "changelog", "contributing")
_SDK_EVIDENCE_RE = re.compile(
    r"(?:\b(?:from|import)\s+graphify\b|\bgraphify\.[A-Za-z_]\w*)",
    re.IGNORECASE,
)
_CLI_EVIDENCE_RE = re.compile(r"(?:^|[;&|]\s*)graphify(?:\s|$)", re.IGNORECASE)
_DECLARATION_RE = re.compile(r"\bgraphifyy?\b", re.IGNORECASE)


def _is_document_path(path: str) -> bool:
    item = PurePosixPath(path)
    return (
        item.suffix.casefold() in _DOC_SUFFIXES
        or item.name.casefold().startswith(_DOC_BASENAME_PREFIXES)
        or (bool(item.parts) and item.parts[0].casefold() in {"doc", "docs", "documentation"})
    )


def classify_usage(evidence: tuple[Evidence, ...]) -> UsageClass | None:
    """Classify only exact evidence, never infer advanced Graphify features.

    Even an executable ``graphify extract --deep`` call is only ``CLI_BASIC``.
    This policy reports that a surface is used; it does not claim ingest,
    semantic extraction, reflection, artifact generation, or artifact quality.
    A command printed in Markdown remains documentation rather than execution.
    """
    ranked = {
        None: 0,
        UsageClass.DOCS_ONLY: 1,
        UsageClass.DECLARED_ONLY: 2,
        UsageClass.CLI_BASIC: 3,
        UsageClass.SDK_BASIC: 4,
    }
    return max((_classify_item(item) for item in evidence), key=ranked.__getitem__, default=None)


def _classify_item(item: Evidence) -> UsageClass | None:
    """Classify one exact observation; documentation paths always stay docs."""
    if _is_document_path(item.path) or item.kind is EvidenceKind.DOCUMENTATION:
        return UsageClass.DOCS_ONLY
    if item.kind is EvidenceKind.SDK_CALL and _SDK_EVIDENCE_RE.search(item.exact):
        return UsageClass.SDK_BASIC
    if item.kind is EvidenceKind.CLI_CALL and _CLI_EVIDENCE_RE.search(item.exact):
        return UsageClass.CLI_BASIC
    if item.kind is EvidenceKind.DECLARATION and _DECLARATION_RE.search(item.exact):
        return UsageClass.DECLARED_ONLY
    return None


def _evidence_path_commits(evidence: tuple[Evidence, ...]) -> dict[str, str]:
    """Collapse call sites to path revisions, rejecting contradictory inputs."""
    revisions: dict[str, str] = {}
    for item in evidence:
        previous = revisions.setdefault(item.path, item.commit_sha)
        if previous != item.commit_sha:
            raise ValueError(f"evidence path has conflicting commits: {item.path}")
    return revisions


def refresh_triggers(
    repository: RepositorySnapshot, reviewed: ReviewedSnapshot
) -> tuple[RefreshTrigger, ...]:
    """Compare evidence-bearing inputs; a moved repository HEAD alone is inert."""
    current_paths = _evidence_path_commits(repository.evidence)
    reviewed_paths = {item.path: item.commit_sha for item in reviewed.evidence_path_commits}
    triggers: list[RefreshTrigger] = []
    if current_paths != reviewed_paths:
        triggers.append(RefreshTrigger.EVIDENCE_PATH_CHANGED)
    if repository.dependency_version != reviewed.dependency_version:
        triggers.append(RefreshTrigger.DEPENDENCY_DRIFT)
    if repository.graphify_version != reviewed.graphify_version:
        triggers.append(RefreshTrigger.VERSION_DRIFT)
    return tuple(triggers)


_GRAPHIFY_PACKAGES = frozenset({"graphify", "graphifyy"})


def _normalized_package(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().casefold())


def _is_self_package(repository: RepositorySnapshot) -> bool:
    packages = {_normalized_package(name) for name in repository.declared_packages}
    for item in repository.evidence:
        if item.kind is EvidenceKind.PACKAGE_DEFINITION:
            packages.update(
                _normalized_package(name) for name in _DECLARATION_RE.findall(item.exact)
            )
    return bool(packages & _GRAPHIFY_PACKAGES)


def check_candidate(
    repository: RepositorySnapshot,
    *,
    checked_at_ns: int,
    reviewed: ReviewedSnapshot | None = None,
    coverage: SearchCoverage | None = None,
) -> CandidateCheck:
    """Classify one adapter observation without network or filesystem effects.

    Completeness has priority over every substantive verdict: a true statement
    about a visible prefix is still not a verdict about the result set GitHub
    withheld.  Self-package definitions are next, preventing Graphify's own
    imports and tests from being promoted as third-party consumer evidence.
    """
    if type(checked_at_ns) is not int or checked_at_ns < 0:
        raise ValueError("checked_at_ns must be an exact non-negative integer")

    observed_id = canonical_repo_id(repository.repository)
    effective_coverage = coverage or SearchCoverage()
    source = repository.fork_parent or repository.template_parent or repository.vendor_origin
    source_id = canonical_repo_id(source or repository.repository)
    paths = tuple(sorted({item.path for item in repository.evidence}))
    reviewed_sha = reviewed.reviewed_sha if reviewed is not None else ""
    moved = (
        reviewed is not None and reviewed.reviewed_sha.casefold() != repository.head_sha.casefold()
    )
    triggers: tuple[RefreshTrigger, ...] = ()
    extra_incomplete: tuple[str, ...] = ()
    if reviewed is not None:
        try:
            triggers = refresh_triggers(repository, reviewed)
        except ValueError as exc:
            extra_incomplete = (str(exc),)

    metadata_reasons = (
        ("fork metadata omitted parent repository",)
        if repository.is_fork and not repository.fork_parent
        else ()
    )
    reasons = effective_coverage.incomplete_reasons + extra_incomplete + metadata_reasons
    usage = classify_usage(repository.evidence)
    if reasons:
        status = CandidateStatus.INCOMPLETE
        usage = None
    elif _is_self_package(repository):
        status = CandidateStatus.EXCLUDED_SELF_PACKAGE
        usage = None
    elif usage is None:
        status = CandidateStatus.NO_USAGE_EVIDENCE
    elif triggers:
        status = CandidateStatus.REFRESH_REQUIRED
    else:
        status = CandidateStatus.CANDIDATE

    return CandidateCheck(
        canonical_repo_id=source_id,
        observed_repo_id=observed_id,
        head_sha=repository.head_sha,
        reviewed_sha=reviewed_sha,
        reviewed_sha_moved=moved,
        license_spdx=repository.license_spdx,
        is_fork=repository.is_fork,
        archived=repository.archived,
        default_branch=repository.default_branch,
        usage=usage,
        usage_evidence_paths=paths,
        checked_at_ns=checked_at_ns,
        status=status,
        refresh_triggers=triggers,
        incomplete_reasons=reasons,
    )


def canonical_repo_id(repository: str) -> str:
    """Return a case-folded ``owner/name`` GitHub repository identity.

    Accepted spellings cover GitHub API names, HTTPS clone URLs, and SCP-like
    SSH clone URLs.  Extra path components are rejected so a blob URL cannot be
    accidentally promoted to a repository identity.
    """
    raw = repository.strip().rstrip("/")
    if raw.startswith("git@github.com:"):
        raw = raw.removeprefix("git@github.com:")
    elif "://" in raw:
        parsed = urlparse(raw)
        if parsed.hostname is None or parsed.hostname.casefold() != "github.com":
            raise ValueError(f"not a GitHub repository: {repository!r}")
        raw = parsed.path.strip("/")
    if raw.casefold().startswith("github.com/"):
        raw = raw[len("github.com/") :]
    raw = raw.removesuffix(".git")
    parts = raw.split("/")
    if len(parts) != _REPOSITORY_ID_PARTS or not all(part.strip() for part in parts):
        raise ValueError(f"repository must be an exact owner/name identity: {repository!r}")
    if any(part in {".", ".."} for part in parts):
        raise ValueError(f"repository identity contains a path segment: {repository!r}")
    return "/".join(part.casefold() for part in parts)


def _lineage_id(snapshot: RepositorySnapshot) -> str:
    """Immediate explicitly evidenced source id, or the repository itself."""
    source = snapshot.fork_parent or snapshot.template_parent or snapshot.vendor_origin
    return canonical_repo_id(source or snapshot.repository)


def _merge_same_repository(
    left: RepositorySnapshot, right: RepositorySnapshot
) -> RepositorySnapshot:
    """Combine search hits for one repo, refusing inconsistent metadata."""
    metadata_left = (
        left.head_sha,
        left.license_spdx,
        left.is_fork,
        left.archived,
        left.default_branch,
        _lineage_id(left),
        left.dependency_version,
        left.graphify_version,
    )
    metadata_right = (
        right.head_sha,
        right.license_spdx,
        right.is_fork,
        right.archived,
        right.default_branch,
        _lineage_id(right),
        right.dependency_version,
        right.graphify_version,
    )
    if metadata_left != metadata_right:
        repo_id = canonical_repo_id(left.repository)
        raise ValueError(f"duplicate observations disagree for {repo_id}")
    evidence = tuple(
        sorted(
            set(left.evidence) | set(right.evidence),
            key=lambda item: (item.path, item.kind, item.exact, item.commit_sha),
        )
    )
    packages = tuple(sorted(set(left.declared_packages) | set(right.declared_packages)))
    return replace(left, evidence=evidence, declared_packages=packages)


def dedupe_candidates(repositories: tuple[RepositorySnapshot, ...]) -> tuple[CandidateGroup, ...]:
    """Group spelling aliases and explicit forks/templates/vendor copies.

    The relation is transitively resolved only through supplied snapshots.  A
    cycle fails closed with ``ValueError``; choosing an arbitrary member would
    make the output unstable and would conceal contradictory provenance.
    """
    by_id: dict[str, RepositorySnapshot] = {}
    for snapshot in repositories:
        repo_id = canonical_repo_id(snapshot.repository)
        previous = by_id.get(repo_id)
        by_id[repo_id] = (
            snapshot if previous is None else _merge_same_repository(previous, snapshot)
        )

    def root(repo_id: str) -> str:
        seen: set[str] = set()
        current = repo_id
        while current in by_id:
            if current in seen:
                raise ValueError(f"repository lineage contains a cycle at {current}")
            seen.add(current)
            parent = _lineage_id(by_id[current])
            if parent == current:
                break
            current = parent
        return current

    grouped: dict[str, list[RepositorySnapshot]] = {}
    for repo_id, snapshot in by_id.items():
        grouped.setdefault(root(repo_id), []).append(snapshot)

    groups: list[CandidateGroup] = []
    for source_id, members in sorted(grouped.items()):
        representative = next(
            (item for item in members if canonical_repo_id(item.repository) == source_id),
            min(members, key=lambda item: canonical_repo_id(item.repository)),
        )
        member_ids = tuple(sorted(canonical_repo_id(item.repository) for item in members))
        groups.append(CandidateGroup(source_id, representative, member_ids))
    return tuple(groups)


_CONSUMER_CODE_QUERIES = (
    '"graphifyy" filename:pyproject.toml',
    '"graphify" filename:requirements.txt',
    '"from graphify" language:Python',
    '"import graphify" language:Python',
    '"graphify query"',
    '"graphify extract"',
    '"graphify reflect"',
    '"graphify artifacts"',
)
_CONSUMER_COMMIT_QUERIES = ('"graphifyy"', '"graphify" extraction')
_ALTERNATIVE_CODE_QUERIES = (
    '"code knowledge graph" repository',
    '"code graph" AST repository',
    '"semantic code graph"',
)
_ALTERNATIVE_COMMIT_QUERIES = ('"code knowledge graph"', '"semantic code graph"')
_MAX_ALTERNATIVES = 10
_ALTERNATIVE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._+/#-]{0,127}")


def _alternative_names(alternatives: tuple[str, ...]) -> tuple[str, ...]:
    """Validate and case-insensitively dedupe caller-supplied search terms."""
    if any(not _ALTERNATIVE_NAME_RE.fullmatch(name) for name in alternatives):
        raise ValueError("alternative names must be non-empty literal search terms")
    names = tuple(dict.fromkeys(name.casefold() for name in alternatives))
    if len(names) > _MAX_ALTERNATIVES:
        raise ValueError(f"at most {_MAX_ALTERNATIVES} alternatives may be searched per plan")
    return names


def build_search_plan(
    *, alternatives: tuple[str, ...] = (), per_page: int = 100, max_pages: int = 2
) -> SearchPlan:
    """Construct bounded code and commit searches without executing them.

    Alternatives are caller-selected because discovery is evidence collection,
    not a place to silently bless a hard-coded competitor list.  The count is
    rejected rather than silently truncated: an omitted suffix would look like
    a complete technology scan.
    """
    names = _alternative_names(alternatives)

    requests = [
        SearchRequest(SearchKind.CODE, SearchTarget.GRAPHIFY_CONSUMER, query, per_page, max_pages)
        for query in _CONSUMER_CODE_QUERIES
    ]
    requests.extend(
        SearchRequest(
            SearchKind.COMMIT,
            SearchTarget.GRAPHIFY_CONSUMER,
            query,
            per_page,
            max_pages,
        )
        for query in _CONSUMER_COMMIT_QUERIES
    )
    requests.extend(
        SearchRequest(SearchKind.CODE, SearchTarget.ALTERNATIVE, query, per_page, max_pages)
        for query in _ALTERNATIVE_CODE_QUERIES
    )
    requests.extend(
        SearchRequest(SearchKind.COMMIT, SearchTarget.ALTERNATIVE, query, per_page, max_pages)
        for query in _ALTERNATIVE_COMMIT_QUERIES
    )
    for name in names:
        requests.extend(
            (
                SearchRequest(
                    SearchKind.CODE,
                    SearchTarget.ALTERNATIVE,
                    f'"{name}"',
                    per_page,
                    max_pages,
                ),
                SearchRequest(
                    SearchKind.COMMIT,
                    SearchTarget.ALTERNATIVE,
                    f'"{name}"',
                    per_page,
                    max_pages,
                ),
            )
        )
    return SearchPlan(tuple(requests))


def plan_main(args: list[str]) -> int:
    """Render the bounded discovery work for a read-only external adapter."""
    try:
        plan = build_search_plan(alternatives=tuple(args))
    except ValueError as exc:
        print(f"ecosystem-discovery-plan: FAIL: {exc}")
        return 2
    print(
        json.dumps(
            {
                "max_total_results": plan.max_total_results,
                "requests": [
                    {
                        "kind": request.kind.value,
                        "max_pages": request.max_pages,
                        "per_page": request.per_page,
                        "query": request.query,
                        "target": request.target.value,
                    }
                    for request in plan.requests
                ],
            },
            sort_keys=True,
        )
    )
    return 0
