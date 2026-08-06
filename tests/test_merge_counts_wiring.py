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

from kb_setup import graph, graph_counts, graphify_ops

if TYPE_CHECKING:
    import pytest


def _handoff(tmp_path: Path, body: str) -> Path:
    p = tmp_path / ".merge-counts.tmp.json"
    p.write_text(body, encoding="utf-8")
    return p


def test_handoff_nodes_reads_then_consumes(tmp_path: Path) -> None:
    """One read, then unknown. A prior count must never outlive its own chunk."""
    h = _handoff(tmp_path, json.dumps({"nodes": 42, "edges": 7}))

    assert graph._handoff_nodes(h) == 42
    assert not h.exists()
    assert graph._handoff_nodes(h) is None


def test_handoff_nodes_consumes_even_when_unusable(tmp_path: Path) -> None:
    """A malformed handoff is removed too, so the NEXT chunk cannot inherit it.

    Returning None while leaving the file behind would be the worst of both:
    this chunk reports "not checked", and the chunk after it reads a count
    belonging to neither.
    """
    for body in ("{not json", "[]", '{"nodes": "many"}', "{}"):
        h = _handoff(tmp_path, body)
        assert graph._handoff_nodes(h) is None, body
        assert not h.exists(), body


def test_handoff_nodes_on_a_missing_file_is_unknown(tmp_path: Path) -> None:
    assert graph._handoff_nodes(tmp_path / "never-written.json") is None


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
    counter = iter((10, 25, 40))

    def _fake_run(argv: list[str], _cwd: Path) -> None:
        seen.append(argv)
        Path(argv[argv.index("--counts-out") + 1]).write_text(
            json.dumps({"nodes": next(counter)}), encoding="utf-8"
        )

    monkeypatch.setattr(graph, "_run", _fake_run)
    graph._replay_doc_chunks(
        tmp_path, "py", tmp_path / "sources", out, sorted(chunks_dir.glob("*.json"))
    )

    priors = [
        argv[argv.index("--prior-nodes") + 1] if "--prior-nodes" in argv else None for argv in seen
    ]
    assert priors == [None, "10", "25"]
    assert not out.with_name(".merge-counts.tmp.json").exists()


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
