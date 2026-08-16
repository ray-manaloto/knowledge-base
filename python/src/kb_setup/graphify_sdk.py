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
from collections.abc import Callable
from contextlib import redirect_stderr
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
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
    approved = approve_metadata_zero_node_warning(
        root,
        admission.source_name if admission else "",
        raw_stderr,
        admission.metadata_inventory if admission else (),
    )
    warning_text = "\n".join(
        part
        for part in (
            "" if approved else raw_stderr.strip(),
            *(str(item.message) for item in caught),
        )
        if part
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
            stderr=warning_text,
            detected_sources=len(paths),
            extracted_sources=len(paths) if accepted_zero_nodes else len(paths) - len(failed),
            zero_node_sources=len(failed),
            zero_node_paths=failed,
            coverage_policy=admission.coverage_policy if admission else None,
            approved_classifications=approved,
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
    """Approve only the reviewed warning backed by exact path/bytes/disposition."""
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
    names = ", ".join(Path(item.relative_path).name for item in warned)
    expected = (
        f"  warning: {len(warned)} source file(s) produced zero nodes and are absent "
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
_LICENSE_PREFIXES = ("LICENSE", "LICENCE", "COPYING")
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
        if (
            name in _NON_SOURCE_NAMES
            or suffix in _NON_SOURCE_SUFFIXES
            or name.upper().startswith(_LICENSE_PREFIXES)
            or _is_ignore_metadata_name(name)
        ):
            non_source.append(relative)
        elif (
            name in _UNSUPPORTED_LANGUAGE_NAMES
            or suffix in _UNSUPPORTED_LANGUAGE_SUFFIXES
            or name.split(".")[0] in _UNSUPPORTED_LANGUAGE_STEMS
            or _FIXTURE_SEGMENTS.search(relative) is not None
            or relative.endswith(f"{_SERVICE_LOADER_DIR}{name}")
        ):
            unsupported.append(relative)
        else:
            unresolved.append(relative)
    return tuple(sorted(non_source)), tuple(sorted(unsupported)), tuple(sorted(unresolved))


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
