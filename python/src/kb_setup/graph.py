# Copyright (c) 2026 Raymond Manaloto
"""Build / update the knowledge graph from committed inputs.

Reproducibility model: the graph is rebuildable from two committed things —
`sources/*.manifest` (external repo pins) and `sources/extractions/*.json` (the
non-free host-agent doc extractions). The external repos themselves are cloned on
demand and gitignored — and so is everything under `graphify-out/` except the
authored `memory/`: `graph.json` is DERIVED, far past git's limits at aggregate
scale, and consumers reach it via `kb-serve` (MCP) or a pushed graph DB, never a
git blob. (This paragraph claimed graph.json + manifest.json were committed
until 2026-08-05 — stale since the aggregate outgrew git, flagged by a lane
mid-#175.) `build()` composes everything in ONE N-ary merge and ends in the
final labelled state; `refresh_self` (kb-watch) recomposes from the recorded
inputs rather than patching the artifact in place.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import queue as queue_module
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, deque
from dataclasses import dataclass, replace
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import msgspec

from kb_setup import atomic, graph_checks, graphify_health, graphify_ops
from kb_setup import manifest as mf
from kb_setup.graphify_env import (
    assert_pinned_graphify,
    clean_env,
    graphify_exe,
    graphify_python,
    pinned_graphify_version,
)

if TYPE_CHECKING:
    from kb_setup.currency.config import ToolSpec


class _ResultQueue(Protocol):
    def put(self, item: object) -> None: ...

    def get_nowait(self) -> object: ...


class SourcePathEvidence(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Bounded identity and content evidence for one detector path."""

    path: str
    sha256: str | None = None
    size: int | None = None
    file_type: str = "regular"


class SourceCensusReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Read-only detector outcome for one immutable source pin."""

    source: str
    kind: str
    status: str
    declared_pin: str = ""
    resolved_commit: str = ""
    tree_digest: str = ""
    categories: tuple[str, ...] = ()
    detected_count: int | None = None
    unclassified_count: int = 0
    ignored_count: int = 0
    #: Files absorbed as a language Graphify cannot parse. Counted, and tallied
    #: per extension, so this stays measurable corpus loss instead of becoming
    #: an invisible allowlist entry.
    unsupported_language_count: int = 0
    unsupported_language_tally: tuple[tuple[str, int], ...] = ()
    #: The unclassified paths no reviewed class absorbed — the ones that block.
    #: `unclassified` below can be a thousand entries of which all but these are
    #: absorbed, so a failure report that shows only `unclassified` hides its own
    #: answer behind the display bound.
    unresolved: tuple[str, ...] = ()
    #: Unbounded total behind the display-bounded `unresolved` tuple above.
    unresolved_count: int = 0
    unclassified: tuple[SourcePathEvidence, ...] = ()
    ignored: tuple[SourcePathEvidence, ...] = ()
    stderr: str = ""


class DetectionCensusReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Deterministic complete-corpus receipt; never authorizes graph mutation."""

    schema_version: int = 1
    state: str = "complete"
    total_sources: int = 0
    status_counts: tuple[tuple[str, int], ...] = ()
    category_counts: tuple[tuple[str, int], ...] = ()
    integrity_errors: tuple[str, ...] = ()
    sources: tuple[SourceCensusReceipt, ...] = ()


class GraphifyBuildReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Content-bound proof that a complete build produced the current graph."""

    schema_version: int
    status: str
    runtime_version: str
    graph_sha256: str
    graph_bytes: int
    node_count: int
    edge_count: int
    hyperedge_count: int
    input_fingerprints_sha256: str
    recorded_at_ns: int
    warnings: tuple[str, ...] = ()


class SourceGitProvenance(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Manifest declaration and independently observed clone identities."""

    declared_pin: str
    resolved_commit: str = ""
    tree_digest: str = ""
    failure_category: str = ""
    detail: str = ""


_MERGE_SCRIPT = Path(__file__).with_name("_merge_docs.py")
_BUILD_RECEIPT_NAME = "build-receipt.json"

_EXPECTED_UNCLASSIFIED = (
    graphify_health.ExpectedUnclassifiedFile(
        source_name="Attacca",
        relative_path=".claudeignore",
        content_sha256="ea4bc0ca648a2339096adda7b96bc619eae53d96c7ccd4a1fe7d3f6dcf86319a",
        classification="reviewed-root-ignore-metadata",
    ),
    graphify_health.ExpectedUnclassifiedFile(
        source_name="Attacca",
        relative_path=".github/BOILERPLATE_VERSION",
        content_sha256="2819592ffada78626fb51ebec43f23a97c1447270ec7f96b0567f830f530c462",
        # Operational input read by scripts/validate-plugins.mjs at this immutable pin.
        classification="reviewed-version-marker",
    ),
)

# `Attacca` emits EIGHT metadata-only JSON files, which is why the truncation
# handling in `graphify_sdk._zero_node_warning_matches` exists: graphify shows
# five names then "(+3 more)", so the old whole-name reconstruction could never
# have matched this source however correctly it was registered.
#
# The set is closed, not sampled. 18 files on disk carry a code extension;
# `website/package-lock.json` is in graphify's `detect.py:_SKIP_FILES` so it is
# never scanned, which is graphify's own "found 17 code"; 9 of those 17 produce
# nodes; 17 - 9 = the 8 below. Hashes taken at pin 34a52ce09db1.
_ATTACCA_METADATA_ONLY_PATHS = (
    (".claude/settings.json", "546fd30432a10ecb0f9001b81d4dc1eeaacadf30895a1bff489a215cac443e58"),
    (
        ".claude-plugin/marketplace.json",
        "2cbb15ef62c4b5786e52658e9e1f3231c8544206907529c1e4355f925348363d",
    ),
    (
        "plugins/attacca-core/.claude-plugin/plugin.json",
        "bc3467422688bff8f3c6ccfd156a65bff7ae81bdf95c7f369cf24706168bc519",
    ),
    (
        "plugins/attacca-core/hooks/hooks.json",
        "f77693d5fd143fe932754dac3703b02d1c703bb3f5af353c57e96e46657e11a1",
    ),
    (
        "plugins/attacca-init/.claude-plugin/plugin.json",
        "3d1388fe93229e64cd652f9588ffc2f4fe24665223ebbdc847f53d85a6295bb5",
    ),
    (
        "plugins/attacca-security/.claude-plugin/plugin.json",
        "321eb2e27ae8ed992c84dbe9f327eb3c091728d0c11b3adf5f6e9db0484f7393",
    ),
    (
        "plugins/attacca-security/hooks/hooks.json",
        "1fcf319836784f10d6639cb991978388bf1238fa5837032a475fca0df50cfc50",
    ),
    ("template/settings.json", "20a9b142dd55131bf2968632b84bdf63a9a7359e238bf6a5ff46d94e2008a3a1"),
)

_EXPECTED_METADATA_ONLY = (
    graphify_health.ExpectedMetadataOnly(
        source_name="10x-Team",
        relative_path=".claude-plugin/marketplace.json",
        content_sha256="c90e241178951c4457dc98de02e33abf86de04ec3a98b012cacff8334c83ca70",
        skipped_disposition="data json (not a config/manifest)",
    ),
    graphify_health.ExpectedMetadataOnly(
        source_name="10x-Team",
        relative_path=".claude-plugin/plugin.json",
        content_sha256="033d0f42d41ae76ffb008b559feaf5f4038f85a1c034f4c60432edcafa6d5d11",
        skipped_disposition="data json (not a config/manifest)",
    ),
    graphify_health.ExpectedMetadataOnly(
        source_name="10x-Team",
        relative_path=".cursor-plugin/plugin.json",
        content_sha256="f06e9e3dbf4d14fa987823811363b1a03f155e94c7df9877c498e26fad159813",
        skipped_disposition="data json (not a config/manifest)",
    ),
    graphify_health.ExpectedMetadataOnly(
        source_name="10x-Team",
        relative_path="gemini-extension.json",
        content_sha256="a2dff2cfbac3d49bbe87501ccb93460b8f3e8a4c0d39787fd4d933cea2318608",
        skipped_disposition="data json (not a config/manifest)",
    ),
    # All eight are object-rooted JSON that `json_config._is_config_json` declines,
    # which is the ONLY route to a zero-node JSON with an object root — the other
    # skip ("data json (non-object root)") cannot apply to any of them.
    *(
        graphify_health.ExpectedMetadataOnly(
            source_name="Attacca",
            relative_path=relative_path,
            content_sha256=content_sha256,
            skipped_disposition="data json (not a config/manifest)",
        )
        for relative_path, content_sha256 in _ATTACCA_METADATA_ONLY_PATHS
    ),
)

# `website/src/pages/index.astro`, the ONE reviewed partial extraction (#328).
#
# MEASURED, because the warning states no count and a remedy chosen without one
# is chosen blind: the file yields exactly 1 node — its own file stub — and none
# of its 25 named symbols. Enumerated from the file at this pin: 5 frontmatter
# consts (GITHUB_URL, BRANCH, plugins, SKILLS, FEATURED), 7 named functions in
# the inline <script> (copyInstall, appendLine, appendEcho, appendAgent,
# runCommand, updateSuggestions, openPluginModal) and 13 script-level bindings.
# Control arm: `scripts/validate-plugins.mjs` in the same source yields 9 symbol
# nodes, so graphify's JS extractor works here and the loss is `.astro`-specific.
#
# Root cause is NOT the generic parse-recovery of #2551. `graphify/extract.py`
# `extract_astro` parses the WHOLE file as JS — its own docstring says that
# "produces a top-level ERROR node because the template is not valid JS" — and
# then regex-rescues IMPORTS only. `extract_vue`, 70 lines further down the same
# file, masks the non-<script> regions and recovers "imports, symbols, and type
# refs". This file has no imports at all, so the rescue recovers nothing.
# Upstream #2551 is watched in `currency.toml` so its close surfaces as movement.
_EXPECTED_PARTIAL_EXTRACTION = (
    # OpenSymphony's deliberately-broken python fixture — 53 bytes, one function
    # with a missing colon, and the file is NAMED `malformed.py`. Being
    # unparsable is its entire purpose as a test input, so the warning is
    # expected forever rather than pending a fix.
    #
    # MEASURED, not inferred, and the measurement is the reason this entry is
    # cheap: graphify says "1 symbol(s) extracted", and the sub-graph carries
    # TWO nodes for the path — the file stub `malformed.py` AND `broken()`. The
    # file defines exactly one symbol, so **nothing is lost** and
    # `lost_symbols` is 0. That is the opposite of the Attacca `.astro` entry
    # below, where 1 node is the stub alone and 25 named symbols are gone; do not
    # read the two entries as the same situation because they share a warning.
    graphify_health.ExpectedPartialExtraction(
        source_name="OpenSymphony",
        relative_path="crates/opensymphony-code-intel/fixtures/python/malformed.py",
        content_sha256="5812469eaff4436903f09258c1dc76da0ff4a8057c3a3fa083dc29bb3d158e6f",
        first_error_line=2,
        extracted_nodes=2,
        lost_symbols=0,
        reason=(
            "a 53-byte fixture named malformed.py whose only function omits a colon; "
            "tree-sitter error recovery still yields the file stub and broken(), so "
            "the partial extraction loses nothing"
        ),
    ),
    # cclint's control-character security test. Line 28 embeds a literal NUL and
    # 0x1f — verified by reading the bytes, not the rendered text, which displays
    # them as spaces — because the test's subject IS rejecting control characters.
    # tree-sitter cannot parse past them, so the loss is permanent and expected.
    #
    # MEASURED from the sub-graph: exactly 1 node survives (the file stub), and
    # the file names 21 `describe`/`it` blocks, all lost. Same shape as the
    # `.astro` entry below and the OPPOSITE of the `malformed.py` entry above,
    # where recovery was complete — which is why each entry carries its own
    # numbers rather than sharing a class.
    graphify_health.ExpectedPartialExtraction(
        source_name="cclint",
        relative_path="tests/unit/infrastructure/security/PathValidator.test.ts",
        content_sha256="8bacc406e7f3b40412570618c0ad219820ec2838d8a7f2d9d7c4f719cabb2c44",
        first_error_line=28,
        extracted_nodes=1,
        lost_symbols=21,
        reason=(
            "the file embeds literal NUL and 0x1f bytes as the fixture for a "
            "control-character rejection test; tree-sitter cannot parse past them "
            "and recovers no symbols"
        ),
    ),
    graphify_health.ExpectedPartialExtraction(
        source_name="Attacca",
        relative_path="website/src/pages/index.astro",
        content_sha256="355b3510c6b9b7ecba2e23a70eeebbc73edf8c372a91cba74d497479540aa942",
        first_error_line=1,
        extracted_nodes=1,
        lost_symbols=25,
        reason=(
            "graphify extract_astro parses the whole .astro file as JS and "
            "regex-rescues imports only; this file has none (#2551)"
        ),
    ),
)

# The tool whose artifacts `kb-build` produces. Named explicitly so a
# multi-tool currency.toml cannot silently stamp the wrong tool.
_STAMPED_TOOL = "graphify"

#: Permission bits restored on the swapped-in graph.json — see
#: `_recompose_into_temp`'s docstring. Same value and same reason as
#: `prose._ARTIFACT_MODE`; a separate constant because these are separate
#: modules and the integer is not worth a shared import.
_GRAPH_MODE = 0o644


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"  $ {' '.join(cmd)}")
    # clean_env: no non-Claude provider key reaches graphify (Claude-Code-only).
    result = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        env=clean_env(),
        capture_output=True,
    )
    if result.stdout:
        sys.stdout.buffer.write(result.stdout)
        sys.stdout.buffer.flush()
    if result.stderr:
        sys.stderr.buffer.write(result.stderr)
        sys.stderr.buffer.flush()
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)
    if result.stderr:
        digest = hashlib.sha256(result.stderr).hexdigest()
        raise SystemExit(
            "[graphify] refusing warning-bearing subprocess success "
            f"(stderr_bytes={len(result.stderr)}, stderr_sha256={digest})"
        )


def _ensure_clone(m: mf.Manifest) -> None:
    """Clone m.url at m.commit into m.clone_dir (gitignored).

    Re-clones if the working tree is missing or lacks git history.
    """
    d = m.clone_dir
    if not (d / ".git").is_dir():
        if d.exists():
            shutil.rmtree(d)
        print(f"  cloning {m.name} @ {m.commit[:10]}")
        subprocess.run(
            ["git", "clone", "--quiet", "--branch", m.ref, m.url, str(d)],
            check=True,
            timeout=600,
        )
    # An EXISTING clone predates any pin advance, so the newly-pinned commit is
    # simply not in it yet and `checkout` dies with "fatal: unable to read tree".
    # Measured 2026-07-23: `kb-update -- claude-plugins-community` advanced the pin
    # to 086db464, the local clone still sat at 07fb1efe, and the whole task
    # aborted — i.e. update was broken for every source whose clone already
    # existed, which is every source after its first build. Fetch when (and only
    # when) the object is absent, so the common no-op path stays offline.
    have = subprocess.run(
        ["git", "-C", str(d), "cat-file", "-e", f"{m.commit}^{{commit}}"],
        check=False,
        capture_output=True,
        timeout=60,
    )
    if have.returncode != 0:
        print(f"  fetching {m.name} @ {m.commit[:10]} (not in local clone)")
        subprocess.run(
            ["git", "-C", str(d), "fetch", "--quiet", "--no-tags", "origin", m.commit],
            check=True,
            timeout=600,
        )
    # The pin may be either a commit object or an annotated-tag object. Both
    # legitimately peel to one commit/tree, so verification is against the
    # peeled identities while checkout still names the exact manifest object.
    expected_commit = _rev_parse(d, f"{m.commit}^{{commit}}")
    expected_tree = _rev_parse(d, f"{m.commit}^{{tree}}")
    subprocess.run(
        [
            "git",
            "-C",
            str(d),
            "-c",
            "advice.detachedHead=false",
            "checkout",
            "--quiet",
            "--detach",
            m.commit,
        ],
        check=True,
        timeout=120,
    )
    actual_commit = _rev_parse(d, "HEAD^{commit}")
    actual_tree = _rev_parse(d, "HEAD^{tree}")
    if (actual_commit, actual_tree) != (expected_commit, expected_tree):
        raise RuntimeError(
            f"{m.name}: checkout did not produce the pinned commit/tree "
            f"({actual_commit[:12]}/{actual_tree[:12]} != "
            f"{expected_commit[:12]}/{expected_tree[:12]})"
        )


