# Copyright (c) 2026 Raymond Manaloto
"""The seam between `_merge_docs.py` and its two callers (#189, #191).

`_merge_docs.py` runs under graphify's bundled interpreter and cannot import
`kb_setup`, so its post-merge counts come back through a FILE. That handoff is
the part most likely to rot quietly: a stale one read as this run's result
produces a prior count silently one chunk out of date, and therefore a
confident, wrong "replaced N" — the exact failure mode the ledger exists to
remove. Every arm here is about consumption and refusal, not about the happy
path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import _merge_docs, graph, graph_counts, graphify_ops

if TYPE_CHECKING:
    import pytest


def _handoff(tmp_path: Path, body: str) -> Path:
    p = tmp_path / ".merge-counts.tmp.json"
    p.write_text(body, encoding="utf-8")
    return p


def test_handoff_counts_reads_then_consumes(tmp_path: Path) -> None:
    """One read, then unknown. A prior count must never outlive its own chunk."""
    h = _handoff(tmp_path, json.dumps({"nodes": 42, "edges": 7, "hyperedges": 11}))

    assert graph._handoff_counts(h) == {"nodes": 42, "hyperedges": 11}
    assert not h.exists()
    assert graph._handoff_counts(h) == {"nodes": None, "hyperedges": None}


def test_handoff_counts_reports_unknown_per_field(tmp_path: Path) -> None:
    """A handoff carrying one threaded field and not the other checks the one it has.

    The whole reason `_handoff_counts` returns a mapping instead of a tuple: #198
    records that `_derive_prose` writes `{nodes, edges, hyperedges}` and NOT
    `members`, so a partial payload is a shape this repo really produces. An
    all-or-nothing reader would answer "not checked" for a count sitting right
    there in the file.
    """
    h = _handoff(tmp_path, json.dumps({"nodes": 42}))
    assert graph._handoff_counts(h) == {"nodes": 42, "hyperedges": None}

    h = _handoff(tmp_path, json.dumps({"hyperedges": 8}))
    assert graph._handoff_counts(h) == {"nodes": None, "hyperedges": 8}


def test_handoff_counts_consumes_even_when_unusable(tmp_path: Path) -> None:
    """A malformed handoff is removed too, so the NEXT chunk cannot inherit it.

    Returning None while leaving the file behind would be the worst of both:
    this chunk reports "not checked", and the chunk after it reads a count
    belonging to neither.
    """
    unknown = {"nodes": None, "hyperedges": None}
    for body in ("{not json", "[]", '{"nodes": "many"}', "{}", '{"hyperedges": []}'):
        h = _handoff(tmp_path, body)
        assert graph._handoff_counts(h) == unknown, body
        assert not h.exists(), body


def test_handoff_counts_on_a_missing_file_is_unknown(tmp_path: Path) -> None:
    assert graph._handoff_counts(tmp_path / "never-written.json") == {
        "nodes": None,
        "hyperedges": None,
    }


def test_every_threaded_count_is_one_the_merge_asserts_an_identity_over() -> None:
    """`_THREADED_COUNTS` must stay a subset of what the ledger actually records.

    A field threaded into argv that `graph_counts` never records would be a flag
    `_merge_docs` waits on forever — silently "not checked" rather than broken,
    which is the failure mode that reads as a pass.
    """
    assert set(graph._THREADED_COUNTS) <= set(graph_counts._FIELDS)


def test_record_counts_moves_the_handoff_into_the_ledger(tmp_path: Path) -> None:
    g = tmp_path / "graphify-out" / "graph.json"
    g.parent.mkdir(parents=True)
    g.write_text("{}", encoding="utf-8")
    counts = {"nodes": 5, "edges": 6, "hyperedges": 1, "members": 3}
    h = _handoff(tmp_path, json.dumps(counts))

    graphify_ops._record_counts(tmp_path, g, h, tag="kb-merge")

    assert not h.exists()
    assert graph_counts.read(tmp_path, g) == counts


def test_record_counts_writes_no_ledger_when_the_merge_left_nothing(tmp_path: Path) -> None:
    """A failed merge writes no handoff, so nothing may be recorded.

    Recording here would certify a count against a graph the failed run may have
    left half-written — and the ledger's whole value is that a number it returns
    can be trusted.
    """
    g = tmp_path / "graphify-out" / "graph.json"
    g.parent.mkdir(parents=True)
    g.write_text("{}", encoding="utf-8")

    graphify_ops._record_counts(tmp_path, g, tmp_path / "absent.json", tag="kb-merge")

    assert not graph_counts.ledger_path(tmp_path).exists()
    assert graph_counts.read(tmp_path, g) is None


def _write_chunk(path: Path, source_file: str, *, supersedes: list[str] | None = None) -> None:
    body: dict = {
        "nodes": [
            {
                "id": f"{path.stem}_n",
                "label": "n",
                "_origin": "semantic",
                "file_type": "concept",
                "source_file": source_file,
                "source_url": "https://example.invalid/x",
                "captured_at": "2026-08-01",
            }
        ],
        "edges": [],
        "hyperedges": [],
    }
    if supersedes is not None:
        body["supersedes"] = supersedes
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding="utf-8")


def test_preflight_refuses_a_chunk_colliding_with_the_committed_corpus(tmp_path: Path) -> None:
    """The door the 2026-08-06 chunk walked through with a ✓ beside it."""
    committed = tmp_path / "sources" / "extractions" / "a-docs.json"
    _write_chunk(committed, "CHANGELOG.md")
    incoming = tmp_path / "incoming" / "b-docs.json"
    _write_chunk(incoming, "CHANGELOG.md")

    assert graphify_ops._preflight(tmp_path, incoming) == 2


def test_preflight_admits_the_same_chunk_once_it_declares(tmp_path: Path) -> None:
    """CONTROL ARM: identical fixture, one declaration, admitted."""
    committed = tmp_path / "sources" / "extractions" / "a-docs.json"
    _write_chunk(committed, "CHANGELOG.md")
    incoming = tmp_path / "incoming" / "b-docs.json"
    _write_chunk(incoming, "CHANGELOG.md", supersedes=["CHANGELOG.md"])

    assert graphify_ops._preflight(tmp_path, incoming) is None


def test_preflight_admits_a_re_merge_of_an_already_committed_chunk(tmp_path: Path) -> None:
    """Re-merging a committed chunk passes it alongside the glob containing it.

    Without the resolve-and-dedup in `collision_issues`, the single most routine
    `kb-merge` invocation there is would refuse itself — and a gate that blocks
    the ordinary case is one someone turns off.
    """
    committed = tmp_path / "sources" / "extractions" / "a-docs.json"
    _write_chunk(committed, "CHANGELOG.md")

    assert graphify_ops._preflight(tmp_path, committed) is None


def test_replay_threads_each_count_into_the_next_chunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chunk 1 carries no prior; every chunk after it carries the one before.

    `_run` is stubbed because the real one shells out to graphify's interpreter,
    and what this arm is about is the ARGV — which flag reaches which chunk. The
    stub also writes the handoff, because a stub that only records calls would
    make every chunk look like chunk 1 and the test would pass with the threading
    deleted.

    Chunk 1's prior is unknown BY CONSTRUCTION, not by accident: `build()` has
    already re-seeded `graph.json` from the code layer by the time this runs, so
    the ledger describes the previous build's artifact. Asserting the absence
    here is what stops someone "fixing" that later into a baseline for a file
    that no longer exists.
    """
    out = tmp_path / "graphify-out" / "graph.json"
    out.parent.mkdir(parents=True)
    chunks_dir = tmp_path / "sources" / "extractions"
    for i, when in enumerate(("2026-08-01", "2026-08-02", "2026-08-03")):
        _write_chunk(chunks_dir / f"c{i}-docs.json", f"f{i}.md")
        (chunks_dir / f"c{i}-docs.json").write_text(
            (chunks_dir / f"c{i}-docs.json").read_text().replace("2026-08-01", when),
            encoding="utf-8",
        )
    # A ledger DOES exist and matches the graph — so a `prior-nodes` on chunk 1
    # would mean the code consulted it, which is the thing being ruled out.
    out.write_text("{}", encoding="utf-8")
    graph_counts.record(tmp_path, out, {"nodes": 999}, tag="kb-build")

    seen: list[list[str]] = []
    counter = iter(({"nodes": 10, "hyperedges": 3}, {"nodes": 25}, {"nodes": 40}))

    def _fake_run(argv: list[str], _cwd: Path) -> None:
        seen.append(argv)
        Path(argv[argv.index("--counts-out") + 1]).write_text(
            json.dumps(next(counter)), encoding="utf-8"
        )

    monkeypatch.setattr(graph, "_run", _fake_run)
    graph._replay_doc_chunks(
        tmp_path, "py", tmp_path / "sources", out, sorted(chunks_dir.glob("*.json"))
    )

    def _flag(argv: list[str], flag: str) -> str | None:
        return argv[argv.index(flag) + 1] if flag in argv else None

    assert [_flag(a, "--prior-nodes") for a in seen] == [None, "10", "25"]
    # The hyperedge half threads on the SAME rule and independently of nodes
    # (#198 item 1). Chunk 2 gets the 3 chunk 1 emitted; chunk 3 gets none,
    # because chunk 2's handoff carried `nodes` alone — a partial payload must
    # narrow the NEXT chunk's check to the field it can still establish, never
    # carry a stale count forward and never suppress the node check as well.
    assert [_flag(a, "--prior-hyperedges") for a in seen] == [None, "3", None]
    assert not out.with_name(".merge-counts.tmp.json").exists()


