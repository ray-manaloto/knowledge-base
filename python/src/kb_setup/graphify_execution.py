# Copyright (c) 2026 Raymond Manaloto
"""Managed Graphify CLI execution with byte capture and durable receipts."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import signal
import stat
import subprocess
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

_DEFAULTS = {
    "claude-cli": ("opus", "xhigh", "claude"),
    "openai-cli": ("gpt-5.6-sol", "high", "codex"),
}
_API_AUTH_NAMES = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "KIMI_API_KEY",
        "DEEPSEEK_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "ANTHROPIC_BASE_URL",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_API_KEY",
        "GROQ_API_KEY",
        "MISTRAL_API_KEY",
        "MOONSHOT_API_KEY",
        "OLLAMA_BASE_URL",
        "OLLAMA_HOST",
    }
)
_PRIVATE_FILE_MODE = 0o600
_SINGLE_FENCE_MARKER_COUNT = 2


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: object) -> str:
    """Return Graphify's canonical JSON SHA-256 representation."""
    return hashlib.sha256(_canonical(value)).hexdigest()


def file_digest(path: Path) -> str:
    """Hash one exact on-disk file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject_hidden_api_auth(environment: dict[str, str]) -> None:
    """Refuse API credentials on a subscription-CLI-only route."""
    present = sorted(name for name in _API_AUTH_NAMES if environment.get(name))
    if present:
        raise ValueError(f"API authentication is forbidden for managed CLI extraction: {present}")


def binary_identity(path: Path) -> dict[str, str]:
    """Measure the executable selected for the managed profile."""
    resolved = path.resolve(strict=True)
    result = subprocess.run(
        [str(resolved), "--version"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot identify CLI binary {resolved}: exit {result.returncode}")
    version = (result.stdout or result.stderr).decode("utf-8", "replace").strip()
    if not version:
        raise RuntimeError(f"cannot identify CLI binary {resolved}: empty --version output")
    return {"path": str(resolved), "sha256": file_digest(resolved), "version": version}


@dataclass(frozen=True, slots=True)
class ProfileSelection:
    """Optional selectors and measured inputs for one managed profile."""

    model: str | None = None
    effort: str | None = None
    environment: dict[str, str] | None = None
    binary: Path | None = None
    identity: dict[str, str] | None = None
    purpose: str = "extract"


def resolve_profile(backend: str = "claude-cli", selection: ProfileSelection | None = None) -> dict:
    """Resolve KB defaults through Graphify's public profile validator."""
    from kb_setup import graphify_sdk

    selected = selection or ProfileSelection()
    env = dict(os.environ if selected.environment is None else selected.environment)
    reject_hidden_api_auth(env)
    if backend not in _DEFAULTS:
        raise ValueError(f"unsupported managed CLI backend: {backend!r}")
    default_model, default_effort, binary_name = _DEFAULTS[backend]
    selected_model = selected.model or default_model
    selected_effort = selected.effort or default_effort
    selected_identity = selected.identity
    if selected_identity is None:
        located = selected.binary or Path(shutil.which(binary_name) or "")
        if not located.is_file():
            raise RuntimeError(f"{binary_name} CLI not found on $PATH")
        selected_identity = binary_identity(located)
    profile = {
        "schema_version": 1,
        "backend": backend,
        "model": selected_model,
        "effort": selected_effort,
        "binary_expectation": selected_identity,
        "cli_policy": {
            "project_configuration": "inherit",
            "session_persistence": "retain",
            "mcp": "ignore-user-config" if backend == "openai-cli" else "inherit",
            "sandbox": "read-only",
        },
        "identity_policy": {
            "required_per_response": False,
            "allowed_reported_models": [selected_model],
        },
    }
    return graphify_sdk.resolve_execution_profile_public(
        backend,
        selected.model,
        selected.effort,
        execution_profile=profile,
        purpose=selected.purpose,
        environment=env,
    )


def public_profile_request(profile: dict) -> dict:
    """Project one resolved managed profile into Graphify's public request shape."""
    if profile.get("_explicit") is not True:
        raise ValueError("KB-managed Graphify APIs require a resolved explicit profile")
    public = dict(profile)
    del public["_explicit"]
    return public


