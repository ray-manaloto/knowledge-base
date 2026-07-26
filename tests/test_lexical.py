"""Tests for the BM25/IDF lexical scorer (kb_setup.lexical, knowledge-base#12 P1).

The load-bearing test here is not "search returns something ranked" — any
scorer does that. It is :func:`test_a_term_in_every_document_cannot_decide_the_ranking`:
the whole justification for IDF over plain term-frequency is that a term
appearing everywhere carries no evidence, and that is the property KB #12 opens
with (the query "distillation" pulling back `distill.py`).

That test's first version was TAUTOLOGICAL — it passed with `idf()` stubbed to a
constant, because BM25's k1 saturation was doing the work the test credited to
IDF. It is written up in full there, because the lesson generalises past this
file: a test that asserts the right outcome for the wrong reason is
indistinguishable from a passing one until somebody removes the feature and
watches it stay green.

Two more are here because they guard a check rather than a feature:

* :func:`test_a_query_matching_nothing_returns_nothing` — `search` must be ABLE
  to return an empty list, or `evals._arm_defect`'s silent-corpus check becomes
  a check that can only pass.
* :func:`test_a_document_with_no_indexable_text_is_not_counted` — an empty
  document counted in `size` would inflate every IDF by a document that can
  never contribute.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import lexical


def _node(
    node_id: str, label: str, *, rationale: str = "", source: str = "a.md"
) -> dict[str, object]:
    node: dict[str, object] = {"id": node_id, "label": label, "source_file": source}
    if rationale:
        node["rationale"] = rationale
    return node


def _sources(hits: list[lexical.Hit]) -> list[str]:
    return [h.source_file for h in hits]


# --- what is indexed -------------------------------------------------------


def test_the_rationale_is_indexed_not_just_the_label() -> None:
    """A term that appears ONLY in the summary must still be findable.

    This is the P1 scope decision (`label` + `rationale`) expressed as a test:
    labels alone are the surface that already fails the natural phrasings, and
    the summary is where a natural wording has its best chance of overlapping.
    """
    index = lexical.build_index(
        [
            _node("a", "Lane fallback", rationale="announced substitution when a CLI is absent"),
            _node("b", "Something else", source="b.md"),
        ]
    )
    assert _sources(lexical.search(index, "substitution")) == ["a.md"]


def test_a_field_holding_the_literal_none_string_contributes_no_terms() -> None:
    """Missing optional fields arrive from graphify as the literal ``"None"``.

    Indexing it would make "none" a term shared by most of the corpus. Verified
    against the real graph, where `source_location`/`author`/`contributor` all
    carry it.
    """
    index = lexical.build_index([_node("a", "Real label", rationale="None")])
    assert lexical.search(index, "none") == []
    # Control arm: the same index DOES answer a term that is really present, so
    # the empty result above is an absence and not a broken index.
    assert _sources(lexical.search(index, "real")) == ["a.md"]


def test_a_document_with_no_indexable_text_is_not_counted() -> None:
    """An empty document must not enter the index, nor inflate ``size``."""
    index = lexical.build_index(
        [_node("a", "kept"), {"id": "b", "label": "", "source_file": "b.md"}]
    )
    assert index.size == 1


def test_only_label_and_rationale_are_indexed() -> None:
    """`source_file` and `community_name` are NOT indexed — see the module docstring.

    Both repeat near-identical text across every node of a document, which
    inflates those terms' document frequency and drags every IDF toward zero.
    """
    index = lexical.build_index(
        [
            {
                "id": "a",
                "label": "x",
                "source_file": "distinctiveword.md",
                "community_name": "othertoken",
            }
        ]
    )
    assert lexical.search(index, "distinctiveword") == []
    assert lexical.search(index, "othertoken") == []
    assert _sources(lexical.search(index, "x")) == ["distinctiveword.md"]


# --- IDF: the reason this module exists ------------------------------------


def test_a_term_in_every_document_cannot_decide_the_ranking() -> None:
    """THE test. A term present everywhere must not outrank a term that discriminates.

    This is the `distill.py`-matches-"distillation" failure from
    knowledge-base#12, reduced to its smallest form: `common` appears in 19 of 20
    documents, `rare` in one, and a query for both must rank the `rare` document
    first.

    THE FIXTURE IS SHAPED THE WAY IT IS SO THAT **IDF** DECIDES IT, and that took
    two attempts. The first version gave the decoy the query's rare term as well
    and let it repeat `common` four times, on the theory that raw term-frequency
    would carry the decoy. It did not: BM25's k1 saturation already discounts the
    repetition, so the test passed with `idf()` stubbed to a constant — a
    tautological test that would have shipped as proof of a property it never
    exercised. Control-armed 2026-07-26 by replacing `Index.idf` with
    `lambda: 1.0` and re-running:

        with IDF     -> ['target.md', 'decoy.md', ...]   (assertion holds)
        without IDF  -> ['decoy.md', 'target.md', ...]   (assertion fails)

    What makes it decide is that the two candidates are otherwise IDENTICAL —
    same length, same term frequency, one query term each — so the only thing
    left to separate them is how much each term is worth. Measured here:
    idf(common)=0.074 against idf(rare)=2.639. Without that weighting the two
    tie and the order falls to graph position, which puts the decoy first.
    """
    nodes = [
        _node("decoy", "common", source="decoy.md"),
        _node("target", "rare", source="target.md"),
        *[_node(f"f{i}", "common", source=f"f{i}.md") for i in range(18)],
    ]
    index = lexical.build_index(nodes)
    assert index.document_frequency["common"] > index.document_frequency["rare"]
    assert _sources(lexical.search(index, "common rare"))[0] == "target.md"


def test_idf_never_goes_negative_for_a_term_in_most_documents() -> None:
    """The BM25+ ``1 +`` floor. A ubiquitous term is worth zero, never less.

    Without it the classic formula goes negative past 50% document frequency, so
    a common term could SUBTRACT from a score and rank a matching document below
    one that matched nothing.
    """
    index = lexical.build_index([_node(str(i), "everywhere", source=f"{i}.md") for i in range(10)])
    assert index.idf("everywhere") >= 0


def test_a_rarer_term_outweighs_a_commoner_one() -> None:
    index = lexical.build_index(
        [
            _node("a", "common rare", source="a.md"),
            *[_node(str(i), "common", source=f"{i}.md") for i in range(9)],
        ]
    )
    assert index.idf("rare") > index.idf("common")


def test_length_normalisation_does_not_let_padding_win() -> None:
    """A long document must not outrank a short one purely for repeating a term.

    Load-bearing on the real corpus: 1,177 of 2,105 nodes carry a `rationale` and
    928 do not, so document length varies ~3x and an unnormalised score would
    systematically favour the longer half.
    """
    index = lexical.build_index(
        [
            _node("short", "signal", source="short.md"),
            _node("padded", "signal", rationale=" ".join(["filler"] * 60), source="padded.md"),
        ]
    )
    assert _sources(lexical.search(index, "signal"))[0] == "short.md"


# --- the empty result must stay reachable ----------------------------------


def test_a_query_matching_nothing_returns_nothing() -> None:
    """`search` MUST be able to return []. See the module docstring.

    `evals._arm_defect` fails an arm whose retriever returned nothing. If this
    scorer padded its output with zero-scoring documents, that check could never
    fire for the P1 arm — the can-only-pass shape.
    """
    index = lexical.build_index([_node("a", "alpha beta")])
    assert lexical.search(index, "zzzznomatch") == []


def test_a_query_with_no_tokens_returns_nothing() -> None:
    index = lexical.build_index([_node("a", "alpha")])
    assert lexical.search(index, "!!! ???") == []


def test_zero_scoring_documents_are_excluded_from_the_ranking() -> None:
    index = lexical.build_index([_node("a", "alpha"), _node("b", "beta", source="b.md")])
    assert _sources(lexical.search(index, "alpha")) == ["a.md"]


# --- determinism -----------------------------------------------------------


def test_ties_break_by_graph_position_so_two_runs_agree() -> None:
    """Identical documents must come back in a stable order.

    A comparison that moves when nothing changed is not a measurement, and this
    scorer's whole job is to produce a number the golden set can subtract.
    """
    nodes = [_node(str(i), "same text", source=f"{i}.md") for i in range(5)]
    index = lexical.build_index(nodes)
    first = _sources(lexical.search(index, "same text"))
    assert first == [f"{i}.md" for i in range(5)]
    assert first == _sources(lexical.search(index, "same text"))


# --- loading from disk -----------------------------------------------------


def _write(path: Path, nodes: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
    return path


def test_loading_a_graph_builds_an_index_over_its_nodes(tmp_path: Path) -> None:
    graph = _write(tmp_path / "g.json", [_node("a", "alpha"), _node("b", "beta", source="b.md")])
    assert lexical.load_index(graph).size == 2


def test_loading_a_graph_with_no_indexable_node_refuses(tmp_path: Path) -> None:
    """An index that answers nothing looks exactly like broken retrieval.

    Same fail-loudly rule as `prose.derive` refusing to write an empty graph.
    """
    graph = _write(tmp_path / "g.json", [{"id": "a", "label": "", "source_file": "a.md"}])
    with pytest.raises(ValueError, match="EMPTY lexical index"):
        lexical.load_index(graph)


def test_loading_malformed_json_raises_rather_than_returning_an_empty_index(tmp_path: Path) -> None:
    """The failure the eval arm's real ``rc`` reports. It has to be reachable."""
    graph = tmp_path / "g.json"
    graph.write_text("not a graph", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        lexical.load_index(graph)


def test_tokenize_lowercases_and_splits_on_non_alphanumerics() -> None:
    assert lexical.tokenize("Claude-Code's /clear (v2.1)") == [
        "claude",
        "code",
        "s",
        "clear",
        "v2",
        "1",
    ]
