# Copyright (c) 2026 Raymond Manaloto
"""Behavioral tests for the reusable Graphify operation receipt."""

from __future__ import annotations

import pytest
from kb_setup.graphify_health import (
    APPROVED_METADATA_ZERO_NODE_WARNING,
    GraphifyEvidence,
    GraphifyOperation,
    GraphifyState,
    IncompleteGraphifyOperationError,
    SourceCoveragePolicy,
    assess,
    require_complete,
)


def test_clean_query_is_complete() -> None:
    receipt = assess(GraphifyOperation.QUERY, GraphifyEvidence(observed=True, stdout="answer\n"))
    assert receipt.state is GraphifyState.COMPLETE
    assert receipt.reasons == ()


@pytest.mark.parametrize("stderr", ["SyntaxWarning: invalid escape sequence", "coverage reduced"])
def test_success_with_stderr_is_incomplete(stderr: str) -> None:
    receipt = assess(
        GraphifyOperation.QUERY,
        GraphifyEvidence(observed=True, stdout="answer\n", stderr=stderr),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "stderr" in receipt.reasons


def test_fully_accounted_stderr_is_retained_with_classification() -> None:
    warning = "upstream zero-node warning"
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr=warning,
            residual_stderr="",
            approved_classifications=(APPROVED_METADATA_ZERO_NODE_WARNING,),
        ),
    )
    assert receipt.state is GraphifyState.COMPLETE
    assert receipt.stderr == warning
    assert receipt.approved_classifications == (APPROVED_METADATA_ZERO_NODE_WARNING,)


