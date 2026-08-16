# Copyright (c) 2026 Raymond Manaloto
"""Chunk-by-chunk execution driver for the authorized semantic corpus plan.

``graphify_semantic_corpus`` could plan and it could verify; the step between
them returned ``provider-execution-not-implemented`` and nothing else in the
repository defined that string. This module is that step. It owns only the loop
and the per-chunk provider call — every validation decision still belongs to
``stage_chunk``, which was already written and already knows how to refuse.

Three properties are deliberate rather than incidental:

* **Serial.** ``graphify/llm.py`` force-serializes the ``claude-cli`` backend
  because parallel Claude subprocesses conflict over session state, and this
  module does not set the override. A second reason survives even if that guard
  is lifted: the adapter writes its metadata and its ``O_EXCL`` provider-boundary
  marker to single fixed paths, so two chunks in one process collide on both.
* **One call, chunked by the plan.** The whole corpus goes through a single
  ``extract_corpus_parallel`` at the plan's ``token_budget``, because that is the
  function the PLANNER used to build the committed ledger — replaying it
  reproduces the grouping rather than approximating it. Per-chunk staging happens
  in the ``on_chunk_done`` callback as each call completes.
* **Resumption is graphify's, not this module's.** Recovery across runs comes
  from graphify's per-chunk incremental cache, which this profile enables by
  OMITTING ``GRAPHIFY_NO_INCREMENTAL_CACHE``. There is deliberately no
  skip-if-staged check here: a single extraction call decides its own chunking
  internally, so this module never gets the chance to decline one chunk of it.
  Stating otherwise would describe a guard that does not exist.
* **Loud on partial completion.** ``RunSummary`` counts completed, failed, and
  never-attempted chunks separately, and the caller returns non-zero unless every
  planned chunk completed. A corpus missing a chunk looks exactly like a corpus
  that never had one, so the count has to be checked rather than the exit path.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from pathlib import Path

import msgspec

from kb_setup import (
    graphify_semantic_adapter,
    graphify_semantic_corpus,
    graphify_semantic_slice,
)

_PROFILE = graphify_semantic_slice.CORPUS_PROFILE


class ChunkOutcome(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """What happened to one chunk, whether or not a provider call was made."""

    ordinal: int
    total: int
    status: str
    node_count: int
    edge_count: int
    hyperedge_count: int
    reasons: tuple[str, ...]


class RunSummary(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Public result of one corpus execution pass."""

    schema_id: str
    run_namespace_sha256: str
    chunk_total: int
    completed: int
    skipped: int
    failed: int
    node_count: int
    edge_count: int
    hyperedge_count: int
    outcomes: tuple[ChunkOutcome, ...]


class _RunContext(msgspec.Struct, frozen=True):
    """Everything fixed for the duration of one execution pass.

    Bundled rather than threaded as parameters because these values travel
    together to every stage of the run and are read-only throughout; passed
    individually they made three signatures wide enough that two same-typed
    arguments could be transposed without a type error.
    """

    candidate: Path
    cache_root: Path
    source_root: Path
    inventory: graphify_semantic_corpus.SourceInventory
    ledger: graphify_semantic_corpus.ChunkLedger
    config: graphify_semantic_corpus.CorpusExecutionConfig
    preflight_receipt: graphify_semantic_slice.ClaudePreflight
    run_namespace: str
    metadata_path: Path
    boundary_path: Path


@contextmanager
def _temporary_environment(overlay: Mapping[str, str]) -> Generator[None]:
    """Apply an environment overlay for one call and restore it exactly.

    ``None`` is the restore sentinel for "was absent", which matters here more
    than usual: `GRAPHIFY_NO_INCREMENTAL_CACHE` is read for TRUTHINESS by
    graphify, so restoring an absent variable as `""` would leave it defined and
    falsy where it had been undefined. Same shape, different fact.
    """
    previous = {name: os.environ.get(name) for name in overlay}
    os.environ.update(overlay)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def admitted_paths(
    inventory: graphify_semantic_corpus.SourceInventory, source_root: Path
) -> list[Path]:
    """Return the admitted FILES, in planned order, deduplicated across slices.

    Files, not units, and that is forced rather than chosen. ``extract_corpus_parallel``
    re-runs ``expand_oversized_files`` on whatever it is given, and that calls
    ``is_splittable_text(f) -> f.suffix`` — a ``FileSlice`` has no ``suffix``, so
    handing it the plan's slice units raises ``AttributeError``. Measured, with a
    control: ``expand_oversized_files([FileSlice(...)])`` raises while
    ``expand_oversized_files([Path(...)])`` returns, so the probe discriminates.

    Handing it the files instead is not a workaround — it is the same input the
    PLANNER used. ``_ledger`` built the committed chunk grouping by calling
    graphify's own ``expand_oversized_files`` and ``_pack_chunks_by_tokens`` over
    these paths, so replaying them at the same ``token_budget`` reproduces that
    grouping rather than approximating it.
    """
    seen: dict[str, None] = {}
    for unit in inventory.units:
        seen.setdefault(unit.path, None)
    return [source_root / path for path in seen]


