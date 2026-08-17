# Copyright (c) 2026 Raymond Manaloto
"""Turn staged semantic-corpus chunks into ONE committed extraction chunk.

`kb-graphify-semantic-corpus` exposes `plan|run|verify` and stops there: `run`
stages each chunk's evidence under
`<cache_root>/<run-namespace>/chunks/<ordinal>/` and nothing carries those
fragments into the aggregate graph. This module is that missing step, and it is
deliberately the LAST one before the existing house path rather than a new
ingestion route — it writes `sources/extractions/<name>-docs.json` via
`chunks.assemble`, after which `mise run kb-merge -- <chunk>` is unchanged.

WHY A SEPARATE MODULE, and not a fourth subcommand on the runner. The plan's
`execution-config.json` digests five files: `graphify_semantic_corpus.py` itself
(`planner_sha256`), the adapter, the slice, `graphify_llm` and
`graphify_semantic_corpus_run.py`. Editing any of them moves the digest,
`AUTHORITY_JSON` no longer authorizes the plan, and the 474-unit/58-chunk plan has
to be re-planned before it can be executed. A new file is in none of those
digests, so the merge step can be built, tested and armed while a plan sits ready
to spend against.

TWO GAPS THIS CLOSES, both measured 2026-08-17 on the real fragment the earlier
semantic-SLICE run left behind, so neither cost a provider call to find:

1. `_origin` is never set anywhere in the pipeline. `normalize_fragment` admits
   `_origin in (None, "semantic")` and the adapter emits neither, so every staged
   node arrives with `_origin=None`. `kb-validate-chunks` refuses that outright,
   and merging it anyway is the silent half: graphify 0.9.32+ infers the tier from
   `source_location`, reads `L<line>` as AST, and drops the node from
   `graph-prose.json` — which is the surface `kb-query --prose` reads. 629 nodes
   were lost that way once already. Stamped on NODES ONLY, because that is the
   committed convention, not a guess:
   `sources/extractions/graphify-2026-08-06-docs.json` carries `semantic` on
   796/796 nodes and `None` on 1099/1099 edges.
2. Every staged fragment is named `semantic-fragment.json`, and
   `chunks.assemble`'s id-collision gate keyed on the basename — so all 58 shared
   one label and no cross-chunk collision could ever be reported. That gate is
   fixed in `chunks._labels`; this module additionally writes each chunk out under
   its own ordinal-bearing name, so the refusal names something a reader can act
   on and the gate does not depend on a caller's naming discipline.

WHAT THIS MODULE DOES NOT DO. It never calls a provider and never merges. It
refuses on any doubt about the staged evidence rather than assembling a partial
corpus quietly, because a short graph that merged cleanly is the failure mode that
reads as success.
"""

from __future__ import annotations

import json
from pathlib import Path

import msgspec

from kb_setup import chunks, events
from kb_setup.graphify_semantic_corpus import (
    ChunkLedger,
    ChunkStageReceipt,
    PlannedChunk,
    encode_canonical,
    sha256_bytes,
    sha256_path,
)


class _ConfigView(msgspec.Struct, frozen=True):
    """The ONE execution-config field this step reads.

    Narrow and permissive on purpose, rather than decoding the planner's whole
    `CorpusExecutionConfig`. Two reasons, and the first is the load-bearing one:
    the config file's identity is already pinned by `execution_config_sha256` in
    every staged receipt, so the strong check is the digest over its bytes, and a
    full strict decode adds no binding this step does not already have. The second
    is that a merge step which cannot decode a config it does not own becomes
    unbuildable in a test and coupled to every future planner field.
    """

    cache_namespace_sha256: str


def cache_root_for(candidate: Path) -> Path:
    """Where `run` staged this plan's chunk evidence.

    Derived from the plan directory exactly as `_execute_authorized` derives it,
    and for the same reason it does: a caller who named a plan location outside the
    repository must get that location's chunks, not the repository's.
    """
    return candidate.parent / f"{candidate.name}-chunks"