def test_classification_token_alone_never_approves_stderr() -> None:
    """The token records WHY something was approved; it is not itself approval.

    Before #328 this shape passed: one recognised token approved everything the
    subprocess printed, so a second, unrelated warning rode in on the first one's
    approval. Approval is now per warning, and an empty residual is the only
    thing that clears stderr.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr="upstream zero-node warning\nan entirely different warning",
            approved_classifications=(APPROVED_METADATA_ZERO_NODE_WARNING,),
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "stderr" in receipt.reasons


def test_residual_stderr_blocks_and_is_named_in_the_failure() -> None:
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr="  warning: reviewed\n  warning: NOT reviewed",
            residual_stderr="  warning: NOT reviewed",
            approved_classifications=(APPROVED_METADATA_ZERO_NODE_WARNING,),
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    with pytest.raises(IncompleteGraphifyOperationError) as raised:
        require_complete(receipt)
    # The reason is one word; the message has to name WHICH line blocked, or a
    # reader has to re-run the build to find out.
    assert "NOT reviewed" in str(raised.value)
    assert "warning: reviewed" not in str(raised.value)


def test_extract_refuses_unclassified_zero_node_and_partial_coverage() -> None:
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            detected_sources=100,
            extracted_sources=45,
            unclassified_files=54,
            zero_node_sources=11,
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert set(receipt.reasons) >= {
        "source-coverage-partial",
        "unclassified-files",
        "zero-node-sources",
    }


def test_query_partial_count_banner_is_incomplete() -> None:
    receipt = assess(
        GraphifyOperation.QUERY,
        GraphifyEvidence(observed=True, stdout="PARTIAL: 278/562 nodes\n"),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "partial-result" in receipt.reasons


def test_coverage_policy_allows_declared_optional_gaps_only() -> None:
    policy = SourceCoveragePolicy(
        required_paths=("mise.toml", "Dockerfile"),
        optional_unclassified_paths=("CHANGELOG.legacy",),
        optional_zero_node_paths=("empty.json",),
    )
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            coverage_policy=policy,
            unclassified_paths=("CHANGELOG.legacy",),
            zero_node_paths=("empty.json",),
        ),
    )
    assert receipt.state is GraphifyState.COMPLETE


def test_coverage_policy_allows_only_declared_ignored_paths() -> None:
    reviewed = assess(
        GraphifyOperation.DETECT,
        GraphifyEvidence(
            observed=True,
            ignored_paths=("docs/superpowers",),
            coverage_policy=SourceCoveragePolicy(
                optional_ignored_paths=("docs/superpowers",),
            ),
        ),
    )
    changed = assess(
        GraphifyOperation.DETECT,
        GraphifyEvidence(
            observed=True,
            ignored_paths=("docs/superpowers", "new-ignored"),
            coverage_policy=SourceCoveragePolicy(
                optional_ignored_paths=("docs/superpowers",),
            ),
        ),
    )

    assert reviewed.state is GraphifyState.COMPLETE
    assert changed.state is GraphifyState.INCOMPLETE
    assert changed.reasons == ("ignored-paths",)


def test_required_ignored_path_is_never_allowlisted() -> None:
    receipt = assess(
        GraphifyOperation.DETECT,
        GraphifyEvidence(
            observed=True,
            ignored_paths=("mise.toml",),
            coverage_policy=SourceCoveragePolicy(
                required_paths=("mise.toml",),
                optional_ignored_paths=("mise.toml",),
            ),
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert receipt.reasons == ("required-source-ignored",)


def test_required_unsupported_source_is_never_silently_ignored() -> None:
    policy = SourceCoveragePolicy(required_paths=("mise.toml", "Dockerfile"))
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            coverage_policy=policy,
            unclassified_paths=("mise.toml", "Dockerfile"),
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "required-source-unclassified" in receipt.reasons


def test_receipt_retains_bounded_source_qualified_paths() -> None:
    paths = tuple(f"deep/path/{index}-{'x' * 200}.unknown" for index in range(30))
    receipt = assess(
        GraphifyOperation.DETECT,
        GraphifyEvidence(
            observed=True,
            source_name="hostile-source",
            unclassified_files=len(paths),
            unclassified_paths=paths,
        ),
    )

    assert receipt.source_name == "hostile-source"
    assert len(receipt.unclassified_paths) == 12
    assert all(len(path) <= 160 for path in receipt.unclassified_paths)


def test_deep_reflection_artifact_and_scope_expectations_fail_closed() -> None:
    receipt = assess(
        GraphifyOperation.BUILD,
        GraphifyEvidence(
            observed=True,
            mode="ast",
            deep_required=True,
            reflection_expected=True,
            reflection_produced=False,
            expected_artifacts=("graph.json", "wiki"),
            produced_artifacts=("graph.json",),
            expected_scope="corpus",
            observed_scope="study",
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert set(receipt.reasons) >= {
        "deep-extraction-missing",
        "reflection-missing",
        "artifacts-partial",
        "source-scope-mismatch",
    }


def test_nonzero_operation_is_failed_and_require_complete_raises() -> None:
    receipt = assess(GraphifyOperation.ARTIFACT, GraphifyEvidence(observed=True, returncode=2))
    assert receipt.state is GraphifyState.FAILED
    with pytest.raises(IncompleteGraphifyOperationError, match="artifact failed"):
        require_complete(receipt)


@pytest.mark.parametrize("operation", list(GraphifyOperation))
def test_missing_evidence_is_incomplete_for_every_operation(
    operation: GraphifyOperation,
) -> None:
    receipt = assess(operation)
    assert receipt.state is GraphifyState.INCOMPLETE
    assert receipt.reasons == ("evidence-missing",)


# The exact line `graphify-out/.build-failure.json` recorded on 2026-08-24: a
# real `kb-build` failed closed on nothing but Graphify's own routine
# node-pruning narration.
_PRUNE_NODE_LINE = "[graphify] Pruned 3 node(s) from 3 deleted or excluded source file(s)."
# The sibling Graphify prints for edges — same code path, no file count.
_PRUNE_EDGE_LINE = "[graphify] Pruned 5 edge(s) from deleted or excluded source file(s)."


@pytest.mark.parametrize(
    "stderr",
    [_PRUNE_NODE_LINE, _PRUNE_EDGE_LINE, f"{_PRUNE_NODE_LINE}\n{_PRUNE_EDGE_LINE}"],
    ids=["node-line", "edge-line", "both-lines"],
)
def test_known_graphify_prune_progress_is_not_unaccounted_stderr(stderr: str) -> None:
    """GREEN ARM: the observed benign line, alone, must not fail a build closed.

    This is the reproduction of the real 2026-08-24 `kb-build` failure: nothing
    was wrong, Graphify only narrated that a merge dropped nodes/edges for a
    deleted source file, and the old fail-closed rule could not tell that apart
    from a genuinely unaccounted warning. Reverting `_unaccounted_stderr`'s
    filtering makes this fail.
    """
    receipt = assess(GraphifyOperation.EXTRACT, GraphifyEvidence(observed=True, stderr=stderr))
    assert receipt.state is GraphifyState.COMPLETE
    assert receipt.reasons == ()
    require_complete(receipt)  # must not raise


def test_known_graphify_prune_progress_is_accounted_for_as_a_residual_too() -> None:
    """The same benign line reaches `_basic_reasons` via `residual_stderr` too.

    A real caller (`graphify_sdk.account_for_extract_stderr`) computes a
    residual after checking its OWN reviewed classes; when none of those match,
    the residual is the full stderr, unfiltered for Graphify's routine lines.
    This must still resolve to COMPLETE — the filtering lives in
    `graphify_health` regardless of which field carried the text.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(observed=True, stderr=_PRUNE_NODE_LINE, residual_stderr=_PRUNE_NODE_LINE),
    )
    assert receipt.state is GraphifyState.COMPLETE


