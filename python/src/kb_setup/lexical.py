"""BM25/IDF lexical retrieval over the prose graph (knowledge-base#12, P1).

WHY THIS EXISTS. P0 fixed *which nodes compete* — `graphify query` truncates at
a token budget before the caller sees a line, so the 126,228 code-AST nodes
crowded prose out entirely, and dropping them (`kb_setup.prose`) moved
natural-phrasing recall from 1/8 pairs to 3/8. What P0 did NOT fix is *how the
survivors are ordered*: `graphify query` applies **no relevance score at all**.
Its printed order is seed-then-BFS, so within the prose corpus a node's rank is
a function of graph topology, not of the question. Five of eight topics are
still retrievable only when the query echoes the document's own label text.

This module is the missing scorer. It ranks the prose nodes by BM25 over
``label`` + ``rationale`` and returns them best-first.

WHY IDF IS THE POINT, not an implementation detail. The failure KB #12 opens
with is a *false neighbour*: the query "distillation" pulled back `distill.py`.
A scorer that merely counts overlapping terms cannot tell a term that
discriminates from one that does not — "the", "how", "code" appear in most
documents and carry no evidence, while "reciprocal", "sshd", "xhigh" each
nominate a handful. IDF is exactly that weighting, and it is why term-frequency
alone was never worth shipping.

WHY ``label`` + ``rationale`` AND NOTHING ELSE (scope locked 2026-07-26). Those
two are what KB #12 names ("node labels + summaries"). ``rationale`` is the
extractor's one-line summary and is where a *natural* phrasing has its best
chance of overlapping — it is prose about the node, not the node's title.
``source_file`` and ``community_name`` were considered and rejected: both repeat
near-identical boilerplate across every node of a document, which inflates the
document frequency of their terms, drags every IDF toward zero, and dilutes the
one signal this module exists to add.

WHY IT IS A THIRD ARM AND NOT A REPLACEMENT FOR ``--prose``. The golden set runs
``unscoped`` / ``prose`` / ``prose+idf`` side by side, so P1's delta is
attributable to P1 alone rather than to P1-plus-P0 (`evals.Arm`). Collapsing the
winner into ``--prose`` is a follow-up, after P2, not part of this.

WHAT ``returned == 0`` MEANS HERE, and why the check still bites. The engine
fails any arm whose retriever returns nothing (`evals._arm_defect`) — a corpus
that resolves and knows nothing. That check is only worth keeping if this
retriever can actually produce it, so :func:`search` returns **only nodes that
score above zero**, never the whole corpus padded with zeros. A real question
against 2,553 documents shares at least one term with something; zero results
therefore means the index or the tokenizer is broken, which is precisely the
defect the check is for. Returning every node ranked would have made the check
unfailable — the can-only-pass shape.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

#: The node fields that are indexed. See the module docstring — this tuple is
#: the scope decision, so it is stated once, here, and read by both the indexer
#: and its tests.
INDEXED_FIELDS = ("label", "rationale")

#: BM25 term-frequency saturation. The standard 1.2: past a few occurrences of a
#: term, more occurrences stop adding evidence. Our documents are short (a label
#: plus a one-line summary, ~15-50 tokens), so saturation rarely binds — it is
#: kept at the literature default rather than tuned, because tuning a constant
#: against the same golden set the change is measured on is how a harness starts
#: grading itself.
K1 = 1.2

#: BM25 length normalisation. The standard 0.75. It matters here: 1,309 of 2,553
#: nodes carry a `rationale` and 1,244 do not, so document length varies by ~3x
#: and an unnormalised score would systematically favour the longer half.
#: Re-derived 2026-08-02 against `graph-prose.json`; the previous figures
#: (1,177 of 2,105) were measured on an earlier build and had gone stale.
B = 0.75

#: Tokens are runs of letters and digits, lowercased. Deliberately NOT a
#: stemmer and NOT a stopword list:
#:
#: * No stemmer — it would be a second, unmeasured change riding along inside a
#:   change whose whole purpose is an attributable delta.
#: * No stopword list — IDF already demotes a term that appears everywhere, and
#:   it does so from THIS corpus rather than from a general-English list that was
#:   never fitted to it. A hand-written stopword list would also be a bound of
#:   exactly the kind that turns a miss into an unreachable
#:   (`probes-need-a-control-arm.md` rule 3).
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase, then split into alphanumeric runs. Order preserved."""
    return _TOKEN.findall(text.lower())


