# Copyright (c) 2026 Raymond Manaloto
"""Claude Code boundary adapter for Graphify's real ``claude-cli`` route."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import msgspec

from kb_setup import atomic, graphify_semantic_slice

_GRAPHIFY_ARG_COUNT = 8


class ModelUsage(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Allowlisted identity and usage for the sole returned provider model."""

    model: str
    canonical_model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class AdapterMetadata(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Public-safe evidence captured before the raw envelope is discarded."""

    schema_id: str
    status: str
    claude_executable: str
    claude_executable_sha256: str
    claude_version: str
    argv: tuple[str, ...]
    environment_names: tuple[str, ...]
    auth: graphify_semantic_slice.AuthIdentity
    prompt_sha256: str
    prompt_size: int
    response_sha256: str
    response_size: int
    stderr_sha256: str
    stderr_size: int
    returncode: int
    result_type: str
    result_subtype: str
    is_error: bool
    terminal_reason: str
    stop_reason: str
    num_turns: int
    structured_output_sha256: str
    model_usage: tuple[ModelUsage, ...]
    input_tokens: int
    output_tokens: int
    total_cost_usd: float
    duration_ms: int
    duration_api_ms: int
    elapsed_ms: int
    permission_denial_count: int
    reasons: tuple[str, ...]
    attempt: int = 1


class MetadataInputs(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Runtime values needed to derive one public-safe adapter receipt."""

    executable: Path
    version: str
    argv: tuple[str, ...]
    environment: dict[str, str]
    auth: graphify_semantic_slice.AuthIdentity
    prompt: bytes
    stdout: bytes
    stderr: bytes
    returncode: int
    envelope: dict[str, object]
    elapsed_ms: int
    reasons: tuple[str, ...]


class ProviderBoundaryStart(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Durable evidence written immediately before the real provider process starts."""

    schema_id: str
    phase: str
    provider_process_invocations: int
    provider_inferences: str
    adapter_sha256: str
    prompt_sha256: str
    prompt_size: int
    argv_sha256: str


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_provider_boundary_start(
    destination: Path,
    *,
    adapter_sha256: str,
    prompt: bytes,
    argv: tuple[str, ...],
) -> ProviderBoundaryStart:
    """Atomically retain the exact provider-boundary crossing before invocation."""
    try:
        parent_mode = destination.parent.lstat().st_mode
    except OSError as exc:
        raise ValueError("provider boundary marker destination is unavailable") from exc
    if not stat.S_ISDIR(parent_mode) or destination.parent.is_symlink():
        raise ValueError("provider boundary marker destination is unavailable")
    marker = ProviderBoundaryStart(
        schema_id="graphify-claude-provider-boundary-start/v0",
        phase="provider-boundary-started",
        provider_process_invocations=1,
        provider_inferences="unknown",
        adapter_sha256=adapter_sha256,
        prompt_sha256=_sha256(prompt),
        prompt_size=len(prompt),
        argv_sha256=_sha256(graphify_semantic_slice.encode_json(argv)),
    )
    raw = graphify_semantic_slice.encode_json(marker) + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination, flags, 0o600)
    except FileExistsError as exc:
        raise ValueError("provider boundary marker already exists") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return marker


def _real_executable() -> Path:
    raw = os.environ.get("KB_SEMANTIC_REAL_CLAUDE", "")
    expected = os.environ.get("KB_SEMANTIC_REAL_CLAUDE_SHA256", "")
    path = Path(raw).resolve()
    if not path.is_file() or not expected or graphify_semantic_slice.sha256_file(path) != expected:
        raise ValueError("real Claude executable identity drifted")
    return path


def _child_environment() -> dict[str, str]:
    return graphify_semantic_slice.claude_child_environment(
        os.environ,
        original_path=os.environ.get("KB_SEMANTIC_ORIGINAL_PATH", ""),
    )


def _result_envelope(stdout: bytes) -> dict[str, object]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError, UnicodeDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _number(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _usage(envelope: dict[str, object]) -> tuple[ModelUsage, ...]:
    raw_usage = envelope.get("modelUsage")
    if not isinstance(raw_usage, dict):
        return ()
    usages: list[ModelUsage] = []
    for model, raw in raw_usage.items():
        if not isinstance(model, str) or not isinstance(raw, dict):
            continue
        usages.append(
            ModelUsage(
                model=model,
                canonical_model=str(raw.get("canonicalModel", "")),
                provider=str(raw.get("provider", "")),
                input_tokens=_integer(raw.get("inputTokens", raw.get("input_tokens"))),
                output_tokens=_integer(raw.get("outputTokens", raw.get("output_tokens"))),
                cache_read_input_tokens=_integer(
                    raw.get("cacheReadInputTokens", raw.get("cache_read_input_tokens"))
                ),
                cache_creation_input_tokens=_integer(
                    raw.get("cacheCreationInputTokens", raw.get("cache_creation_input_tokens"))
                ),
            )
        )
    return tuple(usages)


def _validate_incoming_args(args: list[str]) -> str:
    if graphify_semantic_slice.route_override_names(os.environ):
        raise ValueError("routing override reached semantic adapter")
    schema = args[7] if len(args) == _GRAPHIFY_ARG_COUNT else ""
    expected = [
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--model",
        graphify_semantic_slice.CLAUDE_MODEL,
        "--json-schema",
        schema,
    ]
    if args != expected:
        raise ValueError("Graphify claude-cli argv drifted")
    if _sha256(schema.encode()) != graphify_semantic_slice.GRAPHIFY_SCHEMA_SHA256:
        raise ValueError("Graphify claude-cli JSON schema digest drifted")
    try:
        parsed_schema = json.loads(schema)
    except json.JSONDecodeError as exc:
        raise ValueError("Graphify claude-cli JSON schema is invalid") from exc
    if not isinstance(parsed_schema, dict) or parsed_schema.get("required") != ["nodes", "edges"]:
        raise ValueError("Graphify claude-cli JSON schema drifted")
    return schema


def _metadata(inputs: MetadataInputs) -> AdapterMetadata:
    envelope = inputs.envelope
    structured = envelope.get("structured_output")
    structured_raw = (
        graphify_semantic_slice.encode_json(structured) if isinstance(structured, dict) else b""
    )
    usage = envelope.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    denials = envelope.get("permission_denials")
    return AdapterMetadata(
        schema_id="graphify-claude-boundary/v0",
        status="complete" if not inputs.reasons else "failed",
        claude_executable="claude",
        claude_executable_sha256=graphify_semantic_slice.sha256_file(inputs.executable),
        claude_version=inputs.version,
        argv=inputs.argv,
        environment_names=tuple(sorted(inputs.environment)),
        auth=inputs.auth,
        prompt_sha256=_sha256(inputs.prompt),
        prompt_size=len(inputs.prompt),
        response_sha256=_sha256(inputs.stdout),
        response_size=len(inputs.stdout),
        stderr_sha256=_sha256(inputs.stderr),
        stderr_size=len(inputs.stderr),
        returncode=inputs.returncode,
        result_type=str(envelope.get("type", "")),
        result_subtype=str(envelope.get("subtype", "")),
        is_error=envelope.get("is_error") is True,
        terminal_reason=str(envelope.get("terminal_reason", "")),
        stop_reason=str(envelope.get("stop_reason", "")),
        num_turns=_integer(envelope.get("num_turns")),
        structured_output_sha256=_sha256(structured_raw) if structured_raw else "",
        model_usage=_usage(envelope),
        input_tokens=_integer(usage.get("input_tokens")),
        output_tokens=_integer(usage.get("output_tokens")),
        total_cost_usd=_number(envelope.get("total_cost_usd")),
        duration_ms=_integer(envelope.get("duration_ms")),
        duration_api_ms=_integer(envelope.get("duration_api_ms")),
        elapsed_ms=inputs.elapsed_ms,
        permission_denial_count=len(denials) if isinstance(denials, list) else -1,
        reasons=inputs.reasons,
    )


def _write_metadata(value: AdapterMetadata) -> None:
    path = Path(os.environ.get("KB_SEMANTIC_METADATA_PATH", ""))
    if not path.parent.is_dir():
        raise ValueError("semantic metadata destination is unavailable")
    atomic.write_text(path, graphify_semantic_slice.encode_json(value).decode() + "\n")


def _delegate_info(executable: Path, args: list[str]) -> int:
    completed = subprocess.run(
        [str(executable), *args],
        check=False,
        env=_child_environment(),
    )
    return completed.returncode


def _runtime_identity(
    executable: Path, environment: dict[str, str]
) -> tuple[graphify_semantic_slice.AuthIdentity, str]:
    auth_proc = subprocess.run(
        [str(executable), "auth", "status"],
        capture_output=True,
        check=False,
        env=environment,
        timeout=30,
    )
    if auth_proc.returncode != 0 or auth_proc.stderr:
        raise ValueError("Claude auth status failed in the sanitized environment")
    auth = graphify_semantic_slice.classify_auth(auth_proc.stdout)
    version_proc = subprocess.run(
        [str(executable), "--version"],
        capture_output=True,
        check=False,
        env=environment,
        timeout=30,
    )
    version = version_proc.stdout.decode("utf-8", errors="strict").strip()
    if version_proc.returncode != 0 or version_proc.stderr or not version:
        raise ValueError("Claude version preflight failed in the sanitized environment")
    return auth, version


def adapter_main() -> int:
    """Forward one validated Graphify call to real Claude and retain safe evidence."""
    executable = _real_executable()
    args = sys.argv[1:]
    if args in (["--help"], ["--version"]):
        return _delegate_info(executable, args)
    try:
        schema = _validate_incoming_args(args)
        environment = _child_environment()
        auth, version = _runtime_identity(executable, environment)
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError, ValueError) as exc:
        print(f"semantic adapter preflight failed: {exc}", file=sys.stderr)
        return 2
    prompt = sys.stdin.buffer.read()
    real_args = (
        str(executable),
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--model",
        graphify_semantic_slice.CLAUDE_MODEL,
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
    started = time.monotonic_ns()
    try:
        boundary_path = Path(os.environ.get("KB_SEMANTIC_PROVIDER_BOUNDARY_PATH", ""))
        write_provider_boundary_start(
            boundary_path,
            adapter_sha256=graphify_semantic_slice.sha256_file(Path(__file__)),
            prompt=prompt,
            argv=real_args,
        )
        completed = subprocess.run(
            real_args,
            input=prompt,
            capture_output=True,
            check=False,
            env=environment,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("semantic adapter inference timed out", file=sys.stderr)
        return 124
    elapsed_ms = (time.monotonic_ns() - started) // 1_000_000
    envelope = _result_envelope(completed.stdout)
    reasons = list(graphify_semantic_slice.envelope_reasons(envelope))
    if completed.returncode != 0:
        reasons.append("claude-returncode-nonzero")
    if completed.stderr:
        reasons.append("claude-stderr-present")
    metadata = _metadata(
        MetadataInputs(
            executable=executable,
            version=version,
            argv=real_args[1:],
            environment=environment,
            auth=auth,
            prompt=prompt,
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
            envelope=envelope,
            elapsed_ms=elapsed_ms,
            reasons=tuple(dict.fromkeys(reasons)),
        )
    )
    _write_metadata(metadata)
    if metadata.reasons:
        print("semantic adapter rejected result: " + ", ".join(metadata.reasons), file=sys.stderr)
        return 1
    sys.stdout.buffer.write(completed.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(adapter_main())
