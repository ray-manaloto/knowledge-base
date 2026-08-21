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
  is lifted: the adapter writes its metadata to one fixed path, so two chunks in
  one process would race on it.
* **One call, chunked by the plan.** The whole corpus goes through a single
  ``extract_corpus_parallel`` at the plan's ``token_budget``, because that is the
  function the PLANNER used to build the committed ledger — replaying it
  reproduces the grouping rather than approximating it. Per-chunk staging happens
  in the ``on_chunk_done`` callback as each call completes.
* **Resumption is a local skip, and it is NOT free.** A chunk whose stage
  directory already holds VERIFIED evidence for that chunk is skipped rather than
  re-published, because ``stage_chunk`` refuses an occupied destination and a
  resumed run would otherwise abort on the first chunk it had already finished.
  Those chunks are counted as ``repaid``, never as ``completed`` — this pass did
  not publish that work — and ``repaid`` is the only such category because the
  skip cannot PREVENT the provider call, only the re-publication: it runs in the
  callback, which graphify reaches only once a result for the chunk exists.
  Nothing upstream of the callback avoids the cost either. ``extract_corpus_parallel``
  has no cache read anywhere in its call chain at the pinned 0.9.45 — the
  incremental cache is written from that entry point and never consulted — so a
  re-run re-buys every chunk at full price. Treat an interrupted run as costing
  its whole remaining corpus again, not its remainder.
* **A stage directory is verified, never trusted.** "Already staged" means
  ``verify_staged_chunk`` returned ``complete``: the four published members
  present and regular, and every payload's digest and byte length matching the
  receipt the writer left. A directory that exists but fails that check is a
  FAILURE naming its reasons, not a completed chunk — an unverified existence
  check let an unrelated directory stand in for all 58 stages and still exit 0.
* **Loud on partial completion.** ``RunSummary`` keeps completed, repaid, failed
  and never-attempted apart, and the caller returns non-zero unless every planned
  chunk is staged with no failures. A corpus missing a chunk looks exactly like a
  corpus that never had one, so the count is the gate, not the absence of an
  exception. Each callback is admitted at most once, so those counts stay a
  bijection onto the ledger rather than a tally of events.

The boundary marker deserves its own note, because its plumbing changed for a
reason that is easy to undo. The adapter is handed a DIRECTORY rather than a file
path: each invocation writes its own uniquely-named marker, so ``O_EXCL`` still
means one crossing per marker while a chunk whose call FAILED strands nothing.
Under the single-path spelling such a chunk never reached the rotation, and every
later chunk died on ``already exists`` — one recoverable error presenting as a
whole-corpus failure that named the wrong cause.
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
    atomic,
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
    # Staged by an earlier run, verified as that chunk's real evidence, and PAID
    # FOR AGAIN this pass. Kept apart from `completed` because "58 completed" on
    # a resumed run would claim this pass published work it did not publish.
    #
    # There is deliberately no `resumed` counterpart. One existed, meaning
    # "served free from graphify's cache", and it was measured to be unreachable:
    # `extract_corpus_parallel` has no cache read anywhere in its call chain at
    # the pinned 0.9.45, so a re-run re-buys every chunk. Naming a free category
    # that cannot occur told the operator a resumed run was cheap; it is not.
    repaid: int
    # Reached and lost: either the provider call raised, or the chunk staged with
    # refusal reasons. Distinct from `skipped`, which is never-attempted.
    failed: int
    skipped: int
    node_count: int
    edge_count: int
    hyperedge_count: int
    # Every provider call this pass could observe, summed. Not "what the corpus
    # cost": a chunk whose call died before writing its record contributes
    # nothing, so read this as a floor on spend, never as a receipt.
    spend_usd: float
    # Empty when the run reached the end of the ledger. Otherwise the reason it
    # stopped early, which is the only thing that tells a reader the counts below
    # are a partial accounting rather than a complete one.
    halted: str
    outcomes: tuple[ChunkOutcome, ...]


class _SpendCapError(Exception):
    """Raised from the chunk callback to stop a run that has spent its authority.

    An exception is the whole mechanism available: ``extract_corpus_parallel``
    exposes no cancellation, and its serial loop calls ``on_chunk_done`` bare —
    no ``try`` wraps the call — so a raise there propagates out of the extractor.
    That was verified against the pinned source rather than assumed, with the
    control being the branch immediately above it, which DOES swallow a failed
    chunk (``if exc is not None: … continue``); the callback has no such guard.

    ``execute`` catches this rather than letting it escape, because the summary
    naming what did land is the artifact an operator needs most on the run that
    stopped early.
    """


#: Where the cumulative spend total lives BETWEEN runs, beside the staged chunks
#: rather than in the run's temporary evidence directory.
SPEND_LEDGER = "spend-ledger.json"


