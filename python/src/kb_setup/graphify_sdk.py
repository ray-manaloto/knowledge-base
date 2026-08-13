# Copyright (c) 2026 Raymond Manaloto
"""Strict contract for the public Graphify SDK used by :mod:`kb_setup`.

The CLI and Python distribution are separate installations in this repository.
Checking only ``graphify --version`` cannot prove that the uv environment exposes
the public functions the library imports, nor that their call contracts still
match the release we reviewed.  This module deliberately imports only public
symbols and records their accepted signatures.  A Graphify bump must update this
contract as part of the reviewed change; an unreviewed drift fails before a graph
writer runs.
"""

from __future__ import annotations

import inspect
import io
import os
import re
import signal
import warnings
from collections.abc import Callable
from contextlib import redirect_stderr
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING

from graphify.build import build, build_from_json, build_merge
from graphify.detect import detect, detect_incremental
from graphify.export import prune_dangling_edges, to_json
from graphify.extract import collect_files, extract
from graphify.extractors.json_config import extract_json
from graphify.reflect import build_learning_overlay, reflect

from kb_setup.graphify_health import (
    APPROVED_METADATA_ZERO_NODE_WARNING,
    ExpectedMetadataOnly,
    ExpectedUnclassifiedFile,
    GraphifyEvidence,
    GraphifyOperation,
    GraphifyReceipt,
    SourceCoveragePolicy,
    assess,
    require_complete,
)

if TYPE_CHECKING:
    import networkx as nx


@dataclass(frozen=True)
class PublicSymbol:
    """One reviewed public Graphify function and its runtime signature."""

    dotted_name: str
    function: Callable[..., object]
    expected_signature: str


_PUBLIC_SYMBOLS = (
    PublicSymbol(
        "graphify.build.build",
        build,
        "(extractions: 'list[dict]', *, directed: 'bool' = False, dedup: 'bool' = True, "
        "dedup_llm_backend: 'str | None' = None, root: 'str | Path | None' = None) -> "
        "'nx.Graph'",
    ),
    PublicSymbol(
        "graphify.build.build_from_json",
        build_from_json,
        "(extraction: 'dict', *, directed: 'bool' = False, root: 'str | Path | None' = None) "
        "-> 'nx.Graph'",
    ),
    PublicSymbol(
        "graphify.build.build_merge",
        build_merge,
        "(new_chunks: 'list[dict]', graph_path: 'str | Path | None' = None, prune_sources: "
        "'list[str] | None' = None, *, directed: 'bool | None' = None, dedup: 'bool' = True, "
        "dedup_llm_backend: 'str | None' = None, root: 'str | Path | None' = None) -> "
        "'nx.Graph'",
    ),
    PublicSymbol(
        "graphify.extract.collect_files",
        collect_files,
        "(target: 'Path', *, follow_symlinks: 'bool' = False, root: 'Path | None' = None) -> "
        "'list[Path]'",
    ),
    PublicSymbol(
        "graphify.extract.extract",
        extract,
        "(paths: 'list[Path]', cache_root: 'Path | None' = None, *, root: 'Path | None' = None, "
        "parallel: 'bool' = True, max_workers: 'int | None' = None, resolution_context_nodes: "
        "'list[dict] | None' = None, resolution_context_edges: 'list[dict] | None' = None) -> "
        "'dict'",
    ),
    PublicSymbol(
        "graphify.extractors.json_config.extract_json",
        extract_json,
        "(path: 'Path') -> 'dict'",
    ),
    PublicSymbol(
        "graphify.detect.detect",
        detect,
        "(root: 'Path', *, follow_symlinks: 'bool | None' = None, google_workspace: "
        "'bool | None' = None, extra_excludes: 'list[str] | None' = None, cache_root: "
        "'Path | None' = None, gitignore: 'bool' = True) -> 'dict'",
    ),
    PublicSymbol(
        "graphify.detect.detect_incremental",
        detect_incremental,
        "(root: 'Path', manifest_path: 'str' = 'graphify-out/manifest.json', *, "
        "follow_symlinks: 'bool | None' = None, google_workspace: 'bool | None' = None, "
        "kind: 'str' = 'semantic', extra_excludes: 'list[str] | None' = None, gitignore: "
        "'bool' = True) -> 'dict'",
    ),
    PublicSymbol(
        "graphify.reflect.reflect",
        reflect,
        "(memory_dir: 'Path', out_path: 'Path', graph_path: 'Path | None' = None, "
        "analysis_path: 'Path | None' = None, labels_path: 'Path | None' = None, *, now: "
        "'datetime | None' = None, half_life_days: 'float' = 30.0, min_corroboration: "
        "'int' = 2) -> 'tuple[Path, dict[str, Any]]'",
    ),
    PublicSymbol(
        "graphify.reflect.build_learning_overlay",
        build_learning_overlay,
        "(agg: 'dict[str, Any]', graph_path: 'Path', *, now: 'datetime | None' = None) -> "
        "'dict[str, Any]'",
    ),
    PublicSymbol(
        "graphify.export.to_json",
        to_json,
        "(G: 'nx.Graph', communities: 'dict[int, list[str]]', output_path: 'str', *, force: "
        "'bool' = False, built_at_commit: 'str | None' = None, community_labels: "
        "'dict[int, str] | None' = None) -> 'bool'",
    ),
    PublicSymbol(
        "graphify.export.prune_dangling_edges",
        prune_dangling_edges,
        "(graph_data: 'dict') -> 'tuple[dict, int]'",
    ),
)


