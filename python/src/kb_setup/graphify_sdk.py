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
from collections.abc import Callable
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from graphify.build import build, build_from_json, build_merge
from graphify.extract import collect_files, extract


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