class SpendLedger(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """The durable running total for one plan's namespace."""

    total_usd: float
    charges: int
    schema_version: int = 1


def read_spend_ledger_record(namespace_dir: Path) -> SpendLedger:
    """The whole durable record, not just its total.

    `charges` travels with `total_usd` because a ledger that reports
    `{"total_usd": 6.0, "charges": 1}` after three charges across two processes
    is a record that contradicts itself — and this file is the only place a
    finished run can be audited for what it spent. Cold lane, PR #339.
    """
    path = namespace_dir / SPEND_LEDGER
    try:
        return msgspec.json.decode(path.read_bytes(), type=SpendLedger, strict=True)
    except OSError, msgspec.DecodeError, msgspec.ValidationError:
        return SpendLedger(total_usd=0.0, charges=0)


def read_spend_ledger(namespace_dir: Path) -> float:
    """The spend already charged against this plan, across every previous run.

    An unreadable or malformed ledger returns 0.0 rather than raising, on
    ``observed_spend_usd``'s precedent — but the two defaults point OPPOSITE
    ways and that is deliberate. There, an unreadable record can only make the
    total too low, which delays the cap. Here it does the same, so this is the
    one place a corrupt file is dangerous: say so rather than hide it. The
    alternative — refusing to run at all on a stray byte — would make a
    resumable run unresumable, which is the failure this ledger exists to fix.
    """
    return read_spend_ledger_record(namespace_dir).total_usd


class _Spend:
    """Running provider spend for one plan, against its cumulative cap.

    Mutable and un-frozen on purpose — it is the one thing in this module that
    accumulates. It exists because nothing summed anything: the plan capped
    ``max_cost_usd`` PER CHUNK and ``--max-budget-usd`` per provider invocation,
    so 26 chunks (post-dedupe, #414; was 58 pre-dedupe) each individually
    within authority could spend far past any total anyone had approved.

    FOR ONE PLAN, NOT ONE PROCESS, and that distinction is the whole reason this
    class writes to disk. The first version seeded at 0.0 and summed records
    living in a ``TemporaryDirectory``, so both halves of the accounting died
    with the process: a run interrupted at chunk 30 — a crash, a timeout, a
    closed laptop, a SIGKILL — resumed with a fresh cap and could spend the whole
    limit again. Measured on the first real chunk: three restarts is three times
    the approved total, and nothing on disk would have said so, because
    ``ChunkStageReceipt`` carries no cost field either. The 26-chunk run takes
    ~4.8 h at concurrency 1 (was 58 chunks / ~10.6 h pre-dedupe), which makes a
    restart the expected case rather than the unlucky one.
    """

    def __init__(self, limit_usd: float, ledger_dir: Path | None = None) -> None:
        self.limit_usd = limit_usd
        self.ledger_dir = ledger_dir
        carried = (
            read_spend_ledger_record(ledger_dir)
            if ledger_dir is not None
            else SpendLedger(total_usd=0.0, charges=0)
        )
        self.carried_usd = carried.total_usd
        self.total_usd = carried.total_usd
        # Seeded, not reset. `charges` is the ledger's own audit field, and a
        # resumed run that rewrote it as 1 after three charges made the record
        # contradict its own total.
        self.charges = carried.charges

    def charge(self, amount: float) -> None:
        self.total_usd += amount
        self.charges += 1
        self._persist()

    def _persist(self) -> None:
        """Write the running total through before the next call can be made.

        Written on EVERY charge rather than at the end, for the same reason the
        ledger exists at all: a total that is only durable once the run finishes
        is not durable on the runs that do not.
        """
        if self.ledger_dir is None:
            return
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        atomic.write_text(
            self.ledger_dir / SPEND_LEDGER,
            msgspec.json.encode(
                SpendLedger(total_usd=self.total_usd, charges=self.charges)
            ).decode()
            + "\n",
        )

    @property
    def exceeded(self) -> bool:
        return self.total_usd > self.limit_usd


def seeded_spend(limit_usd: float, ledger_dir: Path) -> _Spend:
    """Build the cap seeded from this plan's durable ledger, and refuse a spent one.

    A standalone function rather than three lines inside `execute`, for the reason
    this repo has recorded twice: `execute` is invoked by no test — it needs a real
    plan, a real clone and a real provider — so anything living inside it is
    unarmed by construction. An armed decision with an unarmed consumer is the
    shape that ships. Here the decision IS the consumer, so it is put somewhere a
    fixture can reach.

    The already-exceeded refusal is not decoration. It is the case a resumable cap
    creates: a run that hit the cap at chunk 40 and was restarted must refuse
    BEFORE the first provider call, not discover it after paying for chunk 41.
    """
    ledger_dir_str = str(ledger_dir)
    spend = _Spend(limit_usd, ledger_dir)
    if spend.carried_usd:
        print(
            f"[corpus] resuming against {spend.carried_usd:.2f} USD already charged to this "
            f"plan (cap {spend.limit_usd:.2f}); ledger {ledger_dir_str}/{SPEND_LEDGER}"
        )
    if spend.exceeded:
        raise _SpendCapError(
            f"cumulative provider spend {spend.total_usd:.2f} USD already exceeds the plan's "
            f"max_total_cost_usd of {spend.limit_usd:.2f} USD — no chunk was run"
        )
    return spend


def observed_spend_usd(boundary_dir: Path) -> float:
    """Sum every per-call spend record currently in the boundary directory.

    Per CALL, not per chunk, and that distinction is the reason this reads the
    records rather than the adapter metadata. graphify's adaptive retry bisects a
    chunk and merges, firing ONE callback for N calls, while the metadata file is
    a single fixed path each call overwrites — so summing metadata undercounts
    exactly the chunks that cost the most.

    A malformed or unreadable record is skipped rather than raised on. The
    alternative is a run that dies on a stray file in a directory it does not own
    exclusively; the cap's job is to stop overspending, and an unreadable record
    can only make the total too LOW, which the cap then handles by not firing
    early rather than by firing wrongly.
    """
    if not boundary_dir.is_dir():
        return 0.0
    total = 0.0
    for record_path in sorted(boundary_dir.glob("provider-spend-*.json")):
        try:
            record = msgspec.json.decode(
                record_path.read_bytes(),
                type=graphify_semantic_adapter.ProviderSpendRecord,
                strict=True,
            )
        except OSError, msgspec.DecodeError, msgspec.ValidationError:
            continue
        total += record.total_cost_usd
    return total


def assert_canonical_evidence(boundary_dir: Path, metadata_path: Path) -> None:
    """Refuse an evidence location the provider boundary marker cannot be written to.

    Called from `_RunContext.__post_init__`, which is the point of it.
    `trusted_evidence_dir` is the fix for the unresolved-`$TMPDIR` defect and is
    exhaustively armed — but its only consumer is `execute`, which no test invokes,
    so deleting that one call would leave every test green and every chunk failing
    again. An armed decision with an unarmed consumer is a shape this repo has
    shipped before, so the invariant is enforced where the value is RECEIVED rather
    than trusted to the caller that produced it: a symlinked or relative spelling is
    rejected when the context is built, before any provider call is attempted.

    A standalone function rather than the body of `__post_init__` so it is reachable
    from a test without constructing a whole context — which would need the real
    plan on disk, and the real plan is gitignored, so that test would SKIP on a
    fresh clone and the guard would be uncovered exactly where it matters.

    `metadata_path` is checked through its PARENT because the property is about the
    DIRECTORY components the marker walk traverses. Stated precisely, because the
    first version of this comment claimed the leaf spelling would be wrong and a
    mutation proved otherwise: `Path.resolve()` is non-strict, so for a leaf that
    does not exist yet it returns the same canonical path either way, and the two
    spellings are equivalent for every case reachable here. The parent form is kept
    because it says what is meant, not because it catches something the other misses.
    """
    for label, directory in (
        ("boundary_dir", boundary_dir),
        ("metadata_path parent", metadata_path.parent),
    ):
        if directory != directory.resolve():
            raise ValueError(
                f"{label} is not canonical: {directory} — the provider boundary "
                "marker is opened with O_NOFOLLOW, so any symlink component refuses "
                "it (see trusted_evidence_dir)"
            )


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
    boundary_dir: Path

    def __post_init__(self) -> None:
        """Refuse a non-canonical evidence directory at the type boundary."""
        assert_canonical_evidence(self.boundary_dir, self.metadata_path)


@contextmanager
def _temporary_environment(overlay: Mapping[str, str | None]) -> Generator[None]:
    """Apply an environment overlay for one call and restore it exactly.

    A ``None`` VALUE means "ensure this name is absent", not "leave it alone".
    That distinction is the fix for a real gap: an overlay can only override
    names it mentions, so a config with caching ENABLED simply omitted
    ``GRAPHIFY_NO_INCREMENTAL_CACHE`` — and an ambient ``=1`` from the operator's
    shell or a CI job then survived into the run. graphify reads that name for
    truthiness, so every checkpoint was skipped while the execution receipt
    recorded caching as enabled: a cold run wearing a warm run's evidence.

    ``None`` is also the restore sentinel for "was absent", for the same reason
    in reverse — restoring an absent name as ``""`` would leave it defined and
    falsy where it had been undefined. Same shape, different fact.
    """
    previous = {name: os.environ.get(name) for name in overlay}
    for name, value in overlay.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
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


def trusted_evidence_dir(raw: str) -> Path:
    """Canonicalise this driver's OWN temporary evidence directory.

    A function rather than an inline `.resolve()` so the property has somewhere to
    be tested: on Linux a `tempfile` path usually has no symlink component, so a
    test that merely compared the two spellings would pass vacuously on the very
    platform where the bug is invisible. See `execute` for the measurement.
    """
    return Path(raw).resolve()


def _adapter_overlay(context: _RunContext, adapter_dir: Path) -> dict[str, str | None]:
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
    overlay: dict[str, str | None] = {
        "PATH": f"{adapter_dir}{os.pathsep}{original_path}",
        "KB_SEMANTIC_REAL_CLAUDE": str(real_path),
        "KB_SEMANTIC_REAL_CLAUDE_SHA256": runtime.executable_sha256,
        "KB_SEMANTIC_ORIGINAL_PATH": original_path,
        "KB_SEMANTIC_METADATA_PATH": str(context.metadata_path),
        "KB_SEMANTIC_PROVIDER_BOUNDARY_DIR": str(context.boundary_dir),
        # The PLAN's cap, not the profile's literal. The profile still carries one
        # as the floor for a launcher with no plan behind it; this is the value a
        # human authorized, resolved once at plan time from the model's real
        # ceiling. It reaches the child as a VALUE for an existing variable, so
        # `environment_names` — the only environment fact the receipt compares —
        # is unchanged.
        graphify_semantic_slice.MAX_OUTPUT_TOKENS_ENV_NAME: str(config.claude_max_output_tokens),
        graphify_semantic_slice.PROFILE_ENV_NAME: _PROFILE.name,
        "GRAPHIFY_CLAUDE_CLI_MODEL": _PROFILE.model,
        "GRAPHIFY_API_TIMEOUT": str(config.timeout_seconds),
    }
    overlay.update(incremental_cache_env(config))
    return overlay


def incremental_cache_env(
    config: graphify_semantic_corpus.CorpusExecutionConfig,
) -> dict[str, str | None]:
    """Return the cache control variable, or an explicit REMOVAL when caching is on.

    Split out of the overlay so it is testable without a real Claude binary,
    because the thing it encodes is a trap rather than a setting. graphify reads
    the variable for TRUTHINESS — ``if os.environ.get("GRAPHIFY_NO_INCREMENTAL_CACHE")``
    — so ``"0"`` reads as "yes, disable the cache". Enabling the cache means the
    name must be ABSENT from the child environment.

    ``None`` rather than an empty mapping, and that is the correction: omitting
    the key left an ambient ``=1`` from the operator's shell or a CI job in
    place, so the run skipped every checkpoint while its receipt recorded caching
    as enabled. Absence has to be asserted, not assumed.
    """
    return {"GRAPHIFY_NO_INCREMENTAL_CACHE": "1" if config.graphify_no_incremental_cache else None}


def _extract_corpus(
    paths: list[Path],
    context: _RunContext,
    *,
    semantic_cache: Path,
    environment: Mapping[str, str | None],
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


def _rotate_evidence(metadata_path: Path, boundary_dir: Path) -> tuple[bytes, int]:
    """Read this chunk's adapter metadata, COUNT its provider calls, and rotate.

    Only the METADATA path still needs rotating. The boundary marker no longer
    does: the driver hands the adapter a DIRECTORY, so each invocation writes its
    own uniquely-named marker and ``O_EXCL`` still means one crossing per marker.
    Under the previous single-path spelling a chunk whose provider call FAILED
    never reached this function, stranding its marker and making every later
    chunk die on ``already exists`` — one recoverable error becoming a
    whole-corpus failure that named the wrong cause.

    Markers are cleared anyway, in a ``finally``, so a long run does not
    accumulate one file per chunk in a directory nothing prunes.

    THE COUNT IS THE POINT, and it used to be thrown away. graphify's
    ``_extract_with_adaptive_retry`` recurses on halves and merges, then
    ``on_chunk_done`` fires ONCE — so a retried chunk makes N provider calls and
    yields one merged fragment, while the adapter's metadata lives at a single
    fixed path that every call overwrites. The callback therefore reads the LAST
    LEAF's metadata against the WHOLE CHUNK's fragment, and the prompt digests
    cannot agree. The chunk was already refused for that, but as
    ``provider-prompt-bytes-mismatch`` — a reason describing corrupted evidence,
    for a run whose evidence was merely incomplete — and the receipt still
    recorded ``attempts=1`` after three calls.
    ``_DIR`` mode exists precisely because "``…_PATH`` cannot serve a multi-call
    run", so the markers proving N calls were being collected all along and
    deleted unexamined. Counting them is what turns that into a diagnosis.
    """
    markers = (
        len(tuple(boundary_dir.glob("provider-boundary-*.json"))) if boundary_dir.is_dir() else 0
    )
    try:
        metadata_raw = metadata_path.read_bytes()
    except OSError as exc:
        raise ValueError("semantic adapter metadata is unavailable") from exc
    finally:
        clear_stale_evidence(metadata_path, boundary_dir)
    return metadata_raw, markers


def clear_stale_evidence(metadata_path: Path, boundary_dir: Path) -> None:
    """Drop the metadata file and every marker currently in the boundary directory.

    Used before the first call as well as between chunks, because a run killed
    mid-call (a timeout, a SIGKILL) leaves both behind. ``missing_ok`` throughout:
    absence is the normal case and is not an error.
    """
    metadata_path.unlink(missing_ok=True)
    if boundary_dir.is_dir():
        # Spend records are cleared alongside the markers, and every caller of
        # this function charges them FIRST. Clearing them here rather than in
        # their own function is what keeps that pairing visible: a record that
        # survived a rotation would be charged again by the next chunk.
        for pattern in ("provider-boundary-*.json", "provider-spend-*.json"):
            for stale in boundary_dir.glob(pattern):
                stale.unlink(missing_ok=True)


def _stage_completed_chunk(
    raw: object,
    chunk: graphify_semantic_corpus.PlannedChunk,
    context: _RunContext,
) -> ChunkOutcome:
    """Turn one completed provider call into staged, validated chunk evidence."""
    config = context.config
    # `normalize_fragment`, NOT `semantic_fragment`. The latter asserts the scope
    # and raises, which for the corpus means one under-covered chunk aborts the
    # whole extraction; `stage_chunk` below applies the same check per chunk and
    # records it as a refusal reason, so the run survives to stage the other 57.
    fragment = graphify_semantic_slice.normalize_fragment(raw)
    # Bytes, unnormalized: `stage_chunk` digests exactly what the adapter wrote.
    # Decoding and re-encoding here would digest this module's serializer instead
    # of the provider's own evidence, and the two agree only by luck.
    metadata_raw, provider_calls = _rotate_evidence(context.metadata_path, context.boundary_dir)
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
        # OBSERVED, not asserted. This was a hardcoded `1`, which was false for
        # every chunk graphify bisected — three provider calls reported as one
        # attempt, in committed evidence.
        #
        # It is deliberately NOT a refusal on its own. The count comes from the
        # boundary directory, and that directory is not chunk-scoped: a chunk
        # whose provider call FAILS never reaches this callback (graphify's
        # serial path does `if exc is not None: ... continue`), so its marker is
        # never cleared and lands in the NEXT chunk's count. A guard keyed on
        # this number alone therefore turned one failure into two and misnamed
        # the second — the exact defect it was written to remove.
        #
        # `_provider_chunk_reasons` owns the discrimination instead, because it
        # already holds the signal that is actually chunk-scoped: whether the
        # retained metadata's prompt digest matches the prompt rebuilt from THIS
        # chunk's full member list. A bisect fails that; a stray marker does not
        # affect it.
        attempts=provider_calls,
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
        # The RUN's one live measurement, taken once by `execute()`'s preflight
        # -- never the plan's own recorded value, which would make the staging
        # comparison a tautology (#426 round 2, cold review P2-2).
        live_runtime=context.preflight_receipt.graphify_runtime,
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


class _Accounting(msgspec.Struct, frozen=True):
    """What one pass observed, gathered so the summary can be derived from it.

    A struct rather than six parameters for the same reason ``_RunContext`` is
    one: these travel together and only together, and passed individually they
    make a signature where two same-typed arguments can be transposed without a
    type error.
    """

    outcomes: list[ChunkOutcome]
    repaid: list[int]
    spend: _Spend
    halted: str


def _summarize(
    context: _RunContext,
    accounting: _Accounting,
    result: Mapping[str, object] | dict[str, object],
) -> RunSummary:
    """Reduce one pass's observations and graphify's own counters into the summary."""
    outcomes = accounting.outcomes
    completed = tuple(item for item in outcomes if item.status == "complete")
    staged_failures = tuple(item for item in outcomes if item.status != "complete")
    # graphify counts a chunk whose provider call raised; it never reaches the
    # callback, so it leaves no outcome. Reading that count is what separates
    # "the provider failed on it" from "it was never attempted" — the previous
    # version folded both into `skipped`, which reported a paid, failed call as
    # though the run had simply not got to it.
    provider_failures = graphify_semantic_slice.result_integer(result, "failed_chunks")
    if provider_failures < 0:
        # `result_integer` returns -1 for a MISSING key, and its docstring says
        # that sentinel exists precisely so absent and zero do not reduce to the
        # same number. Clamping it to 0 here reduced them to the same number —
        # the sentinel was created and then discarded one line later. A graphify
        # release that stopped emitting `failed_chunks` would have reported zero
        # provider failures and inflated `skipped`, in the summary a human reads
        # to decide whether the corpus is whole.
        raise ValueError("graphify result omitted failed_chunks")
    planned = len(context.ledger.chunks)
    accounted = len(outcomes) + len(accounting.repaid) + provider_failures
    return RunSummary(
        schema_id="graphify-semantic-corpus-run/v0",
        run_namespace_sha256=context.run_namespace,
        chunk_total=planned,
        completed=len(completed),
        repaid=len(accounting.repaid),
        failed=len(staged_failures) + provider_failures,
        # Only what the run genuinely never reached. A negative would mean more
        # outcomes than planned chunks, which the callback's ledger check already
        # refuses — clamping keeps a nonsense number out of a summary a human
        # reads to decide whether the corpus is complete.
        skipped=max(planned - accounted, 0),
        node_count=sum(item.node_count for item in completed),
        edge_count=sum(item.edge_count for item in completed),
        hyperedge_count=sum(item.hyperedge_count for item in completed),
        spend_usd=accounting.spend.total_usd,
        halted=accounting.halted,
        outcomes=tuple(outcomes),
    )


def _resolve_existing_stage(
    chunk: graphify_semantic_corpus.PlannedChunk,
    reasons: tuple[str, ...],
    context: _RunContext,
) -> ChunkOutcome | None:
    """Dispose of a chunk whose stage directory already exists.

    ``None`` means REPAID — the directory verified as this chunk's own evidence,
    so this pass must not re-publish it. ``stage_chunk`` REFUSES an existing
    destination (correctly; silently overwriting published evidence is worse), so
    without this branch a resumed run aborts on the first chunk it had already
    completed.

    There is deliberately no "resumed" (free) disposition, and that is a
    measurement rather than a simplification. An AST walk of the pinned 0.9.45
    finds no cache read anywhere in ``extract_corpus_parallel``'s call chain
    (``_run_one`` -> ``_extract_with_adaptive_retry`` -> ``extract_files_direct``);
    ``load_cached`` is reached only from ``graphify/extract.py``, an entry point
    this driver never uses. The probe discriminates — the same walk does find
    ``_checkpoint_chunk``, the WRITER, on this path. So every already-staged chunk
    is paid for again. If a future graphify serves this entry point from cache,
    re-derive that before adding a free branch back; do not restore it on the
    strength of the name.

    Any reasons at all mean a directory is sitting where this chunk's evidence
    belongs and is not this chunk's evidence. There is no repair path from here,
    so the only honest disposition is a failure naming what is wrong and letting
    the operator remove it. Counting it as done is the behaviour this replaced.

    The rotation is NOT skipped with the staging. Returning without it leaves this
    chunk's metadata file and its ``O_EXCL`` boundary marker in place, so the very
    next chunk dies on ``provider boundary marker already exists`` — the cascade
    the callback exists to prevent, reintroduced by the fix for a different
    finding.
    """
    clear_stale_evidence(context.metadata_path, context.boundary_dir)
    if not reasons:
        return None
    return ChunkOutcome(
        ordinal=chunk.ordinal,
        total=chunk.total,
        status="failed",
        node_count=0,
        edge_count=0,
        hyperedge_count=0,
        reasons=tuple(f"chunk-stage-unverifiable: {reason}" for reason in reasons),
    )


def _stage_or_failure(
    raw: object,
    chunk: graphify_semantic_corpus.PlannedChunk,
    context: _RunContext,
) -> ChunkOutcome:
    """Stage one completed chunk, or turn the reason it cannot be into an outcome.

    One unusable chunk must not take the other 57 with it. Four reachable paths
    raise from ``_stage_completed_chunk``: ``normalize_fragment`` on a malformed
    result, ``_rotate_evidence`` on absent adapter metadata, the metadata decode
    (a ``msgspec.DecodeError``, which subclasses ``ValueError`` at the pinned
    msgspec 0.21.1, so naming it here would be redundant), and ``stage_chunk``'s
    filesystem writes, whose ``mkdir``, ``write_text`` and ``replace`` raise
    ``OSError``. Any of them propagates out through ``extract_corpus_parallel``
    and out of ``execute``, past the caller's ``print``. The chunks already staged
    survived on disk, but the summary naming them never printed, so the operator
    lost the one artifact that says what landed.

    The evidence is rotated on the way out so the next chunk starts clean;
    skipping that is how a single recoverable error became ``provider boundary
    marker already exists`` for every chunk after it.
    """
    try:
        return _stage_completed_chunk(raw, chunk, context)
    except (TypeError, ValueError, OSError) as exc:
        clear_stale_evidence(context.metadata_path, context.boundary_dir)
        return ChunkOutcome(
            ordinal=chunk.ordinal,
            total=chunk.total,
            status="failed",
            node_count=0,
            edge_count=0,
            hyperedge_count=0,
            reasons=(f"chunk-staging-failed: {exc}",),
        )


def _verified_stages(context: _RunContext) -> dict[int, tuple[str, ...]]:
    """Map each already-present stage directory to why it is NOT usable, or ``()``.

    VERIFIED, not merely present. This used to be a set comprehension over
    ``chunk_stage_dir(...).exists()``, and a cold cross-family lane showed exactly
    what that bought: substituting an unrelated directory for every stage produced
    "58 accounted, 0 failed, success". Existence is a claim about the filesystem;
    the driver needs a claim about the EVIDENCE.

    ``verify_staged_chunk`` is not new code written for this fix — it already
    existed in ``graphify_semantic_corpus``, rehashing every payload against the
    digests and byte lengths the writer itself recorded, refusing a symlinked or
    non-regular directory, and refusing an entry set that is not exactly the four
    published members. The defect was never a missing verifier. It was that
    nothing on this path CALLED the one that was already there, which is the only
    reason a validator can be thorough and still gate nothing.
    """
    staged: dict[int, tuple[str, ...]] = {}
    for chunk in context.ledger.chunks:
        destination = graphify_semantic_corpus.chunk_stage_dir(
            context.cache_root, context.run_namespace, chunk.ordinal
        )
        # `lstat`, via `is_symlink`, so a dangling or redirected stage is a
        # candidate for verification rather than invisible: `exists()` follows the
        # link and answers about the TARGET.
        if not destination.exists() and not destination.is_symlink():
            continue
        verification = graphify_semantic_corpus.verify_staged_chunk(
            context.cache_root,
            graphify_semantic_corpus.ChunkStageReference(
                candidate=context.candidate,
                source_root=context.source_root,
                cache_namespace=context.config.cache_namespace_sha256,
                run_namespace=context.run_namespace,
                chunk=chunk,
            ),
        )
        staged[chunk.ordinal] = () if verification.state == "complete" else verification.reasons
    return staged


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


def _assert_graphify_runtime_unchanged_since_plan(
    preflight_receipt: graphify_semantic_slice.ClaudePreflight,
    config: graphify_semantic_corpus.CorpusExecutionConfig,
) -> None:
    """Refuse to spend when the Graphify runtime moved since the plan was written (#426).

    Mirrors `_adapter_overlay`'s "Claude executable changed after preflight" check
    above, for the Graphify half of the identity rather than the Claude half.
    `verify_plan` already refused a plan whose recorded runtime disagreed with the
    installed one at VERIFY time; this catches the runtime moving in the gap
    BETWEEN a verified `run` dispatch and the moment `execute` actually reaches a
    provider — the same window `_adapter_overlay`'s check exists to close for
    Claude.
    """
    live, plan = preflight_receipt.graphify_runtime, config.graphify_runtime
    differing = [
        field.name
        for field in msgspec.structs.fields(live)
        if getattr(live, field.name) != getattr(plan, field.name)
    ]
    if preflight_receipt.graphify_version != config.graphify_version:
        differing.append("graphify_version")
    if differing:
        # Name the fields that differ, not just the two top-level version
        # strings: those agree whenever it is `RuntimeIdentity`'s whole-struct
        # comparison that actually fired -- a re-locked wheel digest, a moved
        # executable path, or an SDK signature change at one version all used
        # to print `plan=0.9.48 live=0.9.48`, a refusal asserting that two
        # identical values differ (cold review P2-4).
        raise ValueError(
            f"Graphify runtime changed after plan: differing field(s) {', '.join(differing)} -- "
            f"plan={config.graphify_runtime!r} live={preflight_receipt.graphify_runtime!r}"
        )


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
    # Scrubbed before ANYTHING else — before the plan even loads — so a forbidden
    # routing name ambient in this process can never reach the preflight below or
    # any `claude` child this run spawns (#334). See
    # `graphify_semantic_slice.scrub_route_overrides`. Reported through
    # `report_routing_scrub`, the same as the slice's own call sites (cold
    # review P1-1): the removed names are emitted, never their values, so a
    # scrubbed run is distinguishable from a clean one after the fact.
    graphify_semantic_slice.report_routing_scrub(
        "execute", graphify_semantic_slice.scrub_route_overrides()
    )
    inventory, ledger, config = _load_plan(candidate)
    run_namespace = _run_namespace(candidate, config.cache_namespace_sha256)
    preflight_receipt = graphify_semantic_slice.preflight(
        repo_root, require_max_turns=True, profile=_PROFILE
    )
    # BEFORE anything that spends.
    _assert_graphify_runtime_unchanged_since_plan(preflight_receipt, config)
    outcomes: list[ChunkOutcome] = []
    repaid: list[int] = []
    # Persistent, and keyed on the CACHE namespace rather than the run namespace,
    # so checkpoints accumulate across runs in one tree instead of one tree per
    # run. That is where graphify WRITES them; it does not read them back on this
    # entry point, so this buys durability for other consumers of the cache, not
    # a discount for the next run.
    semantic_cache = cache_root / config.cache_namespace_sha256 / "semantic-cache"
    semantic_cache.mkdir(parents=True, exist_ok=True)

    with (
        tempfile.TemporaryDirectory(prefix="kb-corpus-adapter-") as bin_dir,
        tempfile.TemporaryDirectory(prefix="kb-corpus-evidence-") as evidence_dir,
    ):
        # RESOLVED via `trusted_evidence_dir`, and that one call is the difference
        # between a corpus that can
        # be extracted and one that cannot. `write_provider_boundary_start` opens
        # every component of this directory with `O_NOFOLLOW`, so a single symlink
        # anywhere in the path refuses the marker — and `$TMPDIR` on macOS is
        # `/var/folders/…`, where **`/var` is a symlink to `private/var`**. Passing
        # the path as `tempfile` spells it therefore failed EVERY chunk with
        # `provider boundary marker destination is unavailable`: measured 58/58 on
        # 2026-08-17, the first time this driver was run on a real plan.
        #
        # The fix is here rather than in `open_directory_nofollow`, which must keep
        # refusing symlinks: resolving inside that primitive would silently weaken
        # it for every caller, including the ones whose path components an attacker
        # could swap. This caller owns its temp directory and knows it is trusted,
        # so it is the one that may canonicalise it.
        #
        # Why it was never seen: the semantic SLICE writes its evidence to
        # `graphify-out/graphify-semantic-slice/`, an in-repo path with no symlink
        # component, and the slice is the only path that had ever run.
        evidence = trusted_evidence_dir(evidence_dir)
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
            boundary_dir=evidence,
        )
        overlay = _adapter_overlay(context, Path(bin_dir))

        clear_stale_evidence(context.metadata_path, context.boundary_dir)
        staged = _verified_stages(context)
        # Ordinals seen so far, so a repeated callback cannot be counted twice.
        # The range check below is necessary and was never sufficient: accounting
        # counts EVENTS, and `skipped` clamps its own negative, so two callbacks
        # for one index silently absorbed an index that never arrived. That is a
        # hole in the corpus reported as `skipped=0`.
        visited: set[int] = set()

        spend = seeded_spend(config.max_total_cost_usd, context.cache_root / context.run_namespace)

        def on_chunk_done(index: int, total: int, raw: object) -> None:
            """Admit one chunk, charge what it spent, and stop if that exhausts the cap.

            The charge happens BEFORE the disposition and outside every branch,
            which is the only placement that counts all of them: a chunk that was
            already staged is paid for again (graphify serves nothing from cache
            on this entry point), and a chunk that fails to stage was paid for
            too. Charging inside the staging path would have counted only the
            branch that succeeds — a spend cap blind to the runs that go wrong.

            The check happens AFTER, so the chunk that crossed the cap is still
            staged. Its cost is already sunk; discarding its evidence would spend
            the money and keep nothing for it.
            """
            _admit(index, total)
            spend.charge(observed_spend_usd(context.boundary_dir))
            _dispose(index, raw)
            if spend.exceeded:
                raise _SpendCapError(
                    f"cumulative provider spend {spend.total_usd:.2f} USD exceeded the plan's "
                    f"max_total_cost_usd of {spend.limit_usd:.2f} USD after chunk {index + 1}"
                )

        def _admit(index: int, total: int) -> None:
            # The ledger's ordering IS graphify's, because the planner derived it
            # from the same packing function over the same inputs. Checked rather
            # than assumed: a divergence would file evidence against the WRONG
            # chunk, and this is the cheapest place to notice.
            #
            # It is NOT the only place, and the previous version of this comment
            # claimed it was — it said every downstream digest check would
            # "confirm as internally consistent" what this one missed. That is
            # backwards, and a cold lane traced why: `_provider_chunk_reasons`
            # recomputes `expected_prompt_sha256` from the ASSUMED chunk's members
            # and compares it against `metadata.prompt_sha256`, which the ADAPTER
            # wrote from the bytes actually dispatched. That digest is ground
            # truth this driver cannot influence, so a real ordering divergence
            # surfaces as `provider-prompt-bytes-mismatch` whether or not the
            # check below fires.
            #
            # The correction matters more than the guard: a comment overstating
            # what a check carries is what stops the next reader from looking for
            # the one that actually carries it. This check earns its place by
            # failing EARLY and by name, not by being the last line of defence.
            if total != len(ledger.chunks) or not 0 <= index < len(ledger.chunks):
                raise ValueError("provider chunk callback disagrees with the planned ledger")
            # Range says the index is ADDRESSABLE; uniqueness says the run is
            # still a bijection onto the ledger. Raising rather than tolerating,
            # because a duplicate means the driver's model of graphify's fan-out
            # is wrong, and every count downstream is derived from that model.
            if index in visited:
                raise ValueError(f"provider chunk callback repeated index {index}")
            visited.add(index)

        def _dispose(index: int, raw: object) -> None:
            """File this chunk's evidence, or the reason it has none."""
            chunk = ledger.chunks[index]
            if chunk.ordinal in staged:
                outcome = _resolve_existing_stage(chunk, staged[chunk.ordinal], context)
                if outcome is None:
                    repaid.append(chunk.ordinal)
                else:
                    outcomes.append(outcome)
                return
            outcomes.append(_stage_or_failure(raw, chunk, context))

        halted = ""
        try:
            result = _extract_corpus(
                admitted_paths(inventory, source_root),
                context,
                semantic_cache=semantic_cache,
                environment=overlay,
                on_chunk_done=on_chunk_done,
            )
        except _SpendCapError as exc:
            # graphify's own counters are UNOBSERVABLE here: the raise leaves
            # `extract_corpus_parallel` before it returns its merged dict, so
            # `failed_chunks` for the chunks it did attempt is lost with it.
            # Substituting a zero would be a claim; `halted` is the disclosure
            # that makes every count below a floor rather than an accounting, and
            # the chunks the run never reached still land in `skipped`, so the
            # completeness gate fails as it should.
            halted = str(exc)
            result = {"failed_chunks": 0}

    return _summarize(
        context,
        _Accounting(outcomes=outcomes, repaid=repaid, spend=spend, halted=halted),
        result,
    )
