# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.edge_direction`.

Every HARD check here has ZERO occurrences in the committed corpus except the one
real `contrasts_with` defect, so a test that only fed it real chunks would pass
while the checks did nothing. Each hard check therefore gets a synthetic FAIL
fixture AND a near-miss PASS fixture — the near-miss is the one that matters,
because it is what distinguishes a check from a `return []`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from kb_setup import cli
from kb_setup import edge_direction as ed

if TYPE_CHECKING:
    import pathlib

    import pytest


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


def test_a_contrasts_with_self_edge_is_not_also_called_both_directions() -> None:
    """One edge cannot be "both directions" of a pair.

    `(a, a)` satisfies `(t, s) in pairs` trivially — it IS `(s, t)` — so the
    symmetric check reported a second, FALSE message beside the true SELF-EDGE
    one. A false line next to a true one is worse than no line: it is what
    teaches a reader to skim the channel.
    """
    hard, _ = ed.check(_chunk(_edge("a", "a", "contrasts_with")))
    assert any("SELF-EDGE" in h for h in hard)
    assert not [h for h in hard if "BOTH directions" in h]


def test_a_cycle_split_across_two_chunks_is_caught() -> None:
    """The P1 gap: neither file alone contains a cycle, together they do.

    A per-file loop reports both files clean. This is not hypothetical — 10 node
    ids are declared in two different committed chunks today, so only the
    relation coincidence was missing.
    """
    hard, _ = ed.check_many(
        [
            ("left.json", _chunk(_edge("a", "b", "requires"))),
            ("right.json", _chunk(_edge("b", "a", "requires"))),
        ]
    )
    assert any("CYCLE" in h for h in hard)


def test_a_cross_chunk_cycle_names_both_chunks() -> None:
    """Otherwise the reader is sent to look for a cycle in one file that has none."""
    hard, _ = ed.check_many(
        [
            ("left.json", _chunk(_edge("a", "b", "requires"))),
            ("right.json", _chunk(_edge("b", "a", "requires"))),
        ]
    )
    cycles = [h for h in hard if "CYCLE" in h]
    assert len(cycles) == 1
    assert "left.json" in cycles[0]
    assert "right.json" in cycles[0]


def test_a_cross_chunk_contrasts_with_pair_is_caught() -> None:
    """Same isolation gap, on the symmetric-relation check."""
    hard, _ = ed.check_many(
        [
            ("left.json", _chunk(_edge("a", "b", "contrasts_with"))),
            ("right.json", _chunk(_edge("b", "a", "contrasts_with"))),
        ]
    )
    both = [h for h in hard if "BOTH directions" in h]
    assert len(both) == 1
    assert "left.json" in both[0]
    assert "right.json" in both[0]


def test_two_chunks_that_do_not_share_a_cycle_stay_clean() -> None:
    """The near-miss for the union: unioning must not INVENT a contradiction.

    Two acyclic chunks whose ids happen to interleave are the ordinary case, and
    a union check that flagged them would be switched off within one round.
    """
    hard, _ = ed.check_many(
        [
            ("left.json", _chunk(_edge("a", "b", "requires"))),
            ("right.json", _chunk(_edge("b", "c", "requires"))),
        ]
    )
    assert not hard


def test_a_single_chunk_cycle_still_names_only_that_chunk() -> None:
    hard, _ = ed.check_many([("only.json", _chunk(_edge("a", "b"), _edge("b", "a")))])
    cycles = [h for h in hard if "CYCLE" in h]
    assert len(cycles) == 1
    assert cycles[0].startswith("only.json:")


def test_check_is_exactly_the_one_chunk_case_of_check_many() -> None:
    """Pins the delegation, so the two can never drift into disagreeing.

    `check` was a parallel implementation before the union landed; a second copy
    of these rules is how one of them silently stops matching the other.
    """
    chunk = _chunk(_edge("a", "a"), _edge("x", "y", "requires"), _edge("y", "x", "requires"))
    assert ed.check(chunk, label="c.json") == ed.check_many([("c.json", chunk)])


def test_check_many_reports_a_non_object_chunk_without_losing_the_others() -> None:
    hard, _ = ed.check_many(
        [("bad.json", ["not", "a", "chunk"]), ("ok.json", _chunk(_edge("a", "a")))]
    )
    assert any(h == "bad.json: not a JSON object" for h in hard)
    assert any("SELF-EDGE" in h for h in hard)


def test_an_unusual_relation_verb_is_accepted() -> None:
    """Regression guard for the check this module deliberately does NOT have.

    A closed allowlist fired 1936 times on 308 legitimate verbs in the real
    corpus. If someone reintroduces one, this fails.
    """
    hard, _ = ed.check(_chunk(_edge("a", "b", "conceptually_related_to")))
    assert not hard


# --- the CLI wiring -------------------------------------------------------
#
# The union lives in `edge_direction.check_many`, but the gap it closes was in
# `cli._report_edge_direction`, which looped. A module-level test alone would
# leave the call site free to loop again and stay green — the "a validator
# nothing calls is not a gate" shape this repo has walked into before.


def _write(tmp_path: pathlib.Path, name: str, *edges: dict[str, object]) -> pathlib.Path:
    p = tmp_path / name
    p.write_text(json.dumps(_chunk(*edges)), encoding="utf-8")
    return p


def test_the_cli_unions_chunks_rather_than_looping(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The end-to-end P1 arm: two files, one cycle between them, rc must be 1."""
    left = _write(tmp_path, "left.json", _edge("a", "b", "requires"))
    right = _write(tmp_path, "right.json", _edge("b", "a", "requires"))
    rc = cli._report_edge_direction([left, right])
    out = capsys.readouterr()
    assert rc == 1
    assert "CYCLE" in out.err
    assert "left.json" in out.err
    assert "right.json" in out.err


def test_the_cli_stays_green_on_two_unrelated_chunks(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The near-miss: unioning must not turn ordinary chunks red."""
    left = _write(tmp_path, "left.json", _edge("a", "b", "requires"))
    right = _write(tmp_path, "right.json", _edge("c", "d", "requires"))
    rc = cli._report_edge_direction([left, right])
    out = capsys.readouterr()
    assert rc == 0
    assert "no structural contradictions" in out.out


def test_an_unreadable_chunk_is_named_and_not_counted_as_covered(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """P2: the green line counted files it never parsed.

    `validate_files` fails the run for the bad file, so this was never a
    false-green on the GATE — but the coverage number was false, and a number
    nobody can trust is the thing that makes the rest of the line unreadable.
    """
    good = _write(tmp_path, "good.json", _edge("a", "b", "requires"))
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    rc = cli._report_edge_direction([good, bad])
    out = capsys.readouterr()
    assert rc == 0
    assert "NOT CHECKED for 1 unreadable chunk(s): bad.json" in out.err
    assert "across the UNION of 1 chunk(s)" in out.out
    assert "2 chunk(s)" not in out.out
