# Copyright (c) 2026 Raymond Manaloto
"""Strict TOML parser and cross-field validation for source-group registries."""

from __future__ import annotations

import http.client
import json
import re
import sys
import tomllib
import urllib.parse
from collections.abc import Hashable, Sequence
from hashlib import sha256
from http import HTTPStatus
from pathlib import Path, PurePosixPath

import msgspec

from kb_setup.generated.source_groups import (
    ArtifactPolicy,
    Capability,
    DeepExtractionPolicy,
    GraphifyIgnorePolicy,
    GraphIngestionPolicy,
    LicenseStatus,
    PivotEvaluationStatus,
    PromotionPolicy,
    ReflectionPolicy,
    RegistryAdmissionPolicy,
    Role,
    SourceGroupConfig,
    SourceRecord,
    SourceStatus,
)

DEFAULT_SOURCE_GROUP_PATH = Path("sources/groups/graphify-ecosystem.toml")
DEFAULT_SOURCE_GROUP_BASELINE = Path("sources/groups/graphify-ecosystem.baseline.json")
_REMOTE_TIMEOUT_SECONDS = 10.0


class SourceGroupValidationError(ValueError):
    """A source-group document violates the structural or semantic contract."""


_ALLOWED_TRANSITIONS: dict[SourceStatus, frozenset[SourceStatus]] = {
    SourceStatus.DISCOVERED: frozenset(
        {
            SourceStatus.REVIEWING,
            SourceStatus.LICENSE_REVIEW_REQUIRED,
            SourceStatus.REJECTED,
        }
    ),
    SourceStatus.REVIEWING: frozenset(
        {
            SourceStatus.LICENSE_REVIEW_REQUIRED,
            SourceStatus.CANDIDATE,
            SourceStatus.QUARANTINED,
            SourceStatus.REJECTED,
        }
    ),
    SourceStatus.LICENSE_REVIEW_REQUIRED: frozenset(
        {
            SourceStatus.REVIEWING,
            SourceStatus.CANDIDATE,
            SourceStatus.QUARANTINED,
            SourceStatus.REJECTED,
        }
    ),
    SourceStatus.CANDIDATE: frozenset(
        {
            SourceStatus.ADMITTED,
            SourceStatus.LICENSE_REVIEW_REQUIRED,
            SourceStatus.QUARANTINED,
            SourceStatus.REJECTED,
        }
    ),
    SourceStatus.ADMITTED: frozenset({SourceStatus.QUARANTINED, SourceStatus.RETIRED}),
    SourceStatus.QUARANTINED: frozenset(
        {
            SourceStatus.REVIEWING,
            SourceStatus.LICENSE_REVIEW_REQUIRED,
            SourceStatus.CANDIDATE,
            SourceStatus.REJECTED,
            SourceStatus.RETIRED,
        }
    ),
    SourceStatus.REJECTED: frozenset(),
    SourceStatus.RETIRED: frozenset(),
}


def parse_source_groups(data: bytes | str) -> SourceGroupConfig:
    """Parse TOML into the generated strict contract and validate its invariants."""
    text = data.decode("utf-8") if isinstance(data, bytes) else data
    try:
        raw = tomllib.loads(text)
        _fill_toml_nulls(raw)
        config = msgspec.convert(raw, type=SourceGroupConfig, strict=True)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError, msgspec.ValidationError) as exc:
        raise SourceGroupValidationError(f"invalid source-group config: {exc}") from exc
    validate_source_groups(config)
    return config


def load_source_groups(path: Path = DEFAULT_SOURCE_GROUP_PATH) -> SourceGroupConfig:
    """Load and validate one source-group TOML document."""
    return parse_source_groups(path.read_bytes())