def _dated_chunk(path: Path, source_file: str, when: str) -> None:
    """A chunk whose nodes carry `captured_at: when` — the replay-order key."""
    _write_chunk(path, source_file)
    path.write_text(path.read_text().replace("2026-08-01", when), encoding="utf-8")


def _recompose_seen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replay: list[tuple[Path, str]]
) -> list[list[str]]:
    """Drive `_recompose_into_temp` over `replay`, returning the argv it built.

    Everything below the replay loop is stubbed because none of it is the
    subject: the swap, the stamp and the N-ary source merge all have their own
    arms. `_run` is the seam that matters — the ORDER it is called in is the
    property under test, and it is the property that was wrong.
    """
    out = tmp_path / "graphify-out" / "graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("{}", encoding="utf-8")

    seen: list[list[str]] = []

    def _fake_run(argv: list[str], _cwd: Path) -> None:
        seen.append(argv)
        if "--counts-out" in argv:
            Path(argv[argv.index("--counts-out") + 1]).write_text(
                json.dumps({"nodes": 10 * len(seen)}), encoding="utf-8"
            )

    monkeypatch.setattr(graph, "_run", _fake_run)
    monkeypatch.setattr(graph, "graphify_python", lambda _root: "py")
    monkeypatch.setattr(graph, "_merge_sources_into", lambda *_a, **_k: None)
    monkeypatch.setattr(graph, "_clear_stamp", lambda *_a, **_k: None)

    graph._recompose_into_temp(tmp_path, out, [], replay)
    return seen