def test_a_novel_line_still_blocks_alongside_the_benign_one() -> None:
    """RED ARM: recognising one benign line is not license for the rest.

    The failure message must name the line that actually blocked, not bury it
    behind the benign narration.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr=f"{_PRUNE_NODE_LINE}\nWARNING: something genuinely unreviewed",
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "stderr" in receipt.reasons
    with pytest.raises(IncompleteGraphifyOperationError) as raised:
        require_complete(receipt)
    assert "something genuinely unreviewed" in str(raised.value)
    assert "Pruned 3 node(s)" not in str(raised.value)


def test_extra_text_on_the_same_line_as_the_benign_pattern_still_blocks() -> None:
    """RED ARM: the match is anchored full-line — trailing text is not laundered.

    A line that merely STARTS with Graphify's benign prefix but says more must
    not be waved through: that shape is exactly how a real problem would slip
    past a substring or prefix match.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(observed=True, stderr=f"{_PRUNE_NODE_LINE} also: 12 edges corrupted"),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "stderr" in receipt.reasons


def test_a_real_graphify_warning_sharing_the_prefix_still_blocks() -> None:
    """RED ARM: `[graphify] ` is not itself a signal.

    Graphify uses the same prefix for genuine `WARNING:` lines a few statements
    away from the benign prune line. Matching on the prefix alone would
    launder those through unread too.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr="[graphify] WARNING: dropped 2 out-of-scope node(s) during merge",
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "stderr" in receipt.reasons


# The exact line a real `kb-build` failed closed on, 2026-08-27, once #397's
# classifier widening let detection through and extraction was reached for the
# first time. Verbatim from the traceback, not reconstructed from the f-string.
_REPLACED_NODE_LINE = "[graphify] Replaced 1555 node(s) from re-extracted source file(s)."


def test_known_graphify_replace_progress_is_not_unaccounted_stderr() -> None:
    """GREEN ARM: the `Replaced` sibling of the prune narration is benign.

    Verified against the vendor source rather than its wording
    (`graphify/build.py:1724`): a node is dropped only when its `source_file`
    appears in the NEW chunks, and those chunks are merged in the same build,
    so no source is removed without a replacement. Reverting the `Replaced`
    alternative in `_ROUTINE_MERGE_PROGRESS` makes this fail.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(observed=True, stderr=_REPLACED_NODE_LINE),
    )
    assert receipt.state is GraphifyState.COMPLETE
    assert receipt.reasons == ()
    require_complete(receipt)  # must not raise


