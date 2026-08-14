# Copyright (c) 2026 Raymond Manaloto
"""One-call launcher and audit boundary for issue #301's max-chunk prototype."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path

import msgspec
from graphify.llm import (
    FileSlice,
    _extraction_system,
    _read_files,
)

from kb_setup import (
    atomic,
    graphify_semantic_corpus,
    graphify_semantic_corpus_authority,
    graphify_semantic_slice,
)

_EXTRACTION_USER_INSTRUCTION = (
    "\n\n---\n"
    "Now extract the knowledge graph from the following source file(s) "
    "and output ONLY the JSON object described above. No prose, no "
    "preamble, no markdown fences.\n\n"
)

_AMBIENT_NAMES = (
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
_REQUIRED_AMBIENT_NAMES = ("HOME", "XDG_CONFIG_HOME")
_OVERLAY_NAMES = frozenset(
    {
        "GRAPHIFY_API_TIMEOUT",
        "GRAPHIFY_CLAUDE_CLI_MODEL",
        "GRAPHIFY_NO_INCREMENTAL_CACHE",
        "KB_SEMANTIC_METADATA_PATH",
        "KB_SEMANTIC_ORIGINAL_PATH",
        "KB_SEMANTIC_PROVIDER_BOUNDARY_PATH",
        "KB_SEMANTIC_REAL_CLAUDE",
        "KB_SEMANTIC_REAL_CLAUDE_SHA256",
        "PATH",
    }
)
_ORIGINAL_OUTCOME_SHA256 = "d451f0009c9769c8b193ca50e3cf4f67293675d773c9e6fd7111d39289b3f90c"
_FAILED_STAGE_SHA256 = "534891bb528e923928d1a83ed3dbb26a3d0c7ff221cec03cbd2c36473f62d1ad"
_FAILED_ELAPSED_MS = 659


class FailedAttemptAudit(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Append-only correction for the first launcher's ambiguous call counter."""

    schema_id: str
    status: str
    adapter_invocations: int
    provider_inferences: str
    failure_phase: str
    original_outcome_sha256: str
    stage_receipt_sha256: str
    adapter_metadata_size: int
    elapsed_ms: int
    reasons: tuple[str, ...]


class PrototypePreflightReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """No-inference proof for the exact corrected launcher and max chunk."""

    schema_id: str
    status: str
    provider_inferences: int
    plan_manifest_sha256: str
    execution_config_sha256: str
    launcher_sha256: str
    adapter_sha256: str
    prototype_contract_sha256: str
    chunk_ordinal: int
    chunk_total: int
    estimated_tokens: int
    prompt_sha256: str
    prompt_size: int
    model: str
    auth_method: str
    api_provider: str
    subscription_type: str
    claude_version: str
    adapter_environment_names: tuple[str, ...]
    reasons: tuple[str, ...]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def adapter_process_environment(
    ambient: Mapping[str, str], overlay: Mapping[str, str]
) -> dict[str, str]:
    """Overlay reviewed adapter controls onto only required ambient auth state."""
    forbidden = graphify_semantic_slice.route_override_names(ambient)
    if forbidden:
        raise ValueError("forbidden routing environment names: " + ", ".join(forbidden))
    unknown = tuple(sorted(set(overlay) - _OVERLAY_NAMES))
    if unknown:
        raise ValueError("unknown adapter overlay names: " + ", ".join(unknown))
    result = {name: ambient[name] for name in _AMBIENT_NAMES if ambient.get(name)}
    result.update(overlay)
    missing = tuple(name for name in (*_REQUIRED_AMBIENT_NAMES, "PATH") if not result.get(name))
    if missing:
        raise ValueError("required adapter environment names missing: " + ", ".join(missing))
    return result