def test_recompose_replays_in_capture_order_not_the_order_it_was_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`kb-watch` must supersede by capture date, exactly as `kb-build` does.

    THE regression arm for the 2026-08-08 `kb-watch` failure. `_recompose_into_temp`
    replayed `manifest.chunks` in the order the manifest stored them — which is
    alphabetical — while `build()` applied `chunks.replay_order`. Same committed
    corpus, two different graphs, chosen by the alphabet: the precise defect
    `chunks.replay_order` exists to remove, fixed on one path and left live on
    its sibling.

    The fixture is the real pair, names and dates unchanged, because the names
    are what carried the bug: `mirror` sorts AFTER `refresh` alphabetically and
    BEFORE it by capture date, so an implementation that has merely been handed
    a pre-sorted list still fails here — the input is deliberately in the wrong
    order, which is how the manifest really holds it.
    """
    ext = tmp_path / "sources" / "extractions"
    _dated_chunk(ext / "claude-code-docs-2026-08-05-refresh-docs.json", "hooks.md", "2026-08-05")
    _dated_chunk(ext / "claude-code-docs-mirror-docs.json", "hooks.md", "2026-07-30")
    given = sorted(ext.glob("*.json"))  # alphabetical, as `manifest.chunks` is
    assert [p.name for p in given] == [
        "claude-code-docs-2026-08-05-refresh-docs.json",
        "claude-code-docs-mirror-docs.json",
    ], "fixture must start in the WRONG order or this arm cannot fail"

    seen = _recompose_seen(tmp_path, monkeypatch, [(p, str(tmp_path)) for p in given])

    replayed = [Path(argv[2]).name for argv in seen]
    assert replayed == [
        "claude-code-docs-mirror-docs.json",
        "claude-code-docs-2026-08-05-refresh-docs.json",
    ]


def test_recompose_threads_each_merges_count_into_the_next(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#191's arithmetic gate must fire on the recomposition path too.

    It never had. Every `[merge]` line `kb-watch` printed said *prior node count
    unknown — arithmetic NOT checked*, because this loop passed neither
    `--prior-<field>` nor `--counts-out`. A silent-loss gate that is wired into
    one of a feature's two callers is not a gate, and the half it was missing
    from is the half that recomposes the whole corpus.
    """
    ext = tmp_path / "sources" / "extractions"
    for i, when in enumerate(("2026-08-01", "2026-08-02", "2026-08-03")):
        _dated_chunk(ext / f"c{i}-docs.json", f"f{i}.md", when)
    given = sorted(ext.glob("*.json"))

    seen = _recompose_seen(tmp_path, monkeypatch, [(p, str(tmp_path)) for p in given])

    priors = [a[a.index("--prior-nodes") + 1] if "--prior-nodes" in a else None for a in seen]
    assert priors == [None, "10", "20"]


