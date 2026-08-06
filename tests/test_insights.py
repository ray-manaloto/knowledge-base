"""`kb-insights` — reading what the graph already computed, honestly.

The two tests that matter most are the ones written against measured defects:
`audit_edges` must not count a node's stray `confidence` field, and the
freshness gate must be able to say YES — its first version could only ever say
STALE, which is a check that can only fail.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from kb_setup import insights

_NODE = {"id": "n1", "label": "n1", "_origin": "ast"}


def _write_full_graph(
    out: Path,
    *,
    nodes: list[dict],
    links: list[dict],
    hyperedges: list[dict] | None = None,
    graph: dict | None = None,
) -> Path:
    """A pretty-printed graph.json with EXPLICIT nodes/links.

    Shaped like graphify's real output. The shared low-level writer:
    `_write_graph` below builds tier-driven nodes/links and delegates here;
    the composition tests build fully-explicit fixtures (specific
    `repo`/`community`/`_origin`/`source`/`target` values) and call this
    directly.

    `graph` overrides the top-level `"graph"` dict (default `{}`, matching
    every existing fixture). The one caller that needs it is the
    hyperedge-collision regression: graphify's real export nests hyperedges
    at `graph.hyperedges`, which precedes the top-level `nodes` array — a
    shape no other fixture here reproduces.
    """
    out.mkdir(parents=True, exist_ok=True)
    p = out / "graph.json"
    p.write_text(
        json.dumps(
            {
                "directed": False,
                "multigraph": False,
                "graph": {} if graph is None else graph,
                "nodes": nodes,
                "links": links,
                "hyperedges": hyperedges or [],
                "built_at_commit": "deadbeef",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return p


def _write_graph(
    out: Path,
    *,
    tiers: list[str],
    node_confidence: int = 0,
    hyperedges: list[dict] | None = None,
) -> Path:
    """A pretty-printed graph.json shaped like graphify's real output.

    `node_confidence` seeds nodes carrying an edge-only `confidence` field —
    which is not hypothetical: 5 real AST nodes in this corpus do exactly that.

    `hyperedges` seeds the top-level array that follows `links`. graphify's own
    hyperedge schema carries a `confidence`, so an entry there is the realistic
    way a scan that fails to stop at the end of `links` over-counts.
    """
    nodes = [dict(_NODE, id=f"n{i}") for i in range(2)]
    nodes += [dict(_NODE, id=f"bad{i}", confidence="EXTRACTED") for i in range(node_confidence)]
    links = [
        {"source": "n0", "target": "n1", "relation": "calls", "confidence": t, "weight": 1}
        for t in tiers
    ]
    return _write_full_graph(out, nodes=nodes, links=links, hyperedges=hyperedges)


def test_audit_counts_each_tier(tmp_path: Path) -> None:
    g = _write_graph(tmp_path / "graphify-out", tiers=["EXTRACTED"] * 3 + ["INFERRED"] * 2)
    a = insights.audit_edges(g)
    assert a.total == 5
    assert a.by_tier == {"EXTRACTED": 3, "INFERRED": 2}
    assert round(a.pct("INFERRED"), 1) == 40.0


def test_audit_ignores_a_node_carrying_confidence(tmp_path: Path) -> None:
    """THE measured defect this module's streaming design exists for.

    A whole-file count of `"confidence":` returned 819,172 against 819,167 links
    on the real graph, because five `codegraph` AST nodes carry a stray
    edge-only `confidence`. Counting those would report the tier split over a
    population that is not the edge set.

    Control arm: the tier counts here are identical to the sibling test above,
    which has no such nodes — so the extra nodes are provably not contributing.
    """
    g = _write_graph(
        tmp_path / "graphify-out",
        tiers=["EXTRACTED"] * 3 + ["INFERRED"] * 2,
        node_confidence=5,
    )
    a = insights.audit_edges(g)
    assert a.total == 5
    assert a.by_tier == {"EXTRACTED": 3, "INFERRED": 2}


def test_audit_stops_at_the_end_of_the_links_array(tmp_path: Path) -> None:
    """Arms the `break` — a hyperedge's own `confidence` must not be counted.

    Found by a cold review, which deleted the `break` and watched the whole
    suite stay green: the line the module's docstring is loudest about had no
    FAIL direction armed. Every other fixture wrote `"hyperedges": []`, so
    nothing followed the links array that could be miscounted — the gate could
    only pass.

    graphify's hyperedge schema carries a `confidence`, so this is the realistic
    shape, not a synthetic one. Without the `break` the scan reports 2 here
    instead of 1.
    """
    g = _write_graph(
        tmp_path / "graphify-out",
        tiers=["EXTRACTED"],
        hyperedges=[
            {
                "id": "he1",
                "nodes": ["n0", "n1"],
                "relation": "participate_in",
                "confidence": "INFERRED",
            }
        ],
    )
    a = insights.audit_edges(g)
    assert a.total == 1
    assert a.by_tier == {"EXTRACTED": 1}


def test_audit_reports_an_unexpected_tier_rather_than_dropping_it(tmp_path: Path) -> None:
    """AMBIGUOUS is not in our validator today, so it must not be silently eaten."""
    g = _write_graph(tmp_path / "graphify-out", tiers=["EXTRACTED", "AMBIGUOUS"])
    a = insights.audit_edges(g)
    assert a.by_tier["AMBIGUOUS"] == 1


def test_freshness_says_yes_when_both_come_from_one_run(tmp_path: Path) -> None:
    """CONTROL ARM: the first version of this gate could only ever say STALE.

    `kb-artifacts` writes the sidecar and then rewrites graph.json, so a strict
    `sidecar >= graph` is false the moment the recommended remedy finishes — it
    told the reader to run the command they had just run.
    """
    out = tmp_path / "graphify-out"
    g = _write_graph(out, tiers=["EXTRACTED"])
    sidecar = out / ".graphify_analysis.json"
    sidecar.write_text("{}", encoding="utf-8")
    # Sidecar written first, graph a few seconds later — the real ordering.
    os.utime(sidecar, (1_700_000_000, 1_700_000_000))
    os.utime(g, (1_700_000_010, 1_700_000_010))

    fresh, note = insights._freshness(tmp_path)
    assert fresh is True
    assert "same run" in note


def test_freshness_says_stale_when_the_sidecar_is_genuinely_behind(tmp_path: Path) -> None:
    """The motivating case was three DAYS behind, describing a 2.4x smaller corpus."""
    out = tmp_path / "graphify-out"
    g = _write_graph(out, tiers=["EXTRACTED"])
    sidecar = out / ".graphify_analysis.json"
    sidecar.write_text("{}", encoding="utf-8")
    os.utime(sidecar, (1_700_000_000, 1_700_000_000))
    os.utime(g, (1_700_000_000 + 3 * 86_400, 1_700_000_000 + 3 * 86_400))

    fresh, note = insights._freshness(tmp_path)
    assert fresh is False
    assert "STALE" in note
    assert "72.0h" in note


def test_clamp_states_how_much_it_cut() -> None:
    """A truncation that trails off silently is indistinguishable from a short question."""
    short = "why does A connect to B?"
    assert insights._clamp(short) == short
    long = "x" * 5_000
    out = insights._clamp(long)
    assert len(out) < 400
    assert "+4,760 more chars" in out


def test_report_refuses_without_a_graph(tmp_path: Path) -> None:
    assert insights.report(tmp_path, []) == 2


def test_report_rejects_a_bad_top(tmp_path: Path) -> None:
    _write_graph(tmp_path / "graphify-out", tiers=["EXTRACTED"])
    assert insights.report(tmp_path, ["--top", "notanumber"]) == 2
    assert insights.report(tmp_path, ["--top"]) == 2


def test_report_works_with_no_sidecar_at_all(capsys, tmp_path: Path) -> None:
    """The audit is computed live, so it must still PRINT when the sidecar is absent.

    Asserting the return code alone is not enough, and a mutation arm proved it:
    replacing the sidecar branch with an unconditional `return 0` left this test
    green, because the happy path also returns 0. The audit section reaching
    stdout is the actual contract — withholding the one section that is never
    stale would be the real regression.
    """
    _write_graph(tmp_path / "graphify-out", tiers=["EXTRACTED", "INFERRED"])
    assert insights.report(tmp_path, []) == 0
    out = capsys.readouterr().out
    assert "Provenance audit" in out
    assert "EXTRACTED" in out


def test_report_prints_all_four_sections_when_the_sidecar_exists(capsys, tmp_path: Path) -> None:
    """The sidecar sections must actually render — a second arm found this gap.

    The sibling test above has NO sidecar, so an early `return 0` at the sidecar
    branch is invisible to it: the audit has already printed and the happy path
    also returns 0. The harm only shows when a sidecar EXISTS and its three
    sections go missing. A fixture that cannot exhibit the harm is not coverage.
    """
    out_dir = tmp_path / "graphify-out"
    _write_graph(out_dir, tiers=["EXTRACTED"])
    (out_dir / ".graphify_analysis.json").write_text(
        json.dumps(
            {
                "surprises": [
                    {
                        "source": "A",
                        "target": "B",
                        "relation": "semantically_similar_to",
                        "confidence": "INFERRED",
                        "source_files": ["a.md", "b.md"],
                        "why": "because",
                    }
                ],
                "questions": [{"type": "bridge_node", "question": "why does A connect B?"}],
                "gods": [{"id": "x", "label": "Result", "degree": 4692}],
            }
        ),
        encoding="utf-8",
    )

    assert insights.report(tmp_path, []) == 0
    printed = capsys.readouterr().out
    assert "Provenance audit" in printed
    assert "Surprising connections" in printed
    assert "Suggested questions" in printed
    assert "God nodes" in printed
    # The fields the MCP resource layer discards are the reason we read the
    # sidecar at all — assert they survive to the output.
    assert "because" in printed
    assert "bridge_node" in printed


def test_the_cli_dispatches_insights(monkeypatch, tmp_path: Path) -> None:
    """The realistic wiring break is deleting the dispatch line, not renaming the function."""
    from kb_setup import cli

    called: list[list[str]] = []
    monkeypatch.setattr(insights, "report", lambda _r, rest: (called.append(list(rest)), 0)[1])
    monkeypatch.chdir(tmp_path)

    assert cli.main(["insights", "--top", "3"]) == 0
    assert called == [["--top", "3"]]


# --- composition (#175, #167): multi-source community spans, cross-origin
# --- edges, and graph.json size vs graphify's default read cap.


def test_composition_finds_a_community_spanning_two_sources(tmp_path: Path) -> None:
    """Two nodes sharing a community but tagged with different repos -> one span."""
    nodes = [
        {"id": "a1", "_origin": "ast", "repo": "graphify", "community": 5},
        {"id": "a2", "_origin": "ast", "repo": "cognee", "community": 5},
    ]
    g = _write_full_graph(tmp_path / "graphify-out", nodes=nodes, links=[])
    comp = insights.composition(g)
    assert len(comp.spanning) == 1
    assert comp.spanning[0].community == 5
    assert comp.spanning[0].tags == ("cognee", "graphify")


def test_composition_reports_zero_spans_on_a_clean_graph(tmp_path: Path) -> None:
    """Every community single-sourced -> no spans, not a crash on the clean case."""
    nodes = [
        {"id": "a1", "_origin": "ast", "repo": "graphify", "community": 5},
        {"id": "a2", "_origin": "ast", "repo": "graphify", "community": 5},
        {"id": "b1", "_origin": "ast", "repo": "cognee", "community": 9},
    ]
    g = _write_full_graph(tmp_path / "graphify-out", nodes=nodes, links=[])
    comp = insights.composition(g)
    assert comp.spanning == ()
    assert comp.total_communities == 2


def test_composition_treats_untagged_as_its_own_source(tmp_path: Path) -> None:
    """A node with no `repo` key at all must not crash the probe.

    Legitimate for #175 semantic doc nodes — and the "(untagged)" bucket
    counts as a SOURCE in its own right: two untagged nodes plus one tagged
    node sharing a community is a two-source span, not a silently-ignored
    one-source community.
    """
    nodes = [
        {"id": "s1", "_origin": "semantic", "community": 3},
        {"id": "s2", "_origin": "semantic", "community": 3},
        {"id": "a1", "_origin": "ast", "repo": "graphify", "community": 3},
    ]
    g = _write_full_graph(tmp_path / "graphify-out", nodes=nodes, links=[])
    comp = insights.composition(g)
    assert len(comp.spanning) == 1
    assert comp.spanning[0].tags == ("(untagged)", "graphify")


#: Shared by the cross-origin control-arm pair below — the SAME base fixture,
#: with only the edge set differing between the two tests, so "identical
#: except for one injected crossing edge" is enforced by construction rather
#: than by eye (`probes-need-a-control-arm.md`).
_CROSS_ORIGIN_NODES = [
    {"id": "a1", "_origin": "ast", "community": 1},
    {"id": "a2", "_origin": "ast", "community": 1},
    {"id": "s1", "_origin": "semantic", "community": 2},
]


def test_cross_origin_is_zero_with_no_crossing_edge(tmp_path: Path) -> None:
    """CONTROL ARM, negative half.

    Both `ast` and `semantic` nodes are present in the graph, but the one link
    stays within a single origin — proves a nonzero count would come from an
    actual crossing, not from mere co-presence of both origins somewhere in
    the graph.
    """
    links = [{"source": "a1", "target": "a2", "confidence": "EXTRACTED"}]
    g = _write_full_graph(tmp_path / "graphify-out", nodes=_CROSS_ORIGIN_NODES, links=links)
    comp = insights.composition(g)
    assert comp.cross_origin_edges == 0


def test_cross_origin_counts_the_injected_crossing_edge(tmp_path: Path) -> None:
    """CONTROL ARM, positive half — THE injection arm #167's gate rests on.

    Identical fixture to the test above, plus exactly one edge whose
    endpoints differ in `_origin`: the count must move 0 -> 1, proving the
    detector can actually FIRE rather than always answering zero.
    """
    links = [
        {"source": "a1", "target": "a2", "confidence": "EXTRACTED"},
        {"source": "a1", "target": "s1", "confidence": "INFERRED"},  # the injected crossing
    ]
    g = _write_full_graph(tmp_path / "graphify-out", nodes=_CROSS_ORIGIN_NODES, links=links)
    comp = insights.composition(g)
    assert comp.cross_origin_edges == 1


def test_iter_objects_ignores_a_field_nested_inside_metadata() -> None:
    """Locks in the empirical finding `_iter_objects`'s docstring cites.

    A key name that ALSO happens to appear nested inside a `metadata` object
    (real on this corpus: 4,272 nodes carry one) must not masquerade as the
    element's own top-level field. Without depth-gating this would capture
    `repo="should-not-be-captured"` instead of the element's real `repo`.
    """
    lines = [
        "    {\n",
        '      "id": "outer",\n',
        '      "metadata": {\n',
        '        "repo": "should-not-be-captured",\n',
        '        "language": "bash"\n',
        "      },\n",
        '      "repo": "the-real-one"\n',
        "    },\n",
        "  ],\n",
        '  "links": [\n',
    ]
    result = list(insights._iter_objects(iter(lines), '"links": ['))
    assert result == [{"id": "outer", "repo": "the-real-one"}]


def test_iter_objects_survives_a_multiline_list_of_strings_field() -> None:
    """A bare string array element (`"foo",` — no `": "`) must not crash the scan.

    `_field_name` accepts any line starting with a quote, so a list-of-strings
    field's own array elements (e.g. `"aliases": ["foo", "bar"]`, written
    multi-line by `json.dump(..., indent=N)`) look exactly like a KEY to it —
    but carry no `": "` at all, and `_value`'s `split(":", 1)[1]` had nothing
    to index: `IndexError`. This scan does not attempt to represent an
    array-valued field correctly (it has no array parser, only brace-depth
    tracking) — what it must not do is crash, and it must still capture this
    element's ordinary SCALAR fields either side of the list. Reproduced
    directly against `_iter_objects`, not `_scan`, because no committed corpus
    input currently has a list-valued node/link field (#175 cold review,
    finding 6 — "latent, not live").
    """
    lines = [
        "    {\n",
        '      "id": "n1",\n',
        '      "aliases": [\n',
        '        "foo",\n',
        '        "bar"\n',
        "      ],\n",
        '      "repo": "r"\n',
        "    },\n",
        "  ],\n",
        '  "links": [\n',
    ]
    result = list(insights._iter_objects(iter(lines), '"links": ['))
    assert len(result) == 1
    assert result[0]["id"] == "n1"
    assert result[0]["repo"] == "r"


def test_composition_total_edges_counts_a_link_with_no_confidence_field(tmp_path: Path) -> None:
    """The denominator must be ALL links, not just ones carrying `confidence`.

    `cross_origin_edges` is counted over every link regardless of whether it
    has a tier (`_crosses_origin` never gates on `confidence`), so a
    denominator counted only over TIERED links could print
    `cross_origin_edges > total_edges` — not merely misleading, actually
    unrepresentable — the moment one link lacks the field. This link crosses
    origin AND carries no `confidence` at all, so `total_edges` must still
    count it (#175 cold review, finding 7).
    """
    nodes = [
        {"id": "a1", "_origin": "ast", "community": 1},
        {"id": "s1", "_origin": "semantic", "community": 2},
    ]
    links = [{"source": "a1", "target": "s1"}]  # no "confidence" at all
    g = _write_full_graph(tmp_path / "graphify-out", nodes=nodes, links=links)
    comp = insights.composition(g)
    assert comp.cross_origin_edges == 1
    assert comp.total_edges == 1


def test_scan_survives_a_populated_graph_hyperedges_before_top_level_nodes(
    tmp_path: Path,
) -> None:
    """Regression for the real post-#175 artifact shape.

    `graph.hyperedges` (populated — graphify writes the nested slot alongside
    the top-level one, and since 0.9.34 `merge-graphs` does too, not `[]`)
    precedes the top-level `nodes` array (`node_link_data` writes `graph`
    before `nodes`), and a hyperedge's own member list is ALSO keyed
    `"nodes"`. Before `_skip_to`/`_iter_objects` were made depth-aware, this
    decoy `"nodes": [` inside the FIRST hyperedge was matched instead of the
    real top-level one, positioning `fh` mid-hyperedge: every node map stayed
    empty (spans 0 of 0, cross-origin 0) while the audit alone still worked
    (a fresh generator over `links`, unaffected by the corrupted node scan).
    This fixture must go RED against the pre-fix code — confirmed before this
    test was added — and green after.
    """
    graph_meta = {
        "hyperedges": [
            {
                "id": "he1",
                "label": "decoy member list",
                "nodes": ["m1", "m2", "m3"],
                "relation": "participate_in",
                "confidence": "INFERRED",
            }
        ]
    }
    nodes = [
        {"id": "a1", "_origin": "ast", "repo": "graphify", "community": 5},
        {"id": "a2", "_origin": "ast", "repo": "cognee", "community": 5},
        {
            "id": "s1",
            "_origin": "semantic",
            "community": 6,
        },  # untagged, own community — not a 3rd span tag
    ]
    links = [{"source": "a1", "target": "s1", "confidence": "EXTRACTED"}]  # the one crossing edge

    g = _write_full_graph(
        tmp_path / "graphify-out",
        nodes=nodes,
        links=links,
        hyperedges=graph_meta["hyperedges"],
        graph=graph_meta,
    )

    audit, comp = insights._scan(g)
    assert audit.total == 1
    assert comp.total_communities == 2
    assert len(comp.spanning) == 1
    assert comp.spanning[0].community == 5
    assert comp.spanning[0].tags == ("cognee", "graphify")
    assert comp.cross_origin_edges == 1


def test_size_vs_cap_reports_the_real_file_size_and_stays_under(tmp_path: Path) -> None:
    g = _write_graph(tmp_path / "graphify-out", tiers=["EXTRACTED"])
    check = insights.size_vs_cap(g)
    assert check.size_bytes == g.stat().st_size
    assert check.cap_bytes == insights._MAX_GRAPH_FILE_BYTES
    assert check.over_cap is False


def test_size_check_over_cap_true_above_the_constant() -> None:
    """Unit-tests the comparison directly.

    Writing a real 512 MiB fixture to prove the OVER branch is not worth the
    disk/time cost this round.
    """
    check = insights.SizeCheck(
        size_bytes=insights._MAX_GRAPH_FILE_BYTES + 1, cap_bytes=insights._MAX_GRAPH_FILE_BYTES
    )
    assert check.over_cap is True
    assert check.ratio > 1.0


def test_report_prints_the_composition_sections(capsys, tmp_path: Path) -> None:
    """Proves `report()` actually WIRES the three new sections in.

    The sibling lesson to
    `test_report_prints_all_four_sections_when_the_sidecar_exists`: a section
    that is only ever a function nobody calls is invisible to every other
    test in this file.
    """
    nodes = [
        {"id": "a1", "_origin": "ast", "repo": "graphify", "community": 5},
        {"id": "a2", "_origin": "ast", "repo": "cognee", "community": 5},
    ]
    links = [{"source": "a1", "target": "a2", "confidence": "EXTRACTED"}]
    _write_full_graph(tmp_path / "graphify-out", nodes=nodes, links=links)

    assert insights.report(tmp_path, []) == 0
    printed = capsys.readouterr().out
    assert "Multi-source community spans" in printed
    assert "community 5" in printed
    assert "Cross-origin edges" in printed
    assert "Size vs cap" in printed
