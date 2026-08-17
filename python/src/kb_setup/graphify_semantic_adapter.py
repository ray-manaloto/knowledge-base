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
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path

import msgspec

from kb_setup import atomic, graphify_semantic_slice

_GRAPHIFY_ARG_COUNT = 8
_SHA256_HEX_LENGTH = 64
_MIN_MULTI_EVENT_COUNT = 2


class _NonJsonConstantError(ValueError):
    """Signal a Python-only numeric constant without retaining its spelling."""


class _JsonNumericLimitError(ValueError):
    """Signal the decoder's bounded integer conversion without retaining digits."""


def _reject_non_json_constant(_value: str) -> None:
    raise _NonJsonConstantError


def _strict_json_integer(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise _JsonNumericLimitError from exc


def open_directory_nofollow(directory: Path) -> int:
    """Open every directory component without following a mutable symlink."""
    if ".." in directory.parts:
        raise ValueError("provider boundary marker destination is unavailable")
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    parts = directory.parts
    descriptor = os.open(os.sep if directory.is_absolute() else ".", flags)
    try:
        for part in parts[1:] if directory.is_absolute() else parts:
            if part in ("", ".", os.sep):
                continue
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


class ModelUsage(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Allowlisted identity and usage for the sole returned provider model."""

    model: str
    canonical_model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class EnvelopeParseObservation(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Content-free facts about parsing one discarded Claude stdout payload."""

    schema_id: str
    status: str
    response_sha256: str
    response_size: int
    utf8_valid: bool
    json_valid: bool
    top_level_kind: str
    event_count: int
    result_count: int
    selected_index: int
    error_offset: int
    trailing_non_whitespace: bool


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
    parse_observation: EnvelopeParseObservation | None = None
    parse_observation_sha256: str = ""
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
    parse_observation: EnvelopeParseObservation
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
        parent_descriptor = open_directory_nofollow(destination.parent)
    except OSError as exc:
        raise ValueError("provider boundary marker destination is unavailable") from exc
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
        if not stat.S_ISDIR(os.fstat(parent_descriptor).st_mode):
            raise ValueError("provider boundary marker destination is unavailable")
        try:
            descriptor = os.open(destination.name, flags, 0o600, dir_fd=parent_descriptor)
        except FileExistsError as exc:
            raise ValueError("provider boundary marker already exists") from exc
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(parent_descriptor)
        except BaseException:
            with suppress(FileNotFoundError):
                os.unlink(destination.name, dir_fd=parent_descriptor)
            raise
    finally:
        os.close(parent_descriptor)
    return marker


class ProviderSpendRecord(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """What ONE provider call cost, written where the caller can sum it.

    ``AdapterMetadata`` already carries ``total_cost_usd``, and this is not a
    second opinion about the same number — it is the same number at a
    granularity the metadata file cannot express. The metadata path is ONE fixed
    file that every call overwrites, so a chunk graphify bisected into four leaf
    calls leaves only the last leaf's cost behind. A caller summing metadata
    therefore undercounts exactly the expensive chunks, which is the wrong
    direction for a spend cap to be wrong in.

    One file per call, in the caller's boundary directory, sums correctly across
    bisected chunks and across a chunk whose provider call FAILED after spending
    — that call writes its record and never reaches the caller's callback, so its
    cost lands in the next chunk's read rather than vanishing.
    """

    schema_id: str
    total_cost_usd: float


def write_provider_spend(directory: Path, total_cost_usd: float) -> Path:
    """Record one call's cost beside its boundary marker, or raise.

    Raising is deliberate: the caller's cumulative cap is only as real as its
    ability to observe spend, so a run that cannot write this record must stop
    rather than continue uncounted. The slice never reaches here — it configures
    ``…_PATH`` and no directory — so the strictness costs it nothing.
    """
    destination = directory / f"provider-spend-{os.getpid()}-{time.monotonic_ns()}.json"
    record = ProviderSpendRecord(
        schema_id="graphify-claude-provider-spend/v0",
        total_cost_usd=total_cost_usd,
    )
    raw = graphify_semantic_slice.encode_json(record) + b"\n"
    parent_descriptor = open_directory_nofollow(destination.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination.name, flags, 0o600, dir_fd=parent_descriptor)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent_descriptor)
    finally:
        os.close(parent_descriptor)
    return destination


def _provider_boundary_path(environment: Mapping[str, str]) -> Path:
    """Resolve where this invocation writes its provider-boundary marker.

    Two spellings, and the second exists because the first cannot serve a
    multi-call run. `…_PATH` is one fixed file: the marker is created `O_EXCL`,
    so a caller that makes N calls must delete it between them, and a call that
    FAILS never gets the chance — stranding the marker and making every later
    call in that run die on `already exists`. One recoverable error became a
    whole-corpus failure naming the wrong cause.

    `…_DIR` gives each invocation its own file inside a caller-owned directory,
    so `O_EXCL` still means what it says — one crossing per marker — while a
    failed call strands nothing. The slice keeps using `…_PATH`: it makes exactly
    one call, and its committed evidence names that exact member.

    Neither set is still an error. Absence must never mean "skip the marker" —
    nothing checks after the fact that one was written, so a launcher that merely
    forgot would lose its provider-call evidence in silence.
    """
    directory = environment.get("KB_SEMANTIC_PROVIDER_BOUNDARY_DIR", "")
    if directory:
        # pid + monotonic ns: unique within a run without a shared counter, and
        # without depending on wall-clock, which can repeat under adjustment.
        return Path(directory) / f"provider-boundary-{os.getpid()}-{time.monotonic_ns()}.json"
    raw = environment.get("KB_SEMANTIC_PROVIDER_BOUNDARY_PATH", "")
    if not raw:
        raise ValueError("provider boundary marker path is unset")
    return Path(raw)


def _real_executable() -> Path:
    raw = os.environ.get("KB_SEMANTIC_REAL_CLAUDE", "")
    expected = os.environ.get("KB_SEMANTIC_REAL_CLAUDE_SHA256", "")
    path = Path(raw).resolve()
    if not path.is_file() or not expected or graphify_semantic_slice.sha256_file(path) != expected:
        raise ValueError("real Claude executable identity drifted")
    return path


def _child_environment(
    profile: graphify_semantic_slice.ClaudeProfile | None = None,
) -> dict[str, str]:
    return graphify_semantic_slice.claude_child_environment(
        os.environ,
        original_path=os.environ.get("KB_SEMANTIC_ORIGINAL_PATH", ""),
        profile=profile,
    )


def _top_level_kind(payload: object) -> str:
    candidates = (
        (isinstance(payload, dict), "object"),
        (isinstance(payload, list), "array"),
        (isinstance(payload, str), "string"),
        (isinstance(payload, bool), "boolean"),
        (payload is None, "null"),
        (isinstance(payload, (int, float)), "number"),
    )
    for accepted, kind in candidates:
        if accepted:
            return kind
    return "unknown"


def _intended_top_level_kind(text: str) -> str:
    stripped = text.lstrip()
    if not stripped:
        return "unknown"
    return {
        "{": "object",
        "[": "array",
        '"': "string",
        "t": "boolean",
        "f": "boolean",
        "n": "null",
    }.get(stripped[0], "number" if stripped[0] in "-0123456789NI" else "unknown")


def parse_result_envelope(stdout: bytes) -> tuple[dict[str, object], EnvelopeParseObservation]:
    """Parse stdout while retaining only content-free diagnostic facts."""
    response_sha256 = _sha256(stdout)
    response_size = len(stdout)
    try:
        text = stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        return {}, EnvelopeParseObservation(
            schema_id="graphify-claude-envelope-parse/v1",
            status="invalid-utf8",
            response_sha256=response_sha256,
            response_size=response_size,
            utf8_valid=False,
            json_valid=False,
            top_level_kind="unknown",
            event_count=0,
            result_count=0,
            selected_index=-1,
            error_offset=exc.start,
            trailing_non_whitespace=False,
        )
    try:
        payload = json.loads(
            text,
            parse_constant=_reject_non_json_constant,
            parse_int=_strict_json_integer,
        )
    except (_NonJsonConstantError, _JsonNumericLimitError, RecursionError) as exc:
        status = (
            "non-json-constant"
            if isinstance(exc, _NonJsonConstantError)
            else "numeric-limit"
            if isinstance(exc, _JsonNumericLimitError)
            else "nesting-limit"
        )
        return {}, EnvelopeParseObservation(
            schema_id="graphify-claude-envelope-parse/v1",
            status=status,
            response_sha256=response_sha256,
            response_size=response_size,
            utf8_valid=True,
            json_valid=False,
            top_level_kind=_intended_top_level_kind(text),
            event_count=0,
            result_count=0,
            selected_index=-1,
            error_offset=-1,
            trailing_non_whitespace=False,
        )
    except json.JSONDecodeError as exc:
        trailing = exc.msg == "Extra data" and bool(text[exc.pos :].strip())
        byte_offset = len(text[: exc.pos].encode("utf-8"))
        status = (
            "trailing-data"
            if trailing
            else "truncated-json"
            if exc.pos >= len(text.rstrip())
            else "invalid-json"
        )
        return {}, EnvelopeParseObservation(
            schema_id="graphify-claude-envelope-parse/v1",
            status=status,
            response_sha256=response_sha256,
            response_size=response_size,
            utf8_valid=True,
            json_valid=False,
            top_level_kind=_intended_top_level_kind(text),
            event_count=0,
            result_count=0,
            selected_index=-1,
            error_offset=byte_offset,
            trailing_non_whitespace=trailing,
        )
    kind = _top_level_kind(payload)
    event_count = 1 if isinstance(payload, dict) else 0
    result_count = int(isinstance(payload, dict) and payload.get("type") == "result")
    selected_index = 0 if isinstance(payload, dict) else -1
    status = "accepted-object" if isinstance(payload, dict) else "valid-non-object"
    envelope: dict[str, object] = payload if isinstance(payload, dict) else {}
    if isinstance(payload, list):
        event_count = len(payload)
        object_events = [event for event in payload if isinstance(event, dict)]
        result_indices = [
            index
            for index, event in enumerate(payload)
            if isinstance(event, dict) and event.get("type") == "result"
        ]
        result_count = len(result_indices)
        if not payload:
            status = "result-array-empty"
        elif len(object_events) != event_count:
            status = "result-array-non-object-event"
        elif not result_indices:
            status = "result-array-missing-final-result"
        elif len(result_indices) != 1:
            status = "result-array-ambiguous-result"
        elif result_indices[0] != event_count - 1:
            status = "result-array-trailing-event"
            selected_index = result_indices[0]
        else:
            status = "accepted-result-array"
            selected_index = result_indices[0]
            envelope = object_events[selected_index]
    observation = EnvelopeParseObservation(
        schema_id="graphify-claude-envelope-parse/v1",
        status=status,
        response_sha256=response_sha256,
        response_size=response_size,
        utf8_valid=True,
        json_valid=True,
        top_level_kind=kind,
        event_count=event_count,
        result_count=result_count,
        selected_index=selected_index,
        error_offset=-1,
        trailing_non_whitespace=False,
    )
    return envelope, observation


def _result_envelope(stdout: bytes) -> dict[str, object]:
    envelope, _observation = parse_result_envelope(stdout)
    return envelope


def parse_observation_sha256(observation: EnvelopeParseObservation) -> str:
    """Digest canonical sanitized observation bytes, never response content."""
    return _sha256(graphify_semantic_slice.encode_json(observation))


def _is_sha256(value: str) -> bool:
    return len(value) == _SHA256_HEX_LENGTH and all(
        character in "0123456789abcdef" for character in value
    )


def parse_observation_reasons(
    observation: EnvelopeParseObservation | None,
    *,
    digest: str,
    response_sha256: str,
    response_size: int,
) -> tuple[str, ...]:
    """Cross-bind one sanitized observation to its enclosing adapter receipt."""
    if observation is None:
        return ("parse-observation-unavailable",)
    valid_shapes = {
        "accepted-object": (
            observation.utf8_valid
            and observation.json_valid
            and observation.top_level_kind == "object"
            and observation.event_count == 1
            and observation.result_count in {0, 1}
            and observation.selected_index == 0
            and observation.error_offset == -1
            and not observation.trailing_non_whitespace
        ),
        "accepted-result-array": (
            observation.utf8_valid
            and observation.json_valid
            and observation.top_level_kind == "array"
            and observation.event_count >= 1
            and observation.result_count == 1
            and observation.selected_index == observation.event_count - 1
            and observation.error_offset == -1
            and not observation.trailing_non_whitespace
        ),
        "result-array-empty": (
            observation.utf8_valid
            and observation.json_valid
            and observation.top_level_kind == "array"
            and observation.event_count == 0
            and observation.result_count == 0
            and observation.selected_index == -1
            and observation.error_offset == -1
            and not observation.trailing_non_whitespace
        ),
        "result-array-non-object-event": (
            observation.utf8_valid
            and observation.json_valid
            and observation.top_level_kind == "array"
            and observation.event_count >= 1
            and 0 <= observation.result_count <= observation.event_count
            and observation.selected_index == -1
            and observation.error_offset == -1
            and not observation.trailing_non_whitespace
        ),
        "result-array-missing-final-result": (
            observation.utf8_valid
            and observation.json_valid
            and observation.top_level_kind == "array"
            and observation.event_count >= 1
            and observation.result_count == 0
            and observation.selected_index == -1
            and observation.error_offset == -1
            and not observation.trailing_non_whitespace
        ),
        "result-array-ambiguous-result": (
            observation.utf8_valid
            and observation.json_valid
            and observation.top_level_kind == "array"
            and observation.event_count >= _MIN_MULTI_EVENT_COUNT
            and _MIN_MULTI_EVENT_COUNT <= observation.result_count <= observation.event_count
            and observation.selected_index == -1
            and observation.error_offset == -1
            and not observation.trailing_non_whitespace
        ),
        "result-array-trailing-event": (
            observation.utf8_valid
            and observation.json_valid
            and observation.top_level_kind == "array"
            and observation.event_count >= _MIN_MULTI_EVENT_COUNT
            and observation.result_count == 1
            and 0 <= observation.selected_index < observation.event_count - 1
            and observation.error_offset == -1
            and not observation.trailing_non_whitespace
        ),
        "valid-non-object": (
            observation.utf8_valid
            and observation.json_valid
            and observation.top_level_kind in {"string", "number", "boolean", "null"}
            and observation.event_count == 0
            and observation.result_count == 0
            and observation.selected_index == -1
            and observation.error_offset == -1
            and not observation.trailing_non_whitespace
        ),
        "invalid-utf8": (
            not observation.utf8_valid
            and not observation.json_valid
            and observation.top_level_kind == "unknown"
            and observation.event_count == 0
            and observation.result_count == 0
            and observation.selected_index == -1
            and observation.error_offset >= 0
            and not observation.trailing_non_whitespace
        ),
        "truncated-json": (
            observation.utf8_valid
            and not observation.json_valid
            and observation.event_count == 0
            and observation.result_count == 0
            and observation.selected_index == -1
            and observation.error_offset >= 0
            and not observation.trailing_non_whitespace
        ),
        "trailing-data": (
            observation.utf8_valid
            and not observation.json_valid
            and observation.event_count == 0
            and observation.result_count == 0
            and observation.selected_index == -1
            and observation.error_offset >= 0
            and observation.trailing_non_whitespace
        ),
        "invalid-json": (
            observation.utf8_valid
            and not observation.json_valid
            and observation.event_count == 0
            and observation.result_count == 0
            and observation.selected_index == -1
            and observation.error_offset >= 0
            and not observation.trailing_non_whitespace
        ),
        "non-json-constant": (
            observation.utf8_valid
            and not observation.json_valid
            and observation.top_level_kind in {"object", "array", "number"}
            and observation.event_count == 0
            and observation.result_count == 0
            and observation.selected_index == -1
            and observation.error_offset == -1
            and not observation.trailing_non_whitespace
        ),
        "numeric-limit": (
            observation.utf8_valid
            and not observation.json_valid
            and observation.top_level_kind in {"object", "array", "number"}
            and observation.event_count == 0
            and observation.result_count == 0
            and observation.selected_index == -1
            and observation.error_offset == -1
            and not observation.trailing_non_whitespace
        ),
        "nesting-limit": (
            observation.utf8_valid
            and not observation.json_valid
            and observation.top_level_kind in {"object", "array"}
            and observation.event_count == 0
            and observation.result_count == 0
            and observation.selected_index == -1
            and observation.error_offset == -1
            and not observation.trailing_non_whitespace
        ),
    }
    checks = (
        (
            observation.schema_id == "graphify-claude-envelope-parse/v1",
            "parse-observation-schema-mismatch",
        ),
        (_is_sha256(digest), "parse-observation-digest-invalid"),
        (
            parse_observation_sha256(observation) == digest,
            "parse-observation-digest-mismatch",
        ),
        (
            _is_sha256(observation.response_sha256) and _is_sha256(response_sha256),
            "parse-observation-response-digest-invalid",
        ),
        (
            observation.response_sha256 == response_sha256,
            "parse-observation-response-digest-mismatch",
        ),
        (
            observation.response_size >= 0 and response_size >= 0,
            "parse-observation-response-size-invalid",
        ),
        (
            observation.response_size == response_size,
            "parse-observation-response-size-mismatch",
        ),
        (
            observation.error_offset == -1
            if observation.json_valid
            or observation.status in {"non-json-constant", "numeric-limit", "nesting-limit"}
            else 0 <= observation.error_offset <= observation.response_size,
            "parse-observation-error-offset-invalid",
        ),
        (
            valid_shapes.get(observation.status, False),
            "parse-observation-shape-mismatch",
        ),
    )
    return tuple(reason for accepted, reason in checks if not accepted)


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


def _validate_incoming_args(args: list[str], profile: graphify_semantic_slice.ClaudeProfile) -> str:
    if graphify_semantic_slice.route_override_names(os.environ):
        raise ValueError("routing override reached semantic adapter")
    schema = args[7] if len(args) == _GRAPHIFY_ARG_COUNT else ""
    expected = [
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--model",
        profile.model,
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
        parse_observation=inputs.parse_observation,
        parse_observation_sha256=parse_observation_sha256(inputs.parse_observation),
    )


#: The ceiling this adapter falls back to when no graphify timeout is configured.
#: It is the historical hardcoded value, kept as the default deliberately: a launcher
#: that configures nothing should get the OLD, SHORTER bound rather than an unbounded
#: wait. Fail-closed for a timeout means shorter, not longer.
_FALLBACK_INFERENCE_TIMEOUT_SECONDS = 120


def inference_timeout_seconds(environment: Mapping[str, str] | None = None) -> float:
    """How long this adapter may wait for one real provider call.

    Read from `GRAPHIFY_API_TIMEOUT` — the variable the corpus driver ALREADY sets
    from `config.timeout_seconds` for graphify's own use — rather than from a second
    variable of its own. That is the point: this ceiling used to be a hardcoded
    `timeout=120` reachable from no configuration at all, so raising the plan's
    `timeout_seconds` moved which of two 120-second limits killed the call instead of
    lengthening it (#335). One variable with two consumers cannot drift; two
    variables asserted to agree can, and nothing was asserting it.

    Measured 2026-08-17, which is why 120 was never going to work: one median corpus
    chunk (7 members, 18,218 estimated tokens) took **659.5 s at rc=0** — and that
    was on graphify's argv, WITHOUT the `--effort high` the adapter adds.

    Equality with graphify's ceiling is intentional rather than sloppy. graphify
    starts the shim and the shim starts Claude, so graphify's clock starts first and
    its timeout fires first at the same nominal value. The outer bound stays the
    governing one and this remains a backstop — which is the right relationship,
    because graphify's failure carries the chunk context and this one does not.
    """
    raw = (os.environ if environment is None else environment).get("GRAPHIFY_API_TIMEOUT", "")
    try:
        parsed = float(raw)
    except ValueError:
        return _FALLBACK_INFERENCE_TIMEOUT_SECONDS
    if parsed <= 0:
        return _FALLBACK_INFERENCE_TIMEOUT_SECONDS
    return parsed


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


def _claude_invocation_args(
    executable: Path,
    schema: str,
    environment: Mapping[str, str],
    profile: graphify_semantic_slice.ClaudeProfile,
) -> tuple[str, ...]:
    """Build the outgoing call from the SAME definition both verifiers check against.

    Previously this tuple was spelled out here and again in the verifier, so the
    two could drift into agreeing with each other about a call neither had seen.
    `expected_adapter_argv` is now the one definition; the boundary marker still
    gates `--max-turns`, so a launcher that configures no marker still gets the
    historical #300 shape rather than silently acquiring a flag.
    """
    return (
        str(executable),
        *graphify_semantic_slice.expected_adapter_argv(
            profile,
            schema,
            # EITHER spelling configures the marker, so either must gate the
            # flag. Checking only `…_PATH` would drop `--max-turns` for every
            # `…_DIR` caller and then fail them on an argv-shape mismatch — a
            # marker-plumbing change surfacing as a turn-limit error.
            with_max_turns=bool(
                environment.get("KB_SEMANTIC_PROVIDER_BOUNDARY_PATH")
                or environment.get("KB_SEMANTIC_PROVIDER_BOUNDARY_DIR")
            ),
        ),
    )


def _completion_reasons(
    envelope: dict[str, object],
    environment: Mapping[str, str],
    completed: subprocess.CompletedProcess[bytes],
) -> tuple[str, ...]:
    """Collect every refusal reason for one completed provider call, first-seen order.

    The process-level reasons live beside the envelope-level ones rather than in
    `adapter_main`, so the refusal policy is one readable unit and the caller
    holds only the decision it makes with the result.
    """
    reasons = list(result_envelope_reasons(envelope, environment))
    if completed.returncode != 0:
        reasons.append("claude-returncode-nonzero")
    if completed.stderr:
        reasons.append("claude-stderr-present")
    return tuple(dict.fromkeys(reasons))


def _report_rejection(reasons: tuple[str, ...]) -> int:
    """Print a refusal to stderr — with the truncation hint when it applies — and fail.

    The refusal stands — a truncated structured output is not evidence and is
    never passed through. What changes is that graphify can now TELL truncation
    from every other refusal.

    It reads this process's failure as `RuntimeError("claude -p exited 1:
    <stderr>")` and classifies it by substring, so a refusal worded only as
    `stop-reason-invalid` matched none of its context-overflow markers and the
    chunk was dropped whole. That made the plan's `graphify_max_retry_depth=2`
    inert for truncation — the one failure it exists to survive. With the hint,
    adaptive retry bisects the chunk.
    """
    print("semantic adapter rejected result: " + ", ".join(reasons), file=sys.stderr)
    hint = graphify_semantic_slice.truncation_retry_hint(reasons)
    if hint:
        print(hint, file=sys.stderr)
    return 1


def adapter_main() -> int:
    """Forward one validated Graphify call to real Claude and retain safe evidence."""
    executable = _real_executable()
    args = sys.argv[1:]
    if args in (["--help"], ["--version"]):
        return _delegate_info(executable, args)
    try:
        profile = graphify_semantic_slice.profile_for(os.environ)
        schema = _validate_incoming_args(args, profile)
        environment = _child_environment(profile)
        auth, version = _runtime_identity(executable, environment)
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError, ValueError) as exc:
        print(f"semantic adapter preflight failed: {exc}", file=sys.stderr)
        return 2
    prompt = sys.stdin.buffer.read()
    real_args = _claude_invocation_args(executable, schema, os.environ, profile)
    started = time.monotonic_ns()
    try:
        boundary_path = _provider_boundary_path(os.environ)
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
            timeout=inference_timeout_seconds(),
        )
    except (OSError, ValueError) as exc:
        print(f"semantic adapter boundary marker failed: {exc}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print("semantic adapter inference timed out", file=sys.stderr)
        return 124
    elapsed_ms = (time.monotonic_ns() - started) // 1_000_000
    envelope, parse_observation = parse_result_envelope(completed.stdout)
    reasons = _completion_reasons(envelope, os.environ, completed)
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
            parse_observation=parse_observation,
            elapsed_ms=elapsed_ms,
            reasons=reasons,
        )
    )
    return _retain_and_report(metadata, completed.stdout)