class StagedChunk(msgspec.Struct, frozen=True):
    """One staged chunk that passed every local integrity check."""

    ordinal: int
    total: int
    namespace: str
    path: Path
    node_count: int
    edge_count: int
    hyperedge_count: int
    source_paths: tuple[str, ...]


def _plan_members(candidate: Path) -> tuple[ChunkLedger, _ConfigView]:
    """The two plan files this step reads: the ledger strictly, the config narrowly."""
    ledger = msgspec.json.decode(
        (candidate / "chunk-ledger.json").read_bytes(), type=ChunkLedger, strict=True
    )
    config = msgspec.json.decode(
        (candidate / "execution-config.json").read_bytes(), type=_ConfigView, strict=False
    )
    return ledger, config


def _chunk_reasons(
    receipt: ChunkStageReceipt,
    fragment_raw: bytes,
    planned: dict[int, PlannedChunk],
    candidate: Path,
    config: _ConfigView,
) -> list[str]:
    """Bind one staged receipt to THIS plan, locally, with no source clone.

    `verify_staged_chunk` is the exhaustive check and needs a `source_root`, i.e. a
    fresh pinned clone. These checks are the subset that answers the only question
    assembly has to settle — are these bytes the ones this plan's run staged, and
    did the run judge the chunk whole — and they answer it offline. Anything
    stronger is `mise run kb-graphify-semantic-corpus -- verify`, which exists.

    This binding is also what makes the run namespace discoverable WITHOUT
    re-deriving it (see `discover`): a staged directory whose receipts agree with
    this plan's manifest, execution config and chunk packing is this plan's run, by
    content rather than by a path convention two modules could spell differently.
    """
    reasons: list[str] = []
    if receipt.status != "complete":
        reasons.append(f"chunk-status-{receipt.status}")
    reasons.extend(f"run-reason:{r}" for r in receipt.reasons)
    reasons.extend(f"run-error:{e}" for e in receipt.errors)
    if sha256_bytes(fragment_raw) != receipt.fragment_sha256:
        reasons.append("fragment-digest-mismatch")
    if len(fragment_raw) != receipt.fragment_size:
        reasons.append("fragment-size-mismatch")
    if receipt.cache_namespace_sha256 != config.cache_namespace_sha256:
        reasons.append("cache-namespace-mismatch")
    chunk = planned.get(receipt.chunk_ordinal)
    if chunk is None:
        reasons.append("chunk-not-in-ledger")
    else:
        if receipt.chunk_total != chunk.total:
            reasons.append("chunk-total-mismatch")
        # The digest that actually binds the staged evidence to this plan's
        # packing. Without it a chunk staged against an earlier ledger — same
        # ordinal, different member list — assembles without complaint.
        if receipt.chunk_sha256 != sha256_bytes(encode_canonical(chunk)):
            reasons.append("chunk-digest-mismatch")
    if receipt.plan_manifest_sha256 != sha256_path(candidate / "manifest.json"):
        reasons.append("chunk-plan-manifest-mismatch")
    if receipt.execution_config_sha256 != sha256_path(candidate / "execution-config.json"):
        reasons.append("chunk-execution-config-mismatch")
    return reasons


def _stamp_origin(fragment: dict[str, object]) -> tuple[dict[str, object], int]:
    """Set `_origin="semantic"` on every node; return the fragment and how many.

    Nodes only — see the module docstring for the measured convention. An absent
    value is filled and an existing one is left alone; a DISAGREEING one cannot
    reach here, because `normalize_fragment` refuses anything that is neither
    `None` nor `"semantic"` before the chunk is ever staged.
    """
    stamped = 0
    nodes = fragment.get("nodes")
    if not isinstance(nodes, list):
        return fragment, 0
    for node in nodes:
        if isinstance(node, dict) and node.get("_origin") is None:
            node["_origin"] = "semantic"
            stamped += 1
    return fragment, stamped


