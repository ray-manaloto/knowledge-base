"""Every writer of `graph.json` must re-derive `graph-prose.json`.

The defect these pin down was invisible for the same reason it was expensive:
`graph-prose.json` is derived from `graph.json`, `kb-build` re-derives it, and a
merge-only ingestion did not — so `kb-query --prose`, the arm this repo
*recommends* for a question about the documents, went on answering from the
corpus as it stood before the merge, and the next unrelated `kb-build` quietly
repaired it. Nothing failed; the answers were just older than the graph.

The file is named for the CONTRACT rather than for `kb-merge`, because there are
two writers and fixing one of them is not a fix. `graphify label` rewrites
`graph.json` outright (installed 0.9.30, `graphify/cli.py:1546` -> :1830), and the
documented ingestion order is merge -> label — so a `merge_chunk` that re-derives
while `label` does not is undone by the very next step of the workflow it fixes.
That gap survived the first round of this change and was found by the cold lane.

So the load-bearing tests here are not "the wrapper returns the subprocess rc".
They are the success/failure PAIRS: without the failure arm, a function that
derives unconditionally passes the success arm just as happily — and would
replace a valid prose graph off the back of an operation that failed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from kb_setup import graphify_ops, hyperedges, prose, stamps
from kb_setup.currency import config, sync

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: What the stub writes as the merged graph: one AST node the derivation must
#: drop, and one prose node it must keep. Naming the merged node lets a test
#: assert the prose graph holds THIS merge rather than merely holding something.
_AST_NODE = {"id": "sym", "label": "sym", "_origin": "ast", "file_type": "code"}
_PROSE_NODE = {"id": "just_merged", "label": "just_merged", "file_type": "concept"}

_MERGED: dict[str, object] = {
    "graph": {"hyperedges": []},
    "nodes": [_AST_NODE, _PROSE_NODE],
    "links": [],
}

_PRE_MERGE: dict[str, object] = {
    "graph": {"hyperedges": []},
    "nodes": [{"id": "yesterday", "label": "yesterday", "file_type": "concept"}],
    "links": [],
}


def _repo(tmp_path: Path) -> Path:
    """A repo root with a pre-merge `graph.json` and a prose graph derived from it."""
    (tmp_path / "graphify-out").mkdir()
    (tmp_path / "graphify-out" / "graph.json").write_text(json.dumps(_PRE_MERGE), encoding="utf-8")
    prose.prose_graph_path(tmp_path).write_text(json.dumps(_PRE_MERGE), encoding="utf-8")
    return tmp_path


def _chunk(tmp_path: Path) -> str:
    """A chunk file on disk. Its CONTENT is irrelevant — the merge is stubbed."""
    path = tmp_path / "chunk.json"
    path.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")
    return str(path)


def _stub_graphify(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    rc: int,
    writes: dict[str, object] | None = None,
) -> None:
    """Stand in for whatever graphify subprocess the wrapper is about to run.

    The real things need graphify's bundled environment, which a unit test has no
    business standing up. What the stub reproduces is the part that matters to
    the caller: an rc, and whether `graph.json` changed underneath it.

    `graphify_exe` is pointed at a file that EXISTS, because `label()` gates on
    `Path(exe).is_file()` and would otherwise refuse before running anything —
    a test that passes because the binary was missing has tested the guard, not
    the labelling.
    """

    def fake_run(cmd: Sequence[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        if writes is not None:
            (tmp_path / "graphify-out" / "graph.json").write_text(
                json.dumps(writes), encoding="utf-8"
            )
        return subprocess.CompletedProcess(list(cmd), rc)

    exe = tmp_path / "graphify"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(graphify_ops, "graphify_python", lambda _root: "/nonexistent/python")
    monkeypatch.setattr(graphify_ops, "graphify_exe", lambda _root: str(exe))
    monkeypatch.setattr(graphify_ops.subprocess, "run", fake_run)


def _prose_ids(repo_root: Path) -> list[str]:
    """Node ids in the derived prose graph."""
    data = json.loads(prose.prose_graph_path(repo_root).read_text(encoding="utf-8"))
    return [str(n["id"]) for n in cast("list[dict[str, object]]", data["nodes"])]


def test_a_successful_merge_re_derives_the_prose_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The direction the fix exists for: `--prose` must see what was just merged.

    Asserting on the merged node's id, not on a count or an mtime: a count moves
    for a re-derivation of the OLD graph too, and an mtime moves for a file that
    was rewritten with identical content. The id is the only one of the three
    that cannot be satisfied by a derivation of the wrong corpus.
    """
    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 0
    assert _prose_ids(repo) == ["just_merged"]


