# Copyright (c) 2026 Raymond Manaloto
"""Fail-closed real-Claude semantic slice for the pinned Graphify source."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import warnings
from collections.abc import Generator, Mapping
from contextlib import contextmanager, redirect_stderr
from pathlib import Path

import msgspec

from kb_setup.graphify_baseline import RuntimeIdentity

_CLAUDE_MODEL = "claude-haiku-4-5-20251001"
_CLAUDE_CANONICAL_MODEL = "claude-haiku-4-5"
_CLAUDE_PROVIDER = "firstParty"
_MAX_TURNS_WITH_ONE_STRUCTURED_REPAIR = 3
_MAX_COST_USD = 0.25
CLAUDE_MODEL = _CLAUDE_MODEL
GRAPHIFY_SCHEMA_SHA256 = "69d307d23913e0cccf5809316a3432b85210776bd5626a4ad0af1317d6113324"

SOURCE_REF = "v0.9.42"
SOURCE_COMMIT = "7fe58b0b0f3873be9a21c30106b8b8527c353aa6"
SOURCE_TREE = "15ca81a8dbd3ded7083c4b573197140e62e95fcc"
SOURCE_PATH = "docs/how-it-works.md"
SOURCE_GIT_OBJECT = "e0e6e5275dfec50b25c38590f151ebd9e263f383"
SOURCE_SHA256 = "cd4a67001704eddc557d67eaa783d0608cd200302fa1b89c3f1a4819497cdc26"
SOURCE_SIZE = 5147
_CANDIDATE_SCHEMA = "graphify-real-semantic-slice/v0"
_ACCEPTED_CANDIDATE_MANIFEST_SHA256 = (
    "8d3407f5cca4c2ddca54d9a4f25df0727cbd5fd2fd378754d48afced220e94a7"
)
_MAX_SEMANTIC_ARGS = 2
_RETAINED_CLAUDE_ARG_COUNT = 17
_REQUIRED_MEMBERS = frozenset({"adapter-metadata.json", "receipt.json", "semantic-fragment.json"})

_REQUIRED_CLAUDE_FLAGS = (
    "--json-schema",
    "--max-budget-usd",
    "--model",
    "--no-chrome",
    "--no-session-persistence",
    "--output-format",
    "--permission-mode",
    "--safe-mode",
    "--strict-mcp-config",
    "--tools",
)
_CHILD_CONTROL_ENV = {
    "API_TIMEOUT_MS": "120000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "CLAUDE_CODE_DISABLE_TELEMETRY": "1",
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "4096",
    "CLAUDE_CODE_MAX_RETRIES": "0",
    "MAX_STRUCTURED_OUTPUT_RETRIES": "1",
}
_CHILD_BASE_ENV_NAMES = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LOGNAME",
    "SHELL",
    "TMPDIR",
    "USER",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
)

_ROUTE_OVERRIDE_NAMES = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_BEDROCK_BASE_URL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_SMALL_FAST_MODEL",
        "ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION",
        "ANTHROPIC_VERTEX_BASE_URL",
        "CLAUDE_CODE_SKIP_BEDROCK_AUTH",
        "CLAUDE_CODE_SKIP_VERTEX_AUTH",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_SUBAGENT_MODEL",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_FOUNDRY",
        "CLAUDE_CODE_USE_VERTEX",
        "ANTHROPIC_VERTEX_PROJECT_ID",
        "CLOUD_ML_REGION",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "AWS_PROFILE",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_API_KEY",
        "ANTHROPIC_CUSTOM_HEADERS",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
    }
)


class AuthIdentity(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Non-sensitive Claude subscription routing identity."""

    logged_in: bool
    auth_method: str
    api_provider: str
    subscription_type: str