def _adapter_overlay(
    runtime: graphify_semantic_slice.ClaudePreflight,
    metadata_path: Path,
    provider_boundary_path: Path,
    adapter_dir: Path,
) -> dict[str, str]:
    original_path = os.environ.get("PATH", "")
    entrypoint = shutil.which("kb-semantic-claude", path=original_path)
    real_claude = shutil.which("claude", path=original_path)
    if entrypoint is None or real_claude is None:
        raise ValueError("semantic adapter or real Claude is unavailable")
    real_path = Path(real_claude).resolve()
    if graphify_semantic_slice.sha256_file(real_path) != runtime.executable_sha256:
        raise ValueError("Claude executable changed after preflight")
    (adapter_dir / "claude").symlink_to(Path(entrypoint).resolve())
    return {
        "PATH": f"{adapter_dir}{os.pathsep}{original_path}",
        "KB_SEMANTIC_REAL_CLAUDE": str(real_path),
        "KB_SEMANTIC_REAL_CLAUDE_SHA256": runtime.executable_sha256,
        "KB_SEMANTIC_ORIGINAL_PATH": original_path,
        "KB_SEMANTIC_METADATA_PATH": str(metadata_path),
        "KB_SEMANTIC_PROVIDER_BOUNDARY_PATH": str(provider_boundary_path),
        "GRAPHIFY_CLAUDE_CLI_MODEL": graphify_semantic_slice.CLAUDE_MODEL,
        "GRAPHIFY_API_TIMEOUT": "120",
        "GRAPHIFY_NO_INCREMENTAL_CACHE": "1",
    }


def _plan_inputs(
    plan: Path, source_root: Path
) -> tuple[
    graphify_semantic_corpus.SourceInventory,
    graphify_semantic_corpus.PlannedChunk,
    graphify_semantic_corpus.CorpusExecutionConfig,
    bytes,
]:
    inventory = msgspec.json.decode(
        (plan / "source-inventory.json").read_bytes(),
        type=graphify_semantic_corpus.SourceInventory,
        strict=True,
    )
    ledger = msgspec.json.decode(
        (plan / "chunk-ledger.json").read_bytes(),
        type=graphify_semantic_corpus.ChunkLedger,
        strict=True,
    )
    config = msgspec.json.decode(
        (plan / "execution-config.json").read_bytes(),
        type=graphify_semantic_corpus.CorpusExecutionConfig,
        strict=True,
    )
    chunk = max(ledger.chunks, key=lambda item: item.estimated_tokens)
    units_by_ordinal = {unit.ordinal: unit for unit in inventory.units}
    units: list[Path | FileSlice] = []
    for member in chunk.members:
        unit = units_by_ordinal[member.unit_ordinal]
        path = source_root / unit.path
        units.append(
            FileSlice(
                path=path,
                start=unit.slice_start,
                end=unit.slice_end,
                index=unit.slice_index,
                total=unit.slice_total,
            )
            if unit.slice_total > 1
            else path
        )
    prompt = (
        _extraction_system(deep=config.deep_mode)
        + _EXTRACTION_USER_INSTRUCTION
        + _read_files(units, source_root)
    ).encode("utf-8")
    return inventory, chunk, config, prompt


def audit_failed_attempt(root: Path) -> FailedAttemptAudit:
    """Classify the retained first launch without inferring an unrecorded phase."""
    outcome_path = root / "prototype-receipt.json"
    outcome_raw = outcome_path.read_bytes()
    if _sha(outcome_raw) != _ORIGINAL_OUTCOME_SHA256:
        raise ValueError("failed prototype outcome identity drifted")
    outcome = json.loads(outcome_raw)
    receipts = tuple(root.glob("*/chunks/0022/receipt.json"))
    metadata = tuple(root.glob("*/chunks/0022/adapter-metadata.json"))
    if len(receipts) != 1 or len(metadata) != 1:
        raise ValueError("failed prototype artifact census drifted")
    stage_raw = receipts[0].read_bytes()
    metadata_size = metadata[0].stat().st_size
    if (
        _sha(stage_raw) != _FAILED_STAGE_SHA256
        or metadata_size != 0
        or outcome.get("provider_calls") != 1
        or outcome.get("elapsed_ms") != _FAILED_ELAPSED_MS
        or outcome.get("status") != "failed"
    ):
        raise ValueError("failed prototype evidence drifted")
    return FailedAttemptAudit(
        schema_id="graphify-semantic-corpus-prototype-attempt-audit/v0",
        status="failed-phase-unknown",
        adapter_invocations=1,
        provider_inferences="unknown",
        failure_phase="unknown",
        original_outcome_sha256=_sha(outcome_raw),
        stage_receipt_sha256=_sha(stage_raw),
        adapter_metadata_size=metadata_size,
        elapsed_ms=_FAILED_ELAPSED_MS,
        reasons=(
            "adapter-process-environment-replaced-ambient",
            "adapter-metadata-unavailable",
            "provider-boundary-phase-not-retained",
        ),
    )