def _namespace_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if (p / "chunks").is_dir())


def discover(
    candidate: Path,
    *,
    cache_root: Path | None = None,
) -> tuple[dict[str, list[StagedChunk]], list[str]]:
    """Group every staged chunk that binds to this plan, by run namespace.

    Identity comes from the receipts, not from a re-derivation of the namespace
    hash. `graphify_semantic_corpus` publishes `chunk_stage_dir` so that no second
    module forms its own opinion about where evidence lives; re-deriving the
    namespace half of that path here would be exactly the opinion it forbids, and
    the alternative — importing the driver's private `_run_namespace` — is
    unavailable because publishing an alias there would move `runner_sha256` and
    de-authorize the standing plan.

    So a directory is this plan's run when its chunks say so and the plan agrees.
    Returned grouped rather than flattened: two namespaces both binding to one plan
    is a state a caller must be told about, never one to silently pick from.
    """
    ledger, config = _plan_members(candidate)
    root = cache_root if cache_root is not None else cache_root_for(candidate)
    planned = {chunk.ordinal: chunk for chunk in ledger.chunks}
    grouped: dict[str, list[StagedChunk]] = {}
    reasons: list[str] = []
    for namespace_dir in _namespace_dirs(root):
        namespace = namespace_dir.name
        for ordinal in sorted(planned):
            stage = namespace_dir / "chunks" / f"{ordinal:04d}"
            if not stage.is_dir():
                continue
            try:
                receipt = msgspec.json.decode(
                    (stage / "receipt.json").read_bytes(), type=ChunkStageReceipt, strict=True
                )
                fragment_raw = (stage / "semantic-fragment.json").read_bytes()
            except (OSError, msgspec.DecodeError) as exc:
                reasons.append(f"{namespace[:12]}/chunk-{ordinal:04d}: unreadable evidence: {exc}")
                continue
            if receipt.run_namespace_sha256 != namespace:
                reasons.append(f"{namespace[:12]}/chunk-{ordinal:04d}: run-namespace-mismatch")
                continue
            problems = _chunk_reasons(receipt, fragment_raw, planned, candidate, config)
            if problems:
                reasons.extend(f"{namespace[:12]}/chunk-{ordinal:04d}: {p}" for p in problems)
                continue
            grouped.setdefault(namespace, []).append(
                StagedChunk(
                    ordinal=ordinal,
                    total=receipt.chunk_total,
                    namespace=namespace,
                    path=stage / "semantic-fragment.json",
                    node_count=receipt.node_count,
                    edge_count=receipt.edge_count,
                    hyperedge_count=receipt.hyperedge_count,
                    source_paths=receipt.source_paths,
                )
            )
    return grouped, reasons


def collect(
    candidate: Path,
    *,
    cache_root: Path | None = None,
    allow_partial: bool = False,
) -> tuple[list[StagedChunk], list[str]]:
    """The single run's staged chunks, or every reason there is not exactly one.

    `allow_partial` is the ONLY way to accept fewer chunks than the ledger plans,
    and it exists for one purpose: proving this path end to end on chunk 1 of 58
    before the other 57 are paid for. Without it a short corpus is a refusal,
    because that is the failure that reads as success.
    """
    ledger, _config = _plan_members(candidate)
    grouped, reasons = discover(candidate, cache_root=cache_root)
    if not grouped:
        reasons.append("no staged chunk binds to this plan")
        return [], reasons
    if len(grouped) > 1:
        reasons.append(
            "staged chunks from "
            f"{len(grouped)} run namespaces bind to this plan: "
            + ", ".join(sorted(n[:12] for n in grouped))
        )
        return [], reasons
    accepted = sorted(next(iter(grouped.values())), key=lambda c: c.ordinal)
    planned_total = len(ledger.chunks)
    if len(accepted) != planned_total and not allow_partial:
        reasons.append(
            f"staged {len(accepted)} of {planned_total} planned chunk(s); "
            "pass --partial to assemble anyway (a short corpus merges cleanly "
            "and is the failure that reads as success)"
        )
    return accepted, reasons