def test_a_failed_merge_leaves_the_prose_graph_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: the derivation is gated on the merge's rc, not unconditional.

    The failing merge WRITES graph.json before it fails, and that detail is the
    whole test. Its first version let the stub leave graph.json byte-identical to
    the pre-merge state, so an unconditional derivation would have re-derived the
    *same* corpus and the assertion below would have passed anyway — a control arm
    that could not produce the other answer. Proved by mutation in cold-lane round
    1: removing the `rc != 0` gate left this test green.

    A merge that mutated the graph and then failed is also the realistic shape of
    the thing the gate defends against, which is why it is what the stub does now.
    """
    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=1, writes=_MERGED)

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 1
    assert _prose_ids(repo) == ["yesterday"]


def test_a_merge_whose_derivation_fails_does_not_report_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The chunk landed, the `--prose` arm did not. rc=0 would say otherwise.

    `prose.derive` unlinks first, so this leaves NO prose graph — the right
    artifact state (a stale one is indistinguishable from a fresh one to every
    consumer) reached by a path the caller has to be told about, because the
    graph really did change underneath them.
    """
    repo = _repo(tmp_path)
    # An all-AST graph: nothing survives the drop rule, so `derive` refuses.
    _stub_graphify(
        monkeypatch,
        tmp_path,
        rc=0,
        writes={"graph": {"hyperedges": []}, "nodes": [_AST_NODE], "links": []},
    )

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 1
    assert not prose.prose_graph_path(repo).exists()
    assert "kb-prose" in capsys.readouterr().err


def test_a_missing_chunk_is_refused_before_anything_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-existing behaviour, pinned so the new tail cannot start reaching it."""
    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.merge_chunk(repo, str(tmp_path / "absent.json")) == 2
    assert _prose_ids(repo) == ["yesterday"]


# --- recomposition ledger (#175) --------------------------------------------


def test_a_successful_merge_appends_to_the_recomposition_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The OTHER thing a fully-successful merge must do: extend the ledger.

    `kb-watch` can only replay what this records. A merge that succeeds and
    re-derives the prose graph but never reaches the ledger would be invisible
    to a later recomposition — silently dropping its content the moment
    `kb-watch` next runs, which is the exact failure the ledger exists to rule
    out.

    The recorded `chunk` is asserted CANONICALIZED — repo-root-relative here,
    since the fixture chunk sits under `repo` — not the raw absolute string
    `merge_chunk` was called with. `append_merged_chunk` resolves and
    relativizes before storing (#175 cold review round 2, the round-1
    finding 8 secondary item), so a later `_verified_ledger_chunks` agrees
    regardless of the cwd at append time or at verify time.
    """
    from kb_setup import graph

    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)
    chunk = _chunk(tmp_path)

    assert graphify_ops.merge_chunk(repo, chunk) == 0

    entries = graph._read_merged_chunks(repo)
    assert entries is not None
    assert [e.chunk for e in entries] == ["chunk.json"]
    assert entries[0].sha256 == graph._sha256_file(Path(chunk))