def node_text(node: dict[str, object]) -> str:
    """The indexed text of one node: its :data:`INDEXED_FIELDS`, space-joined.

    A field that is missing, empty, or the string ``"None"`` contributes
    nothing. That last case is not defensive padding: this graph really does
    carry the literal four characters ``None`` in optional string fields
    (`source_location`, `author`, `contributor` all show it), because the
    extractor stringified a Python ``None``. Indexing it would make "none" a
    term shared by most of the corpus.
    """
    parts = []
    for field in INDEXED_FIELDS:
        value = node.get(field)
        if isinstance(value, str) and value and value != "None":
            parts.append(value)
    return " ".join(parts)


@dataclass(frozen=True)
class Document:
    """One indexed node: what it is called, where it came from, its terms."""

    node_id: str
    label: str
    source_file: str
    terms: Counter[str]
    length: int


@dataclass(frozen=True)
class Index:
    """A BM25 index over the prose graph.

    Built once per process and reused across queries — the eval runs 18 queries
    against it, and rebuilding per query would make the arm's wall clock a
    measurement of JSON parsing.
    """

    documents: tuple[Document, ...]
    #: Document frequency: how many documents contain each term at least once.
    document_frequency: dict[str, int]
    average_length: float

    @property
    def size(self) -> int:
        """How many documents are indexed."""
        return len(self.documents)

    def idf(self, term: str) -> float:
        """Inverse document frequency, BM25+ variant — never negative.

        The classic Robertson/Sparck-Jones form goes NEGATIVE for a term present
        in more than half the corpus, which lets a common term *subtract* from a
        document's score and can rank a document below one that matched nothing.
        The ``1 +`` inside the log is the standard fix and floors the weight at
        zero, so a ubiquitous term is worth very little and never less than
        nothing.

        IT IS A FLOOR, NOT A CLAMP, AND THAT IS DELIBERATE. At ``df == size`` the
        smoothed formula returns a small positive number (0.047 over 10
        documents) rather than exactly 0, so in principle a query made only of
        everywhere-terms still orders documents — by length, via the ``b``
        normalisation. Returning a hard 0.0 there was tried and REVERTED
        (CodeRabbit, PR #33); measuring both sides is what settled it:

        * In this corpus the branch is unreachable. **No term reaches
          ``df == size``** — the commonest, "the", is 1,848 of 2,553 (72%). So
          the clamp buys nothing where the scorer actually runs.
        * It is actively harmful on a small corpus, because ``df == size`` is
          not a rare pathology there but the NORMAL case: in a one-document
          index every term is ubiquitous, so a clamp makes the document
          unfindable by any of its own words. Measured at n = 1, 2, 3 and 10,
          every query returned nothing, and four existing tests went red for
          that reason rather than a fixture reason.

        The real defect this exchange found was in the previous docstring, which
        promised "worth nothing" — a claim the arithmetic never made. Fixing the
        sentence is the correct repair; deviating from standard BM25 to satisfy
        a sentence is not.
        """
        df = self.document_frequency.get(term, 0)
        return math.log(1 + (self.size - df + 0.5) / (df + 0.5))

    def score(self, terms: Sequence[str], doc: Document) -> float:
        """BM25 score of one document against a tokenized query."""
        if not doc.length:
            return 0.0
        norm = K1 * (1 - B + B * doc.length / self.average_length)
        total = 0.0
        for term in set(terms):
            freq = doc.terms.get(term, 0)
            if freq:
                total += self.idf(term) * freq * (K1 + 1) / (freq + norm)
        return total