def allocate_run_root(
    repo_root: Path, requested: Path | None = None, *, base: Path | None = None
) -> Path:
    """Create a unique run root; an explicit existing root is never overwritten."""
    run_base = base or repo_root / ".agent" / "graphify-runs"
    if requested is not None and requested.exists():
        raise FileExistsError(f"run root already exists: {requested}")
    run_root = (
        requested
        if requested is not None
        else run_base / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:12]}"
    )
    run_root.mkdir(parents=True, exist_ok=False)
    return run_root.resolve(strict=True)


@dataclass(frozen=True, slots=True)
class RunContextSpec:
    """All identities that close one Graphify execution context."""

    run_root: Path
    repo_root: Path
    source_bytes: bytes
    source_scope: list[str]
    prompt: str
    profile: dict
    stage_id: str
    parent_receipts: list[str] | None = None
    cache_ancestry: list[str] | None = None


def build_run_context(spec: RunContextSpec) -> dict:
    """Build the closed provenance context Graphify validates."""
    from kb_setup import graphify_sdk

    module = Path(__file__).resolve(strict=True)
    return {
        "schema_version": 1,
        "run_id": spec.run_root.name,
        "stage_id": spec.stage_id,
        "project_root": str(spec.repo_root.resolve(strict=True)),
        "cwd": str(spec.repo_root.resolve(strict=True)),
        "source_identity": {
            "algorithm": "sha256",
            "digest": hashlib.sha256(spec.source_bytes).hexdigest(),
            "scope": spec.source_scope,
        },
        "prompt_identity": {
            "algorithm": "sha256",
            "digest": hashlib.sha256(spec.prompt.encode()).hexdigest(),
        },
        "extractor_identity": {
            "name": "kb-graphify-managed-cli",
            "version": graphify_sdk.running_sdk_version(),
            "digest": file_digest(module),
        },
        "configuration_identity": {
            "digest": digest({k: v for k, v in spec.profile.items() if not k.startswith("_")}),
            "sources": ["execution_profile"],
        },
        "instruction_identity": {
            "digest": file_digest(module),
            "sources": [str(module)],
        },
        "parent_receipts": list(spec.parent_receipts or []),
        "cache_ancestry": list(spec.cache_ancestry or []),
        "capture_required": True,
    }