def test_a_failed_merge_does_not_touch_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: the ledger append is gated on rc, same as the prose re-derive.

    Without this gate, a failed merge that happened to leave a chunk file
    sitting on disk would still record a ledger entry for content that was
    never actually merged into graph.json.
    """
    from kb_setup import graph

    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=1, writes=_MERGED)
    chunk = _chunk(tmp_path)

    assert graphify_ops.merge_chunk(repo, chunk) == 1

    assert graph._read_merged_chunks(repo) == []


def test_a_merge_whose_ledger_write_fails_does_not_report_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The chunk merged and the prose graph re-derived, but the ledger did not extend.

    `rc=0` here would tell a caller that everything about this merge is
    durably recorded, when the one artifact `kb-watch` reads to recompose from
    just failed to extend — the same class of lie `_derive_prose`'s own gate
    exists to prevent, one step further down the same function.
    """
    from kb_setup import graph

    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)
    chunk = _chunk(tmp_path)

    def boom(_repo_root: Path, _chunk: str, _root: str) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(graph, "append_merged_chunk", boom)

    assert graphify_ops.merge_chunk(repo, chunk) == 1
    assert "recomposition ledger" in capsys.readouterr().err


def test_a_successful_label_re_derives_the_prose_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`kb-label` is the OTHER writer of graph.json, and the next workflow step.

    `graphify label` does not only touch sidecars — it ends in
    `to_json(G, communities, str(out / "graph.json"), …)` (installed 0.9.30,
    `graphify/cli.py:1830`, reached from the `label` branch at :1546 with no
    intervening branch). The documented order is merge -> label, so fixing only
    the merge would have left the prose graph stale again one step later, which
    is the whole failure this change exists to end.
    """
    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.label(repo) == 0
    assert _prose_ids(repo) == ["just_merged"]


def test_a_failed_label_leaves_the_prose_graph_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM for the label path — same shape, same reason, same rc gate."""
    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=1, writes=_MERGED)

    assert graphify_ops.label(repo) == 1
    assert _prose_ids(repo) == ["yesterday"]


# --- hyperedge carry (#171 local mitigation, #175) --------------------------

_HYPEREDGE = {"id": "he1", "nodes": ["just_merged", "yesterday"]}

_PRE_LABEL_WITH_HYPEREDGE: dict[str, object] = {
    "graph": {"hyperedges": [_HYPEREDGE]},
    "nodes": [{"id": "yesterday", "label": "yesterday", "file_type": "concept"}],
    "links": [],
    "hyperedges": [_HYPEREDGE],
}