def _rev_parse(clone_dir: Path, revision: str) -> str:
    """Resolve one required Git object identity; unknown is an error, never a pass."""
    proc = subprocess.run(
        ["git", "-C", str(clone_dir), "rev-parse", "--verify", revision],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    identity = proc.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", identity):
        raise RuntimeError(f"git returned an invalid object identity for {revision!r}")
    return identity


def _nodes_by_source_file(nodes: list[object]) -> dict[str, int]:
    """Per-file node totals from the sub-graph graphify just wrote.

    This is what turns a reviewed partial-extraction entry from an assertion into
    a measurement: the entry states how many nodes the file contributes, and the
    approval is checked against what actually landed.
    """
    counts: Counter[str] = Counter()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        source_file = node.get("source_file")
        if isinstance(source_file, str) and source_file:
            counts[source_file] += 1
    return dict(counts)


def _extract_code(repo_root: Path, name: str) -> bool:
    """AST-extract one source's code into its own sub-graph; True iff it made nodes.

    `--force` = clean full re-scan, no cache/manifest gate (a true reproduction). A
    prose-only repo yields an empty graph and graphify exits non-zero; that is
    NON-fatal here (its value comes from the host-agent prose wave), so the status is
    swallowed and emptiness is read from the sub-graph.
    """
    from kb_setup import graphify_health, graphify_sdk

    source_root = repo_root / "sources" / name
    print(f"  $ graphify extract sources/{name} --code-only --force")
    proc = subprocess.run(
        [graphify_exe(repo_root), "extract", f"sources/{name}", "--code-only", "--force"],
        cwd=repo_root,
        check=False,
        env=clean_env(),
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    sub = repo_root / "sources" / name / "graphify-out" / "graph.json"
    nodes: list[object] = []
    try:
        data = json.loads(sub.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        data = {}
    raw_nodes = data.get("nodes", [])
    if isinstance(raw_nodes, list):
        nodes = raw_nodes
    inventory = tuple(item for item in _EXPECTED_METADATA_ONLY if item.source_name == name)
    partial = tuple(item for item in _EXPECTED_PARTIAL_EXTRACTION if item.source_name == name)
    approved, residual = graphify_sdk.account_for_extract_stderr(
        source_root,
        proc.stderr or "",
        graphify_sdk.ExtractWarningReview(
            source_name=name,
            metadata_inventory=inventory,
            partial_inventory=partial,
            extracted_nodes_by_path=_nodes_by_source_file(nodes),
        ),
    )
    receipt = graphify_health.assess(
        graphify_health.GraphifyOperation.EXTRACT,
        graphify_health.GraphifyEvidence(
            observed=True,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            approved_classifications=approved,
            residual_stderr=residual,
            detected_sources=1,
            extracted_sources=1 if nodes else 0,
            zero_node_sources=0 if nodes else 1,
            zero_node_paths=() if nodes else (name,),
            mode="ast",
        ),
    )
    graphify_health.require_complete(receipt)
    return True


_DETECT_WORKERS = 1
_DETECT_SOURCE_TIMEOUT_SECONDS = 120.0
_DETECT_GLOBAL_TIMEOUT_SECONDS = 900.0
_CENSUS_MAX_PATHS_PER_CLASS = 128
_CENSUS_MAX_PATH_LENGTH = 240
_CENSUS_MAX_STDERR_LENGTH = 2000
_CENSUS_MAX_SOURCE_LENGTH = 120
_CENSUS_MAX_RECEIPT_BYTES = 8 * 1024 * 1024
_SNAPSHOT_MAX_PATH_LENGTH = 4096


def _bounded_identity(value: str, limit: int) -> str:
    """Bound a field while retaining collision-resistant identity evidence."""
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    suffix = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"{normalized[: limit - 18]}~{suffix}"


def _detect_worker(
    root: Path,
    source_name: str,
    policy: graphify_health.SourceCoveragePolicy,
    result_queue: _ResultQueue,
) -> None:
    """Child-process detection body; parent owns all timeout enforcement."""
    from kb_setup import graphify_sdk

    try:
        result, receipt = graphify_sdk.observe_detect(
            root,
            source_name=source_name,
            coverage_policy=policy,
            timeout_seconds=_DETECT_SOURCE_TIMEOUT_SECONDS,
        )
        result_queue.put(_source_census_receipt(root, source_name, result, receipt))
    except (
        OSError,
        RuntimeError,
        TimeoutError,
        ValueError,
        graphify_health.IncompleteGraphifyOperationError,
    ) as exc:
        detail = _bounded_identity(str(exc), 900)
        result_queue.put(
            SourceCensusReceipt(
                source=source_name,
                kind="code",
                status="error",
                categories=("detector-error",),
                stderr=_bounded_identity(
                    f"{type(exc).__name__}: {detail}", _CENSUS_MAX_STDERR_LENGTH
                ),
            )
        )


def _source_census_receipt(
    root: Path,
    source_name: str,
    result: dict,
    receipt: graphify_health.GraphifyReceipt,
) -> SourceCensusReceipt:
    unclassified_paths = graphify_sdk_paths(root, result.get("unclassified", []))
    ignored_paths = graphify_sdk_paths(root, result.get("ignored", []))
    return SourceCensusReceipt(
        source=source_name,
        kind="code",
        status=receipt.state.value,
        categories=tuple(sorted(receipt.reasons)),
        detected_count=receipt.detected_sources,
        unclassified_count=len(unclassified_paths),
        ignored_count=len(ignored_paths),
        # The receipt's `*_paths` tuples are display-bounded at 12 entries, so
        # counts and tallies come from its unbounded fields, never from len().
        unsupported_language_count=receipt.unsupported_language_count,
        unsupported_language_tally=receipt.unsupported_language_tally,
        unresolved=receipt.unresolved_paths,
        unresolved_count=receipt.unresolved_count,
        unclassified=tuple(
            _source_path_evidence(root, path)
            for path in unclassified_paths[:_CENSUS_MAX_PATHS_PER_CLASS]
        ),
        ignored=tuple(
            _source_path_evidence(root, path)
            for path in ignored_paths[:_CENSUS_MAX_PATHS_PER_CLASS]
        ),
        stderr=_bounded_identity(receipt.stderr, _CENSUS_MAX_STDERR_LENGTH),
    )


def graphify_sdk_paths(root: Path, paths: object) -> tuple[str, ...]:
    """Normalize detector paths without importing Graphify in the parent process."""
    if not isinstance(paths, list):
        return ()
    absolute_root = root.resolve()
    normalized: list[str] = []
    for raw in paths:
        path = Path(str(raw))
        absolute_path = path if path.is_absolute() else (root / path).resolve()
        try:
            relative = str(absolute_path.relative_to(absolute_root))
        except ValueError:
            relative = str(path)
        normalized.append(relative)
    return tuple(sorted(set(normalized)))


def _source_path_evidence(root: Path, relative_path: str) -> SourcePathEvidence:
    bounded_path = _bounded_identity(relative_path, _CENSUS_MAX_PATH_LENGTH)
    if len(relative_path) > _SNAPSHOT_MAX_PATH_LENGTH:
        return SourcePathEvidence(path=bounded_path, file_type="path-too-long")
    path = root / relative_path
    try:
        resolved_root = root.resolve()
        resolved_path = path.resolve(strict=True)
        if os.path.commonpath((resolved_root, resolved_path)) != str(resolved_root):
            return SourcePathEvidence(path=bounded_path, file_type="out-of-root")
        if path.is_symlink():
            return SourcePathEvidence(path=bounded_path, file_type="symlink")
        if path.is_dir():
            return _git_tree_evidence(root, relative_path)
    except OSError:
        return SourcePathEvidence(path=bounded_path, file_type="unreadable")
    return _regular_path_evidence(path, bounded_path)


def source_path_evidence(root: Path, relative_path: str) -> SourcePathEvidence:
    """Return content evidence for one source-relative path."""
    return _source_path_evidence(root, relative_path)


def _regular_path_evidence(path: Path, bounded_path: str) -> SourcePathEvidence:
    try:
        if not path.is_file():
            return SourcePathEvidence(path=bounded_path, file_type="non-regular")
        content = path.read_bytes()
    except OSError:
        return SourcePathEvidence(path=bounded_path, file_type="unreadable")
    return SourcePathEvidence(
        path=bounded_path,
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
    )


def _git_tree_evidence(root: Path, relative_path: str) -> SourcePathEvidence:
    bounded_path = _bounded_identity(relative_path, _CENSUS_MAX_PATH_LENGTH)
    directory = root / relative_path
    digest = hashlib.sha256()
    entries = 0
    total_size = 0
    try:
        paths = sorted(directory.rglob("*"), key=lambda path: str(path.relative_to(directory)))
        for path in paths:
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                return SourcePathEvidence(path=bounded_path, file_type="directory-unsafe")
            relative = str(path.relative_to(directory))
            digest.update(relative.encode())
            digest.update(b"\0d\0" if path.is_dir() else b"\0f\0")
            if path.is_file():
                content = path.read_bytes()
                total_size += len(content)
                digest.update(hashlib.sha256(content).digest())
            entries += 1
    except OSError:
        return SourcePathEvidence(path=bounded_path, file_type="directory-unreadable")
    return SourcePathEvidence(
        path=bounded_path,
        sha256=digest.hexdigest(),
        size=total_size,
        file_type=f"snapshot-tree:{entries}",
    )


def _run_detection_census(
    jobs: list[tuple[str, Path, graphify_health.SourceCoveragePolicy]],
) -> list[tuple[str, str]]:
    receipts = _run_detection_census_receipts(jobs)
    return sorted(
        (receipt.source, _source_census_failure_detail(receipt))
        for receipt in receipts
        if receipt.status != graphify_health.GraphifyState.COMPLETE.value
    )


def _source_census_failure_detail(receipt: SourceCensusReceipt) -> str:
    if receipt.status == "timed-out":
        return f"TimeoutError: {receipt.stderr}"
    categories = ", ".join(receipt.categories) or receipt.status
    evidence: list[str] = []
    if receipt.unresolved:
        evidence.append(f"unresolved({receipt.unresolved_count})={list(receipt.unresolved[:12])!r}")
    elif receipt.unclassified:
        evidence.append(f"unclassified={[item.path for item in receipt.unclassified[:12]]!r}")
    if receipt.ignored:
        evidence.append(f"ignored={[item.path for item in receipt.ignored[:12]]!r}")
    if receipt.stderr:
        evidence.append(f"detail={receipt.stderr[:240]}")
    suffix = f"; {'; '.join(evidence)}" if evidence else ""
    exception = "RuntimeError" if receipt.status == "error" else "IncompleteGraphifyOperationError"
    return f"{exception}: Graphify detect failed closed ({receipt.status}): {categories}{suffix}"


def _verify_source_provenance(manifest: mf.Manifest) -> SourceGitProvenance:
    """Resolve the exact declared object; mutable worktree state is irrelevant."""
    root = manifest.clone_dir
    declared_pin = _bounded_identity(manifest.commit, 80)
    if not (root / ".git").is_dir():
        return SourceGitProvenance(
            declared_pin=declared_pin,
            failure_category="missing-clone",
            detail="verified Git clone is missing",
        )
    if not re.fullmatch(r"[0-9a-f]{40,64}", manifest.commit):
        return SourceGitProvenance(
            declared_pin=declared_pin,
            failure_category="invalid-pin",
            detail="declared pin is not a full Git object identity",
        )
    try:
        resolved_commit = _rev_parse(root, f"{manifest.commit}^{{commit}}")
        tree_digest = _rev_parse(root, f"{manifest.commit}^{{tree}}")
    except OSError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired:
        return SourceGitProvenance(
            declared_pin=declared_pin,
            failure_category="pin-unreachable",
            detail="declared pin commit/tree is unavailable in the verified clone",
        )
    return SourceGitProvenance(
        declared_pin=declared_pin,
        resolved_commit=resolved_commit,
        tree_digest=tree_digest,
    )


def _create_source_snapshot(
    manifest: mf.Manifest, provenance: SourceGitProvenance, destination: Path
) -> SourceGitProvenance:
    """Create an independent disposable clone at the exact verified commit."""
    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-checkout",
                "--no-local",
                "--no-hardlinks",
                "--no-tags",
                "--",
                manifest.clone_dir.resolve().as_uri(),
                str(destination),
            ],
            check=True,
            capture_output=True,
            timeout=600,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(destination),
                "fetch",
                "--quiet",
                "--no-tags",
                "origin",
                provenance.resolved_commit,
            ],
            check=True,
            capture_output=True,
            timeout=600,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "advice.detachedHead=false",
                "-C",
                str(destination),
                "checkout",
                "--quiet",
                "--detach",
                provenance.resolved_commit,
            ],
            check=True,
            capture_output=True,
            timeout=600,
        )
        _assert_disposable_clone_identity(destination, provenance)
    except (
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as exc:
        shutil.rmtree(destination, ignore_errors=True)
        return msgspec.structs.replace(
            provenance,
            failure_category="snapshot-failed",
            detail=_bounded_identity(
                f"{type(exc).__name__}: immutable Git tree materialization failed",
                _CENSUS_MAX_STDERR_LENGTH,
            ),
        )
    return provenance


def _assert_disposable_clone_identity(clone_dir: Path, provenance: SourceGitProvenance) -> None:
    """Fail unless a disposable clone remains exact, detached, and clean."""
    alternates = clone_dir / ".git" / "objects" / "info" / "alternates"
    if alternates.exists():
        raise RuntimeError("disposable clone inherited an object alternates dependency")
    head = _rev_parse(clone_dir, "HEAD^{commit}")
    tree = _rev_parse(clone_dir, "HEAD^{tree}")
    symbolic = subprocess.run(
        ["git", "-C", str(clone_dir), "symbolic-ref", "-q", "HEAD"],
        check=False,
        capture_output=True,
        timeout=60,
    )
    status = subprocess.run(
        ["git", "-C", str(clone_dir), "status", "--porcelain=v1", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout
    # Name WHICH invariant broke. The single undifferentiated message this
    # replaces cost a whole investigation to get behind: four distinct failures
    # — a rewritten commit, a changed tree, a re-attached HEAD, and a detector
    # that wrote into its own input — all surfaced as one sentence that named
    # none of them, and the only way to tell them apart was to edit this line.
    drift: list[str] = []
    if head != provenance.resolved_commit:
        drift.append(f"commit {provenance.resolved_commit[:12]}->{head[:12]}")
    if tree != provenance.tree_digest:
        drift.append(f"tree {provenance.tree_digest[:12]}->{tree[:12]}")
    if symbolic.returncode == 0:
        drift.append("HEAD re-attached to a branch")
    entries = [line for line in status.splitlines() if not _is_detector_sidecar(line)]
    if entries:
        drift.append(f"{len(entries)} dirty path(s): {entries[:8]}")
    if drift:
        raise RuntimeError(f"disposable clone changed during detection: {'; '.join(drift)}")


#: Graphify's detector is not read-only: when a tree contains an Office or
#: Google-Workspace document it converts it and writes the markdown sidecar to
#: `<root>/graphify-out/converted/`. That path is HARDCODED in `detect.py`
#: (`converted_dir = root / GRAPHIFY_OUT / "converted"`); `cache_root` redirects
#: only the word-count cache, so there is no native knob to move it. `cognee`
#: ships `example.docx` and `example.pptx`, which is why it alone drifted.
_DETECTOR_OUTPUT_PREFIX = "graphify-out/"


def _is_detector_sidecar(status_line: str) -> bool:
    """True only for an UNTRACKED entry under Graphify's own output directory.

    Deliberately narrow. `??` is git's untracked code, so a MODIFIED or DELETED
    tracked file under `graphify-out/` still counts as drift — a source that
    tracks that directory must not get a free pass, and the point of this check
    is that the detector never alters its input's *content*.
    """
    if not status_line.startswith("?? "):
        return False
    path = status_line[3:].strip().strip('"')
    return path.startswith(_DETECTOR_OUTPUT_PREFIX)


def materialize_source_snapshot(manifest: mf.Manifest, destination: Path) -> SourceGitProvenance:
    """Materialize one verified, detached source snapshot for a public consumer."""
    _ensure_clone(manifest)
    provenance = _verify_source_provenance(manifest)
    if provenance.failure_category:
        raise ValueError(f"{manifest.name}: {provenance.failure_category}: {provenance.detail}")
    materialized = _create_source_snapshot(manifest, provenance, destination)
    if materialized.failure_category:
        raise ValueError(f"{manifest.name}: {materialized.failure_category}: {materialized.detail}")
    return materialized


def detection_census(manifests: list[mf.Manifest]) -> DetectionCensusReceipt:
    """Return a read-only, deterministic receipt for every configured source."""
    manifest_names = [manifest.name for manifest in manifests]
    duplicate_manifests = sorted(
        name for name, count in Counter(manifest_names).items() if count != 1
    )
    if duplicate_manifests:
        names = ", ".join(
            _bounded_identity(name, _CENSUS_MAX_SOURCE_LENGTH) for name in duplicate_manifests[:12]
        )
        raise ValueError(f"duplicate manifest source names: {names}")
    with tempfile.TemporaryDirectory(prefix="kb-graphify-census-") as snapshot_dir:
        return _detection_census_from_snapshots(manifests, Path(snapshot_dir))


def _detection_census_from_snapshots(
    manifests: list[mf.Manifest], snapshot_dir: Path
) -> DetectionCensusReceipt:
    from kb_setup import graphify_sdk

    sources: list[SourceCensusReceipt] = []
    jobs: list[tuple[str, Path, graphify_health.SourceCoveragePolicy]] = []
    verified: dict[str, SourceGitProvenance] = {}
    for index, manifest in enumerate(sorted(manifests, key=lambda item: item.name)):
        provenance = _verify_source_provenance(manifest)
        if provenance.failure_category:
            sources.append(
                SourceCensusReceipt(
                    source=_bounded_identity(manifest.name, _CENSUS_MAX_SOURCE_LENGTH),
                    kind=_bounded_identity(manifest.kind, 32),
                    status="provenance-failed",
                    declared_pin=provenance.declared_pin,
                    resolved_commit=provenance.resolved_commit,
                    tree_digest=provenance.tree_digest,
                    categories=(provenance.failure_category,),
                    stderr=_bounded_identity(provenance.detail, _CENSUS_MAX_STDERR_LENGTH),
                )
            )
            continue
        verified[manifest.name] = provenance
        if manifest.kind == "docs":
            sources.append(
                SourceCensusReceipt(
                    source=_bounded_identity(manifest.name, _CENSUS_MAX_SOURCE_LENGTH),
                    kind="docs",
                    status="skipped-docs",
                    declared_pin=provenance.declared_pin,
                    resolved_commit=provenance.resolved_commit,
                    tree_digest=provenance.tree_digest,
                )
            )
            continue
        root = snapshot_dir / f"source-{index:04d}"
        snapshot = _create_source_snapshot(manifest, provenance, root)
        if snapshot.failure_category:
            sources.append(
                SourceCensusReceipt(
                    source=_bounded_identity(manifest.name, _CENSUS_MAX_SOURCE_LENGTH),
                    kind="code",
                    status="provenance-failed",
                    declared_pin=snapshot.declared_pin,
                    resolved_commit=snapshot.resolved_commit,
                    tree_digest=snapshot.tree_digest,
                    categories=(snapshot.failure_category,),
                    stderr=_bounded_identity(snapshot.detail, _CENSUS_MAX_STDERR_LENGTH),
                )
            )
            verified.pop(manifest.name, None)
            continue
        reviewed = tuple(
            item for item in _EXPECTED_UNCLASSIFIED if item.source_name == manifest.name
        )
        jobs.append(
            (
                manifest.name,
                root,
                graphify_sdk.source_detection_policy(root, manifest.name, reviewed),
            )
        )
    integrity_errors: tuple[str, ...] = ()
    if jobs:
        received = _run_detection_census_receipts(jobs)
        received = _require_post_detection_clone_identity(jobs, received, verified)
        bound, integrity_errors = _bind_detection_receipts(jobs, received, verified)
        sources.extend(bound)
    sources.sort(key=lambda receipt: receipt.source)
    status_counts = Counter(receipt.status for receipt in sources)
    category_counts = Counter(category for receipt in sources for category in receipt.categories)
    census = DetectionCensusReceipt(
        state=(
            "incomplete"
            if integrity_errors
            or any(source.status not in {"complete", "skipped-docs"} for source in sources)
            else "complete"
        ),
        total_sources=len(manifests),
        status_counts=tuple(sorted(status_counts.items())),
        category_counts=tuple(sorted(category_counts.items())),
        integrity_errors=integrity_errors,
        sources=tuple(sources),
    )
    if len(msgspec.json.encode(census)) > _CENSUS_MAX_RECEIPT_BYTES:
        raise ValueError("detection census receipt exceeds the aggregate size bound")
    return census


def _require_post_detection_clone_identity(
    jobs: list[tuple[str, Path, graphify_health.SourceCoveragePolicy]],
    received: list[SourceCensusReceipt],
    verified: dict[str, SourceGitProvenance],
) -> list[SourceCensusReceipt]:
    """Replace detector output if its disposable clone changed during detection."""
    replacements: dict[str, SourceCensusReceipt] = {}
    for name, root, _policy in jobs:
        provenance = verified[name]
        try:
            _assert_disposable_clone_identity(root, provenance)
        except (
            OSError,
            RuntimeError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as exc:
            replacements[name] = SourceCensusReceipt(
                source=name,
                kind="code",
                status="provenance-failed",
                categories=("snapshot-drift",),
                # Carry the exception's own detail. A fixed string here threw
                # away the only description of what actually drifted, so every
                # cause reported identically and none could be diagnosed
                # without editing this file.
                stderr=_bounded_identity(f"{type(exc).__name__}: {exc}", _CENSUS_MAX_STDERR_LENGTH),
            )
    if not replacements:
        return received
    return [row for row in received if row.source not in replacements] + list(replacements.values())


def _bind_detection_receipts(
    jobs: list[tuple[str, Path, graphify_health.SourceCoveragePolicy]],
    received: list[SourceCensusReceipt],
    verified: dict[str, SourceGitProvenance],
) -> tuple[list[SourceCensusReceipt], tuple[str, ...]]:
    """Require exactly one child receipt for every and only expected source name."""
    expected = {name for name, _root, _policy in jobs}
    by_name: dict[str, list[SourceCensusReceipt]] = {}
    for receipt in received:
        by_name.setdefault(receipt.source, []).append(receipt)
    unexpected = sorted(set(by_name) - expected)
    bounded_unexpected = [
        _bounded_identity(name, _CENSUS_MAX_SOURCE_LENGTH) for name in unexpected[:12]
    ]
    integrity_errors = (
        (f"unexpected-receipts:{len(unexpected)}:{','.join(bounded_unexpected)}",)
        if unexpected
        else ()
    )
    bound: list[SourceCensusReceipt] = []
    for name in sorted(expected):
        rows = by_name.get(name, [])
        provenance = verified[name]
        if len(rows) != 1:
            category = "receipt-missing" if not rows else "receipt-duplicate"
            bound.append(
                SourceCensusReceipt(
                    source=_bounded_identity(name, _CENSUS_MAX_SOURCE_LENGTH),
                    kind="code",
                    status="census-integrity-failed",
                    declared_pin=provenance.declared_pin,
                    resolved_commit=provenance.resolved_commit,
                    tree_digest=provenance.tree_digest,
                    categories=(category,),
                    stderr=f"expected exactly one detector receipt; received {len(rows)}",
                )
            )
            continue
        bound.append(
            msgspec.structs.replace(
                rows[0],
                source=_bounded_identity(name, _CENSUS_MAX_SOURCE_LENGTH),
                declared_pin=provenance.declared_pin,
                resolved_commit=provenance.resolved_commit,
                tree_digest=provenance.tree_digest,
            )
        )
    return bound, integrity_errors


def write_detection_census(repo_root: Path, output: Path, receipt: DetectionCensusReceipt) -> Path:
    """Persist a diagnostic only below ignored ``.agent/``; never graphify-out."""
    destination = output if output.is_absolute() else repo_root / output
    agent_root = (repo_root / ".agent").resolve()
    resolved_parent = destination.parent.resolve()
    if os.path.commonpath((agent_root, resolved_parent)) != str(agent_root):
        raise ValueError("detect census output must be under .agent/")
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = _encode_detection_census(receipt) + "\n"
    atomic.write_text(destination, encoded)
    return destination


def _encode_detection_census(receipt: DetectionCensusReceipt) -> str:
    encoded = msgspec.json.encode(receipt)
    if len(encoded) > _CENSUS_MAX_RECEIPT_BYTES:
        raise ValueError("detection census receipt exceeds the aggregate size bound")
    return encoded.decode()


def detection_census_main(repo_root: Path, args: list[str]) -> int:
    """CLI boundary for a complete-corpus or exact-source read-only JSON census."""
    output: Path | None = None
    source_name: str | None = None
    seen: set[str] = set()
    index = 0
    while index < len(args):
        flag = args[index]
        if flag not in {"--output", "--source"}:
            raise ValueError("detect-census accepts only --source NAME and --output PATH")
        if flag in seen:
            raise ValueError(f"{flag} flag may be specified only once")
        if index + 1 >= len(args):
            raise ValueError(f"{flag} requires a value")
        seen.add(flag)
        value = args[index + 1]
        if flag == "--output":
            output = Path(value)
        else:
            source_name = value
        index += 2

    manifests = list(mf.load_all(repo_root / "sources"))
    if source_name is not None:
        manifests = [manifest for manifest in manifests if manifest.name == source_name]
        if not manifests:
            raise ValueError(f"source manifest not found: {source_name}")
    receipt = detection_census(manifests)
    encoded = _encode_detection_census(receipt)
    if output is None:
        print(encoded)
    else:
        destination = write_detection_census(repo_root, output, receipt)
        print(destination.relative_to(repo_root))
    return 0


def _run_detection_census_receipts(
    jobs: list[tuple[str, Path, graphify_health.SourceCoveragePolicy]],
) -> list[SourceCensusReceipt]:
    """Run at most four detector children with hard per-source/global deadlines."""
    context = multiprocessing.get_context("spawn")
    pending = deque(jobs)
    active: dict[BaseProcess, tuple[str, float, _ResultQueue]] = {}
    receipts: list[SourceCensusReceipt] = []
    started = time.monotonic()
    while pending or active:
        while pending and len(active) < _DETECT_WORKERS:
            name, root, policy = pending.popleft()
            queue = context.Queue()
            process = context.Process(target=_detect_worker, args=(root, name, policy, queue))
            process.start()
            active[process] = (name, time.monotonic(), cast("_ResultQueue", queue))
        global_expired = time.monotonic() - started > _DETECT_GLOBAL_TIMEOUT_SECONDS
        _reap_detection_processes(active, receipts, global_expired=global_expired)
        if global_expired:
            receipts.extend(
                SourceCensusReceipt(
                    source=name,
                    kind="code",
                    status="timed-out",
                    categories=("timeout",),
                    stderr="detect global deadline",
                )
                for name, *_ in pending
            )
            pending.clear()
        if active:
            time.sleep(0.02)
    return sorted(receipts, key=lambda receipt: receipt.source)


def _reap_detection_processes(
    active: dict[BaseProcess, tuple[str, float, _ResultQueue]],
    receipts: list[SourceCensusReceipt],
    *,
    global_expired: bool,
) -> None:
    now = time.monotonic()
    for process, (name, source_started, result_queue) in list(active.items()):
        timed_out = global_expired or now - source_started > _DETECT_SOURCE_TIMEOUT_SECONDS
        if timed_out:
            process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
            label = "global deadline" if global_expired else "source timeout"
            receipts.append(
                SourceCensusReceipt(
                    source=name,
                    kind="code",
                    status="timed-out",
                    categories=("timeout",),
                    stderr=f"detect {label}",
                )
            )
            del active[process]
        elif not process.is_alive():
            process.join(timeout=2)
            try:
                result = result_queue.get_nowait()
            except queue_module.Empty:
                result = SourceCensusReceipt(
                    source=name,
                    kind="code",
                    status="error",
                    categories=("detector-error",),
                    stderr="detector child returned no receipt",
                )
            if isinstance(result, SourceCensusReceipt):
                receipts.append(result)
            else:
                receipts.append(
                    SourceCensusReceipt(
                        source=name,
                        kind="code",
                        status="error",
                        categories=("detector-error",),
                        stderr="detector child returned invalid receipt",
                    )
                )
            del active[process]


def _detect_preflight(manifests: list[mf.Manifest]) -> None:
    """Census every code source before aggregate graph/stamp mutation."""
    census = detection_census(manifests)
    failures = [
        (source.source, _source_census_failure_detail(source))
        for source in census.sources
        if source.status not in {"complete", "skipped-docs"}
    ]
    failures.extend(("<census>", f"RuntimeError: {error}") for error in census.integrity_errors)
    failures.sort()
    _report_unsupported_languages(census)
    if failures:
        categorized = [
            (_detect_failure_categories(detail), name, detail) for name, detail in failures
        ]
        category_counts = Counter(
            category for categories, _name, _detail in categorized for category in categories
        )
        summary = ", ".join(
            f"{category}: {category_counts[category]}" for category in sorted(category_counts)
        )
        lines = [
            # 240 was right when the payload was a raw unclassified dump nobody
            # could act on anyway. Now the payload leads with `unresolved`, a
            # bounded list of exactly the paths a reader must fix, so truncating
            # it re-hides the answer this message exists to give.
            f"  {name}: {'+'.join(categories)}: {detail[:900]}"
            for categories, name, detail in categorized
        ]
        raise SystemExit(
            f"Graphify detect preflight failed for {len(failures)} source(s); "
            f"categories={{{summary}}}; no aggregate artifact or stamp was mutated:\n"
            + "\n".join(lines)
        )


def _report_unsupported_languages(census: DetectionCensusReceipt) -> None:
    """Print the corpus loss the build is proceeding over, every run.

    This is the half of the class policy that keeps it honest. Absorbing a
    language Graphify cannot parse is what lets `kb-build` finish at all; saying
    nothing about it is how a green build comes to bury real loss (#231). The
    tally is unconditional and goes to stderr, so it survives a piped stdout.
    """
    tally: Counter[str] = Counter()
    sources = 0
    for source in census.sources:
        if not source.unsupported_language_count:
            continue
        sources += 1
        tally.update(dict(source.unsupported_language_tally))
    if not tally:
        return
    ranked = ", ".join(f"{suffix}={count}" for suffix, count in tally.most_common(12))
    print(
        f"[kb-build] unsupported-language corpus loss: {sum(tally.values())} file(s) "
        f"across {sources} source(s), absorbed so detection can proceed. "
        f"Graphify cannot parse these: {ranked}",
        file=sys.stderr,
    )


def _detect_failure_categories(detail: str) -> tuple[str, ...]:
    normalized = detail.casefold()
    patterns = (
        ("timeout", ("timeout", "deadline")),
        ("missing-clone", ("missing verified clone",)),
        ("ignored-paths", ("ignored-paths", "ignored=")),
        ("unclassified-files", ("unclassified-files", "unclassified=")),
        ("stderr", ("stderr",)),
    )
    categories = tuple(
        category for category, tokens in patterns if any(token in normalized for token in tokens)
    )
    if categories:
        return categories
    if normalized.startswith(("oserror:", "runtimeerror:", "valueerror:")):
        return ("detector-error",)
    return ("incomplete",)


#: THIS repo's own code, indexed into the aggregate graph beside the pinned
#: sources. Two trees rather than one, and the second is not an afterthought:
#: `python/` holds the library dotfiles consumes as a pinned git dependency, while
#: the root `tests/` holds the 41 files Ray widened this to include (2026-07-31).
#:
#: ⚠️ THAT WIDENING DOES NOT YET DELIVER WHAT IT WAS FOR — knowledge-base#101.
#: Its purpose was "which tests cover this symbol?", and that is unavailable FOR
#: OUR CODE. It is a config gap of ours, NOT a tool gap — a first pass here said
#: otherwise and an adversarial verifier refuted it. `affected` links tests fine:
#: `affected "_state"` returns 9 test functions under `tests/`, and a
#: `conftest.py` fixture reaches 17 test functions across two modules.
#:
#: The cause is that these are TWO extraction runs and `merge-graphs`
#: re-namespaces ids per merge, so the two halves land in disjoint namespaces
#: (`knowledge-base::python::…` vs `tests::…`) and no edge can span them. A/B on
#: byte-identical syntax: `sync.restamp_artifacts(...)` at `graph.py:252` gets an
#: edge; the same call at `test_currency_staleness.py:378` does not. Edge census:
#: 3,368 tests-touching, **0** crossing, against a control of 2,194 within
#: `python/`. `cognee` — one pinned source, ONE extraction run — has 10,099
#: test<->src edges in the same graph file. One variable differs.
#:
#: RESOLVED 2026-08-02 by the constants below. Kept as history because it is the
#: only place the pre-fix measurement survives, and because the refuted reading
#: ("a graphify limitation") is the one a future reader will reach for again.
#:
#: The `_SELF_TREES = ("python", "tests")` tuple this paragraph used to annotate
#: is GONE, not merely unused. Once one root covers both trees it had no reader —
#: a constant nothing consults is a claim about the code that the code does not
#: make, and leaving it would have let a later edit "restore" the loop by
#: consulting it again. The two trees are still exactly what gets indexed; the
#: root below is simply what contains them.

#: ONE extraction root covering both trees, which is THE FIX for the above.
#: `merge-graphs` re-namespaces ids on every merge, so two runs can only ever
#: produce two namespaces; the crossing edge has to exist *within a single
#: extraction* or it cannot exist at all. graphify's `extract` takes exactly one
#: path, so the one root that contains both of ours is the repo root.
#:
#: Indirect arm: `cognee` is one pinned source extracted in ONE run, and it has
#: 10,099 test<->src edges in this same graph file. That is evidence the shape
#: works, NOT evidence this change works — the direct arm is the depth test in
#: `tests/test_affected_covers_tests.py`, which must move from red to green
#: across the rebuild that carries this.
#:
#: CONFIRMED GENERALLY 2026-08-03: the rebuilt aggregate has **0 cross-namespace
#: edges of 815,481** across 40 namespaces (control-armed — injecting one crossing
#: moves the count to 1). So "no edge can span two namespaces" is not a quirk of
#: our two trees; it is what `merge-graphs` does to every input, and one extraction
#: root is the only way any cross-tree edge can exist.
_SELF_ROOT = "."

#: Where the single self sub-graph is written, and the reason this constant
#: exists at all. `graphify extract <path>` defaults its output to
#: `<path>/graphify-out/`, so extracting the repo root would write the AGGREGATE
#: `graphify-out/graph.json` — overwriting a 133k-node merged corpus with a
#: root-only extraction. `--out` redirects it. Gitignored, derived, disposable.
_SELF_OUT = ".self-graph"

#: Where `scope = study` sources land — repos we are analysing rather than
#: learning from. They are still fully ingested — no exclusions — just not ranked
#: beside the corpus.
#:
#: ⚠️ THE ORIGINAL RATIONALE WAS PARTLY A BUG, corrected 2026-08-03 (#120). This
#: said the partition existed because merging study sources took graph.json 7.6 MiB
#: past the 512 MiB cap — "71.0 MB of sub-graphs became >=155 MiB of aggregate
#: growth, since `merge-graphs` re-namespaces ids and expands edges on every merge".
#: The re-namespacing was real; the >=2x expansion was not inherent to it. It came
#: from `build()` merging PAIRWISE and re-prefixing its own accumulator once per
#: source. After the N-ary fix, duplicate-prefix waste measures 0.00% and id depth
#: is 1-2 rather than 1-22.
#:
#: The partition SURVIVES the correction on its own merits — nothing analysing a
#: study repo needs its nodes ranked beside the corpus, and Ray's instruction was
#: "ingest all three, no exclusions", which routing satisfies and dropping would
#: not. But do not carry the byte figure forward as an argument: it was inflated,
#: and a reader reaching for it to justify the next partition would be reasoning
#: from a defect. See `_merge_sources_into`.
STUDY_GRAPH_NAME = "study-graph.json"


def _self_subgraph(repo_root: Path) -> Path:
    """The single sub-graph the self extraction writes. One place, one spelling."""
    return repo_root / _SELF_OUT / "graphify-out" / "graph.json"


def _self_extract_argv(repo_root: Path) -> list[str]:
    """The ONE argv both self-extraction call sites use.

    Stated once because the two call sites drifting apart is precisely how the
    `update`-vs-`extract` defect arrived: two spellings of "extract our code",
    one of which produced different `source_file` values. A shared builder makes
    that class of drift unrepresentable rather than merely discouraged.
    """
    return [
        graphify_exe(repo_root),
        "extract",
        _SELF_ROOT,
        "--code-only",
        "--force",
        "--out",
        _SELF_OUT,
    ]


def _extract_self(repo_root: Path) -> list[Path]:
    """AST-extract this repo's OWN code; return each sub-graph for merging.

    Why this exists at all. `graphify affected "<symbol>"` is the blast-radius
    question, and it was unanswerable about our own code for a reason that had
    nothing to do with graphify: `python/src/kb_setup/` was simply never
    extracted — 0 of 37 tracked files, control-armed on `source_file` against
    `graphify/extractors/` -> 429 and `cognee/api/` -> 793. Every such query
    returned "No unique node match", which is the SAME string graphify returns for
    a symbol that does not exist. A missing INDEX and a missing SYMBOL were
    indistinguishable, so the failure announced nothing.

    Emptiness is NOT tolerated here, unlike `_extract_code`. That function
    swallows a non-zero status because a pinned upstream source may legitimately
    be prose-only, and its content arrives later via the host-agent wave. These
    two trees are ours and are always Python, so an empty sub-graph means the
    extraction broke rather than that there was nothing to find — `_run`'s
    check=True says so loudly instead of shipping a graph that silently cannot
    answer the question this function exists to answer.

    Paths are relative to `repo_root` (`_run` passes cwd), matching how
    `_extract_code` addresses `sources/<name>`.
    """
    _run(_self_extract_argv(repo_root), repo_root)
    return [_self_subgraph(repo_root)]


#: Filename of the DERIVED record `build()` writes describing what it actually
#: composed — never hand-authored, never committed (`graphify-out/` is
#: gitignored beyond `memory/`). `refresh_self` reads it back so a
#: recomposition uses the SAME corpus leaves and self location the last full
#: build did, rather than re-deriving them from `sources/*.manifest` (which may
#: have grown or shrunk since — `refresh_self` deliberately never reads a
#: manifest at all; that is the point, not an oversight).
_COMPOSE_MANIFEST_NAME = ".compose-manifest.json"

#: Filename of the ledger every successful `kb-merge` appends to between
#: builds (`append_merged_chunk`). `build()` resets it to `[]` at the moment it
#: writes the compose manifest — a fresh build subsumes every merge recorded
#: since the previous one.
_MERGED_CHUNKS_NAME = ".merged-chunks.json"


def _compose_manifest_path(repo_root: Path) -> Path:
    """Where `build()` records what it composed."""
    return repo_root / "graphify-out" / _COMPOSE_MANIFEST_NAME


def _merged_chunks_path(repo_root: Path) -> Path:
    """Where every between-build `kb-merge` is recorded for later replay."""
    return repo_root / "graphify-out" / _MERGED_CHUNKS_NAME


@dataclass(frozen=True)
class ComposeManifest:
    """What ONE `build()` actually composed, read back by `refresh_self`.

    Every path is repo-root-relative (:func:`_resolve` turns it back into a
    real `Path`), except a `chunks` entry for a chunk merged from outside the
    repo tree, which is its own absolute string — see
    :func:`_relativize_or_str`, which is what produces one. `self_graph` is
    recorded for provenance — it IS what "this build actually composed" means,
    literally — even though `refresh_self` never reads it back to find the
    self sub-graph: that location is a fixed constant (:func:`_self_subgraph`),
    not something a recomposition needs to recover from a record.

    `chunk_roots` is the root OVERRIDE map for `chunks` entries whose replay
    root cannot be safely re-derived from the naming convention
    `_replay_targets` otherwise falls back to — see `_write_compose_manifest`.
    """

    corpus: tuple[str, ...]
    self_graph: str
    chunks: tuple[str, ...]
    chunk_roots: dict[str, str]


def _write_compose_manifest(
    repo_root: Path, manifest: ComposeManifest, *, tag: str = "kb-build"
) -> None:
    """Record what `build()` (or a successful `refresh_self`) just composed.

    Takes the whole `ComposeManifest` rather than its four fields as separate
    keywords — `build()` constructs one fresh each time, `refresh_self` builds
    one via `dataclasses.replace` on the manifest it just read back, and
    either way the shape written here is exactly the shape `ComposeManifest`
    already declares, so restating its fields as a parallel parameter list
    was pure duplication (and had grown past ruff's arg-count budget).

    `manifest.chunk_roots` maps a SUBSET of `manifest.chunks` to the root it
    must replay under. Only entries whose root is not safely re-derivable
    from the `<name>-docs.json` -> `sources/<name>` naming convention need
    one — every chunk `build()` itself discovers via the
    `sources/extractions/*.json` glob follows that convention by
    construction, so `build()` always passes `{}`. A chunk promoted here from
    the between-build merge ledger may not: it was merged with whatever root
    `kb-merge` actually used, recorded on the ledger entry itself
    (:class:`MergedChunkEntry`), which can differ from the convention's guess
    (#175 cold review, finding 4b). See :func:`_replay_targets` for how the
    two are reconciled.

    `tag` names the CALLER in every printed line — `build()`'s default is
    right for a full build, and `refresh_self` passes `"kb-watch"` so a
    `kb-watch` run's own bookkeeping does not print as if `kb-build` had run
    (#175 cold review, finding 9).

    Best-effort, like the build stamp it sits beside: a failure here must not
    fail a build that just produced a correct `graph.json`. The one thing that
    goes wrong if this write fails is that `kb-watch` later refuses and says
    so (:func:`_load_compose_manifest_or_refuse`) — the safe direction to fail
    in, not a build dying over its own bookkeeping.
    """
    try:
        path = _compose_manifest_path(repo_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "corpus": list(manifest.corpus),
            "self": manifest.self_graph,
            "chunks": list(manifest.chunks),
            "chunk_roots": manifest.chunk_roots,
        }
        atomic.write_text(path, json.dumps(payload, indent=2) + "\n")
    except OSError as e:
        print(
            f"[{tag}] WARNING: could not record the compose manifest: {e}\n"
            f"[{tag}] `mise run kb-watch` will refuse until the next successful "
            f"`mise run kb-build`."
        )


def _valid_compose_fields(
    data: dict[str, object],
) -> tuple[list[str], str, list[str], dict[str, str]] | None:
    """Extract + validate every compose-manifest field, or None if any is malformed.

    Split out of `_read_compose_manifest` purely to keep THAT function's own
    return-statement count under ruff's complexity budget — adding the
    `chunk_roots` check (#175 cold review, finding 4) pushed it over. The
    validation itself is unchanged: every field is checked rather than
    trusted, this is untrusted JSON any editor could have touched, the same
    discipline `kb_setup.gates._parse` applies to its own on-disk record. An
    over-promising type here is how a caller stops checking it. `chunk_roots`
    is validated as strictly as every other field: a manifest written before
    #175's cold-review fixes has no such key at all, and that reads as
    "unreadable", not "no overrides" — the same unknown-is-not-permission
    rule the rest of this module follows, and it costs nothing since the file
    is derived and `mise run kb-build` regenerates it.
    """
    corpus, self_graph, chunks, chunk_roots = (
        data.get("corpus"),
        data.get("self"),
        data.get("chunks"),
        data.get("chunk_roots"),
    )
    if not isinstance(corpus, list) or not all(isinstance(c, str) and c for c in corpus):
        return None
    if not isinstance(self_graph, str) or not self_graph:
        return None
    if not isinstance(chunks, list) or not all(isinstance(c, str) and c for c in chunks):
        return None
    if not isinstance(chunk_roots, dict) or not all(
        isinstance(k, str) and k and isinstance(v, str) and v for k, v in chunk_roots.items()
    ):
        return None
    # Rebuilt explicitly rather than returned as narrowed: `isinstance(x, list)`
    # proves "x is A list", never "a list of str" — `ty` cannot follow the
    # `all(isinstance(...))` checks above into an element-type narrowing, so
    # the checked-but-untyped `corpus`/`chunks`/`chunk_roots` would not satisfy
    # this function's own declared return type. Same idiom as
    # `sync.stamped_input_fingerprints`'s `{str(k): str(v) ...}`.
    return (
        [str(c) for c in corpus],
        str(self_graph),
        [str(c) for c in chunks],
        {str(k): str(v) for k, v in chunk_roots.items()},
    )


def _read_compose_manifest(repo_root: Path) -> ComposeManifest | None:
    """The compose manifest, or `None` if it is absent, unreadable, or not one.

    See :func:`_valid_compose_fields` for the field-level validation rules.
    """
    try:
        data = json.loads(_compose_manifest_path(repo_root).read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    fields = _valid_compose_fields(data)
    if fields is None:
        return None
    corpus, self_graph, chunks, chunk_roots = fields
    return ComposeManifest(
        corpus=tuple(corpus),
        self_graph=self_graph,
        chunks=tuple(chunks),
        chunk_roots=dict(chunk_roots),
    )


@dataclass(frozen=True)
class MergedChunkEntry:
    """One between-build `kb-merge`, as recorded in the recomposition ledger.

    `root` is the source root `kb-merge` actually used for path
    relativization (`graphify_ops.merge_chunk`'s `src_root` — a caller's
    `--root`, or its own default of the chunk's parent directory). Recorded so
    a later `kb-watch` replays this chunk under the SAME root it was really
    merged with, rather than re-deriving one from the `<name>-docs.json` ->
    `sources/<name>` naming convention that a chunk merged with a custom (or
    even the ordinary default) root need not follow (#175 cold review,
    finding 4b).
    """

    chunk: str
    sha256: str
    root: str


def _write_merged_chunks(repo_root: Path, entries: list[MergedChunkEntry]) -> None:
    path = _merged_chunks_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [{"chunk": e.chunk, "sha256": e.sha256, "root": e.root} for e in entries]
    atomic.write_text(path, json.dumps(payload, indent=2) + "\n")


def _reset_merged_chunks(repo_root: Path, *, tag: str = "kb-build") -> None:
    """Empty the ledger. Best-effort, for the same reason the compose manifest is.

    `tag` names the caller — see `_clear_stamp`'s docstring for why (#175 cold
    review, finding 9).
    """
    try:
        _write_merged_chunks(repo_root, [])
    except OSError as e:
        print(f"[{tag}] WARNING: could not reset the merge ledger: {e}")


def merged_chunk_paths(repo_root: Path) -> list[Path] | None:
    """Chunks merged since the last build, resolved to paths — `[]` when unknown.

    A read-only view of the recomposition ledger for callers that only need
    "which chunks are in the graph but not in `sources/extractions/`". That set
    is not decorative: `kb-merge` accepts a chunk from any path, and an
    out-of-tree chunk's nodes sit in the graph exactly like a committed one's —
    so `graphify_ops._committed_chunks` has to include them or the collision gate
    has a blind side (cold lane, #189 round 1).

    **`None` for a CORRUPT ledger, `[]` for an absent one, and the distinction is
    the whole point.** Collapsing them returned the same empty list either way, so
    a corrupt derived file silently narrowed a REFUSAL gate back to the blind spot
    the ledger was added to close — unknown read as permission, which is the shape
    `_read_merged_chunks`'s own docstring refuses one function above. This caller
    is only widening a check rather than recomposing from it, so it does not have
    to abort; it does have to SAY SO, and it cannot say so if it cannot tell.
    (Cold lane, round 2, P1.)
    """
    entries = _read_merged_chunks(repo_root)
    if entries is None:
        return None
    return [_resolve(repo_root, e.chunk) for e in entries]


def _read_merged_chunks(repo_root: Path) -> list[MergedChunkEntry] | None:
    """The ledger's entries — `[]` if absent, `None` if present but unreadable.

    The distinction is the whole point of the ledger existing. An ABSENT file
    means no `kb-merge` has landed since the last build — the ordinary case,
    indistinguishable from "nothing to replay". A PRESENT-but-corrupt one means
    a recomposition cannot tell whether it would be dropping an entry it can no
    longer read, and must refuse rather than guess "empty" — the same
    unknown-is-not-permission rule the compose manifest follows. A ledger
    entry missing `root` (written before #175's cold-review fixes) is
    unreadable by the same rule: guessing a root would silently reintroduce
    the exact divergence recording it exists to prevent, and the file is
    derived — `mise run kb-build` regenerates it from nothing.
    """
    path = _merged_chunks_path(repo_root)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    entries: list[MergedChunkEntry] = []
    for row in data:
        if not isinstance(row, dict):
            return None
        chunk, sha, root = row.get("chunk"), row.get("sha256"), row.get("root")
        if (
            not isinstance(chunk, str)
            or not chunk
            or not isinstance(sha, str)
            or not sha
            or not isinstance(root, str)
            or not root
        ):
            return None
        entries.append(MergedChunkEntry(chunk=chunk, sha256=sha, root=root))
    return entries


def _sha256_file(path: Path) -> str:
    """Hex sha256 of `path`'s bytes, read in blocks rather than loaded whole."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def append_merged_chunk(repo_root: Path, chunk: str, root: str) -> None:
    """Record one successful between-build `kb-merge` in the recomposition ledger.

    Called by `graphify_ops.merge_chunk` on its fully-successful path only —
    after the merge subprocess AND the prose re-derivation both succeeded — so
    every ledger entry corresponds to content that is really on `graph.json`
    right now. `root` is `merge_chunk`'s own `src_root` — the root the merge
    ACTUALLY ran under — recorded so a later replay uses it verbatim instead
    of re-deriving one (#175 cold review, finding 4b).

    `chunk` is stored CANONICALIZED — resolved, then made repo-root-relative
    when it sits under `repo_root`, else its own absolute string
    (:func:`_relativize_or_str`, the SAME helper `refresh_self`'s
    ledger-promotion loop already uses) — never the raw string the caller
    passed. Before this, the raw string was stored VERBATIM and read two
    different ways by two different readers: this function digested it
    relative to the process's CURRENT WORKING DIRECTORY (`Path(chunk)`, opened
    as given), while `_verified_ledger_chunks` later resolved the recorded
    string relative to `repo_root` (:func:`_resolve`). The two agreed only
    because mise always runs tasks from the config root — a caller invoked
    from anywhere else recorded a ledger entry that could never verify again
    (#175 cold review round 2, the round-1 finding 8 secondary item).
    Resolving once, HERE, and storing the canonical form makes every later
    reader agree regardless of the cwd at append time or at verify time.

    Raises rather than swallowing a write failure: a caller that reported
    success while silently failing to extend the ledger would leave a future
    `kb-watch` unable to tell this merge ever happened — the exact silent
    discard the ledger exists to prevent, just arriving through its own
    recording step instead of through recomposition. `merge_chunk` turns a
    raise here into its own `rc=1`, the same shape `_derive_prose` already uses
    when a real change could not be fully accounted for.

    Also raises if the EXISTING ledger cannot be read: appending blindly to an
    unreadable file would either duplicate or silently drop whatever is
    already there, and neither is an improvement on refusing.
    """
    existing = _read_merged_chunks(repo_root)
    if existing is None:
        raise ValueError(
            f"{_merged_chunks_path(repo_root)} exists but is not a readable merge "
            f"ledger — refusing to append blindly"
        )
    resolved = Path(chunk).resolve()
    digest = _sha256_file(resolved)
    stored = _relativize_or_str(resolved, repo_root)
    _write_merged_chunks(
        repo_root, [*existing, MergedChunkEntry(chunk=stored, sha256=digest, root=root)]
    )


def _resolve(repo_root: Path, rel_or_abs: str) -> Path:
    """A compose-manifest/ledger path string -> a real `Path`.

    Every string either record carries is either ABSOLUTE or relative to
    `repo_root` — never to the process cwd, matching how the rest of this
    module addresses `sources/` (always `repo_root / ...`, never a bare
    relative literal). `mise run kb-watch` therefore recomposes the same way
    regardless of where it happens to be invoked from.
    """
    p = Path(rel_or_abs)
    return p if p.is_absolute() else repo_root / p


def _relativize_or_str(path: Path, repo_root: Path) -> str:
    """`path` relative to `repo_root` when possible, else its own absolute string.

    `Path.relative_to` raises `ValueError` for a path outside `repo_root` — and
    an out-of-tree ledger chunk is a real, supported case: `_resolve` already
    special-cases an absolute string, and `cli.py` passes a `kb-merge` caller's
    argv through verbatim, so `mise run kb-merge -- /elsewhere/chunk.json`
    genuinely reaches the ledger. Letting that raise here would crash
    `refresh_self` AFTER `graph.json` has already been swapped in — the
    recomposition would land with no stamp written and the ledger not reset
    (#175 cold review, finding 8). Falling back to the absolute string keeps
    the round-trip lossless either way: `_resolve` reads an absolute string
    back unchanged, exactly as it does a repo-relative one.

    Two call sites must agree on this canonical form, and both go through this
    one helper rather than reimplementing it: `refresh_self`'s ledger-promotion
    loop (naming a chunk already promoted into `manifest.chunks`) and
    `append_merged_chunk` (naming what a `kb-merge` just recorded) — see the
    latter's docstring for the append/verify cwd mismatch that unifying on
    this helper closes (#175 cold review round 2).
    """
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _load_compose_manifest_or_refuse(repo_root: Path) -> ComposeManifest:
    """The last build's recorded composition, or a refusal naming the fix.

    A missing file, a malformed one, and one from before this mechanism
    existed are all treated identically: unknown is not permission, and there
    is nothing safe to recompose FROM until a `kb-build` has written one.
    """
    manifest = _read_compose_manifest(repo_root)
    if manifest is None:
        raise SystemExit(
            f"no usable {_compose_manifest_path(repo_root)} — `kb-watch` recomposes "
            f"from what the last full build actually composed, and there is no "
            f"readable record of one. Run `mise run kb-build` first."
        )
    return manifest


def _verified_ledger_chunks(repo_root: Path) -> list[tuple[Path, str]]:
    """Ledger entries COLLAPSED to one per resolved path, then VERIFIED `(path, root)` pairs.

    Collapsed FIRST, by resolved path, keeping the LAST row for each — append
    order is merge order, so the last row for a path is what `graph.json`
    actually reflects right now. The ordinary re-ingestion flow supersedes a
    row this way with no misuse at all: `kb-assemble` overwrites a chunk under
    `sources/extractions/` in place, then `kb-merge` merges it again, and the
    ledger simply gets a second row for the same path. Verifying EVERY row
    instead of only the surviving one produced two defects (#175 cold review
    round 2, NEW-2 and NEW-3):

    * an EARLIER row's sha256 — computed against content the file no longer
      holds — refused `kb-watch` forever, for a flow that did nothing wrong
      (NEW-3); and
    * a chunk merged N times with UNCHANGED content (every row's sha256 still
      matches) was verified, promoted, and replayed N times — and because the
      promoted duplicates land in the persisted `manifest.chunks` tuple, the
      waste PERSISTED on every subsequent `kb-watch` until the next full
      `kb-build` (NEW-2).

    `dict.pop` then re-insert (not a plain `d[k] = v` overwrite) so the
    surviving row also takes the POSITION of its LATEST occurrence — a plain
    reassignment updates the value but leaves an existing key at its ORIGINAL
    position, which would replay a since-superseded path too early relative to
    whatever else was appended between its two occurrences.

    Refuses the moment the SURVIVING entry for a path cannot be trusted —
    missing file, unreadable file, or a sha256 that no longer matches what was
    recorded at merge time — because recomposing over that would silently drop
    that merge's content, which is the one property this mechanism exists to
    keep from the base-guard machinery it replaces. `root` is the entry's OWN
    recorded root (:attr:`MergedChunkEntry.root`), returned alongside the path
    so a caller never has to re-derive one — see :func:`_replay_targets`.
    """
    ledger = _read_merged_chunks(repo_root)
    if ledger is None:
        raise SystemExit(
            f"{_merged_chunks_path(repo_root)} exists but could not be read as a "
            f"merge ledger — recomposing now could silently drop a between-build "
            f"`kb-merge`. Run `mise run kb-build` to reset it."
        )
    by_path: dict[Path, MergedChunkEntry] = {}
    for entry in ledger:
        key = _resolve(repo_root, entry.chunk)
        by_path.pop(key, None)
        by_path[key] = entry

    verified: list[tuple[Path, str]] = []
    for path, entry in by_path.items():
        if not path.is_file():
            raise SystemExit(
                f"the recomposition ledger names {entry.chunk!r} but that file is "
                f"missing — recomposing now would silently drop that merge's "
                f"content. Restore the file, or run `mise run kb-build` to reset "
                f"the ledger."
            )
        try:
            actual = _sha256_file(path)
        except OSError as e:
            raise SystemExit(
                f"the recomposition ledger names {entry.chunk!r} but it could not "
                f"be read ({e}) — recomposing now would silently drop that merge's "
                f"content."
            ) from e
        if actual != entry.sha256:
            raise SystemExit(
                f"{entry.chunk!r} has changed since it was merged (sha256 was "
                f"{entry.sha256}, is now {actual}) — recomposing now would replay "
                f"different content than what was actually merged. Run "
                f"`mise run kb-build` to reset the ledger."
            )
        verified.append((path, entry.root))
    return verified


#: The ledger fields threaded from one replayed chunk into the next as its prior.
#: A SUBSET of `graph_counts._FIELDS` on purpose: these are the two `_merge_docs`
#: asserts an identity over. `edges` has no such identity (a merge adds edges
#: between pre-existing nodes, so no arithmetic predicts the total) and `members`
#: is not produced by every writer — `_derive_prose` omits it, which #198 flags.
#: Threading a field nothing checks would put a number in argv that no arm covers.
_THREADED_COUNTS = ("nodes", "hyperedges")


def _handoff_counts(handoff: Path) -> dict[str, int | None]:
    """The counts `_merge_docs.py` just wrote, consuming the handoff file.

    Returns None PER FIELD — *unknown* — for a missing, unreadable or malformed
    handoff, never a stale number: the file is removed on every read, so a value
    from an earlier chunk can never be mistaken for this one's. That distinction is
    the whole point of threading counts at all; a prior count that is quietly one
    chunk out of date produces a confident, wrong "replaced" figure, which is worse
    than admitting the arithmetic was not checked.

    Returns the whole mapping rather than one field (#198 item 1) — and that is
    forced, not stylistic. The handoff is UNLINKED on read, so a second
    `_handoff_hyperedges` reading the same file could never see it: whichever ran
    first would delete it and the other would report *unknown* forever, which is
    the failure mode that looks exactly like a passing check.
    """
    try:
        data = json.loads(handoff.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return dict.fromkeys(_THREADED_COUNTS)
    finally:
        handoff.unlink(missing_ok=True)
    if not isinstance(data, dict):
        return dict.fromkeys(_THREADED_COUNTS)
    return {
        field: v if isinstance(v := data.get(field), int) else None for field in _THREADED_COUNTS
    }


def _replay_doc_chunks(
    repo_root: Path, gpy: str, sources: Path, out: Path, chunk_paths: list[Path]
) -> None:
    """Replay every committed chunk in CAPTURE-DATE order, checking the arithmetic.

    Order first, because it is the load-bearing part: `build_merge` gives a
    `source_file` to the LAST chunk that names it, so replay order IS the
    supersession rule — see `chunks.replay_order` for the measured defect (a
    rebuild and an incremental merge producing different graphs from the same
    committed corpus, chosen by the alphabet).

    Each merge's post-count is then threaded into the NEXT merge as its prior, so
    every step asserts its own arithmetic (#191). This is the loop where the
    2026-08-05 rebuild silently swapped a fresh page's 69 nodes for an older
    chunk's 13, and the only reason anyone noticed was a human subtracting
    `+290 printed` from `total rose 221` across two printed lines.

    The FIRST chunk's prior is deliberately UNKNOWN, and the ledger is not
    consulted for it. By the time this runs `build()` has already re-seeded
    `graph.json` from the freshly composed code layer, so the ledger describes a
    DIFFERENT artifact — the previous build's — and any number it returned would
    be a baseline for a file that no longer exists. Its fingerprint gate would
    reject it anyway; not asking is the version of that which cannot be misread
    later as "the ledger had nothing to say". So chunk 1 reports *not checked*,
    and every chunk after it is checked against the merge immediately before it.

    The ledger's own payoff is the INCREMENTAL path (`graphify_ops.merge_chunk`),
    where the graph on disk really is the one it describes — and that is the path
    the 2026-08-06 loss arrived on.

    HYPEREDGES ARE THREADED HERE TOO (#198 item 1), and this path is the one that
    needed it most: the #186 loss that started this whole ticket family — 11
    hyperedges to 8, no nodes moved — was observed on a REBUILD, i.e. in this loop,
    by a human diffing rebuild against incremental. Until now this loop threaded
    `nodes` alone, so it would have replayed straight past it printing "0 replaced"
    and been entirely correct about nodes while the thing it was written to catch
    went by.
    """
    _replay_pairs(repo_root, gpy, out, [(c, _derived_root(sources, c)) for c in chunk_paths])


def _derived_root(sources: Path, chunk: Path) -> str:
    """The `sources/<name>` root `build()` merges a globbed chunk under."""
    return str((sources / chunk.stem.removesuffix("-docs")).resolve())


def _replay_pairs(repo_root: Path, gpy: str, out: Path, pairs: list[tuple[Path, str]]) -> None:
    """Replay `(chunk, root)` pairs in CAPTURE-DATE order, checking the arithmetic.

    THE one replay loop. Both paths that exist call it — `build()`'s
    :func:`_replay_doc_chunks`, which derives each root from the chunk stem, and
    `refresh_self()`'s :func:`_recompose_into_temp`, which carries a recorded
    root per chunk. They were separate loops until 2026-08-08, and the whole
    cost of that is what this function's existence is for:

    `build()`'s loop applied `chunks.replay_order` and threaded `--prior-<field>`;
    the recomposition loop did neither. It replayed in `manifest.chunks` order —
    alphabetical — so `kb-build` and `kb-watch` produced DIFFERENT graphs from
    the same committed corpus, which is invariant 3's precise failure shape and
    is the very defect `chunks.replay_order` was written to remove. It was fixed
    on one path and left live on the other for as long as both existed. Every
    `[merge]` line `kb-watch` ever printed said *prior node count unknown —
    arithmetic NOT checked*, so #191's gate had never once fired there either.

    Two fixes on one path and not its sibling is not two bugs; it is one missing
    seam. Hence pairs rather than paths: the root is the only thing the two
    callers genuinely disagree about, so it is the only thing they still supply.
    """
    from kb_setup import chunks as _chunks

    counts_out = out.with_name(".merge-counts.tmp.json")
    prior: dict[str, int | None] = dict.fromkeys(_THREADED_COUNTS)
    for chunk, root in sorted(pairs, key=lambda pair: _chunks.replay_key(pair[0])):
        argv = [gpy, str(_MERGE_SCRIPT), str(chunk), root, str(out)]
        # Per field, not all-or-nothing: a handoff carrying `nodes` but not
        # `hyperedges` (or the reverse) must still check the half it can. The
        # loop emits `--prior-<field>` from one table so a field added to
        # `_THREADED_COUNTS` is threaded here without a second edit — the
        # divergence that let the incremental and rebuild paths disagree in the
        # first place.
        for field, value in prior.items():
            if value is not None:
                argv += [f"--prior-{field}", str(value)]
        argv += ["--counts-out", str(counts_out)]
        _run(argv, repo_root)
        prior = _handoff_counts(counts_out)


def _validate_replay_chunks(paths: list[Path]) -> None:
    """Refuse if any chunk about to be replayed fails schema/integrity validation.

    The same gate `build()` applies to the same chunks, for the same reason —
    a chunk that merged cleanly once is not guaranteed to still be well-formed
    if it, or a chunk sharing its cross-chunk id space, was hand-edited since.
    """
    from kb_setup import chunks as _chunks

    problems = {p: i for p, i in _chunks.validate_files(paths).items() if i}
    if problems:
        lines = [f"  {p.name}: {i}" for p, issues in problems.items() for i in issues[:5]]
        raise SystemExit(
            f"{len(problems)} extraction chunk(s) failed validation — refusing to "
            f"recompose:\n" + "\n".join(lines)
        )
    # Cross-chunk (#189). Checked HERE as well as in `kb-merge` because the two
    # doors admit different inputs: `kb-merge` sees one fresh chunk against the
    # corpus, while this sees the whole replay SET — which is the only place a
    # collision between two ALREADY-committed chunks can surface. It is also the
    # path a fresh clone takes, where nothing was ever merged interactively.
    collisions = _chunks.collision_issues(paths)
    if collisions:
        raise SystemExit(
            f"{len(collisions)} cross-chunk source_file collision(s) — refusing to "
            f"recompose:\n  " + "\n  ".join(collisions)
        )


def _require_present(paths: list[Path], *, what: str) -> None:
    """Refuse, NAMING every path, if any recorded input is no longer on disk."""
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise SystemExit(
            f"{len(missing)} recorded {what}(s) no longer on disk — cannot "
            f"recompose:\n  " + "\n  ".join(missing) + "\nRun `mise run kb-build`."
        )


def _replay_targets(
    repo_root: Path,
    sources: Path,
    manifest_chunk_names: list[str],
    chunk_roots: dict[str, str],
    ledger_chunks: list[tuple[Path, str]],
) -> list[tuple[Path, str]]:
    """`(chunk, root)` pairs for `_MERGE_SCRIPT`, manifest order then ledger order.

    A manifest chunk's root is `chunk_roots[name]` when the compose manifest
    recorded an override for it — every chunk ever promoted from the ledger
    carries one (:func:`append_merged_chunk`'s `root`, threaded through
    `refresh_self`'s promotion) — and otherwise falls back to the convention
    `build()` itself used to merge it the first time: `sources/<name>`, `name`
    derived from the chunk's stem. That fallback is safe ONLY for a chunk
    `build()` discovered via its own `sources/extractions/*.json` glob, which
    is exactly the set that has no override.

    A ledger chunk not yet promoted carries its OWN verified `(path, root)`
    pair straight from `_verified_ledger_chunks` — the root `kb-merge`
    actually used, never a guess. Before #175's cold-review fixes this derived
    a ledger chunk's root from `c.resolve().parent` on every call, which
    happened to match `merge_chunk`'s own DEFAULT but silently discarded a
    caller's custom `--root` — and, the sharper bug, was recomputed fresh on
    every recomposition rather than recorded once, so a chunk promoted into
    `manifest.chunks` replayed under a DIFFERENT derived root on the very next
    `kb-watch` (finding 4b). Recording the root at merge time and carrying it
    through the promotion is what makes it stable across every later replay.
    """
    manifest_targets = [
        (
            _resolve(repo_root, name),
            chunk_roots.get(name, str((sources / Path(name).stem.removesuffix("-docs")).resolve())),
        )
        for name in manifest_chunk_names
    ]
    return manifest_targets + list(ledger_chunks)


def _recompose_into_temp(
    repo_root: Path, real_out: Path, inputs: list[Path], replay: list[tuple[Path, str]]
) -> None:
    """Merge `inputs`, replay `replay`, into a scratch file — then swap it in atomically.

    The scratch file lives in the SAME directory as `real_out` (never the
    system temp dir), so the final `Path.replace` is guaranteed to be an
    atomic rename rather than risking a cross-filesystem copy — the same
    reason `atomic.write_text` and `prose.derive` both reserve their temp
    name beside the file they replace.

    Every step above the swap runs against the SCRATCH file, never `real_out`
    — so the real `graphify-out/graph.json` stays exactly what the last
    successful build (or recomposition) left it, valid and correctly stamped,
    for the entire — potentially multi-minute — duration of this call. The
    stamp is cleared only immediately before the swap (see the comment at that
    line); any failure before the swap leaves `real_out` untouched, and the
    `except` below removes the scratch file and re-raises — the same "clear
    first, only re-stamp on full success" rule `build()`'s own `_clear_stamp`
    follows, applied at the one moment it actually matters for this shape.

    `tmp_out` is chmod'd to :data:`_GRAPH_MODE` BEFORE the swap:
    `tempfile.mkstemp` always creates its file `0600`, and `Path.replace` is a
    rename — the surviving inode's permission bits are the TEMP file's, not
    the file it replaces. Left unfixed, one recomposition would silently
    tighten `graph.json` from world-readable to owner-only, and graphify's own
    `_atomic_replace` PRESERVES whatever mode is already there, so nothing
    downstream would ever repair it (#175 cold review, finding 5 — the exact
    hazard `prose.derive` already guards against for its own writes; see
    `prose._ARTIFACT_MODE`).
    """
    gpy = graphify_python(repo_root)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(real_out.parent), prefix=real_out.name + ".", suffix=".recompose.tmp"
    )
    os.close(fd)
    tmp_out = Path(tmp_name)
    try:
        print(f"[kb-watch] composing graph.json from {len(inputs)} recorded input(s)")
        _merge_sources_into(repo_root, tmp_out, inputs)
        print(f"[kb-watch] replaying {len(replay)} doc extraction(s)")
        # Through the SHARED loop, which is what puts these replays in capture
        # order and checks each merge's arithmetic. Both properties were absent
        # here until 2026-08-08 — see `_replay_pairs` for what that cost.
        _replay_pairs(repo_root, gpy, tmp_out, replay)
        # Only NOW — immediately before the swap — does the REAL artifact's
        # identity actually change. Clearing the stamp any earlier would mark a
        # still-good graph unstamped for no reason (everything above wrote only
        # to `tmp_out`); any later and a crash between clearing and replacing
        # could leave the swap landing under a stamp that no longer describes
        # what it is about to become.
        _clear_stamp(repo_root, tag="kb-watch")
        tmp_out.chmod(_GRAPH_MODE)
        tmp_out.replace(real_out)
    except BaseException:
        tmp_out.unlink(missing_ok=True)
        raise


def refresh_self(repo_root: Path) -> None:
    """Recompose `graph.json` from what the last build recorded — `kb-watch`.

    THIS REPLACES the base-snapshot/guard machinery that used to restart
    `graph.json` from a pre-self-merge snapshot, which #175's single-N-ary
    -merge restructure removed the separable step that machinery depended on
    (see git history for the two rounds of cold-review fixes — a
    competing-writer race, then a re-check-before-swap race — that machinery
    had needed to be safe). The property that machinery existed to guarantee
    survives here in a different shape: instead of a snapshot, `build()`
    records exactly what it composed (`.compose-manifest.json`) and every
    between-build `kb-merge` appends its chunk's path and sha256 to a ledger
    (`.merged-chunks.json`, via :func:`append_merged_chunk`); this function
    refuses — rather than silently dropping — the moment a ledger entry cannot
    be verified against what is actually on disk, and recomposes entirely in a
    scratch file (:func:`_recompose_into_temp`) so the real artifact is never
    at risk while that verification and the recompose itself are running.

    This does NOT fingerprint `sources/*.manifest` / `sources/extractions/*.json`
    the way `build()` does. That was tried and was a REGRESSION, not a
    simplification (#175 cold review, finding 1): this function recomposes
    ONLY from the recorded compose manifest and the verified ledger,
    deliberately never re-reading a manifest at all (see the paragraph above).
    Stamping a live glob over those files anyway would record, as "what this
    graph was built from", inputs it structurally did not consult — so a
    manifest or chunk added since the last `kb-build` would be fingerprinted
    WITHOUT being in the graph, and `kb-currency-check` would report the
    corpus in sync while it excludes exactly that content. What a
    recomposition CAN honestly claim is that the artifact's own fingerprints
    still describe what is on disk now, with the input map it inherits from
    the last real build carried forward VERBATIM — recorded by
    :func:`_restamp_self` from a snapshot :func:`_held_stamp` takes BEFORE
    `_recompose_into_temp` clears the stamp, since by the time this function's
    own tail runs there is no stamp left on disk to read back (#175 cold
    review round 2, NEW-1 — see `_held_stamp`'s docstring for the defect this
    fixes).
    """
    manifest = _load_compose_manifest_or_refuse(repo_root)
    sources = repo_root / "sources"
    manifest_chunks = [_resolve(repo_root, c) for c in manifest.chunks]
    ledger_verified = _verified_ledger_chunks(repo_root)
    ledger_chunks = [path for path, _root in ledger_verified]

    _validate_replay_chunks(manifest_chunks + ledger_chunks)

    corpus_leaves = [_resolve(repo_root, c) for c in manifest.corpus]
    _require_present(corpus_leaves, what="corpus leaf")
    _require_present(manifest_chunks + ledger_chunks, what="chunk")

    # Fold this run's ledger into the chunk bookkeeping BEFORE anything
    # replays — DE-DUPLICATED (#175 cold review, finding 4a): a chunk whose
    # resolved path is already in `manifest.chunks` (an earlier `kb-watch`
    # already promoted it, or it was already part of `build()`'s own glob
    # before ALSO being merged by hand — the documented flow commits a chunk
    # under `sources/extractions/` AND merges it, so both can name the same
    # file in the SAME run) is replayed exactly ONCE, via the manifest branch
    # below, never a second time via the ledger branch. `chunk_roots` is
    # refreshed for EVERY verified ledger entry regardless of the dedup
    # outcome, so an already-present chunk still replays with the root THIS
    # run actually used — the most recently correct one — not a stale or
    # re-derived guess.
    #
    # `ledger_verified` cannot itself name the same resolved path twice —
    # `_verified_ledger_chunks` already collapsed the ledger to one row per
    # path before returning (#175 cold review round 2, NEW-2) — so this
    # `existing_chunks` check only ever has the ledger-vs-MANIFEST case left
    # to catch; a within-this-run ledger-vs-ledger duplicate can no longer
    # reach this loop at all.
    existing_chunks = set(manifest.chunks)
    new_chunk_roots = dict(manifest.chunk_roots)
    promoted: list[str] = []
    new_ledger_entries: list[tuple[Path, str]] = []
    for path, root in ledger_verified:
        name = _relativize_or_str(path, repo_root)
        new_chunk_roots[name] = root
        if name in existing_chunks:
            continue
        promoted.append(name)
        new_ledger_entries.append((path, root))

    self_subgraphs = _extract_self(repo_root)
    replay = _replay_targets(
        repo_root, sources, list(manifest.chunks), new_chunk_roots, new_ledger_entries
    )
    real_out = repo_root / "graphify-out" / "graph.json"
    # MUST run before `_recompose_into_temp` — that call is what clears the
    # stamp (`_clear_stamp`, immediately before the swap), and this is the
    # only remaining chance to read what it is about to delete. See
    # `_held_stamp`'s own docstring (#175 cold review round 2, NEW-1).
    held_stamp = _held_stamp(repo_root)
    refresh_build_receipt = _current_build_receipt_matches(repo_root, held_stamp)
    _recompose_into_temp(repo_root, real_out, [*corpus_leaves, *self_subgraphs], replay)

    label_rc = graphify_ops.label(repo_root)
    if label_rc != 0:
        raise SystemExit(f"[kb-watch] label pass failed (rc={label_rc}) — aborting")
    graph_checks.assert_composition(real_out, tag="kb-watch", repo_root=repo_root)

    _write_compose_manifest(
        repo_root,
        replace(
            manifest,
            self_graph=str(_self_subgraph(repo_root).relative_to(repo_root)),
            chunks=(*manifest.chunks, *promoted),
            chunk_roots=new_chunk_roots,
        ),
        tag="kb-watch",
    )
    _reset_merged_chunks(repo_root, tag="kb-watch")
    _restamp_self(repo_root, held_stamp)
    if refresh_build_receipt and held_stamp is not None:
        _write_build_receipt(
            repo_root,
            runtime_version=held_stamp.version,
            inputs=held_stamp.inputs,
        )
    print("[kb-watch] done — graphify-out/graph.json recomposed from recorded inputs")


def _merge_sources_into(repo_root: Path, out: Path, inputs: list[Path]) -> None:
    """Compose `inputs` into `out` with ONE `merge-graphs` call — never pairwise.

    THE FIX FOR #120, and the reason it is a shared helper rather than two edits.

    graphify's `merge-graphs` takes N graph paths (`cli.py` parses every
    non-`--out` argument into `graph_paths`) and prefixes each input's node ids
    with a distinct `<repo_tag>::` so same-stem nodes from different repos cannot
    collide (#1729). `prefix_graph_for_global` (`build.py:1449`) applies that
    prefix UNCONDITIONALLY — `relabel = {n: f"{repo_tag}::{n}" ...}` with no
    already-prefixed guard.

    So feeding the accumulator back in as an input, once per source, re-prefixes
    everything already merged. Measured on the 2026-08-03 aggregate: of 218,243
    node ids only 9,645 (4.4%) carried a single `::`; 90,795 carried ten and
    11,932 carried twenty-two. Across every id-bearing field (`id`, `source`,
    `target`, `_src`, `_tgt`) that is 296,904,672 bytes where 112,626,720 would
    do — **184 MB, 33% of the whole file**, which is what pushed graph.json past
    graphify's 512 MiB read cap and made the entire aggregate unqueryable.

    Calling the N-ary form once gives every input exactly one prefix, which is
    the invariant `tests/test_merge_prefixes_once.py` asserts. It is also
    `use-tool-builtins.md` in the literal: the loop was ours, the N-ary merge is
    graphify's, and the loop was the defect.

    Two related workarounds in this file were written believing the blowup was
    inherent to merging rather than a bug in how we called it — the
    `STUDY_GRAPH_NAME` partition ("71.0 MB of sub-graphs became >=155 MiB of
    aggregate growth") and the #101 disjoint-namespace note. Neither is retired
    here: study partitioning still has an independent ranking rationale, and #101
    was fixed by extracting one root. But a future reader weighing either should
    know the cost figure behind them was inflated by this.

    A single input is COPIED, not merged: `merge-graphs` requires two paths and
    exits 1 on one. That leaves a lone source unprefixed while N>=2 sources each
    carry one — an asymmetry inherited from the code this replaces, harmless
    because it is reachable only with exactly one code-bearing corpus source.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    if len(inputs) == 1:
        shutil.copy(inputs[0], out)
        return
    _run(
        [graphify_exe(repo_root), "merge-graphs", *[str(p) for p in inputs], "--out", str(out)],
        repo_root,
    )


def _build_study_graph(repo_root: Path, sources: Path, out_dir: Path, study: list[str]) -> None:
    """Merge every `scope = study` source into its own graph, never the aggregate.

    Extracted from `build()` rather than inlined — ruff flagged `build` at
    complexity 12, and the honest fix for "this function grew a fourth job" is a
    fourth function, not a suppression.

    These repos are fully ingested; only their DESTINATION differs. That
    distinction is the whole design: the standing instruction was "ingest all
    three, no exclusions", and merging them into the corpus took graph.json 7.6
    MiB past graphify's 512 MiB cap. Nothing that analyses them needs their nodes
    ranked beside the corpus.
    """
    if not study:
        return
    study_out = out_dir / STUDY_GRAPH_NAME
    print(f"[kb-build] composing {STUDY_GRAPH_NAME} from {len(study)} study source(s)")
    _merge_sources_into(
        repo_root, study_out, [sources / n / "graphify-out" / "graph.json" for n in study]
    )


def _cluster_study_graph(repo_root: Path, study_out: Path) -> None:
    """Deterministically re-cluster `study_out` THROUGH the graphify binary.

    A no-op when there is nothing to cluster (no study sources this build, or a
    study source that produced no graph) — matching `_build_study_graph`'s own
    early return rather than raising over an absent optional artifact.

    VERIFIED MECHANISM (installed graphify 0.9.33 `cli.py`, the
    `cmd in ("cluster-only", "label")` branch — never run graphify by hand here;
    read the installed source instead). `--graph <path>` controls only where the
    run LOADS from (`graph_json = graph_override if ... else watch_path /
    _GRAPHIFY_OUT / "graph.json"`, cli.py:1640). The WRITE target is computed
    separately and does NOT follow it: `out = graph_json.parent` only when that
    parent directory is literally named `graphify-out` (cli.py:1711-1716), and
    either way the final write is `to_json(G, communities, str(out /
    "graph.json"), ...)` (cli.py:1862) — the LITERAL string `"graph.json"`,
    never `graph_json.name`. So `--graph graphify-out/study-graph.json` would
    LOAD the study graph but WRITE its clustered result to
    `graphify-out/graph.json` — the aggregate — because that path's parent
    directory happens to also be named `graphify-out`. No flag changes this.

    The only safe invocation is therefore to give the run its OWN isolated
    `<tmp>/graphify-out/graph.json` to read and write: with no `--graph`
    override, `graph_json` resolves to exactly that path by default, so both
    the load and the write stay inside the throwaway directory and the real
    aggregate is never touched. `--no-label` keeps this deterministic —
    placeholder `"Community {cid}"` names, no hub-labeler, no LLM call
    (cli.py:1797-1799) — and `--no-viz` skips the `graph.html` render, which
    this graph is never served from.
    """
    if not study_out.is_file():
        return
    with tempfile.TemporaryDirectory(prefix="kb-study-cluster-") as tmp:
        work = Path(tmp)
        staged = work / "graphify-out" / "graph.json"
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(study_out, staged)
        _run([graphify_exe(repo_root), "cluster-only", ".", "--no-label", "--no-viz"], work)
        shutil.copy(staged, study_out)


def _drop_skipped_builds(manifests: list[mf.Manifest]) -> list[mf.Manifest]:
    """Partition off `build = skip` sources, announcing each with its reason.

    Called BEFORE the clone, the detect preflight and the AST pass — those are the
    three things that cost, and the two that fail. Never silently: the hazard of
    this field is that it can turn a red build green by removing the source that
    was reporting a real problem, so every exclusion states why on its own line.

    A skipped manifest is NOT dropped from the input fingerprints `build` takes
    first: the pin stays committed and fingerprinted, so the source remains
    reproducible-by-reference. It is excluded from this build, not from the record.
    """
    kept = [m for m in manifests if m.build != "skip"]
    if not kept:
        raise SystemExit("every sources/*.manifest is build = skip — nothing to build")
    for m in manifests:
        if m.build == "skip":
            print(f"  [excluded] {m.name}: build = skip — {m.skip_reason}")
    return kept


def build(repo_root: Path) -> None:
    """Reproduce the full graph from committed inputs (deterministic, no LLM)."""
    sources = repo_root / "sources"
    out = repo_root / "graphify-out" / "graph.json"

    # FIRST — before `mf.load_all` reads a single manifest. The direction is the
    # point: an input edited mid-build did not reach this graph, so recording its
    # pre-read digest makes the very next check FIRE. Digesting later would record
    # content the build never saw and bless a graph the edit never reached, which
    # is the one direction this detector must never fail in.
    #
    # It sat after `load_all` when this landed, which is 17 lines too late — the
    # manifests were already `read_text`-ed by then, so an edit in that window
    # produced exactly the false green the comment claimed to prevent. Keep this
    # line at the top of the function; nothing above it may touch `sources/`.
    # (Cold lane, round 1.)
    inputs = _required_input_fingerprints(repo_root)

    manifests = mf.load_all(sources)
    if not manifests:
        raise SystemExit("no sources/*.manifest found")

    # VALIDATE EVERY COMMITTED CHUNK **FIRST** — before the stamp is cleared,
    # before a single clone, and above all before anything writes graph.json.
    #
    # This sat after the corpus merge until the cold lane's round 2. It refused,
    # correctly, but only AFTER `_merge_sources_into` had already replaced the
    # aggregate with a code-only composition — so a bad chunk cost the working
    # graph and left a partial one that `kb-query` will happily serve, since it
    # checks only that the file exists. A refusal that is not atomic with respect
    # to the artifact it protects is a refusal that has already done the damage.
    # Cheap enough to be free here: 18 files, a few milliseconds, no network.
    from kb_setup import chunks as _chunks

    chunk_paths = sorted((sources / "extractions").glob("*.json"))
    problems = {p: i for p, i in _chunks.validate_files(chunk_paths).items() if i}
    if problems:
        lines = [f"  {p.name}: {i}" for p, issues in problems.items() for i in issues[:5]]
        raise SystemExit(
            f"{len(problems)} extraction chunk(s) failed validation — refusing to build:\n"
            + "\n".join(lines)
            + "\nRun `mise run kb-validate-chunks -- sources/extractions/*.json` for the full list."
        )

    # Cross-chunk source_file ownership (#189), BEFORE the stamp is cleared and
    # before anything touches graph.json — same atomicity argument as the block
    # above. A collision is invisible per-chunk: both chunks validate, and
    # `build_merge` resolves the shared `source_file` by DELETING the replay
    # loser's nodes for it, which is how a 2026-08-06 chunk destroyed 72 nodes of
    # an unrelated source with every gate green.
    collisions = _chunks.collision_issues(chunk_paths)
    if collisions:
        raise SystemExit(
            f"{len(collisions)} cross-chunk source_file collision(s) — refusing to build:\n  "
            + "\n  ".join(collisions)
        )

    manifests = _drop_skipped_builds(manifests)

    print(f"[kb-build] {len(manifests)} source(s)")
    for m in manifests:
        _ensure_clone(m)

    # Detection is a read-only, complete-corpus preflight. It runs only after
    # every immutable pin is present and verified, and before either the stamp
    # or graph.json is touched. One bad source must not hide the others.
    _detect_preflight(manifests)

    # Invalidate the stamp BEFORE anything touches graph.json. `build()` overwrites
    # the artifact at the seed step but only stamps at the very end, so any abort in
    # between — a merge failure, Ctrl-C — used to leave a NEW artifact under the OLD
    # stamp, which then asserted it was built by the pinned version. Clearing first
    # makes every abort fail closed as "never stamped". Detection above is deliberately
    # outside this mutation window.
    _clear_stamp(repo_root)

    # Code graph (AST — free, deterministic). Each source extracts into its own
    # sub-graph; prose-only repos (no code) are skipped WITHOUT aborting the build —
    # their content is added later by the host-agent prose wave, not here.
    #
    # A `kind = docs` manifest is NOT ASKED. `--code-only` is defined by graphify as
    # "index code … and skip doc/paper/image files", so running it over a docs mirror
    # is a guaranteed-empty full AST scan of every markdown file, on every build. The
    # reason to skip it is not only the waste: a docs manifest that never ran and a
    # code repo that ran and produced nothing are DIFFERENT ANSWERS, and until now
    # both printed the same `[skip] … no code nodes` line. That is the
    # not-applicable/could-not-check collapse this repo refuses everywhere else
    # (`currency`'s DRIFT/SKIP/OK). Declaring the kind makes the build say which.
    docs_only = [m.name for m in manifests if m.kind == "docs"]
    askable = [m.name for m in manifests if m.name not in docs_only]
    with_code = [name for name in askable if _extract_code(repo_root, name)]
    for name in docs_only:
        print(f"  [docs] {name}: kind=docs — no AST pass; prose comes from the extraction wave")
    skipped = [name for name in askable if name not in with_code]
    for name in skipped:
        print(f"  [skip] {name}: no code nodes — prose-only, deferred to the extraction wave")
    if not with_code:
        raise SystemExit("no source produced code nodes")

    # Partition by SCOPE before anything is seeded. Doing it here rather than in
    # the merge loop below is the whole correctness argument: the seed is chosen
    # first, so a partition applied only to merging would still let a study repo
    # seed the aggregate whenever it sorted ahead of the corpus sources — and the
    # corpus would then simply BE that repo, silently and totally.
    study_names = {m.name for m in manifests if m.scope == "study"}
    corpus = [n for n in with_code if n not in study_names]
    study = [n for n in with_code if n in study_names]
    if not corpus:
        raise SystemExit("no CORPUS source produced code nodes (only scope=study ones did)")

    # Compose graph.json from every code-bearing CORPUS source AND our own code
    # in ONE merge. Self joins this call rather than a second one as of #175 —
    # see `_merge_sources_into` for why pairwise/sequential merging duplicates
    # prefixes (#120), and `refresh_self` for why that removes its old
    # incremental-restart path. Every source (and self) now carries its own
    # tag, exactly once.
    self_subgraphs = _extract_self(repo_root)
    print(f"[kb-build] composing graph.json from {len(corpus)} corpus source(s) + our own code")
    _merge_sources_into(
        repo_root,
        out,
        [sources / n / "graphify-out" / "graph.json" for n in corpus] + self_subgraphs,
    )

    _build_study_graph(repo_root, sources, out.parent, study)
    _cluster_study_graph(repo_root, out.parent / STUDY_GRAPH_NAME)

    # Doc layer: replay the committed host-agent extractions (free — no subagents).
    # MERGE-ONLY (#169): `_merge_docs.py` no longer clusters, scores, or reports
    # per chunk — 17 of 18 such passes were discarded and never read. It loads
    # graph.json, merges the chunk, reconstructs communities from what the graph
    # already carries, and writes. The real clustering/labelling happens ONCE,
    # below, after every chunk has landed — not once per chunk.
    gpy = graphify_python(repo_root)
    # Already validated at the TOP of build(), before anything wrote graph.json.
    # CAPTURE-DATE order, not the glob's alphabetical order: build_merge gives
    # a source_file to the LAST chunk that names it, so replay order IS the
    # supersession rule — see `chunks.replay_order` for the measured defect
    # (a rebuild and an incremental merge producing different graphs from the
    # same committed corpus).
    print(f"[kb-build] merging {len(chunk_paths)} validated doc extraction(s)")
    _replay_doc_chunks(repo_root, gpy, sources, out, chunk_paths)

    # ONE final label pass — deterministic (no LLM; see `graphify_ops.label`'s own
    # docstring) — re-clusters the fully-composed graph and re-derives the prose
    # graph as its own last step. Hyperedge survival across the label round-trip
    # is graphify's own job since 0.9.34 (#171's carry was retired at that bump;
    # `hyperedges.py`'s module docstring carries the history), and
    # `assert_composition` below still refuses a dangling member either way.
    # `build()` no longer calls `prose.derive_for` itself: this IS that call
    # now, made by the function that already has to load graph.json for the
    # label pass, rather than a second, separate load of the same file.
    label_rc = graphify_ops.label(repo_root)
    if label_rc != 0:
        raise SystemExit(f"[kb-build] final label pass failed (rc={label_rc}) — aborting")

    # The composition invariants #120 and #171/#175 depend on: every id carries
    # at most one merge prefix, every carried hyperedge still resolves. Checked
    # HERE, on the artifact this build just produced, so a regression is caught
    # on the next build rather than only on the next `mise run test`.
    graph_checks.assert_composition(out, tag="kb-build", repo_root=repo_root)

    # What `kb-watch` recomposes FROM (#175's follow-up). Recorded here, after
    # composition is proven correct, so a `refresh_self` reading it back is
    # reading a description of an artifact `assert_composition` just vouched
    # for — never of a build that failed partway through. Resetting the ledger
    # in the same breath is the other half: this build already reflects every
    # `kb-merge` that landed since the last one (they are baked into `out`
    # above), so replaying them again on the next recomposition would be
    # redundant at best and wrong if any of them has since been hand-edited.
    _write_compose_manifest(
        repo_root,
        ComposeManifest(
            corpus=tuple(
                str((sources / n / "graphify-out" / "graph.json").relative_to(repo_root))
                for n in corpus
            ),
            self_graph=str(_self_subgraph(repo_root).relative_to(repo_root)),
            chunks=tuple(str(p.relative_to(repo_root)) for p in chunk_paths),
            # Every chunk here came from `build()`'s own `sources/extractions/*.json`
            # glob, so its root is always the naming-convention default
            # `_replay_targets` falls back to — no override needed.
            chunk_roots={},
        ),
    )
    _reset_merged_chunks(repo_root)

    _finalize_build_receipts(repo_root, inputs)
    print("[kb-build] done — graphify-out/graph.json + graph-prose.json reproduced")


def _currency_spec(repo_root: Path) -> ToolSpec | None:
    """The tool whose build artifacts THIS repo stamps, or None.

    Selected by NAME, not by "first spec that declares a stamp". `currency.toml`
    is explicitly multi-tool, so taking the first stamped entry would write
    `graphify --version` into whichever tool happened to sort first.
    """
    from kb_setup.currency import config

    return next((s for s in config.load(repo_root) if s.name == _STAMPED_TOOL and s.stamp), None)


def _clear_stamp(repo_root: Path, *, tag: str = "kb-build") -> None:
    """Remove the build stamp so an aborted build cannot leave a stale one.

    `tag` names the caller in the printed lines — `refresh_self` (via
    `_recompose_into_temp`) passes `"kb-watch"` so a `kb-watch` run's own
    bookkeeping is not misreported as `kb-build`'s (#175 cold review,
    finding 9).
    """
    receipt_path = repo_root / "graphify-out" / _BUILD_RECEIPT_NAME
    try:
        if receipt_path.exists():
            receipt_path.unlink()
            print(f"[{tag}] cleared {receipt_path.name} — it is rewritten only on success")
    except OSError as e:
        raise SystemExit(f"[{tag}] could not clear {receipt_path.name}: {e}") from e

    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return
        path = sync.stamp_path(repo_root, spec)
        if path is not None and path.exists():
            path.unlink()
            print(f"[{tag}] cleared {path.name} — it is rewritten only on success")
    except (OSError, ValueError, ImportError) as e:
        print(f"[{tag}] WARNING: could not clear the currency stamp: {e}")


def _input_fingerprints(repo_root: Path) -> dict[str, str] | None:
    """sha256 over every committed input `currency.toml` declares, or None.

    None means "could not be read", which `write_stamp` records as the ABSENCE of
    an input map — so the staleness check reports *not verifiable* rather than
    comparing against a partial one. Best-effort, like the stamp itself: a build
    must not fail over its own bookkeeping.
    """
    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return None
        return sync.input_fingerprints(repo_root, spec)
    except (OSError, ValueError, ImportError) as e:
        print(f"[kb-build] WARNING: could not fingerprint the corpus inputs: {e}")
        return None


def _required_input_fingerprints(repo_root: Path) -> dict[str, str]:
    """Return complete input evidence or refuse before any build input is read."""
    inputs = _input_fingerprints(repo_root)
    if inputs is None:
        raise SystemExit(
            "[kb-build] corpus input fingerprints are unavailable — refusing an unverifiable build"
        )
    return inputs


def _stamp_build(repo_root: Path, inputs: dict[str, str] | None = None) -> str:
    """Record which graphify version built these artifacts (currency step 1).

    graphify stamps nothing itself — `export.to_json()` writes only
    `built_at_commit` — so without this sidecar "which version built this graph?"
    is unanswerable from the artifact, and a graph built by a stale binary is
    indistinguishable from a current one.

    The version recorded is the one that ACTUALLY RAN (`graphify --version` on
    the resolved binary), never the pin. Since #40 that means resolving it the
    SAME way the build did — through `graphify_exe` — because `observed_version`
    resolves a bare name through PATH, and the build no longer does. Reading the
    two differently would stamp one binary's version onto another binary's graph:
    the precise unfalsifiable state this stamp exists to prevent, and one that
    did not exist while both sides happened to read PATH.
    Best-effort — a build must not fail over its stamp.
    """
    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return ""
        # NO fallback to the pin. Falling back would stamp the version we HOPED
        # ran, turning an unreadable binary into a false "in sync" — the exact
        # laundering this stamp exists to prevent. An empty version is written
        # as empty, and `check_sync` then reports "built by an unknown version".
        # Resolved exactly as the build resolved it (see the docstring).
        # Unconditional, not guarded on `spec.binary`: `_currency_spec` selects
        # by `name == _STAMPED_TOOL`, so the spec reaching here is always
        # graphify's, and the build always ran `graphify_exe`. An earlier draft
        # guarded on `spec.binary == _STAMPED_TOOL`, which compared a BINARY name
        # to a TOOL name — unreachable in the normal case and, for a config
        # setting `binary` to anything else, a silent fall back to the
        # PATH-resolved reading this exists to eliminate.
        version = _strict_graphify_version(repo_root)
        source_ref = sync.manifest_ref(repo_root, spec)
        path = sync.write_stamp(
            repo_root, spec, version=version, source_ref=source_ref, inputs=inputs
        )
        if version:
            print(f"[kb-build] stamped {path.name}: built by graphify {version}")
        else:
            print(
                f"[kb-build] WARNING: stamped {path.name} with an UNKNOWN version — "
                f"`{spec.binary} --version` could not be read, so currency step 1 "
                f"will report the graph as not verifiably built by the pin."
            )
    except (OSError, ValueError, ImportError) as e:
        print(f"[kb-build] WARNING: could not write the currency stamp: {e}")
        return ""
    return version


def _strict_graphify_version(repo_root: Path) -> str:
    """Observe the builder executable without accepting warning-bearing output."""
    exe = graphify_exe(repo_root)
    try:
        result = subprocess.run(
            [exe, "--version"],
            cwd=repo_root,
            check=False,
            env=clean_env(),
            capture_output=True,
        )
    except OSError, subprocess.SubprocessError:
        return ""
    if result.returncode != 0 or result.stderr:
        return ""
    match = re.search(rb"\b(\d+\.\d+\.\d+(?:\.\d+)?)\b", result.stdout)
    return match.group(1).decode() if match else ""


def _write_build_receipt(
    repo_root: Path,
    *,
    runtime_version: str,
    inputs: dict[str, str] | None,
) -> Path:
    """Atomically bind a successful build to exact graph, runtime, and input bytes."""
    pinned = pinned_graphify_version(repo_root)
    if not runtime_version or not pinned or runtime_version != pinned:
        raise SystemExit(
            "[kb-build] refusing build receipt with Graphify version drift "
            f"(pin={pinned or 'UNKNOWN'}, runtime={runtime_version or 'UNKNOWN'})"
        )
    if inputs is None:
        raise SystemExit("[kb-build] refusing build receipt without corpus input fingerprints")

    graph_path = repo_root / "graphify-out" / "graph.json"
    try:
        graph_bytes = graph_path.read_bytes()
        payload = json.loads(graph_bytes)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise SystemExit(f"[kb-build] refusing build receipt for unreadable graph.json: {e}") from e
    if not isinstance(payload, dict):
        raise SystemExit("[kb-build] refusing build receipt: graph.json root is not an object")
    collections: dict[str, list[object]] = {}
    for field in ("nodes", "edges", "hyperedges"):
        value = payload.get(field)
        if not isinstance(value, list):
            raise SystemExit(
                f"[kb-build] refusing build receipt: graph field {field!r} is not an array"
            )
        collections[field] = value

    receipt = GraphifyBuildReceipt(
        schema_version=1,
        status="complete",
        runtime_version=runtime_version,
        graph_sha256=hashlib.sha256(graph_bytes).hexdigest(),
        graph_bytes=len(graph_bytes),
        node_count=len(collections["nodes"]),
        edge_count=len(collections["edges"]),
        hyperedge_count=len(collections["hyperedges"]),
        input_fingerprints_sha256=_input_map_sha256(inputs),
        recorded_at_ns=time.time_ns(),
    )
    path = graph_path.with_name(_BUILD_RECEIPT_NAME)
    atomic.write_text(path, msgspec.json.encode(receipt).decode() + "\n")
    print(f"[kb-build] wrote {path.name}: sha256={receipt.graph_sha256}")
    return path


def _input_map_sha256(inputs: dict[str, str]) -> str:
    """Hash an input map with the same canonical encoding used in receipts."""
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _current_build_receipt_matches(repo_root: Path, held: _HeldStamp | None) -> bool:
    """Return whether kb-watch may honestly carry a prior build receipt forward."""
    if held is None or held.inputs is None:
        return False
    graph_path = repo_root / "graphify-out" / "graph.json"
    receipt_path = graph_path.with_name(_BUILD_RECEIPT_NAME)
    try:
        graph_bytes = graph_path.read_bytes()
        payload = json.loads(graph_bytes)
        receipt = msgspec.json.decode(receipt_path.read_bytes(), type=GraphifyBuildReceipt)
    except OSError, json.JSONDecodeError, UnicodeDecodeError, msgspec.DecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    collections = tuple(payload.get(field) for field in ("nodes", "edges", "hyperedges"))
    if not all(isinstance(value, list) for value in collections):
        return False
    nodes, edges, hyperedges = collections
    return (
        receipt.schema_version == 1
        and receipt.status == "complete"
        and receipt.warnings == ()
        and receipt.runtime_version == held.version
        and receipt.graph_sha256 == hashlib.sha256(graph_bytes).hexdigest()
        and receipt.graph_bytes == len(graph_bytes)
        and receipt.node_count == len(nodes)
        and receipt.edge_count == len(edges)
        and receipt.hyperedge_count == len(hyperedges)
        and receipt.input_fingerprints_sha256 == _input_map_sha256(held.inputs)
    )


def _finalize_build_receipts(repo_root: Path, inputs: dict[str, str]) -> None:
    """Write both compatible build receipts only after the graph is complete."""
    runtime_version = _stamp_build(repo_root, inputs)
    _write_build_receipt(repo_root, runtime_version=runtime_version, inputs=inputs)


@dataclass(frozen=True)
class _HeldStamp:
    """A build stamp's carry-forward fields, snapshotted before `_clear_stamp` runs.

    `_recompose_into_temp` unlinks the stamp file (`_clear_stamp`) immediately
    before swapping in the recomposed graph.json — the same "clear first,
    write only on success" rule `build()` follows, applied at the one moment
    it matters for this shape (see that function's own docstring). But unlike
    `build()`, `refresh_self` never runs a builder to re-observe `version`
    from and never re-reads a manifest to derive `source_ref` from — the only
    thing it can honestly do is carry the LAST real build's values forward
    VERBATIM, and that means reading them off disk BEFORE the clear destroys
    them, not after.

    Before this existed, `refresh_self` tried to restamp AFTER the clear by
    calling `sync.restamp_artifacts` — whose contract is "refresh an EXISTING
    stamp" (`if path is None or not path.exists(): return None`), exactly
    right for its OTHER caller `kb-artifacts`, which never deletes the stamp
    first. Here it always found the file already gone and always returned
    `None`, so every `kb-watch` silently left the repo permanently unstamped
    (#175 cold review round 2, NEW-1). `_held_stamp` is the fix: read these
    fields while the file still exists, hold them across the clear, and write
    them straight back via `sync.write_stamp` — never through
    `restamp_artifacts`, which by then would find nothing.
    """

    version: str
    source_ref: str
    inputs: dict[str, str] | None


def _held_stamp(repo_root: Path) -> _HeldStamp | None:
    """Snapshot the stamp's carry-forward fields — MUST run BEFORE the clear.

    `refresh_self` calls this before `_recompose_into_temp`, which is what
    clears the stamp. There is no later point at which these fields could
    still be read off disk — see :class:`_HeldStamp`'s docstring for the
    defect this exists to avoid repeating.

    Mirrors `sync.restamp_artifacts`'s own "no existing stamp -> nothing to
    carry forward" rule (`None` here means the same thing `restamp_artifacts`
    returning `None` means there), just evaluated on the PRE-clear file
    instead of a post-clear one that can no longer exist.

    Best-effort, like every other stamp path in this module: a read failure
    must not abort a recomposition that is otherwise fine. `refresh_self`
    just ends unstamped and says so — the same outcome as running `kb-watch`
    before any `kb-build` has ever stamped anything.
    """
    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return None
        path = sync.stamp_path(repo_root, spec)
        if path is None or not path.exists():
            return None
        existing = sync.read_stamp(repo_root, spec)
        return _HeldStamp(
            version=str(existing.get("version", "")),
            source_ref=str(existing.get("source_ref", "")),
            inputs=sync.stamped_input_fingerprints(existing),
        )
    except (OSError, ValueError, ImportError) as e:
        print(f"[kb-watch] WARNING: could not read the existing currency stamp: {e}")
        return None


def _restamp_self(repo_root: Path, held: _HeldStamp | None) -> None:
    """Write `held` back as the stamp — the fields `_held_stamp` read before the clear.

    NOT `sync.restamp_artifacts`: that reads the CURRENT on-disk stamp, and by
    the time `refresh_self` reaches its own tail, `_recompose_into_temp` has
    already unlinked it (`_clear_stamp`, immediately before the swap). `held`
    is what survives that — a snapshot taken earlier, before the file was
    destroyed (#175 cold review round 2, NEW-1; see `_held_stamp`).

    `version` and `source_ref` are written back exactly as held, never
    re-observed: the graph changed but the BUILDER did not, and re-observing
    would let a graphify upgrade mid-session silently relabel a graph the
    previous version actually built. The recorded INPUT fingerprint map is
    carried forward the same way and for the same reason: `refresh_self`
    deliberately never re-reads `sources/*.manifest` /
    `sources/extractions/*.json` (see its own docstring), so it has no more
    standing to restate what the graph was built from than `kb-artifacts`
    does. `sync.write_stamp` recomputes `artifact_fingerprints` itself, fresh
    — that part MUST be live, since the whole point of a restamp is that the
    artifact's bytes just moved.

    `held is None` means there was nothing to carry forward — either no
    `kb-build` has ever stamped this repo, or `_held_stamp`'s own read failed.
    Without ANY restamp, a refresh is actively harmful: `artifact_fingerprints`
    is `size:mtime_ns`, so any rewrite of graph.json moves it, and every later
    `kb-currency-check` reports the graph as not verifiably built by the pin —
    a permanent red that means nothing, which is how a real signal gets
    ignored. So this still prints the warning a from-scratch `kb-watch` has
    always printed, rather than staying silent. Best-effort like every other
    stamp path here: a refresh must not fail over its own bookkeeping.
    """
    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return
        if held is None:
            print(
                "[kb-watch] WARNING: no build stamp to refresh — run `mise run kb-build`; "
                "currency step 1 will report this graph as never stamped."
            )
            return
        path = sync.write_stamp(
            repo_root, spec, version=held.version, source_ref=held.source_ref, inputs=held.inputs
        )
        print(f"[kb-watch] restamped {path.name}")
    except (OSError, ValueError, ImportError) as e:
        print(f"[kb-watch] WARNING: could not restamp: {e}")


def update_all(repo_root: Path) -> int:
    """Advance every tracked source to its latest upstream commit.

    `kind = docs` sources are INCLUDED, and the omission is worth recording: this
    filtered to `kind == "code"` when the only kind in use was `code`, so adding
    the docs kind silently excluded every docs mirror from the bulk path. The
    changed-page worklist — the entire reason a mirror is pinned — would then only
    ever appear when someone named the source by hand, which is the failure mode
    where a check exists and never runs. (Cold lane, P2.)
    """
    manifests = mf.load_all(repo_root / "sources")
    repos = [m for m in manifests if m.kind in {"code", "docs"}]
    if not repos:
        print("[kb-update] no manifests to update")
        return 0
    print(f"[kb-update] checking {len(repos)} source(s) for upstream updates")
    # WORST rc, not the last one: a bulk run must not report success because the
    # source that failed happened not to sort last.
    return max((update(repo_root, m.name) for m in repos), default=0)


def update(repo_root: Path, name: str) -> int:
    """Advance one source to its latest upstream commit and incrementally re-extract.

    Returns a process exit code. A docs pin whose diff FAILED returns 1: the pin
    is correctly left unmoved, but the CLI used to `return 0` regardless, so the
    one failure path this module has was invisible to anything reading an rc.
    (Cold lane round 2, P2 — the round-1 fix stopped the state corruption and
    left the signal broken.)
    """
    sources = repo_root / "sources"
    m = mf.load(sources / f"{name}.manifest")
    latest = mf.latest_commit(m)
    if latest == m.commit:
        print(f"[kb-update] {name} already at latest {latest[:10]} — nothing to do")
        return 0

    print(f"[kb-update] {name}: {m.commit[:10]} -> {latest[:10]}")
    if m.kind == "docs":
        return _advance_docs_pin(m, latest)

    # The writer version gate belongs to THIS branch, not the dispatch layer:
    # the docs pin advance above is pure git and must never be blocked by a
    # stale binary it does not run (cold lane round 2, P2). Only from here on
    # does graphify touch the artifact.
    assert_pinned_graphify(repo_root)

    m = mf.write_commit(m, latest)
    _ensure_clone(m)

    # Incremental CODE re-extract (AST — free; MD5-diffs graphify-out/manifest.json).
    _run([graphify_exe(repo_root), "update", f"sources/{name}"], repo_root)
    print(
        f"[kb-update] {name} code updated. NOTE: changed DOCS are not re-extracted "
        f"here — host-agent extraction (a Claude Code session) must re-run on changed "
        f"docs and refresh sources/extractions/{name}-docs.json (the semantic cache "
        f"skips unchanged docs)."
    )
    return 0


#: Extensions the host-agent extraction wave can actually read. A docs mirror is
#: still a git repo, so its own metadata (`docs_manifest.json`, workflows, README
#: scaffolding) changes on syncs that touched no documentation at all. Listing
#: those as "re-extraction work" would spend host-agent tokens on a build script.
#: (Cold lane, P2.)
_DOC_SUFFIXES = frozenset({".md", ".mdx", ".markdown", ".rst", ".txt"})

#: `git diff --name-status` emits `R<score>\told\tnew` for a rename or copy — two
#: paths where every other status has one.
_RENAME_PATHS = 2


def _is_doc(path: str) -> bool:
    return Path(path).suffix.lower() in _DOC_SUFFIXES


def _classify_change(status: str, paths: list[str]) -> tuple[list[str], list[str]]:
    """One `--name-status` row -> (paths to re-extract, stale extractions to drop).

    Both lists empty means the row touched no document — a mirror's own metadata,
    which is real churn but not extraction work.
    """
    if not any(_is_doc(p) for p in paths):
        return [], []
    if status.startswith("D"):
        return [], [p for p in paths if _is_doc(p)]
    if status.startswith(("R", "C")) and len(paths) == _RENAME_PATHS:
        old, new = paths
        extract = [new] if _is_doc(new) else []
        # A COPY leaves the original in place; only a RENAME makes it stale.
        # Treating `C###` like `R###` queued a file that still exists for
        # removal. Bounded — the worklist is advisory, read by a host agent
        # rather than executed — but it would send that agent to delete a live
        # page's extraction. (Cold lane round 2, P2.)
        if status.startswith("C"):
            return extract, []
        return extract, ([old] if _is_doc(old) else [])
    return [p for p in paths if _is_doc(p)], []


def _advance_docs_pin(m: mf.Manifest, latest: str) -> int:
    """Advance a `kind = docs` pin, but ONLY once its worklist has been reported.

    THE POINT OF A DOCS MIRROR, and the reason `kind` had to stop being inert
    metadata. Fingerprinting a page (`currency.toml` `docs_watch`) proves THAT it
    changed and can never say WHAT — knowledge-base#76 was opened on three moved
    sha256 values with no way to read the delta, and the only reason that session
    recovered one was that a gitignored `.agent/kb/raw/` copy of the old text
    happened to survive. A `git clean -xdf` erases that; a pinned clone does not.

    ORDER IS THE WHOLE CORRECTNESS ARGUMENT, and the first version got it wrong.
    It wrote the pin, then diffed, and on a diff failure printed "UNKNOWN, not
    empty — re-run". But the pin had already moved, so the re-run hit
    `latest == m.commit` and reported *"already at latest — nothing to do"*: the
    worklist was not merely unreported, it was **unrecoverable**, and the careful
    UNKNOWN message pointed at a retry that could no longer work. The comment
    there read "a report gap, not a build failure", which is exactly the kind of
    self-reassurance a cold reviewer is for — it was found by one (P2).

    So the clone is brought to `latest` in memory, the diff runs, and the manifest
    is written only if the diff SUCCEEDED. A failure now leaves the pin where it
    was, which makes the retry the message promises actually work.

    Printed, never acted on. Re-extraction is a Claude Code session's job
    (invariant: the host agent IS the extraction LLM), so this task's contract is
    to hand over an accurate worklist and stop.
    """
    advanced = replace(m, commit=latest)
    _ensure_clone(advanced)
    diff = subprocess.run(
        ["git", "-C", str(advanced.clone_dir), "diff", "--name-status", m.commit, latest],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if diff.returncode != 0:
        print(
            f"[kb-update] {m.name}: doc diff FAILED "
            f"({diff.stderr.strip() or 'no stderr'}) — the changed-page list is "
            f"UNKNOWN, not empty, so the pin was NOT advanced (still "
            f"{m.commit[:10]}). Re-run to retry."
        )
        return 1

    mf.write_commit(m, latest)
    _print_doc_worklist(m.name, diff.stdout)
    return 0


def _print_doc_worklist(name: str, name_status: str) -> None:
    """Turn `git diff --name-status` into a worklist that says what to DO.

    `--name-only` was the first version and it flattened three different jobs into
    one list (cold lane, P2). A deletion upstream is not re-extraction work — it is
    a *stale extraction to remove*, and reporting it as a page to read sends the
    host agent after a file that no longer exists. A rename is the same, plus the
    old path that has to be dropped. So the status column is kept and the output is
    grouped by the action each change implies.
    """
    extract: list[str] = []
    drop: list[str] = []
    other = 0
    for line in name_status.splitlines():
        if not line.strip():
            continue
        status, *paths = line.split("\t")
        if not paths:
            continue
        did_extract, did_drop = _classify_change(status, paths)
        if not did_extract and not did_drop:
            other += 1
            continue
        extract.extend(did_extract)
        drop.extend(did_drop)

    if not extract and not drop:
        # Distinct from "0 files changed": non-document churn is a real answer —
        # the mirror synced, and nothing the extraction wave reads was touched.
        suffix = f" ({other} non-document file(s) changed)" if other else ""
        print(f"[kb-update] {name}: pin advanced, no document changes{suffix}")
        return

    print(f"[kb-update] {name}: pin advanced — re-extraction worklist:")
    for path in extract:
        print(f"    re-extract  {path}")
    for path in drop:
        print(f"    REMOVE stale extraction for  {path}")
    if other:
        print(f"    ({other} non-document file(s) changed — not extraction work)")