def test_recompose_replays_under_the_root_it_was_handed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL on the two arms above: routing through the shared loop kept the roots.

    `_replay_doc_chunks` derives `sources/<name>`; recomposition carries a root
    recorded at merge time (`chunk_roots`), and that difference is the entire
    reason the two loops were separate. Sharing the loop by making it derive the
    root itself would silently discard every recorded override — passing both
    tests above while breaking the thing those overrides exist for.
    """
    ext = tmp_path / "sources" / "extractions"
    _dated_chunk(ext / "a-docs.json", "a.md", "2026-08-01")
    recorded = str(tmp_path / "sources" / "somewhere-else")

    seen = _recompose_seen(tmp_path, monkeypatch, [(ext / "a-docs.json", recorded)])

    assert seen[0][3] == recorded


def test_both_replay_paths_order_by_the_same_key(tmp_path: Path) -> None:
    """The invariant the split loops violated: one supersession rule, not two.

    Asserted against `chunks.replay_key` itself rather than by re-deriving an
    expected order here, because a test that reimplements the key is a second
    implementation of exactly the thing that drifted.

    THE FIXTURE IS THE LOAD-BEARING PART, and the first version of it was inert.
    Bare `Path("a-docs.json")`/`Path("z-docs.json")` do not exist, so
    `chunk_captured_at` returns the same value for both and name-order and
    date-order AGREE — a mutation swapping the key to name-first was a genuine
    no-op and survived the sweep. Real files whose alphabetical and chronological
    orders are OPPOSITE are the only fixture that can tell the two apart.
    """
    from kb_setup import chunks as _chunks

    _dated_chunk(tmp_path / "a-docs.json", "a.md", "2026-08-09")
    _dated_chunk(tmp_path / "z-docs.json", "z.md", "2026-07-01")
    paths = sorted(tmp_path.glob("*.json"))
    assert [p.name for p in paths] == ["a-docs.json", "z-docs.json"]

    ordered = _chunks.replay_order(paths)

    assert ordered == sorted(paths, key=_chunks.replay_key)
    # ...and that shared key really is the date one, not the alphabet.
    assert [p.name for p in ordered] == ["z-docs.json", "a-docs.json"]


def test_preflight_still_refuses_a_schema_break(tmp_path: Path) -> None:
    """The older gate must survive the refactor that added the newer one."""
    bad = tmp_path / "incoming" / "bad-docs.json"
    bad.parent.mkdir(parents=True)
    bad.write_text(json.dumps({"nodes": [{"id": "x"}], "edges": []}), encoding="utf-8")

    assert graphify_ops._preflight(tmp_path, bad) == 2


def test_self_remerge_only_when_the_chunk_exclusively_owns_its_files(tmp_path: Path) -> None:
    """Committed AND sole claimant — both conditions, and neither alone is enough.

    An UNCOMMITTED chunk contributed nothing to the graph, so anything it
    replaces belongs to somebody else. A committed chunk that SHARES a
    `source_file` with a sibling is doing a cross-chunk supersession, which is
    #189's subject and must not be waved through as routine. Only the
    intersection is the boring re-extraction case.
    """
    ext = tmp_path / "sources" / "extractions"
    _write_chunk(ext / "solo-docs.json", "solo.md")
    _write_chunk(ext / "shared-a-docs.json", "shared.md")
    _write_chunk(ext / "shared-b-docs.json", "shared.md")
    loose = tmp_path / "elsewhere" / "loose-docs.json"
    _write_chunk(loose, "loose.md")

    assert graphify_ops._self_remerge(tmp_path, ext / "solo-docs.json") is True
    assert graphify_ops._self_remerge(tmp_path, ext / "shared-a-docs.json") is False
    assert graphify_ops._self_remerge(tmp_path, loose) is False


def test_committed_chunks_includes_out_of_tree_ledger_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A chunk merged from ANY path is in the graph, so it is in the collision set.

    `kb-merge` accepts an out-of-tree chunk and `append_merged_chunk` records it
    so `kb-watch` can replay it — its nodes sit in the graph exactly like a
    committed chunk's. The glob alone therefore had a blind side: a new chunk
    could claim a `source_file` that chunk already owned, pass the gate, and have
    `build_merge` delete its nodes. Both halves are asserted so the ledger read
    cannot be a no-op that happens to look right.
    """
    ext = tmp_path / "sources" / "extractions"
    _write_chunk(ext / "committed-docs.json", "committed.md")
    loose = tmp_path / "elsewhere" / "loose-docs.json"
    _write_chunk(loose, "CHANGELOG.md")

    monkeypatch.setattr(graph, "merged_chunk_paths", lambda _root: [loose])
    found = {p.name for p in graphify_ops._committed_chunks(tmp_path)}
    assert found == {"committed-docs.json", "loose-docs.json"}

    monkeypatch.setattr(graph, "merged_chunk_paths", lambda _root: [])
    assert {p.name for p in graphify_ops._committed_chunks(tmp_path)} == {"committed-docs.json"}