def write_failed_attempt_audit(root: Path) -> Path:
    """Append the correction without altering any retained attempt evidence."""
    destination = root / "failed-attempt-audit-v2.json"
    if destination.exists() or destination.is_symlink():
        raise ValueError("failed attempt audit already exists")
    raw = msgspec.json.encode(audit_failed_attempt(root), order="sorted") + b"\n"
    atomic.write_text(destination, raw.decode("utf-8"))
    return destination


def prototype_identity_reasons(plan: Path, launcher: Path) -> tuple[str, ...]:
    """Compare executable prototype files to independently planned identities."""
    config = msgspec.json.decode(
        (plan / "execution-config.json").read_bytes(),
        type=graphify_semantic_corpus.CorpusExecutionConfig,
        strict=True,
    )
    reasons: list[str] = []
    if (
        graphify_semantic_slice.sha256_file(launcher)
        != graphify_semantic_corpus_authority.PROTOTYPE_LAUNCHER_SHA256
    ):
        reasons.append("launcher-identity-mismatch")
    if (
        graphify_semantic_slice.sha256_file(Path(__file__))
        != graphify_semantic_corpus_authority.PROTOTYPE_CONTRACT_SHA256
    ):
        reasons.append("prototype-contract-identity-mismatch")
    adapter_path = Path(__file__).with_name("graphify_semantic_adapter.py")
    if graphify_semantic_slice.sha256_file(adapter_path) != config.adapter_sha256:
        reasons.append("adapter-identity-mismatch")
    return tuple(reasons)


def prepare_prototype_topology(output: Path, state_root: Path) -> Path:
    """Create marker state without pre-creating the atomic stage output root."""
    if ".." in output.parts or ".." in state_root.parts:
        raise ValueError("prototype topology refuses lexical parent traversal")
    if any(parent.is_symlink() for parent in (output.parent, *output.parent.parents)) or any(
        parent.is_symlink() for parent in (state_root.parent, *state_root.parent.parents)
    ):
        raise ValueError("prototype topology refuses a symlinked parent")
    canonical_output = output.resolve(strict=False)
    canonical_state = state_root.resolve(strict=False)
    if output.is_symlink() or canonical_output.exists():
        raise ValueError("prototype output already exists")
    if state_root.is_symlink() or canonical_state.exists():
        raise ValueError("prototype state already exists")
    if (
        canonical_output == canonical_state
        or canonical_output.parent != canonical_state.parent
        or canonical_output in canonical_state.parents
        or canonical_state in canonical_output.parents
    ):
        raise ValueError("prototype paths must be distinct canonical siblings")
    canonical_state.mkdir()
    return canonical_state / "provider-boundary-start.json"