def running_sdk_version() -> str:
    """Return the installed Graphify SDK distribution version."""
    return metadata.version("graphifyy")


def public_api_fingerprint() -> tuple[tuple[str, str], ...]:
    """Return the deterministic public-symbol/signature fingerprint."""
    return tuple(
        (symbol.dotted_name, str(inspect.signature(symbol.function))) for symbol in _PUBLIC_SYMBOLS
    )


def contract_errors(expected_version: str) -> tuple[str, ...]:
    """Describe every SDK version or public-signature mismatch."""
    errors: list[str] = []
    running = running_sdk_version()
    if running != expected_version:
        errors.append(f"graphify SDK version {running} != accepted version {expected_version}")
    for symbol in _PUBLIC_SYMBOLS:
        actual = str(inspect.signature(symbol.function))
        if actual != symbol.expected_signature:
            errors.append(
                f"{symbol.dotted_name} signature changed: expected "
                f"{symbol.expected_signature}; got {actual}"
            )
    return tuple(errors)


def assert_public_sdk(expected_version: str) -> None:
    """Fail closed unless the installed public SDK matches the reviewed contract."""
    errors = contract_errors(expected_version)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise RuntimeError(
            "Graphify public SDK contract failed; review the release and update call sites "
            f"before writing/querying the graph:\n{details}"
        )


def contract_main(repo_root: Path) -> int:
    """Verify the pinned CLI and reviewed public SDK surface for automation."""
    from kb_setup.graphify_env import assert_pinned_graphify

    assert_pinned_graphify(repo_root)
    print(f"Graphify CLI/SDK contract PASS: {running_sdk_version()}")
    for dotted_name, signature in public_api_fingerprint():
        print(f"  {dotted_name}{signature}")
    return 0