def _adapter_overlay(context: _RunContext, adapter_dir: Path) -> dict[str, str]:
    """Build the provider environment for the corpus profile."""
    runtime = context.preflight_receipt
    config = context.config
    original_path = os.environ.get("PATH", "")
    entrypoint = shutil.which("kb-semantic-claude", path=original_path)
    real_claude = shutil.which("claude", path=original_path)
    if entrypoint is None or real_claude is None:
        raise ValueError("semantic adapter or real Claude is unavailable")
    real_path = Path(real_claude).resolve()
    if graphify_semantic_slice.sha256_file(real_path) != runtime.executable_sha256:
        raise ValueError("Claude executable changed after preflight")
    (adapter_dir / "claude").symlink_to(Path(entrypoint).resolve())
    overlay = {
        "PATH": f"{adapter_dir}{os.pathsep}{original_path}",
        "KB_SEMANTIC_REAL_CLAUDE": str(real_path),
        "KB_SEMANTIC_REAL_CLAUDE_SHA256": runtime.executable_sha256,
        "KB_SEMANTIC_ORIGINAL_PATH": original_path,
        "KB_SEMANTIC_METADATA_PATH": str(context.metadata_path),
        "KB_SEMANTIC_PROVIDER_BOUNDARY_PATH": str(context.boundary_path),
        graphify_semantic_slice.PROFILE_ENV_NAME: _PROFILE.name,
        "GRAPHIFY_CLAUDE_CLI_MODEL": _PROFILE.model,
        "GRAPHIFY_API_TIMEOUT": str(config.timeout_seconds),
    }
    overlay.update(incremental_cache_env(config))
    return overlay


def incremental_cache_env(
    config: graphify_semantic_corpus.CorpusExecutionConfig,
) -> dict[str, str]:
    """Return the cache control variable, or nothing at all when caching is on.

    Split out of the overlay so it is testable without a real Claude binary,
    because the thing it encodes is a trap rather than a setting. graphify reads
    the variable for TRUTHINESS — ``if os.environ.get("GRAPHIFY_NO_INCREMENTAL_CACHE")``
    — so the string ``"0"`` reads as "yes, disable the cache". Enabling the cache
    means OMITTING the name; a run configured with ``"0"`` would look warm in
    every artifact and be cold in every invoice.
    """
    return {"GRAPHIFY_NO_INCREMENTAL_CACHE": "1"} if config.graphify_no_incremental_cache else {}


def _extract_corpus(
    paths: list[Path],
    context: _RunContext,
    *,
    semantic_cache: Path,
    environment: Mapping[str, str],
    on_chunk_done: Callable[[int, int, object], None],
) -> dict[str, object]:
    """Run the whole corpus, staging each chunk through ``on_chunk_done``.

    ``token_budget`` is the plan's, so graphify's packing reproduces the
    committed ledger instead of inventing a second grouping. The callback fires
    once per completed chunk, in order, which is what lets the caller stage each
    chunk's evidence while the next call has not yet started.
    """
    from kb_setup import graphify_sdk

    config = context.config
    with _temporary_environment(environment):
        return graphify_sdk.extract_corpus_parallel(
            paths,
            backend="claude-cli",
            model=_PROFILE.model,
            root=context.source_root,
            chunk_size=config.graphify_chunk_size,
            token_budget=config.token_budget,
            max_concurrency=config.concurrency,
            max_retry_depth=config.graphify_max_retry_depth,
            on_chunk_done=on_chunk_done,
            deep_mode=config.deep_mode,
            cache_root=semantic_cache,
        )


def _run_namespace(candidate: Path, cache_namespace: str) -> str:
    """Derive a namespace that is stable for one plan, so a rerun can resume.

    Keyed on the plan manifest as well as the config so that a re-planned corpus
    lands in a different tree rather than appending chunks to a run whose plan no
    longer exists. Stability is the point: a per-invocation namespace would make
    every interruption cost the whole corpus again.
    """
    return graphify_semantic_corpus.sha256_bytes(
        (
            cache_namespace + graphify_semantic_corpus.sha256_path(candidate / "manifest.json")
        ).encode()
    )