def build_no_inference_preflight(
    repo_root: Path, plan: Path, launcher: Path
) -> PrototypePreflightReceipt:
    """Reverify the source, max chunk, and corrected adapter auth env without inference."""
    with (
        tempfile.TemporaryDirectory(prefix="kb301-prototype-preflight-source-") as source_dir,
        tempfile.TemporaryDirectory(prefix="kb301-prototype-preflight-adapter-") as adapter_dir,
        tempfile.TemporaryDirectory(prefix="kb301-prototype-preflight-metadata-") as metadata_dir,
    ):
        source_root = Path(source_dir) / "graphify"
        graphify_semantic_slice.admit_source(repo_root, source_root)
        verdict = graphify_semantic_corpus.verify_plan(plan, source_root)
        _inventory, chunk, config, prompt = _plan_inputs(plan, source_root)
        runtime = graphify_semantic_slice.preflight(repo_root)
        overlay = _adapter_overlay(
            runtime,
            Path(metadata_dir) / "adapter-metadata.json",
            Path(metadata_dir) / "provider-boundary-start.json",
            Path(adapter_dir),
        )
        adapter_environment = adapter_process_environment(os.environ, overlay)
        real_environment = graphify_semantic_slice.claude_child_environment(
            adapter_environment,
            original_path=adapter_environment["KB_SEMANTIC_ORIGINAL_PATH"],
        )
        executable = Path(adapter_environment["KB_SEMANTIC_REAL_CLAUDE"])
        auth_process = subprocess.run(
            [str(executable), "auth", "status"],
            capture_output=True,
            check=False,
            env=real_environment,
            timeout=30,
        )
        version_process = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            check=False,
            env=real_environment,
            timeout=30,
        )
        reasons: list[str] = []
        reasons.extend(prototype_identity_reasons(plan, launcher))
        if verdict.state != "complete" or not verdict.execution_authorized or verdict.reasons:
            reasons.append("plan-not-authorized")
        try:
            auth = graphify_semantic_slice.classify_auth(auth_process.stdout)
        except TypeError, ValueError:
            auth = runtime.auth
            reasons.append("corrected-environment-auth-failed")
        version = version_process.stdout.decode("utf-8", errors="replace").strip()
        if (
            auth_process.returncode
            or auth_process.stderr
            or version_process.returncode
            or version_process.stderr
            or not version.startswith(runtime.version)
        ):
            reasons.append("corrected-environment-runtime-failed")
        if _sha(prompt) != "4162fec1faa5fdf12f1e8149aa6dcb641b268799112e5e7a80cfd3781786d4d6":
            reasons.append("max-chunk-prompt-drifted")
        if (chunk.ordinal, chunk.total, chunk.estimated_tokens) != (22, 57, 19_985):
            reasons.append("max-chunk-identity-drifted")
        return PrototypePreflightReceipt(
            schema_id="graphify-semantic-corpus-prototype-preflight/v0",
            status="complete" if not reasons else "failed",
            provider_inferences=0,
            plan_manifest_sha256=graphify_semantic_slice.sha256_file(plan / "manifest.json"),
            execution_config_sha256=graphify_semantic_slice.sha256_file(
                plan / "execution-config.json"
            ),
            launcher_sha256=graphify_semantic_slice.sha256_file(launcher),
            adapter_sha256=graphify_semantic_slice.sha256_file(
                Path(__file__).with_name("graphify_semantic_adapter.py")
            ),
            prototype_contract_sha256=graphify_semantic_slice.sha256_file(Path(__file__)),
            chunk_ordinal=chunk.ordinal,
            chunk_total=chunk.total,
            estimated_tokens=chunk.estimated_tokens,
            prompt_sha256=_sha(prompt),
            prompt_size=len(prompt),
            model=config.claude_model,
            auth_method=auth.auth_method,
            api_provider=auth.api_provider,
            subscription_type=auth.subscription_type,
            claude_version=runtime.version,
            adapter_environment_names=tuple(sorted(adapter_environment)),
            reasons=tuple(dict.fromkeys(reasons)),
        )


def write_no_inference_preflight(
    repo_root: Path, plan: Path, launcher: Path, destination: Path
) -> Path:
    """Atomically retain a fresh no-inference receipt for independent review."""
    if destination.exists() or destination.is_symlink():
        raise ValueError("prototype preflight destination already exists")
    receipt = build_no_inference_preflight(repo_root, plan, launcher)
    raw = msgspec.json.encode(receipt, order="sorted") + b"\n"
    atomic.write_text(destination, raw.decode("utf-8"))
    return destination
