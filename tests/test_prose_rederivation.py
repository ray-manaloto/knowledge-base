"""Every writer of `graph.json` must re-derive `graph-prose.json`.

The defect these pin down was invisible for the same reason it was expensive:
`graph-prose.json` is derived from `graph.json`, `kb-build` re-derives it, and a
merge-only ingestion did not — so `kb-query --prose`, the arm this repo
*recommends* for a question about the documents, went on answering from the
corpus as it stood before the merge, and the next unrelated `kb-build` quietly
repaired it. Nothing failed; the answers were just older than the graph.

The file is named for the CONTRACT rather than for `kb-merge`, because there are
two writers and fixing one of them is not a fix. `graphify label` rewrites
`graph.json` outright (installed 0.9.30, `graphify/cli.py:1546` -> :1836), and the
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
from kb_setup import graphify_ops, prose

if TYPE_CHECKING:
    from collections.abc import Sequence

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


def test_a_successful_label_re_derives_the_prose_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`kb-label` is the OTHER writer of graph.json, and the next workflow step.

    `graphify label` does not only touch sidecars — it ends in
    `to_json(G, communities, str(out / "graph.json"), …)` (installed 0.9.30,
    `graphify/cli.py:1836`, reached from the `label` branch at :1546 with no
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
