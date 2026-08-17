# Copyright (c) 2026 Raymond Manaloto
"""Immutable planning and fail-closed evidence for Graphify semantic coverage.

The planner is deterministic and makes no provider calls.  A future execution
lane may consume only a verified plan whose provisional source decisions and
runtime configuration have acquired an independent review authority.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from html.parser import HTMLParser
from pathlib import Path
from types import ModuleType

import graphify.llm as graphify_llm
import msgspec
from graphify.detect import detect
from graphify.llm import (
    FileSlice,
    _estimate_file_tokens,
    _extraction_system,
    _pack_chunks_by_tokens,
    _read_files,
    expand_oversized_files,
    read_slice_text,
    unit_path,
)

from kb_setup import (
    atomic,
    graphify_baseline,
    graphify_sdk,
    graphify_semantic_adapter,
    graphify_semantic_corpus_authority,
    graphify_semantic_slice,
)

_SCHEMA = "graphify-semantic-corpus-plan/v0"
_ABORT_SCHEMA = "graphify-semantic-corpus-abort/v0"
_FILE_CHAR_CAP = 20_000
_DEFAULT_TOKEN_BUDGET = 20_000
_INTENTIONAL_EXCLUSIONS = {
    "docs/demo-path.svg": (
        "regenerable-derived-visual",
        "scripts/gen_demo_path.py",
        ("scripts/gen_demo_path.py",),
    ),
    "docs/graph-hero.png": (
        "presentation-derived-screenshot",
        "README.md",
        ("README.md",),
    ),
    "docs/logo.png": (
        "presentation-branding-asset",
        "README.md",
        ("README.md",),
    ),
    "worked/rsl-siege-manager/graph.html": (
        "generated-graph-visualization-duplicate",
        "worked/rsl-siege-manager/graph.json",
        ("worked/rsl-siege-manager/graph.json",),
    ),
}
_PLAN_MEMBERS = (
    "source-inventory.json",
    "advisories.json",
    "exclusions.json",
    "chunk-ledger.json",
    "execution-config.json",
)
_MAX_ARGS = 2
_EXECUTION_MODE_COUNT = 4
_SHA256_LENGTH = 64
_GIT_OBJECT_LENGTH = 40
_ACCEPTED_GRAPHIFY_REF = "v0.9.45"
_ACCEPTED_GRAPHIFY_COMMIT = "0738af373af9cf5c95f862cc5f3327fd96b4ea23"
_ACCEPTED_GRAPHIFY_TREE = "e0e089a404dd0b9f6d01273b869c80197c0cc03c"
# The digest of the baseline's GENERATED `source-manifest.json` member, not of
# `sources/graphify.manifest`. Worth stating: the two are both "the source
# manifest" in English, the committed file is the obvious reading, and it is the
# wrong one — this value is re-derived by `graphify-baseline build` and read from
# its candidate, which is what makes it a measurement rather than a guess that
# happens to be 64 hex characters.
_ACCEPTED_BASELINE_SOURCE_MANIFEST_SHA256 = (
    "980fab12cee6348416b2962121f42a3c66a97277ac9e89855abb9d6fe4856911"
)
# `graphify/detect.py`'s git blob at the pinned commit. Control-armed before it
# was trusted: the same derivation at v0.9.43 reproduces the c51ea916 this line
# used to hold, so the method is right and the new value is not a guess.
#
# UNCHANGED at v0.9.45, and that is a measurement with two independent routes
# agreeing: the blob API at the 0.9.45 commit returns this same f76a4259…, and
# `graphify/detect.py` does not appear in `compare/v0.9.44...v0.9.45` at all. The
# tree digest above moved in the same derivation, which is what proves the probe
# can return a different value rather than echoing its input.
_ACCEPTED_GRAPHIFY_DETECT_OBJECT = "f76a4259f6a7360872663fbe711c4738ecda4680"
_ACCEPTED_GRAPHIFY_RUNTIME = graphify_baseline.RuntimeIdentity(
    version="0.9.45",
    cli_version="0.9.45",
    sdk_version="0.9.45",
    executable=".venv/bin/graphify",
    # Unchanged, and MEASURED rather than carried forward — see
    # `graphify_semantic_slice._CURRENT_GRAPHIFY_RUNTIME` for the re-derivation.
    sdk_fingerprint_sha256="b10406f90fe7c369fc1396991679f6e4490e59f9351332c30b9fe2216f071157",
    wheel_sha256="134250477dbcf2e465b5794b7f09c38dcbe0006b1284718beb962bd704865663",
    sdist_sha256="ba27f7b797fc3b8c21c46e5e7bd75d8f9136582e38af98eedee0cebb339fd1e7",
)
_PROFILE = graphify_semantic_slice.CORPUS_PROFILE
_CORPUS_WORD_UPPER = 500_000
_CORPUS_FILE_UPPER = 500
# Kept in step with `graphify_semantic_slice._ACCEPTED_CLAUDE_*`, which carries
# the reasoning: the `--help` digest is unchanged across 2.1.232 -> 2.1.233, so
# only the binary moved and the pinned flag contract did not.
_CLAUDE_VERSION = "2.1.233"
_CLAUDE_EXECUTABLE_SHA256 = "bc466b6cde63edafc773f471a1fb98787fabb31f52240c8616ce7e1f587b212d"
_CLAUDE_HELP_SHA256 = "71ad650f59e08ae40ede14c534db4f49d8590ee5a4f92f6da2882d3a5560fea6"
_CLAUDE_REQUIRED_FLAGS = (
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
    "--max-turns",
    # Appended in the same order `preflight` appends it, because
    # `_provider_runtime_reasons` compares this tuple to the receipt's
    # `required_flags` for EQUALITY, not membership. The corpus profile passes
    # `--effort`, so the preflight proves it, so it lands in the receipt — and a
    # config that omitted it would fail every real run as a capability-flag
    # mismatch, which reads like a missing CLI feature rather than a stale list.
    "--effort",
)
_EXTRACTION_USER_INSTRUCTION = (
    "\n\n---\n"
    "Now extract the knowledge graph from the following source file(s) "
    "and output ONLY the JSON object described above. No prose, no "
    "preamble, no markdown fences.\n\n"
)
PLAN_MEMBER_NAMES = _PLAN_MEMBERS


class SourcePin(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Immutable Git identity of the planned source tree."""

    ref: str
    commit: str
    tree: str


def admit_source(repo_root: Path, destination: Path) -> SourcePin:
    """Materialize the current #301 Graphify pin without reusing #300's old source."""
    from kb_setup import graph
    from kb_setup import manifest as source_manifests

    source_manifest = source_manifests.load(repo_root / "sources/graphify.manifest")
    provenance = graph.materialize_source_snapshot(source_manifest, destination)
    observed = (
        source_manifest.ref,
        provenance.resolved_commit,
        provenance.tree_digest,
    )
    expected = (
        _ACCEPTED_GRAPHIFY_REF,
        _ACCEPTED_GRAPHIFY_COMMIT,
        _ACCEPTED_GRAPHIFY_TREE,
    )
    if observed != expected:
        raise ValueError("Graphify semantic corpus source identity drifted")
    return SourcePin(ref=observed[0], commit=observed[1], tree=observed[2])