def detect_checked(
    root: Path,
    *,
    source_name: str | None = None,
    coverage_policy: SourceCoveragePolicy | None = None,
    timeout_seconds: float = 30.0,
) -> tuple[dict, GraphifyReceipt]:
    """Run public detection and refuse warnings or undeclared coverage gaps."""
    try:
        stream = io.StringIO()
        with warnings.catch_warnings(record=True) as caught, redirect_stderr(stream):
            warnings.simplefilter("always")
            result = _detect_with_timeout(root, timeout_seconds)
    except TimeoutError:
        receipt = assess(
            GraphifyOperation.DETECT,
            GraphifyEvidence(
                observed=True,
                source_name=source_name,
                returncode=124,
                timed_out=True,
            ),
        )
        require_complete(receipt)
        return {}, receipt
    warning_text = "\n".join(
        part
        for part in (stream.getvalue().strip(), *(str(item.message) for item in caught))
        if part
    )
    unclassified = tuple(_relative_paths(root, result.get("unclassified", [])))
    ignored = tuple(_relative_paths(root, result.get("ignored", [])))
    receipt = assess(
        GraphifyOperation.DETECT,
        GraphifyEvidence(
            observed=True,
            source_name=source_name,
            stderr=warning_text,
            detected_sources=int(result.get("total_files", 0)) + len(unclassified),
            unclassified_files=len(unclassified),
            unclassified_paths=unclassified,
            ignored_paths=ignored,
            coverage_policy=coverage_policy,
        ),
    )
    require_complete(receipt)
    return result, receipt


def _detect_with_timeout(root: Path, timeout_seconds: float) -> dict:
    """Bound the synchronous public detector without changing its reviewed API."""
    if timeout_seconds <= 0:
        raise ValueError("detect timeout must be positive")

    def timeout_handler(_signum: int, _frame: object) -> None:
        raise TimeoutError("Graphify detect timed out")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return detect(root)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def extract_checked(paths: list[Path], *, root: Path) -> tuple[dict, GraphifyReceipt]:
    """Run public extraction and refuse warnings, partial input, or zero-node sources."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = extract(paths, root=root)
    nodes = result.get("nodes", [])
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr="\n".join(str(item.message) for item in caught),
            detected_sources=len(paths),
            extracted_sources=len(paths) if nodes else 0,
            zero_node_sources=0 if nodes else len(paths),
            mode="ast",
        ),
    )
    require_complete(receipt)
    return result, receipt


def build_checked(extractions: list[dict], *, root: Path) -> tuple[nx.Graph, GraphifyReceipt]:
    """Run public graph construction and require a nonempty, warning-free result."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        graph = build(extractions, root=root)
    node_count = int(graph.number_of_nodes())
    receipt = assess(
        GraphifyOperation.BUILD,
        GraphifyEvidence(
            observed=True,
            stderr="\n".join(str(item.message) for item in caught),
            detected_sources=len(extractions),
            extracted_sources=len(extractions) if node_count else 0,
            zero_node_sources=0 if node_count else len(extractions),
        ),
    )
    require_complete(receipt)
    return graph, receipt


def reflect_checked(
    memory_dir: Path,
    out_path: Path,
    *,
    graph_path: Path,
) -> tuple[tuple[Path, dict], GraphifyReceipt]:
    """Run public reflection and require its declared output."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = reflect(memory_dir, out_path, graph_path)
    receipt = assess(
        GraphifyOperation.REFLECT,
        GraphifyEvidence(
            observed=True,
            stderr="\n".join(str(item.message) for item in caught),
            reflection_expected=True,
            reflection_produced=out_path.is_file(),
        ),
    )
    require_complete(receipt)
    return result, receipt


def artifact_checked(
    graph: nx.Graph,
    communities: dict[int, list[str]],
    output_path: Path,
) -> GraphifyReceipt:
    """Run the public JSON exporter and require the requested artifact."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        written = to_json(graph, communities, str(output_path), force=True)
    receipt = assess(
        GraphifyOperation.ARTIFACT,
        GraphifyEvidence(
            observed=True,
            stderr="\n".join(str(item.message) for item in caught),
            expected_artifacts=(str(output_path),),
            produced_artifacts=(str(output_path),) if written and output_path.is_file() else (),
        ),
    )
    require_complete(receipt)
    return receipt


