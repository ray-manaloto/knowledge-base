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
import tempfile
import warnings
from collections import Counter
from collections.abc import Callable, Mapping
from contextlib import redirect_stderr
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

import msgspec
from graphify.build import build, build_from_json, build_merge
from graphify.detect import detect, detect_incremental
from graphify.export import prune_dangling_edges, to_json
from graphify.extract import collect_files, extract
from graphify.extractors.json_config import extract_json
from graphify.llm import extract_corpus_parallel
from graphify.reflect import build_learning_overlay, reflect

from kb_setup.graphify_health import (
    APPROVED_METADATA_ZERO_NODE_WARNING,
    APPROVED_PARTIAL_EXTRACTION_WARNING,
    ExpectedMetadataOnly,
    ExpectedPartialExtraction,
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


@dataclass(frozen=True)
class ExtractionAdmission:
    """Reviewed exceptions that can authorize exact zero-node AST inputs."""

    source_name: str
    coverage_policy: SourceCoveragePolicy
    metadata_inventory: tuple[ExpectedMetadataOnly, ...]


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

# Graphify's semantic module is not part of the deterministic baseline's public
# compatibility fingerprint. Issue #300 nevertheless needs one exact SDK seam:
# the non-underscore corpus function is the only callable that both exercises
# Graphify's real claude-cli route and lets the caller set adaptive retries to
# zero. Keep its reviewed contract separate so extending semantic evidence does
# not re-authorize the already-landed #299 deterministic candidate.
_SEMANTIC_SYMBOLS = (
    PublicSymbol(
        "graphify.llm.extract_corpus_parallel",
        extract_corpus_parallel,
        "(files: 'list[Path]', backend: 'str' = 'kimi', api_key: 'str | None' = None, "
        "model: 'str | None' = None, root: 'Path' = PosixPath('.'), chunk_size: 'int' = 20, "
        "on_chunk_done: 'Callable | None' = None, token_budget: 'int | None' = 60000, "
        "max_concurrency: 'int' = 4, max_retry_depth: 'int' = 3, deep_mode: 'bool' = False, "
        "cache_root: \"'Path | None'\" = None) -> 'dict'",
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


def semantic_api_fingerprint() -> tuple[tuple[str, str], ...]:
    """Return the reviewed Graphify semantic-symbol fingerprint for issue #300."""
    return tuple(
        (symbol.dotted_name, str(inspect.signature(symbol.function)))
        for symbol in _SEMANTIC_SYMBOLS
    )


def semantic_contract_errors(expected_version: str) -> tuple[str, ...]:
    """Describe version or signature drift at the real semantic SDK seam."""
    errors: list[str] = []
    running = running_sdk_version()
    if running != expected_version:
        errors.append(f"graphify SDK version {running} != accepted version {expected_version}")
    for symbol in _SEMANTIC_SYMBOLS:
        actual = str(inspect.signature(symbol.function))
        if actual != symbol.expected_signature:
            errors.append(
                f"{symbol.dotted_name} signature changed: expected "
                f"{symbol.expected_signature}; got {actual}"
            )
    return tuple(errors)


def assert_semantic_sdk(expected_version: str) -> None:
    """Fail closed unless Graphify's one reviewed semantic seam still matches."""
    errors = semantic_contract_errors(expected_version)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise RuntimeError(
            "Graphify semantic SDK contract failed; review the release before inference:\n"
            f"{details}"
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
    result, receipt = observe_detect(
        root,
        source_name=source_name,
        coverage_policy=coverage_policy,
        timeout_seconds=timeout_seconds,
    )
    require_complete(receipt)
    return result, receipt


def observe_detect(
    root: Path,
    *,
    source_name: str | None = None,
    coverage_policy: SourceCoveragePolicy | None = None,
    timeout_seconds: float = 30.0,
) -> tuple[dict, GraphifyReceipt]:
    """Run public detection and return typed evidence without authorizing mutation."""
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
        return {}, receipt
    warning_text = "\n".join(
        part
        for part in (stream.getvalue().strip(), *(str(item.message) for item in caught))
        if part
    )
    unclassified = tuple(_relative_paths(root, result.get("unclassified", [])))
    ignored = tuple(_relative_paths(root, result.get("ignored", [])))
    if coverage_policy is not None:
        coverage_policy = _apply_detection_classes(root, unclassified, coverage_policy)
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
        with tempfile.TemporaryDirectory(prefix="kb-graphify-detect-cache-") as cache_dir:
            return detect(root, cache_root=Path(cache_dir))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def extract_checked(
    paths: list[Path],
    *,
    root: Path,
    cache_root: Path | None = None,
    admission: ExtractionAdmission | None = None,
) -> tuple[dict, GraphifyReceipt]:
    """Run public extraction and refuse warnings, partial input, or zero-node sources."""
    stream = io.StringIO()
    with warnings.catch_warnings(record=True) as caught, redirect_stderr(stream):
        warnings.simplefilter("always")
        result = extract(paths, root=root, cache_root=cache_root)
    nodes = result.get("nodes", [])
    failed = tuple(_relative_paths(root, result.get("failed_sources", [])))
    if not nodes and not failed:
        failed = tuple(_relative_paths(root, paths))
    raw_stderr = stream.getvalue()
    approved, residual = account_for_extract_stderr(
        root,
        raw_stderr,
        ExtractWarningReview(
            source_name=admission.source_name if admission else "",
            metadata_inventory=admission.metadata_inventory if admission else (),
        ),
    )
    # `caught` warnings are never approved by name, so they always land in the
    # residual. Previously an approval blanked ALL of stderr, which took these
    # with it — an approved zero-node warning silently swallowed any unrelated
    # Python warning raised in the same call.
    warning_text = "\n".join(
        part for part in (residual.strip(), *(str(item.message) for item in caught)) if part
    )
    # `stderr` keeps everything that was said; `residual_stderr` keeps what
    # nobody accounted for. Collapsing the two — which the pre-#328 code did by
    # blanking stderr on approval — destroys the evidence that a warning was
    # printed at all, so a receipt could not later be audited for what it let by.
    observed_stderr = "\n".join(
        part for part in (raw_stderr.strip(), *(str(item.message) for item in caught)) if part
    )
    accepted_zero_nodes = (
        bool(approved)
        and admission is not None
        and set(failed) <= set(admission.coverage_policy.optional_zero_node_paths)
    )
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            source_name=admission.source_name if admission else None,
            stderr=observed_stderr,
            detected_sources=len(paths),
            extracted_sources=len(paths) if accepted_zero_nodes else len(paths) - len(failed),
            zero_node_sources=len(failed),
            zero_node_paths=failed,
            coverage_policy=admission.coverage_policy if admission else None,
            approved_classifications=approved,
            residual_stderr=warning_text,
            mode="ast",
        ),
    )
    require_complete(receipt)
    return result, receipt


def build_checked(extractions: list[dict], *, root: Path) -> tuple[nx.Graph, GraphifyReceipt]:
    """Run public graph construction and require a nonempty, warning-free result."""
    stream = io.StringIO()
    with warnings.catch_warnings(record=True) as caught, redirect_stderr(stream):
        warnings.simplefilter("always")
        graph = build(extractions, root=root)
    node_count = int(graph.number_of_nodes())
    receipt = assess(
        GraphifyOperation.BUILD,
        GraphifyEvidence(
            observed=True,
            stderr="\n".join(
                part
                for part in (stream.getvalue().strip(), *(str(item.message) for item in caught))
                if part
            ),
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
    *,
    built_at_commit: str | None = None,
) -> GraphifyReceipt:
    """Run the public JSON exporter and require the requested artifact."""
    stream = io.StringIO()
    with warnings.catch_warnings(record=True) as caught, redirect_stderr(stream):
        warnings.simplefilter("always")
        written = to_json(
            graph,
            communities,
            str(output_path),
            force=True,
            built_at_commit=built_at_commit,
        )
    receipt = assess(
        GraphifyOperation.ARTIFACT,
        GraphifyEvidence(
            observed=True,
            stderr="\n".join(
                part
                for part in (stream.getvalue().strip(), *(str(item.message) for item in caught))
                if part
            ),
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
    """Approve only the reviewed warning backed by exact path/bytes/disposition.

    `stderr` is ONE warning line — approval is per warning, not per subprocess.
    Passing whole multi-line stderr still works and still refuses, because an
    unrecognised second line prevents the match.
    """
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
        actual_disposition = result.get("skipped")
        if actual_disposition != item.skipped_disposition:
            valid = False
            break
    warned = tuple(item for item in inventory if not item.skipped_disposition.startswith("error:"))
    # rstrip, never strip: the warning's two LEADING spaces are part of the text
    # graphify prints and part of what is matched.
    if not valid or not _zero_node_warning_matches(stderr.rstrip(), warned):
        return ()
    return (APPROVED_METADATA_ZERO_NODE_WARNING,)


#: Graphify shows at most this many names before "(+N more)" (`extract.py:5511`).
_ZERO_NODE_SHOWN_LIMIT = 5

_ZERO_NODE_WARNING = re.compile(
    r"\A {2}warning: (?P<count>\d+) source file\(s\) produced zero nodes and are absent "
    r"from the graph: (?P<shown>.+?)"
    r"(?: \(\+(?P<more>\d+) more\))?"
    r"\. A re-run will retry them \(empties are no longer cached\); if it persists, "
    r"please report the file\(s\) \(#1666\)\.\Z"
)

_PARTIAL_EXTRACTION_WARNING = re.compile(
    r"\A {2}warning: (?P<count>\d+) file\(s\) had syntax errors and may be partially "
    r"extracted: (?P<path>[^()]+?) \(first error at line (?P<line>\d+)\) \(#2551\)\.?\Z"
)


def _zero_node_warning_matches(line: str, warned: tuple[ExpectedMetadataOnly, ...]) -> bool:
    """True iff this #1666 warning is fully accounted for by the reviewed inventory.

    Graphify TRUNCATES the name list at five and appends "(+N more)", so the
    warning cannot be reconstructed by joining every reviewed name — the previous
    implementation did exactly that and therefore could never approve a source
    with more than five metadata-only files, no matter how correctly they were
    registered. (Measured on `Attacca`: eight files, so graphify prints five names
    plus "(+3 more)" while the reconstruction printed all eight and no suffix.)

    Identity still comes from the INVENTORY, which pins every path to its bytes and
    its skipped disposition; this function's job is only to confirm the warning
    graphify actually printed describes that same set — same total, and every name
    it does show accounted for. A ninth zero-node file moves `count` and is refused.
    """
    if not warned:
        return False
    match = _ZERO_NODE_WARNING.match(line)
    if match is None:
        return False
    if int(match.group("count")) != len(warned):
        return False
    shown = [name.strip() for name in match.group("shown").split(",")]
    more = int(match.group("more") or 0)
    # Reproduce graphify's own truncation arithmetic rather than trusting either
    # half of it: a "(+N more)" that disagrees with the total is a warning we do
    # not understand, and an unrecognised warning is never approved.
    if len(shown) != min(len(warned), _ZERO_NODE_SHOWN_LIMIT):
        return False
    if more != max(0, len(warned) - _ZERO_NODE_SHOWN_LIMIT):
        return False
    available = Counter(PurePosixPath(item.relative_path).name for item in warned)
    return not (Counter(shown) - available)


@dataclass(frozen=True)
class ExtractWarningReview:
    """Everything a reviewer registered about ONE source's extract warnings."""

    source_name: str
    metadata_inventory: tuple[ExpectedMetadataOnly, ...] = ()
    partial_inventory: tuple[ExpectedPartialExtraction, ...] = ()
    #: Per-file node totals from the sub-graph graphify just wrote. A reviewed
    #: partial extraction is checked against THIS, never against its own claim.
    extracted_nodes_by_path: Mapping[str, int] = field(default_factory=dict)


def _partial_extraction_is_reviewed(root: Path, line: str, review: ExtractWarningReview) -> bool:
    """True iff this #2551 warning matches a reviewed entry AND the measured loss."""
    inventory = review.partial_inventory
    if not inventory or any(item.source_name != review.source_name for item in inventory):
        return False
    match = _PARTIAL_EXTRACTION_WARNING.match(line)
    if match is None or int(match.group("count")) != len(inventory):
        return False
    named = match.group("path").strip()
    entry = next((item for item in inventory if item.relative_path == named), None)
    if entry is None or int(match.group("line")) != entry.first_error_line:
        return False
    try:
        if _sha256_file(root / entry.relative_path) != entry.content_sha256:
            return False
    except OSError:
        return False
    # `.get(..., 0)`, not `.get(...)`: `_nodes_by_source_file` is a Counter cast to
    # a dict, so a file that produced NO nodes is ABSENT rather than zero. Without
    # the default, a reviewed entry recording `extracted_nodes=0` — a file whose
    # partial extraction recovered nothing at all, the worst case this inventory
    # exists to record — compares `None == 0` and can never be approved.
    return review.extracted_nodes_by_path.get(entry.relative_path, 0) == entry.extracted_nodes


def approve_partial_extraction_warning(
    root: Path, line: str, review: ExtractWarningReview
) -> tuple[str, ...]:
    """Approve one reviewed #2551 warning, with the loss re-counted from the graph.

    Graphify's wording is "may be partially extracted" and carries NO count, so
    approving it on the strength of the text alone would approve an unmeasured
    quantity of corpus loss — the #231 shape. The reviewed entry states how many
    nodes the file contributes, and that number is checked against the sub-graph
    graphify just wrote, so the approval expires the moment the parser's
    behaviour changes in EITHER direction: a regression to zero nodes and a fix
    that recovers the symbols both stop matching, and both are worth a look.

    Deliberately handles ONE partially-extracted file per source. Graphify
    comma-joins a second one (and truncates at five, like the #1666 warning), and
    that form does not match here — so a newly-partial file blocks the build with
    its warning named in the residual, rather than inheriting the first file's
    review. Widen this only alongside a measurement of the new file's loss; the
    count is the whole point of the entry.
    """
    if not _partial_extraction_is_reviewed(root, line, review):
        return ()
    return (APPROVED_PARTIAL_EXTRACTION_WARNING,)


def account_for_extract_stderr(
    root: Path, stderr: str, review: ExtractWarningReview
) -> tuple[tuple[str, ...], str]:
    """Account for each warning line BY NAME; return (classifications, residual).

    One graphify extract can print several independent warnings, so approval is
    per line. A line no reviewer registered stays in the residual and blocks —
    `graphify_health._basic_reasons` refuses any non-empty residual — which is
    what keeps this from being the whole-stderr rubber stamp it replaces.
    """
    classifications: list[str] = []
    residual: list[str] = []
    for raw in stderr.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        approved = approve_metadata_zero_node_warning(
            root, review.source_name, line, review.metadata_inventory
        ) or approve_partial_extraction_warning(root, line, review)
        if approved:
            classifications.extend(approved)
        else:
            residual.append(line)
    return tuple(dict.fromkeys(classifications)), "\n".join(residual)


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


_ROOT_LICENSE_NAMES = frozenset(
    {"LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md", "COPYING.txt"}
)
_IGNORE_MAX_BYTES = 16 * 1024
_IGNORE_PATTERN = re.compile(r"!?[A-Za-z0-9_.*?/[\]{}()@+,:=~-]+")

# Two reviewed CLASSES, applied to vendored third-party clones at any depth.
#
# The split is the whole point, and it is drawn on one question: *would a human
# call this a program or a schema?* If yes it is a language Graphify cannot
# parse, and it is COUNTED as corpus loss (`_UNSUPPORTED_LANGUAGE_SUFFIXES` /
# `_UNSUPPORTED_LANGUAGE_NAMES`). If it is repo bookkeeping, a binary artifact,
# or config data, it is not graph source at all and is absorbed silently
# (`_NON_SOURCE_*`).
#
# Collapsing the two would make 879 measured source files indistinguishable
# from a LICENSE file and buy a green build with hidden loss — the #231 shape.
# Membership below is derived from the 2026-08-16 detection census over 3,304
# unclassified records; `mise`, `pkl` and `ruff` (4,683 further records) were
# NOT sampled, so this is a reviewed floor and not a closed set.
_NON_SOURCE_NAMES = frozenset(
    {
        ".bazelversion",
        ".editorconfig",
        ".git-blame-ignore-revs",
        ".gitattributes",
        ".gitkeep",
        ".gitmodules",
        ".mailmap",
        ".python-version",
        ".python-version-default",
        "AUTHORS",
        "CHANGES",
        "CITATION",
        "CITATION.cff",
        "CODEOWNERS",
        "COPYRIGHT",
        "DCO",
        "MANIFEST.in",
        "NOTICE",
        "SHA256SUMS",
        "py.typed",
        # Version and release markers: a bare string, carrying no structure to
        # graph. Distinct from a config file, which at least has a schema.
        ".java-version",
        ".nojekyll",
        ".release-skip-e2e",
        ".tool-versions",
        ".python-versions",
        ".version",
        ".worktreeinclude",
        "BOILERPLATE_VERSION",
        "CNAME",
        "VERSION",
        "_redirects",
        "latest",
        "mapping",
        # `.dev.vars` is a Cloudflare secrets template; `VERSIONS` is typeshed's
        # per-module availability table. Data, not structure.
        ".dev.vars",
        "VERSIONS",
        # A per-environment variant of an ignore file. `_is_ignore_metadata_name`
        # cannot see it: the name ends `.ci`, not `ignore`.
        ".dockerignore.ci",
    }
)
#: Repo bookkeeping, packaging data and binary artifacts — never graph source.
_NON_SOURCE_SUFFIXES = frozenset(
    {
        ".base64",
        ".csv",
        ".example",
        ".exe",
        ".gif",
        ".gz",
        ".ico",
        ".jpeg",
        ".jpg",
        ".jsonl",
        ".lock",
        ".lockfile",
        ".node",
        ".patch",
        ".pdf",
        ".plist",
        ".afdesign",
        ".age",
        # Detached signatures and armored keys: opaque bytes whose whole purpose
        # is to be verified, never read.
        ".asc",
        ".minisig",
        ".sig",
        ".bin",
        ".db",
        ".gpg",
        ".icns",
        ".idx",
        ".jar",
        ".marker",
        ".png",
        ".pub",
        ".resolved",
        ".sha256",
        ".so",
        ".stderr",
        ".spv",
        ".tsbuildinfo",
        ".wasm",
        ".whl",
        ".woff",
        ".woff2",
        ".xz",
        ".zst",
    }
)
#: Real source in a language Graphify does not parse. Absorbed so the build can
#: proceed, but reported with a per-language tally on every run.
_UNSUPPORTED_LANGUAGE_NAMES = frozenset(
    {
        "PKGBUILD",
        "PklProject",
        "make.bat",
        # Tool configs that live as a bare dotfile with no extension. These are
        # schemas, not markers, so they belong in the COUNTED class.
        ".bazelrc",
        ".clang-format",
        ".clang-tidy",
        ".codespellrc",
        ".coveragerc",
        ".cppcheck",
        ".cursorrules",
        ".known-crates",
        ".prettierrc",
        ".shellcheckrc",
        ".windsurfrules",
        # A leading-dot filename has NO `Path.suffix` — `Path(".SRCINFO").suffix`
        # is `""` — so every dotfile must be matched by NAME. Putting one in the
        # suffix set silently matches nothing, which is how `.SRCINFO` and
        # `.justfile` survived the first pass of this triage.
        ".SRCINFO",
        ".justfile",
        # Extensionless shell completions, wrapper scripts and C++ config
        # headers: real programs, just not ones Graphify parses.
        "__assertion_handler",
        "__config_site",
        "_bwrap",
        "_mise",
        "activate",
        "alpine",
        "argument-comment-lint",
        "buildifier",
        "bwrap",
        "codex-zsh",
        "rg",
        "rpmmacros",
        "rust-toolchain",
        "xonsh_script",
        "zstd",
        "dockerize",
        "pr_lint",
        # Extensionless prose Graphify declines to classify.
        "README",
    }
)
#: `Dockerfile.alpine`, `Makefile.cbm`, `Makefile.deepseek-v4.units`, `Justfile`
#: — one family rule instead of the 20 one-off spellings the census found. The
#: stem is everything before the first dot, so a variant suffix cannot smuggle a
#: file past the class by inventing a new extension.
_UNSUPPORTED_LANGUAGE_STEMS = frozenset({"Dockerfile", "Justfile", "Makefile", "justfile"})
_UNSUPPORTED_LANGUAGE_SUFFIXES = frozenset(
    {
        ".adoc",
        ".avsc",
        # BAML prompt definitions, and OWL ontologies. The ontologies are the
        # most knowledge-dense thing in this whole class — `cognee` ships eight —
        # which is exactly why they are COUNTED rather than quietly dropped.
        ".baml",
        ".owl",
        ".bat",
        ".bats",
        ".bazel",
        ".bzl",
        ".build",
        ".cbl",
        ".cfg",
        ".cmd",
        ".conf",
        ".Processor",
        ".cpy",
        ".css",
        # Graphviz source, and the Java service-loader tables `pkl` ships under
        # META-INF — both declare structure Graphify has no parser for.
        ".dot",
        ".processors",
        ".fish",
        ".graphql",
        ".gyp",
        ".hxx",
        ".in",
        ".ini",
        ".ipynb",
        ".jinja",
        ".jinja2",
        ".json5",
        ".kdl",
        ".mdc",
        ".nix",
        ".pkl",
        ".proto",
        ".pyi",
        ".scm",
        ".tmpl",
        ".toml",
        ".xsd",
        ".xsh",
        ".xml",
        # Languages, grammars, policies and markup Graphify has no parser for.
        ".1",
        ".S",
        ".bpf",
        # `builder.dockerfile` / `foo.justfile`: the STEM rule cannot see these,
        # because their stem is the project name, not the build-tool name.
        ".dockerfile",
        ".justfile",
        ".cedar",
        ".cedarschema",
        ".code-workspace",
        ".codexpolicy",
        ".comp",
        ".csh",
        ".el",
        ".envsubst",
        ".feature",
        ".hbs",
        ".hook",
        ".jsonc",
        ".lark",
        ".mako",
        ".man",
        ".manifest",
        ".mdm",
        ".mmd",
        ".nu",
        ".nuspec",
        ".pbxproj",
        ".postcss",
        ".properties",
        ".repo",
        ".sbpl",
        ".scss",
        ".spec",
        ".tape",
        ".template",
        ".tpl",
        ".typ",
        ".webmanifest",
        ".wprp",
        ".xcconfig",
        ".xcscheme",
        ".xcworkspacedata",
        ".entitlements",
    }
)
#: `LICENSE`, `LICENCE.md`, `License-Apache`, `LICENSE.BSD`, … one rule instead
#: of the eleven spellings the census found across 67 sources.
#:
#: Anchored, and requiring a NON-ALPHANUMERIC after the word, because a bare
#: `startswith` also absorbs `LICENSEPLATE.py` and `LICENSED_users.rs` — real
#: source, silently taken as a licence file and (unlike the counted class) never
#: tallied. Found by the cold lane; the first version of this rule was a
#: `.upper().startswith(...)`.
#:
#: An underscore counts as a boundary ONLY when no letter follows it: the same
#: failure class recurs as `LICENSE_KEYS.py` and `COPYING_utils.c`, which are
#: real source, while `LICENSE_1_0.txt` (Boost's spelling) is a licence file
#: and must keep matching.
_LICENSE_NAME = re.compile(
    r"(LICENSE|LICENCE|COPYING)($|[^A-Za-z0-9_]|_(?![A-Za-z]))", re.IGNORECASE
)
#: Vendored test fixtures — `gitleaks` ships fake `.git` trees, `typos` ships
#: `*.in/` input dirs, `pkl` ships `.jva` goldens. These are inputs to somebody
#: else's test suite, not corpus knowledge.
#:
#: This is the ONLY rule here that matches on PATH rather than on a name, which
#: makes it the loosest one in the file — so it is COUNTED, never absorbed
#: silently. A rule drawn too wide shows up in the printed tally instead of
#: hiding there. Anchored on whole path segments so `latest/` matches but
#: `contest/` does not.
_FIXTURE_SEGMENTS = re.compile(
    r"(^|/)(testdata|test|tests|fixture|fixtures|__tests__|golden|snapshot|snapshots)(/|$)"
)
#: Java service-loader tables. These are the one case where matching on a name
#: or an extension is STRUCTURALLY impossible: the file is named after the
#: fully-qualified interface it registers, so `java.nio.file.spi.FileTypeDetector`
#: has the "extension" `.FileTypeDetector` and the next one will have a different
#: one. The directory is what carries the meaning, and it is a JVM standard, so
#: the rule is anchored on the exact `META-INF/services/` parent rather than on
#: anything the filename happens to contain.
_SERVICE_LOADER_DIR = "META-INF/services/"


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


def _apply_detection_classes(
    root: Path, unclassified: tuple[str, ...], policy: SourceCoveragePolicy
) -> SourceCoveragePolicy:
    """Widen a policy with the two reviewed classes, never touching required_paths.

    `required_paths` is deliberately excluded from both classes: a path the
    corpus REQUIRES must fail loudly even if its extension happens to be one
    Graphify cannot parse. `_coverage_reasons` enforces that independently, and
    an arm covers it.
    """
    required = set(policy.required_paths)
    non_source, unsupported, _unresolved = classify_unclassified(root, unclassified)
    return msgspec.structs.replace(
        policy,
        optional_unclassified_paths=tuple(
            sorted({*policy.optional_unclassified_paths, *non_source} - required)
        ),
        unsupported_language_paths=tuple(
            sorted({*policy.unsupported_language_paths, *unsupported} - required)
        ),
    )


def classify_unclassified(
    root: Path, relative_paths: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Split detector leftovers into (non-source, unsupported-language, unresolved).

    Membership is a name/suffix class, but admission is still STRUCTURAL: a path
    only ever leaves `unresolved` if it resolves to a real regular file that is
    still contained by `root`.

    Symlinks are admitted, but only after that containment check. The census
    found three (`bubblewrap/LICENSE`, `mise:Dockerfile`, `mise:docs/settings.toml`)
    and all three point at ordinary files inside their own repo. The hazard a
    symlink poses is ESCAPE — a name that says `LICENSE` while the bytes live
    somewhere nobody reviewed — and `commonpath` on the RESOLVED pair is what
    answers that, not refusing links outright. A link out of the tree, a dangling
    link, and a link to a directory each fail here and stay `unresolved`.
    """
    non_source: list[str] = []
    unsupported: list[str] = []
    unresolved: list[str] = []
    for relative in relative_paths:
        target = _classifiable_name(root, relative)
        if target is None:
            unresolved.append(relative)
            continue
        name, suffix = target
        if _is_non_source(name, suffix):
            non_source.append(relative)
        elif _is_unsupported_language(relative, name, suffix):
            unsupported.append(relative)
        else:
            unresolved.append(relative)
    return tuple(sorted(non_source)), tuple(sorted(unsupported)), tuple(sorted(unresolved))


def _is_non_source(name: str, suffix: str) -> bool:
    """Repo bookkeeping, packaging data or a binary artifact — never graph source.

    Absorbed SILENTLY, which is why this predicate is the conservative one: a
    file that lands here is not counted anywhere, so anything arguable belongs
    in `_is_unsupported_language` instead.
    """
    return (
        name in _NON_SOURCE_NAMES
        or suffix in _NON_SOURCE_SUFFIXES
        or _LICENSE_NAME.match(name) is not None
        or _is_ignore_metadata_name(name)
    )


def _is_unsupported_language(relative: str, name: str, suffix: str) -> bool:
    """Real source, a schema, or a vendored fixture Graphify has no parser for.

    Absorbed but COUNTED, and tallied per extension on every build. Takes
    `relative` as well as the name because two of its five rules are about where
    a file sits rather than what it is called: a fixture directory, and the
    `META-INF/services/` tables whose filenames are the interfaces they register.
    """
    return (
        name in _UNSUPPORTED_LANGUAGE_NAMES
        or suffix in _UNSUPPORTED_LANGUAGE_SUFFIXES
        or name.split(".", maxsplit=1)[0] in _UNSUPPORTED_LANGUAGE_STEMS
        or _FIXTURE_SEGMENTS.search(relative) is not None
        or relative.endswith(f"{_SERVICE_LOADER_DIR}{name}")
    )


def _classifiable_name(root: Path, relative: str) -> tuple[str, str] | None:
    """Return (name, suffix) only for a file that RESOLVES inside `root`.

    `is_file()` follows symlinks, so a dangling link or a link to a directory is
    rejected here; `commonpath` on the resolved pair rejects one that escapes the
    tree. The returned name/suffix are the LINK's, which is what the class rules
    are written against.
    """
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    path = root / candidate
    if not path.is_file():
        return None
    try:
        resolved_root = root.resolve()
        if os.path.commonpath((resolved_root, path.resolve())) != str(resolved_root):
            return None
    except OSError, ValueError:
        return None
    return candidate.name, candidate.suffix


def _is_ignore_metadata_name(name: str) -> bool:
    """`.gitignore`, `.dockerignore`, `.npmignore`, … but never a `*.ignore` fixture."""
    return name.startswith(".") and name.endswith("ignore")


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