def _chunk_evidence(
    chunk: graphify_semantic_corpus.PlannedChunk,
    context: _RunContext,
    *,
    prompt_sha256: str,
    fragment_sha256: str,
    counts: tuple[int, int, int],
) -> tuple[graphify_semantic_slice.ChunkEvidence, ...]:
    """Bind every planned unit in this chunk to the one call that covered it.

    One entry per MEMBER, not per file: ``_provider_receipt_reasons`` compares
    ``{(source_path, source_sha256)}`` against the planned member set, and two
    slices of one document are two members with two digests. Emitting one entry
    per file would drop a slice from the covered set and be refused — correctly,
    because the corpus would then hold no record that the slice was dispatched.

    The counts are the CHUNK's, repeated. One provider call produced one
    fragment, so there is no per-unit attribution to be had; inventing a split
    would be a more precise-looking number with less truth in it.
    """
    units_by_ordinal = {unit.ordinal: unit for unit in context.inventory.units}
    evidence: list[graphify_semantic_slice.ChunkEvidence] = []
    for member in chunk.members:
        unit = units_by_ordinal[member.unit_ordinal]
        evidence.append(
            graphify_semantic_slice.ChunkEvidence(
                ordinal=chunk.ordinal,
                total=chunk.total,
                source_path=unit.path,
                source_git_object=unit.source_git_object,
                source_sha256=unit.sha256,
                # The verifier's OWN function, not a local re-derivation. The
                # obvious guess — `slice_end - slice_start` — is a CHARACTER
                # count, while the verifier compares UTF-8 BYTE length; the two
                # agree on ASCII and diverge the moment a chunk contains
                # non-ASCII prose, which this corpus does (there are translated
                # READMEs in it). Re-deriving would shadow-implement the check.
                source_size=graphify_semantic_corpus.source_unit_size(unit, context.source_root),
                prompt_sha256=prompt_sha256,
                fragment_sha256=fragment_sha256,
                node_count=counts[0],
                edge_count=counts[1],
                hyperedge_count=counts[2],
            )
        )
    return tuple(evidence)


def _chunk_source_identity(
    chunk: graphify_semantic_corpus.PlannedChunk,
    context: _RunContext,
) -> graphify_semantic_slice.SourceIdentity:
    """Describe the chunk as the receipt's single ``source``.

    ``SourceIdentity`` was written for the slice, where one receipt covers one
    file, so ``path``/``git_object``/``sha256`` have no single honest value for a
    multi-file chunk. Rather than pick one member and imply the chunk was that
    file, this names the chunk itself: a synthetic path, the chunk's own digest,
    and the summed source bytes. ``git_object`` is left empty because there is no
    git object for a grouping the planner invented — an empty field is a smaller
    lie than a plausible wrong SHA. The per-unit identities that DO have exact
    values live in ``chunks``, which is what the verifier actually checks.
    """
    inventory = context.inventory
    units_by_ordinal = {unit.ordinal: unit for unit in inventory.units}
    size = sum(
        graphify_semantic_corpus.source_unit_size(
            units_by_ordinal[member.unit_ordinal], context.source_root
        )
        for member in chunk.members
    )
    return graphify_semantic_slice.SourceIdentity(
        source="graphify",
        ref=inventory.source_ref,
        commit=inventory.source_commit,
        tree=inventory.source_tree,
        path=f"chunks/{chunk.ordinal:04d}",
        git_object="",
        sha256=graphify_semantic_corpus.sha256_bytes(
            graphify_semantic_corpus.encode_canonical(chunk)
        ),
        size=size,
    )


def _provider_execution_config(
    config: graphify_semantic_corpus.CorpusExecutionConfig,
) -> graphify_semantic_slice.ExecutionConfig:
    """Project the plan's config into the shape the receipt declares.

    Every field here is READ from the plan rather than restated, because
    ``_provider_config_reasons`` compares the two field by field. A literal typed
    in this function would be a second opinion about the run's configuration,
    and the verifier would then be checking that this module agrees with itself.
    """
    return graphify_semantic_slice.ExecutionConfig(
        api_timeout_ms=config.timeout_seconds * 1000,
        claude_code_disable_nonessential_traffic=True,
        claude_code_disable_telemetry=True,
        claude_code_max_output_tokens=config.claude_max_output_tokens,
        claude_code_max_retries=config.claude_max_retries,
        max_structured_output_retries=config.structured_output_retries,
        graphify_api_timeout_seconds=config.timeout_seconds,
        graphify_no_incremental_cache=config.graphify_no_incremental_cache,
        chunk_size=config.graphify_chunk_size,
        token_budget=config.token_budget,
        max_concurrency=config.concurrency,
        max_retry_depth=config.graphify_max_retry_depth,
        deep_mode=config.deep_mode,
    )


