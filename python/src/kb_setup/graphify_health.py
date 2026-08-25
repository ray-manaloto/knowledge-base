# Copyright (c) 2026 Raymond Manaloto
"""Typed, fail-closed health receipts for Graphify operations."""

from __future__ import annotations

import re
from collections import Counter
from enum import StrEnum
from pathlib import PurePosixPath

import msgspec

APPROVED_METADATA_ZERO_NODE_WARNING = "approved-reviewed-metadata-zero-node"
APPROVED_PARTIAL_EXTRACTION_WARNING = "approved-reviewed-partial-extraction"
#: A SAME-FILE id collision: one entity the extractor labelled twice, one label
#: discarded. Approved because graphify itself draws this distinction and says
#: what it costs — `dedup.py:_report_id_collision` emits a lower-case `note:`
#: here and states that "the structural entity and its edges survive", reserving
#: `WARNING:` for the different-FILE case where "they are distinct entities and
#: one is genuinely lost".
#:
#: The severity split is the whole reason this is a separate token rather than a
#: widening of an existing one. Approving the `note:` must not approve the
#: `WARNING:`: that one IS the #231 silent-loss shape and has to keep blocking.
APPROVED_SAME_FILE_ID_COLLISION_NOTE = "approved-same-file-id-collision-note"
#: A language Graphify has NO extractor for at all (#1689). Deliberately its own
#: token rather than a widening of `APPROVED_PARTIAL_EXTRACTION_WARNING`, because
#: the two describe opposite situations and only one of them can be fixed here:
#: a partial extraction means the parser RAN and recovered some of the file, so
#: the loss moves when the file or the grammar changes; a missing extractor means
#: no parser exists, so every file in that language contributes zero forever and
#: the loss moves only when UPSTREAM ships one.
#:
#: Keeping them apart is what makes the eventual fix visible. Graphify's own
#: `extract.py` draws the same line — the #1666 zero-node warning "deliberately
#: skips these (it only fires when an extractor exists)" — and flattening it here
#: would let an upstream R extractor land without anything in this repo noticing
#: that a reviewed loss had stopped being real.
APPROVED_UNSUPPORTED_LANGUAGE_WARNING = "approved-reviewed-unsupported-language"


class GraphifyOperation(StrEnum):
    """Graphify lifecycle operations covered by the shared health contract."""

    HEALTH = "health"
    QUERY = "query"
    DETECT = "detect"
    EXTRACT = "extract"
    BUILD = "build"
    REFLECT = "reflect"
    ARTIFACT = "artifact"


class GraphifyState(StrEnum):
    """Whether an operation produced evidence safe for downstream use."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class GraphifyReceipt(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Serializable result retaining output, coverage, and integrity findings."""

    operation: GraphifyOperation
    state: GraphifyState
    returncode: int
    reasons: tuple[str, ...]
    source_name: str | None = None
    stdout: str = ""
    stderr: str = ""
    detected_sources: int | None = None
    extracted_sources: int | None = None
    unclassified_files: int = 0
    zero_node_sources: int = 0
    unclassified_paths: tuple[str, ...] = ()
    zero_node_paths: tuple[str, ...] = ()
    ignored_paths: tuple[str, ...] = ()
    #: Absorbed as a language Graphify cannot parse — retained so the count
    #: survives into the census rather than disappearing into a green result.
    unsupported_language_paths: tuple[str, ...] = ()
    #: The paths that ACTUALLY block: unclassified minus everything a reviewed
    #: class absorbed. Reported separately from `unclassified_paths` because a
    #: failure message listing all 1,075 unclassified files — of which 1,070 are
    #: absorbed and 5 are the problem — buries its own answer.
    unresolved_paths: tuple[str, ...] = ()
    #: Unbounded totals. The `*_paths` tuples above are display evidence capped
    #: by `_bounded_paths`, so any count or tally MUST come from these fields —
    #: a `len()` over the bounded tuples saturates at the display bound.
    unresolved_count: int = 0
    unsupported_language_count: int = 0
    unsupported_language_tally: tuple[tuple[str, int], ...] = ()
    timed_out: bool = False
    approved_classifications: tuple[str, ...] = ()
    #: Retained so a reader can see WHICH stderr blocked, not merely that some
    #: did — the reason string is one word and the raw stderr may be pages.
    residual_stderr: str | None = None
    mode: str | None = None
    expected_artifacts: tuple[str, ...] = ()
    produced_artifacts: tuple[str, ...] = ()
    expected_scope: str | None = None
    observed_scope: str | None = None