def _relative_paths(root: Path, paths: object) -> tuple[str, ...]:
    if not isinstance(paths, list):
        return ()
    absolute_root = root.resolve()
    relative: list[str] = []
    for raw in paths:
        path = Path(str(raw))
        try:
            absolute_path = path if path.is_absolute() else path.resolve()
            relative.append(str(absolute_path.relative_to(absolute_root)))
        except ValueError:
            relative.append(str(path))
    return tuple(relative)


def approve_metadata_zero_node_warning(
    root: Path,
    source_name: str,
    stderr: str,
    inventory: tuple[ExpectedMetadataOnly, ...],
) -> tuple[str, ...]:
    """Approve only the exact 0.9.41 warning backed by reviewed path/bytes/disposition."""
    if not inventory or any(item.source_name != source_name for item in inventory):
        return ()
    valid = True
    for item in inventory:
        path = root / item.relative_path
        try:
            content_hash = _sha256_file(path)
        except OSError:
            valid = False
            break
        if content_hash != item.content_sha256:
            valid = False
            break
        result = extract_json(path)
        if result.get("error") or result.get("nodes") or result.get("edges"):
            valid = False
            break
        if result.get("skipped") != item.skipped_disposition:
            valid = False
            break
    names = ", ".join(Path(item.relative_path).name for item in inventory)
    expected = (
        f"  warning: {len(inventory)} source file(s) produced zero nodes and are absent "
        f"from the graph: {names}. A re-run will retry them (empties are no longer "
        "cached); if it persists, please report the file(s) (#1666).\n"
    )
    if not valid or stderr != expected:
        return ()
    return (APPROVED_METADATA_ZERO_NODE_WARNING,)


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


_ROOT_LICENSE_NAMES = frozenset(
    {"LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt"}
)
_IGNORE_MAX_BYTES = 16 * 1024
_IGNORE_PATTERN = re.compile(r"!?[A-Za-z0-9_.*?/[\]{}()@+,:=~-]+")


def source_detection_policy(
    root: Path,
    source_name: str,
    reviewed: tuple[ExpectedUnclassifiedFile, ...] = (),
) -> SourceCoveragePolicy:
    """Return only structurally and cryptographically reviewed unclassified metadata."""
    allowed = [
        name
        for name in sorted({".gitignore", *_ROOT_LICENSE_NAMES})
        if _safe_root_regular_file(root, name)
    ]
    for item in reviewed:
        if item.source_name != source_name:
            continue
        if item.classification == "reviewed-version-marker" and _safe_exact_reviewed_file(
            root, item
        ):
            allowed.append(item.relative_path)
        if item.classification == "reviewed-root-ignore-metadata" and _safe_reviewed_ignore(
            root, item
        ):
            allowed.append(item.relative_path)
    return SourceCoveragePolicy(optional_unclassified_paths=tuple(sorted(allowed)))


def _safe_root_regular_file(root: Path, name: str) -> bool:
    path = root / name
    return path.parent == root and path.is_file() and not path.is_symlink()


def _safe_reviewed_ignore(root: Path, item: ExpectedUnclassifiedFile) -> bool:
    if item.relative_path != ".claudeignore" or not _safe_root_regular_file(root, ".claudeignore"):
        return False
    path = root / item.relative_path
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except OSError, UnicodeDecodeError:
        return False
    if len(raw) > _IGNORE_MAX_BYTES or "\x00" in text or _sha256_file(path) != item.content_sha256:
        return False
    return all(
        not line or line.startswith("#") or _IGNORE_PATTERN.fullmatch(line) is not None
        for line in (item.strip() for item in text.splitlines())
    )


def _safe_exact_reviewed_file(root: Path, item: ExpectedUnclassifiedFile) -> bool:
    relative = Path(item.relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        return False
    path = root / relative
    if not path.is_file() or path.is_symlink():
        return False
    try:
        if os.path.commonpath((root.resolve(), path.resolve())) != str(root.resolve()):
            return False
        return _sha256_file(path) == item.content_sha256
    except OSError:
        return False