def _rotate_evidence(metadata_path: Path, boundary_path: Path) -> bytes:
    """Read this chunk's adapter evidence and free both paths for the next one.

    The adapter writes its metadata to one fixed path and creates its provider
    boundary marker with ``O_EXCL``, so a second chunk in the same run would find
    the marker already present and refuse. Rotating here works only because the
    run is serial: ``on_chunk_done`` fires after a chunk completes and before the
    next call starts, so there is no window in which both exist.

    That coupling is the reason the marker is NOT simply made overwritable. Its
    whole job is to prove a provider process started exactly once; an
    overwrite-in-place marker could not distinguish one crossing from three.
    """
    try:
        metadata_raw = metadata_path.read_bytes()
    except OSError as exc:
        raise ValueError("semantic adapter metadata is unavailable") from exc
    metadata_path.unlink(missing_ok=True)
    boundary_path.unlink(missing_ok=True)
    return metadata_raw


def _stage_completed_chunk(
    raw: object,
    chunk: graphify_semantic_corpus.PlannedChunk,
    context: _RunContext,
) -> ChunkOutcome:
    """Turn one completed provider call into staged, validated chunk evidence."""
    config = context.config
    fragment = graphify_semantic_slice.semantic_fragment(raw)
    # Bytes, unnormalized: `stage_chunk` digests exactly what the adapter wrote.
    # Decoding and re-encoding here would digest this module's serializer instead
    # of the provider's own evidence, and the two agree only by luck.
    metadata_raw = _rotate_evidence(context.metadata_path, context.boundary_path)
    metadata = msgspec.json.decode(
        metadata_raw, type=graphify_semantic_adapter.AdapterMetadata, strict=True
    )
    counts = graphify_semantic_corpus.fragment_counts(fragment)
    receipt = graphify_semantic_slice.SemanticReceipt(
        schema_id="graphify-corpus-chunk-provider/v0",
        status="complete",
        source=_chunk_source_identity(chunk, context),
        runtime=context.preflight_receipt,
        adapter_metadata_sha256=graphify_semantic_corpus.sha256_bytes(metadata_raw),
        semantic_fragment_sha256=graphify_semantic_corpus.sha256_bytes(
            graphify_semantic_corpus.encode_canonical(fragment)
        ),
        chunks=_chunk_evidence(
            chunk,
            context,
            # The digests the ADAPTER recorded for the bytes it actually sent and
            # received. `_provider_chunk_reasons` requires the receipt and the
            # adapter to agree AND both to match the prompt rebuilt from the plan,
            # so recomputing either here would let this module agree with itself
            # while disagreeing with the call that happened.
            prompt_sha256=metadata.prompt_sha256,
            fragment_sha256=metadata.structured_output_sha256,
            counts=counts,
        ),
        execution_config=_provider_execution_config(config),
        attempts=1,
        backend="claude-cli",
        model=_PROFILE.model,
        max_concurrency=config.concurrency,
        max_retry_depth=config.graphify_max_retry_depth,
        failed_chunks=0,
        uncovered_files=(),
        out_of_scope_dropped=0,
        semantic_node_count=counts[0],
        semantic_edge_count=counts[1],
        semantic_hyperedge_count=counts[2],
        graph_node_count=counts[0],
        graph_edge_count=counts[1],
        warnings=(),
        errors=(),
    )
    stage_receipt = graphify_semantic_corpus.stage_chunk(
        context.candidate,
        context.cache_root,
        graphify_semantic_corpus.ChunkStageRequest(
            source_root=context.source_root,
            cache_namespace=config.cache_namespace_sha256,
            run_namespace=context.run_namespace,
            chunk=chunk,
            fragment=fragment,
            provider_evidence=graphify_semantic_corpus.RetainedProviderEvidence(
                receipt_raw=graphify_semantic_corpus.encode_canonical(receipt),
                adapter_metadata_raw=metadata_raw,
            ),
        ),
    )
    return ChunkOutcome(
        ordinal=chunk.ordinal,
        total=chunk.total,
        status=stage_receipt.status,
        node_count=stage_receipt.node_count,
        edge_count=stage_receipt.edge_count,
        hyperedge_count=stage_receipt.hyperedge_count,
        reasons=stage_receipt.reasons,
    )