class SourceCoveragePolicy(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Explicit source-coverage boundary; required paths can never be allowlisted."""

    required_paths: tuple[str, ...] = ()
    optional_unclassified_paths: tuple[str, ...] = ()
    optional_zero_node_paths: tuple[str, ...] = ()
    optional_ignored_paths: tuple[str, ...] = ()
    #: Real source in a language Graphify cannot parse. Kept in its OWN field
    #: rather than folded into `optional_unclassified_paths`, because these are
    #: measurable corpus loss and the build reports them; a single allowlist
    #: would make them indistinguishable from a LICENSE file.
    unsupported_language_paths: tuple[str, ...] = ()


#: Sentinel `ExpectedMetadataOnly.skipped_disposition` for a package manifest
#: (`pyproject.toml`/`Cargo.toml`/`go.mod`/...) whose zero-node route is
#: graphify's `extract_package_manifest`, never `extract_json` — #1377 routes
#: every `PACKAGE_MANIFEST_NAMES` filename there ahead of all suffix dispatch.
#: That extractor never emits a `skipped` reason on its zero-node case
#: (`manifest_ingest.py:66-67` returns a bare `{"nodes": [], "edges": []}` when
#: the parsed table has no `[project]`/`[package]` name — a workspace root or a
#: manifest holding only `[tool.*]` configuration) — so unlike every other value
#: of this field, this one is never graphify's own output. It is this repo's own
#: reviewed classification, checked for an EXACT match anyway
#: (`graphify_sdk.approve_metadata_zero_node_warning`) so an item misrouted to
#: the wrong extractor still refuses.
#:
#: Deliberately does NOT start with `"error:"` — `graphify_sdk.py`'s `warned`
#: filter drops any entry whose disposition does, which would silently remove
#: every manifest entry from the zero-node count and present as an inexplicable
#: refusal rather than the mistake it is.
EXPECTED_PACKAGE_MANIFEST_NO_NAME = "reviewed-package-manifest-no-name"


class ExpectedMetadataOnly(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Reviewed file whose exact bytes intentionally produce no graph nodes.

    Two disjoint routes share this one struct, distinguished by
    `graphify.manifest_ingest.is_package_manifest_path` at verification time —
    never a `try/except` fallback between extractors, which would give an
    errored file a second bite at approval:

    - an ordinary JSON file `extract_json` skips (e.g. an MCP/plugin config it
      declines as "not a config/manifest"): `skipped_disposition` is the exact
      string graphify's own `skipped` key reports.
    - a package manifest `extract_package_manifest` parses but finds no
      `name` in: `skipped_disposition` is the `EXPECTED_PACKAGE_MANIFEST_NO_NAME`
      sentinel above, since graphify reports nothing to pin to for this case.
    """

    source_name: str
    relative_path: str
    content_sha256: str
    skipped_disposition: str


class ExpectedPartialExtraction(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Reviewed file Graphify's parser only recovers partially, with the loss COUNTED.

    Graphify's #2551 warning says "may be partially extracted" and states no
    count, so registering one of these without a number would approve an unknown
    quantity of corpus loss — the #231 shape. `extracted_nodes` is therefore
    checked against the sub-graph at build time, and `lost_symbols` records the
    reviewed measurement of what is missing.
    """

    source_name: str
    relative_path: str
    content_sha256: str
    #: The line the warning names. Pinned so a parser whose failure MOVES stops
    #: matching this entry rather than silently reusing its approval.
    first_error_line: int
    #: Nodes the file actually contributes. VERIFIED against the emitted
    #: sub-graph, never trusted from this file.
    extracted_nodes: int
    #: Named symbols absent from the graph — the reviewed measurement.
    lost_symbols: int
    reason: str


class ExpectedUnsupportedLanguage(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Reviewed file in a language Graphify has no AST extractor for, loss COUNTED.

    The #1689 warning names EXTENSIONS and counts, never paths — so unlike
    `ExpectedPartialExtraction`, the warning text alone cannot say which files it
    is about. The paths come from this inventory and are verified two ways: the
    bytes must still hash to `content_sha256`, and the sub-graph must carry ZERO
    nodes for the path. That second check is what stops this from becoming a
    blanket per-language allowlist: the moment upstream ships an extractor the
    file starts producing nodes, the entry stops matching, and the build says so
    rather than quietly keeping an approval for loss that no longer happens.

    `lost_symbols` is the reviewed count of named definitions the file contains
    and the graph therefore does not. It is not derivable from the warning — the
    warning's number counts FILES — so registering an entry without it would
    approve an unmeasured quantity of corpus loss, the #231 shape.
    """

    source_name: str
    relative_path: str
    content_sha256: str
    #: The lower-cased suffix Graphify groups the warning by, e.g. `.r`. Stored
    #: rather than derived from `relative_path` because the warning is matched on
    #: THIS, and a file whose extension case differs (`.R` on disk, `.r` in the
    #: warning) must still be matched by the token graphify actually printed.
    language: str
    #: Named definitions in the file that are absent from the graph — the
    #: reviewed measurement, counted by reading the file.
    lost_symbols: int
    reason: str


class ExpectedUnclassifiedFile(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Reviewed source-specific file Graphify intentionally cannot classify."""

    source_name: str
    relative_path: str
    content_sha256: str
    classification: str


class IncompleteGraphifyOperationError(RuntimeError):
    """A Graphify receipt cannot authorize downstream work."""


class GraphifyEvidence(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    """Raw observations to classify for one Graphify operation."""

    observed: bool = False
    source_name: str | None = None
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    detected_sources: int | None = None
    extracted_sources: int | None = None
    unclassified_files: int = 0
    zero_node_sources: int = 0
    unclassified_paths: tuple[str, ...] = ()
    zero_node_paths: tuple[str, ...] = ()
    ignored_paths: tuple[str, ...] = ()
    coverage_policy: SourceCoveragePolicy | None = None
    timed_out: bool = False
    approved_classifications: tuple[str, ...] = ()
    #: Stderr left over after every REVIEWED warning block was removed by name.
    #: `None` means no caller computed it, and then the full `stderr` blocks —
    #: absence of a residual is never absence of a problem.
    #:
    #: This exists because approval used to be whole-stderr: one recognised
    #: token approved everything the subprocess printed. One source can emit two
    #: independent warnings (measured on `Attacca`: an 8-file zero-node warning
    #: AND a #2551 partial-extraction warning), and under whole-stderr approval
    #: registering either one could never approve the pair — while a single
    #: token would have approved an unrelated third warning for free.
    residual_stderr: str | None = None
    mode: str | None = None
    deep_required: bool = False
    reflection_expected: bool = False
    reflection_produced: bool = False
    expected_artifacts: tuple[str, ...] = ()
    produced_artifacts: tuple[str, ...] = ()
    expected_scope: str | None = None
    observed_scope: str | None = None


#: Graphify's OWN routine progress narration for a merge that drops nodes/edges
#: belonging to a source file it no longer sees (deleted upstream, or newly
#: excluded) — not a warning, and not something a caller reviews. The graph
#: falling back into sync with a deletion is not corpus loss, so unlike every
#: APPROVED_*/Expected* class above this needs no token and no inventory entry:
#: there is nothing here for a reviewer to have gotten wrong.
#:
#: Matched ANCHORED against the exact two f-strings Graphify's `build.py` prints
#: for this (the node line carries a from-N-files count; the edge line does
#: not). Graphify reuses the SAME "[graphify] " prefix a few statements away in
#: the same function for genuine `WARNING:` lines (a prune source that matched
#: nothing, a dropped hyperedge) — so recognising the prefix alone, or "Pruned"
#: alone, would launder those through as if reviewed. Anchoring on the full
#: line (`\A…\Z`) means a benign line carrying extra trailing text is NOT
#: silently approved either.
_ROUTINE_PRUNE_PROGRESS = re.compile(
    r"\A\[graphify\] Pruned \d+ (?:node|edge)\(s\) from(?: \d+)? deleted or "
    r"excluded source file\(s\)\.\Z"
)


def _unaccounted_stderr(stderr: str, residual_stderr: str | None) -> str:
    """Stderr no caller reviewed, minus lines Graphify narrates as routine.

    `residual_stderr` already drops everything a CALLER approved BY NAME (see
    its own docstring on `GraphifyEvidence`); this drops the smaller, separate
    class that needs no approval at all because Graphify prints it on every
    ordinary merge whether or not anything is actually wrong. Filtered
    line-by-line and matched anchored — recognising one benign line is never
    license to wave the rest of the same stderr through unread.
    """
    raw = stderr if residual_stderr is None else residual_stderr
    kept = [line for line in raw.splitlines() if not _ROUTINE_PRUNE_PROGRESS.match(line.strip())]
    return "\n".join(kept)


def _basic_reasons(evidence: GraphifyEvidence) -> list[str]:
    reasons: list[str] = []
    if not evidence.observed:
        reasons.append("evidence-missing")
    if evidence.timed_out:
        reasons.append("timeout")
    # Approval is per WARNING, never per subprocess. `residual_stderr` is what a
    # caller could not account for by name; when it was never computed, the whole
    # of stderr is unaccounted for. A classification token records WHY something
    # was approved — it has never been sufficient on its own, and is deliberately
    # not consulted here, so a token can no longer approve text nobody read. A
    # second, narrower class needs no token at all: see `_unaccounted_stderr`.
    unaccounted = _unaccounted_stderr(evidence.stderr, evidence.residual_stderr)
    if unaccounted.strip():
        reasons.append("stderr")
    if "truncated" in f"{evidence.stdout}\n{evidence.stderr}".casefold():
        reasons.append("truncated")
    if re.search(
        r"\bpartial(?:\s+result)?\s*:\s*\d+\s*/\s*\d+\b",
        f"{evidence.stdout}\n{evidence.stderr}",
        flags=re.IGNORECASE,
    ):
        reasons.append("partial-result")
    if (
        evidence.detected_sources is not None
        and evidence.extracted_sources is not None
        and evidence.extracted_sources < evidence.detected_sources
    ):
        reasons.append("source-coverage-partial")
    return reasons


def _unresolved_unclassified(evidence: GraphifyEvidence) -> tuple[str, ...]:
    """Unclassified paths no reviewed class absorbed — the ones that block."""
    policy = evidence.coverage_policy
    if policy is None:
        return tuple(evidence.unclassified_paths)
    absorbed = set(policy.optional_unclassified_paths) | set(policy.unsupported_language_paths)
    return tuple(sorted(set(evidence.unclassified_paths) - absorbed))


def _coverage_reasons(evidence: GraphifyEvidence) -> list[str]:
    reasons: list[str] = []
    required = set(evidence.coverage_policy.required_paths) if evidence.coverage_policy else set()
    ignored = set(evidence.ignored_paths)
    if required & ignored:
        reasons.append("required-source-ignored")
    if ignored and (
        evidence.coverage_policy is None
        or ignored - set(evidence.coverage_policy.optional_ignored_paths)
    ):
        reasons.append("ignored-paths")
    if evidence.coverage_policy is None:
        if evidence.unclassified_files or evidence.unclassified_paths:
            reasons.append("unclassified-files")
        if evidence.zero_node_sources or evidence.zero_node_paths:
            reasons.append("zero-node-sources")
    else:
        unclassified = set(evidence.unclassified_paths)
        zero_node = set(evidence.zero_node_paths)
        if required & unclassified:
            reasons.append("required-source-unclassified")
        if required & zero_node:
            reasons.append("required-source-zero-nodes")
        absorbed = set(evidence.coverage_policy.optional_unclassified_paths) | set(
            evidence.coverage_policy.unsupported_language_paths
        )
        if unclassified - absorbed:
            reasons.append("unclassified-files")
        if zero_node - set(evidence.coverage_policy.optional_zero_node_paths):
            reasons.append("zero-node-sources")
    return reasons


def _output_reasons(evidence: GraphifyEvidence) -> list[str]:
    reasons: list[str] = []
    if evidence.deep_required and evidence.mode != "deep":
        reasons.append("deep-extraction-missing")
    if evidence.reflection_expected and not evidence.reflection_produced:
        reasons.append("reflection-missing")
    if set(evidence.expected_artifacts) - set(evidence.produced_artifacts):
        reasons.append("artifacts-partial")
    if evidence.expected_scope is not None and evidence.observed_scope != evidence.expected_scope:
        reasons.append("source-scope-mismatch")
    return reasons


def assess(
    operation: GraphifyOperation,
    evidence: GraphifyEvidence | None = None,
) -> GraphifyReceipt:
    """Classify explicit Graphify evidence without converting unknowns into success."""
    evidence = evidence or GraphifyEvidence()
    reasons = [
        *_basic_reasons(evidence),
        *_coverage_reasons(evidence),
        *_output_reasons(evidence),
    ]
    unresolved = _unresolved_unclassified(evidence)
    unsupported = (
        evidence.coverage_policy.unsupported_language_paths if evidence.coverage_policy else ()
    )

    state = GraphifyState.COMPLETE
    if evidence.returncode != 0:
        state = GraphifyState.FAILED
        reasons.insert(0, "nonzero-returncode")
    elif reasons:
        state = GraphifyState.INCOMPLETE
    return GraphifyReceipt(
        operation=operation,
        state=state,
        returncode=evidence.returncode,
        reasons=tuple(dict.fromkeys(reasons)),
        source_name=evidence.source_name,
        stdout=evidence.stdout,
        stderr=evidence.stderr,
        detected_sources=evidence.detected_sources,
        extracted_sources=evidence.extracted_sources,
        unclassified_files=evidence.unclassified_files,
        zero_node_sources=evidence.zero_node_sources,
        unclassified_paths=_bounded_paths(evidence.unclassified_paths),
        zero_node_paths=_bounded_paths(evidence.zero_node_paths),
        ignored_paths=_bounded_paths(evidence.ignored_paths),
        unresolved_paths=_bounded_paths(unresolved),
        unsupported_language_paths=_bounded_paths(unsupported),
        unresolved_count=len(unresolved),
        unsupported_language_count=len(unsupported),
        unsupported_language_tally=_language_tally(unsupported),
        timed_out=evidence.timed_out,
        approved_classifications=evidence.approved_classifications,
        residual_stderr=evidence.residual_stderr,
        mode=evidence.mode,
        expected_artifacts=evidence.expected_artifacts,
        produced_artifacts=evidence.produced_artifacts,
        expected_scope=evidence.expected_scope,
        observed_scope=evidence.observed_scope,
    )


def require_complete(receipt: GraphifyReceipt) -> GraphifyReceipt:
    """Return a complete receipt or raise with its retained integrity reasons."""
    if receipt.state is not GraphifyState.COMPLETE:
        detail = ", ".join(receipt.reasons) or "unknown integrity failure"
        evidence: list[str] = []
        if receipt.source_name:
            evidence.append(f"source={receipt.source_name[:80]}")
        if receipt.unresolved_paths:
            # The blocking subset first, and on its own: these are the paths a
            # reader has to act on. `unclassified` may be a thousand entries of
            # which every one but these was absorbed by a reviewed class.
            evidence.append(f"unresolved={list(receipt.unresolved_paths)!r}")
        elif receipt.unclassified_paths:
            evidence.append(f"unclassified={list(receipt.unclassified_paths)!r}")
        if receipt.zero_node_paths:
            evidence.append(f"zero_nodes={list(receipt.zero_node_paths)!r}")
        if receipt.ignored_paths:
            evidence.append(f"ignored={list(receipt.ignored_paths)!r}")
        if "stderr" in receipt.reasons:
            # The line(s) nobody accounted for, bounded, with Graphify's own
            # routine progress narration already filtered out — a reader should
            # not have to skim past "Pruned 3 node(s)..." to find the line that
            # actually blocked. `stderr` on its own sent a reader to re-run the
            # build to find out WHICH warning blocked.
            unaccounted = _unaccounted_stderr(receipt.stderr, receipt.residual_stderr)
            evidence.append(f"unaccounted_stderr={unaccounted.strip()[:400]!r}")
        suffix = f"; {'; '.join(evidence)}" if evidence else ""
        raise IncompleteGraphifyOperationError(
            f"Graphify {receipt.operation.value} failed closed "
            f"({receipt.state.value}): {detail}{suffix}"
        )
    return receipt


def _bounded_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    """Retain enough path evidence to diagnose scope without unbounded exceptions."""
    return tuple(path[:160] for path in paths[:12])


def _language_tally(paths: tuple[str, ...]) -> tuple[tuple[str, int], ...]:
    """Per-extension totals over the FULL path set, never the display bound."""
    tally = Counter(PurePosixPath(path).suffix or PurePosixPath(path).name for path in paths)
    return tuple(sorted(tally.items()))