def build_index(nodes: Iterable[dict[str, object]]) -> Index:
    """Index every node that has indexable text.

    A node whose `label` and `rationale` are both empty is skipped rather than
    indexed as an empty document: it can never match anything, and counting it
    in ``size`` would inflate every IDF by a document that cannot contribute.
    """
    documents = []
    document_frequency: Counter[str] = Counter()
    for node in nodes:
        terms = Counter(tokenize(node_text(node)))
        if not terms:
            continue
        documents.append(
            Document(
                node_id=str(node.get("id", "")),
                label=str(node.get("label", "")),
                source_file=str(node.get("source_file", "")),
                terms=terms,
                length=sum(terms.values()),
            )
        )
        document_frequency.update(terms.keys())
    total = sum(d.length for d in documents)
    return Index(
        documents=tuple(documents),
        document_frequency=dict(document_frequency),
        average_length=total / len(documents) if documents else 0.0,
    )


def _schema_problem(graph: object) -> str:
    """What is wrong with this parsed JSON as a graph, or '' if nothing is.

    Returns a message rather than raising, so the caller owns the exception type.
    That matters here: the natural reading of a bad type is ``TypeError``, but
    every caller of :func:`load_index` catches ``OSError``/``ValueError`` — the
    CLI to print a diagnostic, `eval_cases._LexicalRetriever` to report its arm
    unreadable with a real ``rc``. A ``TypeError`` would sail past both and turn
    a defective corpus into a stack trace, which is the very failure this check
    was added to close.
    """
    if not isinstance(graph, dict):
        return f"its root is a {type(graph).__name__}, not an object"
    nodes = graph.get("nodes", [])
    if not isinstance(nodes, list):
        return f"its `nodes` is a {type(nodes).__name__}, not a list"
    if not all(isinstance(node, dict) for node in nodes):
        return "its `nodes` is not a list of objects"
    return ""


def load_index(graph_path: Path) -> Index:
    """Build an index from a graph file on disk.

    Raises:
        ValueError: if the file is not a graph — either structurally (the root is
            not an object, or ``nodes`` is not a list of objects) or in substance
            (it parses and holds no indexable node). An empty index answers every
            query with nothing, which is indistinguishable from the retrieval
            failure this module exists to fix — so it is refused loudly rather
            than served (same rule as `prose.derive`).

    THE SHAPE CHECKS EXIST TO KEEP THE FAILURE INSIDE THE DOCUMENTED CHANNEL
    (CodeRabbit, PR #33). Callers catch ``OSError`` and ``ValueError`` — the CLI
    to print a diagnostic, `eval_cases._LexicalRetriever` to report its arm
    unreadable with a real ``rc``. Valid JSON of the wrong shape used to raise
    ``AttributeError`` (a root array, a non-object node) or ``TypeError``
    (``{"nodes": null}``), all three of which sailed straight past those handlers
    — so a malformed graph crashed the eval run instead of being reported as a
    defective arm. Probed before fixing; all three now raise ``ValueError``.
    """
    with graph_path.open(encoding="utf-8") as fh:
        graph = json.load(fh)
    problem = _schema_problem(graph)
    if problem:
        raise ValueError(f"{graph_path} is not a graph — {problem}")
    nodes = graph.get("nodes", [])
    index = build_index(nodes)
    if not index.size:
        raise ValueError(
            f"{graph_path} produced an EMPTY lexical index — none of its "
            f"{len(nodes)} node(s) carry {' or '.join(INDEXED_FIELDS)} text. An "
            f"index that answers nothing looks exactly like broken retrieval."
        )
    return index


@dataclass(frozen=True)
class Hit:
    """One scored document, in rank order."""

    source_file: str
    node_id: str
    label: str
    score: float


def search(index: Index, query: str) -> list[Hit]:
    """Rank the indexed documents against ``query``, best first.

    Only documents scoring **above zero** are returned — see the module
    docstring: an empty result has to remain reachable or `evals._arm_defect`'s
    silent-corpus check becomes a check that can only pass.

    Ties are broken by the document's position in the graph file, which is
    stable across runs of the same corpus, so two invocations over one graph
    return the identical order. A comparison that moves when nothing changed is
    not a measurement.
    """
    terms = tokenize(query)
    if not terms:
        return []
    scored = [
        (score, position, doc)
        for position, doc in enumerate(index.documents)
        if (score := index.score(terms, doc)) > 0
    ]
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [
        Hit(source_file=doc.source_file, node_id=doc.node_id, label=doc.label, score=score)
        for score, _, doc in scored
    ]
