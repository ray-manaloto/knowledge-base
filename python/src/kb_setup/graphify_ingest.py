# Copyright (c) 2026 Raymond Manaloto
"""NORMAL knowledge-source ingestion through Graphify's managed CLI seam."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path, PurePosixPath

from kb_setup import chunks, graphify_execution, graphify_sdk
from kb_setup.graphify_env import assert_pinned_graphify

_KINDS = {"article", "doc", "designdoc", "research_json", "inventory", "article_partial"}
_MIN_CAPTURE_YEAR = 1970
_TASK_ROOT = Path(".agent/kb/graphify-ingest")
_RUNS_ROOT = _TASK_ROOT / "runs"
_SCRATCH_ROOT = _TASK_ROOT / "scratch"
_CACHE_ROOT = _TASK_ROOT / "cache"
_HELP = """Usage: mise run kb-graphify-ingest -- REQUEST.json

REQUEST.json requires:
  capturedAt  real ISO date YYYY-MM-DD
  scratchDir  output directory beneath .agent/kb/graphify-ingest/scratch/
  sources     non-empty array of {key,path,url,kind?,note?,sourceFile?}

Optional request fields:
  backend        claude-cli (default) or openai-cli
  model          backend model override (defaults: opus / gpt-5.6-sol)
  effort         reasoning override (defaults: xhigh / high)
  cacheRoot      compatible cache beneath .agent/kb/graphify-ingest/cache/
  timeoutSeconds per-source CLI timeout (default: 300)
  maxAttempts    total CLI launches across this request (default: 8)
  totalTimeoutSeconds total case wall time (default: 1800)
  fallbackBackend explicit alternate CLI, only after zero primary successes
  fallbackModel / fallbackEffort optional alternate selectors

This route uses subscription CLIs only; provider API credentials are refused.
"""
_KIND_NOTES = {
    "designdoc": (
        "NOTE: this is one of OUR OWN design docs. Extract the DECISIONS, invariants, "
        "components, and their rationales so the design is graph-queryable. Faithful rationales."
    ),
    "research_json": (
        "NOTE: this file is JSON of structured research agent-outputs. Extract the DESIGN "
        "PATTERNS and findings as concept nodes with faithful rationales; connect related patterns."
    ),
    "article_partial": (
        "NOTE: this fetch is PARTIAL (JS-rendered; body may be thin but the section TABLE OF "
        "CONTENTS came through). Extract section-level concepts from the TOC with the best "
        "rationale the titles and surrounding text support. Do not fabricate claims."
    ),
}


@dataclass(frozen=True, slots=True)
class Source:
    """One validated source descriptor from the former Workflow contract."""

    key: str
    path: Path
    url: str
    kind: str = "doc"
    note: str = ""
    source_file: str | None = None

    def __post_init__(self) -> None:
        """Reject identifiers that could become filesystem traversal."""
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", self.key):
            raise ValueError("source key must be one lowercase filesystem-safe component")


@dataclass(frozen=True, slots=True)
class IngestSourceRequest:
    """Filesystem, source, and profile inputs for one NORMAL source."""

    repo_root: Path
    scratch_dir: Path
    source: Source
    captured_at: str
    profile: dict
    run_root: Path | None = None
    cache_root: Path | None = None
    timeout_seconds: float = 300.0
    execution_budget: graphify_execution.ExecutionBudget | None = None
    fallback_profile: dict | None = None


@dataclass(frozen=True, slots=True)
class _UncachedCliAttempt:
    request: IngestSourceRequest
    prompt: str
    run_root: Path
    run_context: dict


def source_file_for(source: Source) -> str:
    """Preserve the Workflow's explicit, clone-qualified, then basename precedence."""
    if source.source_file:
        return _safe_source_file(source.source_file)
    match = re.search(r"/sources/([^/]+/.+)$", source.path.as_posix())
    return _safe_source_file(match.group(1) if match else source.path.name)