def test_committed_chunks_survives_an_unreadable_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupt derived file must narrow the check, never abort it.

    `_read_merged_chunks` returns None for a corrupt ledger and its own callers
    refuse — correctly, they are about to recompose FROM it. This caller is only
    widening a set, and a collision check that raises on a corrupt derived file
    would take the whole gate down with it.
    """
    ext = tmp_path / "sources" / "extractions"
    _write_chunk(ext / "committed-docs.json", "committed.md")

    def _boom(_root: Path) -> list[Path]:
        raise OSError("ledger unreadable")

    monkeypatch.setattr(graph, "merged_chunk_paths", _boom)

    assert {p.name for p in graphify_ops._committed_chunks(tmp_path)} == {"committed-docs.json"}


class _FakeGraph:
    """Enough of a networkx graph for `counts_for` — including `.graph`."""

    def __init__(self, nodes: int, edges: int, hyperedges: list) -> None:
        self._n, self._e = nodes, edges
        self.graph = {"hyperedges": hyperedges}

    def number_of_nodes(self) -> int:
        return self._n

    def number_of_edges(self) -> int:
        return self._e


def test_the_real_counts_producer_is_exercised() -> None:
    """The ONLY producer of real ledger counts had no test at all.

    `_merge_docs.main()` imports graphify and is unreachable from this
    interpreter, so every arm in this suite fabricated the very dict the producer
    is supposed to emit — a regression there (a renamed hyperedge slot, members
    counted per-edge rather than summed) would have left the whole suite green.
    Extracting `counts_for` is what makes it reachable. (Cold lane, round 2, P1.)

    Both member spellings are covered, plus a non-dict entry, because graphify
    writes `nodes` while older chunks say `members` and a malformed entry must
    not turn a successful merge into a traceback.
    """
    g = _FakeGraph(
        10,
        20,
        [{"nodes": ["a", "b", "c"]}, {"members": ["d", "e"]}, "not a dict", {"nodes": None}],
    )

    assert _merge_docs.counts_for(g) == {
        "nodes": 10,
        "edges": 20,
        "hyperedges": 4,
        "members": 5,
    }


def test_counts_for_an_empty_graph_attr() -> None:
    """CONTROL: no hyperedges at all is 0/0, not a KeyError."""
    assert _merge_docs.counts_for(_FakeGraph(3, 4, [])) == {
        "nodes": 3,
        "edges": 4,
        "hyperedges": 0,
        "members": 0,
    }


def test_a_stale_handoff_is_cleared_before_the_subprocess_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A leftover from an interrupted run must never be read as this run's counts.

    The path is fixed and reused, and `_merge_docs.py` legitimately writes nothing
    for a 0-node chunk or a refused export — so consuming-after was not enough.
    The stub writes NO handoff, exactly like those cases; a stale file surviving
    into the ledger is the defect. (Cold lane, round 2, P2.)
    """
    ext = tmp_path / "sources" / "extractions"
    _write_chunk(ext / "c-docs.json", "c.md")
    out = tmp_path / "graphify-out" / "graph.json"
    out.parent.mkdir(parents=True)
    out.write_text("{}", encoding="utf-8")
    stale = out.with_name(".merge-counts.tmp.json")
    stale.write_text(json.dumps({"nodes": 999_999}), encoding="utf-8")

    monkeypatch.setattr(graphify_ops, "graphify_python", lambda _root: "true")
    monkeypatch.setattr(graphify_ops, "clean_env", dict)
    monkeypatch.setattr(graphify_ops, "_derive_prose", lambda *_a, **_k: 1)

    graphify_ops.merge_chunk(tmp_path, str(ext / "c-docs.json"))

    assert not stale.exists()
    assert graph_counts.read(tmp_path, out) is None


