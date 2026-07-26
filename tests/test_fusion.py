"""Tests for `kb_setup.fusion` — reciprocal rank fusion (knowledge-base#12, P2).

The load-bearing pair here is
:func:`test_consensus_beats_a_single_strong_vote` and its control arm
:func:`test_a_single_list_lets_the_strong_vote_win`. The first is the entire
written justification for RRF, and the shape of that claim — "this proves the
feature does the work" — is exactly the shape that shipped a tautological test in
PR #33 (`feedback_test_right_answer_wrong_reason`). So the feature is disabled —
the second list removed, which is the realistic regression — and the assertion
must flip. It does.
"""

from __future__ import annotations

import pytest
from kb_setup import fusion

#: A document ranked first by one retriever and unseen by the other.
_LONER = "one-strong-vote.md"

#: A document ranked mid-list by BOTH retrievers. Deliberately below `_LONER` in
#: the first list, so it can only win on consensus.
_AGREED = "two-middling-votes.md"


def _lists() -> tuple[list[str], list[str]]:
    """One retriever putting `_LONER` first, another that never saw it."""
    first = [_LONER, "a.md", "b.md", _AGREED]
    second = ["c.md", "d.md", _AGREED]
    return first, second


def test_consensus_beats_a_single_strong_vote() -> None:
    """The claim RRF is adopted for: agreement outweighs one rank-1 vote.

    `_AGREED` is 4th in the first list and 3rd in the second; `_LONER` is 1st in
    the first and absent from the second. Two middling votes must win.
    """
    first, second = _lists()
    assert fusion.fuse([first, second])[0] == _AGREED


def test_a_single_list_lets_the_strong_vote_win() -> None:
    """CONTROL ARM for the above: with the second list gone, rank 1 wins.

    Without this, the test above would pass for a `fuse` that simply returned
    whatever sorted first for an unrelated reason. Removing the second input is
    the realistic regression — a fused retriever whose second retriever silently
    returned nothing — and it must flip the answer.
    """
    first, _ = _lists()
    assert fusion.fuse([first])[0] == _LONER


def test_the_smoothing_constant_is_what_makes_consensus_win() -> None:
    """Shrink the constant and the single strong vote wins again — so k is load-bearing.

    At k=60 the rank-1-vs-rank-4 gap (1/61 vs 1/64) is small next to the gain
    from a second list. At k=1 that gap dominates (1/2 vs 1/5), so the same
    inputs invert. This is the second control arm on the claim above — it names
    the mechanism rather than just the outcome.
    """
    first, second = _lists()
    assert fusion.fuse([first, second], k=60)[0] == _AGREED
    assert fusion.fuse([first, second], k=1)[0] == _LONER


def test_a_repeated_document_votes_once_per_list() -> None:
    """A list that split one document across several nodes does not vote twice.

    Counting each repeat would let a single retriever manufacture consensus with
    itself, which is the property fusion exists to measure across retrievers.
    """
    repeated = fusion.fuse([["x.md", "x.md", "x.md", _AGREED], ["y.md", _AGREED]])
    assert repeated[0] == _AGREED


def test_a_repeat_takes_its_first_rank() -> None:
    """CONTROL ARM for the above: the dedupe keeps the BEST rank, not the last.

    If it kept the last occurrence, `early.md` would score 1/63 instead of 1/61
    and lose to `mid.md` — so this pins which of the two dedupe directions is
    implemented, not merely that one is.
    """
    assert fusion.fuse([["early.md", "mid.md", "early.md"]]) == ["early.md", "mid.md"]


def test_the_fused_list_is_the_union_and_nothing_more() -> None:
    """No padding: an item absent from every input never appears.

    Load-bearing for `evals._arm_defect`'s silent-corpus check — a fused
    retriever that invented candidates could never return an empty result, and a
    check that cannot fire is not a check.
    """
    assert sorted(fusion.fuse([["a.md"], ["b.md"]])) == ["a.md", "b.md"]


def test_fusing_nothing_returns_nothing() -> None:
    """Both the no-lists and the all-empty-lists cases stay empty."""
    assert fusion.fuse([]) == []
    assert fusion.fuse([[], []]) == []


def test_ties_are_broken_by_first_appearance_and_are_stable() -> None:
    """Two runs over one input must agree, or a delta between arms is noise."""
    lists = [["a.md", "b.md"], ["b.md", "a.md"]]
    once, twice = fusion.fuse(lists), fusion.fuse(lists)
    assert once == twice == ["a.md", "b.md"]


@pytest.mark.parametrize("k", [0, -1, -61])
def test_a_k_below_one_is_rejected(k: int) -> None:
    """A nonsense ordering must not be returned silently.

    k=-1 divides by zero at rank 1; every negative k inverts the ranking for the
    ranks below its magnitude. Both are worse than an exception, because both
    return a plausible-looking list.
    """
    with pytest.raises(ValueError, match="k >= 1"):
        fusion.fuse([["a.md"]], k=k)


def test_the_default_k_is_the_published_constant() -> None:
    """Pinned so a "small tweak" to a fitted value is a visible diff.

    60 is Cormack et al.'s value and the one Cerebras report. The module
    docstring records why nothing here is tuned against the golden set.
    """
    assert fusion.RRF_K == 60