class SourceUnit(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """One exact semantic unit after Graphify's own 20k expansion."""

    ordinal: int
    kind: str
    path: str
    parent_sha256: str
    source_git_object: str
    parent_size: int
    slice_start: int
    slice_end: int
    slice_index: int
    slice_total: int
    sha256: str
    estimated_tokens: int


class SourceInventory(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Complete detected semantic inventory before reviewed dispositions."""

    source_ref: str
    source_commit: str
    source_tree: str
    source_manifest_sha256: str
    detected_source_count: int
    discovered_unit_count: int
    admitted_unit_count: int
    units: tuple[SourceUnit, ...]
    warnings: tuple[str, ...]
    schema_version: int = 1


class CorpusAdvisory(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """One retained operational notice which is never silently discarded."""

    code: str
    message: str
    detector_git_object: str
    observed_files: int
    observed_words: int
    file_count_threshold: int
    word_count_threshold: int
    review_status: str = "provisional"


class AdvisoryCatalog(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Content-addressed operational notices awaiting independent review."""

    source_commit: str
    source_tree: str
    entries: tuple[CorpusAdvisory, ...]
    schema_version: int = 1


class IntentionalExclusion(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Content-bound omission proposal backed by deterministic source evidence."""

    path: str
    exclusion_class: str
    sha256: str
    size: int
    semantic_authority_path: str
    evidence_paths: tuple[str, ...]
    evidence_git_objects: tuple[str, ...]
    evidence_sha256: str
    review_status: str = "provisional"


class ExclusionCatalog(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Exact unresolved source decisions for independent review."""

    source_commit: str
    source_tree: str
    entries: tuple[IntentionalExclusion, ...]
    schema_version: int = 1


class ChunkMember(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """One source unit assigned to exactly one planned provider call."""

    unit_ordinal: int
    path: str
    slice_index: int
    sha256: str
    estimated_tokens: int


class PlannedChunk(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Deterministic, ordered unit packing for one future call."""

    ordinal: int
    total: int
    estimated_tokens: int
    members: tuple[ChunkMember, ...]


class ChunkLedger(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Complete no-duplication/no-omission execution ledger."""

    token_budget: int
    unit_count: int
    chunks: tuple[PlannedChunk, ...]
    schema_version: int = 1


class CorpusExecutionConfig(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """All non-secret controls that key a future semantic cache namespace."""

    graphify_ref: str
    graphify_commit: str
    graphify_tree: str
    graphify_version: str
    graphify_runtime: graphify_baseline.RuntimeIdentity
    graphify_semantic_fingerprint_sha256: str
    graphify_llm_sha256: str
    planner_sha256: str
    adapter_sha256: str
    semantic_slice_sha256: str
    # The module that actually makes the calls. Bound here for the same reason as
    # the three above, and it was the one missing: an authorization is a review of
    # what a run WILL DO, and every other participant in that run was pinned while
    # the driver could be rewritten under a still-valid authority.
    runner_sha256: str
    prompt_contract_sha256: str
    structured_schema_sha256: str
    claude_version: str
    claude_executable_sha256: str
    claude_help_sha256: str
    claude_required_flags: tuple[str, ...]
    claude_model: str
    claude_canonical_model: str
    resolved_model: str
    backend: str
    auth_route: str
    endpoint_policy: str
    tools: tuple[str, ...]
    token_budget: int
    file_char_cap: int
    timeout_seconds: int
    claude_max_output_tokens: int
    claude_max_retries: int
    structured_output_retries: int
    max_turns: int
    max_cost_usd: float
    graphify_max_retry_depth: int
    graphify_chunk_size: int
    graphify_no_incremental_cache: bool
    concurrency: int
    deep_mode: bool
    cache_policy: str
    source_inventory_sha256: str
    exclusions_sha256: str
    chunk_ledger_sha256: str
    cache_namespace_sha256: str
    schema_version: int = 1


class ArtifactMember(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """One independently rehashed regular plan member."""

    name: str
    sha256: str
    size: int


class PlanManifest(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Public trust boundary for a staged semantic corpus plan."""

    schema_id: str
    source_commit: str
    source_tree: str
    members: tuple[ArtifactMember, ...]
    warnings: tuple[str, ...]


class PlanVerification(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Read-only typed plan verdict."""

    state: str
    structural_complete: bool
    execution_authorized: bool
    reasons: tuple[str, ...]


class AuthorityRoots(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Review-owned roots kept outside the implementation hashed by the plan."""

    plan_manifest_sha256: str
    execution_config_sha256: str
    advisories_sha256: str
    exclusions_sha256: str
    schema_version: int = 1


class AbortReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Durable proof that a refused run made no provider calls."""

    schema_id: str
    status: str
    provider_calls: int
    reasons: tuple[str, ...]


class ChunkStageReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Content binding for one atomically published semantic fragment."""

    status: str
    cache_namespace_sha256: str
    run_namespace_sha256: str
    chunk_ordinal: int
    chunk_total: int
    chunk_sha256: str
    plan_manifest_sha256: str
    execution_config_sha256: str
    prompt_contract_sha256: str
    structured_schema_sha256: str
    provider_prompt_sha256: str
    source_paths: tuple[str, ...]
    fragment_sha256: str
    fragment_size: int
    provider_receipt_sha256: str
    provider_receipt_size: int
    adapter_metadata_sha256: str
    adapter_metadata_size: int
    node_count: int
    edge_count: int
    hyperedge_count: int
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    reasons: tuple[str, ...]
    schema_version: int = 1


class ChunkStageVerification(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Read-only verdict for one staged chunk directory."""

    state: str
    reasons: tuple[str, ...]


class RetainedProviderEvidence(msgspec.Struct, frozen=True):
    """Exact provider and adapter bytes retained without normalization."""

    receipt_raw: bytes
    adapter_metadata_raw: bytes


class ChunkStageRequest(msgspec.Struct, frozen=True):
    """Exact plan chunk and retained provider bytes requested for staging."""

    source_root: Path
    cache_namespace: str
    run_namespace: str
    chunk: PlannedChunk
    fragment: object
    provider_evidence: RetainedProviderEvidence


class ChunkStageReference(msgspec.Struct, frozen=True):
    """Exact plan/source/cache/run identity for read-only stage verification."""

    candidate: Path
    source_root: Path
    cache_namespace: str
    run_namespace: str
    chunk: PlannedChunk


class _ProviderValidationContext(msgspec.Struct, frozen=True):
    evidence: RetainedProviderEvidence
    fragment_raw: bytes
    source_paths: tuple[str, ...]
    chunk: PlannedChunk
    counts: tuple[int, int, int]
    inventory: SourceInventory
    config: CorpusExecutionConfig
    source_root: Path


class RunEvidence(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Comparable public evidence for cold, reuse, rebuild, or variance runs."""

    mode: str
    plan_manifest_sha256: str
    execution_config_sha256: str
    exclusions_sha256: str
    source_inventory_sha256: str
    chunk_ledger_sha256: str
    source_commit: str
    source_tree: str
    cache_namespace_sha256: str
    run_namespace_sha256: str
    chunk_count: int
    completed_chunks: int
    provider_calls: int
    failed_chunks: int
    uncovered_units: int
    fragment_ledger_sha256: str
    graph_sha256: str
    covered_units: int
    semantic_node_count: int
    semantic_edge_count: int
    semantic_hyperedge_count: int
    graph_node_count: int
    graph_edge_count: int
    graph_hyperedge_count: int
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    schema_version: int = 1


class RunFragmentMember(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Exact staged evidence and plan coverage for one run chunk."""

    chunk_ordinal: int
    chunk_sha256: str
    unit_ordinals: tuple[int, ...]
    source_paths: tuple[str, ...]
    stage_receipt_sha256: str
    provider_receipt_sha256: str
    adapter_metadata_sha256: str
    fragment_sha256: str
    node_count: int
    edge_count: int
    hyperedge_count: int


class RunFragmentLedger(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Ordered content-addressed index of every staged real-provider chunk."""

    cache_namespace_sha256: str
    run_namespace_sha256: str
    members: tuple[RunFragmentMember, ...]
    schema_version: int = 1


class ExecutionModeVerification(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Typed parity/variance verdict across all required execution modes."""

    state: str
    reasons: tuple[str, ...]


class ExecutionRunSet(msgspec.Struct, frozen=True):
    """Exact artifact roots for the four required execution modes."""

    cold: object
    reuse: object
    rebuild: object
    variance: object


def _encode(value: object) -> bytes:
    return msgspec.json.encode(value, order="sorted") + b"\n"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha_file(path: Path) -> str:
    return graphify_semantic_slice.sha256_file(path)


def _valid_sha(value: str) -> bool:
    return len(value) == _SHA256_LENGTH and all(char in "0123456789abcdef" for char in value)


def _fragment_counts(fragment: object) -> tuple[int, int, int]:
    if not isinstance(fragment, dict):
        raise TypeError("semantic fragment is not an object")
    counts: list[int] = []
    for name in ("nodes", "edges", "hyperedges"):
        records = fragment.get(name)
        if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
            raise TypeError(f"semantic fragment {name} are invalid")
        counts.append(len(records))
    if counts[0] == 0:
        raise ValueError("semantic fragment has zero nodes")
    return counts[0], counts[1], counts[2]


def _write(path: Path, value: object) -> bytes:
    raw = _encode(value)
    atomic.write_text(path, raw.decode("utf-8"))
    return raw


def _module_sha(module: ModuleType) -> str:
    source = inspect.getsourcefile(module)
    if source is None:
        raise ValueError("effective semantic module has no source identity")
    return _sha_file(Path(source))


def _config_without_namespace(config: CorpusExecutionConfig) -> dict[str, object]:
    payload = msgspec.to_builtins(config)
    if not isinstance(payload, dict):
        raise TypeError("semantic execution config is not an object")
    payload.pop("cache_namespace_sha256", None)
    return payload


def cache_namespace_for(config: CorpusExecutionConfig | dict[str, object]) -> str:
    """Return the exact namespace for every effective non-secret control."""
    typed = (
        config
        if isinstance(config, CorpusExecutionConfig)
        else msgspec.convert(config, type=CorpusExecutionConfig, strict=True)
    )
    return _sha(msgspec.json.encode(_config_without_namespace(typed), order="sorted"))


def _effective_config(
    source: SourcePin,
    *,
    token_budget: int,
    inventory_sha256: str,
    exclusions_sha256: str,
    ledger_sha256: str,
) -> CorpusExecutionConfig:
    semantic_fingerprint = _sha(
        graphify_semantic_slice.encode_json(graphify_sdk.semantic_api_fingerprint())
    )
    graphify_llm_sha = _module_sha(graphify_llm)
    prompt_contract_sha = _sha(
        (_extraction_system(deep=True) + _EXTRACTION_USER_INSTRUCTION).encode("utf-8")
    )
    provisional = CorpusExecutionConfig(
        graphify_ref=source.ref,
        graphify_commit=source.commit,
        graphify_tree=source.tree,
        # Read from the runtime identity rather than spelled again: this literal
        # said "0.9.43" while `_ACCEPTED_GRAPHIFY_RUNTIME` next to it said 0.9.44,
        # so every plan written since the pin bump recorded two different versions
        # for one run. A version that is transcribed can disagree with the version
        # that ran; a version that is READ cannot.
        graphify_version=_ACCEPTED_GRAPHIFY_RUNTIME.version,
        graphify_runtime=_ACCEPTED_GRAPHIFY_RUNTIME,
        graphify_semantic_fingerprint_sha256=semantic_fingerprint,
        graphify_llm_sha256=graphify_llm_sha,
        planner_sha256=_sha_file(Path(__file__)),
        adapter_sha256=_module_sha(graphify_semantic_adapter),
        semantic_slice_sha256=_module_sha(graphify_semantic_slice),
        # Imported here rather than at module scope: the driver imports THIS
        # module, so a top-level import would be circular.
        runner_sha256=_sha_file(Path(__file__).with_name("graphify_semantic_corpus_run.py")),
        prompt_contract_sha256=prompt_contract_sha,
        structured_schema_sha256=graphify_semantic_slice.GRAPHIFY_SCHEMA_SHA256,
        claude_version=_CLAUDE_VERSION,
        claude_executable_sha256=_CLAUDE_EXECUTABLE_SHA256,
        claude_help_sha256=_CLAUDE_HELP_SHA256,
        claude_required_flags=_CLAUDE_REQUIRED_FLAGS,
        claude_model=_PROFILE.model,
        claude_canonical_model=_PROFILE.canonical_model,
        resolved_model=_PROFILE.canonical_model,
        backend="claude-cli",
        auth_route="claude.ai:firstParty:max",
        endpoint_policy="subscription-default-no-api-endpoint",
        tools=(),
        token_budget=token_budget,
        file_char_cap=_FILE_CHAR_CAP,
        timeout_seconds=120,
        claude_max_output_tokens=int(_PROFILE.max_output_tokens),
        claude_max_retries=int(_PROFILE.max_retries),
        structured_output_retries=1,
        max_turns=int(_PROFILE.max_turns),
        max_cost_usd=_PROFILE.max_cost_usd,
        # 0 -> 2 alongside `claude_max_retries`: one blip over 57 chunks is likely
        # rather than hypothetical, and a lost chunk is a hole in the corpus that
        # nothing downstream reports as missing.
        graphify_max_retry_depth=2,
        graphify_chunk_size=20,
        # False, which leaves graphify's per-chunk checkpoint WRITES enabled.
        #
        # It was justified here as buying a discount — "a resumed or repeated run
        # pays only for the chunks it has not already extracted" — and that was
        # never true on this path. An AST walk of the pinned 0.9.45 finds no cache
        # read anywhere in `extract_corpus_parallel`'s call chain
        # (`_run_one` -> `_extract_with_adaptive_retry` -> `extract_files_direct`);
        # `load_cached` is reached only from `graphify/extract.py`, which this
        # driver never calls. The probe discriminates: the same walk does find
        # `_checkpoint_chunk`, the writer, on this path.
        #
        # So a re-run re-buys the whole corpus regardless of this flag, and the
        # value it does buy is durable checkpoints for anything that reads the
        # cache by another route. Kept False for that, and because a cold policy
        # would discard the checkpoints too. Budget an interrupted run at full
        # price; the driver's `repaid` count is the measurement of that.
        graphify_no_incremental_cache=False,
        # 1, and it is a MEASUREMENT of what the extractor will do rather than a
        # preference (Ray, 2026-08-16, after the constraint was surfaced).
        # `graphify/llm.py` force-serializes this backend —
        # `if backend == "claude-cli" and GRAPHIFY_CLAUDE_CLI_PARALLEL != "1":
        # max_concurrency = 1` — because parallel Claude subprocesses conflict
        # over session state. Recording 4 here would have made the plan assert a
        # concurrency no run could exhibit, and `_provider_config_reasons`
        # compares this field against the receipt, so it would have failed as a
        # provider mismatch pointing at the wrong thing.
        #
        # The override is deliberately NOT taken: the adapter writes its metadata
        # and its O_EXCL boundary marker to single fixed paths, so concurrent
        # chunks in one process collide on both regardless of what graphify allows.
        concurrency=1,
        deep_mode=True,
        # "checkpoint-write", not "warm-read-atomic-per-chunk". The old value
        # asserted a cache READ this path never performs, and it is the same
        # falsehood as the `graphify_no_incremental_cache` comment above —
        # corrected there in prose while this, the MACHINE-READABLE field, kept
        # saying it. A reader who checks the config rather than the comment gets
        # the wrong answer, which is the worse of the two places to leave it.
        cache_policy="checkpoint-write-atomic-per-chunk",
        source_inventory_sha256=inventory_sha256,
        exclusions_sha256=exclusions_sha256,
        chunk_ledger_sha256=ledger_sha256,
        cache_namespace_sha256="",
    )
    return msgspec.structs.replace(
        provisional, cache_namespace_sha256=cache_namespace_for(provisional)
    )


def _relative(source_root: Path, path: Path) -> str:
    return path.resolve().relative_to(source_root.resolve()).as_posix()


def _unit_bytes(unit: Path | FileSlice) -> bytes:
    if isinstance(unit, FileSlice):
        return read_slice_text(unit).encode("utf-8")
    return unit.read_bytes()


def _semantic_files(
    source_root: Path, *, source_commit: str
) -> tuple[dict[str, str], tuple[str, ...], tuple[CorpusAdvisory, ...]]:
    observed = detect(source_root)
    files = observed.get("files", {})
    if not isinstance(files, dict):
        raise TypeError("Graphify detection did not return typed file groups")
    typed: dict[str, str] = {}
    for kind in ("document", "paper", "image"):
        paths = files.get(kind, [])
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            raise ValueError(f"Graphify detection returned invalid {kind} paths")
        for raw in paths:
            relative = _relative(source_root, Path(raw))
            if relative in typed:
                raise ValueError(f"Graphify detected a duplicate semantic path: {relative}")
            typed[relative] = kind
    warning = observed.get("warning")
    walk_errors = tuple(str(value) for value in observed.get("walk_errors", []) if value)
    advisories: tuple[CorpusAdvisory, ...] = ()
    detector_object = ""
    if source_commit == _ACCEPTED_GRAPHIFY_COMMIT:
        try:
            detector_object = _git(source_root, "rev-parse", f"{source_commit}:graphify/detect.py")
        except OSError, ValueError:
            detector_object = ""
    observed_files = observed.get("total_files")
    observed_words = observed.get("total_words")
    expected_cost_message = (
        f"Large corpus: {observed_files} files · ~{observed_words:,} words. "
        "Semantic extraction will be expensive (many Claude tokens). "
        "Consider running on a subfolder."
        if isinstance(observed_files, int) and isinstance(observed_words, int)
        else ""
    )
    if (
        warning == expected_cost_message
        and source_commit == _ACCEPTED_GRAPHIFY_COMMIT
        and detector_object == _ACCEPTED_GRAPHIFY_DETECT_OBJECT
        and isinstance(observed_files, int)
        and isinstance(observed_words, int)
        and (observed_files >= _CORPUS_FILE_UPPER or observed_words >= _CORPUS_WORD_UPPER)
    ):
        advisories = (
            CorpusAdvisory(
                code="graphify-large-corpus-token-cost",
                message=warning,
                detector_git_object=detector_object,
                observed_files=observed_files,
                observed_words=observed_words,
                file_count_threshold=_CORPUS_FILE_UPPER,
                word_count_threshold=_CORPUS_WORD_UPPER,
            ),
        )
        warning = None
    warnings = tuple(str(value) for value in (warning, *walk_errors) if value)
    if observed.get("skipped_sensitive"):
        raise ValueError("Graphify detection skipped sensitive inputs")
    return typed, warnings, advisories


def _svg_evidence(source_root: Path, source_sha256: str) -> dict[str, object]:
    generator = source_root / "scripts/gen_demo_path.py"
    with tempfile.TemporaryDirectory(prefix="kb-graphify-svg-proof-") as raw_stage:
        stage = Path(raw_stage)
        (stage / "docs").mkdir()
        env = dict(os.environ)
        env.pop("STATIC", None)
        completed = subprocess.run(
            [sys.executable, str(generator)],
            cwd=stage,
            capture_output=True,
            check=False,
            env=env,
            text=True,
            timeout=30,
        )
        generated = stage / "docs/demo-path.svg"
        if completed.returncode != 0 or not generated.is_file():
            raise ValueError("svg-evidence-regeneration-failed")
        generated_sha = _sha_file(generated)
    if generated_sha != source_sha256:
        raise ValueError("svg-evidence-byte-mismatch")
    return {
        "evidence_kind": "byte-identical-svg-regeneration",
        "generated_sha256": generated_sha,
        "generator_sha256": _sha_file(generator),
        "source_sha256": source_sha256,
    }


def _html_graph_evidence(source_root: Path, source_sha256: str) -> dict[str, object]:
    html = (source_root / "worked/rsl-siege-manager/graph.html").read_text(encoding="utf-8")
    graph_path = source_root / "worked/rsl-siege-manager/graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    def embedded(name: str) -> list[dict[str, object]]:
        match = re.search(rf"const {name} = (\[.*?\]);", html, re.DOTALL)
        if match is None:
            raise ValueError(f"html-evidence-missing:{name}")
        value = json.loads(match.group(1))
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ValueError(f"html-evidence-invalid:{name}")
        return value

    html_nodes = embedded("RAW_NODES")
    html_edges = embedded("RAW_EDGES")
    graph_nodes = graph.get("nodes", [])
    graph_links = graph.get("links", [])
    nodes = [
        (
            str(item.get("id", "")),
            str(item.get("label", "")),
            str(item.get("community", "")),
            str(item.get("source_file", "")),
            str(item.get("file_type", "")),
        )
        for item in graph_nodes
    ]
    html_nodes_normalized = [
        (
            str(item.get("id", "")),
            str(item.get("label", "")),
            str(item.get("community", "")),
            str(item.get("source_file", "")),
            str(item.get("file_type", "")),
        )
        for item in html_nodes
    ]
    links = [
        (
            str(item.get("source", "")),
            str(item.get("target", "")),
            str(item.get("relation", "")),
            str(item.get("confidence", "EXTRACTED")),
        )
        for item in graph_links
    ]
    html_links = [
        (
            str(item.get("from", "")),
            str(item.get("to", "")),
            str(item.get("label", "")),
            str(item.get("confidence", "EXTRACTED")),
        )
        for item in html_edges
    ]
    graph_node_ids = [node[0] for node in nodes]
    html_node_ids = [node[0] for node in html_nodes_normalized]
    if len(graph_node_ids) != len(set(graph_node_ids)) or len(html_node_ids) != len(
        set(html_node_ids)
    ):
        raise ValueError("html-evidence-duplicate-node-id")
    if len(links) != len(set(links)) or len(html_links) != len(set(html_links)):
        raise ValueError("html-evidence-duplicate-edge")
    if html_nodes_normalized != nodes or html_links != links:
        raise ValueError("html-evidence-graph-mismatch")
    return {
        "edge_count": len(links),
        "edge_identity_sha256": _sha(_encode(links)),
        "evidence_kind": "html-graph-semantic-reconciliation",
        "graph_sha256": _sha_file(graph_path),
        "node_count": len(nodes),
        "node_identity_sha256": _sha(_encode(nodes)),
        "source_sha256": source_sha256,
    }


class _ReadmeEvidenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[tuple[tuple[str, str], ...], str]] = []
        self._images: list[tuple[str, str]] | None = None
        self._em_depth = 0
        self._caption: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self._images = []
            self._caption = []
        elif tag == "img" and self._images is not None:
            values = dict(attrs)
            self._images.append((values.get("src") or "", values.get("alt") or ""))
        elif tag == "em" and self._images is not None:
            self._em_depth += 1

    def handle_data(self, data: str) -> None:
        if self._images is not None and self._em_depth:
            self._caption.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "em" and self._em_depth:
            self._em_depth -= 1
        elif tag == "p" and self._images is not None:
            self.blocks.append((tuple(self._images), "".join(self._caption).strip()))
            self._images = None
            self._caption = []
            self._em_depth = 0


def _png_readme_evidence(source_root: Path, path: str, source_sha256: str) -> dict[str, object]:
    readme = source_root / "README.md"
    expected = {
        "docs/logo.png": (
            "https://raw.githubusercontent.com/Graphify-Labs/graphify/v8/docs/logo.png",
            "Graphify",
            "",
        ),
        "docs/graph-hero.png": (
            "https://raw.githubusercontent.com/Graphify-Labs/graphify/v8/docs/graph-hero.png",
            (
                "graphify's interactive graph.html showing the FastAPI codebase as a "
                "force-directed knowledge graph with a legend of detected communities"
            ),
            (
                "The FastAPI codebase mapped by graphify. Every node is a concept, colors are "
                "detected communities, and the whole thing is clickable in graph.html."
            ),
        ),
    }[path]
    parser = _ReadmeEvidenceParser()
    parser.feed(readme.read_text(encoding="utf-8"))
    matching = [
        index
        for index, (images, _caption) in enumerate(parser.blocks)
        if any(src == expected[0] for src, _alt in images)
    ]
    valid = len(matching) == 1
    if valid:
        index = matching[0]
        images, _caption = parser.blocks[index]
        valid = (
            images.count((expected[0], expected[1])) == 1
            and sum(src == expected[0] for src, _alt in images) == 1
        )
        if expected[2]:
            valid = (
                valid
                and index + 1 < len(parser.blocks)
                and parser.blocks[index + 1] == ((), expected[2])
            )
    if not valid:
        raise ValueError(f"png-evidence-readme-mismatch:{path}")
    return {
        "caption": expected[2],
        "evidence_kind": "readme-presentation-binding",
        "image_alt": expected[1],
        "image_src": expected[0],
        "readme_sha256": _sha_file(readme),
        "required_text_sha256": _sha(_encode(expected)),
        "source_sha256": source_sha256,
    }


def _intentional_exclusion(
    source_root: Path,
    path: str,
    *,
    sha256: str,
    size: int,
    members: Mapping[str, object],
) -> IntentionalExclusion:
    exclusion_class, authority_path, evidence_paths = _INTENTIONAL_EXCLUSIONS[path]
    if path == "docs/demo-path.svg":
        evidence = _svg_evidence(source_root, sha256)
    elif path == "worked/rsl-siege-manager/graph.html":
        evidence = _html_graph_evidence(source_root, sha256)
    else:
        evidence = _png_readme_evidence(source_root, path, sha256)
    evidence_objects: list[str] = []
    for evidence_path in evidence_paths:
        member = members.get(evidence_path)
        git_object = getattr(member, "git_object", "")
        if len(git_object) != _GIT_OBJECT_LENGTH:
            raise ValueError(f"exclusion-evidence-absent:{evidence_path}")
        evidence_objects.append(git_object)
    return IntentionalExclusion(
        path=path,
        exclusion_class=exclusion_class,
        sha256=sha256,
        size=size,
        semantic_authority_path=authority_path,
        evidence_paths=evidence_paths,
        evidence_git_objects=tuple(evidence_objects),
        evidence_sha256=_sha(_encode(evidence)),
    )


def _inventory(
    source_root: Path,
    *,
    source_ref: str,
    source_commit: str,
    source_tree: str,
) -> tuple[SourceInventory, AdvisoryCatalog, ExclusionCatalog, list[Path | FileSlice]]:
    manifest = graphify_baseline.source_manifest(
        source_root, commit=source_commit, tree=source_tree
    )
    # Match the exact candidate-member encoding certified by landed issue #299.
    # The underlying manifest is already Git path ordered; preserving its typed
    # field order and trailing newline makes this digest directly reusable.
    manifest_raw = msgspec.json.encode(manifest) + b"\n"
    kinds, warnings, advisories = _semantic_files(source_root, source_commit=source_commit)
    paths = [source_root / relative for relative in sorted(kinds)]
    expanded = expand_oversized_files(paths, _FILE_CHAR_CAP)
    exclusions: list[IntentionalExclusion] = []
    admitted: list[Path | FileSlice] = []
    units: list[SourceUnit] = []
    members = {member.path: member for member in manifest.members}
    for unit in expanded:
        parent = unit_path(unit)
        relative = _relative(source_root, parent)
        member = members.get(relative)
        if member is None:
            raise ValueError(f"semantic source is absent from Git inventory: {relative}")
        if relative in _INTENTIONAL_EXCLUSIONS:
            if not any(entry.path == relative for entry in exclusions):
                exclusions.append(
                    _intentional_exclusion(
                        source_root,
                        relative,
                        sha256=member.sha256,
                        size=member.size,
                        members=members,
                    )
                )
            continue
        admitted.append(unit)
        raw = _unit_bytes(unit)
        if isinstance(unit, FileSlice):
            start, end, index, total = unit.start, unit.end, unit.index, unit.total
        else:
            start, end, index, total = 0, len(raw), 0, 1
        units.append(
            SourceUnit(
                ordinal=len(units) + 1,
                kind=kinds[relative],
                path=relative,
                parent_sha256=member.sha256,
                source_git_object=member.git_object,
                parent_size=member.size,
                slice_start=start,
                slice_end=end,
                slice_index=index,
                slice_total=total,
                sha256=_sha(raw),
                estimated_tokens=_estimate_file_tokens(unit),
            )
        )
    return (
        SourceInventory(
            source_ref=source_ref,
            source_commit=source_commit,
            source_tree=source_tree,
            source_manifest_sha256=_sha(manifest_raw),
            detected_source_count=len(kinds),
            discovered_unit_count=len(expanded),
            admitted_unit_count=len(units),
            units=tuple(units),
            warnings=warnings,
        ),
        AdvisoryCatalog(
            source_commit=source_commit,
            source_tree=source_tree,
            entries=advisories,
        ),
        ExclusionCatalog(
            source_commit=source_commit,
            source_tree=source_tree,
            entries=tuple(sorted(exclusions, key=lambda entry: entry.path)),
        ),
        admitted,
    )


def _ledger(
    source_root: Path,
    units: tuple[SourceUnit, ...],
    expanded: list[Path | FileSlice],
    budget: int,
) -> ChunkLedger:
    by_identity = {(unit.path, unit.slice_index): unit for unit in units}
    packed = _pack_chunks_by_tokens(expanded, budget)
    chunks: list[PlannedChunk] = []
    seen: set[int] = set()
    for ordinal, chunk in enumerate(packed, start=1):
        members: list[ChunkMember] = []
        for item in chunk:
            relative = _relative(source_root, unit_path(item))
            identity = (relative, item.index if isinstance(item, FileSlice) else 0)
            source = by_identity.get(identity)
            if source is None:
                raise ValueError(f"planned unit identity is unavailable: {relative}")
            if source.ordinal in seen:
                raise ValueError(f"planned unit is duplicated: {source.ordinal}")
            seen.add(source.ordinal)
            members.append(
                ChunkMember(
                    unit_ordinal=source.ordinal,
                    path=source.path,
                    slice_index=source.slice_index,
                    sha256=source.sha256,
                    estimated_tokens=source.estimated_tokens,
                )
            )
        chunks.append(
            PlannedChunk(
                ordinal=ordinal,
                total=len(packed),
                estimated_tokens=sum(member.estimated_tokens for member in members),
                members=tuple(members),
            )
        )
    if seen != {unit.ordinal for unit in units}:
        raise ValueError("chunk ledger omitted admitted semantic units")
    return ChunkLedger(token_budget=budget, unit_count=len(units), chunks=tuple(chunks))


def plan_source(
    source_root: Path,
    output: Path,
    *,
    source: SourcePin,
    token_budget: int = _DEFAULT_TOKEN_BUDGET,
) -> PlanManifest:
    """Atomically publish a deterministic, provider-free plan for one Git tree."""
    if output.exists():
        raise ValueError(f"semantic corpus plan already exists: {output}")
    if source.commit != _git(source_root, "rev-parse", "HEAD"):
        raise ValueError("source commit does not match materialized HEAD")
    if source.tree != _git(source_root, "rev-parse", "HEAD^{tree}"):
        raise ValueError("source tree does not match materialized HEAD")
    before = graphify_baseline.source_manifest(source_root, commit=source.commit, tree=source.tree)
    inventory, advisories, exclusions, admitted = _inventory(
        source_root,
        source_ref=source.ref,
        source_commit=source.commit,
        source_tree=source.tree,
    )
    ledger = _ledger(source_root, inventory.units, admitted, token_budget)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as raw_stage:
        stage = Path(raw_stage)
        inventory_raw = _write(stage / _PLAN_MEMBERS[0], inventory)
        _write(stage / _PLAN_MEMBERS[1], advisories)
        exclusions_raw = _write(stage / _PLAN_MEMBERS[2], exclusions)
        ledger_raw = _write(stage / _PLAN_MEMBERS[3], ledger)
        config = _effective_config(
            source,
            token_budget=token_budget,
            inventory_sha256=_sha(inventory_raw),
            exclusions_sha256=_sha(exclusions_raw),
            ledger_sha256=_sha(ledger_raw),
        )
        _write(stage / _PLAN_MEMBERS[4], config)
        after = graphify_baseline.source_manifest(
            source_root, commit=source.commit, tree=source.tree
        )
        if before != after:
            raise ValueError("source-snapshot-drift: planner input changed")
        members = tuple(
            ArtifactMember(
                name=name, sha256=_sha_file(stage / name), size=(stage / name).stat().st_size
            )
            for name in _PLAN_MEMBERS
        )
        manifest = PlanManifest(
            schema_id=_SCHEMA,
            source_commit=source.commit,
            source_tree=source.tree,
            members=members,
            warnings=inventory.warnings,
        )
        _write(stage / "manifest.json", manifest)
        Path(raw_stage).replace(output)
    return manifest


def _git(root: Path, *args: str) -> str:
    import subprocess

    completed = subprocess.run(["git", *args], cwd=root, capture_output=True, check=True, text=True)
    return completed.stdout.strip()


def _verdict(
    state: str, *, structural: bool, authorized: bool, reasons: tuple[str, ...]
) -> PlanVerification:
    return PlanVerification(
        state=state,
        structural_complete=structural,
        execution_authorized=authorized,
        reasons=reasons,
    )


def _manifest_reasons(candidate: Path, manifest: PlanManifest) -> list[str]:
    reasons: list[str] = []
    if manifest.schema_id != _SCHEMA:
        reasons.append("schema-id-mismatch")
    if manifest.warnings:
        reasons.append("plan-warning-bearing")
    if tuple(member.name for member in manifest.members) != _PLAN_MEMBERS:
        reasons.append("member-set-mismatch")
    try:
        entries = tuple(sorted(path.name for path in candidate.iterdir()))
    except OSError:
        return ["candidate-unavailable"]
    if entries != tuple(sorted((*_PLAN_MEMBERS, "manifest.json"))):
        reasons.append("candidate-entry-set-mismatch")
    for member in manifest.members:
        path = candidate / member.name
        try:
            mode = path.lstat().st_mode
        except OSError:
            reasons.append(f"member-unavailable:{member.name}")
            continue
        if not stat.S_ISREG(mode) or path.is_symlink():
            reasons.append(f"member-not-regular:{member.name}")
        elif path.stat().st_size != member.size or _sha_file(path) != member.sha256:
            reasons.append(f"member-digest-mismatch:{member.name}")
    return reasons


def _typed_members(
    candidate: Path,
) -> tuple[
    SourceInventory,
    AdvisoryCatalog,
    ExclusionCatalog,
    ChunkLedger,
    CorpusExecutionConfig,
]:
    inventory = msgspec.json.decode(
        (candidate / "source-inventory.json").read_bytes(),
        type=SourceInventory,
        strict=True,
    )
    advisories = msgspec.json.decode(
        (candidate / "advisories.json").read_bytes(), type=AdvisoryCatalog, strict=True
    )
    exclusions = msgspec.json.decode(
        (candidate / "exclusions.json").read_bytes(), type=ExclusionCatalog, strict=True
    )
    ledger = msgspec.json.decode(
        (candidate / "chunk-ledger.json").read_bytes(), type=ChunkLedger, strict=True
    )
    config = msgspec.json.decode(
        (candidate / "execution-config.json").read_bytes(),
        type=CorpusExecutionConfig,
        strict=True,
    )
    return inventory, advisories, exclusions, ledger, config


def _inventory_reasons(inventory: SourceInventory) -> list[str]:
    reasons: list[str] = []
    units = inventory.units
    if (inventory.source_commit, inventory.source_tree) == (
        _ACCEPTED_GRAPHIFY_COMMIT,
        _ACCEPTED_GRAPHIFY_TREE,
    ) and inventory.source_manifest_sha256 != _ACCEPTED_BASELINE_SOURCE_MANIFEST_SHA256:
        reasons.append("issue-299-source-manifest-mismatch")
    if inventory.admitted_unit_count != len(units):
        reasons.append("inventory-admitted-count-mismatch")
    if tuple(unit.ordinal for unit in units) != tuple(range(1, len(units) + 1)):
        reasons.append("inventory-ordinal-sequence-invalid")
    if inventory.warnings:
        reasons.append("plan-warning-bearing")
    identities = [(unit.path, unit.slice_index) for unit in units]
    if len(identities) != len(set(identities)):
        reasons.append("inventory-unit-identity-duplicate")
    for unit in units:
        valid = (
            unit.kind in {"document", "paper", "image"}
            and bool(unit.path)
            and not unit.path.startswith("/")
            and ".." not in Path(unit.path).parts
            and _valid_sha(unit.parent_sha256)
            and len(unit.source_git_object) == _GIT_OBJECT_LENGTH
            and all(char in "0123456789abcdef" for char in unit.source_git_object)
            and _valid_sha(unit.sha256)
            and unit.parent_size > 0
            and unit.estimated_tokens > 0
            and 0 <= unit.slice_start < unit.slice_end <= unit.parent_size
            and 0 <= unit.slice_index < unit.slice_total
        )
        if not valid:
            reasons.append(f"inventory-unit-invalid:{unit.ordinal}")
    for path in sorted({unit.path for unit in units}):
        group = [unit for unit in units if unit.path == path]
        totals = {unit.slice_total for unit in group}
        if (
            len(totals) != 1
            or tuple(unit.slice_index for unit in group) != tuple(range(len(group)))
            or totals != {len(group)}
        ):
            reasons.append(f"inventory-slice-sequence-invalid:{path}")
    return reasons


def _advisory_reasons(inventory: SourceInventory, advisories: AdvisoryCatalog) -> list[str]:
    reasons: list[str] = []
    if (advisories.source_commit, advisories.source_tree) != (
        inventory.source_commit,
        inventory.source_tree,
    ):
        reasons.append("advisory-source-mismatch")
    if len(advisories.entries) > 1:
        reasons.append("advisory-entry-set-invalid")
    for entry in advisories.entries:
        expected_message = (
            f"Large corpus: {entry.observed_files} files · ~{entry.observed_words:,} words. "
            "Semantic extraction will be expensive (many Claude tokens). "
            "Consider running on a subfolder."
        )
        if (
            entry.code != "graphify-large-corpus-token-cost"
            or entry.message != expected_message
            or entry.detector_git_object != _ACCEPTED_GRAPHIFY_DETECT_OBJECT
            or entry.file_count_threshold != _CORPUS_FILE_UPPER
            or entry.word_count_threshold != _CORPUS_WORD_UPPER
            or entry.review_status != "provisional"
            or (
                entry.observed_files < entry.file_count_threshold
                and entry.observed_words < entry.word_count_threshold
            )
            or inventory.source_commit != _ACCEPTED_GRAPHIFY_COMMIT
        ):
            reasons.append(f"advisory-entry-invalid:{entry.code}")
    return reasons


def _exclusion_reasons(inventory: SourceInventory, exclusions: ExclusionCatalog) -> list[str]:
    reasons: list[str] = []
    if (exclusions.source_commit, exclusions.source_tree) != (
        inventory.source_commit,
        inventory.source_tree,
    ):
        reasons.append("exclusion-source-mismatch")
    paths = tuple(entry.path for entry in exclusions.entries)
    if paths != tuple(sorted(set(paths))):
        reasons.append("exclusion-path-order-invalid")
    reasons.extend(
        f"exclusion-entry-invalid:{entry.path}"
        for entry in exclusions.entries
        if (
            entry.path not in _INTENTIONAL_EXCLUSIONS
            or _INTENTIONAL_EXCLUSIONS[entry.path]
            != (
                entry.exclusion_class,
                entry.semantic_authority_path,
                entry.evidence_paths,
            )
            or entry.review_status != "provisional"
            or not _valid_sha(entry.sha256)
            or not _valid_sha(entry.evidence_sha256)
            or len(entry.evidence_paths) != len(entry.evidence_git_objects)
            or any(
                len(value) != _GIT_OBJECT_LENGTH
                or any(char not in "0123456789abcdef" for char in value)
                for value in entry.evidence_git_objects
            )
            or entry.size <= 0
        )
    )
    admitted_paths = {unit.path for unit in inventory.units}
    if admitted_paths.intersection(paths):
        reasons.append("exclusion-admission-overlap")
    if inventory.detected_source_count != len(admitted_paths) + len(paths):
        reasons.append("detected-source-count-mismatch")
    if inventory.discovered_unit_count != inventory.admitted_unit_count + len(paths):
        reasons.append("discovered-unit-count-mismatch")
    return reasons


def _ledger_reasons(inventory: SourceInventory, ledger: ChunkLedger) -> list[str]:
    reasons: list[str] = []
    expected_units = {unit.ordinal: unit for unit in inventory.units}
    if ledger.unit_count != len(expected_units) or ledger.token_budget <= 0:
        reasons.append("chunk-ledger-count-mismatch")
    chunks = ledger.chunks
    if not chunks or tuple(chunk.ordinal for chunk in chunks) != tuple(range(1, len(chunks) + 1)):
        reasons.append("chunk-ledger-order-invalid")
    flat: list[ChunkMember] = []
    for chunk in chunks:
        if (
            not chunk.members
            or chunk.total != len(chunks)
            or chunk.estimated_tokens != sum(member.estimated_tokens for member in chunk.members)
            or chunk.estimated_tokens > ledger.token_budget
        ):
            reasons.append(f"chunk-shape-invalid:{chunk.ordinal}")
        flat.extend(chunk.members)
    ordinals = tuple(member.unit_ordinal for member in flat)
    if len(ordinals) != len(set(ordinals)) or set(ordinals) != set(expected_units):
        reasons.append("chunk-ledger-coverage-invalid")
    for member in flat:
        unit = expected_units.get(member.unit_ordinal)
        expected = (
            (
                unit.path,
                unit.slice_index,
                unit.sha256,
                unit.estimated_tokens,
            )
            if unit is not None
            else None
        )
        observed = (
            member.path,
            member.slice_index,
            member.sha256,
            member.estimated_tokens,
        )
        if observed != expected:
            reasons.append("ledger-member-inventory-mismatch")
            break
    return reasons


def _config_reasons(
    candidate: Path,
    inventory: SourceInventory,
    exclusions: ExclusionCatalog,
    ledger: ChunkLedger,
    config: CorpusExecutionConfig,
) -> list[str]:
    reasons: list[str] = []
    source = SourcePin(
        ref=inventory.source_ref,
        commit=inventory.source_commit,
        tree=inventory.source_tree,
    )
    expected = _effective_config(
        source,
        token_budget=ledger.token_budget,
        inventory_sha256=_sha_file(candidate / "source-inventory.json"),
        exclusions_sha256=_sha_file(candidate / "exclusions.json"),
        ledger_sha256=_sha_file(candidate / "chunk-ledger.json"),
    )
    if config != expected:
        reasons.append("config-contract-mismatch")
    if config.token_budget != ledger.token_budget:
        reasons.append("config-ledger-budget-mismatch")
    if exclusions.source_commit != config.graphify_commit:
        reasons.append("config-exclusion-source-mismatch")
    return reasons


def _cross_reasons(
    candidate: Path,
    inventory: SourceInventory,
    exclusions: ExclusionCatalog,
    ledger: ChunkLedger,
    config: CorpusExecutionConfig,
) -> list[str]:
    reasons = _inventory_reasons(inventory)
    reasons.extend(_exclusion_reasons(inventory, exclusions))
    reasons.extend(_ledger_reasons(inventory, ledger))
    reasons.extend(_config_reasons(candidate, inventory, exclusions, ledger, config))
    return reasons


def _source_reasons(
    source_root: Path,
    inventory: SourceInventory,
    advisories: AdvisoryCatalog,
    exclusions: ExclusionCatalog,
    ledger: ChunkLedger,
) -> list[str]:
    try:
        expected_inventory, expected_advisories, expected_exclusions, admitted = _inventory(
            source_root,
            source_ref=inventory.source_ref,
            source_commit=inventory.source_commit,
            source_tree=inventory.source_tree,
        )
        expected_ledger = _ledger(
            source_root, expected_inventory.units, admitted, ledger.token_budget
        )
    except OSError, ValueError:
        return ["source-snapshot-unavailable"]
    reasons: list[str] = []
    if inventory != expected_inventory:
        reasons.append("source-inventory-recomputation-mismatch")
    if advisories != expected_advisories:
        reasons.append("source-advisory-recomputation-mismatch")
    if exclusions != expected_exclusions:
        reasons.append("source-exclusion-recomputation-mismatch")
    if ledger != expected_ledger:
        reasons.append("source-ledger-recomputation-mismatch")
    return reasons


def _load_manifest(candidate: Path) -> PlanManifest | None:
    manifest_path = candidate / "manifest.json"
    try:
        mode = manifest_path.lstat().st_mode
    except OSError:
        return None
    if not stat.S_ISREG(mode) or manifest_path.is_symlink():
        return None
    try:
        return msgspec.json.decode(manifest_path.read_bytes(), type=PlanManifest, strict=True)
    except OSError, msgspec.DecodeError:
        return None


def _load_authority(path: Path | None) -> AuthorityRoots | None:
    if path is None:
        try:
            return msgspec.json.decode(
                graphify_semantic_corpus_authority.AUTHORITY_JSON,
                type=AuthorityRoots,
                strict=True,
            )
        except msgspec.DecodeError:
            return None
    try:
        mode = path.lstat().st_mode
        if not stat.S_ISREG(mode) or path.is_symlink():
            return None
        return msgspec.json.decode(path.read_bytes(), type=AuthorityRoots, strict=True)
    except OSError, msgspec.DecodeError:
        return None


def verify_plan(
    candidate: Path,
    source_root: Path,
    *,
    authority_path: Path | None = None,
) -> PlanVerification:
    """Rehash and cross-check a plan without mutating it or invoking Graphify."""
    manifest = _load_manifest(candidate)
    if manifest is None:
        return _verdict(
            "failed", structural=False, authorized=False, reasons=("manifest-unavailable",)
        )
    reasons = _manifest_reasons(candidate, manifest)
    if reasons:
        return _verdict(
            "failed",
            structural=False,
            authorized=False,
            reasons=tuple(dict.fromkeys(reasons)),
        )
    try:
        inventory, advisories, exclusions, ledger, config = _typed_members(candidate)
    except msgspec.DecodeError:
        return _verdict(
            "failed", structural=False, authorized=False, reasons=("typed-member-invalid",)
        )
    reasons = _advisory_reasons(inventory, advisories)
    reasons.extend(_cross_reasons(candidate, inventory, exclusions, ledger, config))
    reasons.extend(_source_reasons(source_root, inventory, advisories, exclusions, ledger))
    if reasons:
        return _verdict(
            "failed",
            structural=False,
            authorized=False,
            reasons=tuple(dict.fromkeys(reasons)),
        )
    manifest_sha = _sha_file(candidate / "manifest.json")
    config_sha = _sha_file(candidate / "execution-config.json")
    advisories_sha = _sha_file(candidate / "advisories.json")
    exclusions_sha = _sha_file(candidate / "exclusions.json")
    authority = _load_authority(authority_path)
    authority_configured = authority is not None and all(
        (
            authority.plan_manifest_sha256,
            authority.execution_config_sha256,
            authority.advisories_sha256,
            authority.exclusions_sha256,
        )
    )
    authorized = authority_configured and (
        manifest_sha,
        config_sha,
        advisories_sha,
        exclusions_sha,
    ) == (
        authority.plan_manifest_sha256,
        authority.execution_config_sha256,
        authority.advisories_sha256,
        authority.exclusions_sha256,
    )
    if not authorized:
        authority_reason = (
            "plan-authority-mismatch" if authority_configured else "plan-authority-unset"
        )
        advisory_pending = ("cost-advisory-review-required",) if advisories.entries else ()
        pending = ("provisional-input-decisions",) if exclusions.entries else ()
        return _verdict(
            "incomplete",
            structural=True,
            authorized=False,
            reasons=(authority_reason, *advisory_pending, *pending),
        )
    return _verdict("complete", structural=True, authorized=True, reasons=())


# Public surface for `graphify_semantic_corpus_run`, which is this module's
# execution half rather than an outside consumer. Exported deliberately: the
# alternative is the driver reaching into privates, and a digest helper that two
# modules reach for by different names is how two spellings of "the same hash"
# get written and then quietly disagree.
encode_canonical = _encode
sha256_bytes = _sha
sha256_path = _sha_file
fragment_counts = _fragment_counts


def _chunk_dir(cache_root: Path, namespace: str, ordinal: int) -> Path:
    if not _valid_sha(namespace):
        raise ValueError("run namespace is not a lowercase SHA-256")
    return cache_root / namespace / "chunks" / f"{ordinal:04d}"


# Exported so the execution driver can ask "is this chunk already staged?" using
# the SAME path `stage_chunk` will refuse to overwrite. Computing it separately
# would be a second opinion about where evidence lives, and the two disagreeing
# is a resumed run that either re-publishes or aborts.
chunk_stage_dir = _chunk_dir


def _provider_evidence_reasons(
    context: _ProviderValidationContext,
) -> tuple[list[str], tuple[str, ...], tuple[str, ...]]:
    """Validate retained provider bytes without manufacturing clean evidence."""
    try:
        provider = msgspec.json.decode(
            context.evidence.receipt_raw,
            type=graphify_semantic_slice.SemanticReceipt,
            strict=True,
        )
        metadata = msgspec.json.decode(
            context.evidence.adapter_metadata_raw,
            type=graphify_semantic_adapter.AdapterMetadata,
            strict=True,
        )
    except msgspec.DecodeError:
        return ["provider-evidence-invalid"], (), ()
    reasons = _provider_receipt_reasons(
        provider,
        context,
    )
    reasons.extend(_adapter_metadata_reasons(metadata))
    reasons.extend(_adapter_config_reasons(metadata, context.config))
    reasons.extend(_provider_config_reasons(provider, context.config))
    reasons.extend(_provider_chunk_reasons(provider, metadata, context))
    if metadata.auth != provider.runtime.auth:
        reasons.append("provider-auth-evidence-mismatch")
    if provider.chunks and any(
        chunk.fragment_sha256 != metadata.structured_output_sha256 for chunk in provider.chunks
    ):
        reasons.append("provider-structured-output-mismatch")
    return reasons, provider.warnings, provider.errors


def _provider_receipt_reasons(
    provider: graphify_semantic_slice.SemanticReceipt,
    context: _ProviderValidationContext,
) -> list[str]:
    covered_paths = tuple(dict.fromkeys(chunk.source_path for chunk in provider.chunks))
    covered_units = {(chunk.source_path, chunk.source_sha256) for chunk in provider.chunks}
    planned_units = {(member.path, member.sha256) for member in context.chunk.members}
    checks = (
        (provider.status == "complete", "provider-status-incomplete"),
        (not provider.warnings, "provider-warning-bearing"),
        (not provider.errors, "provider-error-bearing"),
        (provider.failed_chunks == 0, "provider-failed-chunks"),
        (not provider.uncovered_files, "provider-uncovered-files"),
        (provider.out_of_scope_dropped == 0, "provider-out-of-scope-dropped"),
        (
            provider.semantic_fragment_sha256 == _sha(context.fragment_raw),
            "provider-fragment-digest-mismatch",
        ),
        (
            provider.adapter_metadata_sha256 == _sha(context.evidence.adapter_metadata_raw),
            "provider-adapter-digest-mismatch",
        ),
        (
            (
                provider.semantic_node_count,
                provider.semantic_edge_count,
                provider.semantic_hyperedge_count,
            )
            == context.counts,
            "provider-semantic-count-mismatch",
        ),
        (covered_paths == context.source_paths, "provider-source-coverage-mismatch"),
        (covered_units == planned_units, "provider-source-identity-mismatch"),
    )
    reasons = [reason for accepted, reason in checks if not accepted]
    reasons.extend(_provider_runtime_reasons(provider, context.config))
    return reasons


def _provider_runtime_reasons(
    provider: graphify_semantic_slice.SemanticReceipt,
    config: CorpusExecutionConfig,
) -> list[str]:
    auth = provider.runtime.auth
    runtime = provider.runtime
    checks = (
        (provider.backend == config.backend, "provider-backend-mismatch"),
        (provider.model == config.claude_model, "provider-model-mismatch"),
        (
            runtime.executable_sha256 == config.claude_executable_sha256,
            "provider-executable-identity-mismatch",
        ),
        (runtime.version == config.claude_version, "provider-version-identity-mismatch"),
        (runtime.help_sha256 == config.claude_help_sha256, "provider-help-identity-mismatch"),
        (
            runtime.required_flags == config.claude_required_flags,
            "provider-capability-flags-mismatch",
        ),
        (runtime.graphify_runtime == config.graphify_runtime, "provider-graphify-runtime-mismatch"),
        (runtime.graphify_version == config.graphify_version, "provider-graphify-version-mismatch"),
        (
            runtime.graphify_semantic_fingerprint_sha256
            == config.graphify_semantic_fingerprint_sha256,
            "provider-semantic-fingerprint-mismatch",
        ),
        (
            auth.logged_in
            and auth.auth_method == "claude.ai"
            and auth.api_provider == "firstParty"
            and auth.subscription_type == "max",
            "provider-auth-route-mismatch",
        ),
    )
    return [reason for accepted, reason in checks if not accepted]


def _chunk_prompt_bytes(context: _ProviderValidationContext) -> bytes:
    inventory = {unit.ordinal: unit for unit in context.inventory.units}
    units: list[Path | FileSlice] = []
    for member in context.chunk.members:
        unit = inventory.get(member.unit_ordinal)
        if unit is None:
            raise ValueError("planned prompt unit is unavailable")
        source = context.source_root / unit.path
        units.append(
            FileSlice(
                path=source,
                start=unit.slice_start,
                end=unit.slice_end,
                index=unit.slice_index,
                total=unit.slice_total,
            )
            if unit.slice_total > 1
            else source
        )
    user_message = _read_files(units, context.source_root)
    return (
        _extraction_system(deep=context.config.deep_mode)
        + _EXTRACTION_USER_INSTRUCTION
        + user_message
    ).encode("utf-8")


def _provider_config_reasons(
    provider: graphify_semantic_slice.SemanticReceipt,
    config: CorpusExecutionConfig,
) -> list[str]:
    observed = provider.execution_config
    checks = (
        (observed.token_budget == config.token_budget, "provider-token-budget-mismatch"),
        (observed.chunk_size == config.graphify_chunk_size, "provider-chunk-size-mismatch"),
        (observed.deep_mode == config.deep_mode, "provider-deep-mode-mismatch"),
        (observed.max_concurrency == config.concurrency, "provider-concurrency-mismatch"),
        (
            observed.max_retry_depth == config.graphify_max_retry_depth,
            "provider-graphify-retry-mismatch",
        ),
        (
            observed.graphify_no_incremental_cache == config.graphify_no_incremental_cache,
            "provider-cache-policy-mismatch",
        ),
        (
            observed.graphify_api_timeout_seconds == config.timeout_seconds,
            "provider-graphify-timeout-mismatch",
        ),
        (
            observed.api_timeout_ms == config.timeout_seconds * 1000,
            "provider-adapter-timeout-mismatch",
        ),
        (
            observed.claude_code_max_output_tokens == config.claude_max_output_tokens,
            "provider-output-bound-mismatch",
        ),
        (
            observed.claude_code_max_retries == config.claude_max_retries,
            "provider-claude-retry-mismatch",
        ),
        (
            observed.max_structured_output_retries == config.structured_output_retries,
            "provider-structured-retry-mismatch",
        ),
    )
    return [reason for accepted, reason in checks if not accepted]


def _provider_chunk_reasons(
    provider: graphify_semantic_slice.SemanticReceipt,
    metadata: graphify_semantic_adapter.AdapterMetadata,
    context: _ProviderValidationContext,
) -> list[str]:
    units = {unit.ordinal: unit for unit in context.inventory.units}
    expected_units = [units.get(member.unit_ordinal) for member in context.chunk.members]
    source_size_unavailable = False
    try:
        expected_identities = {
            (
                unit.path,
                unit.source_git_object,
                unit.sha256,
                _source_unit_size(unit, context.source_root),
            )
            for unit in expected_units
            if unit is not None
        }
    except OSError:
        expected_identities = set()
        source_size_unavailable = True
    observed_identities = {
        (
            item.source_path,
            item.source_git_object,
            item.source_sha256,
            item.source_size,
        )
        for item in provider.chunks
    }
    reasons: list[str] = []
    if source_size_unavailable:
        reasons.append("provider-source-bytes-unavailable")
    if (
        None in expected_units
        or len(provider.chunks) != len(context.chunk.members)
        or observed_identities != expected_identities
    ):
        reasons.append("provider-source-evidence-mismatch")
    if not provider.chunks or any(
        (item.ordinal, item.total) != (context.chunk.ordinal, context.chunk.total)
        for item in provider.chunks
    ):
        reasons.append("provider-chunk-ordinal-total-mismatch")
    try:
        expected_prompt_sha256 = _sha(_chunk_prompt_bytes(context))
    except OSError, ValueError:
        expected_prompt_sha256 = ""
        reasons.append("provider-prompt-source-unavailable")
    if metadata.prompt_sha256 != expected_prompt_sha256 or any(
        item.prompt_sha256 != expected_prompt_sha256 for item in provider.chunks
    ):
        # WHICH mismatch, because the remedies are opposite. Both land here, and
        # the reason used to name only the first:
        #
        # * corrupted — the retained bytes are not what was sent. Investigate the
        #   adapter, the evidence tree, the disk.
        # * PARTIAL — graphify bisected this chunk into N provider calls, merged
        #   them into one callback, and the adapter's single-path metadata
        #   therefore describes only the last leaf. Nothing is corrupt; the
        #   evidence covers a fraction of the chunk. Re-plan with smaller chunks.
        #
        # `attempts` is the observed provider-call count and separates them. It
        # is only trusted HERE, where the prompt comparison has already
        # established that this chunk's evidence is wrong — the count alone is
        # not chunk-scoped (a failed chunk strands its marker for the next one),
        # so using it as the primary signal produced false refusals.
        reasons.append(
            "provider-multi-call-evidence"
            if provider.attempts > 1
            else "provider-prompt-bytes-mismatch"
        )
    if any(item.prompt_sha256 != metadata.prompt_sha256 for item in provider.chunks):
        reasons.append("provider-prompt-identity-mismatch")
    schema = _argv_value(metadata.argv, "--json-schema")
    if schema is None or _sha(schema.encode()) != context.config.structured_schema_sha256:
        reasons.append("provider-schema-identity-mismatch")
    return reasons


def _source_unit_size(unit: SourceUnit, source_root: Path) -> int:
    if unit.slice_total == 1:
        return unit.parent_size
    return len(
        read_slice_text(
            FileSlice(
                path=source_root / unit.path,
                start=unit.slice_start,
                end=unit.slice_end,
                index=unit.slice_index,
                total=unit.slice_total,
            )
        ).encode("utf-8")
    )


# Exported for the execution driver on the same grounds as the digest helpers
# above: it is the ONE definition of a unit's byte size, and the obvious
# re-derivation (`slice_end - slice_start`) is a character count that silently
# disagrees with it on any non-ASCII source — of which this corpus has plenty.
source_unit_size = _source_unit_size


def _argv_value(argv: tuple[str, ...], flag: str) -> str | None:
    try:
        index = argv.index(flag)
        return argv[index + 1]
    except ValueError, IndexError:
        return None


def _adapter_metadata_reasons(
    metadata: graphify_semantic_adapter.AdapterMetadata,
) -> list[str]:
    complete = (
        metadata.status == "complete"
        and metadata.returncode == 0
        and metadata.stderr_size == 0
        and not metadata.is_error
        and metadata.result_type == "result"
        and metadata.result_subtype == "success"
        and metadata.terminal_reason == "completed"
        and metadata.stop_reason == "tool_use"
        and metadata.permission_denial_count == 0
        and not metadata.reasons
    )
    reasons = [] if complete else ["provider-truncated-or-incomplete"]
    parse_reasons = graphify_semantic_adapter.parse_observation_reasons(
        metadata.parse_observation,
        digest=metadata.parse_observation_sha256,
        response_sha256=metadata.response_sha256,
        response_size=metadata.response_size,
    )
    reasons.extend(f"provider-{reason}" for reason in parse_reasons)
    if metadata.parse_observation is not None and metadata.parse_observation.status not in {
        "accepted-object",
        "accepted-result-array",
    }:
        reasons.append("provider-response-untyped")
    return reasons


def _adapter_config_reasons(
    metadata: graphify_semantic_adapter.AdapterMetadata,
    config: CorpusExecutionConfig,
) -> list[str]:
    schema = _argv_value(metadata.argv, "--json-schema")
    # Built from the SAME function the adapter builds the real call with. The
    # local copy this replaces rendered the budget as `str(config.max_cost_usd)`,
    # which agreed with the adapter's literal only while the cap happened to be
    # `0.25`: at 25.0 it renders "25.0" against an argv carrying "25.00", and the
    # run would have failed as an argv-shape mismatch with nothing pointing at the
    # formatting. The profile owns the literal precisely so it is never re-derived.
    expected_argv = graphify_semantic_slice.expected_adapter_argv(_PROFILE, schema or "")
    usage_valid = (
        len(metadata.model_usage) == 1
        and metadata.model_usage[0].model == config.claude_model
        and metadata.model_usage[0].canonical_model == config.claude_canonical_model
        and metadata.model_usage[0].provider == "firstParty"
    )
    forbidden_environment = any(
        name.endswith("API_KEY") or "ENDPOINT" in name for name in metadata.environment_names
    )
    checks = (
        (
            metadata.claude_executable_sha256 == config.claude_executable_sha256,
            "provider-adapter-executable-mismatch",
        ),
        (
            metadata.claude_version.startswith(config.claude_version),
            "provider-adapter-version-mismatch",
        ),
        (metadata.argv == expected_argv, "provider-adapter-argv-mismatch"),
        (not forbidden_environment, "provider-adapter-endpoint-policy-mismatch"),
        # BOTH bounds. The upper one alone accepted `total_cost_usd = -1.0` — an
        # impossible cost, and exactly the shape a missing-value sentinel takes,
        # so an adapter that failed to observe the cost would have passed the
        # check that exists to observe it. The slice validator has always checked
        # `0.0 <= cost <= max` (`graphify_semantic_slice.py`); this is the corpus
        # copy of one rule drifting from it in the looser direction.
        (
            0.0 <= metadata.total_cost_usd <= config.max_cost_usd,
            "provider-adapter-cost-bound-exceeded",
        ),
        (usage_valid, "provider-adapter-model-usage-mismatch"),
    )
    return [reason for accepted, reason in checks if not accepted]


def stage_chunk(
    candidate: Path,
    cache_root: Path,
    request: ChunkStageRequest,
) -> ChunkStageReceipt:
    """Retain and atomically publish exact real-provider evidence for one chunk."""
    inventory, config, plan_reasons = _stage_plan_context(candidate, request)
    chunk = request.chunk
    provider_evidence = request.provider_evidence
    destination = _chunk_dir(cache_root, request.run_namespace, chunk.ordinal)
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"chunk stage already exists: {destination}")
    source_paths = tuple(dict.fromkeys(member.path for member in chunk.members))
    fragment_reasons = list(
        graphify_semantic_slice.fragment_scope_reasons(request.fragment, source_paths=source_paths)
    )
    try:
        node_count, edge_count, hyperedge_count = _fragment_counts(request.fragment)
    except TypeError, ValueError:
        node_count, edge_count, hyperedge_count = 0, 0, 0
        fragment_reasons.append("fragment-invalid")
    fragment_raw = _encode(request.fragment)
    provider_reasons, provider_warnings, provider_errors = _provider_evidence_reasons(
        _ProviderValidationContext(
            provider_evidence,
            fragment_raw,
            source_paths,
            chunk,
            (node_count, edge_count, hyperedge_count),
            inventory,
            config,
            request.source_root,
        )
    )
    reasons = tuple(dict.fromkeys((*plan_reasons, *fragment_reasons, *provider_reasons)))
    metadata = _decode_adapter_metadata(provider_evidence.adapter_metadata_raw)
    receipt = ChunkStageReceipt(
        status="failed" if reasons else "complete",
        cache_namespace_sha256=request.cache_namespace,
        run_namespace_sha256=request.run_namespace,
        chunk_ordinal=chunk.ordinal,
        chunk_total=chunk.total,
        chunk_sha256=_sha(_encode(chunk)),
        plan_manifest_sha256=_sha_file(candidate / "manifest.json"),
        execution_config_sha256=_sha_file(candidate / "execution-config.json"),
        prompt_contract_sha256=config.prompt_contract_sha256,
        structured_schema_sha256=config.structured_schema_sha256,
        provider_prompt_sha256=metadata.prompt_sha256 if metadata is not None else "",
        source_paths=source_paths,
        fragment_sha256=_sha(fragment_raw),
        fragment_size=len(fragment_raw),
        provider_receipt_sha256=_sha(provider_evidence.receipt_raw),
        provider_receipt_size=len(provider_evidence.receipt_raw),
        adapter_metadata_sha256=_sha(provider_evidence.adapter_metadata_raw),
        adapter_metadata_size=len(provider_evidence.adapter_metadata_raw),
        node_count=node_count,
        edge_count=edge_count,
        hyperedge_count=hyperedge_count,
        warnings=provider_warnings,
        errors=provider_errors,
        reasons=reasons,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-", dir=destination.parent
    ) as raw_stage:
        stage = Path(raw_stage)
        atomic.write_text(stage / "semantic-fragment.json", fragment_raw.decode("utf-8"))
        atomic.write_text(
            stage / "provider-receipt.json", provider_evidence.receipt_raw.decode("utf-8")
        )
        atomic.write_text(
            stage / "adapter-metadata.json",
            provider_evidence.adapter_metadata_raw.decode("utf-8"),
        )
        _write(stage / "receipt.json", receipt)
        Path(raw_stage).replace(destination)
    return receipt


def _decode_adapter_metadata(
    raw: bytes,
) -> graphify_semantic_adapter.AdapterMetadata | None:
    try:
        return msgspec.json.decode(raw, type=graphify_semantic_adapter.AdapterMetadata, strict=True)
    except msgspec.DecodeError:
        return None


def _stage_plan_context(
    candidate: Path, request: ChunkStageRequest
) -> tuple[SourceInventory, CorpusExecutionConfig, list[str]]:
    manifest = _load_manifest(candidate)
    if manifest is None:
        raise ValueError("staged chunk plan manifest is unavailable")
    inventory, advisories, exclusions, ledger, config = _typed_members(candidate)
    reasons = _manifest_reasons(candidate, manifest)
    reasons.extend(_advisory_reasons(inventory, advisories))
    reasons.extend(_cross_reasons(candidate, inventory, exclusions, ledger, config))
    reasons.extend(_source_reasons(request.source_root, inventory, advisories, exclusions, ledger))
    expected = next(
        (chunk for chunk in ledger.chunks if chunk.ordinal == request.chunk.ordinal),
        None,
    )
    if expected != request.chunk:
        reasons.append("stage-chunk-plan-mismatch")
    if request.cache_namespace != config.cache_namespace_sha256:
        reasons.append("stage-cache-namespace-mismatch")
    if not _valid_sha(request.run_namespace):
        reasons.append("stage-run-namespace-invalid")
    return inventory, config, reasons


def _chunk_payloads(destination: Path) -> tuple[dict[str, bytes], list[str]]:
    expected = (
        "adapter-metadata.json",
        "provider-receipt.json",
        "receipt.json",
        "semantic-fragment.json",
    )
    try:
        mode = destination.lstat().st_mode
        if not stat.S_ISDIR(mode) or destination.is_symlink():
            return {}, ["chunk-directory-not-regular"]
        entries = tuple(sorted(destination.iterdir(), key=lambda path: path.name))
    except OSError:
        return {}, ["chunk-stage-unavailable"]
    reasons: list[str] = []
    if tuple(entry.name for entry in entries) != expected:
        reasons.append("chunk-entry-set-mismatch")
    payloads: dict[str, bytes] = {}
    for entry in entries:
        try:
            entry_mode = entry.lstat().st_mode
        except OSError:
            reasons.append(f"chunk-entry-unavailable:{entry.name}")
            continue
        if not stat.S_ISREG(entry_mode) or entry.is_symlink():
            reasons.append(f"chunk-entry-not-regular:{entry.name}")
            continue
        try:
            payloads[entry.name] = entry.read_bytes()
        except OSError:
            reasons.append(f"chunk-entry-unavailable:{entry.name}")
    return payloads, reasons


def verify_staged_chunk(
    cache_root: Path,
    reference: ChunkStageReference,
) -> ChunkStageVerification:
    """Rehash one staged fragment without executing or repairing it."""
    destination = _chunk_dir(cache_root, reference.run_namespace, reference.chunk.ordinal)
    return _verify_staged_destination(destination, reference)


def _verify_staged_destination(
    destination: Path,
    reference: ChunkStageReference,
) -> ChunkStageVerification:
    """Verify an exact staged directory at a caller-resolved run location."""
    payloads, reasons = _chunk_payloads(destination)
    if reasons:
        return ChunkStageVerification(state="failed", reasons=tuple(dict.fromkeys(reasons)))
    try:
        receipt = msgspec.json.decode(
            payloads["receipt.json"],
            type=ChunkStageReceipt,
            strict=True,
        )
        fragment_raw = payloads["semantic-fragment.json"]
        provider_raw = payloads["provider-receipt.json"]
        metadata_raw = payloads["adapter-metadata.json"]
    except KeyError, msgspec.DecodeError:
        return ChunkStageVerification(state="failed", reasons=("chunk-stage-unavailable",))
    reasons = []
    try:
        inventory, _advisories, _exclusions, _ledger, config = _typed_members(reference.candidate)
    except OSError, msgspec.DecodeError:
        return ChunkStageVerification(state="failed", reasons=("chunk-plan-unavailable",))
    metadata = _decode_adapter_metadata(metadata_raw)
    expected = {
        "cache-namespace-mismatch": (
            receipt.cache_namespace_sha256,
            reference.cache_namespace,
        ),
        "cache-namespace-config-mismatch": (
            reference.cache_namespace,
            config.cache_namespace_sha256,
        ),
        "run-namespace-mismatch": (
            receipt.run_namespace_sha256,
            reference.run_namespace,
        ),
        "chunk-ordinal-mismatch": (receipt.chunk_ordinal, reference.chunk.ordinal),
        "chunk-total-mismatch": (receipt.chunk_total, reference.chunk.total),
        "chunk-digest-mismatch": (
            receipt.chunk_sha256,
            _sha(_encode(reference.chunk)),
        ),
        "chunk-plan-manifest-mismatch": (
            receipt.plan_manifest_sha256,
            _sha_file(reference.candidate / "manifest.json"),
        ),
        "chunk-execution-config-mismatch": (
            receipt.execution_config_sha256,
            _sha_file(reference.candidate / "execution-config.json"),
        ),
        "chunk-prompt-contract-mismatch": (
            receipt.prompt_contract_sha256,
            config.prompt_contract_sha256,
        ),
        "chunk-schema-contract-mismatch": (
            receipt.structured_schema_sha256,
            config.structured_schema_sha256,
        ),
        "chunk-provider-prompt-mismatch": (
            receipt.provider_prompt_sha256,
            metadata.prompt_sha256 if metadata is not None else "",
        ),
        "chunk-source-scope-mismatch": (
            receipt.source_paths,
            tuple(dict.fromkeys(member.path for member in reference.chunk.members)),
        ),
        "fragment-digest-mismatch": (receipt.fragment_sha256, _sha(fragment_raw)),
        "fragment-size-mismatch": (receipt.fragment_size, len(fragment_raw)),
        "provider-receipt-digest-mismatch": (
            receipt.provider_receipt_sha256,
            _sha(provider_raw),
        ),
        "provider-receipt-size-mismatch": (
            receipt.provider_receipt_size,
            len(provider_raw),
        ),
        "adapter-metadata-digest-mismatch": (
            receipt.adapter_metadata_sha256,
            _sha(metadata_raw),
        ),
        "adapter-metadata-size-mismatch": (
            receipt.adapter_metadata_size,
            len(metadata_raw),
        ),
    }
    reasons.extend(reason for reason, values in expected.items() if values[0] != values[1])
    if receipt.status != "complete" or receipt.warnings or receipt.errors or receipt.reasons:
        reasons.append("chunk-receipt-incomplete")
    try:
        fragment = msgspec.json.decode(fragment_raw)
        counts = _fragment_counts(fragment)
        reasons.extend(
            graphify_semantic_slice.fragment_scope_reasons(
                fragment, source_paths=receipt.source_paths
            )
        )
        if counts != (receipt.node_count, receipt.edge_count, receipt.hyperedge_count):
            reasons.append("fragment-count-mismatch")
        provider_reasons, warnings, errors = _provider_evidence_reasons(
            _ProviderValidationContext(
                RetainedProviderEvidence(provider_raw, metadata_raw),
                fragment_raw,
                receipt.source_paths,
                reference.chunk,
                counts,
                inventory,
                config,
                reference.source_root,
            )
        )
        reasons.extend(provider_reasons)
        if warnings != receipt.warnings or errors != receipt.errors:
            reasons.append("provider-diagnostics-mismatch")
    except msgspec.DecodeError, TypeError, ValueError:
        reasons.append("fragment-invalid")
    return ChunkStageVerification(
        state="failed" if reasons else "complete",
        reasons=tuple(dict.fromkeys(reasons)),
    )


class _PlanBinding(msgspec.Struct, frozen=True):
    manifest_sha256: str
    config_sha256: str
    exclusions_sha256: str
    inventory_sha256: str
    ledger_sha256: str
    source_commit: str
    source_tree: str
    cache_namespace_sha256: str
    chunk_count: int
    unit_count: int


class _RunArtifact(msgspec.Struct, frozen=True):
    evidence: RunEvidence
    fragment_ledger: RunFragmentLedger
    graph_node_count: int
    graph_edge_count: int
    graph_hyperedge_count: int


class _RunPayloads(msgspec.Struct, frozen=True):
    receipt: bytes
    ledger: bytes
    graph: bytes
    chunks_root: Path


def _plan_binding(candidate: Path) -> _PlanBinding:
    manifest = _load_manifest(candidate)
    if manifest is None:
        raise ValueError("plan manifest is unavailable")
    inventory, _advisories, _exclusions, ledger, config = _typed_members(candidate)
    return _PlanBinding(
        manifest_sha256=_sha_file(candidate / "manifest.json"),
        config_sha256=_sha_file(candidate / "execution-config.json"),
        exclusions_sha256=_sha_file(candidate / "exclusions.json"),
        inventory_sha256=_sha_file(candidate / "source-inventory.json"),
        ledger_sha256=_sha_file(candidate / "chunk-ledger.json"),
        source_commit=manifest.source_commit,
        source_tree=manifest.source_tree,
        cache_namespace_sha256=config.cache_namespace_sha256,
        chunk_count=len(ledger.chunks),
        unit_count=inventory.admitted_unit_count,
    )


def _run_evidence_reasons(evidence: RunEvidence, binding: _PlanBinding) -> list[str]:
    reasons: list[str] = []
    if evidence.warnings or evidence.errors:
        reasons.append(f"{evidence.mode}-warning-or-error")
    if not all(
        _valid_sha(value)
        for value in (
            evidence.cache_namespace_sha256,
            evidence.run_namespace_sha256,
            evidence.plan_manifest_sha256,
            evidence.execution_config_sha256,
            evidence.exclusions_sha256,
            evidence.source_inventory_sha256,
            evidence.chunk_ledger_sha256,
            evidence.fragment_ledger_sha256,
            evidence.graph_sha256,
        )
    ):
        reasons.append(f"{evidence.mode}-digest-invalid")
    expected = (
        binding.manifest_sha256,
        binding.config_sha256,
        binding.exclusions_sha256,
        binding.inventory_sha256,
        binding.ledger_sha256,
        binding.source_commit,
        binding.source_tree,
        binding.cache_namespace_sha256,
        binding.chunk_count,
        binding.chunk_count,
        binding.unit_count,
    )
    observed = (
        evidence.plan_manifest_sha256,
        evidence.execution_config_sha256,
        evidence.exclusions_sha256,
        evidence.source_inventory_sha256,
        evidence.chunk_ledger_sha256,
        evidence.source_commit,
        evidence.source_tree,
        evidence.cache_namespace_sha256,
        evidence.chunk_count,
        evidence.completed_chunks,
        evidence.covered_units,
    )
    if observed != expected:
        reasons.append(f"{evidence.mode}-plan-binding-mismatch")
    if (
        evidence.chunk_count <= 0
        or evidence.covered_units <= 0
        or evidence.failed_chunks != 0
        or evidence.uncovered_units != 0
        or evidence.semantic_node_count <= 0
        or evidence.semantic_edge_count <= 0
        or evidence.semantic_hyperedge_count < 0
        or evidence.graph_node_count <= 0
        or evidence.graph_edge_count <= 0
        or evidence.graph_hyperedge_count < 0
    ):
        reasons.append(f"{evidence.mode}-evidence-empty")
    return reasons


def _regular_payload(path: Path, label: str, reasons: list[str]) -> bytes | None:
    try:
        mode = path.lstat().st_mode
    except OSError:
        reasons.append(f"{label}-unavailable")
        return None
    if not stat.S_ISREG(mode) or path.is_symlink():
        reasons.append(f"{label}-not-regular")
        return None
    try:
        return path.read_bytes()
    except OSError:
        reasons.append(f"{label}-unavailable")
        return None


def _graph_counts(raw: bytes) -> tuple[int, int, int] | None:
    try:
        graph = msgspec.json.decode(raw)
    except msgspec.DecodeError:
        return None
    if not isinstance(graph, dict):
        return None
    nodes = graph.get("nodes")
    edges = graph.get("links", graph.get("edges"))
    graph_metadata = graph.get("graph", {})
    if not isinstance(graph_metadata, dict):
        return None
    hyperedges = graph_metadata.get("hyperedges", graph.get("hyperedges", []))
    if not all(isinstance(value, list) for value in (nodes, edges, hyperedges)):
        return None
    return len(nodes), len(edges), len(hyperedges)


def _semantic_graph_integrity_reasons(raw: bytes, source_paths: set[str]) -> list[str]:
    """Validate references and source provenance in an exported semantic graph."""
    try:
        graph = msgspec.json.decode(raw)
    except msgspec.DecodeError:
        return ["run-graph-invalid"]
    if not isinstance(graph, dict):
        return ["run-graph-invalid"]
    nodes = graph.get("nodes")
    links = graph.get("links", graph.get("edges"))
    metadata = graph.get("graph", {})
    hyperedges = (
        metadata.get("hyperedges", graph.get("hyperedges", []))
        if isinstance(metadata, dict)
        else None
    )
    if (
        not isinstance(nodes, list)
        or not isinstance(links, list)
        or not isinstance(hyperedges, list)
    ):
        return ["run-graph-invalid"]
    node_ids = [node.get("id") for node in nodes if isinstance(node, dict)]
    reasons: list[str] = []
    if len(node_ids) != len(nodes) or len(node_ids) != len(set(node_ids)):
        reasons.append("run-graph-node-identity-invalid")
    known = set(node_ids)
    if any(
        not isinstance(link, dict)
        or link.get("source") not in known
        or link.get("target") not in known
        for link in links
    ):
        reasons.append("run-graph-reference-invalid")
    if any(
        not isinstance(hyperedge, dict)
        or not isinstance(hyperedge.get("nodes"), list)
        or any(member not in known for member in hyperedge.get("nodes", []))
        for hyperedge in hyperedges
    ):
        reasons.append("run-graph-hyperedge-reference-invalid")
    sourced = (*nodes, *links, *hyperedges)
    if any(
        not isinstance(item, dict)
        or not isinstance(item.get("source_file"), str)
        or item["source_file"] not in source_paths
        for item in sourced
    ):
        reasons.append("run-graph-source-provenance-invalid")
    return reasons


def _semantic_graph_bytes(
    fragments: list[dict[str, object]], binding: _PlanBinding
) -> tuple[bytes | None, list[str]]:
    """Rebuild exact semantic graph bytes using Graphify's public SDK only."""
    try:
        graph, _build_receipt = graphify_sdk.build_checked(fragments, root=Path("/"))
        with tempfile.TemporaryDirectory(prefix="kb301-semantic-graph-") as raw_dir:
            output = Path(raw_dir) / "graph.json"
            graphify_sdk.artifact_checked(
                graph,
                {},
                output,
                built_at_commit=binding.source_commit,
            )
            return output.read_bytes(), []
    except OSError, RuntimeError, TypeError, ValueError:
        return None, ["run-semantic-graph-rebuild-failed"]


def _fragment_member(
    destination: Path, chunk: PlannedChunk, receipt: ChunkStageReceipt
) -> RunFragmentMember:
    return RunFragmentMember(
        chunk_ordinal=chunk.ordinal,
        chunk_sha256=_sha(_encode(chunk)),
        unit_ordinals=tuple(member.unit_ordinal for member in chunk.members),
        source_paths=tuple(dict.fromkeys(member.path for member in chunk.members)),
        stage_receipt_sha256=_sha_file(destination / "receipt.json"),
        provider_receipt_sha256=_sha_file(destination / "provider-receipt.json"),
        adapter_metadata_sha256=_sha_file(destination / "adapter-metadata.json"),
        fragment_sha256=_sha_file(destination / "semantic-fragment.json"),
        node_count=receipt.node_count,
        edge_count=receipt.edge_count,
        hyperedge_count=receipt.hyperedge_count,
    )


def _run_payloads(
    run_root: Path, chunks: tuple[PlannedChunk, ...]
) -> tuple[_RunPayloads | None, list[str]]:
    reasons: list[str] = []
    try:
        root_mode = run_root.lstat().st_mode
        entries = tuple(sorted(entry.name for entry in run_root.iterdir()))
    except OSError:
        return None, ["run-artifact-unavailable"]
    if not stat.S_ISDIR(root_mode) or run_root.is_symlink():
        return None, ["run-artifact-root-not-directory"]
    if entries != ("chunks", "fragment-ledger.json", "graph.json", "run-receipt.json"):
        reasons.append("run-artifact-entry-set-mismatch")
    receipt_raw = _regular_payload(run_root / "run-receipt.json", "run-receipt", reasons)
    ledger_raw = _regular_payload(run_root / "fragment-ledger.json", "fragment-ledger", reasons)
    graph_raw = _regular_payload(run_root / "graph.json", "run-graph", reasons)
    chunks_root = run_root / "chunks"
    try:
        chunks_mode = chunks_root.lstat().st_mode
        chunk_entries = tuple(sorted(entry.name for entry in chunks_root.iterdir()))
    except OSError:
        reasons.append("run-chunks-unavailable")
        return None, reasons
    if not stat.S_ISDIR(chunks_mode) or chunks_root.is_symlink():
        reasons.append("run-chunks-not-directory")
    expected_entries = tuple(f"{chunk.ordinal:04d}" for chunk in chunks)
    if chunk_entries != expected_entries:
        reasons.append("run-chunk-entry-set-mismatch")
    if receipt_raw is None or ledger_raw is None or graph_raw is None:
        return None, reasons
    return _RunPayloads(receipt_raw, ledger_raw, graph_raw, chunks_root), reasons


def _staged_run_members(
    reference: ChunkStageReference,
    chunks_root: Path,
    chunks: tuple[PlannedChunk, ...],
) -> tuple[list[RunFragmentMember], list[dict[str, object]], list[str]]:
    expected_members: list[RunFragmentMember] = []
    fragments: list[dict[str, object]] = []
    reasons: list[str] = []
    for chunk in chunks:
        destination = chunks_root / f"{chunk.ordinal:04d}"
        verification = _verify_staged_destination(
            destination,
            msgspec.structs.replace(reference, chunk=chunk),
        )
        if verification.state != "complete":
            reasons.extend(f"run-chunk-{chunk.ordinal}:{reason}" for reason in verification.reasons)
            continue
        receipt_raw = _regular_payload(
            destination / "receipt.json", f"run-chunk-{chunk.ordinal}:receipt", reasons
        )
        if receipt_raw is None:
            continue
        try:
            stage_receipt = msgspec.json.decode(receipt_raw, type=ChunkStageReceipt, strict=True)
            fragment = msgspec.json.decode((destination / "semantic-fragment.json").read_bytes())
        except msgspec.DecodeError:
            reasons.append(f"run-chunk-{chunk.ordinal}:receipt-invalid")
            continue
        expected_members.append(_fragment_member(destination, chunk, stage_receipt))
        if isinstance(fragment, dict):
            fragments.append(fragment)
        else:
            reasons.append(f"run-chunk-{chunk.ordinal}:fragment-invalid")
    return expected_members, fragments, reasons


def _run_reconciliation_reasons(
    artifact: _RunArtifact,
    payloads: _RunPayloads,
    expected_members: list[RunFragmentMember],
    rebuilt_graph: bytes | None,
    binding: _PlanBinding,
) -> list[str]:
    evidence = artifact.evidence
    ledger = artifact.fragment_ledger
    reasons: list[str] = []
    checks = (
        (
            ledger.cache_namespace_sha256 == evidence.cache_namespace_sha256,
            "fragment-ledger-cache-namespace-mismatch",
        ),
        (
            ledger.run_namespace_sha256 == evidence.run_namespace_sha256,
            "fragment-ledger-run-namespace-mismatch",
        ),
        (ledger.members == tuple(expected_members), "fragment-ledger-content-mismatch"),
        (
            evidence.fragment_ledger_sha256 == _sha(payloads.ledger),
            "fragment-ledger-digest-mismatch",
        ),
        (evidence.graph_sha256 == _sha(payloads.graph), "run-graph-digest-mismatch"),
        (
            (
                evidence.semantic_node_count,
                evidence.semantic_edge_count,
                evidence.semantic_hyperedge_count,
            )
            == (
                sum(member.node_count for member in expected_members),
                sum(member.edge_count for member in expected_members),
                sum(member.hyperedge_count for member in expected_members),
            ),
            "run-semantic-count-mismatch",
        ),
        (
            (
                evidence.graph_node_count,
                evidence.graph_edge_count,
                evidence.graph_hyperedge_count,
            )
            == (
                artifact.graph_node_count,
                artifact.graph_edge_count,
                artifact.graph_hyperedge_count,
            ),
            "run-graph-count-mismatch",
        ),
    )
    reasons.extend(reason for accepted, reason in checks if not accepted)
    if rebuilt_graph is None:
        reasons.append("run-semantic-graph-unreconstructable")
    elif payloads.graph != rebuilt_graph:
        reasons.append("run-graph-content-mismatch")
    source_paths = {path for member in expected_members for path in member.source_paths}
    reasons.extend(_semantic_graph_integrity_reasons(payloads.graph, source_paths))
    covered = tuple(ordinal for member in expected_members for ordinal in member.unit_ordinals)
    if (
        len(covered) != len(set(covered))
        or set(covered) != set(range(1, binding.unit_count + 1))
        or evidence.covered_units != len(covered)
    ):
        reasons.append("run-unit-coverage-mismatch")
    return reasons


def _run_artifact(
    candidate: Path,
    source_root: Path,
    run_root: Path,
    binding: _PlanBinding,
    chunks: tuple[PlannedChunk, ...],
) -> tuple[_RunArtifact | None, list[str]]:
    payloads, reasons = _run_payloads(run_root, chunks)
    if payloads is None:
        return None, reasons
    try:
        evidence = msgspec.json.decode(payloads.receipt, type=RunEvidence, strict=True)
        fragment_ledger = msgspec.json.decode(payloads.ledger, type=RunFragmentLedger, strict=True)
    except msgspec.DecodeError:
        reasons.append("run-artifact-schema-invalid")
        return None, reasons
    reasons.extend(_run_evidence_reasons(evidence, binding))
    expected_members, fragments, staged_reasons = _staged_run_members(
        ChunkStageReference(
            candidate,
            source_root,
            evidence.cache_namespace_sha256,
            evidence.run_namespace_sha256,
            chunks[0],
        ),
        payloads.chunks_root,
        chunks,
    )
    reasons.extend(staged_reasons)
    rebuilt_graph: bytes | None = None
    if len(fragments) == len(chunks):
        rebuilt_graph, rebuild_reasons = _semantic_graph_bytes(fragments, binding)
        reasons.extend(rebuild_reasons)
    counts = _graph_counts(payloads.graph)
    if counts is None or counts[0] <= 0 or counts[1] <= 0:
        reasons.append("run-graph-invalid")
        counts = (0, 0, 0)
    artifact = _RunArtifact(evidence, fragment_ledger, *counts)
    reasons.extend(
        _run_reconciliation_reasons(artifact, payloads, expected_members, rebuilt_graph, binding)
    )
    return artifact, reasons


def _mode_parity_reasons(cold: RunEvidence, reuse: RunEvidence, rebuild: RunEvidence) -> list[str]:
    reasons: list[str] = []
    if cold.provider_calls != cold.chunk_count:
        reasons.append("cold-provider-call-count-invalid")
    if reuse.provider_calls != 0:
        reasons.append("reuse-provider-calls-nonzero")
    if rebuild.provider_calls != 0:
        reasons.append("rebuild-provider-calls-nonzero")
    byte_parity = (
        "cache_namespace_sha256",
        "run_namespace_sha256",
        "chunk_count",
        "completed_chunks",
        "fragment_ledger_sha256",
        "graph_sha256",
        "covered_units",
        "semantic_node_count",
        "semantic_edge_count",
        "semantic_hyperedge_count",
        "graph_node_count",
        "graph_edge_count",
        "graph_hyperedge_count",
    )
    for mode, evidence in (("reuse", reuse), ("rebuild", rebuild)):
        if any(getattr(evidence, field) != getattr(cold, field) for field in byte_parity):
            reasons.append(f"{mode}-cold-parity-mismatch")
    return reasons


def _variance_reasons(cold: RunEvidence, variance: RunEvidence, binding: _PlanBinding) -> list[str]:
    reasons: list[str] = []
    if variance.provider_calls != variance.chunk_count:
        reasons.append("variance-provider-call-count-invalid")
    if variance.run_namespace_sha256 == cold.run_namespace_sha256:
        reasons.append("variance-namespace-not-fresh")
    if (
        variance.chunk_count != cold.chunk_count
        or variance.covered_units != cold.covered_units
        or variance.semantic_node_count <= 0
        or variance.semantic_edge_count <= 0
    ):
        reasons.append("variance-semantic-coverage-mismatch")
    if cold.run_namespace_sha256 != binding.cache_namespace_sha256:
        reasons.append("cold-namespace-mismatch")
    return reasons


def _derived_namespace_reasons(
    cold: RunEvidence, reuse: RunEvidence, rebuild: RunEvidence
) -> list[str]:
    reasons: list[str] = []
    if reuse.run_namespace_sha256 != cold.run_namespace_sha256:
        reasons.append("reuse-namespace-mismatch")
    if rebuild.run_namespace_sha256 != cold.run_namespace_sha256:
        reasons.append("rebuild-namespace-mismatch")
    return reasons


def verify_execution_modes(
    candidate: Path,
    source_root: Path,
    runs: ExecutionRunSet,
    *,
    authority_path: Path | None = None,
) -> ExecutionModeVerification:
    """Reconstruct mode evidence from exact artifact directories and verify it."""
    if (
        not isinstance(runs.cold, Path)
        or not isinstance(runs.reuse, Path)
        or not isinstance(runs.rebuild, Path)
        or not isinstance(runs.variance, Path)
    ):
        return ExecutionModeVerification(
            state="failed", reasons=("execution-artifact-path-invalid",)
        )
    plan = verify_plan(candidate, source_root=source_root, authority_path=authority_path)
    try:
        binding = _plan_binding(candidate)
        (
            _inventory_value,
            _advisories_value,
            _exclusions_value,
            plan_ledger,
            _config_value,
        ) = _typed_members(candidate)
    except OSError, ValueError, msgspec.DecodeError:
        return ExecutionModeVerification(state="failed", reasons=("authorized-plan-invalid",))
    artifacts: list[_RunArtifact] = []
    reasons: list[str] = []
    for expected_mode, run_root in zip(
        ("cold", "reuse", "rebuild", "variance"),
        (runs.cold, runs.reuse, runs.rebuild, runs.variance),
        strict=True,
    ):
        artifact, artifact_reasons = _run_artifact(
            candidate,
            source_root,
            run_root,
            binding,
            plan_ledger.chunks,
        )
        reasons.extend(f"{expected_mode}:{reason}" for reason in artifact_reasons)
        if artifact is not None:
            artifacts.append(artifact)
            if artifact.evidence.mode != expected_mode:
                reasons.append(f"{expected_mode}:execution-mode-invalid")
    if len(artifacts) != _EXECUTION_MODE_COUNT:
        return ExecutionModeVerification(
            state="failed", reasons=tuple(dict.fromkeys(reasons or ["run-artifact-unavailable"]))
        )
    cold_evidence, reuse_evidence, rebuild_evidence, variance_evidence = (
        artifact.evidence for artifact in artifacts
    )
    reasons.extend(_mode_parity_reasons(cold_evidence, reuse_evidence, rebuild_evidence))
    reasons.extend(_variance_reasons(cold_evidence, variance_evidence, binding))
    reasons.extend(_derived_namespace_reasons(cold_evidence, reuse_evidence, rebuild_evidence))
    if reasons:
        return ExecutionModeVerification(state="failed", reasons=tuple(dict.fromkeys(reasons)))
    if not plan.execution_authorized:
        return ExecutionModeVerification(state=plan.state, reasons=plan.reasons)
    return ExecutionModeVerification(
        state="complete",
        reasons=(),
    )


def _abort(candidate: Path, reasons: tuple[str, ...]) -> int:
    receipt = AbortReceipt(_ABORT_SCHEMA, "aborted", 0, reasons)
    if candidate.is_dir():
        _write(candidate.with_name(f"{candidate.name}.abort.json"), receipt)
    print(_encode(receipt).decode().rstrip())
    return 2


def _execute_authorized(repo_root: Path, output: Path) -> int:
    """Spend against an already-authorized plan and report what it produced.

    The source is re-admitted into a fresh temporary tree rather than reusing the
    one ``verify_plan`` just checked: the verification proved the plan matches a
    pristine snapshot, and extracting from a tree something else has since
    touched would spend real tokens on bytes nobody verified. graphify's
    ``detect()`` in particular writes converted sidecars INTO the tree it scans.

    Returns non-zero unless every planned chunk completed. A partially-extracted
    corpus is the failure mode that reads as success — the chunks that landed are
    real and the graph is quietly short — so the count is the gate, not the
    absence of an exception.
    """
    from kb_setup import graphify_semantic_corpus_run

    with tempfile.TemporaryDirectory(prefix="kb-graphify-corpus-run-") as raw_source:
        source_root = Path(raw_source) / "graphify"
        admit_source(repo_root, source_root)
        summary = graphify_semantic_corpus_run.execute(
            output,
            # DERIVED from the plan the operator named, not from `repo_root`.
            # Planning is deterministic, so a plan regenerated into a temporary
            # directory is byte-identical to the committed one and passes the
            # authority check unchanged — after which a hardcoded repo-root path
            # wrote that run's chunk evidence into the repository tree while the
            # operator had named a directory outside it. For the default plan
            # location the two spellings produce the same path, so this changes
            # only the case that was wrong.
            output.parent / f"{output.name}-chunks",
            source_root,
            repo_root=repo_root,
        )
    print(_encode(summary).decode().rstrip())
    # `completed + repaid`, not `completed`. On a resumed run the chunks staged by
    # the earlier pass are not re-published, so gating on `completed` alone would
    # report a fully-staged corpus as a failure and invite a re-run that could
    # only produce the same answer. `repaid` is the same DISPOSITION — staged,
    # not re-published — and differs only in having cost money this pass; that
    # distinction belongs in the printed summary, not in the completeness gate,
    # which asks whether the corpus is whole.
    #
    # `repaid` now carries only chunks whose stage directory VERIFIED as that
    # chunk's evidence. Before that check this sum was the whole exit-0 story for
    # a directory nobody had looked inside, which is how a substituted directory
    # reported a complete corpus.
    staged = summary.completed + summary.repaid
    return 0 if staged == summary.chunk_total and summary.failed == 0 else 1


def corpus_main(repo_root: Path, args: list[str]) -> int:
    """CLI boundary for provider-free planning and read-only verification."""
    if not args or args[0] not in {"plan", "run", "verify"} or len(args) > _MAX_ARGS:
        print("kb-setup graphify-semantic-corpus plan|run|verify [PATH]")
        return 2
    action = args[0]
    output = (
        Path(args[1])
        if len(args) == _MAX_ARGS
        else repo_root / "graphify-out/graphify-semantic-corpus"
    )
    if action == "run" and not output.is_dir():
        return _abort(output, ("plan-unavailable",))
    if action in {"verify", "run"}:
        with tempfile.TemporaryDirectory(prefix="kb-graphify-corpus-verify-") as raw_source:
            source_root = Path(raw_source) / "graphify"
            admit_source(repo_root, source_root)
            verification = verify_plan(output, source_root)
        if action == "verify":
            print(_encode(verification).decode().rstrip())
            return 0 if verification.state == "complete" else 2
        if not verification.execution_authorized:
            return _abort(output, verification.reasons)
        return _execute_authorized(repo_root, output)
    with tempfile.TemporaryDirectory(prefix="kb-graphify-corpus-source-") as raw_source:
        source_root = Path(raw_source) / "graphify"
        source_pin = admit_source(repo_root, source_root)
        manifest = plan_source(
            source_root,
            output,
            source=source_pin,
        )
    print(_encode(manifest).decode().rstrip())
    return 0
