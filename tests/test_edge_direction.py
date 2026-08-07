# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.edge_direction`.

Every HARD check here has ZERO occurrences in the committed corpus except the one
real `contrasts_with` defect, so a test that only fed it real chunks would pass
while the checks did nothing. Each hard check therefore gets a synthetic FAIL
fixture AND a near-miss PASS fixture — the near-miss is the one that matters,
because it is what distinguishes a check from a `return []`.
"""

from __future__ import annotations

from kb_setup import edge_direction as ed


def _edge(source: str, target: str, relation: str = "part_of") -> dict[str, object]:
    return {
        "source": source,
        "target": target,
        "relation": relation,
        "confidence": "EXTRACTED",
        "confidence_score": 1,
        "source_file": "x.md",
        "weight": 1,
    }


def _chunk(*edges: dict[str, object]) -> dict[str, object]:
    return {"nodes": [], "edges": list(edges), "hyperedges": []}


def test_a_self_edge_is_a_hard_failure() -> None:
    hard, _ = ed.check(_chunk(_edge("a", "a")))
    assert any("SELF-EDGE" in h for h in hard)


def test_a_distinct_pair_is_not_a_self_edge() -> None:
    hard, _ = ed.check(_chunk(_edge("a", "b")))
    assert not hard


def test_a_two_cycle_in_part_of_is_caught() -> None:
    hard, _ = ed.check(_chunk(_edge("a", "b"), _edge("b", "a")))
    assert any("CYCLE" in h for h in hard)


def test_a_longer_part_of_cycle_is_caught() -> None:
    hard, _ = ed.check(_chunk(_edge("a", "b"), _edge("b", "c"), _edge("c", "a")))
    assert any("CYCLE" in h for h in hard)


def test_a_diamond_is_not_a_cycle() -> None:
    """The near-miss: two paths to one container is normal, not circular.

    A checker flagging any re-visited node would fail this, and the shape is
    everywhere in a real chunk — many members, one doc node.
    """
    hard, _ = ed.check(_chunk(_edge("a", "b"), _edge("a", "c"), _edge("b", "d"), _edge("c", "d")))
    assert not hard


def test_a_cycle_across_different_relations_is_not_flagged() -> None:
    """`a part_of b` plus `b requires a` contradicts neither relation."""
    hard, _ = ed.check(_chunk(_edge("a", "b", "part_of"), _edge("b", "a", "requires")))
    assert not hard


def test_requires_cycles_are_caught_too() -> None:
    hard, _ = ed.check(_chunk(_edge("a", "b", "requires"), _edge("b", "a", "requires")))
    assert any("CYCLE" in h and "requires" in h for h in hard)


def test_contrasts_with_in_both_directions_is_caught() -> None:
    hard, _ = ed.check(_chunk(_edge("a", "b", "contrasts_with"), _edge("b", "a", "contrasts_with")))
    assert any("BOTH directions" in h for h in hard)


def test_a_bidirectional_pair_is_reported_once_not_twice() -> None:
    hard, _ = ed.check(_chunk(_edge("a", "b", "contrasts_with"), _edge("b", "a", "contrasts_with")))
    assert len([h for h in hard if "BOTH directions" in h]) == 1


def test_one_contrasts_with_direction_alone_is_fine() -> None:
    hard, _ = ed.check(_chunk(_edge("a", "b", "contrasts_with")))
    assert not hard


def test_a_prereq_named_source_is_advisory_never_hard() -> None:
    """The whole point of the soft channel: this must never fail a gate."""
    hard, soft = ed.check(_chunk(_edge("bun_requirement", "channels", "requires")))
    assert not hard
    assert len(soft) == 1


def test_the_correct_prereq_direction_is_silent() -> None:
    """`channels requires bun_requirement` is the RIGHT way round."""
    _, soft = ed.check(_chunk(_edge("channels", "bun_requirement", "requires")))
    assert not soft


def test_the_prereq_advisory_only_applies_to_requires() -> None:
    _, soft = ed.check(_chunk(_edge("bun_requirement", "channels", "part_of")))
    assert not soft


def test_a_substring_match_does_not_fire_the_prereq_advisory() -> None:
    """`needle` contains `need`; the pattern is segment-anchored, not substring."""
    _, soft = ed.check(_chunk(_edge("needle_parser", "x", "requires")))
    assert not soft


def test_a_non_object_chunk_is_reported_not_crashed() -> None:
    hard, _ = ed.check(["not", "a", "chunk"])
    assert hard


def test_a_non_list_edges_key_defers_to_chunks_validate() -> None:
    hard, soft = ed.check({"edges": "nope"})
    assert not hard
    assert not soft


def test_a_non_dict_edge_is_skipped_not_crashed() -> None:
    hard, _ = ed.check({"edges": ["nope", _edge("a", "a")]})
    assert any("SELF-EDGE" in h for h in hard)


def test_missing_endpoints_do_not_crash() -> None:
    ed.check({"edges": [{"relation": "part_of"}]})


def test_an_unusual_relation_verb_is_accepted() -> None:
    """Regression guard for the check this module deliberately does NOT have.

    A closed allowlist fired 1936 times on 308 legitimate verbs in the real
    corpus. If someone reintroduces one, this fails.
    """
    hard, _ = ed.check(_chunk(_edge("a", "b", "conceptually_related_to")))
    assert not hard
