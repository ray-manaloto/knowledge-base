# Copyright (c) 2026 Raymond Manaloto
"""Count continuity across graph.json writers (#191).

Two halves, and each is about the same failure: a graph losing nodes with every
gate green, caught three times running only by a human subtracting two printed
numbers.

- `kb_setup.graph_counts` — the ledger. Its defining property is not that it
  remembers a count; it is that it REFUSES to hand one back once the graph has
  moved underneath it. A ledger that answered anyway would produce a confident
  "replaced N" computed against an artifact two generations old, which is worse
  than the silence it replaced.
- `kb_setup._merge_docs._report` — the arithmetic itself. Reachable from this
  interpreter only because the graphify imports were moved inside `main()`; the
  alternative was a check verified solely by the incident that motivated it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import _merge_docs, graph_counts

_COUNTS = {"nodes": 10, "edges": 20, "hyperedges": 3, "members": 9}


class _Graph:
    """The surface `_report` touches on a networkx graph: two methods and `.graph`.

    `.graph` is a real attribute rather than something `_report` getattrs its way
    around, because that is what `build_merge` returns and a fallback would be a
    branch no arm could reach (#198 item 1).
    """

    def __init__(self, nodes: int, edges: int = 0, hyperedges: int = 0) -> None:
        self._n, self._e = nodes, edges
        self.graph = {"hyperedges": [{"id": f"h{i}"} for i in range(hyperedges)]}

    def number_of_nodes(self) -> int:
        return self._n

    def number_of_edges(self) -> int:
        return self._e


def _chunk(nodes: int, supersedes: list[str] | None = None, hyperedges: int = 0) -> dict:
    """A chunk shaped only as far as `_report` reads it: counts + declaration."""
    body: dict = {"nodes": [{"id": f"n{i}"} for i in range(nodes)]}
    if supersedes is not None:
        body["supersedes"] = supersedes
    if hyperedges:
        body["hyperedges"] = [{"id": f"ch{i}"} for i in range(hyperedges)]
    return body


def _priors(nodes: int | None = None, hyperedges: int | None = None) -> dict:
    """What the graph held before, in the ledger's own shape.

    A helper rather than a literal at every call site so that adding the next
    ledger field (`edges`, `members` — #198 notes `_derive_prose` omits the
    latter) does not mean editing every arm in this file.
    """
    return {"nodes": nodes, "hyperedges": hyperedges}


def _graph_file(tmp_path: Path, body: str = "{}") -> Path:
    p = tmp_path / "graphify-out" / "graph.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_record_then_read_round_trips(tmp_path: Path) -> None:
    g = _graph_file(tmp_path)
    graph_counts.record(tmp_path, g, _COUNTS, tag="kb-build")

    assert graph_counts.read(tmp_path, g) == _COUNTS


def test_read_returns_none_once_the_graph_moves(tmp_path: Path) -> None:
    """THE arm. A rewrite outside a tracked writer must yield unknown, not a number.

    The rewrite changes the file's size, so `size:mtime_ns` moves for a reason
    that does not depend on clock resolution — a same-length rewrite inside one
    mtime tick is the case a stat cannot see, and is exactly why the ledger is
    an enhancement rather than a guarantee (see `_fingerprint`).
    """
    g = _graph_file(tmp_path, "{}")
    graph_counts.record(tmp_path, g, _COUNTS, tag="kb-build")
    assert graph_counts.read(tmp_path, g) == _COUNTS  # control: it did work

    g.write_text('{"nodes": [], "links": []}', encoding="utf-8")

    assert graph_counts.read(tmp_path, g) is None


def test_read_returns_none_with_no_ledger(tmp_path: Path) -> None:
    """The fresh-clone state. Nothing to seed, nothing to explain."""
    assert graph_counts.read(tmp_path, _graph_file(tmp_path)) is None


@pytest.mark.parametrize("body", ["{not json", "[]", '"a string"', '{"nodes": 10}'])
def test_read_returns_none_for_an_unusable_ledger(tmp_path: Path, body: str) -> None:
    """Malformed, wrong shape, or missing its fingerprint — all unknown.

    `{"nodes": 10}` is the interesting one: a ledger with real-looking counts and
    no fingerprint must NOT be trusted, because nothing ties those counts to the
    file on disk.
    """
    g = _graph_file(tmp_path)
    graph_counts.ledger_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    graph_counts.ledger_path(tmp_path).write_text(body, encoding="utf-8")

    assert graph_counts.read(tmp_path, g) is None


def test_read_returns_none_when_the_graph_is_absent(tmp_path: Path) -> None:
    """An absent artifact fingerprints as "", which must never match a record."""
    g = _graph_file(tmp_path)
    graph_counts.record(tmp_path, g, _COUNTS, tag="kb-build")
    g.unlink()

    assert graph_counts.read(tmp_path, g) is None


def test_record_ignores_unknown_fields(tmp_path: Path) -> None:
    g = _graph_file(tmp_path)
    graph_counts.record(tmp_path, g, {**_COUNTS, "bogus": 1}, tag="kb-build")

    assert graph_counts.read(tmp_path, g) == _COUNTS
    assert "bogus" not in json.loads(graph_counts.ledger_path(tmp_path).read_text())


def test_opt_reads_a_flag_value_and_tolerates_a_trailing_flag() -> None:
    argv = ["s", "c", "r", "o", "--prior-nodes", "41"]

    assert _merge_docs._opt(argv, "--prior-nodes") == "41"
    assert _merge_docs._opt(argv, "--counts-out") is None
    assert _merge_docs._opt([*argv, "--counts-out"], "--counts-out") is None


def test_report_states_the_identity_when_nothing_was_replaced(capsys) -> None:
    _merge_docs._report("c.json", _chunk(10), _priors(nodes=100), _Graph(110))

    out = capsys.readouterr().out
    assert "0 replaced" in out
    assert "100 + 10 = 110" in out
    assert "REPLACED" not in out


def test_report_names_the_replaced_count_when_the_arithmetic_disagrees(capsys) -> None:
    """The 2026-08-06 shape, to scale: +796 printed while the total rose 681.

    The number this prints — 115 — is the one that took a human three rounds to
    notice, and 72 of it belonged to a source nobody was touching.
    """
    _merge_docs._report("c.json", _chunk(796), _priors(nodes=336488), _Graph(337169))

    out = capsys.readouterr().out
    assert "REPLACED 115 node(s)" in out
    assert "UNEXPECTED" in out
    assert "declares no supersession" in out


def test_report_still_flags_a_replacement_that_was_declared(capsys) -> None:
    """A declaration explains a replacement; it does not hide it.

    #189 is the blocking layer. This line's job is visibility, and a supersession
    that silently printed nothing would put the legitimate case and the
    catastrophic one back into the same silence.
    """
    _merge_docs._report("c.json", _chunk(10, ["p.md"]), _priors(nodes=100), _Graph(105))

    out = capsys.readouterr().out
    assert "REPLACED 5 node(s)" in out
    assert "EXPECTED" in out
    assert "supersedes=['p.md']" in out


def test_report_says_not_checked_rather_than_guessing(capsys) -> None:
    """No prior means no arithmetic — never a delta computed against a guess."""
    _merge_docs._report("c.json", _chunk(10), None, _Graph(110))

    out = capsys.readouterr().out
    assert "arithmetic NOT checked" in out
    assert "REPLACED" not in out
    assert "replaced" not in out


def test_the_186_shape_is_reported_while_the_node_half_is_correctly_silent(capsys) -> None:
    """THE arm for #198 item 1: nodes balance, hyperedges do not.

    The #186 loss — 11 hyperedges to 8, no nodes moved — is the FIRST incident this
    whole ticket family was filed over, and the node-only assertion would have
    printed "0 replaced" over it and been RIGHT. That is the point: this arm fails
    if the hyperedge line is removed, and it also pins that the node line keeps
    saying nothing, so a future reader cannot mistake the node half for the thing
    that caught this.
    """
    _merge_docs._report(
        "c.json",
        _chunk(10),
        _priors(nodes=100, hyperedges=11),
        _Graph(110, hyperedges=8),
    )

    out = capsys.readouterr().out
    assert "0 replaced" in out
    assert "REPLACED" not in out
    assert "LOST 3 hyperedge(s)" in out
    assert "11 + 0 = 11" in out
    assert "the graph holds 8" in out


def test_the_hyperedge_message_enumerates_causes_instead_of_asserting_one(capsys) -> None:
    """It may NOT reuse the node line's single-cause sentence.

    A doc merge has one way to drop a node, so the node line names it. Hyperedges
    have four (`_HYPEREDGE_LOSS_CAUSES`), only one of which is that same rule and
    only one of which graphify announces — so a copied "every one carried a
    source_file this chunk also names" would be a confident sentence that is false
    three ways. This arm is what stops the wording drifting back into symmetry.
    """
    _merge_docs._report(
        "c.json", _chunk(10), _priors(nodes=100, hyperedges=11), _Graph(110, hyperedges=8)
    )

    out = capsys.readouterr().out
    assert "UNEXPECTED" in out
    for fragment in ("source_file this chunk also names", "id collision", "stderr", "falsy"):
        assert fragment in out, fragment
    # The node line's claim, which must NOT be made about hyperedges.
    assert "Every replaced node carried" not in out


def test_a_hyperedge_line_is_silent_only_about_a_provably_empty_set() -> None:
    """Nothing before, nothing incoming, nothing held — there is no claim to make.

    Every OTHER unknown says so out loud. Silence that could mean "unchecked" is
    how a gate gets read as a pass.
    """
    assert _merge_docs._hyperedge_line(0, 0, 0) is None
    assert _merge_docs._hyperedge_line(None, 0, 0) is None

    unknown = _merge_docs._hyperedge_line(None, 0, 5)
    assert unknown is not None
    assert "NOT checked" in unknown


def test_a_hyperedge_self_remerge_does_not_cry_wolf() -> None:
    """A routine re-merge balances to "every hyperedge it owns", every time.

    Re-merging the committed 45-hyperedge `graphify-2026-08-06` chunk puts every
    source_file it names into `new_sem_sources`, so all 45 prior hyperedges leave
    the carry and its 45 new ones are added back: the arithmetic reads as 45 lost
    on the single most common merge there is.
    """
    line = _merge_docs._hyperedge_line(92, 45, 92, self_remerge=True)

    assert line is not None
    assert "LOST 45 hyperedge(s)" in line
    assert "EXPECTED" in line
    assert "UNEXPECTED" not in line


def test_a_declared_hyperedge_supersession_is_explained_not_hidden() -> None:
    line = _merge_docs._hyperedge_line(11, 5, 13, declared=["p.md"])

    assert line is not None
    assert "LOST 3 hyperedge(s)" in line
    assert "supersedes=['p.md']" in line


def test_a_balanced_hyperedge_merge_states_the_identity() -> None:
    line = _merge_docs._hyperedge_line(11, 5, 16)

    assert line is not None
    assert "11 + 5 = 16, 0 lost" in line
    assert "LOST" not in line


def test_an_impossible_hyperedge_gain_is_reported_rather_than_assumed_away() -> None:
    """`build_merge` as read cannot produce this — which is exactly why it prints.

    The kept set is a subset of (new + carried), so total <= prior + added. That is
    an assumption about SOMEONE ELSE'S code, in a file that already carries one
    comment which overstated what that code does.
    """
    line = _merge_docs._hyperedge_line(5, 1, 9)

    assert line is not None
    assert "UNEXPECTED GAIN of 3" in line


def test_int_opt_degrades_a_non_numeric_count_to_not_checked() -> None:
    argv = ["s", "--prior-nodes", "41", "--prior-hyperedges", "many", "--counts-out"]

    assert _merge_docs._int_opt(argv, "--prior-nodes") == 41
    assert _merge_docs._int_opt(argv, "--prior-hyperedges") is None
    assert _merge_docs._int_opt(argv, "--counts-out") is None
    assert _merge_docs._int_opt(argv, "--absent") is None


def test_report_calls_a_self_remerge_expected_rather_than_a_loss(capsys) -> None:
    """The routine case, and the reason this branch exists at all.

    Measured live 2026-08-06: re-merging `claude-commands-docs.json` reports
    `REPLACED 10` with the total unchanged — its own ten nodes, pruned and
    re-added. That happens on EVERY re-merge. The first draft of this line
    printed "the identities collided and the loss is real" for it, which is a
    false alarm on the single most common merge there is; a check that cries wolf
    on the ordinary path is one people learn to skip.

    The caller decides, because only it can see the committed corpus — this arm
    pins that the wording actually changes, so the flag cannot be quietly ignored
    the way an unread parameter would be.
    """
    _merge_docs._report("c.json", _chunk(10), _priors(nodes=100), _Graph(100), self_remerge=True)

    out = capsys.readouterr().out
    assert "REPLACED 10 node(s)" in out
    assert "EXPECTED" in out
    assert "replaced its own prior contribution" in out
    assert "loss is real" not in out


def test_the_prose_derivation_refreshes_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every graph write path ends in a prose derivation — so that is where counts land.

    Without this the feature was largely dead in ordinary use. `kb-label`
    rewrites `graph.json` and recorded nothing, the documented ingestion order is
    "always relabel after a merge", and the ledger is fingerprint-gated — so the
    merge AFTER any prior ingestion's label pass found the fingerprint moved and
    reported "arithmetic NOT checked". The check existed and could almost never
    run. (Cold lane, round 1, P2.)

    `members` is absent by design: `ProseStats` counts hyperedges, not their
    members, and inventing a zero would be worse than an absent key.
    """
    from kb_setup import graphify_ops, prose

    g = _graph_file(tmp_path)
    stats = prose.ProseStats(
        nodes_in=500, nodes_out=40, links_in=900, links_out=60, hyperedges_in=7, hyperedges_out=7
    )
    monkeypatch.setattr(prose, "derive_for", lambda _root: stats)

    assert graphify_ops._derive_prose(tmp_path, tag="kb-label", did="the graph was relabelled") == 0
    assert graph_counts.read(tmp_path, g) == {"nodes": 500, "edges": 900, "hyperedges": 7}


def test_a_failed_prose_derivation_records_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: no derivation, no counts — never a number from a run that failed."""
    from kb_setup import graphify_ops, prose

    g = _graph_file(tmp_path)

    def _boom(_root: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(prose, "derive_for", _boom)

    assert graphify_ops._derive_prose(tmp_path, tag="kb-label", did="x") == 1
    assert graph_counts.read(tmp_path, g) is None
