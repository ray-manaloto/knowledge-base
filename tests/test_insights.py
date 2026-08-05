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


def _write_graph(out: Path, *, tiers: list[str], node_confidence: int = 0) -> Path:
    """A pretty-printed graph.json shaped like graphify's real output.

    `node_confidence` seeds nodes carrying an edge-only `confidence` field —
    which is not hypothetical: 5 real AST nodes in this corpus do exactly that.
    """
    nodes = [dict(_NODE, id=f"n{i}") for i in range(2)]
    nodes += [dict(_NODE, id=f"bad{i}", confidence="EXTRACTED") for i in range(node_confidence)]
    links = [
        {"source": "n0", "target": "n1", "relation": "calls", "confidence": t, "weight": 1}
        for t in tiers
    ]
    out.mkdir(parents=True, exist_ok=True)
    p = out / "graph.json"
    p.write_text(
        json.dumps(
            {
                "directed": False,
                "multigraph": False,
                "graph": {},
                "nodes": nodes,
                "links": links,
                "hyperedges": [],
                "built_at_commit": "deadbeef",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return p


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