def atomic_bytes(path: Path, payload: bytes) -> None:
    """Atomically persist bytes and fsync both file and containing directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass
class ExecutionBudget:
    """One finite launch count and monotonic deadline shared by a KB case."""

    max_attempts: int = 8
    total_seconds: float = 1800.0
    attempts_started: int = 0
    started_monotonic: float = field(default_factory=time.monotonic)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        """Reject invalid limits before any managed process can launch."""
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts < 1
        ):
            raise ValueError("max_attempts must be a positive integer")
        if (
            isinstance(self.total_seconds, bool)
            or not isinstance(self.total_seconds, (int, float))
            or not math.isfinite(self.total_seconds)
            or self.total_seconds <= 0
        ):
            raise ValueError("total_seconds must be finite and positive")

    def admit(self, per_attempt_seconds: float) -> float:
        """Consume one launch allowance and return its bounded process timeout."""
        if (
            isinstance(per_attempt_seconds, bool)
            or not isinstance(per_attempt_seconds, (int, float))
            or not math.isfinite(per_attempt_seconds)
            or per_attempt_seconds <= 0
        ):
            raise ValueError("per-attempt timeout must be finite and positive")
        with self._lock:
            if self.attempts_started >= self.max_attempts:
                raise RuntimeError("Graphify case attempt budget exhausted before launch")
            remaining = self.total_seconds - (time.monotonic() - self.started_monotonic)
            if remaining <= 0:
                raise TimeoutError("Graphify case deadline expired before launch")
            self.attempts_started += 1
            return min(per_attempt_seconds, remaining)


@dataclass
class CapturedProcessRunner:
    """Callable Graphify runner that retains raw byte streams per attempt."""

    run_root: Path
    environment: dict[str, str]
    timeout_seconds: float = 300.0
    shutdown_seconds: float = 5.0
    attempt: int = 0
    environment_overrides: tuple[dict[str, object], ...] = ()
    budget: ExecutionBudget = field(default_factory=ExecutionBudget)

    def __call__(self, request: dict) -> dict:
        """Execute one closed invocation and retain its byte artifacts."""
        if not math.isfinite(self.shutdown_seconds) or self.shutdown_seconds <= 0:
            raise ValueError("shutdown_seconds must be finite and positive")
        argv = list(request["argv"])
        expected = request["requested_profile"]["binary_expectation"]
        actual_path = Path(argv[0]).resolve(strict=True)
        actual = {
            "path": str(actual_path),
            "sha256": file_digest(actual_path),
            "version": expected["version"],
        }
        if actual != expected:
            raise RuntimeError("CLI binary identity changed after profile resolution")
        requested_timeout = request.get("timeout_seconds")
        timeout = self.budget.admit(
            self.timeout_seconds if requested_timeout is None else requested_timeout
        )
        self.attempt += 1
        attempt_root = self.run_root / "attempts" / f"{self.attempt:04d}"
        attempt_root.mkdir(parents=True, exist_ok=False)
        environment_evidence = {
            "schema_version": 1,
            "scope": "selected_child_process",
            "overrides": [dict(item) for item in self.environment_overrides],
        }
        environment_evidence_path = attempt_root / "environment-overrides.json"
        atomic_bytes(environment_evidence_path, _canonical(environment_evidence))
        atomic_bytes(
            attempt_root / "budget.json",
            _canonical(
                {
                    "max_attempts": self.budget.max_attempts,
                    "total_seconds": self.budget.total_seconds,
                    "attempts_started": self.budget.attempts_started,
                    "timeout_seconds": timeout,
                }
            ),
        )
        proc = subprocess.Popen(
            argv,
            cwd=request["cwd"],
            env=self.environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
        )
        timed_out = False
        streams_complete = True
        try:
            stdout, stderr = proc.communicate(
                input=request["stdin"],
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as first_timeout:
            timed_out = True
            with suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            try:
                stdout, stderr = proc.communicate(timeout=self.shutdown_seconds)
            except subprocess.TimeoutExpired as drain_timeout:
                streams_complete = False
                stdout = drain_timeout.output or first_timeout.output or b""
                stderr = drain_timeout.stderr or first_timeout.stderr or b""
        stdout_path = attempt_root / "stdout.bin"
        stderr_path = attempt_root / "stderr.bin"
        atomic_bytes(stdout_path, stdout)
        atomic_bytes(stderr_path, stderr)
        result = {
            "returncode": proc.poll(),
            "stdout": stdout,
            "stderr": stderr,
            "stdout_eof": streams_complete,
            "stderr_eof": streams_complete,
            "finalized": streams_complete,
            "binary": actual,
            "raw_capture_refs": {
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
                "environment_overrides": str(environment_evidence_path),
            },
            "provider_events": _provider_events(stdout),
            "environment_overrides": environment_evidence["overrides"],
            "runner_error": (
                "timed_out_incomplete_capture"
                if timed_out and not streams_complete
                else "timed_out"
                if timed_out
                else None
            ),
        }
        if request.get("output_contract") == "last-message-file":
            output_path = Path(request["output_path"])
            try:
                payload = output_path.read_bytes()
                present = True
            except OSError:
                payload = b""
                present = False
            retained = attempt_root / "result.bin"
            if present:
                atomic_bytes(retained, payload)
            result["result_artifact"] = {
                "requested_path": str(output_path),
                "payload": payload,
                "byte_count": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "raw_ref": str(retained),
                "eof": present and streams_complete,
                "finalized": present and streams_complete,
            }
        return result


def _provider_events(raw: bytes) -> list[dict]:
    events = []
    for line in raw.splitlines():
        try:
            value = json.loads(line)
        except UnicodeDecodeError, json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
        elif isinstance(value, list):
            events.extend(item for item in value if isinstance(item, dict))
    return events


def _reported_responses(events: list[dict]) -> list[dict]:
    responses = []
    for event in events:
        model = event.get("model") or event.get("reported_model")
        response_id = event.get("response_id") or event.get("id")
        if isinstance(model, str) and isinstance(response_id, str):
            responses.append({"response_id": response_id, "reported_model": model})
    return responses


def _provider_token_usage(backend: str, events: list[dict]) -> dict:
    """Record final provider counts, or say explicitly why they are unknown."""
    event_type = "result" if backend == "claude-cli" else "turn.completed"
    candidates = [event for event in events if event.get("type") == event_type]
    if not candidates:
        return {"status": "unknown", "reason": "provider_usage_event_missing"}
    usage = candidates[-1].get("usage")
    if not isinstance(usage, dict):
        return {"status": "unknown", "reason": "provider_usage_missing"}
    names = (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "reasoning_output_tokens",
    )
    if any(
        name not in usage or type(usage[name]) is not int or usage[name] < 0
        for name in ("input_tokens", "output_tokens")
    ) or any(
        name in usage and (type(usage[name]) is not int or usage[name] < 0) for name in names[2:]
    ):
        return {"status": "unknown", "reason": "provider_usage_invalid"}
    return {
        "status": "known",
        "source_event": event_type,
        **{name: usage[name] for name in names if name in usage},
    }


def _claude_terminal_bytes(stdout: bytes) -> bytes:
    """Accept only one explicit final result from a Claude event array."""
    envelope = json.loads(stdout.decode("utf-8"))
    if isinstance(envelope, dict):
        if envelope.get("is_error") is True:
            raise ValueError("Claude terminal result reports an error")
        result = envelope.get("result")
        return result.encode() if isinstance(result, str) else stdout
    if not isinstance(envelope, list):
        return stdout
    if not all(isinstance(event, dict) for event in envelope):
        raise ValueError("Claude terminal event array must contain only JSON objects")
    terminals = [
        (index, event) for index, event in enumerate(envelope) if event.get("type") == "result"
    ]
    if len(terminals) != 1:
        raise ValueError("Claude terminal event array requires exactly one result")
    terminal_index, terminal = terminals[0]
    if terminal_index != len(envelope) - 1:
        raise ValueError("Claude terminal result must be the final provider event")
    if any(event.get("type") == "error" or event.get("is_error") is True for event in envelope):
        raise ValueError("Claude terminal event array reports an error")
    if terminal.get("subtype") != "success" or terminal.get("is_error") is not False:
        raise ValueError("Claude terminal result is not an explicit success")
    result = terminal.get("result")
    if not isinstance(result, str):
        raise TypeError("Claude terminal result must contain a JSON string")
    return result.encode()


def _graph_value(raw: bytes) -> dict:
    """Decode one complete graph object, refusing malformed terminal output."""
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("CLI terminal result is not valid graph JSON") from exc
    if not isinstance(value, dict):
        raise TypeError("CLI terminal graph must be a JSON object")
    if not isinstance(value.get("nodes"), list) or not isinstance(value.get("edges"), list):
        raise TypeError("CLI terminal graph requires nodes and edges arrays")
    if "hyperedges" in value and not isinstance(value["hyperedges"], list):
        raise TypeError("CLI terminal graph hyperedges must be an array")
    return value


def _claude_graph_value(raw: bytes) -> dict:
    """Allow only an exact, single JSON fence around the final Claude graph."""
    if (
        raw.startswith(b"```json\n")
        and raw.endswith(b"\n```")
        and raw.count(b"```") == _SINGLE_FENCE_MARKER_COUNT
    ):
        raw = raw[len(b"```json\n") : -len(b"\n```")]
    return _graph_value(raw)


def restrict_claude_invocation(invocation: dict) -> dict:
    """Confine a managed Claude extraction while recording its actual argv."""
    if invocation.get("backend") != "claude-cli":
        return invocation
    argv = invocation.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) for arg in argv):
        raise ValueError("managed Claude invocation requires a nonempty argv")
    if any(arg in {"--safe-mode", "--tools"} for arg in argv):
        raise ValueError("managed Claude invocation already supplies confinement flags")
    return {**invocation, "argv": [*argv, "--safe-mode", "--tools", "Read"]}


def result_parser(backend: str) -> Callable[[dict], dict]:
    """Return a parser for Graphify's Claude envelope or Codex result artifact."""

    def parse(process: dict) -> dict:
        events = process.get("provider_events", [])
        responses = _reported_responses(events)
        usage = _provider_token_usage(backend, events)
        reasons = ["complete_response_coverage_unverified"]
        if not responses:
            reasons.append("served_model_identity_missing")
        coverage = {"status": "unproved", "reasons": reasons}
        if process.get("runner_error") in {"timed_out", "timed_out_incomplete_capture"}:
            return _parsed(None, "timed_out", responses, coverage, usage)
        if process["returncode"] != 0:
            no_response = (
                not process.get("stdout")
                and not process.get("provider_events")
                and not (process.get("result_artifact") or {}).get("payload")
            )
            return _parsed(
                None,
                "failed_before_response" if no_response else "failed",
                responses,
                coverage,
                usage,
            )
        raw = (
            process["result_artifact"]["payload"]
            if backend == "openai-cli"
            else _claude_terminal_bytes(process["stdout"])
        )
        try:
            value = _graph_value(raw) if backend == "openai-cli" else _claude_graph_value(raw)
        except ValueError, TypeError:
            return _parsed(
                None,
                "failed",
                responses,
                {"status": "unproved", "reasons": [*reasons, "terminal_graph_invalid"]},
                usage,
            )
        return _parsed(value, "completed", responses, coverage, usage)

    return parse