def _capture_merge_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ledger: dict[str, int]
) -> list[str]:
    """Run `merge_chunk` against a ledger and return the argv it built.

    `subprocess.run` is stubbed rather than pointed at `true` because what this
    seam is about IS the argv — a stub that only makes the call succeed would let
    the flags be deleted with every arm still green.
    """
    import subprocess

    ext = tmp_path / "sources" / "extractions"
    _write_chunk(ext / "c-docs.json", "c.md")
    out = tmp_path / "graphify-out" / "graph.json"
    out.parent.mkdir(parents=True)
    out.write_text("{}", encoding="utf-8")
    graph_counts.record(tmp_path, out, ledger, tag="kb-build")

    seen: list[list[str]] = []

    def _fake_run(cmd: list[str], **_kw: object) -> subprocess.CompletedProcess:
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(graphify_ops.subprocess, "run", _fake_run)
    monkeypatch.setattr(graphify_ops, "graphify_python", lambda _root: "true")
    monkeypatch.setattr(graphify_ops, "clean_env", dict)
    monkeypatch.setattr(graphify_ops, "_derive_prose", lambda *_a, **_k: 1)

    graphify_ops.merge_chunk(tmp_path, str(ext / "c-docs.json"))
    return seen[0]


def test_merge_chunk_passes_both_prior_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The INCREMENTAL path's half of #198 item 1.

    `_replay_doc_chunks` and `merge_chunk` build argv separately — the divergence
    that let the rebuild and incremental paths disagree in the first place — so
    each needs its own arm. Covering one and calling the feature done is how the
    node-only version survived a review that read only the other.
    """
    argv = _capture_merge_argv(tmp_path, monkeypatch, {"nodes": 100, "hyperedges": 11})

    assert argv[argv.index("--prior-nodes") + 1] == "100"
    assert argv[argv.index("--prior-hyperedges") + 1] == "11"


def test_merge_chunk_checks_the_half_it_can_when_the_ledger_is_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing `nodes` must not suppress an available `hyperedges`, or the reverse.

    This is the arm for passing the two flags INDEPENDENTLY rather than nesting the
    hyperedge emission inside the node `if`. `_derive_prose` records
    `{nodes, edges, hyperedges}` and not `members`, so a ledger entry carrying one
    slot and not another is a shape this repo already produces — and a nested
    version would go quiet on a check that was sitting right there.
    """
    only_nodes = _capture_merge_argv(tmp_path, monkeypatch, {"nodes": 100})
    assert only_nodes[only_nodes.index("--prior-nodes") + 1] == "100"
    assert "--prior-hyperedges" not in only_nodes