def _safe_source_file(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("sourceFile must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != value
    ):
        raise ValueError("sourceFile must be a canonical relative path without traversal")
    return path.as_posix()


def _runtime_path(repo_root: Path, candidate: Path, *, label: str, boundary: Path) -> Path:
    """Resolve one write destination beneath its task-owned runtime boundary."""
    runtime_root = (repo_root / boundary).resolve(strict=False)
    anchored = candidate if candidate.is_absolute() else repo_root / candidate
    resolved = anchored.resolve(strict=False)
    try:
        resolved.relative_to(runtime_root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay under {runtime_root}") from exc
    return resolved


def validate_captured_at(value: str) -> str:
    """Return a real canonical ISO date, rejecting the old frozen-date failure mode."""
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("capturedAt is required and must be a real ISO date YYYY-MM-DD") from exc
    if parsed.year < _MIN_CAPTURE_YEAR or parsed.isoformat() != value:
        raise ValueError("capturedAt is required and must be a real ISO date YYYY-MM-DD")
    return value


def _common_prompt(source: Source, captured_at: str, body: str) -> str:
    source_file = source_file_for(source)
    note = f"\nContext: {source.note}" if source.note else ""
    kind_note = f"\n\n{_KIND_NOTES[source.kind]}" if source.kind in _KIND_NOTES else ""
    return f"""You are a knowledge-graph extractor for a graphify KB. The complete source bytes
are embedded below and came from:
  {source.path}{note}

Produce ONLY a graphify DOC-EXTRACTION CHUNK JSON object:
  {{ "nodes": [...], "edges": [...], "hyperedges": [...], "input_tokens": 0, "output_tokens": 0 }}

NODE object (exact keys):
  id          : globally-unique snake_case slug; MUST start with "{source.key}_".
  label       : short human name of the concept/entity.
  _origin     : "semantic" (EXACTLY this literal on EVERY node).
  file_type   : "concept"
  source_file : "{source_file}"
  source_url  : "{source.url}"
  captured_at : "{captured_at}"
  author      : the author name if the source states one, else null
  contributor : null
  rationale   : 1-3 substantive, self-contained sentences faithful to the source.

EDGE object (exact keys):
  source, target   : node ids that BOTH exist in this chunk.
  relation         : snake_case verb.
  confidence       : "EXTRACTED" when stated; "INFERRED" when reasoned.
  confidence_score : 1 for EXTRACTED, 0.5 for INFERRED.
  source_file      : "{source_file}"
  weight           : 1

EDGE DIRECTION: read each as "<source> <relation> <target>" and emit the direction
that makes the sentence true. part_of is MEMBER -> CONTAINER; requires/depends_on is
DEPENDENT -> DEPENDENCY; enables/defines/mitigates/verifies/routes_to is ACTOR -> OBJECT;
contrasts_with is symmetric in meaning but must be emitted exactly once. Decide each edge
from the source; never batch-flip a relation type.

HYPEREDGE object (exact keys):
  id               : snake_case, MUST start with "{source.key}_".
  label            : short human name of the shared concept.
  nodes            : THREE OR MORE ids defined in THIS chunk.
  relation         : participate_in | implement | form
  confidence       : "EXTRACTED" | "INFERRED" (never AMBIGUOUS).
  confidence_score : 1 for EXTRACTED, 0.5 for INFERRED.
  source_file      : "{source_file}"

Emit a hyperedge only when 3+ nodes genuinely co-participate in one concept, flow, or
pattern that pairwise edges do not already capture. Maximum 3; [] is valid. Every edge
endpoint and hyperedge member must resolve in THIS chunk. Prefer faithful EXTRACTED edges,
mark reasoned links INFERRED honestly, and never invent facts. `_origin: "semantic"` is
mandatory because omitting it can make Graphify misclassify prose nodes as AST nodes.
{kind_note}

--- BEGIN COMPLETE SOURCE BYTES (UTF-8) ---
{body}
--- END COMPLETE SOURCE BYTES ---
"""


def _inventory_prompt(source: Source, captured_at: str, body: str) -> str:
    source_file = source_file_for(source)
    note = f"\nContext: {source.note}" if source.note else ""
    return f"""You are a knowledge-graph extractor. This complete curated inventory came from:
  {source.path}{note}

Produce ONLY a graphify chunk JSON object with nodes, edges, an empty hyperedges array,
input_tokens 0, and output_tokens 0. Create one node per item with id "{source.key}_" plus
an item slug, _origin "semantic", file_type "concept", source_file "{source_file}",
source_url "{source.url}", captured_at "{captured_at}", author null, contributor null,
and a faithful one-line rationale. Also create category nodes with ids beginning
"{source.key}_cat_". Emit item -> category part_of edges with confidence "EXTRACTED",
confidence_score 1, source_file "{source_file}", and weight 1. Capture every listed item,
invent none, and emit no hyperedges because pairwise category membership is complete.

--- BEGIN COMPLETE SOURCE BYTES (UTF-8) ---
{body}
--- END COMPLETE SOURCE BYTES ---
"""


def render_prompt(source: Source, captured_at: str, source_bytes: bytes) -> str:
    """Render one strict UTF-8 text source for cache lookup, invocation, and save.

    NORMAL ingestion has a caller-level text-only contract and no raster
    attachment contract. This strict decode rejects non-UTF-8 bytes, but is not
    claimed as a general binary-format preflight. Admitted raster transport
    belongs to the native deep SDK path.
    """
    validate_captured_at(captured_at)
    if source.kind not in _KINDS:
        raise ValueError(f"unknown source kind: {source.kind!r}")
    body = source_bytes.decode("utf-8", "strict")
    if source.kind == "inventory":
        return _inventory_prompt(source, captured_at, body)
    return _common_prompt(source, captured_at, body)


def _write_chunk(path: Path, chunk: dict) -> None:
    payload = json.dumps(chunk, sort_keys=True, indent=2, ensure_ascii=False).encode() + b"\n"
    graphify_execution.atomic_bytes(path, payload)


def ingest_source(
    request: IngestSourceRequest,
    *,
    process_runner: Callable[[dict], dict] | None = None,
    receipt_sink: Callable[[dict], dict] | None = None,
) -> dict:
    """Ingest one source, using only a compatible Graphify cache entry or one CLI attempt."""
    repo_root = request.repo_root
    scratch_dir = request.scratch_dir
    source = request.source
    captured_at = request.captured_at
    profile = request.profile
    public_profile = graphify_execution.public_profile_request(profile)
    run_root = request.run_root
    cache_root = request.cache_root
    source_path = source.path.resolve(strict=True)
    source_bytes = source_path.read_bytes()
    prompt = render_prompt(source, captured_at, source_bytes)
    requested_run_root = (
        _runtime_path(
            repo_root,
            run_root,
            label="run root",
            boundary=_RUNS_ROOT,
        )
        if run_root is not None
        else None
    )
    scratch_dir = _runtime_path(repo_root, scratch_dir, label="scratchDir", boundary=_SCRATCH_ROOT)
    semantic_cache = _runtime_path(
        repo_root,
        cache_root or repo_root / _CACHE_ROOT,
        label="cacheRoot",
        boundary=_CACHE_ROOT,
    )
    actual_run_root = graphify_execution.allocate_run_root(
        repo_root,
        requested_run_root,
        base=(repo_root / _RUNS_ROOT).resolve(strict=False),
    )
    cache_input_root = actual_run_root / "cache-input"
    source_file = source_file_for(source)
    staged_source = _runtime_path(
        repo_root,
        cache_input_root / source_file,
        label="staged sourceFile",
        boundary=actual_run_root,
    )
    graphify_execution.atomic_bytes(staged_source, source_bytes)
    context = graphify_execution.build_run_context(
        graphify_execution.RunContextSpec(
            run_root=actual_run_root,
            repo_root=repo_root,
            source_bytes=source_bytes,
            source_scope=[str(source_path), source_file],
            prompt=prompt,
            profile=profile,
            stage_id=f"normal:{source.key}",
        )
    )
    cache_evidence: list[dict] = []
    nodes, edges, hyperedges, uncached_files = graphify_sdk.check_semantic_cache_public(
        [source_file],
        root=cache_input_root,
        mode=None,
        prompt=prompt,
        cache_root=semantic_cache,
        execution_profile=public_profile,
        run_context=context,
        cache_evidence_out=cache_evidence,
    )
    output_path = _runtime_path(
        repo_root,
        scratch_dir / f"{source.key}.json",
        label="chunk output",
        boundary=scratch_dir,
    )
    if source_file not in uncached_files:
        chunk = _portable_cached_chunk(
            {"nodes": nodes, "edges": edges, "hyperedges": hyperedges},
            staged_source=staged_source,
            source_file=source_file,
        )
        _require_valid(chunk, source.key)
        _write_chunk(output_path, chunk)
        return {
            "key": source.key,
            "wrote": True,
            "cached": True,
            "run_root": str(actual_run_root),
            "output": str(output_path),
            "cache_evidence": cache_evidence,
        }
    attempt = _run_uncached_cli(
        _UncachedCliAttempt(request, prompt, actual_run_root, context),
        process_runner=process_runner,
        receipt_sink=receipt_sink,
    )
    receipt = attempt["receipt"]
    if receipt["completion"] != "completed":
        if request.fallback_profile is not None:
            from graphify.execution import paid_work_state

            if paid_work_state([receipt]) == "none":
                fallback_request = replace(
                    request,
                    profile=request.fallback_profile,
                    fallback_profile=None,
                    run_root=None,
                )
                fallback_result = ingest_source(
                    fallback_request,
                    process_runner=process_runner,
                    receipt_sink=receipt_sink,
                )
                fallback_result["fallback_after_receipt"] = receipt["receipt_id"]
                fallback_result["primary_run_root"] = str(actual_run_root)
                return fallback_result
        raise RuntimeError(f"managed extraction did not complete: {receipt['completion']}")
    value = attempt["value"]
    chunk = {
        "nodes": value["nodes"],
        "edges": value["edges"],
        "hyperedges": value.get("hyperedges", []),
    }
    _require_valid(chunk, source.key)
    graphify_sdk.save_semantic_cache_public(
        chunk["nodes"],
        chunk["edges"],
        chunk.get("hyperedges", []),
        root=cache_input_root,
        allowed_source_files=[source_file],
        mode=None,
        prompt=prompt,
        cache_root=semantic_cache,
        execution_profile=public_profile,
        run_context=context,
        producer_receipt=receipt,
    )
    _write_chunk(output_path, chunk)
    return {
        "key": source.key,
        "wrote": True,
        "cached": False,
        "run_root": str(actual_run_root),
        "output": str(output_path),
        "receipt_id": receipt["receipt_id"],
        "coverage": receipt["coverage"],
    }


def _run_uncached_cli(
    spec: _UncachedCliAttempt,
    *,
    process_runner: Callable[[dict], dict] | None,
    receipt_sink: Callable[[dict], dict] | None,
) -> dict:
    """Keep an isolated CLI workspace alive through execution and receipt publication."""
    profile = spec.request.profile
    timeout_seconds = spec.request.timeout_seconds
    with ExitStack() as workspace:
        cli_cwd = spec.request.repo_root
        if profile.get("cli_policy", {}).get("project_configuration") == "isolated":
            cli_cwd = Path(
                workspace.enter_context(tempfile.TemporaryDirectory(prefix="kb-graphify-codex-"))
            )
        invocation = graphify_sdk.build_cli_invocation_public(
            spec.prompt,
            purpose="extract",
            max_tokens=60_000,
            profile=profile,
            output_path=spec.run_root / "result.json",
            project_root=spec.request.repo_root,
            cwd=cli_cwd,
        )
        invocation = graphify_execution.restrict_claude_invocation(invocation)
        invocation["timeout_seconds"] = timeout_seconds
        runner = process_runner or graphify_execution.CapturedProcessRunner(
            spec.run_root,
            graphify_execution.safe_child_environment(backend=profile["backend"]),
            timeout_seconds,
            environment_overrides=graphify_execution.child_environment_override_evidence(
                profile["backend"]
            ),
            budget=spec.request.execution_budget
            or graphify_execution.ExecutionBudget(max_attempts=1, total_seconds=timeout_seconds),
        )
        sink = receipt_sink or graphify_execution.DurableReceiptSink(spec.run_root)
        return graphify_sdk.run_cli_invocation_public(
            invocation,
            run_context=spec.run_context,
            process_runner=runner,
            result_parser=graphify_execution.result_parser(profile["backend"]),
            receipt_sink=sink,
        )


def _portable_cached_chunk(chunk: dict, *, staged_source: Path, source_file: str) -> dict:
    """Undo only the public cache's known re-anchoring of this staged source."""
    portable = {}
    for bucket in ("nodes", "edges", "hyperedges"):
        items = []
        for item in chunk[bucket]:
            copied = dict(item)
            cached_source = copied.get("source_file")
            if cached_source is not None:
                if cached_source not in (source_file, str(staged_source)):
                    raise ValueError("cached source_file does not match the staged source identity")
                copied["source_file"] = source_file
            items.append(copied)
        portable[bucket] = items
    return portable


def _require_valid(chunk: object, label: str) -> None:
    issues = chunks.validate(chunk, label=label)
    if issues:
        raise ValueError("invalid graphify chunk:\n" + "\n".join(issues))


def _source(value: object) -> Source:
    if not isinstance(value, dict):
        raise TypeError("each source must be a JSON object")
    try:
        return Source(
            key=value["key"],
            path=Path(value["path"]),
            url=value["url"],
            kind=value.get("kind", "doc"),
            note=value.get("note", ""),
            source_file=value.get("sourceFile"),
        )
    except KeyError as exc:
        raise ValueError(f"source missing required field: {exc.args[0]}") from exc


def _fallback_profile(request: dict, environment: dict[str, str], primary: dict) -> dict | None:
    """Resolve an explicitly named alternate before any source can launch."""
    backend = request.get("fallbackBackend")
    if backend is None:
        if any(key in request for key in ("fallbackModel", "fallbackEffort")):
            raise ValueError("fallbackBackend is required for fallback selectors")
        return None
    fallback = graphify_execution.resolve_profile(
        backend,
        graphify_execution.ProfileSelection(
            model=request.get("fallbackModel"),
            effort=request.get("fallbackEffort"),
            environment=environment,
        ),
    )
    if fallback == primary:
        raise ValueError("fallback profile must differ from the primary profile")
    return fallback


def ingest_main(repo_root: Path, argv: list[str]) -> int:
    """CLI entry point: ``graphify-ingest REQUEST.json``."""
    if argv == ["--help"]:
        print(_HELP, end="")
        return 0
    if len(argv) != 1:
        print(_HELP, end="")
        return 2
    request_path = Path(argv[0]).resolve(strict=True)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise TypeError("ingest request must be a JSON object")
    sources = request.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("ingest request requires a non-empty sources array")
    parsed_sources = [_source(item) for item in sources]
    timeout_seconds = float(request.get("timeoutSeconds", 300))
    budget = graphify_execution.ExecutionBudget(
        max_attempts=request.get("maxAttempts", 8),
        total_seconds=request.get("totalTimeoutSeconds", 1800),
    )
    if not 0 < timeout_seconds < float("inf"):
        raise ValueError("timeoutSeconds must be finite and positive")
    assert_pinned_graphify(repo_root)
    scratch_dir = _runtime_path(
        repo_root,
        Path(request["scratchDir"]),
        label="scratchDir",
        boundary=_SCRATCH_ROOT,
    )
    scratch_dir.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    profile = graphify_execution.resolve_profile(
        request.get("backend", "claude-cli"),
        graphify_execution.ProfileSelection(
            model=request.get("model"),
            effort=request.get("effort"),
            environment=environment,
        ),
    )
    fallback_profile = _fallback_profile(request, environment, profile)
    results: list[dict] = []
    state_path = scratch_dir / "run-state.json"

    def write_state(completion: str, failed_key: str | None = None) -> None:
        graphify_execution.atomic_bytes(
            state_path,
            json.dumps(
                {
                    "completion": completion,
                    "total": len(parsed_sources),
                    "succeeded": len(results),
                    "failed_key": failed_key,
                    "unattempted": [
                        source.key
                        for source in parsed_sources[len(results) + int(failed_key is not None) :]
                    ],
                    "results": results,
                    "budget": {
                        "max_attempts": budget.max_attempts,
                        "attempts_started": budget.attempts_started,
                        "total_seconds": budget.total_seconds,
                    },
                },
                sort_keys=True,
            ).encode()
            + b"\n",
        )

    write_state("in_progress")
    for source in parsed_sources:
        try:
            result = ingest_source(
                IngestSourceRequest(
                    repo_root=repo_root,
                    scratch_dir=scratch_dir,
                    source=source,
                    captured_at=request["capturedAt"],
                    profile=profile,
                    cache_root=_runtime_path(
                        repo_root,
                        Path(request["cacheRoot"]),
                        label="cacheRoot",
                        boundary=_CACHE_ROOT,
                    )
                    if request.get("cacheRoot")
                    else None,
                    timeout_seconds=timeout_seconds,
                    execution_budget=budget,
                    fallback_profile=fallback_profile if not results else None,
                )
            )
        except Exception:
            write_state("incomplete", failed_key=source.key)
            raise
        results.append(result)
        write_state("in_progress")
    write_state("completed")
    print(json.dumps({"total": len(sources), "succeeded": len(results), "results": results}))
    return 0