def _parsed(
    value: object, completion: str, responses: list[dict], coverage: dict, usage: dict
) -> dict:
    return {
        "value": value,
        "completion": completion,
        "usage": usage,
        "observations": [],
        "responses": responses,
        "coverage": coverage,
    }


@dataclass(frozen=True)
class DurableReceiptSink:
    """Persist canonical receipt bytes before acknowledging Graphify."""

    run_root: Path

    def __call__(self, receipt: dict) -> dict:
        """Write one receipt and return Graphify's exact acknowledgement."""
        payload = _canonical(receipt)
        receipt_id = receipt["receipt_id"]
        path = self.run_root / "receipts" / f"{receipt_id}.json"
        atomic_bytes(path, payload)
        return {
            "receipt_id": receipt_id,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "finalized": True,
            "durable_ref": str(path),
        }


def _stable_file_bytes(path: Path) -> bytes:
    """Read an exact regular file without following a final symlink."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("raster staged bytes must be one regular file")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_uid,
            before.st_gid,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_uid,
            after.st_gid,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
        )
        if before_identity != after_identity:
            raise ValueError("raster staged bytes changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _require_private_directory(descriptor: int, label: str) -> None:
    info = os.fstat(descriptor)
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError(f"{label} is not a directory")
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError(f"{label} is not an owner-private directory")


def _open_private_directory_at(parent: int, name: str, label: str) -> int:
    with suppress(FileExistsError):
        os.mkdir(name, mode=0o700, dir_fd=parent)
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
        dir_fd=parent,
    )
    try:
        _require_private_directory(descriptor, label)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


@contextmanager
def _snapshot_directories(snapshot_root: Path) -> Iterator[tuple[int, int]]:
    """Open a private retained root and both fixed children without following them."""
    parent_path = snapshot_root.parent.resolve(strict=True)
    if snapshot_root.name in {"", ".", ".."}:
        raise ValueError("raster snapshot root must have one safe final component")
    descriptors: list[int] = []
    try:
        parent = os.open(
            parent_path,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
        )
        descriptors.append(parent)
        root = _open_private_directory_at(parent, snapshot_root.name, "raster snapshot root")
        descriptors.append(root)
        raw = _open_private_directory_at(root, "raw", "raster raw directory")
        descriptors.append(raw)
        receipts = _open_private_directory_at(root, "receipts", "raster receipt directory")
        descriptors.append(receipts)
    except BaseException as exc:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        if isinstance(exc, OSError):
            raise OSError("raster snapshot directory chain is unsafe") from exc
        raise
    try:
        yield raw, receipts
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _atomic_bytes_at(directory: int, name: str, payload: bytes) -> None:
    """Publish one exact file relative to an already authenticated directory."""
    if Path(name).name != name or name in {"", ".", ".."}:
        raise ValueError("raster snapshot file name is unsafe")
    temporary = f".{name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
        0o600,
        dir_fd=directory,
    )
    published = False
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("raster snapshot write made no progress")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        published = True
        os.fsync(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not published:
            with suppress(FileNotFoundError):
                os.unlink(temporary, dir_fd=directory)


def _stable_file_bytes_at(directory: int, name: str) -> bytes:
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
        dir_fd=directory,
    )
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != _PRIVATE_FILE_MODE
        ):
            raise ValueError("raster snapshot is not one regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_uid,
            before.st_gid,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_uid,
            after.st_gid,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
        )
        if before_identity != after_identity:
            raise ValueError("raster snapshot changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


@dataclass(frozen=True, slots=True)
class CapturedRasterStager:
    """Promote Graphify-validated raster bytes into a retained run snapshot."""

    snapshot_root: Path
    source_root: Path

    def __call__(self, request: dict) -> dict:
        """Return Graphify's exact durable snapshot acknowledgment."""
        from kb_setup import graphify_sdk

        expected_root = self.snapshot_root.parent.resolve(strict=True) / self.snapshot_root.name
        if request.get("snapshot_root") != str(expected_root):
            raise ValueError("raster snapshot root differs from the retained run root")
        source_record = request.get("source_record")
        if not isinstance(source_record, dict):
            raise TypeError("raster source record is required")
        with graphify_sdk.stage_ephemeral_raster_attachments_public(
            [source_record], root=self.source_root
        ) as staged_records:
            if len(staged_records) != 1:
                raise ValueError("raster source staging did not return exactly one record")
            staged = staged_records[0]
            staged_bytes = staged["staged_bytes"]
            payload = _stable_file_bytes(Path(staged_bytes["transport_path"]))
            source = source_record["original_source"]
            if (
                len(payload) != source["byte_count"]
                or hashlib.sha256(payload).hexdigest() != source["sha256"]
            ):
                raise ValueError("raster staged bytes differ from the admitted source")
            suffix = Path(staged_bytes["transport_path"]).suffix
            snapshot_id = digest(
                {
                    "canonical_path": source["canonical_path"],
                    "source_sha256": source["sha256"],
                }
            )
            raw_name = f"{snapshot_id}{suffix}"
            receipt_name = f"{snapshot_id}.json"
            raw_path = expected_root / "raw" / raw_name
            receipt_path = expected_root / "receipts" / receipt_name
            with _snapshot_directories(expected_root) as (
                raw_directory,
                receipt_directory,
            ):
                _atomic_bytes_at(raw_directory, raw_name, payload)
                if _stable_file_bytes_at(raw_directory, raw_name) != payload:
                    raise ValueError("raster snapshot bytes are not self-consistent")
                acknowledgment = {
                    "schema_version": staged["schema_version"],
                    "status": "complete",
                    "raw_ref": str(raw_path),
                    "receipt_ref": str(receipt_path),
                    "transport_path": str(raw_path),
                    "source_sha256": source["sha256"],
                    "source_byte_count": source["byte_count"],
                    "staged_sha256": hashlib.sha256(payload).hexdigest(),
                    "staged_byte_count": len(payload),
                    "finalized": True,
                }
                graphify_sdk.verify_raster_snapshot_ack_public(
                    acknowledgment,
                    source_record=source_record,
                    snapshot_root=expected_root,
                )
                receipt_payload = _canonical(acknowledgment)
                _atomic_bytes_at(receipt_directory, receipt_name, receipt_payload)
                if _stable_file_bytes_at(receipt_directory, receipt_name) != receipt_payload:
                    raise ValueError("raster snapshot receipt bytes are not self-consistent")
                return acknowledgment


def child_environment_override_evidence(
    backend: str,
) -> tuple[dict[str, object], ...]:
    """Describe leaf-only environment policy without exposing environment values."""
    if backend != "claude-cli":
        return ()
    return ({"name": "CLAUDE_CODE_BRIEF", "action": "unset", "scope": "selected_child"},)


def safe_child_environment(
    environment: dict[str, str] | None = None, *, backend: str | None = None
) -> dict[str, str]:
    """Preserve project CLI discovery while removing provider API credentials."""
    source = dict(os.environ if environment is None else environment)
    reject_hidden_api_auth(source)
    child = {
        name: value
        for name, value in source.items()
        if name not in _API_AUTH_NAMES and not name.startswith("__MISE_")
    }
    if backend == "claude-cli":
        child.pop("CLAUDE_CODE_BRIEF", None)
    return child