def _retain_and_report(metadata: AdapterMetadata, stdout: bytes) -> int:
    """Persist this call's evidence, then decide what the caller sees.

    Split out of ``adapter_main`` so the spend record could be added without the
    entry point growing a seventh exit. The order is load-bearing: metadata, then
    spend, then the verdict — the caller's cumulative cap reads the spend record,
    so a call that reported its result before recording its cost would let the
    next chunk start against a stale total.
    """
    _write_metadata(metadata)
    # Unconditionally on the directory path — a REJECTED call still spent money,
    # so recording the cost only for accepted results would hide precisely the
    # calls a cap exists to stop.
    spend_directory = os.environ.get("KB_SEMANTIC_PROVIDER_BOUNDARY_DIR", "")
    if spend_directory:
        try:
            write_provider_spend(Path(spend_directory), metadata.total_cost_usd)
        except (OSError, ValueError) as exc:
            # Fail the call. The caller's cap is only as real as its ability to
            # observe spend, so a run that cannot record what it just spent must
            # stop rather than continue uncounted.
            print(f"semantic adapter spend record failed: {exc}", file=sys.stderr)
            return 2
    if metadata.reasons:
        return _report_rejection(metadata.reasons)
    sys.stdout.buffer.write(stdout)
    return 0


def result_envelope_reasons(
    envelope: object,
    environment: Mapping[str, str],
) -> tuple[str, ...]:
    """Apply the same bounded result policy at both semantic boundaries.

    The environment is READ now rather than ignored: it selects the profile, and
    the model check is per-profile. While it was `_environment` the policy was
    "bounded" in the sense of pinned to the slice's model, so the corpus boundary
    rejected its own correct responses.
    """
    return graphify_semantic_slice.envelope_reasons(
        envelope, profile=graphify_semantic_slice.profile_for(environment)
    )


if __name__ == "__main__":
    raise SystemExit(adapter_main())