def check_main(repo_root: Path, args: Sequence[str]) -> int:
    """Validate one registry and print a bounded machine-readable census."""
    if len(args) > 1:
        print("kb-setup source-groups-check [path]", file=sys.stderr)
        return 2
    path = Path(args[0]) if args else DEFAULT_SOURCE_GROUP_PATH
    if not path.is_absolute():
        path = repo_root / path
    try:
        config = load_source_groups(path)
        baseline = DEFAULT_SOURCE_GROUP_BASELINE
        if not baseline.is_absolute():
            baseline = repo_root / baseline
        validate_reviewed_baseline(config, baseline)
        validate_remote_authority(config, baseline)
    except (OSError, SourceGroupValidationError) as exc:
        print(f"source-groups-check: FAIL: {exc}", file=sys.stderr)
        return 1
    statuses: dict[str, int] = {}
    for source in config.sources:
        statuses[source.status.value] = statuses.get(source.status.value, 0) + 1
    print(
        json.dumps(
            {
                "group_id": config.group_id,
                "path": str(path),
                "source_count": len(config.sources),
                "statuses": dict(sorted(statuses.items())),
            },
            sort_keys=True,
        )
    )
    return 0


def validate_reviewed_baseline(config: SourceGroupConfig, path: Path) -> None:
    """Bind registry membership, identity, ref, reviewed SHA, and evidence to review."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceGroupValidationError(f"reviewed baseline unavailable: {exc}") from exc
    if raw.get("schema_version") != config.schema_version or raw.get("group_id") != config.group_id:
        raise SourceGroupValidationError("reviewed baseline identity does not match registry")
    expected_sources = raw.get("sources")
    if not isinstance(expected_sources, list):
        raise SourceGroupValidationError("reviewed baseline has no source list")
    expected = {
        str(item.get("source_id")): item for item in expected_sources if isinstance(item, dict)
    }
    actual = {source.source_id: source for source in config.sources}
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        added = sorted(set(actual) - set(expected))
        raise SourceGroupValidationError(
            f"registry membership differs from reviewed baseline: missing={missing}, added={added}"
        )
    for source_id, source in actual.items():
        _validate_reviewed_source(source, expected[source_id])


def validate_remote_authority(config: SourceGroupConfig, baseline_path: Path) -> None:
    """Verify local review claims against GitHub repository and Git object identities."""
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceGroupValidationError(f"reviewed baseline unavailable: {exc}") from exc
    raw_sources = baseline.get("sources")
    if not isinstance(raw_sources, list):
        raise SourceGroupValidationError("reviewed baseline has no source list")
    reviewed = {str(item.get("source_id")): item for item in raw_sources if isinstance(item, dict)}
    for source in config.sources:
        _validate_remote_source(source, reviewed[source.source_id])


def _validate_remote_source(source: SourceRecord, reviewed: dict[str, object]) -> None:
    repo_id = source.repository.repo_id
    encoded_repo = "/".join(urllib.parse.quote(part, safe="") for part in repo_id.split("/"))
    repository = _fetch_json(f"https://api.github.com/repos/{encoded_repo}", source.source_id)
    _validate_remote_identity(source, repository)

    commit = source.repository.reviewed_commit
    if commit is None:
        raise SourceGroupValidationError(f"{source.source_id}: reviewed commit is required")
    remote_commit = _fetch_json(
        f"https://api.github.com/repos/{encoded_repo}/commits/{commit}", source.source_id
    )
    if remote_commit.get("sha") != commit:
        raise SourceGroupValidationError(
            f"{source.source_id}: reviewed commit is not authoritative"
        )

    _validate_remote_evidence(source, reviewed, encoded_repo, commit)


def _validate_remote_identity(source: SourceRecord, repository: dict[str, object]) -> None:
    repo_id = source.repository.repo_id
    remote_identity = repository.get("full_name")
    remote_url = repository.get("html_url")
    if not isinstance(remote_identity, str) or remote_identity.casefold() != repo_id.casefold():
        raise SourceGroupValidationError(f"{source.source_id}: remote repository identity mismatch")
    if (
        not isinstance(remote_url, str)
        or remote_url.rstrip("/").casefold()
        != source.repository.canonical_url.rstrip("/").casefold()
    ):
        raise SourceGroupValidationError(f"{source.source_id}: remote canonical URL mismatch")
    if repository.get("default_branch") != source.repository.default_branch:
        raise SourceGroupValidationError(f"{source.source_id}: remote default branch mismatch")
    if repository.get("fork") is not source.repository.is_fork:
        raise SourceGroupValidationError(f"{source.source_id}: remote fork identity mismatch")
    if repository.get("archived") is not source.repository.is_archived:
        raise SourceGroupValidationError(f"{source.source_id}: remote archive identity mismatch")


def _validate_remote_evidence(
    source: SourceRecord,
    reviewed: dict[str, object],
    encoded_repo: str,
    commit: str,
) -> None:
    evidence_by_path = reviewed.get("capability_evidence")
    if not isinstance(evidence_by_path, list):
        raise SourceGroupValidationError(f"{source.source_id}: reviewed evidence is invalid")
    for evidence in evidence_by_path:
        if not isinstance(evidence, dict):
            raise SourceGroupValidationError(f"{source.source_id}: reviewed evidence is invalid")
        path = evidence.get("path")
        expected_hash = evidence.get("content_sha256")
        if not isinstance(path, str) or not isinstance(expected_hash, str):
            raise SourceGroupValidationError(f"{source.source_id}: reviewed evidence is invalid")
        encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
        content = _fetch_remote(
            f"https://raw.githubusercontent.com/{encoded_repo}/{commit}/{encoded_path}",
            source.source_id,
        )
        if sha256(content).hexdigest() != expected_hash:
            raise SourceGroupValidationError(
                f"{source.source_id}: evidence content differs from reviewed Git blob"
            )


def _fetch_json(url: str, source_id: str) -> dict[str, object]:
    try:
        payload = json.loads(_fetch_remote(url, source_id))
    except json.JSONDecodeError as exc:
        raise SourceGroupValidationError(
            f"{source_id}: remote authority returned invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise SourceGroupValidationError(f"{source_id}: remote authority returned invalid JSON")
    return payload


def _fetch_remote(url: str, source_id: str) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    allowed_hosts = frozenset({"api.github.com", "raw.githubusercontent.com"})
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
        raise SourceGroupValidationError(f"{source_id}: remote authority URL is not permitted")
    target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=_REMOTE_TIMEOUT_SECONDS)
    try:
        connection.request(
            "GET",
            target,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "kb-source-groups/1",
            },
        )
        response = connection.getresponse()
        body = response.read()
    except (OSError, http.client.HTTPException) as exc:
        raise SourceGroupValidationError(
            f"{source_id}: remote authority unavailable for {url}: {exc}"
        ) from exc
    finally:
        connection.close()
    if response.status != HTTPStatus.OK:
        raise SourceGroupValidationError(
            f"{source_id}: remote authority returned HTTP {response.status} for {url}"
        )
    return body


def _validate_reviewed_source(source: SourceRecord, expected: dict[str, object]) -> None:
    identity = {
        "repo_id": source.repository.repo_id,
        "canonical_url": source.repository.canonical_url,
        "ref": source.repository.ref,
        "reviewed_commit": source.repository.reviewed_commit,
    }
    for field, value in identity.items():
        if expected.get(field) != value:
            raise SourceGroupValidationError(
                f"{source.source_id}: {field} differs from reviewed baseline"
            )
    evidence = [
        {"capability": item.capability.value, "path": item.path, "commit": item.commit}
        for item in source.capability_evidence
    ]
    expected_evidence = expected.get("capability_evidence")
    if not isinstance(expected_evidence, list):
        raise SourceGroupValidationError(
            f"{source.source_id}: reviewed baseline capability evidence is invalid"
        )
    reviewed_evidence = [
        {key: item.get(key) for key in ("capability", "path", "commit")}
        for item in expected_evidence
        if isinstance(item, dict)
    ]
    if len(reviewed_evidence) != len(expected_evidence) or reviewed_evidence != evidence:
        raise SourceGroupValidationError(
            f"{source.source_id}: capability evidence differs from reviewed baseline"
        )
    for item in expected_evidence:
        content_sha256 = item.get("content_sha256")
        if (
            not isinstance(content_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", content_sha256) is None
        ):
            raise SourceGroupValidationError(
                f"{source.source_id}: evidence lacks reviewed content SHA-256"
            )
    selected = set(source.paths.include_paths)
    for item in source.capability_evidence:
        if item.path not in selected:
            raise SourceGroupValidationError(
                f"{source.source_id}: evidence path {item.path!r} is not a selected in-repo path"
            )
        if item.commit != source.repository.reviewed_commit:
            raise SourceGroupValidationError(
                f"{source.source_id}: evidence commit does not bind the reviewed commit"
            )


def validate_source_groups(config: SourceGroupConfig) -> None:
    """Validate invariants JSON Schema and msgspec cannot express."""
    source_ids = [source.source_id for source in config.sources]
    _require_unique(source_ids, "source_id")
    repo_ids = [source.repository.repo_id.casefold() for source in config.sources]
    _require_unique(repo_ids, "repository.repo_id")
    canonical_urls = [source.repository.canonical_url.casefold() for source in config.sources]
    _require_unique(canonical_urls, "repository.canonical_url")

    for source in config.sources:
        _validate_source(source)


def validate_transition(previous: SourceGroupConfig, current: SourceGroupConfig) -> None:
    """Reject removal, identity mutation, reviewed-SHA mutation, and illegal status moves."""
    validate_source_groups(previous)
    validate_source_groups(current)
    if previous.schema_version != current.schema_version:
        raise SourceGroupValidationError("schema_version cannot change in a registry transition")
    if previous.group_id != current.group_id:
        raise SourceGroupValidationError("group_id cannot change in a registry transition")

    previous_by_id = {source.source_id: source for source in previous.sources}
    current_by_id = {source.source_id: source for source in current.sources}
    removed = sorted(previous_by_id.keys() - current_by_id.keys())
    if removed:
        raise SourceGroupValidationError(
            f"source records cannot be removed; retire or reject them instead: {removed}"
        )

    for source_id, old in previous_by_id.items():
        new = current_by_id[source_id]
        _validate_identity_transition(old, new)
        if old.status != new.status and new.status not in _ALLOWED_TRANSITIONS[old.status]:
            raise SourceGroupValidationError(
                f"invalid status transition for {source_id}: {old.status} -> {new.status}"
            )
        if old.status == new.status:
            if old.timestamps.last_status_change_at_ns != new.timestamps.last_status_change_at_ns:
                raise SourceGroupValidationError(
                    f"{source_id}: last_status_change_at_ns changed without a status change"
                )
        elif new.timestamps.last_status_change_at_ns <= old.timestamps.last_status_change_at_ns:
            raise SourceGroupValidationError(
                f"{source_id}: a status change requires a later last_status_change_at_ns"
            )


def _validate_identity_transition(old: SourceRecord, new: SourceRecord) -> None:
    if old.repository.repo_id != new.repository.repo_id:
        raise SourceGroupValidationError(f"{old.source_id}: repo_id is immutable")
    if old.repository.canonical_url != new.repository.canonical_url:
        raise SourceGroupValidationError(f"{old.source_id}: canonical_url is immutable")
    if old.timestamps.discovered_at_ns != new.timestamps.discovered_at_ns:
        raise SourceGroupValidationError(f"{old.source_id}: discovered_at_ns is immutable")
    old_reviewed = old.repository.reviewed_commit
    new_reviewed = new.repository.reviewed_commit
    if old_reviewed is not None and new_reviewed != old_reviewed:
        raise SourceGroupValidationError(f"{old.source_id}: reviewed_commit is immutable once set")


def _validate_source(source: SourceRecord) -> None:
    prefix = source.source_id
    repository = source.repository
    expected_url = f"https://github.com/{repository.repo_id}"
    if repository.canonical_url.casefold() != expected_url.casefold():
        raise SourceGroupValidationError(
            f"{prefix}: canonical_url must match repository.repo_id exactly"
        )

    _validate_paths(source)
    _require_unique(source.warnings, f"{prefix}.warnings")
    _require_unique(
        source.pivot.comparison_dimensions,
        f"{prefix}.pivot.comparison_dimensions",
    )
    _validate_timestamps(source)
    _validate_review_evidence(source)
    _validate_license(source)
    _validate_policy_state(source)
    _validate_budgets(source)
    _validate_pivot(source)


def _validate_paths(source: SourceRecord) -> None:
    prefix = source.source_id
    include = source.paths.include_paths
    exclude = source.paths.exclude_paths
    _require_unique(include, f"{prefix}.paths.include_paths")
    _require_unique(exclude, f"{prefix}.paths.exclude_paths")
    for path in [*include, *exclude]:
        if not _is_exact_repo_path(path):
            raise SourceGroupValidationError(f"{prefix}: path is not repository-relative: {path!r}")
    overlap = sorted(set(include) & set(exclude))
    if overlap:
        raise SourceGroupValidationError(
            f"{prefix}: selected and excluded paths overlap: {overlap}"
        )

    ignore_policy = source.paths.graphifyignore_policy
    ignore_path = source.paths.graphifyignore_path
    if ignore_path is not None and not _is_exact_repo_path(ignore_path):
        raise SourceGroupValidationError(
            f"{prefix}: graphifyignore_path is not repository-relative: {ignore_path!r}"
        )
    if ignore_policy == GraphifyIgnorePolicy.REQUIRE_AND_HONOR and ignore_path is None:
        raise SourceGroupValidationError(
            f"{prefix}: REQUIRE_AND_HONOR requires graphifyignore_path"
        )
    if ignore_policy == GraphifyIgnorePolicy.EXPLICIT_PATHS_ONLY and ignore_path is not None:
        raise SourceGroupValidationError(
            f"{prefix}: EXPLICIT_PATHS_ONLY forbids graphifyignore_path"
        )


def _validate_timestamps(source: SourceRecord) -> None:
    prefix = source.source_id
    timestamps = source.timestamps
    if timestamps.last_status_change_at_ns < timestamps.discovered_at_ns:
        raise SourceGroupValidationError(f"{prefix}: last_status_change_at_ns predates discovery")
    if (
        timestamps.last_reviewed_at_ns is not None
        and timestamps.last_reviewed_at_ns < timestamps.discovered_at_ns
    ):
        raise SourceGroupValidationError(f"{prefix}: last_reviewed_at_ns predates discovery")
    if (
        source.repository.current_head is not None
        and source.repository.current_head.observed_at_ns < timestamps.discovered_at_ns
    ):
        raise SourceGroupValidationError(f"{prefix}: current head observation predates discovery")
    if source.repository.current_head is not None and source.repository.reviewed_commit is not None:
        update_observed = source.repository.current_head.commit != source.repository.reviewed_commit
        if source.refresh.update_available != update_observed:
            raise SourceGroupValidationError(
                f"{prefix}: update_available disagrees with reviewed and current commits"
            )

    refresh = source.refresh
    if refresh.last_checked_at_ns is not None:
        if refresh.last_checked_at_ns < timestamps.discovered_at_ns:
            raise SourceGroupValidationError(f"{prefix}: refresh check predates discovery")
        if (
            refresh.next_check_after_ns is not None
            and refresh.next_check_after_ns <= refresh.last_checked_at_ns
        ):
            raise SourceGroupValidationError(
                f"{prefix}: next refresh must be later than the last check"
            )


def _validate_review_evidence(source: SourceRecord) -> None:
    prefix = source.source_id
    reviewed_commit = source.repository.reviewed_commit
    if reviewed_commit is None:
        if source.timestamps.last_reviewed_at_ns is not None:
            raise SourceGroupValidationError(
                f"{prefix}: last_reviewed_at_ns requires reviewed_commit"
            )
        if source.capability_evidence or source.license.evidence:
            raise SourceGroupValidationError(
                f"{prefix}: evidence requires an immutable reviewed_commit"
            )
    elif source.timestamps.last_reviewed_at_ns is None:
        raise SourceGroupValidationError(f"{prefix}: reviewed_commit requires last_reviewed_at_ns")

    evidence_keys: list[tuple[Capability, object, str, str]] = []
    for evidence in source.capability_evidence:
        if evidence.commit != reviewed_commit:
            raise SourceGroupValidationError(
                f"{prefix}: capability evidence commit must equal reviewed_commit"
            )
        if not _is_exact_repo_path(evidence.path):
            raise SourceGroupValidationError(
                f"{prefix}: capability evidence path is not repository-relative"
            )
        evidence_keys.append((evidence.capability, evidence.stage, evidence.path, evidence.commit))
    _require_unique(evidence_keys, f"{prefix}.capability_evidence")

    if (
        source.status in {SourceStatus.CANDIDATE, SourceStatus.ADMITTED}
        and not source.capability_evidence
    ):
        raise SourceGroupValidationError(f"{prefix}: {source.status} requires capability evidence")


def _validate_license(source: SourceRecord) -> None:
    prefix = source.source_id
    license_info = source.license
    reviewed_commit = source.repository.reviewed_commit
    _require_unique(
        [(evidence.path, evidence.commit) for evidence in license_info.evidence],
        f"{prefix}.license.evidence",
    )
    for evidence in license_info.evidence:
        if evidence.commit != reviewed_commit:
            raise SourceGroupValidationError(
                f"{prefix}: license evidence commit must equal reviewed_commit"
            )
        if not _is_exact_repo_path(evidence.path):
            raise SourceGroupValidationError(
                f"{prefix}: license evidence path is not repository-relative"
            )

    unresolved = {LicenseStatus.UNKNOWN, LicenseStatus.REVIEW_REQUIRED}
    if license_info.status in unresolved:
        if license_info.spdx_id is not None or license_info.reviewed_at_ns is not None:
            raise SourceGroupValidationError(
                f"{prefix}: unresolved license cannot claim SPDX or review completion"
            )
        if license_info.evidence:
            raise SourceGroupValidationError(
                f"{prefix}: unresolved license must not claim conclusive evidence"
            )
    else:
        if not license_info.spdx_id or not license_info.evidence:
            raise SourceGroupValidationError(
                f"{prefix}: resolved license requires SPDX and exact evidence"
            )
        if license_info.reviewed_at_ns is None:
            raise SourceGroupValidationError(f"{prefix}: resolved license requires reviewed_at_ns")


def _validate_policy_state(source: SourceRecord) -> None:
    _validate_license_policy(source)
    _validate_admission_policy(source)
    _validate_output_policy(source)


def _validate_license_policy(source: SourceRecord) -> None:
    policies = source.policies
    admitted = source.status == SourceStatus.ADMITTED
    if source.license.status in {LicenseStatus.UNKNOWN, LicenseStatus.REVIEW_REQUIRED}:
        if admitted or policies.registry_admission == RegistryAdmissionPolicy.ADMITTED:
            raise SourceGroupValidationError(f"{source.source_id}: unknown license cannot admit")
        if policies.deep_extraction != DeepExtractionPolicy.DISABLED:
            raise SourceGroupValidationError(
                f"{source.source_id}: unknown license cannot deep-extract"
            )
        if policies.promotion != PromotionPolicy.BLOCKED:
            raise SourceGroupValidationError(f"{source.source_id}: unknown license cannot promote")

    if source.status == SourceStatus.LICENSE_REVIEW_REQUIRED and source.license.status not in {
        LicenseStatus.UNKNOWN,
        LicenseStatus.REVIEW_REQUIRED,
    }:
        raise SourceGroupValidationError(
            f"{source.source_id}: LICENSE_REVIEW_REQUIRED needs an unresolved license"
        )


def _validate_admission_policy(source: SourceRecord) -> None:
    if source.status == SourceStatus.ADMITTED:
        _validate_admitted_source(source)
    else:
        _validate_metadata_only_source(source)
    _validate_denial_policy(source)


def _validate_admitted_source(source: SourceRecord) -> None:
    prefix = source.source_id
    policies = source.policies
    if policies.registry_admission != RegistryAdmissionPolicy.ADMITTED:
        raise SourceGroupValidationError(
            f"{prefix}: ADMITTED status requires ADMITTED registry policy"
        )
    if policies.graph_ingestion != GraphIngestionPolicy.SELECTED_PATHS_ONLY:
        raise SourceGroupValidationError(
            f"{prefix}: admitted source requires selected-path graph ingestion"
        )
    if not source.paths.include_paths:
        raise SourceGroupValidationError(f"{prefix}: admitted source has no selected paths")
    if source.repository.reviewed_commit is None:
        raise SourceGroupValidationError(f"{prefix}: admitted source has no reviewed commit")


def _validate_metadata_only_source(source: SourceRecord) -> None:
    prefix = source.source_id
    policies = source.policies
    if policies.registry_admission == RegistryAdmissionPolicy.ADMITTED:
        raise SourceGroupValidationError(
            f"{prefix}: registry admission is separate and cannot precede ADMITTED status"
        )
    if policies.graph_ingestion != GraphIngestionPolicy.DISABLED:
        raise SourceGroupValidationError(
            f"{prefix}: metadata-only source cannot enable graph ingestion"
        )
    if policies.deep_extraction != DeepExtractionPolicy.DISABLED:
        raise SourceGroupValidationError(
            f"{prefix}: metadata-only source cannot enable deep extraction"
        )
    if policies.reflection != ReflectionPolicy.DISABLED:
        raise SourceGroupValidationError(f"{prefix}: metadata-only source cannot enable reflection")
    if policies.artifacts != ArtifactPolicy.DISABLED:
        raise SourceGroupValidationError(
            f"{prefix}: metadata-only source cannot generate graph artifacts"
        )
    if policies.promotion != PromotionPolicy.BLOCKED:
        raise SourceGroupValidationError(f"{prefix}: metadata-only source cannot enable promotion")


def _validate_denial_policy(source: SourceRecord) -> None:
    prefix = source.source_id
    policies = source.policies

    if source.status == SourceStatus.REJECTED:
        if policies.registry_admission != RegistryAdmissionPolicy.DENIED:
            raise SourceGroupValidationError(
                f"{prefix}: REJECTED status requires DENIED registry policy"
            )
    elif policies.registry_admission == RegistryAdmissionPolicy.DENIED:
        raise SourceGroupValidationError(
            f"{prefix}: DENIED registry policy requires REJECTED status"
        )


def _validate_output_policy(source: SourceRecord) -> None:
    prefix = source.source_id
    policies = source.policies
    if (
        policies.reflection != ReflectionPolicy.DISABLED
        and policies.deep_extraction == DeepExtractionPolicy.DISABLED
    ):
        raise SourceGroupValidationError(
            f"{prefix}: reflection requires successful deep extraction policy"
        )
    semantic_artifacts = {
        ArtifactPolicy.SEMANTIC_ON_SUCCESS,
        ArtifactPolicy.STRUCTURAL_AND_SEMANTIC,
    }
    if (
        policies.artifacts in semantic_artifacts
        and policies.deep_extraction == DeepExtractionPolicy.DISABLED
    ):
        raise SourceGroupValidationError(f"{prefix}: semantic artifacts require deep extraction")


def _validate_budgets(source: SourceRecord) -> None:
    prefix = source.source_id
    policies = source.policies
    source_budget = source.budgets.source
    semantic_budget = source.budgets.semantic
    if policies.graph_ingestion != GraphIngestionPolicy.DISABLED:
        values = (
            source_budget.estimated_checkout_bytes,
            source_budget.estimated_selected_files,
            source_budget.estimated_ingest_seconds,
        )
        if any(value is None for value in values):
            raise SourceGroupValidationError(
                f"{prefix}: graph ingestion requires complete source budget estimates"
            )
    if policies.deep_extraction != DeepExtractionPolicy.DISABLED:
        values = (
            semantic_budget.estimated_input_tokens,
            semantic_budget.max_output_tokens,
            semantic_budget.estimated_deep_seconds,
            semantic_budget.max_cost_usd_micros,
        )
        if any(value is None for value in values):
            raise SourceGroupValidationError(
                f"{prefix}: deep extraction requires complete semantic budget estimates"
            )
        if semantic_budget.max_output_tokens == 0:
            raise SourceGroupValidationError(
                f"{prefix}: deep extraction max_output_tokens must be positive"
            )


def _validate_pivot(source: SourceRecord) -> None:
    prefix = source.source_id
    pivot = source.pivot
    if pivot.is_candidate:
        if source.role != Role.ALTERNATIVE_TECHNOLOGY:
            raise SourceGroupValidationError(
                f"{prefix}: pivot candidate must have ALTERNATIVE_TECHNOLOGY role"
            )
        if not pivot.technology_name or not pivot.comparison_dimensions:
            raise SourceGroupValidationError(
                f"{prefix}: pivot candidate requires a technology and comparison dimensions"
            )
    else:
        if source.role == Role.ALTERNATIVE_TECHNOLOGY:
            raise SourceGroupValidationError(
                f"{prefix}: ALTERNATIVE_TECHNOLOGY must be tracked as a pivot candidate"
            )
        if (
            pivot.technology_name is not None
            or pivot.status != PivotEvaluationStatus.NOT_EVALUATED
            or pivot.comparison_dimensions
            or pivot.last_evaluated_at_ns is not None
            or pivot.next_evaluation_after_ns is not None
            or pivot.recommendation is not None
        ):
            raise SourceGroupValidationError(
                f"{prefix}: non-pivot source carries pivot evaluation metadata"
            )


def _require_unique[T: Hashable](values: Sequence[T], field: str) -> None:
    seen: set[T] = set()
    duplicates: set[T] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise SourceGroupValidationError(f"duplicate {field}: {sorted(map(str, duplicates))}")


def _fill_toml_nulls(raw: dict[str, object]) -> None:
    """Fill required nullable schema fields, since TOML has no null literal."""
    sources = raw.get("sources")
    if not isinstance(sources, list):
        return
    nullable_fields = {
        "repository": ("reviewed_commit", "current_head"),
        "license": ("spdx_id", "reviewed_at_ns"),
        "paths": ("graphifyignore_path",),
        "timestamps": ("last_reviewed_at_ns",),
        "refresh": ("last_checked_at_ns", "next_check_after_ns"),
        "pivot": (
            "technology_name",
            "last_evaluated_at_ns",
            "next_evaluation_after_ns",
            "recommendation",
        ),
    }
    budget_fields = {
        "source": (
            "estimated_checkout_bytes",
            "estimated_selected_files",
            "estimated_ingest_seconds",
        ),
        "semantic": (
            "estimated_input_tokens",
            "max_output_tokens",
            "estimated_deep_seconds",
            "max_cost_usd_micros",
        ),
    }
    for source in sources:
        if not isinstance(source, dict):
            continue
        for table_name, fields in nullable_fields.items():
            _fill_fields(source.get(table_name), fields)
        _fill_budget_nulls(source.get("budgets"), budget_fields)


def _fill_budget_nulls(budgets: object, budget_fields: dict[str, tuple[str, ...]]) -> None:
    if not isinstance(budgets, dict):
        return
    for table_name, fields in budget_fields.items():
        _fill_fields(budgets.get(table_name), fields)


def _fill_fields(table: object, fields: tuple[str, ...]) -> None:
    if not isinstance(table, dict):
        return
    for field in fields:
        table.setdefault(field, None)


def _is_exact_repo_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        bool(value)
        and not value.startswith("/")
        and "//" not in value
        and "\\" not in value
        and path.as_posix() == value
        and ".." not in path.parts
        and "." not in path.parts
    )