def test_label_restores_hyperedges_the_round_trip_would_have_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bug this carry exists for, reproduced end to end through `label()`.

    `_MERGED` (the stub's `writes=`) carries no hyperedges in either slot —
    exactly what `build_from_json` + `to_json` leave on THIS repo's aggregate
    graph (measured 5->0; see `hyperedges.py`'s module docstring for the
    verified mechanism). Without the carry, `label()` would durably write that
    loss back to disk; with it, the pre-run list survives the round trip.
    """
    repo = _repo(tmp_path)
    (repo / "graphify-out" / "graph.json").write_text(
        json.dumps(_PRE_LABEL_WITH_HYPEREDGE), encoding="utf-8"
    )
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.label(repo) == 0

    on_disk = json.loads((repo / "graphify-out" / "graph.json").read_text(encoding="utf-8"))
    assert on_disk["hyperedges"] == [_HYPEREDGE]
    assert on_disk["graph"]["hyperedges"] == [_HYPEREDGE]


def test_a_failed_label_does_not_restore_hyperedges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: rc != 0 leaves whatever the failed run wrote untouched.

    Same reasoning as `test_a_failed_label_leaves_the_prose_graph_alone`: a
    failed run's graph.json is in an unknown state, and reattaching the
    captured pre-run list over it would assert a fact ("the run succeeded")
    that is false. Asserted as full-dict equality against `_MERGED` — the
    stub's exact output — so this fails if reattach touched ANY part of the
    file, not just the two hyperedge slots.
    """
    repo = _repo(tmp_path)
    (repo / "graphify-out" / "graph.json").write_text(
        json.dumps(_PRE_LABEL_WITH_HYPEREDGE), encoding="utf-8"
    )
    _stub_graphify(monkeypatch, tmp_path, rc=1, writes=_MERGED)

    assert graphify_ops.label(repo) == 1

    on_disk = json.loads((repo / "graphify-out" / "graph.json").read_text(encoding="utf-8"))
    assert on_disk == _MERGED


# --- currency stamp refresh (#179) -------------------------------------------
#
# `label()` rewrites graph.json wholesale (see the module docstring for the
# installed-0.9.30 citation), which is a REGENERATION exactly like
# `artifacts.generate`'s `report` entry — so it needs the same
# `kb_setup.stamps.refresh_after_regen` call, or every manual `mise run
# kb-label`, including the documented merge -> label curator flow, leaves
# `mise run kb-currency-check` reporting build-stamp drift until the next full
# `kb-build` (the fingerprint is `size:mtime_ns`, so ANY rewrite moves it).


def _with_currency_stamp(repo_root: Path) -> None:
    """Add a currency.toml + an existing stamp to a repo `_repo` already built.

    `_repo` already wrote the declared artifact (the pre-merge `graph.json`),
    which a stamp must fingerprint something that exists.
    """
    (repo_root / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'artifact = "graphify-out/graph.json"\n'
        'stamp = "graphify-out/.currency-stamp.json"\n',
        encoding="utf-8",
    )
    spec = config.load(repo_root)[0]
    sync.write_stamp(repo_root, spec, version="0.9.32")


def test_a_successful_label_refreshes_the_currency_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful `label()` must re-fingerprint graph.json, not leave it stale.

    Without this, `label()`'s rewrite moves the file's `size:mtime_ns` and step
    1 reports drift for a graph that was legitimately relabelled — the #179
    defect. Asserted as a real fingerprint comparison, not a spy, per the
    ticket's preference for a real assertion where the cost is affordable.
    """
    repo = _repo(tmp_path)
    _with_currency_stamp(repo)
    spec = config.load(repo)[0]
    before = sync.read_stamp(repo, spec)

    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    assert graphify_ops.label(repo) == 0

    after = sync.read_stamp(repo, spec)
    live_fp = sync.artifact_fingerprint(repo / "graphify-out" / "graph.json")
    before_fps = sync.stamped_fingerprints(before)
    after_fps = sync.stamped_fingerprints(after)
    assert after_fps["graphify-out/graph.json"] == live_fp
    assert before_fps["graphify-out/graph.json"] != after_fps["graphify-out/graph.json"]
    # version/source_ref are carried forward, not re-derived by a restamp —
    # `label()` never reads `sources/` and has no standing to restate them.
    assert after["version"] == before["version"] == "0.9.32"


def test_a_failed_label_does_not_refresh_the_currency_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: a failed label run must restamp nothing.

    graph.json may be in any state after a failed run, and stamping it would
    assert "this is the artifact the pin built" — a claim the same `rc != 0`
    gate that protects the hyperedge carry and the prose re-derivation
    (`_labelled`'s early `return rc`) also protects here.
    """
    repo = _repo(tmp_path)
    _with_currency_stamp(repo)
    spec = config.load(repo)[0]
    before = sync.read_stamp(repo, spec)

    _stub_graphify(monkeypatch, tmp_path, rc=1, writes=_MERGED)

    assert graphify_ops.label(repo) == 1

    after = sync.read_stamp(repo, spec)
    assert after == before


def test_label_restamps_after_reattach_not_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ordering requirement from #179: `reattach()` must run before the restamp.

    The stamp's fingerprint has to cover graph.json's FINAL bytes, and
    `reattach` is the last writer of that file — mirroring `artifacts.generate`,
    which orders capture -> subprocess -> reattach -> restamp for the same
    reason. Proven by call order, not by outcome: reading the fingerprint after
    `label()` returns reflects the final disk state regardless of which ran
    first, so an outcome-only assertion would pass even with the order flipped.
    """
    repo = _repo(tmp_path)
    (repo / "graphify-out" / "graph.json").write_text(
        json.dumps(_PRE_LABEL_WITH_HYPEREDGE), encoding="utf-8"
    )
    _with_currency_stamp(repo)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    calls: list[str] = []
    real_reattach = hyperedges.reattach
    real_refresh = stamps.refresh_after_regen

    def spy_reattach(graph_path: Path, edges: Sequence[Mapping[str, object]]) -> None:
        calls.append("reattach")
        real_reattach(graph_path, edges)

    def spy_refresh(repo_root: Path, *, tag: str) -> None:
        calls.append("refresh")
        real_refresh(repo_root, tag=tag)

    monkeypatch.setattr(hyperedges, "reattach", spy_reattach)
    monkeypatch.setattr(stamps, "refresh_after_regen", spy_refresh)

    assert graphify_ops.label(repo) == 0
    assert calls == ["reattach", "refresh"], f"restamp must run after reattach; got {calls}"


def test_an_interrupted_write_leaves_no_partial_prose_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reader must never see a half-written prose graph, only present or absent.

    `kb-query --prose` checks `.is_file()` and hands the path to graphify, so a
    write that is visible before it is complete can be read mid-serialisation.
    Writing straight into the destination held that window open for as long as a
    full dump of the corpus, and this path is now reached on every merge and every
    label rather than only on a build. (Cold lane, round 1.)

    The failure is injected at `json.dump`, which is where a real interruption
    (disk full, SIGKILL, a broken pipe) lands — not at a wrapper that would prove
    only that the wrapper was called.
    """
    src = tmp_path / "graph.json"
    src.write_text(json.dumps(_MERGED), encoding="utf-8")
    out = tmp_path / prose.PROSE_GRAPH_NAME

    def boom(*_: object, **__: object) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(prose.json, "dump", boom)
    with pytest.raises(OSError, match="no space"):
        prose.derive(src, out)

    assert not out.exists(), "a partial write was left where a reader would find it"
    assert list(tmp_path.glob("*.tmp")) == [], "the temp file outlived the failure"


def test_a_write_failure_becomes_an_rc_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An `OSError` from the derivation must reach the caller as rc=1 and a message.

    The wrapper caught `ValueError` and `SystemExit` and not this — so a full disk
    during a `kb-merge` surfaced as an unhandled traceback rather than the line
    telling you `--prose` now has no corpus. The gap was visible from inside this
    very file, which already injects an `OSError` against `prose.derive` one test
    up. (Cold lane, round 2.)
    """
    repo = _repo(tmp_path)
    _stub_graphify(monkeypatch, tmp_path, rc=0, writes=_MERGED)

    def boom(*_: object, **__: object) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(prose.json, "dump", boom)

    assert graphify_ops.merge_chunk(repo, _chunk(tmp_path)) == 1
    assert "kb-prose" in capsys.readouterr().err


def test_a_derivation_does_not_clobber_another_ones_temp_file(tmp_path: Path) -> None:
    """Two concurrent derivations must not share one temp path.

    A temp name derived from `out_path` is the SAME path for every caller, so two
    derivations running at once write into one file and each `replace` a graph the
    other half-wrote — a torn WRITE in place of the torn read the temp file was
    added to prevent. (Cold lane, round 2.)

    Stated as the harm rather than as "mkstemp was called": the decoy stands in
    for another derivation's in-flight temp file, and a fixed-name implementation
    both overwrites it and then renames it away, so it fails on the read below
    rather than on an implementation detail it might satisfy some other way.
    """
    src = tmp_path / "graph.json"
    src.write_text(json.dumps(_MERGED), encoding="utf-8")
    out = tmp_path / prose.PROSE_GRAPH_NAME

    inflight = "another derivation is part-way through writing this"
    decoy = out.with_name(out.name + ".tmp")
    decoy.write_text(inflight, encoding="utf-8")

    prose.derive(src, out)

    assert decoy.exists(), "the other derivation's temp file was renamed away"
    assert decoy.read_text(encoding="utf-8") == inflight, "it was written over"
    derived = json.loads(out.read_text(encoding="utf-8"))
    ids = [str(n["id"]) for n in cast("list[dict[str, object]]", derived["nodes"])]
    assert ids == ["just_merged"], "the derivation itself did not land"