def test_the_replace_line_is_anchored_like_its_prune_sibling() -> None:
    r"""RED ARM: trailing text on the same line is NOT approved by association.

    The whole reason the pattern is anchored `\A…\Z` is that Graphify reuses
    the `[graphify] ` prefix for genuine warnings a few statements away.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr=f"{_REPLACED_NODE_LINE} WARNING: 900 of them had no replacement",
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "stderr" in receipt.reasons


def test_a_replace_line_for_edges_is_not_silently_approved() -> None:
    """A pattern must not be drawn wider than what was observed.

    Graphify prints no `Replaced N edge(s)` line at all — only the node one —
    so approving an edge spelling would approve something never seen.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr="[graphify] Replaced 12 edge(s) from re-extracted source file(s).",
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE


# The exact line a real `mise run kb-build` failed closed on, 2026-09-03, on the
# OpenSymphony source — whose extract had SUCCEEDED (11,004 nodes, 34,665 edges
# written) immediately above it in the same log. Verbatim from the traceback,
# em dash included, not reconstructed from the f-string.
_ALREADY_CLEAN_LINE = (
    "[graphify] 3 source file(s) deleted or excluded since last run — "
    "no matching nodes or edges in graph, already clean."
)

#: Graphify's SUSPICIOUS sibling, from the `if` branch immediately above the
#: benign `else` (`graphify/build.py:1983-1991`, READ 2026-09-03). Prune entries
#: that matched nothing usually mean the effective root is wrong, so this one
#: must keep failing the build closed.
_PRUNE_MATCHED_NOTHING_LINE = (
    "[graphify] WARNING: 3 prune source(s) matched no nodes or edges — nothing "
    "was removed. Prune entry 'a/b.py' does not correspond to any stored "
    "source_file (e.g. 'src/a/b.py'). If these files should have been pruned, "
    "pass root= to build_merge so absolute paths relativize to the graph's "
    "source_file keys. (#2446)"
)


def test_the_already_clean_line_is_not_unaccounted_stderr() -> None:
    """GREEN ARM: the zero-count sibling of the prune narration is benign.

    Verified against the vendor source rather than its wording
    (`graphify/build.py:1969-1997`): this is the `else` of a branch on
    `(prune_set or prune_abs) and not _matched_prune_entries`, so it is reached
    only when the prune entries DID match or there were none. Reverting the
    third alternative in `_ROUTINE_MERGE_PROGRESS` makes this fail.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(observed=True, stderr=_ALREADY_CLEAN_LINE),
    )
    assert receipt.state is GraphifyState.COMPLETE
    assert receipt.reasons == ()
    require_complete(receipt)  # must not raise


def test_the_prune_matched_nothing_warning_still_refuses() -> None:
    r"""RED ARM, and the control arm for the addition above.

    These two lines are the two branches of ONE `if`/`else` in Graphify. If a
    pattern written for the benign branch also swallowed the suspicious one,
    approving it would hide a wrong-root prune — exactly the failure #2446 was
    filed for.

    WHAT ACTUALLY REFUSES IT IS THE ANCHOR, NOT THE WORDING, and the difference
    was found by a mutation that SURVIVED. The enclosing pattern ends `\\.\\Z`
    and this line ends `(#2446)`, so no widening of the alternation alone can
    make it match — a mutation that only broadens the wording is inert here and
    proves nothing. The arm that does kill this test
    (`.agent/kb/arms/already-clean-narration.toml::pattern-widened-and-unanchored`)
    widens the alternation AND drops the end anchor, which is the sloppy pattern
    a person would really write. Stated because the first version of this
    docstring credited the wording, which would have disarmed the next reader.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(observed=True, stderr=_PRUNE_MATCHED_NOTHING_LINE),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "stderr" in receipt.reasons


def test_the_already_clean_line_is_anchored_like_its_siblings() -> None:
    r"""RED ARM: trailing text on the same line is NOT approved by association.

    Same reason the `Replaced` and `Pruned` patterns are anchored `\A…\Z`:
    Graphify reuses the `[graphify] ` prefix for genuine warnings a few
    statements away in the same function.
    """
    receipt = assess(
        GraphifyOperation.EXTRACT,
        GraphifyEvidence(
            observed=True,
            stderr=f"{_ALREADY_CLEAN_LINE} WARNING: the root may be wrong",
        ),
    )
    assert receipt.state is GraphifyState.INCOMPLETE
    assert "stderr" in receipt.reasons