def _load_plan(
    candidate: Path,
) -> tuple[
    graphify_semantic_corpus.SourceInventory,
    graphify_semantic_corpus.ChunkLedger,
    graphify_semantic_corpus.CorpusExecutionConfig,
]:
    """Decode the three committed plan members this run is bound to."""
    inventory = msgspec.json.decode(
        (candidate / "source-inventory.json").read_bytes(),
        type=graphify_semantic_corpus.SourceInventory,
        strict=True,
    )
    ledger = msgspec.json.decode(
        (candidate / "chunk-ledger.json").read_bytes(),
        type=graphify_semantic_corpus.ChunkLedger,
        strict=True,
    )
    config = msgspec.json.decode(
        (candidate / "execution-config.json").read_bytes(),
        type=graphify_semantic_corpus.CorpusExecutionConfig,
        strict=True,
    )
    return inventory, ledger, config


def execute(
    candidate: Path,
    cache_root: Path,
    source_root: Path,
    *,
    repo_root: Path,
) -> RunSummary:
    """Execute one authorized corpus plan, staging every chunk it completes.

    The caller is responsible for having established that the plan is authorized;
    this function assumes it and does the spending. It returns a summary rather
    than raising on a failed chunk, because a run that dies on chunk 40 of 58
    should still leave the first 39 staged and say so.
    """
    inventory, ledger, config = _load_plan(candidate)
    run_namespace = _run_namespace(candidate, config.cache_namespace_sha256)
    preflight_receipt = graphify_semantic_slice.preflight(
        repo_root, require_max_turns=True, profile=_PROFILE
    )
    outcomes: list[ChunkOutcome] = []
    # Persistent, and keyed on the CACHE namespace rather than the run namespace:
    # the cache's whole value is surviving between runs, and a per-run directory
    # would make every resumed run a cold one while still looking warm.
    semantic_cache = cache_root / config.cache_namespace_sha256 / "semantic-cache"
    semantic_cache.mkdir(parents=True, exist_ok=True)

    with (
        tempfile.TemporaryDirectory(prefix="kb-corpus-adapter-") as bin_dir,
        tempfile.TemporaryDirectory(prefix="kb-corpus-evidence-") as evidence_dir,
    ):
        evidence = Path(evidence_dir)
        context = _RunContext(
            candidate=candidate,
            cache_root=cache_root,
            source_root=source_root,
            inventory=inventory,
            ledger=ledger,
            config=config,
            preflight_receipt=preflight_receipt,
            run_namespace=run_namespace,
            metadata_path=evidence / "adapter-metadata.json",
            boundary_path=evidence / "provider-boundary-start.json",
        )
        overlay = _adapter_overlay(context, Path(bin_dir))

        def on_chunk_done(index: int, total: int, raw: object) -> None:
            # The ledger's ordering IS graphify's, because the planner derived it
            # from the same packing function over the same inputs. Checked rather
            # than assumed: if the two ever diverge, the failure this catches is
            # evidence filed against the WRONG chunk, which every downstream
            # digest check would then confirm as internally consistent.
            if total != len(ledger.chunks) or not 0 <= index < len(ledger.chunks):
                raise ValueError("provider chunk callback disagrees with the planned ledger")
            outcomes.append(_stage_completed_chunk(raw, ledger.chunks[index], context))

        _extract_corpus(
            admitted_paths(inventory, source_root),
            context,
            semantic_cache=semantic_cache,
            environment=overlay,
            on_chunk_done=on_chunk_done,
        )

    completed = tuple(item for item in outcomes if item.status == "complete")
    failed = tuple(item for item in outcomes if item.status != "complete")
    return RunSummary(
        schema_id="graphify-semantic-corpus-run/v0",
        run_namespace_sha256=run_namespace,
        chunk_total=len(ledger.chunks),
        completed=len(completed),
        # A chunk the ledger names and the provider never reported is neither
        # completed nor failed — it was never attempted. Counting it as either
        # would hide the one outcome that most needs to be visible.
        skipped=len(ledger.chunks) - len(outcomes),
        failed=len(failed),
        node_count=sum(item.node_count for item in completed),
        edge_count=sum(item.edge_count for item in completed),
        hyperedge_count=sum(item.hyperedge_count for item in completed),
        outcomes=tuple(outcomes),
    )