class ClaudePreflight(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Read-only identity and capability proof required before inference."""

    executable: str
    executable_sha256: str
    version: str
    help_sha256: str
    required_flags: tuple[str, ...]
    auth: AuthIdentity
    environment_names: tuple[str, ...]
    graphify_runtime: RuntimeIdentity
    graphify_version: str
    graphify_semantic_fingerprint_sha256: str


class SourceIdentity(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Exact immutable source bytes admitted to the semantic slice."""

    source: str
    ref: str
    commit: str
    tree: str
    path: str
    git_object: str
    sha256: str
    size: int


class ArtifactMember(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """One independently rehashed regular-file candidate member."""

    name: str
    sha256: str
    size: int


class ChunkEvidence(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Exact one-unit dispatch and result binding for the semantic call."""

    ordinal: int
    total: int
    source_path: str
    source_git_object: str
    source_sha256: str
    source_size: int
    prompt_sha256: str
    fragment_sha256: str
    node_count: int
    edge_count: int
    hyperedge_count: int


class ExecutionConfig(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Exact non-secret runtime controls for the one authorized call."""

    api_timeout_ms: int
    claude_code_disable_nonessential_traffic: bool
    claude_code_disable_telemetry: bool
    claude_code_max_output_tokens: int
    claude_code_max_retries: int
    max_structured_output_retries: int
    graphify_api_timeout_seconds: int
    graphify_no_incremental_cache: bool
    chunk_size: int
    token_budget: int | None
    max_concurrency: int
    max_retry_depth: int
    deep_mode: bool


class SemanticReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Public receipt for exactly one real Graphify-to-Claude semantic call."""

    schema_id: str
    status: str
    source: SourceIdentity
    runtime: ClaudePreflight
    adapter_metadata_sha256: str
    semantic_fragment_sha256: str
    chunks: tuple[ChunkEvidence, ...]
    execution_config: ExecutionConfig
    attempts: int
    backend: str
    model: str
    max_concurrency: int
    max_retry_depth: int
    failed_chunks: int
    uncovered_files: tuple[str, ...]
    out_of_scope_dropped: int
    semantic_node_count: int
    semantic_edge_count: int
    semantic_hyperedge_count: int
    graph_node_count: int
    graph_edge_count: int
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


class CandidateManifest(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Content-addressed public manifest for one complete semantic candidate."""

    schema_id: str
    source: SourceIdentity
    members: tuple[ArtifactMember, ...]
    warnings: tuple[str, ...]


class SemanticVerification(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Fail-closed public verification verdict."""

    state: str
    structural_complete: bool
    real_semantic_complete: bool
    reasons: tuple[str, ...]


_ACCEPTED_GRAPHIFY_RUNTIME = RuntimeIdentity(
    version="0.9.42",
    cli_version="0.9.42",
    sdk_version="0.9.42",
    executable=".venv/bin/graphify",
    sdk_fingerprint_sha256="b10406f90fe7c369fc1396991679f6e4490e59f9351332c30b9fe2216f071157",
    wheel_sha256="d87bec57d5dbca1203ce719f4b4afb83ae5eb6cea1b4af2d62d0c10c1c3e26e6",
    sdist_sha256="a45ff2d9517340a429d8e74a7dc7a74062d1bbc18019f26ec62b98b03863eb1b",
)
_ACCEPTED_CLAUDE_VERSION = "2.1.232"
_ACCEPTED_CLAUDE_EXECUTABLE_SHA256 = (
    "7b39c1588df919d001dea3ffd5651adb682f2451b5a0e18d42d4233296b53cc7"
)
_ACCEPTED_CLAUDE_HELP_SHA256 = "71ad650f59e08ae40ede14c534db4f49d8590ee5a4f92f6da2882d3a5560fea6"
_ACCEPTED_SEMANTIC_FINGERPRINT_SHA256 = (
    "43122fca6fdda78fa16630a89ede645f06b7fdbded00377cd27188f627d371d9"
)
_ACCEPTED_EXECUTION_CONFIG = ExecutionConfig(
    api_timeout_ms=120_000,
    claude_code_disable_nonessential_traffic=True,
    claude_code_disable_telemetry=True,
    claude_code_max_output_tokens=4096,
    claude_code_max_retries=0,
    max_structured_output_retries=1,
    graphify_api_timeout_seconds=120,
    graphify_no_incremental_cache=True,
    chunk_size=1,
    token_budget=None,
    max_concurrency=1,
    max_retry_depth=0,
    deep_mode=False,
)


def accepted_graphify_runtime() -> RuntimeIdentity:
    """Return the reviewed Graphify 0.9.42 runtime identity from issue #300."""
    return _ACCEPTED_GRAPHIFY_RUNTIME


def encode_json(value: object) -> bytes:
    """Encode one public evidence object canonically enough for hashing."""
    return msgspec.json.encode(value, order="sorted")


def _is_sha256(value: str) -> bool:
    return re.fullmatch(r"[0-9a-f]{64}", value) is not None


def sha256_file(path: Path) -> str:
    """Hash one file without retaining its full contents in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def claude_child_environment(
    environment: Mapping[str, str], *, original_path: str | None = None
) -> dict[str, str]:
    """Build the fixed OAuth-compatible environment used for auth and inference."""
    child = {
        name: environment[name]
        for name in _CHILD_BASE_ENV_NAMES
        if environment.get(name) is not None
    }
    child["PATH"] = original_path if original_path is not None else environment.get("PATH", "")
    child.update(_CHILD_CONTROL_ENV)
    return child


def route_override_names(environment: Mapping[str, str]) -> tuple[str, ...]:
    """Return only forbidden routing variable names; never inspect their values."""
    return tuple(sorted(name for name in environment if name in _ROUTE_OVERRIDE_NAMES))


def classify_auth(raw: bytes) -> AuthIdentity:
    """Reduce `claude auth status` JSON to the accepted non-sensitive fields."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Claude auth status is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise TypeError("Claude auth status is not an object")
    identity = AuthIdentity(
        logged_in=payload.get("loggedIn") is True,
        auth_method=str(payload.get("authMethod", "")),
        api_provider=str(payload.get("apiProvider", "")),
        subscription_type=str(payload.get("subscriptionType", "")),
    )
    if (
        not identity.logged_in
        or identity.auth_method != "claude.ai"
        or identity.api_provider != _CLAUDE_PROVIDER
        or identity.subscription_type != "max"
    ):
        raise ValueError("Claude auth is not claude.ai first-party Max")
    return identity


def _completed_bytes(executable: Path, *args: str, environment: Mapping[str, str]) -> bytes:
    completed = subprocess.run(
        [str(executable), *args],
        capture_output=True,
        check=False,
        env=dict(environment),
        timeout=30,
    )
    if completed.returncode != 0 or completed.stderr:
        raise ValueError(f"Claude {' '.join(args)} preflight failed")
    return completed.stdout


def _assert_value_flag_supported(
    executable: Path,
    flag: str,
    *,
    environment: Mapping[str, str],
) -> None:
    """Prove a hidden value-taking CLI flag at parser time without inference."""
    invalid_value = "not-an-integer"
    completed = subprocess.run(
        [str(executable), "-p", flag, invalid_value],
        capture_output=True,
        check=False,
        env=dict(environment),
        timeout=30,
    )
    diagnostic = completed.stderr
    if (
        completed.returncode != 1
        or completed.stdout
        or flag.encode() not in diagnostic
        or invalid_value.encode() not in diagnostic
        or b"is invalid" not in diagnostic
        or b"must be a number" not in diagnostic
    ):
        raise ValueError(f"Claude {flag} parser probe failed")


def preflight(
    repo_root: Path,
    environment: Mapping[str, str] | None = None,
    *,
    graphify_version: str = "0.9.42",
    require_max_turns: bool = False,
) -> ClaudePreflight:
    """Prove exact Graphify/Claude/auth/routing capability without inference."""
    from kb_setup import graphify_baseline, graphify_env, graphify_sdk

    current = dict(os.environ if environment is None else environment)
    overrides = route_override_names(current)
    if overrides:
        raise ValueError("forbidden routing environment names: " + ", ".join(overrides))
    graphify_env.assert_pinned_graphify(repo_root)
    graphify_sdk.assert_semantic_sdk(graphify_version)
    resolved = shutil.which("claude", path=current.get("PATH"))
    if not resolved:
        raise ValueError("Claude Code CLI is unavailable")
    executable = Path(resolved).resolve()
    child = claude_child_environment(current)
    help_raw = _completed_bytes(executable, "--help", environment=child)
    help_text = help_raw.decode("utf-8", errors="strict")
    missing = tuple(flag for flag in _REQUIRED_CLAUDE_FLAGS if flag not in help_text)
    if missing:
        raise ValueError("Claude Code required flags are unavailable: " + ", ".join(missing))
    required_flags = _REQUIRED_CLAUDE_FLAGS
    if require_max_turns:
        _assert_value_flag_supported(executable, "--max-turns", environment=child)
        required_flags = (*required_flags, "--max-turns")
    version_raw = _completed_bytes(executable, "--version", environment=child)
    version_text = version_raw.decode("utf-8", errors="strict").strip()
    match = re.search(r"\b\d+\.\d+\.\d+\b", version_text)
    if match is None:
        raise ValueError("Claude Code version is unparsable")
    auth_raw = _completed_bytes(executable, "auth", "status", environment=child)
    fingerprint = encode_json(graphify_sdk.semantic_api_fingerprint())
    return ClaudePreflight(
        executable="claude",
        executable_sha256=sha256_file(executable),
        version=match.group(0),
        help_sha256=hashlib.sha256(help_raw).hexdigest(),
        required_flags=required_flags,
        auth=classify_auth(auth_raw),
        environment_names=tuple(sorted(child)),
        graphify_runtime=graphify_baseline.runtime_identity(repo_root),
        graphify_version=graphify_sdk.running_sdk_version(),
        graphify_semantic_fingerprint_sha256=hashlib.sha256(fingerprint).hexdigest(),
    )


def _list_is_empty(value: object) -> bool:
    return isinstance(value, list) and not value


def _result_reasons(
    envelope: dict[str, object],
    *,
    max_turns: int | None = _MAX_TURNS_WITH_ONE_STRUCTURED_REPAIR,
) -> list[str]:
    reasons = []
    checks = (
        (envelope.get("type") == "result", "result-type-invalid"),
        (envelope.get("subtype") == "success", "result-subtype-invalid"),
        (envelope.get("is_error") is False, "result-error"),
        (envelope.get("terminal_reason") == "completed", "terminal-state-invalid"),
        (envelope.get("stop_reason") in {"end_turn", "tool_use"}, "stop-reason-invalid"),
    )
    reasons.extend(reason for accepted, reason in checks if not accepted)
    turns = envelope.get("num_turns")
    if (
        isinstance(turns, bool)
        or not isinstance(turns, int)
        or turns < 1
        or (max_turns is not None and turns > max_turns)
    ):
        reasons.append("turn-bound-exceeded")
    return reasons


def _structured_reasons(envelope: dict[str, object]) -> list[str]:
    structured = envelope.get("structured_output")
    if not isinstance(structured, dict):
        return ["structured-output-missing"]
    if not isinstance(structured.get("nodes"), list) or not isinstance(
        structured.get("edges"), list
    ):
        return ["structured-output-invalid"]
    return []


def _model_reasons(envelope: dict[str, object]) -> list[str]:
    model_usage = envelope.get("modelUsage")
    if not isinstance(model_usage, dict) or tuple(model_usage) != (_CLAUDE_MODEL,):
        return ["model-identity-invalid"]
    model = model_usage[_CLAUDE_MODEL]
    if not isinstance(model, dict) or (model.get("canonicalModel"), model.get("provider")) != (
        _CLAUDE_CANONICAL_MODEL,
        _CLAUDE_PROVIDER,
    ):
        return ["model-identity-invalid"]
    return []


def _negative_evidence_reasons(envelope: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    if not _list_is_empty(envelope.get("permission_denials")):
        reasons.append("permission-denial-present")
    errors = envelope.get("errors")
    if errors is not None and not _list_is_empty(errors):
        reasons.append("error-present")
    for key, reason in (
        ("warnings", "warning-present"),
        ("fallback_models", "fallback-model-present"),
        ("routing_overrides", "routing-override-present"),
        ("external_tools", "external-tool-present"),
    ):
        if envelope.get(key, []) not in (None, [], {}):
            reasons.append(reason)
    return reasons


def envelope_reasons(
    envelope: object,
    *,
    max_turns: int | None = _MAX_TURNS_WITH_ONE_STRUCTURED_REPAIR,
) -> tuple[str, ...]:
    """Explain why a redacted real Claude result envelope cannot be accepted."""
    if not isinstance(envelope, dict):
        return ("result-envelope-invalid",)
    reasons = [
        *_result_reasons(envelope, max_turns=max_turns),
        *_structured_reasons(envelope),
        *_model_reasons(envelope),
        *_negative_evidence_reasons(envelope),
    ]
    return tuple(dict.fromkeys(reasons))


def _records(value: object) -> list[dict[str, object]] | None:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        return None
    return value


def _hyperedge_invalid(hyperedges: list[dict[str, object]], known_ids: set[str]) -> bool:
    for hyperedge in hyperedges:
        member_ids = hyperedge.get("nodes")
        if (
            not isinstance(member_ids, list)
            or not member_ids
            or any(not isinstance(node_id, str) or not node_id for node_id in member_ids)
            or any(node_id not in known_ids for node_id in member_ids)
        ):
            return True
    return False


def _fragment_source_reasons(
    records: list[dict[str, object]], source_paths: tuple[str, ...]
) -> list[str]:
    accepted_paths = set(source_paths)
    raw_observed_paths = [item.get("source_file") for item in records]
    observed_paths = {path for path in raw_observed_paths if isinstance(path, str) and path}
    invalid_scope = (
        not source_paths
        or len(accepted_paths) != len(source_paths)
        or any(not isinstance(path, str) or not path for path in source_paths)
        or any(not isinstance(path, str) or not path for path in raw_observed_paths)
        or not observed_paths.issubset(accepted_paths)
    )
    reasons = ["fragment-source-scope-mismatch"] if invalid_scope else []
    if observed_paths != accepted_paths:
        reasons.append("fragment-source-coverage-mismatch")
    return reasons


def fragment_scope_reasons(fragment: object, *, source_paths: tuple[str, ...]) -> tuple[str, ...]:
    """Validate structure, provenance, scope, and references for semantic records."""
    if not isinstance(fragment, dict):
        return ("fragment-invalid",)
    nodes = _records(fragment.get("nodes"))
    edges = _records(fragment.get("edges"))
    hyperedges = _records(fragment.get("hyperedges", []))
    if nodes is None or edges is None or hyperedges is None:
        return ("fragment-schema-invalid",)
    reasons: list[str] = []
    node_ids = [node.get("id") for node in nodes]
    if not nodes:
        reasons.append("zero-semantic-nodes")
    if any(not isinstance(node_id, str) or not node_id for node_id in node_ids):
        reasons.append("semantic-node-identity-invalid")
    valid_node_ids = [node_id for node_id in node_ids if isinstance(node_id, str) and node_id]
    if len(valid_node_ids) != len(set(valid_node_ids)):
        reasons.append("duplicate-semantic-node-identity")
    known_ids = set(valid_node_ids)
    records = [*nodes, *edges, *hyperedges]
    if any(item.get("_origin") not in (None, "semantic") for item in records):
        reasons.append("fragment-origin-invalid")
    reasons.extend(_fragment_source_reasons(records, source_paths))
    if any(
        not isinstance(edge.get("source"), str)
        or not isinstance(edge.get("target"), str)
        or edge.get("source") not in known_ids
        or edge.get("target") not in known_ids
        for edge in edges
    ):
        reasons.append("unresolved-edge-endpoint")
    if _hyperedge_invalid(hyperedges, known_ids):
        reasons.append("unresolved-hyperedge-member")
    return tuple(dict.fromkeys(reasons))


def fragment_reasons(fragment: object, *, source_path: str) -> tuple[str, ...]:
    """Validate one-source fragment structure, provenance, scope, and references."""
    return fragment_scope_reasons(fragment, source_paths=(source_path,))


def expected_source_identity() -> SourceIdentity:
    """Return the reviewed trust root for the single #300 source document."""
    return SourceIdentity(
        source="graphify",
        ref=SOURCE_REF,
        commit=SOURCE_COMMIT,
        tree=SOURCE_TREE,
        path=SOURCE_PATH,
        git_object=SOURCE_GIT_OBJECT,
        sha256=SOURCE_SHA256,
        size=SOURCE_SIZE,
    )


def _candidate_entry_reasons(candidate: Path) -> list[str]:
    try:
        entries = tuple(candidate.iterdir())
    except OSError:
        return ["candidate-unavailable"]
    expected = {*_REQUIRED_MEMBERS, "manifest.json"}
    names = {entry.name for entry in entries}
    reasons = [f"candidate-entry-mismatch:{name}" for name in sorted(names ^ expected)]
    for entry in entries:
        try:
            mode = entry.lstat().st_mode
        except OSError:
            reasons.append(f"candidate-entry-unreadable:{entry.name}")
            continue
        if not stat.S_ISREG(mode):
            reasons.append(f"candidate-entry-not-regular:{entry.name}")
    return reasons


def _manifest_reasons(manifest: CandidateManifest) -> list[str]:
    names = tuple(member.name for member in manifest.members)
    reasons: list[str] = []
    if manifest.schema_id != _CANDIDATE_SCHEMA:
        reasons.append("manifest-schema-mismatch")
    if manifest.source != expected_source_identity():
        reasons.append("manifest-source-identity-mismatch")
    if names != tuple(sorted(_REQUIRED_MEMBERS)):
        reasons.append("manifest-member-set-mismatch")
    if len(names) != len(set(names)):
        reasons.append("manifest-member-duplicate")
    if manifest.warnings:
        reasons.append("manifest-warning-bearing")
    return reasons


def _member_reasons(
    candidate: Path, manifest: CandidateManifest
) -> tuple[list[str], dict[str, bytes]]:
    reasons: list[str] = []
    payloads: dict[str, bytes] = {}
    for member in manifest.members:
        path = candidate / member.name
        try:
            raw = path.read_bytes()
        except OSError:
            reasons.append(f"member-unavailable:{member.name}")
            continue
        payloads[member.name] = raw
        if len(raw) != member.size:
            reasons.append(f"member-size-mismatch:{member.name}")
        if hashlib.sha256(raw).hexdigest() != member.sha256:
            reasons.append(f"member-digest-mismatch:{member.name}")
    return reasons, payloads


def _adapter_reasons(metadata: object, receipt: SemanticReceipt, fragment: object) -> list[str]:
    from kb_setup.graphify_semantic_adapter import AdapterMetadata, parse_observation_reasons

    if not isinstance(metadata, AdapterMetadata):
        return ["adapter-metadata-schema-mismatch"]
    reasons: list[str] = []
    expected_auth = AuthIdentity(
        logged_in=True,
        auth_method="claude.ai",
        api_provider=_CLAUDE_PROVIDER,
        subscription_type="max",
    )
    checks = (
        (metadata.schema_id == "graphify-claude-boundary/v0", "adapter-schema-mismatch"),
        (metadata.status == "complete", "adapter-incomplete"),
        (metadata.claude_executable == "claude", "adapter-executable-name-mismatch"),
        (
            metadata.claude_version == f"{receipt.runtime.version} (Claude Code)",
            "adapter-version-mismatch",
        ),
        (metadata.auth == expected_auth, "adapter-auth-mismatch"),
        (metadata.returncode == 0, "adapter-returncode-nonzero"),
        (metadata.stderr_size == 0, "adapter-stderr-present"),
        (
            metadata.stderr_sha256 == hashlib.sha256(b"").hexdigest(),
            "adapter-stderr-digest-mismatch",
        ),
        (metadata.reasons == (), "adapter-rejected-result"),
        (metadata.attempt == 1, "adapter-attempt-mismatch"),
        (metadata.permission_denial_count == 0, "adapter-permission-denial-present"),
        (metadata.result_type == "result", "adapter-result-type-mismatch"),
        (metadata.result_subtype == "success", "adapter-result-subtype-mismatch"),
        (not metadata.is_error, "adapter-result-error"),
        (metadata.terminal_reason == "completed", "adapter-terminal-state-mismatch"),
        (metadata.stop_reason in {"end_turn", "tool_use"}, "adapter-stop-reason-mismatch"),
        (1 <= metadata.num_turns <= _MAX_TURNS_WITH_ONE_STRUCTURED_REPAIR, "adapter-turn-bound"),
        (
            _is_sha256(metadata.structured_output_sha256),
            "adapter-structured-output-digest-invalid",
        ),
        (
            metadata.structured_output_sha256 == hashlib.sha256(encode_json(fragment)).hexdigest(),
            "adapter-structured-output-digest-mismatch",
        ),
        (metadata.prompt_size > 0, "adapter-prompt-empty"),
        (_is_sha256(metadata.prompt_sha256), "adapter-prompt-digest-invalid"),
        (metadata.response_size > 0, "adapter-response-empty"),
        (_is_sha256(metadata.response_sha256), "adapter-response-digest-invalid"),
        (metadata.input_tokens > 0, "adapter-input-token-count-invalid"),
        (metadata.output_tokens > 0, "adapter-output-token-count-invalid"),
        (0.0 <= metadata.total_cost_usd <= _MAX_COST_USD, "adapter-cost-invalid"),
        (
            0
            < metadata.duration_api_ms
            <= metadata.duration_ms
            <= metadata.elapsed_ms
            <= _ACCEPTED_EXECUTION_CONFIG.api_timeout_ms,
            "adapter-duration-invalid",
        ),
        (metadata.environment_names == receipt.runtime.environment_names, "adapter-env-mismatch"),
        (
            metadata.claude_executable_sha256 == receipt.runtime.executable_sha256,
            "adapter-executable-mismatch",
        ),
    )
    reasons.extend(reason for accepted, reason in checks if not accepted)
    if metadata.parse_observation is not None:
        reasons.extend(
            f"adapter-{reason}"
            for reason in parse_observation_reasons(
                metadata.parse_observation,
                digest=metadata.parse_observation_sha256,
                response_sha256=metadata.response_sha256,
                response_size=metadata.response_size,
            )
        )
        if metadata.parse_observation.status not in {
            "accepted-object",
            "accepted-result-array",
        }:
            reasons.append("adapter-response-untyped")
    if len(metadata.model_usage) != 1:
        reasons.append("adapter-model-count-mismatch")
    else:
        model = metadata.model_usage[0]
        if (model.model, model.canonical_model, model.provider) != (
            _CLAUDE_MODEL,
            _CLAUDE_CANONICAL_MODEL,
            _CLAUDE_PROVIDER,
        ):
            reasons.append("adapter-model-identity-mismatch")
        if (
            min(
                model.input_tokens,
                model.output_tokens,
                model.cache_read_input_tokens,
                model.cache_creation_input_tokens,
            )
            < 0
        ):
            reasons.append("adapter-model-token-count-invalid")
        if (metadata.input_tokens, metadata.output_tokens) != (
            model.input_tokens,
            model.output_tokens,
        ):
            reasons.append("adapter-token-count-mismatch")
    argv = metadata.argv
    schema = argv[7] if len(argv) == _RETAINED_CLAUDE_ARG_COUNT else ""
    expected_argv = (
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--model",
        _CLAUDE_MODEL,
        "--json-schema",
        schema,
        "--safe-mode",
        "--tools",
        "",
        "--strict-mcp-config",
        "--permission-mode",
        "dontAsk",
        "--no-chrome",
        "--max-budget-usd",
        "0.25",
    )
    if argv != expected_argv:
        reasons.append("adapter-argv-shape-mismatch")
    if hashlib.sha256(schema.encode()).hexdigest() != GRAPHIFY_SCHEMA_SHA256:
        reasons.append("adapter-schema-digest-mismatch")
    return reasons


def _runtime_reasons(runtime: ClaudePreflight) -> list[str]:
    names = set(runtime.environment_names)
    allowed = {*_CHILD_BASE_ENV_NAMES, *_CHILD_CONTROL_ENV}
    required = {*_CHILD_CONTROL_ENV, "PATH"}
    checks = (
        (runtime.executable == "claude", "receipt-claude-executable-name-mismatch"),
        (runtime.version == _ACCEPTED_CLAUDE_VERSION, "receipt-claude-version-mismatch"),
        (
            runtime.executable_sha256 == _ACCEPTED_CLAUDE_EXECUTABLE_SHA256,
            "receipt-claude-executable-digest-mismatch",
        ),
        (runtime.help_sha256 == _ACCEPTED_CLAUDE_HELP_SHA256, "receipt-claude-help-mismatch"),
        (runtime.required_flags == _REQUIRED_CLAUDE_FLAGS, "receipt-cli-flags-mismatch"),
        (runtime.graphify_runtime == _ACCEPTED_GRAPHIFY_RUNTIME, "receipt-runtime-mismatch"),
        (runtime.graphify_version == "0.9.42", "receipt-graphify-version-mismatch"),
        (
            runtime.graphify_semantic_fingerprint_sha256 == _ACCEPTED_SEMANTIC_FINGERPRINT_SHA256,
            "receipt-semantic-fingerprint-mismatch",
        ),
        (names <= allowed, "receipt-runtime-env-name-invalid"),
        (required <= names, "receipt-runtime-control-missing"),
    )
    return [reason for accepted, reason in checks if not accepted]


def _chunk_reasons(receipt: SemanticReceipt, metadata: object, fragment: object) -> list[str]:
    from kb_setup.graphify_semantic_adapter import AdapterMetadata

    if not isinstance(metadata, AdapterMetadata) or not isinstance(fragment, dict):
        return ["chunk-evidence-unavailable"]
    counts = _fragment_counts(fragment)
    expected = ChunkEvidence(
        ordinal=1,
        total=1,
        source_path=SOURCE_PATH,
        source_git_object=SOURCE_GIT_OBJECT,
        source_sha256=SOURCE_SHA256,
        source_size=SOURCE_SIZE,
        prompt_sha256=metadata.prompt_sha256,
        fragment_sha256=metadata.structured_output_sha256,
        node_count=counts[0],
        edge_count=counts[1],
        hyperedge_count=counts[2],
    )
    return [] if receipt.chunks == (expected,) else ["chunk-ledger-mismatch"]


def _receipt_reasons(
    receipt: SemanticReceipt,
    manifest: CandidateManifest,
    metadata_raw: bytes,
    fragment_raw: bytes,
    fragment: object,
) -> list[str]:
    reasons: list[str] = []
    checks = (
        (receipt.schema_id == _CANDIDATE_SCHEMA, "receipt-schema-mismatch"),
        (receipt.status == "complete", "receipt-incomplete"),
        (receipt.source == expected_source_identity(), "receipt-source-identity-mismatch"),
        (receipt.source == manifest.source, "receipt-manifest-source-mismatch"),
        (
            receipt.runtime.auth
            == AuthIdentity(
                logged_in=True,
                auth_method="claude.ai",
                api_provider=_CLAUDE_PROVIDER,
                subscription_type="max",
            ),
            "receipt-auth-mismatch",
        ),
        (receipt.attempts == 1, "receipt-attempt-mismatch"),
        (receipt.backend == "claude-cli", "receipt-backend-mismatch"),
        (receipt.model == _CLAUDE_MODEL, "receipt-model-mismatch"),
        (receipt.max_concurrency == 1, "receipt-concurrency-mismatch"),
        (receipt.max_retry_depth == 0, "receipt-retry-depth-mismatch"),
        (
            receipt.execution_config == _ACCEPTED_EXECUTION_CONFIG,
            "receipt-execution-config-mismatch",
        ),
        (receipt.failed_chunks == 0, "receipt-failed-chunks"),
        (receipt.uncovered_files == (), "receipt-uncovered-files"),
        (receipt.out_of_scope_dropped == 0, "receipt-out-of-scope-dropped"),
        (receipt.warnings == (), "receipt-warning-bearing"),
        (receipt.errors == (), "receipt-error-bearing"),
        (
            receipt.adapter_metadata_sha256 == hashlib.sha256(metadata_raw).hexdigest(),
            "receipt-adapter-digest-mismatch",
        ),
        (
            receipt.semantic_fragment_sha256 == hashlib.sha256(fragment_raw).hexdigest(),
            "receipt-fragment-digest-mismatch",
        ),
    )
    reasons.extend(reason for accepted, reason in checks if not accepted)
    reasons.extend(_runtime_reasons(receipt.runtime))
    if isinstance(fragment, dict):
        counts = (
            len(fragment.get("nodes", [])),
            len(fragment.get("edges", [])),
            len(fragment.get("hyperedges", [])),
        )
        if counts != (
            receipt.semantic_node_count,
            receipt.semantic_edge_count,
            receipt.semantic_hyperedge_count,
        ):
            reasons.append("receipt-semantic-count-mismatch")
    if receipt.graph_node_count < receipt.semantic_node_count:
        reasons.append("receipt-graph-node-count-invalid")
    if receipt.graph_edge_count < receipt.semantic_edge_count:
        reasons.append("receipt-graph-edge-count-invalid")
    return reasons


def _verify_candidate(candidate: Path, *, enforce_authority: bool) -> SemanticVerification:
    reasons = _candidate_entry_reasons(candidate)
    if reasons:
        return SemanticVerification(
            state="failed",
            structural_complete=False,
            real_semantic_complete=False,
            reasons=tuple(reasons),
        )
    try:
        manifest_raw = (candidate / "manifest.json").read_bytes()
        manifest = msgspec.json.decode(manifest_raw, type=CandidateManifest, strict=True)
    except OSError, msgspec.DecodeError:
        return SemanticVerification(
            state="failed",
            structural_complete=False,
            real_semantic_complete=False,
            reasons=("manifest-corrupt",),
        )
    if not isinstance(manifest, CandidateManifest):
        return SemanticVerification(
            state="failed",
            structural_complete=False,
            real_semantic_complete=False,
            reasons=("manifest-schema-mismatch",),
        )
    reasons.extend(_manifest_reasons(manifest))
    if (
        enforce_authority
        and hashlib.sha256(manifest_raw).hexdigest() != _ACCEPTED_CANDIDATE_MANIFEST_SHA256
    ):
        reasons.append("candidate-authority-mismatch")
    if reasons:
        return SemanticVerification(
            state="failed",
            structural_complete=False,
            real_semantic_complete=False,
            reasons=tuple(dict.fromkeys(reasons)),
        )
    member_reasons, payloads = _member_reasons(candidate, manifest)
    reasons.extend(member_reasons)
    if reasons:
        return SemanticVerification(
            state="failed",
            structural_complete=False,
            real_semantic_complete=False,
            reasons=tuple(dict.fromkeys(reasons)),
        )
    try:
        receipt = msgspec.json.decode(payloads["receipt.json"], type=SemanticReceipt, strict=True)
        from kb_setup.graphify_semantic_adapter import AdapterMetadata

        metadata = msgspec.json.decode(
            payloads["adapter-metadata.json"], type=AdapterMetadata, strict=True
        )
        fragment = msgspec.json.decode(payloads["semantic-fragment.json"], strict=True)
    except KeyError, msgspec.DecodeError:
        reasons.append("member-schema-mismatch")
    else:
        fragment_failures = fragment_reasons(fragment, source_path=SOURCE_PATH)
        reasons.extend(fragment_failures)
        if not fragment_failures:
            reasons.extend(_adapter_reasons(metadata, receipt, fragment))
            reasons.extend(_chunk_reasons(receipt, metadata, fragment))
            reasons.extend(
                _receipt_reasons(
                    receipt,
                    manifest,
                    payloads["adapter-metadata.json"],
                    payloads["semantic-fragment.json"],
                    fragment,
                )
            )
    unique = tuple(dict.fromkeys(reasons))
    return SemanticVerification(
        state="failed" if unique else ("complete" if enforce_authority else "unapproved"),
        structural_complete=not unique,
        real_semantic_complete=enforce_authority and not unique,
        reasons=unique,
    )


def verify_candidate(candidate: Path) -> SemanticVerification:
    """Independently verify a candidate against the reviewed real-run authority."""
    return _verify_candidate(candidate, enforce_authority=True)


@contextmanager
def _temporary_environment(updates: Mapping[str, str]) -> Generator[None]:
    prior = {name: os.environ.get(name) for name in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for name, value in prior.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _write_json(path: Path, value: object) -> bytes:
    raw = encode_json(value) + b"\n"
    path.write_bytes(raw)
    return raw


def _admit_source(repo_root: Path, destination: Path) -> tuple[Path, object]:
    from kb_setup import graph, graphify_baseline
    from kb_setup import manifest as source_manifests

    source_manifest = source_manifests.load(repo_root / "sources/graphify.manifest")
    provenance = graph.materialize_source_snapshot(source_manifest, destination)
    if (source_manifest.ref, provenance.resolved_commit, provenance.tree_digest) != (
        SOURCE_REF,
        SOURCE_COMMIT,
        SOURCE_TREE,
    ):
        raise ValueError("Graphify semantic source identity drifted")
    inventory = graphify_baseline.source_manifest(
        destination,
        commit=SOURCE_COMMIT,
        tree=SOURCE_TREE,
    )
    matches = tuple(member for member in inventory.members if member.path == SOURCE_PATH)
    if len(matches) != 1:
        raise ValueError("Graphify semantic source member is unavailable")
    member = matches[0]
    if (member.git_object, member.sha256, member.size) != (
        SOURCE_GIT_OBJECT,
        SOURCE_SHA256,
        SOURCE_SIZE,
    ):
        raise ValueError("Graphify semantic source bytes drifted")
    return destination / SOURCE_PATH, inventory


def admit_source(repo_root: Path, destination: Path) -> tuple[Path, object]:
    """Materialize and verify the complete pinned Graphify source snapshot."""
    return _admit_source(repo_root, destination)


def _semantic_fragment(result: object) -> dict[str, object]:
    if not isinstance(result, dict):
        raise TypeError("Graphify semantic result is not an object")
    fragment: dict[str, object] = {}
    for field in ("nodes", "edges", "hyperedges"):
        records = _records(result.get(field, []))
        if records is None:
            raise TypeError(f"Graphify semantic {field} are invalid")
        exact: list[dict[str, object]] = []
        for record in records:
            if record.get("_origin") not in (None, "semantic"):
                raise ValueError(f"Graphify semantic {field} origin drifted")
            exact.append(record)
        fragment[field] = exact
    reasons = fragment_reasons(fragment, source_path=SOURCE_PATH)
    if reasons:
        raise ValueError("Graphify semantic fragment failed: " + ", ".join(reasons))
    return fragment


def _fragment_counts(fragment: Mapping[str, object]) -> tuple[int, int, int]:
    counts: list[int] = []
    for field in ("nodes", "edges", "hyperedges"):
        records = _records(fragment.get(field))
        if records is None:
            raise TypeError(f"Graphify semantic {field} are invalid")
        counts.append(len(records))
    return counts[0], counts[1], counts[2]


def _adapter_environment(
    *, preflight_receipt: ClaudePreflight, metadata_path: Path, adapter_dir: Path
) -> dict[str, str]:
    original_path = os.environ.get("PATH", "")
    entrypoint = shutil.which("kb-semantic-claude", path=original_path)
    if entrypoint is None:
        raise ValueError("KB semantic Claude adapter entrypoint is unavailable")
    real_claude = shutil.which("claude", path=original_path)
    if real_claude is None:
        raise ValueError("Claude Code CLI is unavailable")
    real_path = Path(real_claude).resolve()
    if sha256_file(real_path) != preflight_receipt.executable_sha256:
        raise ValueError("Claude Code executable changed after preflight")
    (adapter_dir / "claude").symlink_to(Path(entrypoint).resolve())
    return {
        "PATH": f"{adapter_dir}{os.pathsep}{original_path}",
        "KB_SEMANTIC_REAL_CLAUDE": str(real_path),
        "KB_SEMANTIC_REAL_CLAUDE_SHA256": preflight_receipt.executable_sha256,
        "KB_SEMANTIC_ORIGINAL_PATH": original_path,
        "KB_SEMANTIC_METADATA_PATH": str(metadata_path),
        "GRAPHIFY_CLAUDE_CLI_MODEL": _CLAUDE_MODEL,
        "GRAPHIFY_API_TIMEOUT": "120",
        "GRAPHIFY_NO_INCREMENTAL_CACHE": "1",
    }


def _extract_real_semantic(
    source: Path,
    *,
    root: Path,
    cache_root: Path,
    environment: Mapping[str, str],
) -> tuple[
    dict[str, object],
    tuple[str, ...],
    tuple[tuple[int, int, str, tuple[int, int, int]], ...],
]:
    from kb_setup import graphify_sdk

    stream = io.StringIO()
    observed_chunks: list[tuple[int, int, str, tuple[int, int, int]]] = []

    def observe_chunk(index: int, total: int, raw: object) -> None:
        fragment = _semantic_fragment(raw)
        observed_chunks.append(
            (
                index + 1,
                total,
                hashlib.sha256(encode_json(fragment)).hexdigest(),
                _fragment_counts(fragment),
            )
        )

    with (
        _temporary_environment(environment),
        warnings.catch_warnings(record=True) as caught,
        redirect_stderr(stream),
    ):
        warnings.simplefilter("always")
        result = graphify_sdk.extract_corpus_parallel(
            [source],
            backend="claude-cli",
            model=_CLAUDE_MODEL,
            root=root,
            chunk_size=1,
            token_budget=None,
            max_concurrency=1,
            max_retry_depth=0,
            on_chunk_done=observe_chunk,
            deep_mode=False,
            cache_root=cache_root,
        )
    warning_text = tuple(
        item
        for item in (stream.getvalue().strip(), *(str(warning.message) for warning in caught))
        if item
    )
    return result, warning_text, tuple(observed_chunks)


def _result_integer(result: Mapping[str, object], name: str) -> int:
    value = result.get(name)
    return value if isinstance(value, int) and not isinstance(value, bool) else -1


def _coverage_evidence(result: Mapping[str, object]) -> tuple[int, tuple[str, ...], int]:
    failed_chunks = _result_integer(result, "failed_chunks")
    dropped = _result_integer(result, "out_of_scope_dropped")
    uncovered_value = result.get("uncovered_files")
    if not isinstance(uncovered_value, list) or not all(
        isinstance(item, str) for item in uncovered_value
    ):
        raise ValueError("Graphify semantic uncovered-file evidence is invalid")
    uncovered = tuple(uncovered_value)
    if failed_chunks != 0 or uncovered or dropped != 0:
        raise ValueError("Graphify semantic extraction was partial")
    if result.get("_partial_files") not in (None, []):
        raise ValueError("Graphify semantic extraction reported partial files")
    return failed_chunks, uncovered, dropped


def build_candidate(repo_root: Path, output: Path) -> CandidateManifest:
    """Run exactly one real semantic call and atomically publish verified evidence."""
    from kb_setup import graphify_baseline, graphify_sdk
    from kb_setup.graphify_semantic_adapter import AdapterMetadata

    if output.exists():
        raise ValueError(f"semantic output already exists: {output}")
    preflight_receipt = preflight(repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kb-graphify-semantic-source-") as source_dir:
        source_root = Path(source_dir) / "graphify"
        source_path, before = _admit_source(repo_root, source_root)
        with (
            tempfile.TemporaryDirectory(prefix="kb-graphify-semantic-cache-") as cache_dir,
            tempfile.TemporaryDirectory(prefix="kb-graphify-semantic-adapter-") as bin_dir,
            tempfile.TemporaryDirectory(
                prefix=f".{output.name}-", dir=output.parent
            ) as candidate_dir,
        ):
            candidate = Path(candidate_dir)
            metadata_path = candidate / "adapter-metadata.json"
            environment = _adapter_environment(
                preflight_receipt=preflight_receipt,
                metadata_path=metadata_path,
                adapter_dir=Path(bin_dir),
            )
            result, warning_text, observed_chunks = _extract_real_semantic(
                source_path,
                root=source_root,
                cache_root=Path(cache_dir),
                environment=environment,
            )
            after = graphify_baseline.source_manifest(
                source_root,
                commit=SOURCE_COMMIT,
                tree=SOURCE_TREE,
            )
            if after != before:
                raise ValueError("source-snapshot-drift: semantic input changed")
            if warning_text:
                raise ValueError("Graphify semantic warnings: " + "; ".join(warning_text))
            failed_chunks, uncovered, dropped = _coverage_evidence(result)
            fragment = _semantic_fragment(result)
            built_graph, build_receipt = graphify_sdk.build_checked([fragment], root=source_root)
            if build_receipt.stderr or build_receipt.reasons:
                raise ValueError("Graphify semantic build was warning-bearing")
            try:
                metadata_raw = metadata_path.read_bytes()
                metadata = msgspec.json.decode(metadata_raw, type=AdapterMetadata, strict=True)
            except (OSError, msgspec.DecodeError) as exc:
                raise ValueError("semantic adapter metadata is unavailable") from exc
            fragment_raw = _write_json(candidate / "semantic-fragment.json", fragment)
            counts = _fragment_counts(fragment)
            expected_observed = (
                (
                    1,
                    1,
                    metadata.structured_output_sha256,
                    counts,
                ),
            )
            if observed_chunks != expected_observed:
                raise ValueError("Graphify semantic chunk callback evidence drifted")
            chunks = (
                ChunkEvidence(
                    ordinal=1,
                    total=1,
                    source_path=SOURCE_PATH,
                    source_git_object=SOURCE_GIT_OBJECT,
                    source_sha256=SOURCE_SHA256,
                    source_size=SOURCE_SIZE,
                    prompt_sha256=metadata.prompt_sha256,
                    fragment_sha256=metadata.structured_output_sha256,
                    node_count=counts[0],
                    edge_count=counts[1],
                    hyperedge_count=counts[2],
                ),
            )
            receipt = SemanticReceipt(
                schema_id=_CANDIDATE_SCHEMA,
                status="complete",
                source=expected_source_identity(),
                runtime=preflight_receipt,
                adapter_metadata_sha256=hashlib.sha256(metadata_raw).hexdigest(),
                semantic_fragment_sha256=hashlib.sha256(fragment_raw).hexdigest(),
                chunks=chunks,
                execution_config=_ACCEPTED_EXECUTION_CONFIG,
                attempts=metadata.attempt,
                backend="claude-cli",
                model=_CLAUDE_MODEL,
                max_concurrency=1,
                max_retry_depth=0,
                failed_chunks=failed_chunks,
                uncovered_files=uncovered,
                out_of_scope_dropped=dropped,
                semantic_node_count=counts[0],
                semantic_edge_count=counts[1],
                semantic_hyperedge_count=counts[2],
                graph_node_count=int(built_graph.number_of_nodes()),
                graph_edge_count=int(built_graph.number_of_edges()),
                warnings=(),
                errors=(),
            )
            _write_json(candidate / "receipt.json", receipt)
            members = tuple(
                ArtifactMember(
                    name=name,
                    sha256=sha256_file(candidate / name),
                    size=(candidate / name).stat().st_size,
                )
                for name in sorted(_REQUIRED_MEMBERS)
            )
            manifest = CandidateManifest(
                schema_id=_CANDIDATE_SCHEMA,
                source=expected_source_identity(),
                members=members,
                warnings=(),
            )
            _write_json(candidate / "manifest.json", manifest)
            verification = _verify_candidate(candidate, enforce_authority=False)
            if not verification.structural_complete:
                raise ValueError(
                    "semantic candidate structural verification failed: "
                    + ", ".join(verification.reasons)
                )
            candidate.replace(output)
            return manifest


def semantic_main(repo_root: Path, args: list[str]) -> int:
    """Preflight, build, or independently verify the #300 semantic slice."""
    if not args or args[0] not in {"preflight", "run", "verify"} or len(args) > _MAX_SEMANTIC_ARGS:
        print("kb-setup graphify-semantic-slice preflight|run|verify [PATH]")
        return 2
    command = args[0]
    if command == "preflight":
        if len(args) != 1:
            print("kb-setup graphify-semantic-slice preflight")
            return 2
        print(msgspec.json.encode(preflight(repo_root)).decode())
        return 0
    output = (
        Path(args[1])
        if len(args) == _MAX_SEMANTIC_ARGS
        else repo_root / "graphify-out/graphify-semantic-slice"
    )
    result = build_candidate(repo_root, output) if command == "run" else verify_candidate(output)
    print(msgspec.json.encode(result).decode())
    complete = (
        result.real_semantic_complete
        if isinstance(result, SemanticVerification)
        else verify_candidate(output).real_semantic_complete
    )
    return 0 if complete else 1
