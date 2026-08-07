# Copyright (c) 2026 Raymond Manaloto
"""Reciprocal Rank Fusion over two or more ranked lists (knowledge-base#12, P2).

WHY THIS EXISTS. P0 fixed *which* nodes compete (`kb_setup.prose`) and P1 added
the missing relevance score (`kb_setup.lexical`). That left two orderings of the
same prose corpus — graphify's seed-then-BFS traversal order and BM25/IDF — and
KB #12's P2 asks whether combining them beats either alone. Cerebras' write-up
(registry #60) gives the formula, ``weight/(60+rank)``, and the reason to expect
a win: the smoothing constant makes *consensus* matter more than a single strong
vote.

WHY RRF FUSES A RANK WITH A SCORE, AND WHY THAT IS NOT AN OVERSIGHT. `graphify
query` exposes no relevance figure at all — only a printed order — so one input
is a bare rank while the other has BM25 scores attached. RRF is the right
instrument for exactly that asymmetry: it consumes **ranks only**, discarding
score magnitudes by construction, so two orderings on incomparable scales (or on
no scale) can still be combined. Nothing here needs the scores, and normalising
BM25 into a pseudo-probability so it could be added to graphify's non-score
would be the invented machinery, not this.

THE UNIT IS THE DOCUMENT, because node-level fusion is not available. Fusing at
node level would be the more faithful choice — it would leave each arm's output
shape untouched — but it needs a stable per-node key present in BOTH inputs, and
`graphify query` **truncates the label it prints** at roughly 250 characters
(observed 2026-07-27: ``…the core insight being you d [src=…``). A truncated
label is not a key, and no other node identifier appears on the line. So both
inputs are reduced to their ``source_file`` sequence, which is also the unit the
golden set declares its targets in.

That reduction dedupes, so it is fair to ask how much of any measured delta is
dedup rather than fusion. Measured, on the 8 natural-phrasing pairs, before this
module was written: **exactly none.** Deduping either input on its own changes
nothing (`prose` 3/8 -> 3/8; `prose+idf` 5/8 -> 5/8), because within the top 10
neither retriever repeats a document often enough to crowd another out. The
confound is real in principle and empirically zero here.

THE MEASURED RESULT IS NEGATIVE, AND THAT IS THE DELIVERABLE. On this corpus
fusing these two inputs scores **4 of 8** natural pairs against `prose+idf`'s
**5 of 8**. It is not noise and not a tuning miss — the arithmetic makes it
structural:

* graphify returns only **7-12 distinct documents** (25 nodes under its
  ~2000-token budget), while the lexical ranking returns ~75. Every document in
  the short list therefore earns a contribution of ~1/61 to ~1/72 — all of them
  effectively "top" by RRF's reckoning.
* So any document in graphify's ~10 *and anywhere at all* in the lexical ~75
  outranks a document with one contribution, however strong:
  ``1/61 + 1/135 = 0.0238`` beats ``1/63 = 0.0159``.
* With one short list and one long one, RRF's consensus term degenerates into
  **membership in the short list** — and that short list is an unranked
  traversal, which P0 and P1 both measured as carrying no relevance signal.
  `delegate-unavailable` shows it exactly: lexical rank 3, absent from
  graphify's 11, fused rank 13, with 10 of the 10 documents ahead of it present
  in both lists.

Consensus itself does work. RRF won `many-agents-one-repo`, a topic **neither**
input scored (graphify 12, lexical 36 -> fused 10) — the smoothing constant
doing precisely what Cerebras described. It is simply outweighed: +1 from
consensus, -2 from short-list dominance, net -1.

WHY NO WEIGHT IS TUNED. The formula's ``weight`` term is the obvious lever —
down-weighting graphify would reverse the two losses. It is deliberately left at
1 for every input. Any other value would be fitted to the same 8 pairs the
change is then measured on, with no established noise floor, which is the reason
`lexical.K1` sits at the literature default too. The honest reading of this
measurement is not "pick a better weight" but "RRF wants two comparable
rankings, and we still have one ranking plus a traversal" — so it becomes worth
revisiting when P3 (reranker) or P5 (embeddings) supplies a genuine second
scorer.

WHAT AN EMPTY RESULT MEANS. The fused list is the union of its inputs and is
never padded, so when every input comes back empty so does this — which keeps
`evals._arm_defect`'s silent-corpus check able to fire (see `lexical.search`,
which holds the same property for the same reason).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

#: RRF's smoothing constant, from Cormack et al. and the value Cerebras report.
#: It is what makes the fusion consensus-seeking rather than rank-1-seeking: at
#: k=60 the gap between rank 1 and rank 10 (1/61 vs 1/70) is far smaller than the
#: gain from appearing in a second list at all, so two middling votes beat one
#: strong one. Left at the published default — see the module docstring on why no
#: constant here is tuned against the golden set.
RRF_K = 60


def fuse(rankings: Sequence[Sequence[str]], *, k: int = RRF_K) -> list[str]:
    """Combine ranked lists into one, best first, by reciprocal rank fusion.

    Each item scores ``sum(1 / (k + rank))`` over the lists it appears in, where
    ``rank`` is 1-based. Items are returned in descending score order.

    Args:
        rankings: The lists to fuse, each already in its own best-first order.
            Ranks are the only thing read from them; any score the caller may
            have had is discarded by design (see the module docstring).
        k: The smoothing constant. See :data:`RRF_K`.

    Returns:
        Every item that appeared in at least one input, ranked. Ties are broken
        by first appearance across the inputs in order, so fusing the same lists
        twice returns the identical sequence — a comparison that moves when
        nothing changed is not a measurement.

    Raises:
        ValueError: if ``k < 1``. At ``k = 0`` a rank-1 item would still score,
            but ``k = -1`` divides by zero on it, and every negative ``k``
            inverts the ranking for the ranks below ``-k``. Rejecting the whole
            range keeps a nonsense ordering from being returned silently.

    A repeated item takes its FIRST rank within a list and contributes once for
    that list. Counting it again would let one list vote twice for the document
    it happens to have split across several nodes.
    """
    if k < 1:
        raise ValueError(f"RRF needs k >= 1, got {k}")
    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    for ranking in rankings:
        # `dict.fromkeys` is the dedupe: it keeps first appearance, in order.
        for rank, item in enumerate(dict.fromkeys(ranking), start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
            first_seen.setdefault(item, len(first_seen))
    return sorted(scores, key=lambda item: (-scores[item], first_seen[item]))