def test_record_survives_a_wrong_typed_payload(tmp_path: Path) -> None:
    """A best-effort recorder must not take its caller down.

    `int()` on a non-number raises, and this is called with whatever a
    foreign-interpreter subprocess wrote to a file — so `{"nodes": "many"}`
    crashed an otherwise-successful merge with an uncaught ValueError. Non-ints
    are dropped, so a partly usable payload records what it can.

    `True` is dropped too: `bool` IS an `int` in Python, so it would otherwise
    record as 1 — a count nobody measured, indistinguishable from one somebody
    did. (Cold lane, round 2, P2.)
    """
    g = tmp_path / "graphify-out" / "graph.json"
    g.parent.mkdir(parents=True)
    g.write_text("{}", encoding="utf-8")

    graph_counts.record(
        tmp_path, g, {"nodes": "many", "edges": 7, "hyperedges": True}, tag="kb-merge"
    )

    assert graph_counts.read(tmp_path, g) == {"edges": 7}


def test_a_corrupt_ledger_is_distinguishable_from_an_absent_one(tmp_path: Path) -> None:
    """`None` for corrupt, `[]` for absent — collapsing them re-opened the gap.

    Both returned an empty list, so a corrupt derived file silently narrowed a
    REFUSAL gate back to exactly the blind spot the ledger was added to close:
    unknown read as permission. (Cold lane, round 2, P1.)
    """
    out = tmp_path / "graphify-out"
    out.mkdir(parents=True)

    assert graph.merged_chunk_paths(tmp_path) == []

    (out / ".merged-chunks.json").write_text("{not json", encoding="utf-8")
    assert graph.merged_chunk_paths(tmp_path) is None


def test_a_corrupt_ledger_narrows_the_collision_set_out_loud(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """It may narrow the check; it may not do so in silence."""
    ext = tmp_path / "sources" / "extractions"
    _write_chunk(ext / "committed-docs.json", "committed.md")
    (tmp_path / "graphify-out").mkdir(parents=True)
    (tmp_path / "graphify-out" / ".merged-chunks.json").write_text("{not json", encoding="utf-8")

    found = {p.name for p in graphify_ops._committed_chunks(tmp_path)}

    assert found == {"committed-docs.json"}
    assert "unreadable" in capsys.readouterr().err