def _staging_dir(candidate: Path) -> Path:
    return candidate.parent / f"{candidate.name}-assembly"


def assemble(
    repo_root: Path,
    candidate: Path,
    name: str,
    *,
    cache_root: Path | None = None,
    allow_partial: bool = False,
) -> tuple[Path, list[StagedChunk]]:
    """Stamp, name and union-assemble the staged chunks into one committed chunk.

    Raises ValueError with every reason on any refusal — from `collect` above or
    from `chunks.assemble`, which owns per-chunk schema validation and both
    cross-chunk collision gates. Nothing is written on a refusal.
    """
    accepted, reasons = collect(candidate, cache_root=cache_root, allow_partial=allow_partial)
    if reasons:
        raise ValueError(
            f"semantic corpus merge refused ({len(reasons)} reason(s)):\n  " + "\n  ".join(reasons)
        )
    staging = _staging_dir(candidate)
    # CLEARED, not merely created. A prior merge of a different chunk set leaves its
    # `chunk-NNNN.json` files behind; they are not passed to `chunks.assemble` (only
    # this run's `paths` are), so they change no output — but a directory holding a
    # mix of two runs' intermediates is a reproducibility trap for the next reader,
    # who has no way to tell which files this artifact was built from. Only the
    # ordinal-named files this function owns are removed, so an unrelated file
    # someone put here is left alone rather than silently deleted.
    staging.mkdir(parents=True, exist_ok=True)
    for stale in staging.glob("chunk-[0-9][0-9][0-9][0-9].json"):
        stale.unlink()
    paths: list[Path] = []
    for staged in accepted:
        fragment, _stamped = _stamp_origin(json.loads(staged.path.read_bytes()))
        # The ordinal-bearing name. `chunks.assemble` no longer DEPENDS on distinct
        # names for its gate to fire, but its messages still read better for one,
        # and a reader tracing a refusal wants the chunk number.
        out = staging / f"chunk-{staged.ordinal:04d}.json"
        out.write_text(json.dumps(fragment, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        paths.append(out)
    return chunks.assemble(repo_root, name, paths), accepted


def merge_main(repo_root: Path, args: list[str]) -> int:
    """CLI boundary: assemble staged corpus chunks into a committed doc chunk."""
    positional = [a for a in args if not a.startswith("--")]
    flags = {a for a in args if a.startswith("--")}
    max_positional = 2
    if not positional or len(positional) > max_positional or flags - {"--partial"}:
        print("kb-setup graphify-semantic-corpus-merge <name> [PLAN_DIR] [--partial]")
        return 2
    name = positional[0]
    candidate = (
        Path(positional[1])
        if len(positional) == max_positional
        else repo_root / "graphify-out/graphify-semantic-corpus"
    )
    if not candidate.is_dir():
        events.fail(
            "corpus_merge.no_plan",
            f"[kb-graphify-semantic-corpus-merge] no plan directory: {candidate}",
            plan=str(candidate),
        )
        return 2
    try:
        out, accepted = assemble(repo_root, candidate, name, allow_partial="--partial" in flags)
    except (ValueError, OSError, msgspec.DecodeError) as exc:
        events.fail("corpus_merge.refused", f"[kb-graphify-semantic-corpus-merge] {exc}")
        return 1
    nodes = sum(c.node_count for c in accepted)
    edges = sum(c.edge_count for c in accepted)
    hyperedges = sum(c.hyperedge_count for c in accepted)
    relative = out.relative_to(repo_root)
    print(
        f"[kb-graphify-semantic-corpus-merge] assembled {len(accepted)}/{accepted[0].total} "
        f"chunk(s) -> {relative}: {nodes} nodes, {edges} edges, {hyperedges} hyperedges"
    )
    print(f"[kb-graphify-semantic-corpus-merge] next: mise run kb-merge -- {relative}")
    return 0
